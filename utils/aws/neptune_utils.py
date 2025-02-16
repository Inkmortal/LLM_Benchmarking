"""
Utilities for working with Amazon Neptune graph database.
"""

import os
import time
import json
import boto3
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.structure.graph import Graph

class NeptuneManager:
    """
    Manages Amazon Neptune graph database operations.
    """
    
    def __init__(
        self,
        cluster_name: str,
        cleanup_enabled: bool = True,
        verbose: bool = True
    ):
        """
        Initialize Neptune manager.
        
        Args:
            cluster_name: Name for the Neptune cluster
            cleanup_enabled: Whether to enable cleanup on deletion
            verbose: Whether to print detailed status messages
        """
        self.cluster_name = cluster_name
        self.cleanup_enabled = cleanup_enabled
        self.verbose = verbose
        
        # Initialize AWS clients
        self.neptune = boto3.client('neptune')
        
        # Track created resources
        self.cluster_id = None
        self.instance_id = None
        self.endpoint = None
        self.param_group_name = f"{cluster_name}-params"
        
        # Get identity for IAM auth
        sts = boto3.client('sts')
        self.identity = sts.get_caller_identity()
        self.current_arn = self.identity['Arn']
        
        # Track resource state
        self._resources_created = False
    
    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def _create_parameter_group(self) -> None:
        """Create a custom DB cluster parameter group."""
        try:
            self._log(f"Creating parameter group: {self.param_group_name}")
            self.neptune.create_db_cluster_parameter_group(
                DBClusterParameterGroupName=self.param_group_name,
                DBParameterGroupFamily='neptune1.2',
                Description=f'Custom parameter group for {self.cluster_name}'
            )
            self._resources_created = True
        except ClientError as e:
            if e.response['Error']['Code'] != 'DBParameterGroupAlreadyExists':
                raise
            self._log(f"Using existing parameter group: {self.param_group_name}")
    
    def _wait_for_cluster(self, cluster_id: str, timeout: int = 1800) -> None:
        """Wait for cluster to be available using polling.
        
        Args:
            cluster_id: Cluster identifier
            timeout: Maximum wait time in seconds (default 30 minutes)
        """
        self._log("Waiting for cluster to be available...")
        start_time = time.time()
        while True:
            try:
                response = self.neptune.describe_db_clusters(
                    DBClusterIdentifier=cluster_id
                )
                status = response['DBClusters'][0]['Status']
                if status == 'available':
                    self._log("Cluster is available")
                    return
                elif status == 'failed':
                    raise Exception(f"Cluster creation failed: {cluster_id}")
                elif time.time() - start_time > timeout:
                    raise Exception(f"Timeout waiting for cluster: {cluster_id}")
                else:
                    self._log(f"Cluster status: {status}")
                    time.sleep(30)
            except ClientError as e:
                if e.response['Error']['Code'] == 'DBClusterNotFoundFault':
                    raise Exception(f"Cluster not found: {cluster_id}")
                raise
    
    def _wait_for_instance(self, instance_id: str, timeout: int = 1800) -> None:
        """Wait for instance to be available using polling.
        
        Args:
            instance_id: Instance identifier
            timeout: Maximum wait time in seconds (default 30 minutes)
        """
        self._log("Waiting for instance to be available...")
        start_time = time.time()
        while True:
            try:
                response = self.neptune.describe_db_instances(
                    DBInstanceIdentifier=instance_id
                )
                status = response['DBInstances'][0]['DBInstanceStatus']
                if status == 'available':
                    self._log("Instance is available")
                    return
                elif status == 'failed':
                    raise Exception(f"Instance creation failed: {instance_id}")
                elif time.time() - start_time > timeout:
                    raise Exception(f"Timeout waiting for instance: {instance_id}")
                else:
                    self._log(f"Instance status: {status}")
                    time.sleep(30)
            except ClientError as e:
                if e.response['Error']['Code'] == 'DBInstanceNotFound':
                    raise Exception(f"Instance not found: {instance_id}")
                raise
    
    def _ensure_instance(self) -> None:
        """Ensure cluster has at least one instance."""
        # Check existing instances
        instances = self.neptune.describe_db_instances(
            Filters=[{'Name': 'db-cluster-id', 'Values': [self.cluster_id]}]
        )
        
        if not instances['DBInstances']:
            self._log("Creating serverless instance...")
            self.instance_id = f"{self.cluster_id}-instance"
            
            # Create instance
            self.neptune.create_db_instance(
                DBInstanceIdentifier=self.instance_id,
                DBClusterIdentifier=self.cluster_id,
                Engine='neptune',
                DBInstanceClass='db.serverless'
            )
            
            # Wait for instance
            self._wait_for_instance(self.instance_id)
            self._resources_created = True
            
        else:
            instance = instances['DBInstances'][0]
            self.instance_id = instance['DBInstanceIdentifier']
            
            # Only wait if instance not ready
            if instance['DBInstanceStatus'] != 'available':
                self._wait_for_instance(self.instance_id)
            else:
                self._log(f"Using existing instance: {self.instance_id}")
    
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
                    # Create parameter group first
                    self._create_parameter_group()
                    
                    # Create new cluster
                    self._log(f"Creating Neptune cluster: {self.cluster_name}")
                    
                    # Create cluster with serverless configuration
                    response = self.neptune.create_db_cluster(
                        DBClusterIdentifier=self.cluster_name,
                        Engine='neptune',
                        EngineVersion='1.2.1.0',
                        ServerlessV2ScalingConfiguration={
                            'MinCapacity': 1.0,
                            'MaxCapacity': 8.0
                        },
                        EnableIAMDatabaseAuthentication=True,
                        DeletionProtection=False,
                        Port=8182,
                        DBClusterParameterGroupName=self.param_group_name
                    )
                    
                    cluster = response['DBCluster']
                    self.cluster_id = cluster['DBClusterIdentifier']
                    
                    # Wait for cluster to be available
                    self._wait_for_cluster(self.cluster_id)
                    
                    # Get endpoint
                    response = self.neptune.describe_db_clusters(
                        DBClusterIdentifier=self.cluster_id
                    )
                    self.endpoint = response['DBClusters'][0]['Endpoint']
                    
                    self._log(f"Neptune cluster created: {self.cluster_id}")
                    self._resources_created = True
                else:
                    raise
            
            # Ensure instance exists and is ready
            self._ensure_instance()
            
            # Only wait for DNS if we created new resources
            if self._resources_created:
                self._log("Waiting for endpoint to be resolvable...")
                time.sleep(60)  # Give DNS time to propagate
            
            return self.endpoint
            
        except Exception as e:
            self._log(f"Error setting up Neptune cluster: {str(e)}")
            raise
    
    def cleanup(self) -> None:
        """Clean up Neptune resources."""
        if not self.cleanup_enabled:
            return
            
        try:
            if self.instance_id:
                self._log(f"Deleting instance: {self.instance_id}")
                try:
                    self.neptune.delete_db_instance(
                        DBInstanceIdentifier=self.instance_id,
                        SkipFinalSnapshot=True
                    )
                    
                    # Wait for instance deletion
                    start_time = time.time()
                    while True:
                        try:
                            self.neptune.describe_db_instances(
                                DBInstanceIdentifier=self.instance_id
                            )
                            if time.time() - start_time > 1800:  # 30 minutes
                                raise Exception(f"Timeout waiting for instance deletion: {self.instance_id}")
                            time.sleep(30)
                        except ClientError as e:
                            if e.response['Error']['Code'] == 'DBInstanceNotFound':
                                break
                            raise
                        
                except ClientError as e:
                    if e.response['Error']['Code'] != 'DBInstanceNotFound':
                        raise
            
            if self.cluster_id:
                self._log(f"Deleting cluster: {self.cluster_id}")
                try:
                    self.neptune.delete_db_cluster(
                        DBClusterIdentifier=self.cluster_id,
                        SkipFinalSnapshot=True
                    )
                    
                    # Wait for cluster deletion
                    start_time = time.time()
                    while True:
                        try:
                            self.neptune.describe_db_clusters(
                                DBClusterIdentifier=self.cluster_id
                            )
                            if time.time() - start_time > 1800:  # 30 minutes
                                raise Exception(f"Timeout waiting for cluster deletion: {self.cluster_id}")
                            time.sleep(30)
                        except ClientError as e:
                            if e.response['Error']['Code'] == 'DBClusterNotFoundFault':
                                break
                            raise
                        
                except ClientError as e:
                    if e.response['Error']['Code'] != 'DBClusterNotFoundFault':
                        raise
                
                # Delete parameter group
                try:
                    self._log(f"Deleting parameter group: {self.param_group_name}")
                    self.neptune.delete_db_cluster_parameter_group(
                        DBClusterParameterGroupName=self.param_group_name
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] != 'DBParameterGroupNotFound':
                        raise
                
                self._log("Cleanup complete")
                
        except Exception as e:
            self._log(f"Error during cleanup: {str(e)}")
            raise

