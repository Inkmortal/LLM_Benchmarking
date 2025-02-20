"""Utilities for interacting with Amazon OpenSearch Service."""

import os
import boto3
import time
import socket
from typing import Dict, Optional
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
        self.domain_name = domain_name
        self.cleanup_enabled = cleanup_enabled
        self.verbose = verbose
        self.opensearch = boto3.client('opensearch', region_name='us-west-2')  # Assuming us-west-2
        self.domain_endpoint = None

    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def _find_existing_domain(self) -> Optional[str]:
        """Find and validate existing domain."""
        try:
            response = self.opensearch.describe_domain(DomainName=self.domain_name)
            domain_status = response['DomainStatus']

            if domain_status['Processing'] or domain_status.get('Deleted'):
                self._log(f"Domain '{self.domain_name}' is not available.")
                return None

            if not self._fix_domain_config(domain_status):
                self._log("Could not fix domain configuration.")
                return None

            self.domain_endpoint = domain_status['Endpoint']
            return self.domain_endpoint

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return None
            raise

    def _fix_domain_config(self, domain_status: Dict) -> bool:
        """Try to fix domain configuration issues."""
        # Placeholder for configuration fixes.
        # In a real implementation, you would check and update settings here.
        # For this example, we assume the domain is correctly configured if it exists.
        if not domain_status.get('EngineVersion') or not domain_status.get('Endpoint'):
            return False
        return True

    def setup_domain(self) -> str:
        """Create or find OpenSearch domain and return endpoint."""
        existing_endpoint = self._find_existing_domain()
        if existing_endpoint:
            self._log(f"Using existing domain: {self.domain_name}")
            return existing_endpoint

        self._log(f"Creating OpenSearch domain: {self.domain_name}")
        try:
            response = self.opensearch.create_domain(
                DomainName=self.domain_name,
                EngineVersion='OpenSearch_2.3',  # Specify version
                ClusterConfig={
                    'InstanceType': 't3.small.search',  # Choose appropriate instance type
                    'InstanceCount': 1,
                    'DedicatedMasterEnabled': False,
                    'ZoneAwarenessEnabled': False
                },
                EBSOptions={
                    'EBSEnabled': True,
                    'VolumeType': 'gp2',
                    'VolumeSize': 10  # Minimum volume size
                },
                # AccessPolicies='string',  # Consider setting access policies
                NodeToNodeEncryptionOptions={
                    'Enabled': True
                },
                EncryptionAtRestOptions={
                    'Enabled': True,
                    'KmsKeyId': 'alias/aws/es'  # Use default AWS managed key
                },
                DomainEndpointOptions={
                    'EnforceHTTPS': True,
                    'TLSSecurityPolicy': 'Policy-Min-TLS-1-2-2019-07'
                },
                OffPeakWindowOptions={
                    'Enabled': True,
                    'Window': {
                        'WindowStartTime': {
                            'Hours': 2,  # 2 AM
                            'Minutes': 0
                        },
                        'Duration': {
                            'Value': 8,  # 8 hours
                            'Unit': 'HOURS'
                        }
                    }
                }
            )

            self._wait_for_domain(response['DomainStatus']['DomainId'])
            self.domain_endpoint = response['DomainStatus']['Endpoint']
            self._log(f"Domain created: {self.domain_name}")
            self._check_dns_propagation(self.domain_endpoint)
            return self.domain_endpoint

        except ClientError as e:
            self._log(f"Error creating domain: {str(e)}")
            raise

    def _wait_for_domain(self, domain_id: str, timeout: int = 1800) -> None:
        """Wait for domain to be available using polling."""
        import time
        self._log("Waiting for domain to be available...")
        start_time = time.time()
        while True:
            try:
                response = self.opensearch.describe_domain(DomainName=self.domain_name)
                status = response['DomainStatus']['DomainStatus']
                if status == 'Active':
                    self._log("Domain is available")
                    return
                elif status == 'Processing':
                    self._log(f"Domain status: {status}")
                    time.sleep(30)
                elif status == 'Deleting':
                    raise Exception(f"Domain is being deleted: {domain_id}")
                elif time.time() - start_time > timeout:
                    raise Exception(f"Timeout waiting for domain: {domain_id}")
                else:
                    self._log(f"Domain status: {status}")
                    time.sleep(30)

            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    raise Exception(f"Domain not found: {domain_id}")
                raise

    def _check_dns_propagation(self, endpoint: str, timeout: int = 300) -> None:
        """Check if DNS has propagated for endpoint."""
        import socket
        self._log("Checking DNS propagation...")
        start_time = time.time()
        while True:
            try:
                # Try to resolve the hostname
                socket.gethostbyname(endpoint)
                self._log("DNS resolution successful")
                return
            except socket.gaierror:
                if time.time() - start_time > timeout:
                    raise Exception(f"DNS propagation timeout for endpoint: {endpoint}")
                self._log("Waiting for DNS propagation...")
                time.sleep(10)  # Check every 10 seconds

    def cleanup(self) -> None:
        """Clean up domain resources."""
        if not self.cleanup_enabled:
            self._log("Cleanup disabled. Skipping domain deletion.")
            return

        try:
            self._log(f"Deleting OpenSearch domain: {self.domain_name}")
            self.opensearch.delete_domain(DomainName=self.domain_name)
            self._log("Domain deletion initiated.")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                self._log("Domain does not exist, skipping deletion.")
            else:
                self._log(f"Error during cleanup: {str(e)}")
                raise

    def _wait_for_deletion(self, timeout: int = 1800) -> None:
        """Wait for domain deletion to complete."""
        import time
        self._log("Waiting for domain deletion...")
        start_time = time.time()
        while True:
            try:
                self.opensearch.describe_domain(DomainName=self.domain_name)
                if time.time() - start_time > timeout:
                    raise Exception(f"Timeout waiting for domain deletion: {self.domain_name}")
                self._log("Domain still deleting...")
                time.sleep(30)

            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    self._log("Domain deleted successfully.")
                    return
                raise
