import boto3
import time
import datetime
from botocore.exceptions import ClientError
from botocore.config import Config

# Amazon Linux 2023 AMI IDs (x86_64)
AMI_MAPPING = {
    'us-east-1': 'ami-0230bd60aa48260c6',
    'us-east-2': 'ami-06d4b7182ac3480fa',
    'us-west-2': 'ami-093467ec28ae4fe03',
    'ap-northeast-1': 'ami-012261b9035f8f938'
}

# Ubuntu 22.04 LTS AMI IDs (x86_64)
AMI_MAPPING_UBUNTU = {
    'us-east-1': 'ami-0c7217cdde317cfec',
    'us-east-2': 'ami-05fb0b8c1424f266b',
    'us-west-2': 'ami-008fe2fc65df48dac',
    'ap-northeast-1': 'ami-0270a6a090e4a3225'
}

def get_vcpu_quota(ak, sk, region, proxy_url=None):
    """
    Get the vCPU quota for 'Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances'.
    Returns: limit (int)
    """
    config = Config(proxies={'https': proxy_url, 'http': proxy_url}) if proxy_url else None
    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
        client = session.client('service-quotas', config=config)
        
        # Quota Code for Running On-Demand Standard instances
        quota_code = 'L-1216C47A' 
        service_code = 'ec2'
        
        response = client.get_service_quota(ServiceCode=service_code, QuotaCode=quota_code)
        limit = int(response['Quota']['Value'])
        return limit
    except Exception as e:
        # Fallback or error handling
        # print(f"Quota check failed: {e}")
        # Try legacy method if service-quotas fails (e.g. permission issue)
        try:
            session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
            ec2 = session.client('ec2', config=config)
            # This attribute is often not accurate for vCPU limits but better than nothing
            # Actually, better to default to a safe value like 32 if we can't read it
            return 32 
        except:
            return 0

def get_current_usage(ak, sk, region, proxy_url=None):
    """
    Count current vCPU usage by summing up vCPUs of all running instances.
    Returns: usage (int)
    """
    config = Config(proxies={'https': proxy_url, 'http': proxy_url}) if proxy_url else None
    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
        ec2 = session.client('ec2', config=config)
        
        response = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'pending']}]
        )
        
        total_vcpus = 0
        for r in response['Reservations']:
            for i in r['Instances']:
                # Calculate vCPU based on CpuOptions (CoreCount * ThreadsPerCore)
                # or fallback to safe defaults for known types if missing
                vcpus = 1
                if 'CpuOptions' in i:
                    core_count = i['CpuOptions'].get('CoreCount', 1)
                    threads_per_core = i['CpuOptions'].get('ThreadsPerCore', 1)
                    vcpus = core_count * threads_per_core
                else:
                    # Fallback heuristic
                    itype = i.get('InstanceType', 't2.micro')
                    if 'xlarge' in itype: vcpus = 4
                    elif 'large' in itype: vcpus = 2
                    elif 'medium' in itype: vcpus = 2
                    else: vcpus = 1
                
                total_vcpus += vcpus
                
        return total_vcpus
    except Exception:
        return 0

def check_capacity(ak, sk, region, proxy_url=None):
    """
    Check available capacity for new instances.
    Returns: {limit, used, available}
    """
    limit = get_vcpu_quota(ak, sk, region, proxy_url)
    used = get_current_usage(ak, sk, region, proxy_url)
    # Assuming we launch 1 vCPU instances
    available = limit - used
    return {
        "limit": limit,
        "used": used,
        "available": max(0, available)
    }

