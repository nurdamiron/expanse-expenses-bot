#!/usr/bin/env python3
"""Direct AWS deployment using boto3"""

import os
import sys
import time
import json
import boto3
from botocore.exceptions import ClientError

# Configuration
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
AWS_ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID')
PROJECT_NAME = "expanse-expenses-bot"

# Validate credentials
if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_ACCOUNT_ID]):
    print("Error: AWS credentials not found. Please set:")
    print("  - AWS_ACCESS_KEY_ID")
    print("  - AWS_SECRET_ACCESS_KEY")
    print("  - AWS_ACCOUNT_ID")
    sys.exit(1)

# Load .env file
def load_env():
    env_vars = {}
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

# Initialize AWS clients
session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

ec2 = session.client('ec2')
ecs = session.client('ecs')
ecr = session.client('ecr')
logs = session.client('logs')
iam = session.client('iam')

def create_iam_role():
    """Create IAM role for ECS task execution"""
    role_name = f"{PROJECT_NAME}-task-execution-role"
    
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ecs-tasks.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        # Create role
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='ECS task execution role for Expanse Expenses Bot'
        )
        print(f"Created IAM role: {role_name}")
        
        # Attach policies
        policies = [
            'arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy',
            'arn:aws:iam::aws:policy/CloudWatchLogsFullAccess'
        ]
        
        for policy in policies:
            iam.attach_role_policy(RoleName=role_name, PolicyArn=policy)
            
        # Wait for role to propagate
        time.sleep(10)
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"IAM role {role_name} already exists")
        else:
            raise
    
    return f"arn:aws:iam::{AWS_ACCOUNT_ID}:role/{role_name}"

def create_vpc_resources():
    """Create VPC and related resources"""
    vpc_name = f"{PROJECT_NAME}-vpc"
    
    # Check if VPC already exists
    vpcs = ec2.describe_vpcs(Filters=[{'Name': 'tag:Name', 'Values': [vpc_name]}])
    
    if vpcs['Vpcs']:
        vpc_id = vpcs['Vpcs'][0]['VpcId']
        print(f"Using existing VPC: {vpc_id}")
    else:
        # Create VPC
        vpc = ec2.create_vpc(CidrBlock='10.0.0.0/16')
        vpc_id = vpc['Vpc']['VpcId']
        
        # Wait for VPC to be available
        ec2.get_waiter('vpc_available').wait(VpcIds=[vpc_id])
        
        # Tag VPC
        ec2.create_tags(Resources=[vpc_id], Tags=[{'Key': 'Name', 'Value': vpc_name}])
        
        # Enable DNS hostnames
        ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={'Value': True})
        
        print(f"Created VPC: {vpc_id}")
    
    # Create Internet Gateway
    igws = ec2.describe_internet_gateways(
        Filters=[{'Name': 'tag:Name', 'Values': [f"{PROJECT_NAME}-igw"]}]
    )
    
    if igws['InternetGateways']:
        igw_id = igws['InternetGateways'][0]['InternetGatewayId']
        print(f"Using existing Internet Gateway: {igw_id}")
    else:
        igw = ec2.create_internet_gateway()
        igw_id = igw['InternetGateway']['InternetGatewayId']
        ec2.create_tags(Resources=[igw_id], Tags=[{'Key': 'Name', 'Value': f"{PROJECT_NAME}-igw"}])
        ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        print(f"Created Internet Gateway: {igw_id}")
    
    # Create subnets
    subnet_ids = []
    availability_zones = ec2.describe_availability_zones()['AvailabilityZones']
    
    for i, az in enumerate(availability_zones[:2]):  # Use first 2 AZs
        subnet_name = f"{PROJECT_NAME}-subnet-{i+1}"
        subnets = ec2.describe_subnets(
            Filters=[
                {'Name': 'tag:Name', 'Values': [subnet_name]},
                {'Name': 'vpc-id', 'Values': [vpc_id]}
            ]
        )
        
        if subnets['Subnets']:
            subnet_id = subnets['Subnets'][0]['SubnetId']
            print(f"Using existing subnet: {subnet_id}")
        else:
            subnet = ec2.create_subnet(
                VpcId=vpc_id,
                CidrBlock=f'10.0.{i+1}.0/24',
                AvailabilityZone=az['ZoneName']
            )
            subnet_id = subnet['Subnet']['SubnetId']
            ec2.create_tags(Resources=[subnet_id], Tags=[{'Key': 'Name', 'Value': subnet_name}])
            
            # Enable auto-assign public IP
            ec2.modify_subnet_attribute(
                SubnetId=subnet_id,
                MapPublicIpOnLaunch={'Value': True}
            )
            print(f"Created subnet: {subnet_id}")
        
        subnet_ids.append(subnet_id)
    
    # Create or update route table
    route_tables = ec2.describe_route_tables(
        Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
    )
    
    route_table_id = route_tables['RouteTables'][0]['RouteTableId']
    
    # Add internet gateway route
    try:
        ec2.create_route(
            RouteTableId=route_table_id,
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=igw_id
        )
        print("Added route to Internet Gateway")
    except ClientError as e:
        if e.response['Error']['Code'] == 'RouteAlreadyExists':
            print("Route to Internet Gateway already exists")
        else:
            raise
    
    # Associate subnets with route table
    for subnet_id in subnet_ids:
        try:
            ec2.associate_route_table(SubnetId=subnet_id, RouteTableId=route_table_id)
        except ClientError as e:
            if 'already associated' in str(e):
                print(f"Subnet {subnet_id} already associated with route table")
            else:
                raise
    
    # Create security group
    sg_name = f"{PROJECT_NAME}-sg"
    sgs = ec2.describe_security_groups(
        Filters=[
            {'Name': 'group-name', 'Values': [sg_name]},
            {'Name': 'vpc-id', 'Values': [vpc_id]}
        ]
    )
    
    if sgs['SecurityGroups']:
        security_group_id = sgs['SecurityGroups'][0]['GroupId']
        print(f"Using existing security group: {security_group_id}")
    else:
        sg = ec2.create_security_group(
            GroupName=sg_name,
            Description='Security group for Expanse Expenses Bot',
            VpcId=vpc_id
        )
        security_group_id = sg['GroupId']
        
        # Add egress rule for all traffic
        ec2.authorize_security_group_egress(
            GroupId=security_group_id,
            IpPermissions=[{
                'IpProtocol': '-1',
                'FromPort': -1,
                'ToPort': -1,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            }]
        )
        print(f"Created security group: {security_group_id}")
    
    return vpc_id, subnet_ids, security_group_id

