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
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q",
            "git+https://github.com/awslabs/amazon-neptune-tools.git#subdirectory=neptune-python-utils"
        ])
    except subprocess.CalledProcessError as e:
        print(f"Error installing neptune-python-utils: {e}")
        return False
    return True

# Install dependencies
print("Installing neptune-python-utils...")
if not install_requirements():
    sys.exit(1)

# Now import required packages
import boto3
import logging
from neptune_python_utils.endpoints import Endpoints
from neptune_python_utils.gremlin_utils import GremlinUtils

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """Test Neptune connection."""
    
    # Neptune endpoint
    CLUSTER_NAME = "graph-rag-originofcovid19dataset-benchmark"
    ENDPOINT = f"{CLUSTER_NAME}.cluster-c7m8ay28gj4o.us-west-2.neptune.amazonaws.com"
    PORT = 8182
    database_url = f"wss://{ENDPOINT}:{PORT}/gremlin"
    
    print(f"Database URL: {database_url}")
    
    try:
        # Create endpoints with proxy support
        endpoints = Endpoints(
            neptune_endpoint=ENDPOINT,
            region_name='us-west-2',
            proxy_dns='localhost',  # Using localhost since we're in a notebook
            proxy_port=PORT,
            remove_host_header=False  # Important for ALB
        )
        
        # Initialize Gremlin utilities
        GremlinUtils.init_statics(globals())
        gremlin_utils = GremlinUtils(endpoints)
        
        # Create connection with SSL verification disabled since we're using a proxy
        print("\nInitializing connection...")
        conn = gremlin_utils.remote_connection(ssl=False)
        
        # Create traversal source
        print("Creating traversal source...")
        g = gremlin_utils.traversal_source(connection=conn)
        
        # Test simple query
        print("\nTesting query...")
        result = g.inject(1).toList()  # Simple test query that doesn't require graph access
        print(f"Query result: {result}")
        
        # Try to get vertex count
        print("\nGetting vertex count...")
        count = g.V().count().next()
        print(f"Number of vertices: {count}")
        
        # Try to get some vertex properties
        print("\nGetting vertex properties...")
        vertices = g.V().limit(5).valueMap(True).toList()
        print("Sample vertices:")
        for v in vertices:
            print(f"\n{v}")
            
        print("\nConnection test successful!")
        return True
        
    except Exception as e:
        print(f"\nConnection failed: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        if 'conn' in locals():
            print("\nClosing connection...")
            try:
                conn.close()
            except:
                pass

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