def ensure_security_group(ec2_client):
    """
    Ensure a security group 'DePIN-Launcher-SG' exists and allows SSH.
    """
    sg_name = 'DePIN-Launcher-SG'
    try:
        response = ec2_client.describe_security_groups(GroupNames=[sg_name])
        return response['SecurityGroups'][0]['GroupId']
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidGroup.NotFound':
            try:
                response = ec2_client.create_security_group(
                    GroupName=sg_name,
                    Description='Allow SSH and Project ports for DePIN Launcher'
                )
                sg_id = response['GroupId']
                ec2_client.authorize_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=[
                        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        # Shardeum Ports
                        {'IpProtocol': 'tcp', 'FromPort': 8080, 'ToPort': 8080, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 9001, 'ToPort': 9001, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 10001, 'ToPort': 10001, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        # Babylon Ports
                        {'IpProtocol': 'tcp', 'FromPort': 26656, 'ToPort': 26657, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        # SOCKS5 Proxy
                        {'IpProtocol': 'tcp', 'FromPort': 1080, 'ToPort': 1080, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        # Squid HTTP Proxy
                        {'IpProtocol': 'tcp', 'FromPort': 3128, 'ToPort': 3128, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
                    ]
                )
                return sg_id
            except Exception as create_err:
                print(f"Failed to create SG: {create_err}")
                return None
        return None

def launch_base_instance(ak, sk, region, instance_type='t2.micro', image_type='al2023', volume_size=8, volume_type='gp3', proxy_url=None):
    """
    Step 1: Launch a base EC2 instance (Pure OS).
    Returns: {status, ip, id, private_key, msg}
    """
    ami_id = None
    if image_type == 'ubuntu':
        if region not in AMI_MAPPING_UBUNTU:
            return {'status': 'error', 'msg': f'Region {region} not supported for Ubuntu.'}
        ami_id = AMI_MAPPING_UBUNTU[region]
        user_name = "ubuntu"
    else:
        if region not in AMI_MAPPING:
            return {'status': 'error', 'msg': f'Region {region} not supported for Amazon Linux.'}
        ami_id = AMI_MAPPING[region]
        user_name = "ec2-user"

    config = Config(proxies={'https': proxy_url, 'http': proxy_url}) if proxy_url else None

    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
        ec2 = session.client('ec2', config=config)

        # 0. Get Root Device Name for AMI
        try:
            img_desc = ec2.describe_images(ImageIds=[ami_id])
            root_device_name = img_desc['Images'][0]['RootDeviceName']
        except Exception:
            root_device_name = '/dev/xvda' # Fallback

        # 1. Create Key Pair
        timestamp = int(time.time())
        key_name = f"depin-base-{timestamp}"
        
        try:
            key_pair = ec2.create_key_pair(KeyName=key_name)
            private_key = key_pair['KeyMaterial']
        except ClientError as e:
            return {'status': 'error', 'msg': f"Failed to create Key Pair: {e}"}
            
        # 2. Ensure Security Group
        sg_id = ensure_security_group(ec2)
        if not sg_id:
             return {'status': 'error', 'msg': "Failed to configure Security Group."}

        # 3. Launch instance
        # UserData to install basic tools (Docker, SSM Agent)
        # Adapt for Ubuntu vs AL2023
        if image_type == 'ubuntu':
            base_user_data = """#!/bin/bash
apt-get update -y
apt-get install -y docker.io
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu
"""
        else:
            base_user_data = """#!/bin/bash
yum update -y
yum install -y docker
service docker start
usermod -a -G docker ec2-user
systemctl enable docker
"""
        # Block Device Mapping for Root Volume
        block_device_mappings = [
            {
                'DeviceName': root_device_name,
                'Ebs': {
                    'VolumeSize': int(volume_size),
                    'VolumeType': volume_type,
                    'DeleteOnTermination': True
                }
            }
        ]

        response = ec2.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            KeyName=key_name,
            UserData=base_user_data,
            BlockDeviceMappings=block_device_mappings,
            NetworkInterfaces=[{
                'DeviceIndex': 0,
                'AssociatePublicIpAddress': True,
                'Groups': [sg_id]
            }],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': 'Base-Worker'},
                    {'Key': 'Project', 'Value': 'Pending'} 
                ]
            }]
        )

        instance_id = response['Instances'][0]['InstanceId']

        # Wait for running
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])

        # Get IP
        desc_response = ec2.describe_instances(InstanceIds=[instance_id])
        instance_data = desc_response['Reservations'][0]['Instances'][0]
        public_ip = instance_data.get('PublicIpAddress', 'N/A')

        return {
            'status': 'success',
            'ip': public_ip,
            'id': instance_id,
            'msg': 'Base Instance launched.',
            'private_key': private_key
        }

    except Exception as e:
        return {'status': 'error', 'msg': str(e)}

# Re-export other functions for compatibility
def get_instance_status(ak, sk, region, instance_ids, proxy_url=None):
    """Get status."""
    if not instance_ids: return {}
    config = Config(proxies={'https': proxy_url, 'http': proxy_url}) if proxy_url else None
    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
        ec2 = session.client('ec2', config=config)
        response = ec2.describe_instances(InstanceIds=instance_ids)
        status_map = {}
        for r in response['Reservations']:
            for i in r['Instances']:
                status_map[i['InstanceId']] = i['State']['Name']
        return status_map
    except Exception as e:
        return {}

def scan_all_instances(ak, sk, region, proxy_url=None):
    """Scan all instances."""
    config = Config(proxies={'https': proxy_url, 'http': proxy_url}) if proxy_url else None
    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
        ec2 = session.client('ec2', config=config)
        response = ec2.describe_instances()
        instances = []
        for r in response['Reservations']:
            for i in r['Instances']:
                p_name = 'Unknown'
                if 'Tags' in i:
                    for t in i['Tags']:
                        if t['Key'] == 'Project':
                            p_name = t['Value']
                            break
                instances.append({
                    'instance_id': i['InstanceId'],
                    'status': i['State']['Name'],
                    'ip_address': i.get('PublicIpAddress', None),
                    'project_name': p_name,
                    'region': region,
                    'instance_type': i.get('InstanceType', 'Unknown')
                })
        return instances
    except Exception:
        return []

def terminate_instance(ak, sk, region, instance_id, proxy_url=None):
    """Terminate instance."""
    config = Config(proxies={'https': proxy_url, 'http': proxy_url}) if proxy_url else None
    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
        ec2 = session.client('ec2', config=config)
        ec2.terminate_instances(InstanceIds=[instance_id])
        return {'status': 'success', 'msg': 'Terminating...'}
    except Exception as e:
        return {'status': 'error', 'msg': str(e)}

def check_account_health(ak, sk, proxy_url=None):
    """Health check."""
    config = Config(proxies={'https': proxy_url, 'http': proxy_url}) if proxy_url else None
    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name='us-east-1')
        ec2 = session.client('ec2', config=config)
        ec2.describe_regions(DryRun=False)
        return {'status': 'active', 'msg': 'Normal'}
    except ClientError as e:
        c = e.response['Error']['Code']
        if c == 'AuthFailure': return {'status': 'error', 'msg': 'Invalid Credentials'}
        elif c == 'OptInRequired': return {'status': 'suspended', 'msg': 'OptInRequired'}
        elif 'Suspended' in str(e): return {'status': 'suspended', 'msg': 'Suspended'}
        else: return {'status': 'error', 'msg': str(e)}
    except Exception as e:
        return {'status': 'error', 'msg': str(e)}

# --- Deprecated but kept for compatibility if needed ---
def launch_instance(ak, sk, region, user_data, project_name, proxy_url=None):
    """Wrapper for backward compatibility or direct launch."""
    return launch_base_instance(ak, sk, region, proxy_url)
