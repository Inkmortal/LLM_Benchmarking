"""OpenSearch index management utilities."""

from typing import Dict, Tuple, Optional
from .client import OpenSearchClient

class OpenSearchIndexManager:
    """
    Manages an OpenSearch index, including checking its configuration and deleting it.
    """

    def __init__(self, client: OpenSearchClient, index_name: str):
        """
        Initializes the OpenSearchIndexManager.

        Args:
            client: An instance of OpenSearchClient.
            index_name: The name of the index to manage.
        """
        self.client = client
        self.index_name = index_name
    
    def get_index_info(self) -> Optional[Tuple[Dict, Dict]]:
        """
        Retrieves the index information (settings and mappings) from OpenSearch.
        Returns None if the index does not exist.
        """
        try:
            settings = self.client.client.indices.get_settings(index=self.index_name)
            mappings = self.client.client.indices.get_mapping(index=self.index_name)
            return settings, mappings
        except Exception as e:
            if "index_not_found_exception" in str(e):
                return None  # Index doesn't exist
            else:
                raise  # Re-raise other exceptions

    def check_configuration(self, expected_settings: dict, expected_mapping: dict) -> bool:
        """
        Checks if the existing OpenSearch index matches the expected configuration.
        Returns True if the config matches, False otherwise.
        """
        index_info = self.get_index_info()
        
        if index_info:
            settings, mappings = index_info
            settings = settings[self.index_name]['settings']
            mappings = mappings[self.index_name]['mappings']
            
            # Check index settings
            index_settings = settings.get('index', {})
            
            # Check for knn enabled
            knn_enabled = index_settings.get('knn') == 'true'
            if not knn_enabled:
                print("k-NN not enabled in existing index.")
                return False

            # Check for ef_search (optional, might not be present)
            ef_search = index_settings.get('knn.algo_param.ef_search')
            if ef_search is not None and int(ef_search) != 512:
                print(f"ef_search mismatch: expected 512, got {ef_search}")
                return False
                
            # Check essential mapping properties
            properties = mappings.get('properties', {})
            if 'embedding' not in properties or properties['embedding'].get('type') != 'knn_vector':
                print("embedding field not configured correctly.")
                return False
            if properties['embedding'].get('dimension') != 1024:
                print("embedding dimension mismatch.")
                return False

            # Check for method and parameters, handling potential missing keys gracefully
            method = properties['embedding'].get('method', {})
            if method.get('name') != 'hnsw' or method.get('space_type') != 'cosinesimil' or method.get('engine') != 'nmslib':
                print("embedding method configuration mismatch.")
                return False

            parameters = method.get('parameters', {})
            if parameters.get('ef_construction') != 512 or parameters.get('m') != 16:
                print("embedding method parameters mismatch.")
                return False

            # Check other fields
            if 'content' not in properties or properties['content'].get('type') != 'text':
                print("content field not configured correctly.")
                return False
            if 'metadata' not in properties or properties['metadata'].get('type') != 'object':
                print("metadata field not configured correctly.")
                return False

            # If all checks pass, configuration matches
            print("Configuration check passed.")
            return True
        else:
            # Index doesn't exist
            print("Index does not exist.")
            return False
    
    def create_index(self, settings: Dict, mapping: Dict) -> None:
        """Creates an index with given settings and mapping."""
        try:
            self.client.client.indices.create(
                index=self.index_name,
                body={
                    'settings': settings,
                    'mappings': mapping
                }
            )
            print(f"Index '{self.index_name}' created successfully.")
        except Exception as e:
            print(f"Error creating index: {e}")
            raise

    def delete_index(self) -> None:
        """Deletes the managed OpenSearch index."""
        try:
            self.client.client.indices.delete(index=self.index_name, ignore=[400, 404])
            print(f"Index '{self.index_name}' deleted successfully.")
        except Exception as e:
            print(f"Error deleting index: {e}")
            raise

    def index_exists(self) -> bool:
        """Checks if the index exists."""
        try:
            return self.client.client.indices.exists(index=self.index_name)
        except Exception as e:
            print(f"Error checking if index exists: {e}")
            return False  # Assume it doesn't exist on error
