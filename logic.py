import boto3
import time
import datetime
from botocore.exceptions import ClientError

# Amazon Linux 2023 AMI IDs (x86_64)
# Note: These IDs change over time. Users should verify valid AMIs for their region.
AMI_MAPPING = {
    'us-east-1': 'ami-0230bd60aa48260c6',
    'us-east-2': 'ami-06d4b7182ac3480fa',
    'us-west-2': 'ami-093467ec28ae4fe03',
    'ap-northeast-1': 'ami-012261b9035f8f938'
}

def ensure_security_group(ec2_client):
    """
    Ensure a security group 'DePIN-Launcher-SG' exists and allows SSH.
    Returns the GroupId.
    """
    sg_name = 'DePIN-Launcher-SG'
    try:
        # Check if SG exists
        response = ec2_client.describe_security_groups(GroupNames=[sg_name])
        return response['SecurityGroups'][0]['GroupId']
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidGroup.NotFound':
            # Create SG
            try:
                response = ec2_client.create_security_group(
                    GroupName=sg_name,
                    Description='Allow SSH and Project ports for DePIN Launcher'
                )
                sg_id = response['GroupId']
                
                # Add Inbound Rules
                ec2_client.authorize_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=[
                        {
                            'IpProtocol': 'tcp',
                            'FromPort': 22,
                            'ToPort': 22,
                            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                        },
                        # Optional: Allow HTTP/HTTPS for some projects
                        {
                            'IpProtocol': 'tcp',
                            'FromPort': 80,
                            'ToPort': 80,
                            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                        },
                         {
                            'IpProtocol': 'tcp',
                            'FromPort': 443,
                            'ToPort': 443,
                            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                        }
                    ]
                )
                return sg_id
            except Exception as create_err:
                print(f"Failed to create SG: {create_err}")
                return None
        else:
            print(f"Error checking SG: {e}")
            return None

def launch_instance(ak, sk, region, user_data, project_name):
    """
    Launch an EC2 instance with a new unique key pair.
    Returns status, instance info, and the PRIVATE KEY content.
    """
    if region not in AMI_MAPPING:
        return {'status': 'error', 'msg': f'Region {region} not supported or AMI not defined.'}

    ami_id = AMI_MAPPING[region]

    try:
        # Create session and client
        session = boto3.Session(
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            region_name=region
        )
        ec2 = session.client('ec2')

        # 1. Create Key Pair
        # Unique name based on project and timestamp
        timestamp = int(time.time())
        key_name = f"depin-key-{project_name}-{timestamp}"
        
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
        # t2.micro, auto-assign public IP, bind the new key pair
        response = ec2.run_instances(
            ImageId=ami_id,
            InstanceType='t2.micro',
            MinCount=1,
            MaxCount=1,
            KeyName=key_name, # Bind the key
            SecurityGroupIds=[sg_id], # Bind the Security Group
            UserData=user_data,
            NetworkInterfaces=[{
                'DeviceIndex': 0,
                'AssociatePublicIpAddress': True,
                'Groups': [sg_id] # Must specify groups here if using NetworkInterfaces
            }],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': f'{project_name}-Worker'},
                    {'Key': 'Project', 'Value': project_name}
                ]
            }]
        )

        instance_id = response['Instances'][0]['InstanceId']

        # Wait for the instance to be in 'running' state to get the Public IP
        # This might take a short while
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])

        # Describe instance to retrieve Public IP
        desc_response = ec2.describe_instances(InstanceIds=[instance_id])
        instance_data = desc_response['Reservations'][0]['Instances'][0]
        public_ip = instance_data.get('PublicIpAddress', 'N/A')

        return {
            'status': 'success',
            'ip': public_ip,
            'id': instance_id,
            'msg': 'Instance launched successfully.',
            'private_key': private_key # Return the private key for storage
        }

    except Exception as e:
        return {'status': 'error', 'msg': str(e)}

def get_instance_status(ak, sk, region, instance_ids):
    """
    Get the real-time status of specified instances from AWS.
    Returns a dictionary mapping instance_id to state (e.g., 'running', 'terminated').
    """
    if not instance_ids:
        return {}

    try:
        session = boto3.Session(
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            region_name=region
        )
        ec2 = session.client('ec2')

        response = ec2.describe_instances(InstanceIds=instance_ids)
        
        status_map = {}
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                status_map[instance['InstanceId']] = instance['State']['Name']
        
        return status_map

    except Exception as e:
        print(f"Error fetching instance status for region {region}: {e}")
        return {}

def scan_all_instances(ak, sk, region):
    """
    Scan ALL instances in the specified region.
    Returns a list of dictionaries with instance details.
    """
    try:
        session = boto3.Session(
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            region_name=region
        )
        ec2 = session.client('ec2')

        # List all instances, not just running ones, to catch stopped/terminated
        response = ec2.describe_instances()
        
        instances = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                # Extract Project tag if exists
                project_name = 'Unknown'
                if 'Tags' in instance:
                    for tag in instance['Tags']:
                        if tag['Key'] == 'Project':
                            project_name = tag['Value']
                            break
                
                instances.append({
                    'instance_id': instance['InstanceId'],
                    'status': instance['State']['Name'],
                    'ip_address': instance.get('PublicIpAddress', None),
                    'project_name': project_name,
                    'region': region
                })
        
        return instances

    except Exception as e:
        print(f"Error scanning region {region}: {e}")
        return []

def terminate_instance(ak, sk, region, instance_id):
    """
    Terminate an EC2 instance.
    """
    try:
        session = boto3.Session(
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            region_name=region
        )
        ec2 = session.client('ec2')

        ec2.terminate_instances(InstanceIds=[instance_id])
        return {'status': 'success', 'msg': f'Instance {instance_id} terminating...'}

    except Exception as e:
        return {'status': 'error', 'msg': str(e)}

def check_account_health(ak, sk):
    """
    Perform a health check on the AWS account by attempting a lightweight API call (describe_regions).
    Returns a dict with 'status' (active/suspended/error) and 'msg'.
    """
    try:
        # Use us-east-1 as default for health check
        session = boto3.Session(
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            region_name='us-east-1'
        )
        ec2 = session.client('ec2')
        
        # Try a lightweight call
        ec2.describe_regions(DryRun=False)
        
        return {'status': 'active', 'msg': 'Normal'}
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        
        if error_code == 'AuthFailure':
            return {'status': 'error', 'msg': 'Invalid Credentials'}
        elif error_code == 'OptInRequired':
            return {'status': 'suspended', 'msg': 'Account Pending Verification (OptInRequired)'}
        elif 'Verification' in error_msg or 'Suspended' in error_msg:
             return {'status': 'suspended', 'msg': 'Account Suspended'}
        else:
             return {'status': 'error', 'msg': f'{error_code}: {error_msg}'}
             
    except Exception as e:
        return {'status': 'error', 'msg': str(e)}
