"""
Test Neptune connection and setup.

This script:
1. Validates/fixes VPC configuration
2. Validates/fixes Neptune cluster configuration
3. Tests connectivity from notebook to Neptune
4. Only cleans up resources if explicitly requested with --cleanup flag
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from utils.aws.neptune import NeptuneManager

def test_connection(cleanup: bool = False):
    """
    Test Neptune connection by setting up a cluster and running a simple query.
    
    Args:
        cleanup: Whether to clean up resources after test (default: False)
    """
    manager = None
    try:
        # Initialize Neptune manager (never cleanup on error)
        manager = NeptuneManager(
            cluster_name='test-graph-rag-benchmark',
            cleanup_enabled=False,
            verbose=True,
            region='us-west-2'
        )
        
        # Set up cluster (will use existing if available)
        print("\nValidating Neptune infrastructure...")
        endpoint = manager.setup_cluster()
        print("\nCluster endpoint:", endpoint)
        
        # Test connectivity
        print("\nTesting connectivity...")
        result = manager.graph.g.inject(1).toList()
        print("Query successful:", result)
        
        print("\nAll tests passed!")
        print("You can now use this endpoint in your notebooks:", endpoint)
        
        # Only cleanup if explicitly requested and test passed
        if cleanup:
            print("\nWARNING: --cleanup flag detected")
            confirm = input("Are you sure you want to delete all Neptune resources? [y/N] ")
            if confirm.lower() == 'y':
                print("\nCleaning up Neptune resources...")
                manager.cleanup_enabled = True
                manager.cleanup()
            else:
                print("\nSkipping cleanup")
        
    except Exception as e:
        print(f"\nConnection failed: {str(e)}")
        print("Error type:", type(e))
        import traceback
        traceback.print_exc()
        
        if manager and manager.graph:
            manager.graph.close()

def main():
    parser = argparse.ArgumentParser(description='Test Neptune connectivity')
    parser.add_argument('--cleanup', action='store_true', 
                       help='Clean up resources after test (requires confirmation)')
    args = parser.parse_args()
    
    test_connection(cleanup=args.cleanup)

if __name__ == '__main__':
    main()
