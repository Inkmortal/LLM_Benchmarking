"""
Neptune database management utilities.
"""

import boto3
from typing import Optional
from .vpc import VPCManager
from .cluster import ClusterManager
from .graph import NeptuneGraph

class NeptuneManager:
    """
    Manages Neptune database infrastructure using modular components.
    """
    
    def __init__(
        self,
        cluster_name: str,
        cleanup_enabled: bool = True,
        verbose: bool = True,
        region: str = None,
        session: Optional[boto3.Session] = None,
        reuse_existing: bool = True
    ):
        """
        Initialize Neptune manager.
        
        Args:
            cluster_name: Name for the Neptune cluster
            cleanup_enabled: Whether to enable cleanup on deletion
            verbose: Whether to print detailed status messages
            region: AWS region (defaults to session region)
            session: Optional boto3 session (defaults to creating new session)
            reuse_existing: Whether to reuse existing resources if found
        """
        # Initialize session
        self.session = session or boto3.Session(region_name=region)
        
        # Initialize components
        self.vpc = VPCManager(
            cluster_name=cluster_name,
            session=self.session,
            verbose=verbose
        )
        
        self.cluster = ClusterManager(
            cluster_name=cluster_name,
            session=self.session,
            verbose=verbose
        )
        
        # Store configuration
        self.cluster_name = cluster_name
        self.cleanup_enabled = cleanup_enabled
        self.verbose = verbose
        self.reuse_existing = reuse_existing
        
        # Track state
        self.graph = None
    
    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def setup_cluster(self) -> str:
        """
        Set up Neptune infrastructure and return endpoint.
        
        Returns:
            Neptune cluster endpoint
        """
        try:
            # Set up VPC infrastructure
            vpc_id, subnet_ids, security_group_id = self.vpc.create_vpc()
            
            # Set up cluster
            endpoint = self.cluster.create_cluster(
                subnet_ids=subnet_ids,
                security_group_id=security_group_id
            )
            
            # Initialize graph connection
            self.graph = NeptuneGraph(
                endpoint=endpoint,
                session=self.session,
                verbose=self.verbose
            )
            
            return endpoint
            
        except Exception as e:
            self._log(f"Error setting up Neptune: {str(e)}")
            raise
    
    def cleanup(self) -> None:
        """Clean up all resources if cleanup is enabled."""
        if not self.cleanup_enabled:
            return
            
        try:
            # Close graph connection first
            if self.graph:
                self.graph.close()
                self.graph = None
            
            # Clean up cluster
            self.cluster.cleanup()
            
            # Clean up VPC last (dependencies must be gone)
            if self.vpc.vpc_id:
                self._log("Cleaning up VPC resources...")
                # Delete NAT Gateway
                if self.vpc.nat_gateway_id:
                    self.vpc.ec2.delete_nat_gateway(
                        NatGatewayId=self.vpc.nat_gateway_id
                    )
                
                # Release Elastic IP
                if self.vpc.eip_allocation_id:
                    self.vpc.ec2.release_address(
                        AllocationId=self.vpc.eip_allocation_id
                    )
                
                # Delete security group
                if self.vpc.security_group_id:
                    self.vpc.ec2.delete_security_group(
                        GroupId=self.vpc.security_group_id
                    )
                
                # Delete VPC
                self.vpc.ec2.delete_vpc(VpcId=self.vpc.vpc_id)
                
            self._log("Cleanup complete")
            
        except Exception as e:
            self._log(f"Error during cleanup: {str(e)}")
            raise
