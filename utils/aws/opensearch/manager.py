"""OpenSearch domain management utilities."""

import os
import time
import socket
import boto3
from typing import Dict, Optional
from botocore.exceptions import ClientError
from tqdm.notebook import tqdm as tqdm_notebook
from .types import OpenSearchConfig
from .client import OpenSearchClient

class OpenSearchManager:
    """Manages OpenSearch domains, including creation, deletion, and configuration checks."""

    def __init__(self, config: OpenSearchConfig):
        """
        Initializes the OpenSearchManager.

        Args:
            config: OpenSearch configuration
        """
        self.config = config
        self.opensearch = boto3.client('opensearch', region_name=config.region)
        self.domain_endpoint = None
        self.client = None

    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.config.verbose:
            print(message)

    def _find_existing_domain(self) -> Optional[str]:
        """Find and validate existing domain."""
        try:
            response = self.opensearch.describe_domain(DomainName=self.config.domain_name)
            domain_status = response['DomainStatus']

            # If domain exists but is processing, wait for it
            if domain_status.get('Processing'):
                self._log(f"Domain '{self.config.domain_name}' exists but is processing")
                self._wait_for_domain(domain_status['DomainId'])
                # Get updated status after waiting
                response = self.opensearch.describe_domain(DomainName=self.config.domain_name)
                domain_status = response['DomainStatus']

            # Check if domain is deleted
            if domain_status.get('Deleted'):
                self._log(f"Domain '{self.config.domain_name}' is marked for deletion.")
                return None

            # Check if domain is properly configured
            if not self._fix_domain_config(domain_status):
                self._log("Could not fix domain configuration.")
                return None

            # Domain exists and is ready
            self.domain_endpoint = domain_status['Endpoint']
            os.environ['OPENSEARCH_HOST'] = self.domain_endpoint  # Set for client use
            self.client = OpenSearchClient(domain_name=self.config.domain_name)  # Initialize client now that we have the host
            return self.domain_endpoint

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                self._log(f"Domain '{self.config.domain_name}' does not exist.")
                return None
            raise

    def _fix_domain_config(self, domain_status: Dict) -> bool:
        """Try to fix domain configuration issues."""
        if not domain_status.get('EngineVersion') or not domain_status.get('Endpoint'):
            return False
        return True

    def setup_domain(self) -> str:
        """Create or find OpenSearch domain and return endpoint."""
        existing_endpoint = self._find_existing_domain()
        if existing_endpoint:
            self._log(f"Using existing domain: {self.config.domain_name}")
            return existing_endpoint

        self._log(f"Creating OpenSearch domain: {self.config.domain_name}")
        try:
            response = self.opensearch.create_domain(
                DomainName=self.config.domain_name,
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
                    'OffPeakWindow': {
                        'WindowStartTime': {
                            'Hours': 2,  # 2 AM
                            'Minutes': 0
                        }
                    }
                }
            )

            # Get domain status from response
            domain_status = response.get('DomainStatus', {})
            if not domain_status:
                domain_status = response.get('CreateDomainResponse', {}).get('DomainStatus', {})
            
            if not domain_status:
                raise ValueError("Failed to get domain status from response")

            # Wait for domain to be ready
            self._wait_for_domain(domain_status['DomainId'])
            
            # Get updated status after waiting
            response = self.opensearch.describe_domain(DomainName=self.config.domain_name)
            domain_status = response['DomainStatus']
            self.domain_endpoint = domain_status['Endpoint']
            os.environ['OPENSEARCH_HOST'] = self.domain_endpoint  # Set for client use
            self.client = OpenSearchClient(domain_name=self.config.domain_name)  # Initialize client now that we have the host
            self._log(f"Domain created: {self.config.domain_name}")
            self._check_dns_propagation(self.domain_endpoint)
            return self.domain_endpoint

        except ClientError as e:
            self._log(f"Error creating domain: {str(e)}")
            raise

    def _wait_for_domain(self, domain_id: str, timeout: int = 1800) -> None:
        """Wait for domain to be available using polling."""
        self._log("Waiting for domain to be available...")
        start_time = time.time()
        steps = timeout // 30  # Update every 30 seconds
        
        with tqdm_notebook(total=steps, desc="Waiting for domain") as pbar:
            while True:
                try:
                    response = self.opensearch.describe_domain(DomainName=self.config.domain_name)
                    domain_status = response['DomainStatus']
                    
                    if domain_status.get('Deleted'):
                        raise Exception(f"Domain is being deleted: {domain_id}")
                    elif domain_status.get('Processing'):
                        pbar.set_postfix({'Status': 'Processing'})
                        time.sleep(30)
                        pbar.update(1)
                    elif domain_status.get('Endpoint'):
                        pbar.set_postfix({'Status': 'Available'})
                        self._log("Domain is available")
                        return
                    elif time.time() - start_time > timeout:
                        raise Exception(f"Timeout waiting for domain: {domain_id}")
                    else:
                        pbar.set_postfix({'Status': 'Initializing'})
                        time.sleep(30)
                        pbar.update(1)

                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        raise Exception(f"Domain not found: {domain_id}")
                    raise

    def _check_dns_propagation(self, endpoint: str, timeout: int = 300) -> None:
        """Check if DNS has propagated for endpoint."""
        self._log("Checking DNS propagation...")
        start_time = time.time()
        steps = timeout // 10  # Update every 10 seconds
        
        with tqdm_notebook(total=steps, desc="Checking DNS propagation") as pbar:
            while True:
                try:
                    socket.gethostbyname(endpoint)
                    pbar.set_postfix({'Status': 'Success'})
                    self._log("DNS resolution successful")
                    return
                except socket.gaierror:
                    if time.time() - start_time > timeout:
                        raise Exception(f"DNS propagation timeout for endpoint: {endpoint}")
                    pbar.set_postfix({'Status': 'Waiting'})
                    time.sleep(10)  # Check every 10 seconds
                    pbar.update(1)

    def cleanup(self) -> None:
        """Clean up domain resources."""
        if not self.config.cleanup_enabled:
            self._log("Cleanup disabled. Skipping domain deletion.")
            return

        try:
            self._log(f"Deleting OpenSearch domain: {self.config.domain_name}")
            self.opensearch.delete_domain(DomainName=self.config.domain_name)
            self._log("Domain deletion initiated.")
            self._wait_for_deletion()
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                self._log("Domain does not exist, skipping deletion.")
            else:
                self._log(f"Error during cleanup: {str(e)}")
                raise

    def _wait_for_deletion(self, timeout: int = 1800) -> None:
        """Wait for domain deletion to complete."""
        self._log("Waiting for domain deletion...")
        start_time = time.time()
        steps = timeout // 30  # Update every 30 seconds
        
        with tqdm_notebook(total=steps, desc="Waiting for domain deletion") as pbar:
            while True:
                try:
                    self.opensearch.describe_domain(DomainName=self.config.domain_name)
                    if time.time() - start_time > timeout:
                        raise Exception(f"Timeout waiting for domain deletion: {self.config.domain_name}")
                    pbar.set_postfix({'Status': 'Deleting'})
                    time.sleep(30)
                    pbar.update(1)

                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        pbar.set_postfix({'Status': 'Deleted'})
                        self._log("Domain deleted successfully.")
                        return
                    raise
