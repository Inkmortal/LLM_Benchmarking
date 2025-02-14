"""OpenSearch utilities for managing domains and operations."""

import json
import time
import datetime
import boto3
from typing import Dict, Optional

class OpenSearchManager:
    """Manages OpenSearch domain operations including setup, status checking, and cleanup."""
    
    def __init__(self, domain_name: str, cleanup_enabled: bool = True):
        """Initialize OpenSearch manager.
        
        Args:
            domain_name: Name of the OpenSearch domain
            cleanup_enabled: Whether to enable cleanup on deletion
        """
        self.domain_name = domain_name
        self.cleanup_enabled = cleanup_enabled
        self.client = boto3.client('opensearch')
        self.region = boto3.Session().region_name
        self._setup_identity()
        
    def _setup_identity(self):
        """Get current AWS identity."""
        sts = boto3.client('sts')
        self.identity = sts.get_caller_identity()
        self.current_arn = self.identity['Arn']
        
    def get_domain_status(self) -> Dict:
        """Get detailed OpenSearch domain status with progress information."""
        try:
            response = self.client.describe_domain(DomainName=self.domain_name)
            status = response['DomainStatus']
            
            # Get creation progress
            elapsed = 0
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
                
            return {
                'exists': True,
                'processing': status.get('Processing', False),
                'stage': status.get('DomainProcessingStatus', 'Unknown'),
                'created': status.get('Created', False),
                'endpoint': status.get('Endpoints', {}).get('vpc') or status.get('Endpoint'),
                'elapsed_minutes': elapsed,
                'full_status': status  # Include full status for debugging
            }
        except self.client.exceptions.ResourceNotFoundException:
            return {
                'exists': False,
                'processing': False,
                'stage': 'NotFound',
                'created': False,
                'endpoint': None,
                'elapsed_minutes': 0,
                'full_status': None
            }
            
    def create_domain(self) -> Dict:
        """Create a new OpenSearch domain with standard configuration."""
        return self.client.create_domain(
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
            elif not status['processing'] and status['endpoint']:
                print(f"\nOpenSearch domain is now active after {status['elapsed_minutes']:.1f} minutes")
                print(f"Stage: {status['stage']}")
                print(f"Endpoint: {status['endpoint']}")
                return status['endpoint']
            else:
                print(f"Domain status: {status['stage']} (elapsed: {status['elapsed_minutes']:.1f} minutes)")
            
            time.sleep(delay)
            attempt += 1
            
        print("\nFinal domain status:")
        print(json.dumps(status['full_status'], indent=2))
        raise TimeoutError(f"OpenSearch domain did not become active after {max_attempts * delay / 60:.1f} minutes")
        
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
            print(f"Status: {status['stage']}")
            print("Full domain status:")
            print(json.dumps(status['full_status'], indent=2))
            
            if status['endpoint']:
                print(f"\nDomain is active with endpoint: {status['endpoint']}")
                return status['endpoint']
                
            print("\nWaiting for domain to become active...")
            return self.wait_for_domain()
        else:
            print(f"\nCreating new domain: {self.domain_name}")
            try:
                response = self.create_domain()
                print("\nDomain creation response:")
                print(json.dumps(response, indent=2))
                
                print("\nWaiting for OpenSearch domain to be active (this may take 10-15 minutes)...")
                return self.wait_for_domain()
                
            except Exception as e:
                print(f"\nError creating domain: {str(e)}")
                print(f"Error type: {type(e)}")
                raise
                
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
            print(f"Deleting OpenSearch domain: {self.domain_name}")
            self.client.delete_domain(DomainName=self.domain_name)
            print("✅ Cleanup successful")
            print("Note: Domain deletion may take 15-20 minutes to complete")
        except Exception as e:
            print(f"❌ Error during cleanup: {str(e)}")
