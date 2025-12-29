import boto3
import time
import datetime
from botocore.exceptions import ClientError

# Amazon Linux 2023 AMI IDs (x86_64)
AMI_MAPPING = {
    'us-east-1': 'ami-0230bd60aa48260c6',
    'us-east-2': 'ami-06d4b7182ac3480fa',
    'us-west-2': 'ami-093467ec28ae4fe03',
    'ap-northeast-1': 'ami-012261b9035f8f938'
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
                        {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
                    ]
                )
                return sg_id
            except Exception as create_err:
                print(f"Failed to create SG: {create_err}")
                return None
        return None

def launch_base_instance(ak, sk, region):
    """
    Step 1: Launch a base EC2 instance (Pure OS).
    Returns: {status, ip, id, private_key, msg}
    """
    if region not in AMI_MAPPING:
        return {'status': 'error', 'msg': f'Region {region} not supported.'}

    ami_id = AMI_MAPPING[region]

    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
        ec2 = session.client('ec2')

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
        base_user_data = """#!/bin/bash
yum update -y
yum install -y docker
service docker start
usermod -a -G docker ec2-user
systemctl enable docker
"""
        response = ec2.run_instances(
            ImageId=ami_id,
            InstanceType='t2.micro',
            MinCount=1,
            MaxCount=1,
            KeyName=key_name,
            UserData=base_user_data,
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
def get_instance_status(ak, sk, region, instance_ids):
    """Get status."""
    if not instance_ids: return {}
    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
        ec2 = session.client('ec2')
        response = ec2.describe_instances(InstanceIds=instance_ids)
        status_map = {}
        for r in response['Reservations']:
            for i in r['Instances']:
                status_map[i['InstanceId']] = i['State']['Name']
        return status_map
    except Exception as e:
        return {}

def scan_all_instances(ak, sk, region):
    """Scan all instances."""
    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
        ec2 = session.client('ec2')
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
                    'region': region
                })
        return instances
    except Exception:
        return []

def terminate_instance(ak, sk, region, instance_id):
    """Terminate instance."""
    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)
        ec2 = session.client('ec2')
        ec2.terminate_instances(InstanceIds=[instance_id])
        return {'status': 'success', 'msg': 'Terminating...'}
    except Exception as e:
        return {'status': 'error', 'msg': str(e)}

def check_account_health(ak, sk):
    """Health check."""
    try:
        session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name='us-east-1')
        ec2 = session.client('ec2')
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
def launch_instance(ak, sk, region, user_data, project_name):
    """Wrapper for backward compatibility or direct launch."""
    return launch_base_instance(ak, sk, region)
