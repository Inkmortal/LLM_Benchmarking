"""
Neptune cluster management utilities.
"""

import time
import socket
from typing import Optional, List, Dict
import boto3
from botocore.exceptions import ClientError
import requests  # Import the requests library

class NeptuneManager:
    def __init__(self, cluster_name: str, session: boto3.Session = None, verbose: bool = True, cleanup_enabled: bool = False):
        self.cluster_name = cluster_name
        self.verbose = verbose
        self.cleanup_enabled = cleanup_enabled
        
        # Create session if not provided
        if session is None:
            session = boto3.Session()
        self.neptune = session.client('neptune')
        self.ec2 = session.client('ec2') # We'll need EC2 client
        
        # Track resources
        self.cluster_id = None
        self.instance_id = None
        self.endpoint = None
        self.param_group_name = f"{cluster_name}-params"
        
        # Initialize VPC settings as None - they will be set during create_cluster
        self.vpc_id = None
        self.subnet_ids = []
        self.security_group_id = None

    
    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def _get_instance_identity(self) -> Dict:
        """Get EC2 instance identity document using requests."""
        try:
            response = requests.get('http://169.254.169.254/latest/dynamic/instance-identity/document', timeout=2)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to get instance identity document: {e}")

    def _get_vpc_id(self) -> str:
        """Get VPC ID from instance identity document."""
        identity = self._get_instance_identity()
        # Use ec2 client to get vpc id from instance id
        instance_description = self.ec2.describe_instances(
            InstanceIds=[identity['instanceId']]
        )
        vpc_id = instance_description['Reservations'][0]['Instances'][0]['VpcId']
        return vpc_id

    def _get_subnet_id(self) -> str:
        """Get Subnet ID from instance identity document."""
        identity = self._get_instance_identity()
        instance_description = self.ec2.describe_instances(
            InstanceIds=[identity['instanceId']]
        )
        subnet_id = instance_description['Reservations'][0]['Instances'][0]['SubnetId']
        return subnet_id
    
    def _fix_cluster_config(self, cluster_id: str) -> bool:
        """Try to fix cluster configuration issues."""
        try:
            cluster = self.neptune.describe_db_clusters(
                DBClusterIdentifier=cluster_id
            )['DBClusters'][0]
            
            fixed = True
            
            # Check and enable IAM auth if needed
            if not cluster.get('EnableIAMDatabaseAuthentication', False):
                self._log("Enabling IAM authentication...")
                try:
                    self.neptune.modify_db_cluster(
                        DBClusterIdentifier=cluster_id,
                        ApplyImmediately=True,
                        EnableIAMDatabaseAuthentication=True
                    )
                    # Wait for modification to complete
                    self._wait_for_cluster(cluster_id)
                except Exception as e:
                    self._log(f"Error enabling IAM auth: {str(e)}")
                    fixed = False
            
            # Check parameter group
            if cluster['DBClusterParameterGroup'] != self.param_group_name:
                self._log(f"Updating parameter group to {self.param_group_name}...")
                try:
                    # Create parameter group if needed
                    self.create_parameter_group()
                    
                    # Apply to cluster
                    self.neptune.modify_db_cluster(
                        DBClusterIdentifier=cluster_id,
                        ApplyImmediately=True,
                        DBClusterParameterGroupName=self.param_group_name
                    )
                except Exception as e:
                    self._log(f"Error updating parameter group: {str(e)}")
                    fixed = False
            
            # Check instances
            instances = self.neptune.describe_db_instances(
                Filters=[{'Name': 'db-cluster-id', 'Values': [cluster_id]}]
            )['DBInstances']
            
            if not instances:
                self._log("No instances found, creating...")
                self._ensure_instance()
            else:
                instance = instances[0]
                if instance['DBInstanceStatus'] != 'available':
                    self._log(f"Instance status: {instance['DBInstanceStatus']}")
                    fixed = False
            
            return fixed
            
        except Exception as e:
            self._log(f"Error fixing cluster config: {str(e)}")
            return False
    
    def _find_existing_cluster(self) -> Optional[str]:
        """Find and validate existing cluster."""
        try:
            response = self.neptune.describe_db_clusters(
                DBClusterIdentifier=self.cluster_name
            )
            
            if not response['DBClusters']:
                return None
                
            cluster = response['DBClusters'][0]
            
            # Try to fix configuration if needed
            if cluster['Status'] != 'available' or not self._fix_cluster_config(cluster['DBClusterIdentifier']):
                self._log("Could not fix cluster configuration")
                return None
            
            self.cluster_id = cluster['DBClusterIdentifier']
            self.endpoint = cluster['Endpoint']
            
            # Ensure instance exists and is ready
            self._ensure_instance()
            
            return self.endpoint
            
        except ClientError as e:
            if e.response['Error']['Code'] != 'DBClusterNotFoundFault':
                raise
            return None
    
    def create_parameter_group(self) -> None:
        """Create a custom DB cluster parameter group."""
        try:
            self._log(f"Creating parameter group: {self.param_group_name}")
            self.neptune.create_db_cluster_parameter_group(
                DBClusterParameterGroupName=self.param_group_name,
                DBParameterGroupFamily='neptune1.2',
                Description=f'Custom parameter group for {self.cluster_name}'
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'DBParameterGroupAlreadyExists':
                raise
            self._log(f"Using existing parameter group: {self.param_group_name}")
    
    def create_cluster(
        self,
        subnet_ids: List[str],
        security_group_id: str,
        subnet_group_name: Optional[str] = None
    ) -> str:
        # Store the security group ID
        self.security_group_id = security_group_id
        """
        Create Neptune cluster and return endpoint.
        
        Args:
            subnet_ids: List of subnet IDs
            security_group_id: Security group ID
            subnet_group_name: Optional subnet group name (defaults to {cluster_name}-subnet-group)
            
        Returns:
            Neptune cluster endpoint
        """
        try:
            # Check for existing cluster first
            existing = self._find_existing_cluster()
            if existing:
                self._log("Using existing cluster")
                return existing
            
            # Create parameter group
            self.create_parameter_group()
            
            # Create subnet group
            if not subnet_group_name:
                subnet_group_name = f"{self.cluster_name}-subnet-group"
                
            # Check if subnet group exists first
            try:
                self.neptune.describe_db_subnet_groups(DBSubnetGroupName=subnet_group_name)
                self._log(f"Using existing subnet group: {subnet_group_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'DBSubnetGroupNotFoundFault':
                    self._log(f"Creating subnet group: {subnet_group_name}")
                    self.neptune.create_db_subnet_group(
                        DBSubnetGroupName=subnet_group_name,
                        DBSubnetGroupDescription=f'Subnet group for {self.cluster_name}',
                        SubnetIds=subnet_ids
                    )
                else:
                    raise
            
            # Validate VPC settings
            self._log("\nValidating VPC settings...")
            try:
                # Get security group's VPC
                sg = self.ec2.describe_security_groups(
                    GroupIds=[security_group_id]
                )['SecurityGroups'][0]
                sg_vpc_id = sg['VpcId']
                
                # Get subnets' VPC
                subnets = self.ec2.describe_subnets(
                    SubnetIds=subnet_ids
                )['Subnets']
                subnet_vpc_ids = {subnet['VpcId'] for subnet in subnets}
                
                # Log VPC information
                self._log(f"Security Group {security_group_id} is in VPC {sg_vpc_id}")
                self._log(f"Subnets {subnet_ids} are in VPCs {subnet_vpc_ids}")
                
                # Check if all resources are in the same VPC
                if len(subnet_vpc_ids) > 1:
                    raise ValueError(f"Subnets are in different VPCs: {subnet_vpc_ids}")
                
                subnet_vpc_id = next(iter(subnet_vpc_ids))
                if sg_vpc_id != subnet_vpc_id:
                    raise ValueError(f"Security group VPC ({sg_vpc_id}) does not match subnet VPC ({subnet_vpc_id})")
                
                # Store validated VPC ID
                self.vpc_id = sg_vpc_id
                self.subnet_ids = subnet_ids
                
                self._log(f"✅ All resources are in VPC {self.vpc_id}")
                
            except Exception as e:
                self._log(f"❌ VPC validation failed: {str(e)}")
                raise
            
            # Create cluster with serverless configuration
            self._log(f"\nCreating Neptune cluster: {self.cluster_name}")
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
            
            # Ensure instance exists and is ready
            self._ensure_instance()
            
            # Check DNS propagation
            self._check_dns_propagation(self.endpoint)
            
            return self.endpoint
            
        except Exception as e:
            self._log(f"Error creating cluster: {str(e)}")
            raise
    
    def _wait_for_cluster(self, cluster_id: str, timeout: int = 1800) -> None:
        """Wait for cluster to be available using polling."""
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
        """Wait for instance to be available using polling."""
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
            self.instance_id = f"{self.cluster_name}-instance"
            
            # Create instance
            self.neptune.create_db_instance(
                DBInstanceIdentifier=self.instance_id,
                DBClusterIdentifier=self.cluster_id,
                Engine='neptune',
                DBInstanceClass='db.serverless'
            )
            
            # Wait for instance
            self._wait_for_instance(self.instance_id)
            
        else:
            instance = instances['DBInstances'][0]
            self.instance_id = instance['DBInstanceIdentifier']
            
            # Only wait if instance not ready
            if instance['DBInstanceStatus'] != 'available':
                self._wait_for_instance(self.instance_id)
            else:
                self._log(f"Using existing instance: {self.instance_id}")
    
    def _check_dns_propagation(self, endpoint: str, timeout: int = 300) -> None:
        """Check if DNS has propagated for endpoint."""
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
    
    def cleanup(self) -> None:
        """Clean up cluster resources."""
        if not self.cleanup_enabled:
            self._log("Cleanup disabled. Skipping resource deletion.")
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
                
                self._log("Cleanup complete")
                
        except Exception as e:
            self._log(f"Error during cleanup: {str(e)}")
            raise

    def setup_cluster(self) -> str:
        """
        Set up Neptune cluster and return endpoint.
        Creates a new cluster if one doesn't exist.
        
        Returns:
            Neptune cluster endpoint
        """
        # Check for existing cluster first
        existing_endpoint = self._find_existing_cluster()
        if existing_endpoint:
            self._log(f"Using existing cluster: {self.cluster_name}")
            return existing_endpoint

        # Create new cluster
        self._log(f"Creating new Neptune cluster: {self.cluster_name}")
        try:
            # Use the VPC settings that were passed to create_cluster
            if not self.vpc_id or not self.subnet_ids:
                raise Exception("VPC and subnet settings must be provided before creating cluster")

            # Create cluster with provided VPC settings
            endpoint = self.create_cluster(
                subnet_ids=self.subnet_ids,
                security_group_id=self.security_group_id
            )
            
            return endpoint
            
        except Exception as e:
            self._log(f"Error setting up cluster: {str(e)}")
            raise
