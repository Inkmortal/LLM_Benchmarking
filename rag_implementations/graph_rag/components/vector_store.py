"""Vector storage using OpenSearch for graph RAG."""

import os
import time
import random
import boto3
import json
from typing import Dict, Any, List, Optional
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth
from botocore.exceptions import ClientError

class VectorStore:
    """Handles vector storage and search using OpenSearch."""
    
    def __init__(
        self,
        index_name: str,
        search_type: str = 'script',
        similarity_threshold: Optional[float] = None,
        index_settings: Optional[Dict] = None,
        max_retries: int = 5,
        min_delay: float = 1.0,
        max_delay: float = 60.0,
        embedding_model_id: str = "cohere.embed-english-v3"
    ):
        """Initialize vector store.

        Args:
            index_name: Name of the OpenSearch index
            search_type: Type of vector search ('script' or 'knn')
            similarity_threshold: Minimum similarity score to include
            index_settings: Custom index settings for OpenSearch
            max_retries: Maximum number of retry attempts
            min_delay: Minimum delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            embedding_model_id: The Bedrock model ID for embeddings
        """
        self.index_name = index_name
        self.search_type = search_type
        self.similarity_threshold = similarity_threshold
        self.index_settings = index_settings or {}
        self.max_retries = max_retries
        self.min_delay = min_delay
        self.max_delay = max_delay

        # Initialize Bedrock client for embeddings
        self.bedrock = boto3.client('bedrock-runtime')
        self.embedding_model_id = embedding_model_id

        # Initialize OpenSearch client
        self._init_client()

        # Ensure index exists
        self._create_index_if_not_exists()
    
    def _init_client(self):
        """Initialize OpenSearch client."""
        # Get OpenSearch host from environment
        self.opensearch_host = os.getenv('OPENSEARCH_HOST')
        if not self.opensearch_host:
            raise ValueError("OPENSEARCH_HOST environment variable is required")
        
        # Get AWS credentials for auth
        credentials = boto3.Session().get_credentials()
        region = boto3.Session().region_name
        self.awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            'es',
            session_token=credentials.token
        )
        
        # Initialize OpenSearch client
        self.opensearch = OpenSearch(
            hosts=[{'host': self.opensearch_host, 'port': 443}],
            http_auth=self.awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=60,
            max_retries=10,
            retry_on_timeout=True
        )
    
    def _create_index_if_not_exists(self):
        """Create OpenSearch index with appropriate mapping and settings."""
        if not self.opensearch.indices.exists(self.index_name):
            # Default settings
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
            
            # Update with custom settings
            settings.update(self.index_settings)
            
            # Default mapping for vector field
            mapping = {
                'properties': {
                    'embedding': {
                        'type': 'knn_vector',
                        'dimension': 1024,  # Cohere embedding dimension
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
            
            settings = {
                'index': {
                    'number_of_shards': 1,
                    'number_of_replicas': 0,
                    'knn': True,  # Enable k-NN
                    'knn.algo_param.ef_search': 512
                }
            }

            # Update with custom settings
            settings.update(self.index_settings)

            # Mapping for vector field - supports both k-NN and script score
            mapping = {
                'properties': {
                    'embedding': {
                        'type': 'knn_vector',
                        'dimension': 1024,  # Cohere embedding dimension
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

            # Create index
            self.opensearch.indices.create(
                index=self.index_name,
                body={
                    'settings': settings,
                    'mappings': mapping
                }
            )
    
    def _invoke_with_retry(self, operation, *args, **kwargs):
        """Execute operation with exponential backoff retry.
        
        Args:
            operation: Function to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Operation result
            
        Raises:
            Exception: If max retries exceeded
        """
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self.max_retries - 1:
                    raise
                # Exponential backoff with jitter
                delay = min(
                    self.max_delay,
                    self.min_delay * (2 ** attempt) + random.uniform(0, 1)
                )
                time.sleep(delay)
        raise last_exception
    
    def store_documents(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> None:
        """Store multiple documents with vectors.
        
        Args:
            documents: List of documents with content, vector, and optional metadata
            batch_size: Number of documents to process in each batch
        """
        actions = []
        for doc in documents:
            if 'content' not in doc or 'vector' not in doc:
                raise ValueError("Each document must have 'content' and 'vector' fields")
            
            # Prepare document for indexing
            action = {
                '_index': self.index_name,
                '_source': {
                    'content': doc['content'],
                    'embedding': doc['vector'],  # Map 'vector' to 'embedding'
                    'metadata': doc.get('metadata', {})
                }
            }
            actions.append(action)
            
            # Bulk index when batch is full
            if len(actions) >= batch_size:
                self._invoke_with_retry(helpers.bulk, self.opensearch, actions)
                actions = []
        
        # Index any remaining documents
        if actions:
            self._invoke_with_retry(helpers.bulk, self.opensearch, actions)
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text using Bedrock.
        
        Args:
            text: Text to embed
            
        Returns:
            Vector embedding
        """
        try:
            response = self._invoke_with_retry(
                self.bedrock.invoke_model,
                modelId=self.embedding_model_id,
                body=json.dumps({
                    "texts": [text],
                    "input_type": "search_query"
                })
            )
            embeddings = json.loads(response['body'].read())['embeddings']
            return embeddings[0]
        except Exception as e:
            raise Exception(f"Failed to get embedding: {str(e)}") from e
    
    def store_document(
        self,
        doc_id: str,
        content: str,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store single document with vector embedding.
        
        Args:
            doc_id: Document identifier
            content: Document content
            vector: Vector embedding
            metadata: Optional document metadata
        """
        # Get embedding if not provided
        if vector is None:
            vector = self.get_embedding(content)
            
        # Store as single document using bulk operation for consistency
        self.store_documents([{
            'content': content,
            'vector': vector,
            'metadata': metadata or {}
        }])
    
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
        try:
            if self.search_type == 'knn':
                # Use k-NN search
                body = {
                    'size': k,
                    'query': {
                        'knn': {
                            'embedding': {
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
                                'source': "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                                'params': {'query_vector': query_vector}
                            }
                        }
                    }
                }
                
                # Add score threshold if specified
                if self.similarity_threshold:
                    body['min_score'] = self.similarity_threshold
            
            # Execute search with retry
            response = self._invoke_with_retry(
                self.opensearch.search,
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
        """Clean up resources.
        
        Args:
            delete_resources: Whether to delete OpenSearch domain (ignored, use OpenSearchManager instead)
        """
        try:
            # Delete index if it exists
            if self.opensearch.indices.exists(index=self.index_name):
                self.opensearch.indices.delete(index=self.index_name)
        except:
            pass  # Best effort cleanup
