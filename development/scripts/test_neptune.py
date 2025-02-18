#!/usr/bin/env python3
"""
Simple script to test Neptune connection.
"""

import os
import sys
import socket
import subprocess
import pkg_resources
import json

def install_requirements():
    """Install required packages."""
    requirements = {
        'gremlinpython': '3.6.3',  # Version compatible with Python 3.10
        'boto3': None,  # Latest version
        'requests': None  # For instance metadata
    }
    
    for package, version in requirements.items():
        try:
            pkg_resources.require(f"{package}=={version}" if version else package)
        except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
            print(f"Installing {package}...")
            spec = f"{package}=={version}" if version else package
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", spec])

# Install dependencies
print("Checking dependencies...")
install_requirements()

# Now import required packages
import boto3
import logging
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.driver.protocol import GremlinServerError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_sagemaker_subnet_cidr() -> str:
    """Get CIDR block of SageMaker notebook's subnet."""
    print("\nGetting SageMaker subnet CIDR...")
    
    try:
        # Get notebook name from environment
        notebook_name = os.environ.get('NOTEBOOK_NAME')
        if not notebook_name:
            # Try to get it from the instance metadata
            response = requests.get('http://169.254.169.254/latest/meta-data/tags/instance/Name', timeout=2)
            if response.status_code == 200:
                notebook_name = response.text
            else:
                raise Exception("Could not determine notebook instance name")
        
        print(f"Notebook instance: {notebook_name}")
        
        # Get notebook instance details
        sagemaker = boto3.client('sagemaker')
        notebook = sagemaker.describe_notebook_instance(
            NotebookInstanceName=notebook_name
        )
        
        subnet_id = notebook.get('SubnetId')
        if not subnet_id:
            raise Exception("Notebook instance is not in a VPC")
            
        print(f"Subnet ID: {subnet_id}")
        
        # Get subnet CIDR
        ec2 = boto3.client('ec2')
        subnet = ec2.describe_subnets(SubnetIds=[subnet_id])['Subnets'][0]
        cidr = subnet['CidrBlock']
        
        print(f"Subnet CIDR: {cidr}")
        return cidr
        
    except Exception as e:
        print(f"Error getting subnet CIDR: {str(e)}")
        raise

def update_neptune_security_group(cluster_name: str, cidr_block: str) -> bool:
    """Update Neptune security group to allow access from CIDR."""
    print(f"\nUpdating Neptune security group for cluster {cluster_name}...")
    
    try:
        # Get cluster info
        neptune = boto3.client('neptune')
        clusters = neptune.describe_db_clusters(
            DBClusterIdentifier=cluster_name
        )
        
        if not clusters['DBClusters']:
            print(f"Cluster {cluster_name} not found!")
            return False
            
        cluster = clusters['DBClusters'][0]
        
        # Get security groups
        security_groups = []
        for sg in cluster['VpcSecurityGroups']:
            security_groups.append(sg['VpcSecurityGroupId'])
            
        if not security_groups:
            print("No security groups found!")
            return False
            
        print(f"Found security groups: {security_groups}")
        
        # Update each security group
        ec2 = boto3.client('ec2')
        for sg_id in security_groups:
            print(f"\nChecking security group: {sg_id}")
            
            # Check if rule already exists
            sg = ec2.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
            rule_exists = False
            
            for rule in sg.get('IpPermissions', []):
                if rule.get('FromPort', 0) <= 8182 <= rule.get('ToPort', 0):
                    for ip_range in rule.get('IpRanges', []):
                        if ip_range['CidrIp'] == cidr_block:
                            print(f"Rule already exists for {cidr_block}")
                            rule_exists = True
                            break
                    if rule_exists:
                        break
            
            if not rule_exists:
                print(f"Adding rule for {cidr_block}...")
                ec2.authorize_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=[{
                        'FromPort': 8182,
                        'ToPort': 8182,
                        'IpProtocol': 'tcp',
                        'IpRanges': [{
                            'CidrIp': cidr_block,
                            'Description': 'SageMaker access'
                        }]
                    }]
                )
                print("Rule added successfully")
        
        return True
        
    except Exception as e:
        print(f"Error updating security group: {str(e)}")
        return False

def test_network_connectivity(endpoint: str, port: int = 8182) -> bool:
    """Test network connectivity to endpoint."""
    print(f"\nTesting network connectivity to {endpoint}:{port}")
    
    # Test DNS resolution
    try:
        print("Testing DNS resolution...")
        ip = socket.gethostbyname(endpoint)
        print(f"DNS resolution successful: {endpoint} -> {ip}")
    except socket.gaierror as e:
        print(f"DNS resolution failed: {e}")
        return False
    
    # Test TCP connection
    try:
        print("Testing TCP connection...")
        sock = socket.create_connection((endpoint, port), timeout=10)
        sock.close()
        print("TCP connection successful")
        return True
    except (socket.timeout, socket.error) as e:
        print(f"TCP connection failed: {e}")
        print("\nThis suggests a security group issue.")
        print("Please check:")
        print("1. Security group inbound rules allow port 8182")
        print("2. Security group is attached to the Neptune cluster")
        print("3. Your subnet CIDR is allowed in the security group")
        return False

def test_connection():
    """Test Neptune connection."""
    
    # Neptune endpoint
    CLUSTER_NAME = "graph-rag-originofcovid19dataset-benchmark"
    ENDPOINT = f"{CLUSTER_NAME}.cluster-c7m8ay28gj4o.us-west-2.neptune.amazonaws.com"
    PORT = 8182
    database_url = f"wss://{ENDPOINT}:{PORT}/gremlin"
    
    print(f"Database URL: {database_url}")
    
    try:
        # Get SageMaker subnet CIDR
        subnet_cidr = get_sagemaker_subnet_cidr()
        
        # Update Neptune security group
        if not update_neptune_security_group(CLUSTER_NAME, subnet_cidr):
            print("\nFailed to update security group!")
            return False
        
        # Test network connectivity
        if not test_network_connectivity(ENDPOINT, PORT):
            print("\nNetwork connectivity test failed!")
            return False
        
        # Get AWS credentials
        print("\nGetting AWS credentials...")
        creds = boto3.Session().get_credentials().get_frozen_credentials()
        
        # Set up request with IAM auth
        print("Setting up IAM auth...")
        request = AWSRequest(method="GET", url=database_url, data=None)
        SigV4Auth(creds, "neptune-db", boto3.Session().region_name).add_auth(request)
        
        # Initialize connection
        print("\nInitializing connection...")
        remoteConn = DriverRemoteConnection(
            database_url,
            'g',
            headers=dict(request.headers)
        )
        
        # Create traversal source
        print("Creating traversal source...")
        g = traversal().withRemote(remoteConn)
        
        # Test simple query
        print("\nTesting query...")
        result = g.inject(1).toList()
        print(f"Query result: {result}")
        
        print("\nConnection test successful!")
        return True
        
    except GremlinServerError as e:
        print(f"\nGremlin Server Error: {str(e)}")
        return False
    except Exception as e:
        print(f"\nConnection failed: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        if 'remoteConn' in locals():
            print("\nClosing connection...")
            try:
                remoteConn.close()
            except:
                pass

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
