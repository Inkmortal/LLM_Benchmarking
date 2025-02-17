#!/usr/bin/env python3
"""
Simple script to test Neptune connection.
"""

import os
import sys
import boto3
import logging
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal

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
        request = AWSRequest(method="GET", url=database_url)
        SigV4Auth(creds, "neptune-db", boto3.Session().region_name).add_auth(request)
        
        # Initialize connection
        print("Initializing connection...")
        remoteConn = DriverRemoteConnection(
            database_url,
            'g',
            headers=request.headers.items(),
            message_timeout=5000  # 5 seconds
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
        
    except Exception as e:
        print(f"\nConnection failed: {str(e)}")
        return False
        
    finally:
        # Clean up
        if 'remoteConn' in locals():
            print("\nClosing connection...")
            remoteConn.close()

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
