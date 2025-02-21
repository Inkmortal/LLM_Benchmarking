"""OpenSearch client utilities."""

import os
import boto3
from typing import List, Dict, Any
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth

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

    def search(self, index: str, body: Dict) -> Dict:
        """Execute a search query."""
        self._ensure_client()
        return self.client.search(index=index, body=body)

    def bulk_index(self, actions: List[Dict[str, Any]]) -> None:
        """Bulk index documents."""
        self._ensure_client()
        try:
            helpers.bulk(self.client, actions)
        except Exception as e:
            print(f"Error during bulk indexing: {e}")
            raise

    def index_exists(self, index_name: str) -> bool:
        """Check if an index exists."""
        self._ensure_client()
        return self.client.indices.exists(index=index_name)

    def create_index(self, index_name: str, settings: Dict, mapping: Dict) -> None:
        """Create an index with settings and mapping."""
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

    def delete_index(self, index_name: str) -> None:
        """Delete an index."""
        self._ensure_client()
        try:
            self.client.indices.delete(index=index_name, ignore=[400, 404])
            print(f"Index '{index_name}' deleted successfully.")
        except Exception as e:
            print(f"Error deleting index: {e}")
            raise
