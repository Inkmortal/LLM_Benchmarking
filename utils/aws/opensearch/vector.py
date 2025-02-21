"""Vector storage and search functionality using OpenSearch."""

import time
import random
from typing import Dict, Any, List, Optional
from tqdm.notebook import tqdm as tqdm_notebook
from .types import VectorSearchConfig
from .client import OpenSearchClient
from .index import OpenSearchIndexManager

class VectorStore:
    """Handles vector storage and search using OpenSearch."""

    def __init__(
        self,
        index_name: str,
        config: VectorSearchConfig,
        client: OpenSearchClient
    ):
        """Initialize vector store.

        Args:
            index_name: Name of the OpenSearch index
            config: Vector search configuration
            client: OpenSearch client instance
        """
        self.index_name = index_name
        self.config = config
        self.client = client
        self.index_manager = OpenSearchIndexManager(client, index_name)
        self._create_index_if_not_exists()

    def _get_index_mapping(self):
        """
        Defines the OpenSearch index mapping for vector storage.
        """
        return {
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

    def _create_index_if_not_exists(self):
        """Create OpenSearch index with appropriate mapping and settings."""
        # Default settings
        settings = {
            'index': {
                'number_of_shards': 1,
                'number_of_replicas': 0,
            },
            'knn': {
                'algo_param': {
                    'ef_search': 512  # Higher values = more accurate but slower
                }
            }
        }

        # Update with custom settings
        if self.config.index_settings:
            settings.update(self.config.index_settings)

        # Get the mapping
        mapping = self._get_index_mapping()

        # Update KNN parameters
        if self.config.knn_params:
            mapping['properties']['embedding']['method']['parameters'].update(
                self.config.knn_params
            )

        # Check if index exists and has correct configuration
        if self.index_manager.index_exists():
            if not self.index_manager.check_configuration(settings, mapping):
                print("Index configuration mismatch. Recreating index.")
                self.index_manager.delete_index()
                self.index_manager.create_index(settings, mapping)
        else:
            # Create new index
            self.index_manager.create_index(settings, mapping)

    def _invoke_with_retry(self, operation, *args, **kwargs):
        """Execute operation with exponential backoff retry."""
        last_exception = None
        for attempt in range(self.config.max_retries):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self.config.max_retries - 1:
                    raise
                # Exponential backoff with jitter
                delay = min(
                    self.config.max_delay,
                    self.config.min_delay * (2 ** attempt) + random.uniform(0, 1)
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
        # Validate documents first
        valid_docs = []
        invalid_count = 0
        
        print("Validating documents...")
        for doc in documents:
            if 'content' not in doc or 'vector' not in doc:
                print(f"Invalid document: missing required fields")
                invalid_count += 1
                continue
                
            if not doc['content'] or not doc['vector']:
                print(f"Invalid document: empty content or vector")
                invalid_count += 1
                continue
                
            if len(doc['vector']) != 1024:  # Cohere embedding dimension
                print(f"Invalid document: incorrect vector dimension {len(doc['vector'])}")
                invalid_count += 1
                continue
                
            valid_docs.append(doc)
        
        if invalid_count > 0:
            print(f"Found {invalid_count} invalid documents that will be skipped")
            
        if not valid_docs:
            print("No valid documents to store")
            return
            
        print(f"Storing {len(valid_docs)} valid documents...")
        
        # Process in batches
        total_batches = (len(valid_docs) + batch_size - 1) // batch_size
        success_count = 0
        failure_count = 0
        
        with tqdm_notebook(total=total_batches, desc="Storing documents") as pbar:
            for i in range(0, len(valid_docs), batch_size):
                batch = valid_docs[i:i + batch_size]
                batch_num = (i//batch_size) + 1
                
                # Prepare batch actions
                actions = []
                for doc in batch:
                    action = {
                        '_index': self.index_name,
                        '_source': {
                            'content': doc['content'],
                            'embedding': doc['vector'],
                            'metadata': doc.get('metadata', {})
                        }
                    }
                    actions.append(action)

                # Bulk index with retry
                for attempt in range(self.config.max_retries):
                    try:
                        self._invoke_with_retry(self.client.bulk_index, actions)
                        success_count += len(batch)
                        pbar.set_postfix({
                            'Status': 'Success',
                            'Batch': f"{batch_num}/{total_batches}",
                            'Success': success_count,
                            'Failed': failure_count
                        })
                        break
                    except Exception as e:
                        if attempt == self.config.max_retries - 1:
                            failure_count += len(batch)
                            pbar.set_postfix({
                                'Status': f'Error: {type(e).__name__}',
                                'Batch': f"{batch_num}/{total_batches}",
                                'Success': success_count,
                                'Failed': failure_count
                            })
                            print(f"\nError storing batch {batch_num}: {str(e)}")
                        else:
                            pbar.set_postfix({
                                'Status': f'Retry {attempt+1}/{self.config.max_retries}',
                                'Batch': f"{batch_num}/{total_batches}",
                                'Success': success_count,
                                'Failed': failure_count
                            })
                            time.sleep(self.config.min_delay * (2 ** attempt))
                            continue
                
                pbar.update(1)
        
        print(f"\nStorage complete:")
        print(f"Successfully stored: {success_count} documents")
        print(f"Failed to store: {failure_count} documents")

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
            # Validate query vector
            if not query_vector or len(query_vector) != 1024:
                raise ValueError(f"Invalid query vector dimension: {len(query_vector) if query_vector else 0}")

            if self.config.search_type == 'knn':
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
                # Use script score with proper Painless syntax
                body = {
                    'size': k,
                    'query': {
                        'script_score': {
                            'query': {'match_all': {}},
                            'script': {
                                'lang': 'painless',
                                'source': """
                                    double score = cosineSimilarity(params.query_vector, doc['embedding']);
                                    return score + 1.0;
                                """,
                                'params': {'query_vector': query_vector}
                            }
                        }
                    }
                }

                # Add score threshold if specified
                if self.config.similarity_threshold:
                    body['min_score'] = self.config.similarity_threshold

            # Execute search with retry
            response = self._invoke_with_retry(
                self.client.search,
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
            print(f"Search failed: {str(e)}")
            return []

    def cleanup(self, delete_resources: bool = False):
        """Clean up resources."""
        try:
            if self.index_manager.index_exists():
                self.index_manager.delete_index()
        except:
            pass  # Best effort cleanup
