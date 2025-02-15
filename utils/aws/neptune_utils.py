"""
Utilities for working with Amazon Neptune graph database.
"""

import os
import time
import boto3
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError

class NeptuneManager:
    """
    Manages Amazon Neptune graph database operations.
    """
    
    def __init__(
        self,
        cluster_name: str,
        instance_type: str = "db.r6g.xlarge",
        cleanup_enabled: bool = True,
        verbose: bool = True
    ):
        """
        Initialize Neptune manager.
        
        Args:
            cluster_name: Name for the Neptune cluster
            instance_type: Neptune instance type
            cleanup_enabled: Whether to enable cleanup on deletion
            verbose: Whether to print detailed status messages
        """
        self.cluster_name = cluster_name
        self.instance_type = instance_type
        self.cleanup_enabled = cleanup_enabled
        self.verbose = verbose
        
        # Initialize AWS client
        self.neptune = boto3.client('neptune')
        
        # Track created resources
        self.cluster_id = None
        self.endpoint = None
    
    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def setup_cluster(self) -> str:
        """
        Set up Neptune cluster and return endpoint.
        
        Returns:
            Neptune cluster endpoint
        """
        try:
            # Check if cluster already exists
            try:
                response = self.neptune.describe_db_clusters(
                    DBClusterIdentifier=self.cluster_name
                )
                cluster = response['DBClusters'][0]
                self.cluster_id = cluster['DBClusterIdentifier']
                self.endpoint = cluster['Endpoint']
                self._log(f"Using existing Neptune cluster: {self.cluster_id}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'DBClusterNotFoundFault':
                    # Create new cluster
                    self._log(f"Creating Neptune cluster: {self.cluster_name}")
                    
                    # Create cluster
                    response = self.neptune.create_db_cluster(
                        DBClusterIdentifier=self.cluster_name,
                        Engine='neptune',
                        EngineVersion='1.2.1.0',
                        DBClusterParameterGroupName='default.neptune1',
                        VpcSecurityGroupIds=['default'],
                        AvailabilityZones=['us-west-2a'],
                        Port=8182,
                        DBSubnetGroupName='default',
                        BackupRetentionPeriod=1,
                        DeletionProtection=False
                    )
                    
                    cluster = response['DBCluster']
                    self.cluster_id = cluster['DBClusterIdentifier']
                    
                    # Create instance
                    self.neptune.create_db_instance(
                        DBInstanceIdentifier=f"{self.cluster_name}-instance-1",
                        DBInstanceClass=self.instance_type,
                        Engine='neptune',
                        DBClusterIdentifier=self.cluster_id,
                        AvailabilityZone='us-west-2a'
                    )
                    
                    # Wait for cluster to be available
                    self._log("Waiting for cluster to be available...")
                    waiter = self.neptune.get_waiter('db_cluster_available')
                    waiter.wait(
                        DBClusterIdentifier=self.cluster_id,
                        WaiterConfig={'Delay': 30, 'MaxAttempts': 60}
                    )
                    
                    # Get endpoint
                    response = self.neptune.describe_db_clusters(
                        DBClusterIdentifier=self.cluster_id
                    )
                    self.endpoint = response['DBClusters'][0]['Endpoint']
                    
                    self._log(f"Neptune cluster created: {self.cluster_id}")
                else:
                    raise
            
            return self.endpoint
            
        except Exception as e:
            self._log(f"Error setting up Neptune cluster: {str(e)}")
            raise
    
    def cleanup(self) -> None:
        """Clean up Neptune resources."""
        if not self.cleanup_enabled:
            return
            
        try:
            if self.cluster_id:
                self._log(f"Cleaning up Neptune cluster: {self.cluster_id}")
                
                # Delete instances
                response = self.neptune.describe_db_instances(
                    Filters=[{
                        'Name': 'db-cluster-id',
                        'Values': [self.cluster_id]
                    }]
                )
                
                for instance in response['DBInstances']:
                    instance_id = instance['DBInstanceIdentifier']
                    self._log(f"Deleting instance: {instance_id}")
                    self.neptune.delete_db_instance(
                        DBInstanceIdentifier=instance_id,
                        SkipFinalSnapshot=True
                    )
                
                # Wait for instances to be deleted
                self._log("Waiting for instances to be deleted...")
                waiter = self.neptune.get_waiter('db_instance_deleted')
                for instance in response['DBInstances']:
                    waiter.wait(
                        DBInstanceIdentifier=instance['DBInstanceIdentifier'],
                        WaiterConfig={'Delay': 30, 'MaxAttempts': 60}
                    )
                
                # Delete cluster
                self._log(f"Deleting cluster: {self.cluster_id}")
                self.neptune.delete_db_cluster(
                    DBClusterIdentifier=self.cluster_id,
                    SkipFinalSnapshot=True
                )
                
                # Wait for cluster to be deleted
                self._log("Waiting for cluster to be deleted...")
                waiter = self.neptune.get_waiter('db_cluster_deleted')
                waiter.wait(
                    DBClusterIdentifier=self.cluster_id,
                    WaiterConfig={'Delay': 30, 'MaxAttempts': 60}
                )
                
                self._log("Cleanup complete")
                
        except Exception as e:
            self._log(f"Error during cleanup: {str(e)}")
            raise

class NeptuneGraph:
    """
    Interface for working with Neptune graph database.
    """
    
    def __init__(self, endpoint: str):
        """
        Initialize Neptune graph interface.
        
        Args:
            endpoint: Neptune cluster endpoint
        """
        self.endpoint = endpoint
        
        # Initialize Gremlin client
        from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
        from gremlin_python.structure.graph import Graph
        
        self.connection = DriverRemoteConnection(
            f'wss://{endpoint}:8182/gremlin',
            'g'
        )
        self.g = Graph().traversal().withRemote(self.connection)
    
    def close(self):
        """Close connection to Neptune."""
        if self.connection:
            self.connection.close()
    
    def add_vertex(
        self,
        label: str,
        properties: Dict[str, Any],
        id: Optional[str] = None
    ) -> str:
        """
        Add vertex to graph.
        
        Args:
            label: Vertex label
            properties: Vertex properties
            id: Optional vertex ID
            
        Returns:
            Vertex ID
        """
        if id:
            vertex = self.g.addV(label).property('id', id)
        else:
            vertex = self.g.addV(label)
            
        for key, value in properties.items():
            vertex = vertex.property(key, value)
            
        result = vertex.next()
        return result.id
    
    def add_edge(
        self,
        from_id: str,
        to_id: str,
        label: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add edge between vertices.
        
        Args:
            from_id: Source vertex ID
            to_id: Target vertex ID
            label: Edge label
            properties: Optional edge properties
            
        Returns:
            Edge ID
        """
        edge = self.g.V(from_id).addE(label).to(self.g.V(to_id))
        
        if properties:
            for key, value in properties.items():
                edge = edge.property(key, value)
                
        result = edge.next()
        return result.id
    
    def get_vertices(
        self,
        label: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get vertices matching criteria.
        
        Args:
            label: Optional vertex label to filter by
            properties: Optional property values to filter by
            limit: Optional maximum number of results
            
        Returns:
            List of vertex data
        """
        if label:
            query = self.g.V().hasLabel(label)
        else:
            query = self.g.V()
            
        if properties:
            for key, value in properties.items():
                query = query.has(key, value)
                
        if limit:
            query = query.limit(limit)
            
        results = query.valueMap(True).toList()
        return results
    
    def get_edges(
        self,
        label: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get edges matching criteria.
        
        Args:
            label: Optional edge label to filter by
            properties: Optional property values to filter by
            limit: Optional maximum number of results
            
        Returns:
            List of edge data
        """
        if label:
            query = self.g.E().hasLabel(label)
        else:
            query = self.g.E()
            
        if properties:
            for key, value in properties.items():
                query = query.has(key, value)
                
        if limit:
            query = query.limit(limit)
            
        results = query.valueMap(True).toList()
        return results
    
    def get_neighbors(
        self,
        vertex_id: str,
        direction: str = 'both',
        edge_label: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get neighboring vertices.
        
        Args:
            vertex_id: ID of vertex to get neighbors for
            direction: 'in', 'out', or 'both'
            edge_label: Optional edge label to filter by
            limit: Optional maximum number of results
            
        Returns:
            List of neighbor data
        """
        if direction == 'in':
            query = self.g.V(vertex_id).in_()
        elif direction == 'out':
            query = self.g.V(vertex_id).out()
        else:
            query = self.g.V(vertex_id).both()
            
        if edge_label:
            query = query.hasLabel(edge_label)
            
        if limit:
            query = query.limit(limit)
            
        results = query.valueMap(True).toList()
        return results
