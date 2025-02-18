"""
VPC management utilities for Neptune.
"""

import boto3
from typing import Tuple, List, Optional
from botocore.exceptions import ClientError

class VPCManager:
    def __init__(self, cluster_name: str, session: boto3.Session, verbose: bool = True):
        self.cluster_name = cluster_name
        self.ec2 = session.client('ec2')
        self.verbose = verbose
        
        # Track resources
        self.vpc_id = None
        self.subnet_ids = []
        self.security_group_id = None
        self.nat_gateway_id = None
        self.eip_allocation_id = None
    
    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def _find_existing_vpc(self) -> Optional[Tuple[str, List[str], str]]:
        """Find existing VPC with our name."""
        try:
            # Look for VPC with our name
            vpcs = self.ec2.describe_vpcs(
                Filters=[{
                    'Name': 'tag:Name',
                    'Values': [f'{self.cluster_name}-vpc']
                }]
            )
            
            if not vpcs['Vpcs']:
                return None
                
            vpc = vpcs['Vpcs'][0]
            vpc_id = vpc['VpcId']
            
            # Get private subnets
            subnets = self.ec2.describe_subnets(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'tag:Name', 'Values': [f'{self.cluster_name}-private-*']}
                ]
            )
            private_subnet_ids = [s['SubnetId'] for s in subnets['Subnets']]
            
            # Get security group
            security_groups = self.ec2.describe_security_groups(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'group-name', 'Values': [f'{self.cluster_name}-sg']}
                ]
            )
            
            if not security_groups['SecurityGroups']:
                # Create security group if it doesn't exist
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
            else:
                security_group_id = security_groups['SecurityGroups'][0]['GroupId']
            
            # Store IDs
            self.vpc_id = vpc_id
            self.subnet_ids = private_subnet_ids
            self.security_group_id = security_group_id
            
            return vpc_id, private_subnet_ids, security_group_id
            
        except Exception as e:
            self._log(f"Error finding existing VPC: {str(e)}")
            return None
    
    def create_vpc(self) -> Tuple[str, List[str], str]:
        """
        Create VPC with public and private subnets.
        
        Returns:
            Tuple of (vpc_id, subnet_ids, security_group_id)
        """
        # First try to find existing VPC
        existing = self._find_existing_vpc()
        if existing:
            self._log("Using existing VPC")
            return existing
            
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
            
            # Create subnets
            public_subnet_ids, private_subnet_ids = self._create_subnets(vpc_id)
            
            # Configure routing
            self._configure_routing(vpc_id, public_subnet_ids, private_subnet_ids, igw_id)
            
            # Create security group
            security_group_id = self._create_security_group(vpc_id)
            
            # Store IDs for cleanup
            self.vpc_id = vpc_id
            self.subnet_ids = private_subnet_ids  # Use private subnets for Neptune
            self.security_group_id = security_group_id
            
            return vpc_id, private_subnet_ids, security_group_id
            
        except Exception as e:
            self._log(f"Error creating VPC: {str(e)}")
            raise
    
    def _create_subnets(self, vpc_id: str) -> Tuple[List[str], List[str]]:
        """Create public and private subnets in first 2 AZs."""
        azs = self.ec2.describe_availability_zones()['AvailabilityZones']
        public_subnet_ids = []
        private_subnet_ids = []
        
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
            
            # Enable auto-assign public IP
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
        
        return public_subnet_ids, private_subnet_ids
    
    def _configure_routing(
        self, 
        vpc_id: str, 
        public_subnet_ids: List[str],
        private_subnet_ids: List[str],
        igw_id: str
    ) -> None:
        """Configure routing tables for public and private subnets."""
        # Create and configure public route table
        self._log("Configuring public route table...")
        public_rt = self.ec2.create_route_table(VpcId=vpc_id)
        public_rt_id = public_rt['RouteTable']['RouteTableId']
        
        self.ec2.create_route(
            RouteTableId=public_rt_id,
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=igw_id
        )
        
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
            SubnetId=public_subnet_ids[0],
            AllocationId=self.eip_allocation_id,
            TagSpecifications=[{
                'ResourceType': 'natgateway',
                'Tags': [{'Key': 'Name', 'Value': f'{self.cluster_name}-nat'}]
            }]
        )
        self.nat_gateway_id = nat_gateway['NatGateway']['NatGatewayId']
        
        # Wait for NAT Gateway
        self._log("Waiting for NAT Gateway to be available...")
        waiter = self.ec2.get_waiter('nat_gateway_available')
        waiter.wait(
            NatGatewayIds=[self.nat_gateway_id],
            WaiterConfig={'Delay': 30, 'MaxAttempts': 20}
        )
        
        # Create and configure private route table
        self._log("Configuring private route table...")
        private_rt = self.ec2.create_route_table(VpcId=vpc_id)
        private_rt_id = private_rt['RouteTable']['RouteTableId']
        
        self.ec2.create_route(
            RouteTableId=private_rt_id,
            DestinationCidrBlock='0.0.0.0/0',
            NatGatewayId=self.nat_gateway_id
        )
        
        for subnet_id in private_subnet_ids:
            self.ec2.associate_route_table(
                RouteTableId=private_rt_id,
                SubnetId=subnet_id
            )
    
    def _create_security_group(self, vpc_id: str) -> str:
        """Create and configure security group."""
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
        
        return security_group_id
