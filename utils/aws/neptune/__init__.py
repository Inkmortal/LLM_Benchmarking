"""
Neptune database management utilities.
"""

from typing import Optional
import boto3
from .vpc import VPCManager
from .cluster import ClusterManager
from .graph import NeptuneGraph

class NeptuneManager:
    """
    Manages Neptune graph database operations.
    """
    
    def __init__(
        self,
        cluster_name: str,
        cleanup_enabled: bool = True,
        verbose: bool = True,
        region: str = None,
        session: Optional[boto3.Session] = None
    ):
        """
        Initialize Neptune manager.
        
        Args:
            cluster_name: Name for the Neptune cluster
            cleanup_enabled: Whether to enable cleanup on deletion
            verbose: Whether to print detailed status messages
            region: AWS region (defaults to session region)
            session: Optional boto3 session (defaults to creating new session)
        """
        self.cluster_name = cluster_name
        self.cleanup_enabled = cleanup_enabled
        self.verbose = verbose
        
        # Initialize session - use instance role by default
        self.session = session or boto3.Session(region_name=region)
        
        # Initialize managers
        self.vpc = VPCManager(cluster_name, self.session, verbose)
        self.cluster = ClusterManager(cluster_name, self.session, verbose)
        
        # Track graph interface
        self.graph = None
    
    def setup_cluster(self) -> str:
        """
        Set up Neptune cluster and return endpoint.
        
        Returns:
            Neptune cluster endpoint
        """
        try:
            # Create VPC infrastructure
            vpc_id, subnet_ids, security_group_id = self.vpc.create_vpc()
            
            # Create cluster
            endpoint = self.cluster.create_cluster(subnet_ids, security_group_id)
            
            # Initialize graph interface
            self.graph = NeptuneGraph(
                endpoint=endpoint,
                session=self.session,
                verbose=self.verbose
            )
            
            return endpoint
            
        except Exception as e:
            if self.verbose:
                print(f"Error setting up Neptune cluster: {str(e)}")
            raise
    
    def cleanup(self) -> None:
        """Clean up Neptune resources."""
        if not self.cleanup_enabled:
            return
            
        try:
            # Close graph connection
            if self.graph:
                self.graph.close()
                self.graph = None
            
            # Clean up cluster resources
            self.cluster.cleanup()
            
            # Clean up VPC resources
            if self.vpc.vpc_id:
                self.vpc.cleanup(self.vpc.vpc_id)
                
        except Exception as e:
            if self.verbose:
                print(f"Error during cleanup: {str(e)}")
            raise
