"""OpenSearch utilities for managing domains and operations."""

import json
import time
import datetime
import boto3
from typing import Dict, Optional, Any
from botocore.exceptions import ClientError

class OpenSearchManager:
    """Manages OpenSearch domain operations including setup, status checking, and cleanup."""
    
    def __init__(self, domain_name: str, cleanup_enabled: bool = True, verbose: bool = False):
        """Initialize OpenSearch manager.
        
        Args:
            domain_name: Name of the OpenSearch domain
            cleanup_enabled: Whether to enable cleanup on deletion
            verbose: Whether to print detailed status information
        """
        self.domain_name = domain_name
        self.cleanup_enabled = cleanup_enabled
        self.verbose = verbose
        self.client = boto3.client('opensearch')
        self.region = boto3.Session().region_name
        self._setup_identity()
        self.start_time = datetime.datetime.now()
        
    def _setup_identity(self):
        """Get current AWS identity."""
        sts = boto3.client('sts')
        self.identity = sts.get_caller_identity()
        self.current_arn = self.identity['Arn']
        
    def _serialize_datetime(self, obj: Any) -> Any:
        """Helper to serialize datetime objects in JSON dumps."""
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return obj
        
    def get_domain_status(self) -> Dict:
        """Get detailed OpenSearch domain status with progress information."""
        try:
            response = self.client.describe_domain(DomainName=self.domain_name)
            status = response['DomainStatus']
            
            # Check if domain is being deleted
            if status.get('Deleted') or status.get('DeletionDate'):
                return {
                    'exists': True,
                    'processing': True,
                    'stage': 'Deleting',
                    'created': False,
                    'endpoint': None,
                    'elapsed_minutes': 0,
                    'full_status': status
                }
            
            # Calculate elapsed time
            elapsed = 0
            now = datetime.datetime.now()
            
            # Try to get elapsed time from change progress
            if 'ChangeProgressDetails' in status:
                progress = status['ChangeProgressDetails']
                # Handle both datetime and timestamp formats
                if isinstance(progress['StartTime'], datetime.datetime):
                    start_time = progress['StartTime']
                    last_update = progress['LastUpdatedTime']
                else:
                    start_time = datetime.datetime.fromtimestamp(progress['StartTime'])
                    last_update = datetime.datetime.fromtimestamp(progress['LastUpdatedTime'])
                elapsed = (last_update - start_time).total_seconds() / 60.0  # minutes
            
            # If no change progress or elapsed is 0, calculate from creation time
            if elapsed == 0:
                if 'Created' in status and status['Created']:
                    if 'CreatedDate' in status:
                        created_date = status['CreatedDate']
                        if not isinstance(created_date, datetime.datetime):
                            created_date = datetime.datetime.fromtimestamp(created_date)
                        elapsed = (now - created_date).total_seconds() / 60.0
                    else:
                        # Fallback to our instance start time
                        elapsed = (now - self.start_time).total_seconds() / 60.0
                else:
                    # Domain is still being created, use our instance start time
                    elapsed = (now - self.start_time).total_seconds() / 60.0
                
            return {
                'exists': True,
                'processing': status.get('Processing', False),
                'stage': status.get('DomainProcessingStatus', 'Unknown'),
                'created': status.get('Created', False),
                'endpoint': status.get('Endpoints', {}).get('vpc') or status.get('Endpoint'),
                'elapsed_minutes': elapsed,
                'full_status': status  # Include full status for debugging
            }
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Calculate elapsed time from instance creation
                elapsed = (datetime.datetime.now() - self.start_time).total_seconds() / 60.0
                return {
                    'exists': False,
                    'processing': False,
                    'stage': 'NotFound',
                    'created': False,
                    'endpoint': None,
                    'elapsed_minutes': elapsed,
                    'full_status': None
                }
            raise
            
    def _wait_for_deletion(self, timeout: int = 1800) -> None:
        """Wait for domain deletion to complete.
        
        Args:
            timeout: Maximum wait time in seconds (default 30 minutes)
            
        Raises:
            TimeoutError: If domain is not deleted within timeout
        """
        print("\nWaiting for domain deletion to complete...")
        start = time.time()
        while time.time() - start < timeout:
            try:
                status = self.get_domain_status()
                if not status['exists']:
                    print("Domain deletion complete")
                    return
                print(f"Domain status: {status['stage']} (elapsed: {(time.time() - start) / 60:.1f} minutes)")
                time.sleep(30)  # Check every 30 seconds
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    print("Domain deletion complete")
                    return
                raise
                
        raise TimeoutError(f"Domain deletion did not complete within {timeout/60:.1f} minutes")
            
    def create_domain(self) -> Dict:
        """Create a new OpenSearch domain with standard configuration."""
        response = self.client.create_domain(
            DomainName=self.domain_name,
            EngineVersion='OpenSearch_2.11',
            ClusterConfig={
                'InstanceType': 't3.small.search',
                'InstanceCount': 1,
                'DedicatedMasterEnabled': False,
                'ZoneAwarenessEnabled': False
            },
            EBSOptions={
                'EBSEnabled': True,
                'VolumeType': 'gp3',
                'VolumeSize': 10
            },
            AccessPolicies=json.dumps({
                'Version': '2012-10-17',
                'Statement': [{
                    'Effect': 'Allow',
                    'Principal': {
                        'AWS': self.current_arn
                    },
                    'Action': 'es:*',
                    'Resource': f'arn:aws:es:*:*:domain/{self.domain_name}/*'
                }]
            })
        )
        
        if self.verbose:
            print("\nDomain creation response:")
            print(json.dumps(response, indent=2, default=self._serialize_datetime))
            
        return response
        
    def wait_for_domain(self, max_attempts: int = 40, delay: int = 30) -> str:
        """Wait for domain to become active.
        
        Args:
            max_attempts: Maximum number of attempts to check status
            delay: Delay in seconds between attempts
            
        Returns:
            str: Domain endpoint
            
        Raises:
            TimeoutError: If domain does not become active within timeout
        """
        attempt = 0
        while attempt < max_attempts:
            status = self.get_domain_status()
            
            if not status['exists']:
                print("Waiting for domain to be created...")
            elif status['stage'] == 'Deleting':
                print(f"Domain is being deleted (elapsed: {status['elapsed_minutes']:.1f} minutes)")
            elif not status['processing'] and status['endpoint']:
                print(f"\nOpenSearch domain is now active after {status['elapsed_minutes']:.1f} minutes")
                print(f"Stage: {status['stage']}")
                print(f"Endpoint: {status['endpoint']}")
                # Add extra wait for DNS propagation
                print("Waiting for DNS propagation...")
                time.sleep(60)
                return status['endpoint']
            else:
                print(f"Domain status: {status['stage']} (elapsed: {status['elapsed_minutes']:.1f} minutes)")
            
            time.sleep(delay)
            attempt += 1
            
        if self.verbose:
            print("\nFinal domain status:")
            print(json.dumps(status['full_status'], indent=2, default=self._serialize_datetime))
            
        raise TimeoutError(f"OpenSearch domain did not become active after {max_attempts * delay / 60:.1f} minutes")
        
    def _create_and_wait(self) -> str:
        """Create new domain and wait for it to be active.
        
        Returns:
            str: Domain endpoint
        """
        print(f"\nCreating new domain: {self.domain_name}")
        try:
            self.create_domain()
            print("\nWaiting for OpenSearch domain to be active (this may take 10-15 minutes)...")
            return self.wait_for_domain()
        except Exception as e:
            print(f"\nError creating domain: {str(e)}")
            if self.verbose:
                print(f"Error type: {type(e)}")
            raise
        
    def setup_domain(self) -> str:
        """Set up OpenSearch domain - either use existing or create new.
        
        Returns:
            str: Domain endpoint
        """
        print(f"Using identity: {self.current_arn}")
        print(f"AWS Region: {self.region}")
        
        # Check existing domains
        domains = self.client.list_domain_names()
        print(f"\nExisting domains: {[d['DomainName'] for d in domains.get('DomainNames', [])]}")
        
        # Get or create domain
        status = self.get_domain_status()
        if status['exists']:
            print(f"\nFound existing domain: {self.domain_name}")
            if self.verbose:
                print("Full domain status:")
                print(json.dumps(status['full_status'], indent=2, default=self._serialize_datetime))
            
            # Check if domain is being deleted
            if status['stage'] == 'Deleting':
                print("\nDomain is being deleted, waiting for deletion to complete...")
                self._wait_for_deletion()
                return self._create_and_wait()
            
            if status['endpoint']:
                print(f"\nDomain is active with endpoint: {status['endpoint']}")
                return status['endpoint']
                
            print("\nWaiting for domain to become active...")
            return self.wait_for_domain()
        else:
            return self._create_and_wait()
                
    def cleanup(self):
        """Clean up OpenSearch domain if cleanup is enabled."""
        if not self.cleanup_enabled:
            print("\n=== Resource Cleanup ===")
            print("To avoid ongoing costs, you can:")
            print(f"1. Set cleanup_enabled=True when creating OpenSearchManager")
            print(f"2. Manually delete the OpenSearch domain '{self.domain_name}' in AWS Console")
            print("   AWS Console > OpenSearch > Domains > Select domain > Delete")
            return
            
        print("\n=== Cleaning Up Resources ===")
        print("Warning: This will delete the OpenSearch domain and all indexed data")
        
        try:
            # Check if domain exists and is not already being deleted
            status = self.get_domain_status()
            if status['exists'] and status['stage'] != 'Deleting':
                print(f"Deleting OpenSearch domain: {self.domain_name}")
                self.client.delete_domain(DomainName=self.domain_name)
                print("✅ Cleanup successful")
                print("Note: Domain deletion may take 15-20 minutes to complete")
            elif status['stage'] == 'Deleting':
                print(f"Domain {self.domain_name} is already being deleted")
            else:
                print(f"Domain {self.domain_name} does not exist")
        except Exception as e:
            print(f"❌ Error during cleanup: {str(e)}")
            if self.verbose:
                print(f"Error type: {type(e)}")
