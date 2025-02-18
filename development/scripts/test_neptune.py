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
import time

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

def get_instance_identity():
    """Get current instance identity information."""
    try:
        # First check if we're on EC2
        response = requests.get('http://169.254.169.254/latest/meta-data/instance-id', timeout=2)
        if response.status_code != 200:
            return None
            
        instance_id = response.text
        metadata = boto3.client('ec2').describe_instances(
            Filters=[{'Name': 'instance-id', 'Values': [instance_id]}]
        )
        return metadata['Reservations'][0]['Instances'][0]
    except:
        return None

def get_current_ip():
    """Get current public IP address."""
    try:
        response = requests.get('https://checkip.amazonaws.com', timeout=5)
        return response.text.strip()
    except:
        return None

def check_vpc_connectivity(cluster_name: str) -> bool:
    """Check VPC connectivity between SageMaker and Neptune."""
    print("\nChecking VPC connectivity...")
    
    try:
        # Get Neptune cluster details
        neptune = boto3.client('neptune')
        ec2 = boto3.client('ec2')
        sagemaker = boto3.client('sagemaker')
        
        # Get cluster info
        clusters = neptune.describe_db_clusters(
            DBClusterIdentifier=cluster_name
        )
        
        if not clusters['DBClusters']:
            print(f"Cluster {cluster_name} not found!")
            return False
            
        cluster = clusters['DBClusters'][0]
        neptune_vpc_id = cluster['VpcSecurityGroups'][0]['VpcId']
        neptune_subnet_ids = cluster['DBSubnetGroup']['Subnets']
        
        print(f"\nNeptune Cluster:")
        print(f"- VPC: {neptune_vpc_id}")
        print("- Subnets:")
        for subnet in neptune_subnet_ids:
            print(f"  - {subnet['SubnetIdentifier']}")
        
        # Get SageMaker notebook instance details
        notebook_name = os.environ.get('NOTEBOOK_NAME')
        if not notebook_name:
            print("\nCould not determine notebook instance name!")
            return False
            
        notebook = sagemaker.describe_notebook_instance(
            NotebookInstanceName=notebook_name
        )
        
        sagemaker_subnet_id = notebook.get('SubnetId')
        if not sagemaker_subnet_id:
            print("\nSageMaker notebook is not in a VPC!")
            return False
            
        # Get subnet details
        subnet = ec2.describe_subnets(SubnetIds=[sagemaker_subnet_id])['Subnets'][0]
        sagemaker_vpc_id = subnet['VpcId']
        
        print(f"\nSageMaker Notebook:")
        print(f"- VPC: {sagemaker_vpc_id}")
        print(f"- Subnet: {sagemaker_subnet_id}")
        
        if sagemaker_vpc_id != neptune_vpc_id:
            print("\nError: SageMaker and Neptune are in different VPCs!")
            print("They must be in the same VPC to communicate using private IPs.")
            return False
            
        # Check route tables
        route_tables = ec2.describe_route_tables(
            Filters=[
                {'Name': 'vpc-id', 'Values': [sagemaker_vpc_id]},
                {'Name': 'association.subnet-id', 'Values': [sagemaker_subnet_id]}
            ]
        )['RouteTables']
        
        if not route_tables:
            print("\nNo route table found for SageMaker subnet!")
            return False
            
        route_table = route_tables[0]
        print(f"\nRoute Table ({route_table['RouteTableId']}):")
        for route in route_table['Routes']:
            print(f"- {route.get('DestinationCidrBlock', 'Unknown')} -> {route.get('GatewayId', route.get('NatGatewayId', 'Unknown'))}")
        
        # Check if route table has route to Neptune subnet
        neptune_subnet = ec2.describe_subnets(
            SubnetIds=[neptune_subnet_ids[0]['SubnetIdentifier']]
        )['Subnets'][0]
        neptune_cidr = neptune_subnet['CidrBlock']
        
        has_route = False
        for route in route_table['Routes']:
            if route.get('DestinationCidrBlock') == neptune_cidr:
                has_route = True
                break
                
        if not has_route:
            print(f"\nNo route found from SageMaker subnet to Neptune subnet ({neptune_cidr})!")
            print("Please check VPC route tables.")
            return False
            
        print("\nVPC connectivity appears correct.")
        return True
        
    except Exception as e:
        print(f"Error checking VPC connectivity: {str(e)}")
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
    except (socket.timeout, socket.error) as e:
        print(f"TCP connection failed: {e}")
        print("\nThis suggests a network connectivity issue.")
        print("Please check:")
        print("1. SageMaker and Neptune are in the same VPC")
        print("2. Route tables allow traffic between subnets")
        print("3. Security groups allow port 8182")
        return False
    
    return True

def test_connection():
    """Test Neptune connection."""
    
    # Neptune endpoint
    CLUSTER_NAME = "graph-rag-originofcovid19dataset-benchmark"
    ENDPOINT = f"{CLUSTER_NAME}.cluster-c7m8ay28gj4o.us-west-2.neptune.amazonaws.com"
    PORT = 8182
    database_url = f"wss://{ENDPOINT}:{PORT}/gremlin"
    
    print(f"Database URL: {database_url}")
    
    # Check VPC connectivity first
    if not check_vpc_connectivity(CLUSTER_NAME):
        print("\nVPC connectivity check failed!")
        return False
    
    # Test network connectivity
    if not test_network_connectivity(ENDPOINT, PORT):
        print("\nNetwork connectivity test failed!")
        return False
    
    try:
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
