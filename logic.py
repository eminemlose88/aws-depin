import boto3
import time

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
