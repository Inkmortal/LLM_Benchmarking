"""Vector storage using OpenSearch for graph RAG."""

import os
import boto3
from typing import Dict, Any, List, Optional
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from utils.aws.opensearch_utils import OpenSearchManager

class VectorStore:
    """Handles vector storage and search using OpenSearch."""
    
    def __init__(
        self,
        index_name: str,
        search_type: str = 'script',
        similarity_threshold: Optional[float] = None,
        index_settings: Optional[Dict] = None,
        knn_params: Optional[Dict] = None
    ):
        """Initialize vector store.
        
        Args:
            index_name: Name of the OpenSearch index
            search_type: Type of vector search ('script' or 'knn')
            similarity_threshold: Minimum similarity score to include
            index_settings: Custom index settings
            knn_params: Parameters for k-NN algorithm
        """
        self.index_name = index_name
        self.search_type = search_type
        self.similarity_threshold = similarity_threshold
        self.index_settings = index_settings
        self.knn_params = knn_params
        
        # Track component state
        self._initialized = False
        self.opensearch_manager = None
        self.opensearch = None
        
        # Initialize OpenSearch
        self._init_vector_store()
    
    def _get_domain_name(self) -> str:
        """Get consistent domain name for benchmarking."""
        return "rag-bench"  # Simple, consistent name for benchmark domain
    
    def _init_vector_store(self):
        """Initialize OpenSearch vector store."""
        try:
            # First check if domain exists and get endpoint
            client = boto3.client('opensearch')
            domain_name = self._get_domain_name()
            
            try:
                # Try to get existing domain
                response = client.describe_domain(DomainName=domain_name)
                if 'DomainStatus' in response:
                    status = response['DomainStatus']
                    if 'Endpoints' in status:
                        endpoint = status['Endpoints'].get('vpc') or status['Endpoint']
                        if endpoint:
                            print(f"Using existing OpenSearch domain: {domain_name}")
                            self._setup_client(endpoint)
                            return
            except client.exceptions.ResourceNotFoundException:
                pass
            
            # Domain doesn't exist or isn't ready, create/wait for it
            self.opensearch_manager = OpenSearchManager(
                domain_name=domain_name,
                cleanup_enabled=False,  # Never cleanup during init
                verbose=True  # Always show progress for vector store
            )
            
            # Get endpoint
            endpoint = self.opensearch_manager.setup_domain()
            self._setup_client(endpoint)
            
        except Exception as e:
            # Clean up on initialization failure
            self.cleanup(delete_resources=False)
            raise Exception(f"Failed to initialize vector store: {str(e)}") from e
    
    def _setup_client(self, endpoint: str):
        """Set up OpenSearch client with endpoint."""
        # Get AWS credentials for auth
        credentials = boto3.Session().get_credentials()
        region = boto3.Session().region_name
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            'es',
            session_token=credentials.token
        )
        
        # Initialize OpenSearch client with proper auth
        self.opensearch = OpenSearch(
            hosts=[{'host': endpoint, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=60,
            max_retries=10,
            retry_on_timeout=True
        )
        
        # Create index if it doesn't exist
        if not self.opensearch.indices.exists(index=self.index_name):
            self._create_index()
        
        self._initialized = True
    
    def _create_index(self):
        """Create OpenSearch index with vector mapping."""
        # Default settings for vector search
        settings = {
            'index': {
                'number_of_shards': 1,
                'number_of_replicas': 0,
                'knn': {
                    'algo_param': {
                        'ef_search': 512  # Higher values = more accurate but slower
                    }
                }
            }
        }
        
        # Default mapping for vector field
        mapping = {
            'properties': {
                'vector': {
                    'type': 'knn_vector',
                    'dimension': 1536,  # OpenAI embedding size
                    'method': {
                        'name': 'hnsw',
                        'space_type': 'cosinesimil',
                        'engine': 'nmslib',
                        'parameters': {
                            'ef_construction': 512,
                            'm': 16
                        }
                    }
                },
                'content': {'type': 'text'},
                'metadata': {'type': 'object'}
            }
        }
        
        # Override with custom settings if provided
        if self.index_settings:
            settings.update(self.index_settings)
        
        # Override k-NN parameters if provided
        if self.knn_params:
            mapping['properties']['vector']['method']['parameters'].update(self.knn_params)
        
        # Create index
        self.opensearch.indices.create(
            index=self.index_name,
            body={
                'settings': settings,
                'mappings': mapping
            }
        )
    
    def ensure_initialized(self):
        """Ensure vector store is properly initialized."""
        if not self._initialized:
            raise RuntimeError("VectorStore not properly initialized")
        if not self.opensearch:
            raise RuntimeError("OpenSearch client not available")
    
    def store_document(
        self,
        doc_id: str,
        content: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store document with vector embedding.
        
        Args:
            doc_id: Document identifier
            content: Document content
            vector: Vector embedding
            metadata: Optional document metadata
        """
        self.ensure_initialized()
        
        try:
            # Store document with vector
            self.opensearch.index(
                index=self.index_name,
                id=doc_id,
                body={
                    'content': content,
                    'vector': vector,
                    'metadata': metadata or {}
                }
            )
        except Exception as e:
            raise Exception(f"Failed to store document {doc_id}: {str(e)}") from e
    
    def search(
        self,
        query_vector: List[float],
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity.
        
        Args:
            query_vector: Query vector embedding
            k: Number of results to return
            
        Returns:
            List of document data with scores
        """
        self.ensure_initialized()
        
        try:
            if self.search_type == 'knn':
                # Use k-NN search
                body = {
                    'size': k,
                    'query': {
                        'knn': {
                            'vector': {
                                'vector': query_vector,
                                'k': k
                            }
                        }
                    }
                }
            else:
                # Use script score with cosine similarity
                body = {
                    'size': k,
                    'query': {
                        'script_score': {
                            'query': {'match_all': {}},
                            'script': {
                                'source': "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                                'params': {'query_vector': query_vector}
                            }
                        }
                    }
                }
                
                # Add score threshold if specified
                if self.similarity_threshold:
                    body['min_score'] = self.similarity_threshold
            
            # Execute search
            response = self.opensearch.search(
                index=self.index_name,
                body=body
            )
            
            # Process results
            results = []
            for hit in response['hits']['hits']:
                results.append({
                    'id': hit['_id'],
                    'content': hit['_source']['content'],
                    'metadata': hit['_source']['metadata'],
                    'score': hit['_score']
                })
                
            return results
            
        except Exception as e:
            raise Exception(f"Failed to search: {str(e)}") from e
    
    def cleanup(self, delete_resources: bool = False):
        """Clean up all resources.
        
        Args:
            delete_resources: Whether to delete OpenSearch domain
        """
        if self.opensearch:
            try:
                # Delete index if it exists
                if self.opensearch.indices.exists(index=self.index_name):
                    self.opensearch.indices.delete(index=self.index_name)
            except:
                pass  # Best effort cleanup
            self.opensearch = None
            
        if self.opensearch_manager:
            try:
                # Only delete domain if requested
                self.opensearch_manager.cleanup_enabled = delete_resources
                self.opensearch_manager.cleanup()
            except:
                pass  # Best effort cleanup
            self.opensearch_manager = None
            
        self._initialized = False
