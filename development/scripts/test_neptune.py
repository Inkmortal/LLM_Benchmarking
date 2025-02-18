#!/usr/bin/env python3
"""
Simple script to test Neptune connection.
"""

import os
import sys
import subprocess
import pkg_resources

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

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

# Import our Neptune manager
from utils.aws.neptune_utils import NeptuneManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """Test Neptune connection."""
    
    # Neptune cluster name
    CLUSTER_NAME = "test-graph-rag-benchmark"
    
    try:
        # Create Neptune manager
        print(f"\nSetting up Neptune cluster: {CLUSTER_NAME}")
        manager = NeptuneManager(
            cluster_name=CLUSTER_NAME,
            cleanup_enabled=True,  # Will clean up resources on failure
            verbose=True,
            region='us-west-2'
        )
        
        # Set up cluster in VPC
        endpoint = manager.setup_cluster()
        print(f"\nCluster endpoint: {endpoint}")
        
        # Initialize Gremlin utilities
        print("\nInitializing Gremlin utilities...")
        GremlinUtils.init_statics(globals())
        gremlin_utils = GremlinUtils(Endpoints(neptune_endpoint=endpoint))
        
        # Create connection
        print("\nInitializing connection...")
        conn = gremlin_utils.remote_connection()
        
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
        
        # Clean up Neptune resources
        if 'manager' in locals():
            print("\nCleaning up Neptune resources...")
            try:
                manager.cleanup()
            except Exception as e:
                print(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
