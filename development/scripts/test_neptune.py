"""
Test Neptune connection and setup.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from utils.aws.neptune import NeptuneManager

def test_connection():
    """Test Neptune connection by setting up a cluster and running a simple query."""
    try:
        # Initialize Neptune manager
        manager = NeptuneManager(
            cluster_name='test-graph-rag-benchmark',
            cleanup_enabled=False,  # Never cleanup existing resources
            verbose=True,
            region='us-west-2'
        )
        
        # Set up cluster (will use existing if available)
        print("\nSetting up Neptune cluster:", manager.cluster_name)
        endpoint = manager.setup_cluster()
        
        print("\nCluster endpoint:", endpoint)
        
        print("\nTesting query...")
        result = manager.graph.g.inject(1).toList()  # Simple test query
        print("Query successful:", result)
        
        # Close connection gracefully
        if manager.graph:
            manager.graph.close()
        
    except Exception as e:
        print(f"\nConnection failed: {str(e)}")
        print("Error type:", type(e))
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_connection()
