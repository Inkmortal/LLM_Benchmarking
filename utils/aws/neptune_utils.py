"""
Utilities for working with Amazon Neptune graph database.
"""

import os
import time
import json
import boto3
import socket
from typing import Dict, Any, Optional, List, Tuple
from botocore.exceptions import ClientError
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal

class NeptuneManager:
    """
    Manages Amazon Neptune graph database operations.
    """
    
    def __init__(
        self,
        cluster_name: str,
        cleanup_enabled: bool = True,
        verbose: bool = True,
        region: str = None
    ):
        """
        Initialize Neptune manager.
        
        Args:
            cluster_name: Name for the Neptune cluster
            cleanup_enabled: Whether to enable cleanup on deletion
            verbose: Whether to print detailed status messages
            region: AWS region (defaults to session region)
        """
        self.cluster_name = cluster_name
        self.cleanup_enabled = cleanup_enabled
        self.verbose = verbose
        
        # Initialize AWS clients
        self.neptune = boto3.client('neptune', region_name=region)
        self.ec2 = boto3.client('ec2', region_name=region)
        
        # Track created resources
        self.cluster_id = None
        self.instance_id = None
        self.endpoint = None
        self.param_group_name = f"{cluster_name}-params"
        self.vpc_id = None
        self.subnet_ids = []
        self.security_group_id = None
        self.nat_gateway_id = None
        self.eip_allocation_id = None
        
        # Get identity for IAM auth
        sts = boto3.client('sts')
        self.identity = sts.get_caller_identity()
        self.current_arn = self.identity['Arn']
        
        # Track resource state
        self._resources_created = False
    
    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def _create_vpc(self) -> Tuple[str, List[str], str]:
        """
        Create VPC with public and private subnets for Neptune.
        
        Returns:
            Tuple of (vpc_id, subnet_ids, security_group_id)
        """
        try:
            # Create VPC
            self._log("Creating VPC...")
            vpc = self.ec2.create_vpc(
                CidrBlock='10.0.0.0/16',
                TagSpecifications=[{
                    'ResourceType': 'vpc',
                    'Tags': [{'Key': 'Name', 'Value': f'{self.cluster_name}-vpc'}]
                }]
            )
            vpc_id = vpc['Vpc']['VpcId']
            
            # Enable DNS hostnames
            self.ec2.modify_vpc_attribute(
                VpcId=vpc_id,
                EnableDnsHostnames={'Value': True}
            )
            
            # Create internet gateway
            self._log("Creating internet gateway...")
            igw = self.ec2.create_internet_gateway()
            igw_id = igw['InternetGateway']['InternetGatewayId']
            
            self.ec2.attach_internet_gateway(
                InternetGatewayId=igw_id,
                VpcId=vpc_id
            )
            
            # Get available AZs
            azs = self.ec2.describe_availability_zones()['AvailabilityZones']
            public_subnet_ids = []
            private_subnet_ids = []
            
            # Create subnets in first 2 AZs
            for i, az in enumerate(azs[:2]):
                # Create public subnet
                self._log(f"Creating public subnet in {az['ZoneName']}...")
                public_subnet = self.ec2.create_subnet(
                    VpcId=vpc_id,
                    CidrBlock=f'10.0.{i*2}.0/24',
                    AvailabilityZone=az['ZoneName'],
                    TagSpecifications=[{
                        'ResourceType': 'subnet',
                        'Tags': [{'Key': 'Name', 'Value': f'{self.cluster_name}-public-{i+1}'}]
                    }]
                )
                public_subnet_ids.append(public_subnet['Subnet']['SubnetId'])
                
                # Enable auto-assign public IP for public subnet
                self.ec2.modify_subnet_attribute(
                    SubnetId=public_subnet['Subnet']['SubnetId'],
                    MapPublicIpOnLaunch={'Value': True}
                )
                
                # Create private subnet
                self._log(f"Creating private subnet in {az['ZoneName']}...")
                private_subnet = self.ec2.create_subnet(
                    VpcId=vpc_id,
                    CidrBlock=f'10.0.{i*2+1}.0/24',
                    AvailabilityZone=az['ZoneName'],
                    TagSpecifications=[{
                        'ResourceType': 'subnet',
                        'Tags': [{'Key': 'Name', 'Value': f'{self.cluster_name}-private-{i+1}'}]
                    }]
                )
                private_subnet_ids.append(private_subnet['Subnet']['SubnetId'])
            
            # Create public route table
            self._log("Configuring public route table...")
            public_rt = self.ec2.create_route_table(VpcId=vpc_id)
            public_rt_id = public_rt['RouteTable']['RouteTableId']
            
            # Add route to internet
            self.ec2.create_route(
                RouteTableId=public_rt_id,
                DestinationCidrBlock='0.0.0.0/0',
                GatewayId=igw_id
            )
            
            # Associate public route table with public subnets
            for subnet_id in public_subnet_ids:
                self.ec2.associate_route_table(
                    RouteTableId=public_rt_id,
                    SubnetId=subnet_id
                )
            
            # Create NAT Gateway
            self._log("Creating NAT Gateway...")
            eip = self.ec2.allocate_address(Domain='vpc')
            self.eip_allocation_id = eip['AllocationId']
            
            nat_gateway = self.ec2.create_nat_gateway(
                SubnetId=public_subnet_ids[0],  # Place in first public subnet
                AllocationId=self.eip_allocation_id,
                TagSpecifications=[{
                    'ResourceType': 'natgateway',
                    'Tags': [{'Key': 'Name', 'Value': f'{self.cluster_name}-nat'}]
                }]
            )
            self.nat_gateway_id = nat_gateway['NatGateway']['NatGatewayId']
            
            # Wait for NAT Gateway to be available
            self._log("Waiting for NAT Gateway to be available...")
            waiter = self.ec2.get_waiter('nat_gateway_available')
            waiter.wait(
                NatGatewayIds=[self.nat_gateway_id],
                WaiterConfig={'Delay': 30, 'MaxAttempts': 20}
            )
            
            # Create private route table
            self._log("Configuring private route table...")
            private_rt = self.ec2.create_route_table(VpcId=vpc_id)
            private_rt_id = private_rt['RouteTable']['RouteTableId']
            
            # Add route through NAT Gateway
            self.ec2.create_route(
                RouteTableId=private_rt_id,
                DestinationCidrBlock='0.0.0.0/0',
                NatGatewayId=self.nat_gateway_id
            )
            
            # Associate private route table with private subnets
            for subnet_id in private_subnet_ids:
                self.ec2.associate_route_table(
                    RouteTableId=private_rt_id,
                    SubnetId=subnet_id
                )
            
            # Create security group
            self._log("Creating security group...")
            security_group = self.ec2.create_security_group(
                GroupName=f'{self.cluster_name}-sg',
                Description=f'Security group for Neptune cluster {self.cluster_name}',
                VpcId=vpc_id
            )
            security_group_id = security_group['GroupId']
            
            # Add inbound rule for Neptune port
            self.ec2.authorize_security_group_ingress(
                GroupId=security_group_id,
                IpPermissions=[{
                    'FromPort': 8182,
                    'ToPort': 8182,
                    'IpProtocol': 'tcp',
                    'IpRanges': [{
                        'CidrIp': '0.0.0.0/0',
                        'Description': 'Allow Neptune access'
                    }]
                }]
            )
            
            # Add outbound rule for all traffic
            self.ec2.authorize_security_group_egress(
                GroupId=security_group_id,
                IpPermissions=[{
                    'IpProtocol': '-1',  # All protocols
                    'FromPort': -1,      # All ports
                    'ToPort': -1,
                    'IpRanges': [{
                        'CidrIp': '0.0.0.0/0',
                        'Description': 'Allow all outbound traffic'
                    }]
                }]
            )
            
            # Store IDs for cleanup
            self.vpc_id = vpc_id
            self.subnet_ids = private_subnet_ids  # Use private subnets for Neptune
            self.security_group_id = security_group_id
            
            return vpc_id, private_subnet_ids, security_group_id
            
        except Exception as e:
            self._log(f"Error creating VPC: {str(e)}")
            raise
    
    def _create_parameter_group(self) -> None:
        """Create a custom DB cluster parameter group."""
        try:
            self._log(f"Creating parameter group: {self.param_group_name}")
            self.neptune.create_db_cluster_parameter_group(
                DBClusterParameterGroupName=self.param_group_name,
                DBParameterGroupFamily='neptune1.2',
                Description=f'Custom parameter group for {self.cluster_name}'
            )
            self._resources_created = True
        except ClientError as e:
            if e.response['Error']['Code'] != 'DBParameterGroupAlreadyExists':
                raise
            self._log(f"Using existing parameter group: {self.param_group_name}")
    
    def _wait_for_cluster(self, cluster_id: str, timeout: int = 1800) -> None:
        """Wait for cluster to be available using polling.
        
        Args:
            cluster_id: Cluster identifier
            timeout: Maximum wait time in seconds (default 30 minutes)
        """
        self._log("Waiting for cluster to be available...")
        start_time = time.time()
        while True:
            try:
                response = self.neptune.describe_db_clusters(
                    DBClusterIdentifier=cluster_id
                )
                status = response['DBClusters'][0]['Status']
                if status == 'available':
                    self._log("Cluster is available")
                    return
                elif status == 'failed':
                    raise Exception(f"Cluster creation failed: {cluster_id}")
                elif time.time() - start_time > timeout:
                    raise Exception(f"Timeout waiting for cluster: {cluster_id}")
                else:
                    self._log(f"Cluster status: {status}")
                    time.sleep(30)
            except ClientError as e:
                if e.response['Error']['Code'] == 'DBClusterNotFoundFault':
                    raise Exception(f"Cluster not found: {cluster_id}")
                raise
    
    def _wait_for_instance(self, instance_id: str, timeout: int = 1800) -> None:
        """Wait for instance to be available using polling.
        
        Args:
            instance_id: Instance identifier
            timeout: Maximum wait time in seconds (default 30 minutes)
        """
        self._log("Waiting for instance to be available...")
        start_time = time.time()
        while True:
            try:
                response = self.neptune.describe_db_instances(
                    DBInstanceIdentifier=instance_id
                )
                status = response['DBInstances'][0]['DBInstanceStatus']
                if status == 'available':
                    self._log("Instance is available")
                    return
                elif status == 'failed':
                    raise Exception(f"Instance creation failed: {instance_id}")
                elif time.time() - start_time > timeout:
                    raise Exception(f"Timeout waiting for instance: {instance_id}")
                else:
                    self._log(f"Instance status: {status}")
                    time.sleep(30)
            except ClientError as e:
                if e.response['Error']['Code'] == 'DBInstanceNotFound':
                    raise Exception(f"Instance not found: {instance_id}")
                raise
    
    def _ensure_instance(self) -> None:
        """Ensure cluster has at least one instance."""
        # Check existing instances
        instances = self.neptune.describe_db_instances(
            Filters=[{'Name': 'db-cluster-id', 'Values': [self.cluster_id]}]
        )
        
        if not instances['DBInstances']:
            self._log("Creating serverless instance...")
            self.instance_id = f"{self.cluster_id}-instance"
            
            # Create instance
            self.neptune.create_db_instance(
                DBInstanceIdentifier=self.instance_id,
                DBClusterIdentifier=self.cluster_id,
                Engine='neptune',
                DBInstanceClass='db.serverless'
            )
            
            # Wait for instance
            self._wait_for_instance(self.instance_id)
            self._resources_created = True
            
        else:
            instance = instances['DBInstances'][0]
            self.instance_id = instance['DBInstanceIdentifier']
            
            # Only wait if instance not ready
            if instance['DBInstanceStatus'] != 'available':
                self._wait_for_instance(self.instance_id)
            else:
                self._log(f"Using existing instance: {self.instance_id}")
    
    def _check_dns_propagation(self, endpoint: str, timeout: int = 300) -> None:
        """Check if DNS has propagated for endpoint.
        
        Args:
            endpoint: Endpoint to check
            timeout: Maximum wait time in seconds (default 5 minutes)
        """
        self._log("Checking DNS propagation...")
        start_time = time.time()
        while True:
            try:
                # Try to resolve the hostname
                socket.gethostbyname(endpoint)
                self._log("DNS resolution successful")
                return
            except socket.gaierror:
                if time.time() - start_time > timeout:
                    raise Exception(f"DNS propagation timeout for endpoint: {endpoint}")
                self._log("Waiting for DNS propagation...")
                time.sleep(10)  # Check every 10 seconds
    
    def _cleanup_vpc(self, vpc_id: str) -> None:
        """Clean up all resources in a VPC."""
        try:
            # Delete NAT Gateway first
            nat_gateways = self.ec2.describe_nat_gateways(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for nat in nat_gateways['NatGateways']:
                if nat['State'] not in ['deleted', 'deleting']:
                    self._log(f"Deleting NAT Gateway: {nat['NatGatewayId']}")
                    self.ec2.delete_nat_gateway(NatGatewayId=nat['NatGatewayId'])
                    
                    # Wait for NAT Gateway to be deleted
                    while True:
                        response = self.ec2.describe_nat_gateways(
                            NatGatewayIds=[nat['NatGatewayId']]
                        )
                        if response['NatGateways'][0]['State'] == 'deleted':
                            break
                        time.sleep(30)
            
            # Release Elastic IPs
            if self.eip_allocation_id:
                self._log(f"Releasing Elastic IP: {self.eip_allocation_id}")
                self.ec2.release_address(AllocationId=self.eip_allocation_id)
            
            # Delete internet gateways
            igws = self.ec2.describe_internet_gateways(
                Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
            )
            for igw in igws['InternetGateways']:
                self._log(f"Detaching and deleting internet gateway: {igw['InternetGatewayId']}")
                self.ec2.detach_internet_gateway(
                    InternetGatewayId=igw['InternetGatewayId'],
                    VpcId=vpc_id
                )
                self.ec2.delete_internet_gateway(
                    InternetGatewayId=igw['InternetGatewayId']
                )
            
            # Delete subnets
            subnets = self.ec2.describe_subnets(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for subnet in subnets['Subnets']:
                self._log(f"Deleting subnet: {subnet['SubnetId']}")
                self.ec2.delete_subnet(SubnetId=subnet['SubnetId'])
            
            # Delete route tables (except main)
            route_tables = self.ec2.describe_route_tables(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for rt in route_tables['RouteTables']:
                # Skip main route table
                associations = rt.get('Associations', [])
                if not any(assoc.get('Main', False) for assoc in associations):
                    self._log(f"Deleting route table: {rt['RouteTableId']}")
                    self.ec2.delete_route_table(RouteTableId=rt['RouteTableId'])
            
            # Delete security groups (except default)
            security_groups = self.ec2.describe_security_groups(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for sg in security_groups['SecurityGroups']:
                if sg['GroupName'] != 'default':
                    self._log(f"Deleting security group: {sg['GroupId']}")
                    self.ec2.delete_security_group(GroupId=sg['GroupId'])
            
            # Delete VPC
            self._log(f"Deleting VPC: {vpc_id}")
            self.ec2.delete_vpc(VpcId=vpc_id)
            
        except Exception as e:
            self._log(f"Error cleaning up VPC: {str(e)}")
            raise
    
    def _cleanup_existing_resources(self) -> None:
        """Clean up any existing resources with our name prefix."""
        try:
            # Find and delete existing cluster
            try:
                response = self.neptune.describe_db_clusters(
                    DBClusterIdentifier=self.cluster_name
                )
                if response['DBClusters']:
                    cluster = response['DBClusters'][0]
                    
                    # Delete instances first
                    for member in cluster['DBClusterMembers']:
                        instance_id = member['DBInstanceIdentifier']
                        self._log(f"Deleting instance: {instance_id}")
                        self.neptune.delete_db_instance(
                            DBInstanceIdentifier=instance_id,
                            SkipFinalSnapshot=True
                        )
                        
                        # Wait for instance deletion
                        start_time = time.time()
                        while True:
                            try:
                                self.neptune.describe_db_instances(
                                    DBInstanceIdentifier=instance_id
                                )
                                if time.time() - start_time > 1800:  # 30 minutes
                                    raise Exception(f"Timeout waiting for instance deletion: {instance_id}")
                                time.sleep(30)
                            except ClientError as e:
                                if e.response['Error']['Code'] == 'DBInstanceNotFound':
                                    break
                                raise
                    
                    # Delete cluster
                    self._log(f"Deleting cluster: {self.cluster_name}")
                    self.neptune.delete_db_cluster(
                        DBClusterIdentifier=self.cluster_name,
                        SkipFinalSnapshot=True
                    )
                    
                    # Wait for cluster deletion
                    start_time = time.time()
                    while True:
                        try:
                            self.neptune.describe_db_clusters(
                                DBClusterIdentifier=self.cluster_name
                            )
                            if time.time() - start_time > 1800:  # 30 minutes
                                raise Exception(f"Timeout waiting for cluster deletion: {self.cluster_name}")
                            time.sleep(30)
                        except ClientError as e:
                            if e.response['Error']['Code'] == 'DBClusterNotFoundFault':
                                break
                            raise
            except ClientError as e:
                if e.response['Error']['Code'] != 'DBClusterNotFoundFault':
                    raise
            
            # Find and delete VPC with our name
            vpcs = self.ec2.describe_vpcs(
                Filters=[{
                    'Name': 'tag:Name',
                    'Values': [f'{self.cluster_name}-vpc']
                }]
            )
            for vpc in vpcs['Vpcs']:
                self._cleanup_vpc(vpc['VpcId'])
            
            # Delete parameter group
            try:
                self._log(f"Deleting parameter group: {self.param_group_name}")
                self.neptune.delete_db_cluster_parameter_group(
                    DBClusterParameterGroupName=self.param_group_name
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'DBParameterGroupNotFound':
                    raise
            
            # Delete subnet group
            try:
                subnet_group_name = f"{self.cluster_name}-subnet-group"
                self._log(f"Deleting subnet group: {subnet_group_name}")
                self.neptune.delete_db_subnet_group(
                    DBSubnetGroupName=subnet_group_name
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'DBSubnetGroupNotFoundFault':
                    raise
                    
        except Exception as e:
            self._log(f"Error cleaning up existing resources: {str(e)}")
            raise
    
    def setup_cluster(self) -> str:
        """
        Set up Neptune cluster and return endpoint.
        
        Returns:
            Neptune cluster endpoint
        """
        try:
            # Clean up any existing resources first
            self._log("Cleaning up any existing resources...")
            self._cleanup_existing_resources()
            
            # Create VPC infrastructure
            self._log("Setting up VPC...")
            vpc_id, subnet_ids, security_group_id = self._create_vpc()
            
            # Create parameter group
            self._create_parameter_group()
            
            # Create new cluster
            self._log(f"Creating Neptune cluster: {self.cluster_name}")
            
            # Create subnet group
            subnet_group_name = f"{self.cluster_name}-subnet-group"
            try:
                self.neptune.create_db_subnet_group(
                    DBSubnetGroupName=subnet_group_name,
                    DBSubnetGroupDescription=f'Subnet group for {self.cluster_name}',
                    SubnetIds=subnet_ids
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'DBSubnetGroupAlreadyExistsFault':
                    raise
            
            # Create cluster with serverless configuration
            response = self.neptune.create_db_cluster(
                DBClusterIdentifier=self.cluster_name,
                Engine='neptune',
                EngineVersion='1.2.1.0',
                ServerlessV2ScalingConfiguration={
                    'MinCapacity': 1.0,
                    'MaxCapacity': 8.0
                },
                EnableIAMDatabaseAuthentication=True,
                DeletionProtection=False,
                Port=8182,
                DBClusterParameterGroupName=self.param_group_name,
                VpcSecurityGroupIds=[security_group_id],
                DBSubnetGroupName=subnet_group_name
            )
            
            cluster = response['DBCluster']
            self.cluster_id = cluster['DBClusterIdentifier']
            
            # Wait for cluster to be available
            self._wait_for_cluster(self.cluster_id)
            
            # Get endpoint
            response = self.neptune.describe_db_clusters(
                DBClusterIdentifier=self.cluster_id
            )
            self.endpoint = response['DBClusters'][0]['Endpoint']
            
            self._log(f"Neptune cluster created: {self.cluster_id}")
            self._resources_created = True
            
            # Ensure instance exists and is ready
            self._ensure_instance()
            
            # Only check DNS if we created new resources
            if self._resources_created:
                self._check_dns_propagation(self.endpoint)
            
            return self.endpoint
            
        except Exception as e:
            self._log(f"Error setting up Neptune cluster: {str(e)}")
            raise
    
    def cleanup(self) -> None:
        """Clean up Neptune resources."""
        if not self.cleanup_enabled:
            return
            
        try:
            if self.instance_id:
                self._log(f"Deleting instance: {self.instance_id}")
                try:
                    self.neptune.delete_db_instance(
                        DBInstanceIdentifier=self.instance_id,
                        SkipFinalSnapshot=True
                    )
                    
                    # Wait for instance deletion
                    start_time = time.time()
                    while True:
                        try:
                            self.neptune.describe_db_instances(
                                DBInstanceIdentifier=self.instance_id
                            )
                            if time.time() - start_time > 1800:  # 30 minutes
                                raise Exception(f"Timeout waiting for instance deletion: {self.instance_id}")
                            time.sleep(30)
                        except ClientError as e:
                            if e.response['Error']['Code'] == 'DBInstanceNotFound':
                                break
                            raise
                        
                except ClientError as e:
                    if e.response['Error']['Code'] != 'DBInstanceNotFound':
                        raise
            
            if self.cluster_id:
                self._log(f"Deleting cluster: {self.cluster_id}")
                try:
                    self.neptune.delete_db_cluster(
                        DBClusterIdentifier=self.cluster_id,
                        SkipFinalSnapshot=True
                    )
                    
                    # Wait for cluster deletion
                    start_time = time.time()
                    while True:
                        try:
                            self.neptune.describe_db_clusters(
                                DBClusterIdentifier=self.cluster_id
                            )
                            if time.time() - start_time > 1800:  # 30 minutes
                                raise Exception(f"Timeout waiting for cluster deletion: {self.cluster_id}")
                            time.sleep(30)
                        except ClientError as e:
                            if e.response['Error']['Code'] == 'DBClusterNotFoundFault':
                                break
                            raise
                        
                except ClientError as e:
                    if e.response['Error']['Code'] != 'DBClusterNotFoundFault':
                        raise
                
                # Delete parameter group
                try:
                    self._log(f"Deleting parameter group: {self.param_group_name}")
                    self.neptune.delete_db_cluster_parameter_group(
                        DBClusterParameterGroupName=self.param_group_name
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] != 'DBParameterGroupNotFound':
                        raise
                
                # Delete subnet group
                try:
                    subnet_group_name = f"{self.cluster_name}-subnet-group"
                    self._log(f"Deleting subnet group: {subnet_group_name}")
                    self.neptune.delete_db_subnet_group(
                        DBSubnetGroupName=subnet_group_name
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] != 'DBSubnetGroupNotFoundFault':
                        raise
                
                # Clean up VPC resources
                if self.vpc_id:
                    self._cleanup_vpc(self.vpc_id)
                
                self._log("Cleanup complete")
                
        except Exception as e:
            self._log(f"Error during cleanup: {str(e)}")
            raise

class NeptuneGraph:
    """
    Interface for working with Neptune graph database.
    """
    
    def __init__(
        self,
        endpoint: str,
        max_retries: int = 5,
        retry_delay: float = 1.0
    ):
        """
        Initialize Neptune graph interface.
        
        Args:
            endpoint: Neptune cluster endpoint
            max_retries: Maximum connection retry attempts
            retry_delay: Initial delay between retries (doubles each attempt)
        """
        self.endpoint = endpoint
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize connection state
        self.connection = None
        self.g = None
        
        # Set up connection with retries
        self._connect_with_retries()
    
    def _connect_with_retries(self):
        """Initialize connection with retries."""
        database_url = f"wss://{self.endpoint}:8182/gremlin"
        
        # Get AWS credentials for IAM auth
        creds = boto3.Session().get_credentials().get_frozen_credentials()
        request = AWSRequest(method="GET", url=database_url, data=None)
        SigV4Auth(creds, "neptune-db", boto3.Session().region_name).add_auth(request)
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Initialize Gremlin connection with IAM auth
                self.connection = DriverRemoteConnection(
                    database_url,
                    'g',
                    headers=request.headers.items()
                )
                self.g = traversal().withRemote(self.connection)
                
                # Test connection
                self.g.V().limit(1).toList()
                return  # Success
                
            except Exception as e:
                last_error = e
                if self.connection:
                    self.connection.close()
                    self.connection = None
                
                if attempt < self.max_retries - 1:
                    delay = min(60, self.retry_delay * (2 ** attempt))
                    time.sleep(delay)
                    continue
                
                raise ConnectionError(
                    f"Failed to connect to Neptune after {self.max_retries} attempts"
                ) from last_error
    
    def close(self):
        """Close all connections."""
