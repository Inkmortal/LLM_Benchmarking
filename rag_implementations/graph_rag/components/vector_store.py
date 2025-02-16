"""Vector storage using OpenSearch for graph RAG."""

import json
import hashlib
import boto3
import requests
from typing import Dict, Any, List, Optional, Literal
from requests_aws4auth import AWS4Auth
from opensearchpy import OpenSearch, RequestsHttpConnection
from utils.aws.opensearch_utils import OpenSearchManager

class VectorStore:
    """Handles vector storage and search using OpenSearch."""
    
    def __init__(
        self,
        index_name: str,
        search_type: Literal['script', 'knn'] = 'script',
        similarity_threshold: Optional[float] = None,
        index_settings: Optional[Dict] = None,
        knn_params: Optional[Dict] = None
    ):
        """Initialize vector store.
        
        Args:
            index_name: Name for the OpenSearch index
            search_type: Type of vector search ('script' or 'knn')
            similarity_threshold: Minimum similarity score
            index_settings: Custom index settings
            knn_params: Parameters for k-NN algorithm
        """
        self.index_name = index_name
        self.search_type = search_type
        self.similarity_threshold = similarity_threshold
        self.index_settings = index_settings or {}
        self.knn_params = knn_params or {}
        
        # Initialize OpenSearch
        self._init_vector_store()
    
    def _get_domain_name(self) -> str:
        """Generate a unique, shortened domain name."""
        # Hash the index name
        hash_obj = hashlib.md5(self.index_name.encode())
        hash_str = hash_obj.hexdigest()[:8]  # Use first 8 chars of hash
        return f"graph-rag-{hash_str}"
    
    def _get_opensearch_client(self, endpoint: str) -> OpenSearch:
        """Create OpenSearch client with AWS authentication."""
        region = boto3.Session().region_name
        credentials = boto3.Session().get_credentials()
        aws_auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            'es',
            session_token=credentials.token
        )
        
        return OpenSearch(
            hosts=[{'host': endpoint, 'port': 443}],
            http_auth=aws_auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
    
    def _init_vector_store(self):
        """Initialize OpenSearch vector store connection."""
        # Set up domain
        self.opensearch_manager = OpenSearchManager(
            domain_name=self._get_domain_name(),
            cleanup_enabled=True
        )
        endpoint = self.opensearch_manager.setup_domain()
        
        # Get domain endpoint without https:// and port
        if endpoint.startswith('https://'):
            endpoint = endpoint[8:]
        if ':' in endpoint:
            endpoint = endpoint.split(':')[0]
        
        # Create OpenSearch client
        self.opensearch = self._get_opensearch_client(endpoint)
        
        # Create index with vector search settings
        settings = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "knn": {
                    "algo_param": {
                        "ef_search": 512  # Higher = more accurate but slower
                    }
                }
            },
            "mappings": {
                "properties": {
                    "content": {"type": "text"},
                    "metadata": {"type": "object"},
                    "vector": {
                        "type": "knn_vector",
                        "dimension": 1024,  # Cohere embedding dimension
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 512,
                                "m": 16
                            }
                        }
                    }
                }
            }
        }
        
        # Update settings
        if self.index_settings:
            settings["settings"].update(self.index_settings)
        
        # Update KNN parameters
        if self.knn_params:
            settings["mappings"]["properties"]["vector"]["method"]["parameters"].update(
                self.knn_params
            )
        
        # Create index if it doesn't exist
        if not self.opensearch.indices.exists(index=self.index_name):
            self.opensearch.indices.create(
                index=self.index_name,
                body=settings
            )
    
    def store_document(
        self,
        doc_id: str,
        content: str,
        vector: List[float],
        metadata: Dict[str, Any]
    ) -> None:
        """Store document with vector embedding.
        
        Args:
            doc_id: Document identifier
            content: Document content
            vector: Document embedding vector
            metadata: Document metadata
        """
        self.opensearch.index(
            index=self.index_name,
            id=doc_id,
            body={
                "content": content,
                "vector": vector,
                "metadata": metadata
            }
        )
    
    def search(
        self,
        query_vector: List[float],
        k: int = 3
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity.
        
        Args:
            query_vector: Query embedding vector
            k: Number of results to return
            
        Returns:
            List of similar documents with scores
        """
        if self.search_type == 'script':
            # Script-based cosine similarity search
            script_query = {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "lang": "painless",
                        "source": "double score = cosineSimilarity(params.query_vector, doc['vector']); return score + 1.0;",
                        "params": {"query_vector": query_vector}
                    }
                }
            }
            
            # Add minimum score if threshold is set
            if self.similarity_threshold is not None:
                script_query["script_score"]["min_score"] = self.similarity_threshold
            
            response = self.opensearch.search(
                index=self.index_name,
                body={
                    "size": k,
                    "query": script_query,
                    "_source": ["content", "metadata"]
                }
            )
            
        else:  # search_type == 'knn'
            # Pure k-NN search
            knn_query = {
                "knn": {
                    "vector": {
                        "vector": query_vector,
                        "k": k
                    }
                }
            }
            
            response = self.opensearch.search(
                index=self.index_name,
                body={
                    "query": knn_query,
                    "_source": ["content", "metadata"]
                }
            )
        
        # Format results
        results = []
        for hit in response["hits"]["hits"]:
            results.append({
                "id": hit["_id"],
                "score": hit["_score"],
                "content": hit["_source"]["content"],
                "metadata": hit["_source"]["metadata"]
            })
        
        return results
    
    def cleanup(self):
        """Clean up OpenSearch resources."""
        if self.opensearch_manager:
            self.opensearch_manager.cleanup()
