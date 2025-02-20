"""Utilities for interacting with Amazon OpenSearch Service."""

import os
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth
from botocore.exceptions import ClientError

class OpenSearchClient:
    """
    A client for interacting with an Amazon OpenSearch Service domain.
    Handles authentication and provides a reusable OpenSearch client instance.
    """

    def __init__(self, domain_name: str, region: str = 'us-west-2'):
        """
        Initializes the OpenSearchClient.

        Args:
            domain_name: The name of the OpenSearch domain.
            region: The AWS region where the domain is located.
        """
        self.domain_name = domain_name
        self.region = region
        self.opensearch_host = os.getenv('OPENSEARCH_HOST')
        if not self.opensearch_host:
            raise ValueError("OPENSEARCH_HOST environment variable is required")
        self.client = self._init_client()


    def _get_aws_credentials(self):
        """Retrieves AWS credentials from the environment."""
        session = boto3.Session(region_name=self.region)
        return session.get_credentials().get_frozen_credentials()

    def _init_client(self) -> OpenSearch:
        """
        Initializes and returns an OpenSearch client instance configured for AWS authentication.
        """
        credentials = self._get_aws_credentials()
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            self.region,
            'es',
            session_token=credentials.token
        )

        return OpenSearch(
            hosts=[{'host': self.opensearch_host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30  # Add a timeout
        )
    
    def index_exists(self, index_name: str) -> bool:
        """
        Checks if an index with the given name exists.
        """
        try:
            return self.client.indices.exists(index=index_name)
        except Exception as e:
            print(f"Error checking if index exists: {e}")
            return False # Assume it doesn't exist on error.
    
    def create_index(self, index_name: str, settings: dict, mapping: dict):
        """Creates an index with given settings and mapping."""
        try:
            self.client.indices.create(
                index=index_name,
                body={
                    'settings': settings,
                    'mappings': mapping
                }
            )
            print(f"Index '{index_name}' created successfully.")
        except Exception as e:
            print(f"Error creating index: {e}")
            raise

    def delete_index(self, index_name: str):
        """Deletes an index"""
        try:
            self.client.indices.delete(index=index_name, ignore=[400, 404])
            print(f"Index '{index_name}' deleted successfully.")
        except Exception as e:
            print(f"Error deleting index: {e}")
            raise

    def get_index_info(self, index_name: str):
        """
        Retrieves the index information (settings and mappings) from OpenSearch.
        Returns None if the index does not exist.
        """
        try:
            settings = self.client.indices.get_settings(index=index_name)
            mappings = self.client.indices.get_mapping(index=index_name)
            return settings, mappings
        except Exception as e:
            if "index_not_found_exception" in str(e):
                return None  # Index doesn't exist
            else:
                raise  # Re-raise other exceptions

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
    
    def check_configuration(self, expected_settings: dict, expected_mapping: dict) -> bool:
        """
        Checks if the existing OpenSearch index matches the expected configuration.
        Returns True if the config matches, False otherwise.
        """
        index_info = self.client.get_index_info(self.index_name)
        
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
    
    def delete_index(self):
        """Deletes the managed OpenSearch index."""
        self.client.delete_index(self.index_name)

class OpenSearchManager:
    """Manages OpenSearch domains, including creation, deletion, and configuration checks."""

    def __init__(self, domain_name: str, cleanup_enabled: bool = False, verbose: bool = False):
        """
        Initializes the OpenSearchManager.

        Args:
            domain_name: The name of the OpenSearch domain.
            cleanup_enabled: Whether to automatically clean up (delete) the domain.
            verbose: Whether to print detailed status messages.
        """
        # ... (rest of the existing OpenSearchManager code) ...
        pass # Remove once implemented
