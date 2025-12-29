import boto3
import time
from botocore.exceptions import ClientError

# Amazon Linux 2023 AMI IDs (x86_64)
# Note: These IDs change over time. Users should verify valid AMIs for their region.
AMI_MAPPING = {
    'us-east-1': 'ami-0230bd60aa48260c6',
    'us-east-2': 'ami-06d4b7182ac3480fa',
    'us-west-2': 'ami-093467ec28ae4fe03',
    'ap-northeast-1': 'ami-012261b9035f8f938'
}

def launch_instance(ak, sk, region, user_data, project_name):
    """
    Launch an EC2 instance and return status.
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

        # Launch instance
        # t2.micro, auto-assign public IP, no key pair
        response = ec2.run_instances(
            ImageId=ami_id,
            InstanceType='t2.micro',
            MinCount=1,
            MaxCount=1,
            UserData=user_data,
            NetworkInterfaces=[{
                'DeviceIndex': 0,
                'AssociatePublicIpAddress': True,
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
            'msg': 'Instance launched successfully.'
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