def create_ecr_repository():
    """Create ECR repository"""
    try:
        response = ecr.create_repository(repositoryName=PROJECT_NAME)
        repository_uri = response['repository']['repositoryUri']
        print(f"Created ECR repository: {repository_uri}")
        return repository_uri
    except ClientError as e:
        if e.response['Error']['Code'] == 'RepositoryAlreadyExistsException':
            response = ecr.describe_repositories(repositoryNames=[PROJECT_NAME])
            repository_uri = response['repositories'][0]['repositoryUri']
            print(f"Using existing ECR repository: {repository_uri}")
            return repository_uri
        else:
            raise

def create_ecs_cluster():
    """Create ECS cluster"""
    cluster_name = f"{PROJECT_NAME}-cluster"
    
    try:
        ecs.create_cluster(clusterName=cluster_name)
        print(f"Created ECS cluster: {cluster_name}")
    except ClientError as e:
        print(f"ECS cluster may already exist: {cluster_name}")
    
    return cluster_name

def create_log_group():
    """Create CloudWatch log group"""
    log_group_name = f"/ecs/{PROJECT_NAME}"
    
    try:
        logs.create_log_group(logGroupName=log_group_name)
        print(f"Created log group: {log_group_name}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceAlreadyExistsException':
            print(f"Log group already exists: {log_group_name}")
        else:
            raise
    
    return log_group_name

def main():
    print(f"Starting deployment setup for {PROJECT_NAME}...")
    
    # Create IAM role
    task_execution_role_arn = create_iam_role()
    
    # Create VPC resources
    vpc_id, subnet_ids, security_group_id = create_vpc_resources()
    
    # Create ECR repository
    repository_uri = create_ecr_repository()
    
    # Create ECS cluster
    cluster_name = create_ecs_cluster()
    
    # Create CloudWatch log group
    log_group_name = create_log_group()
    
    # Save configuration
    config = {
        'aws_region': AWS_REGION,
        'aws_account_id': AWS_ACCOUNT_ID,
        'task_execution_role_arn': task_execution_role_arn,
        'vpc_id': vpc_id,
        'subnet_ids': subnet_ids,
        'security_group_id': security_group_id,
        'repository_uri': repository_uri,
        'cluster_name': cluster_name,
        'log_group_name': log_group_name
    }
    
    with open('infrastructure-config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("\nInfrastructure setup complete!")
    print(f"Configuration saved to infrastructure-config.json")
    print(f"\nNext steps:")
    print(f"1. Build and push Docker image:")
    print(f"   docker build -t {PROJECT_NAME} .")
    print(f"   aws ecr get-login-password --region {AWS_REGION} | docker login --username AWS --password-stdin {repository_uri}")
    print(f"   docker tag {PROJECT_NAME}:latest {repository_uri}:latest")
    print(f"   docker push {repository_uri}:latest")
    print(f"2. Deploy the ECS service using deploy-ecs.sh")

if __name__ == '__main__':
    main()