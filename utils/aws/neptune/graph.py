"""
Neptune graph database interface.
"""

import time
from typing import Dict, Any, Optional, List
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.traversal import __ as _

class NeptuneGraph:
    """Interface for working with Neptune graph database."""
    
    def __init__(
        self,
        endpoint: str,
        max_retries: int = 5,
        retry_delay: float = 1.0,
        session: Optional[boto3.Session] = None,
        verbose: bool = True
    ):
        """
        Initialize Neptune graph interface.
        
        Args:
            endpoint: Neptune cluster endpoint
            max_retries: Maximum connection retry attempts
            retry_delay: Initial delay between retries (doubles each attempt)
            session: Optional boto3 session (defaults to creating new session)
            verbose: Whether to print detailed status messages
        """
        self.endpoint = endpoint
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        # Initialize session - use instance role by default
        self.session = session or boto3.Session()
        self.verbose = verbose
        
        # Initialize connection state
        self.connection = None
        self.g = None
        
        # Set up connection with retries
        self._connect_with_retries()
    
    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def _connect_with_retries(self):
        """Initialize connection with retries."""
        database_url = f"wss://{self.endpoint}:8182/gremlin"
        
        # Get AWS credentials for IAM auth
        creds = self.session.get_credentials().get_frozen_credentials()
        request = AWSRequest(method="GET", url=database_url, data=None)
        SigV4Auth(creds, "neptune-db", self.session.region_name).add_auth(request)
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Initialize Gremlin connection with IAM auth
                self.connection = DriverRemoteConnection(
                    database_url,
                    'g',
                    headers=request.headers.items()
                )
                self.g = traversal().withRemote(self.connection)
                
                # Test connection
                self.g.V().limit(1).toList()
                self._log("Connection successful")
                return
                
            except Exception as e:
                last_error = e
                if self.connection:
                    self.connection.close()
                    self.connection = None
                
                if attempt < self.max_retries - 1:
                    delay = min(60, self.retry_delay * (2 ** attempt))
                    self._log(f"Connection failed, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                
                raise ConnectionError(
                    f"Failed to connect to Neptune after {self.max_retries} attempts"
                ) from last_error
    
    def close(self):
        """Close all connections."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.g = None
    
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
            
        edge = self.g.V(from_id).addE(label).to(_.V(to_id))
        
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
