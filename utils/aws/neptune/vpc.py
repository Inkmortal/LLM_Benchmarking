"""
VPC management utilities for Neptune.
"""

import boto3
from typing import Tuple, List, Optional, Dict
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

    def _fix_vpc_config(self, vpc_id: str) -> bool:
        """Try to fix VPC configuration issues."""
        try:
            fixed = True
            
            # Fix DNS hostnames if needed
            vpc = self.ec2.describe_vpc_attribute(
                VpcId=vpc_id,
                Attribute='enableDnsHostnames'
            )
            if not vpc['EnableDnsHostnames']['Value']:
                self._log("Enabling DNS hostnames...")
                self.ec2.modify_vpc_attribute(
                    VpcId=vpc_id,
                    EnableDnsHostnames={'Value': True}
                )
            
            # Check/fix NAT Gateway
            nat_gateways = self.ec2.describe_nat_gateways(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            
            working_nat = None
            for nat in nat_gateways['NatGateways']:
                if nat['State'] == 'available':
                    working_nat = nat
                    break
            
            if not working_nat:
                self._log("No working NAT Gateway found")
                # Find public subnet for NAT
                subnets = self.ec2.describe_subnets(
                    Filters=[
                        {'Name': 'vpc-id', 'Values': [vpc_id]},
                        {'Name': 'tag:Name', 'Values': [f'{self.cluster_name}-public-*']}
                    ]
                )
                if not subnets['Subnets']:
                    self._log("No public subnet found for NAT Gateway")
                    fixed = False
                else:
                    # Create NAT Gateway in first public subnet
                    self._log("Creating NAT Gateway...")
                    eip = self.ec2.allocate_address(Domain='vpc')
                    self.eip_allocation_id = eip['AllocationId']
                    
                    nat_gateway = self.ec2.create_nat_gateway(
                        SubnetId=subnets['Subnets'][0]['SubnetId'],
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
            
            # Check/fix internet gateway
            igws = self.ec2.describe_internet_gateways(
                Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
            )
            if not igws['InternetGateways']:
                self._log("Creating internet gateway...")
                igw = self.ec2.create_internet_gateway()
                igw_id = igw['InternetGateway']['InternetGatewayId']
                
                self.ec2.attach_internet_gateway(
                    InternetGatewayId=igw_id,
                    VpcId=vpc_id
                )
            
            # Check/fix routing tables
            self._fix_routing_tables(vpc_id)
            
            return fixed
            
        except Exception as e:
            self._log(f"Error fixing VPC config: {str(e)}")
            return False
    
    def _fix_routing_tables(self, vpc_id: str) -> bool:
        """Fix routing table configurations."""
        try:
            # Get subnets
            public_subnets = self.ec2.describe_subnets(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'tag:Name', 'Values': [f'{self.cluster_name}-public-*']}
                ]
            )['Subnets']
            
            private_subnets = self.ec2.describe_subnets(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'tag:Name', 'Values': [f'{self.cluster_name}-private-*']}
                ]
            )['Subnets']
            
            # Get internet gateway
            igw = self.ec2.describe_internet_gateways(
                Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
            )['InternetGateways'][0]
            
            # Fix public subnet routing
            for subnet in public_subnets:
                route_tables = self.ec2.describe_route_tables(
                    Filters=[{'Name': 'association.subnet-id', 'Values': [subnet['SubnetId']]}]
                )['RouteTables']
                
                if not route_tables:
                    # Create new route table
                    self._log(f"Creating route table for public subnet {subnet['SubnetId']}...")
                    rt = self.ec2.create_route_table(VpcId=vpc_id)
                    rt_id = rt['RouteTable']['RouteTableId']
                    
                    # Add internet gateway route
                    self.ec2.create_route(
                        RouteTableId=rt_id,
                        DestinationCidrBlock='0.0.0.0/0',
                        GatewayId=igw['InternetGatewayId']
                    )
                    
                    # Associate with subnet
                    self.ec2.associate_route_table(
                        RouteTableId=rt_id,
                        SubnetId=subnet['SubnetId']
                    )
                else:
                    # Check/fix internet gateway route
                    rt = route_tables[0]
                    has_igw_route = False
                    for route in rt['Routes']:
                        if route.get('DestinationCidrBlock') == '0.0.0.0/0' and \
                           route.get('GatewayId') == igw['InternetGatewayId']:
                            has_igw_route = True
                            break
                    
                    if not has_igw_route:
                        self._log(f"Adding internet gateway route to {rt['RouteTableId']}...")
                        self.ec2.create_route(
                            RouteTableId=rt['RouteTableId'],
                            DestinationCidrBlock='0.0.0.0/0',
                            GatewayId=igw['InternetGatewayId']
                        )
            
            # Fix private subnet routing
            nat_gateway = self.ec2.describe_nat_gateways(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['NatGateways'][0]
            
            for subnet in private_subnets:
                route_tables = self.ec2.describe_route_tables(
                    Filters=[{'Name': 'association.subnet-id', 'Values': [subnet['SubnetId']]}]
                )['RouteTables']
                
                if not route_tables:
                    # Create new route table
                    self._log(f"Creating route table for private subnet {subnet['SubnetId']}...")
                    rt = self.ec2.create_route_table(VpcId=vpc_id)
                    rt_id = rt['RouteTable']['RouteTableId']
                    
                    # Add NAT Gateway route
                    self.ec2.create_route(
                        RouteTableId=rt_id,
                        DestinationCidrBlock='0.0.0.0/0',
                        NatGatewayId=nat_gateway['NatGatewayId']
                    )
                    
                    # Associate with subnet
                    self.ec2.associate_route_table(
                        RouteTableId=rt_id,
                        SubnetId=subnet['SubnetId']
                    )
                else:
                    # Check/fix NAT Gateway route
                    rt = route_tables[0]
                    has_nat_route = False
                    for route in rt['Routes']:
                        if route.get('DestinationCidrBlock') == '0.0.0.0/0' and \
                           route.get('NatGatewayId') == nat_gateway['NatGatewayId']:
                            has_nat_route = True
                            break
                    
                    if not has_nat_route:
                        self._log(f"Adding NAT Gateway route to {rt['RouteTableId']}...")
                        self.ec2.create_route(
                            RouteTableId=rt['RouteTableId'],
                            DestinationCidrBlock='0.0.0.0/0',
                            NatGatewayId=nat_gateway['NatGatewayId']
                        )
            
            return True
            
        except Exception as e:
            self._log(f"Error fixing routing tables: {str(e)}")
            return False
    
    def _check_security_group(self, security_group_id: str) -> bool:
        """Check and fix security group rules."""
        try:
            sg = self.ec2.describe_security_groups(
                GroupIds=[security_group_id]
            )['SecurityGroups'][0]
            
            # Check Neptune port inbound rule
            has_neptune_rule = False
            for rule in sg['IpPermissions']:
                if rule.get('FromPort') == 8182 and rule.get('ToPort') == 8182:
                    has_neptune_rule = True
                    break
            
            if not has_neptune_rule:
                self._log("Adding Neptune port rule...")
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
            
            # Check outbound rules
            has_outbound = False
            for rule in sg['IpPermissionsEgress']:
                if rule.get('IpProtocol') == '-1':
                    has_outbound = True
                    break
            
            if not has_outbound:
                self._log("Adding outbound rule...")
                self.ec2.authorize_security_group_egress(
                    GroupId=security_group_id,
                    IpPermissions=[{
                        'IpProtocol': '-1',
                        'FromPort': -1,
                        'ToPort': -1,
                        'IpRanges': [{
                            'CidrIp': '0.0.0.0/0',
                            'Description': 'Allow all outbound traffic'
                        }]
                    }]
                )
            
            return True
            
        except Exception as e:
            self._log(f"Error checking security group: {str(e)}")
            return False
    
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
            
            # Try to fix VPC configuration if needed
            if not self._fix_vpc_config(vpc_id):
                self._log("Could not fix VPC configuration")
                return None
            
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
                
                # Add rules
                self._check_security_group(security_group_id)
            else:
                security_group_id = security_groups['SecurityGroups'][0]['GroupId']
                # Check and fix rules if needed
                self._check_security_group(security_group_id)
            
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
        # First try to find and fix existing VPC
        existing = self._find_existing_vpc()
        if existing:
            self._log("Using existing VPC")
            return existing
            
        try:
            # Create new VPC if needed
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
            
            # Store IDs for reference
            self.vpc_id = vpc_id
            self.subnet_ids = private_subnet_ids  # Use private subnets for Neptune
            self.security_group_id = security_group_id
            
            return vpc_id, private_subnet_ids, security_group_id
            
        except Exception as e:
            self._log(f"Error creating VPC: {str(e)}")
            raise
