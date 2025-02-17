#!/usr/bin/env python3
"""
Simple script to test Neptune connection.
"""

import os
import sys
import subprocess
import pkg_resources

def install_requirements():
    """Install required packages."""
    requirements = {
        'gremlinpython': '3.6.3',  # Version compatible with Python 3.10
        'boto3': None,  # Latest version
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
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.driver.protocol import GremlinServerError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """Test Neptune connection."""
    
    # Neptune endpoint
    ENDPOINT = "graph-rag-originofcovid19dataset-benchmark.cluster-c7m8ay28gj4o.us-west-2.neptune.amazonaws.com"
    PORT = 8182
    database_url = f"wss://{ENDPOINT}:{PORT}/gremlin"
    
    print(f"Database URL: {database_url}")
    
    try:
        # Get AWS credentials
        print("Getting AWS credentials...")
        creds = boto3.Session().get_credentials().get_frozen_credentials()
        
        # Set up request with IAM auth
        print("Setting up IAM auth...")
        request = AWSRequest(method="GET", url=database_url, data=None)
        SigV4Auth(creds, "neptune-db", boto3.Session().region_name).add_auth(request)
        
        # Debug headers
        print("\nHeaders before conversion:")
        for k, v in request.headers.items():
            print(f"  {k}: {v}")
            
        # Keep headers as a dictionary
        headers = dict(request.headers)
        
        print("\nHeaders after conversion:")
        for k, v in headers.items():
            print(f"  {k}: {v}")
        
        # Initialize connection
        print("\nInitializing connection...")
        remoteConn = DriverRemoteConnection(
            database_url,
            'g',
            headers=headers
        )
        
        # Create traversal source
        print("Creating traversal source...")
        g = traversal().withRemote(remoteConn)
        
        # Test simple query
        print("\nTesting query...")
        result = g.inject(1).toList()
        print(f"Query result: {result}")
        
        # Try a real graph query
        print("\nTesting graph query...")
        vertices = g.V().limit(1).toList()
        print(f"Found vertices: {vertices}")
        
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
