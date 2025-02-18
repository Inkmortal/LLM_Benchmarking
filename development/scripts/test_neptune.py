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

def wait_for_cluster_available(neptune, cluster_name: str, timeout: int = 300) -> bool:
    """Wait for cluster to be available."""
    print("Waiting for cluster to be available...")
    start_time = time.time()
    
    while True:
        try:
            response = neptune.describe_db_clusters(
                DBClusterIdentifier=cluster_name
            )
            status = response['DBClusters'][0]['Status']
            
            if status == 'available':
                print("Cluster is available")
                return True
            elif status in ['failed', 'deleting', 'stopped']:
                print(f"Cluster is in {status} state")
                return False
                
            if time.time() - start_time > timeout:
                print(f"Timeout waiting for cluster (waited {timeout} seconds)")
                return False
                
            print(f"Cluster status: {status}, waiting...")
            time.sleep(10)
            
        except Exception as e:
            print(f"Error checking cluster status: {str(e)}")
            return False

def update_cluster_security_group(cluster_name: str, current_ip: str = None) -> bool:
    """Update Neptune cluster security group to allow access."""
    print(f"\nUpdating Neptune cluster {cluster_name} security group...")
    
    try:
        neptune = boto3.client('neptune')
        
        # Get cluster info
        clusters = neptune.describe_db_clusters(
            DBClusterIdentifier=cluster_name
        )
        
        if not clusters['DBClusters']:
            print(f"Cluster {cluster_name} not found!")
            return False
            
        cluster = clusters['DBClusters'][0]
        
        # Get VPC ID from subnet group
        subnet_group = neptune.describe_db_subnet_groups(
            DBSubnetGroupName=cluster['DBSubnetGroup']
        )['DBSubnetGroups'][0]
        vpc_id = subnet_group['VpcId']
        
        # Create new security group
        print(f"Creating new security group in VPC {vpc_id}...")
        ec2 = boto3.client('ec2')
        
        # Generate unique name with timestamp
        timestamp = int(time.time())
        group_name = f"neptune-access-{cluster_name}-{timestamp}"
        
        response = ec2.create_security_group(
            GroupName=group_name,
            Description=f"Security group for Neptune cluster {cluster_name}",
            VpcId=vpc_id
        )
        new_sg_id = response['GroupId']
        
        # Add inbound rule
        if current_ip:
            print(f"Adding rule for IP {current_ip}...")
            ec2.authorize_security_group_ingress(
                GroupId=new_sg_id,
                IpPermissions=[{
                    'FromPort': 8182,
                    'ToPort': 8182,
                    'IpProtocol': 'tcp',
                    'IpRanges': [{
                        'CidrIp': f"{current_ip}/32",
                        'Description': 'Neptune access'
                    }]
                }]
            )
        
        # Add new security group to cluster
        print("Adding security group to cluster...")
        vpc_security_group_ids = [sg['VpcSecurityGroupId'] for sg in cluster['VpcSecurityGroups']]
        vpc_security_group_ids.append(new_sg_id)
        
        neptune.modify_db_cluster(
            DBClusterIdentifier=cluster_name,
            VpcSecurityGroupIds=vpc_security_group_ids
        )
        
        # Wait for the change to take effect
        if not wait_for_cluster_available(neptune, cluster_name):
            print("Failed to update cluster security groups")
            return False
        
        print("Security group updated successfully")
        return True
        
    except Exception as e:
        print(f"Error updating security group: {str(e)}")
        return False

def check_security_groups(cluster_name: str, auto_update: bool = True) -> bool:
    """Check Neptune security group settings."""
    print("\nChecking Neptune security group settings...")
    
    try:
        # Get Neptune cluster details
        neptune = boto3.client('neptune')
        ec2 = boto3.client('ec2')
        
        # Get cluster info
        clusters = neptune.describe_db_clusters(
            DBClusterIdentifier=cluster_name
        )
        
        if not clusters['DBClusters']:
            print(f"Cluster {cluster_name} not found!")
            return False
            
        cluster = clusters['DBClusters'][0]
        vpc_security_groups = cluster['VpcSecurityGroups']
        
        print(f"\nCluster VPC Security Groups:")
        
        # Get current instance security groups if running on EC2
        instance_info = get_instance_identity()
        instance_security_groups = []
        if instance_info:
            instance_security_groups = instance_info.get('SecurityGroups', [])
            print("\nCurrent Instance Security Groups:")
            for sg in instance_security_groups:
                print(f"- {sg['GroupName']} ({sg['GroupId']})")
        else:
            print("\nNot running on EC2 - will use public IP for access")
            current_ip = get_current_ip()
            if current_ip:
                print(f"Current public IP: {current_ip}")
            else:
                print("Could not determine public IP")
        
        has_access = False
        for vpc_sg in vpc_security_groups:
            sg_id = vpc_sg['VpcSecurityGroupId']
            
            # Get security group details
            sg_details = ec2.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
            
            print(f"\nSecurity Group: {sg_details['GroupName']} ({sg_id})")
            print("Inbound Rules:")
            
            # Check inbound rules
            for rule in sg_details['IpPermissions']:
                if rule.get('FromPort', 0) <= 8182 <= rule.get('ToPort', 0):
                    for ip_range in rule.get('IpRanges', []):
                        print(f"- {ip_range['CidrIp']} (TCP {rule['FromPort']}-{rule['ToPort']})")
                        # If we're not on EC2, check if our IP is allowed
                        if not instance_info:
                            current_ip = get_current_ip()
                            if current_ip and ip_range['CidrIp'] in [f"{current_ip}/32", "0.0.0.0/0"]:
                                has_access = True
                    for group in rule.get('UserIdGroupPairs', []):
                        print(f"- Security Group: {group['GroupId']}")
                        # Check if our instance's security group is allowed
                        if instance_info and any(isg['GroupId'] == group['GroupId'] 
                                               for isg in instance_security_groups):
                            has_access = True
                            print("  (Current instance's security group)")
            
            if not has_access and auto_update:
                print("\nNo valid access rules found - attempting to add...")
                if not instance_info:
                    # Add current IP
                    current_ip = get_current_ip()
                    if current_ip and update_cluster_security_group(cluster_name, current_ip):
                        has_access = True
            
        if not has_access:
            print("\nWarning: No valid inbound rules found for port 8182!")
            print("Recommendations:")
            print("1. Add inbound rule for port 8182 to Neptune's security group")
            if instance_info:
                print("2. Allow access from this instance's security group")
                print("3. Or add CIDR range that includes this instance")
            else:
                print("2. Add CIDR range that includes your client IP")
            return False
            
        print("\nSecurity group configuration appears correct.")
        return True
        
    except Exception as e:
        print(f"Error checking security groups: {str(e)}")
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
        print("\nThis suggests a security group issue.")
        print("Please check:")
        print("1. Security group inbound rules allow port 8182")
        print("2. Security group is attached to the Neptune cluster")
        print("3. Your client (this machine) is allowed in the security group")
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
    
    # Check security groups first
    if not check_security_groups(CLUSTER_NAME, auto_update=True):
        print("\nSecurity group check failed!")
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
