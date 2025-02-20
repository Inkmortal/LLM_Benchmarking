"""OpenSearch client utilities."""

import os
import boto3
from typing import Dict, Any, Optional
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
        self.opensearch_host = os.getenv('OPENSEARCH_HOST')  # Get from environment
        self.client = self._init_client() if self.opensearch_host else None  # Initialize if host exists

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
    
    def _ensure_client(self):
        """Ensure client is initialized."""
        # Update host from environment if needed
        env_host = os.getenv('OPENSEARCH_HOST')
        if env_host and env_host != self.opensearch_host:
            self.opensearch_host = env_host
            self.client = None  # Force client reinitialization

        if not self.client and self.opensearch_host:
            self.client = self._init_client()
        if not self.client:
            raise RuntimeError("OpenSearch client not initialized - host not set")

    def index_exists(self, index_name: str) -> bool:
        """
        Checks if an index with the given name exists.
        """
        try:
            self._ensure_client()
            return self.client.indices.exists(index=index_name)
        except Exception as e:
            print(f"Error checking if index exists: {e}")
            return False # Assume it doesn't exist on error.
    
    def create_index(self, index_name: str, settings: dict, mapping: dict):
        """Creates an index with given settings and mapping."""
        self._ensure_client()
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
        self._ensure_client()
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
        self._ensure_client()
        try:
            settings = self.client.indices.get_settings(index=index_name)
            mappings = self.client.indices.get_mapping(index=index_name)
            return settings, mappings
        except Exception as e:
            if "index_not_found_exception" in str(e):
                return None  # Index doesn't exist
            else:
                raise  # Re-raise other exceptions

    def bulk_index(self, actions: list, **kwargs):
        """Perform bulk indexing operation."""
        self._ensure_client()
        return helpers.bulk(self.client, actions, **kwargs)

    def search(self, index: str, body: Dict[str, Any], **kwargs):
        """Perform search operation."""
        self._ensure_client()
        return self.client.search(index=index, body=body, **kwargs)