class NeptuneGraph:
    """
    Interface for working with Neptune graph database.
    """
    
    def __init__(
        self,
        endpoint: str,
        max_retries: int = 5,
        retry_delay: float = 1.0
    ):
        """
        Initialize Neptune graph interface.
        
        Args:
            endpoint: Neptune cluster endpoint
            max_retries: Maximum connection retry attempts
            retry_delay: Initial delay between retries (doubles each attempt)
        """
        self.endpoint = endpoint
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize connection state
        self._session = None
        self._loop = None
        self.connection = None
        self.g = None
        
        # Set up connection with retries
        self._connect_with_retries()
    
    def _connect_with_retries(self):
        """Initialize connection with retries."""
        # Set up event loop
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Create new session for each attempt
                self._session = aiohttp.ClientSession()
                
                # Initialize Gremlin connection
                self.connection = DriverRemoteConnection(
                    f'wss://{self.endpoint}:8182/gremlin',
                    'g'
                )
                self.g = Graph().traversal().withRemote(self.connection)
                
                # Test connection
                self.g.V().limit(1).toList()
                return  # Success
                
            except Exception as e:
                last_error = e
                self._cleanup_session()
                
                if attempt < self.max_retries - 1:
                    delay = min(60, self.retry_delay * (2 ** attempt))
                    time.sleep(delay)
                    continue
                
                raise ConnectionError(
                    f"Failed to connect to Neptune after {self.max_retries} attempts"
                ) from last_error
    
    def _cleanup_session(self):
        """Clean up aiohttp session."""
        if self._session and not self._session.closed:
            self._loop.run_until_complete(self._session.close())
        self._session = None
    
    def close(self):
        """Close all connections."""
        if self.connection:
            self.connection.close()
            self.connection = None
        
        self._cleanup_session()
        
        if self._loop:
            self._loop.close()
            self._loop = None
    
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
        if not self.g:
            raise RuntimeError("Graph connection not initialized")
            
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
        if not self.g:
            raise RuntimeError("Graph connection not initialized")
            
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
        if not self.g:
            raise RuntimeError("Graph connection not initialized")
            
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
        if not self.g:
            raise RuntimeError("Graph connection not initialized")
            
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
        if not self.g:
            raise RuntimeError("Graph connection not initialized")
            
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
