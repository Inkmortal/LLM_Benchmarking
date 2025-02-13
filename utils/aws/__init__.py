"""AWS utilities for checking permissions and providing setup instructions."""

import boto3
from botocore.exceptions import ClientError
import json
import os

def is_running_in_sagemaker():
    """Check if we're running in a SageMaker notebook."""
    return os.path.exists('/opt/ml/metadata/resource-metadata.json')

def test_s3_permissions():
    """Test S3 permissions by attempting actual operations."""
    missing_permissions = []
    s3 = boto3.client('s3')
    test_bucket = "test-permissions-bucket-" + str(hash(str(boto3.client('sts').get_caller_identity())))[:8]
    test_key = "test-file.txt"
    test_data = b"test data"

    try:
        # Test ListBuckets
        try:
            s3.list_buckets()
            print("✅ S3:ListBuckets - Success")
        except ClientError as e:
            missing_permissions.append('ListBuckets')
            print(f"❌ S3:ListBuckets - {e.response['Error']['Message']}")

        # Test CreateBucket, PutObject, GetObject, DeleteObject, DeleteBucket
        try:
            s3.create_bucket(Bucket=test_bucket)
            print("✅ S3:CreateBucket - Success")
            
            s3.put_object(Bucket=test_bucket, Key=test_key, Body=test_data)
            print("✅ S3:PutObject - Success")
            
            s3.get_object(Bucket=test_bucket, Key=test_key)
            print("✅ S3:GetObject - Success")
            
            s3.delete_object(Bucket=test_bucket, Key=test_key)
            print("✅ S3:DeleteObject - Success")
            
            s3.delete_bucket(Bucket=test_bucket)
            print("✅ S3:DeleteBucket - Success")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if 'AccessDenied' in error_code:
                current_operation = e.operation_name
                missing_permissions.append(current_operation)
                print(f"❌ S3:{current_operation} - {e.response['Error']['Message']}")
            else:
                print(f"Warning: Non-permission error during S3 tests: {str(e)}")
    except Exception as e:
        print(f"❌ Error during S3 tests: {str(e)}")
        missing_permissions.extend(['ListBuckets', 'CreateBucket', 'PutObject', 'GetObject', 'DeleteObject', 'DeleteBucket'])

    return missing_permissions if missing_permissions else None

def test_bedrock_permissions():
    """Test Bedrock permissions."""
    try:
        bedrock = boto3.client('bedrock-runtime')
        # List models to verify access (doesn't cost money)
        bedrock_mgr = boto3.client('bedrock')
        bedrock_mgr.list_foundation_models()
        print("✅ Bedrock access verified")
        return None
    except Exception as e:
        print(f"❌ Error accessing Bedrock: {str(e)}")
        return ['InvokeModel', 'ListFoundationModels']

def test_neptune_permissions():
    """Test Neptune permissions."""
    try:
        neptune = boto3.client('neptune')
        # List DB clusters to verify access
        neptune.describe_db_clusters()
        print("✅ Neptune access verified")
        return None
    except Exception as e:
        print(f"❌ Error accessing Neptune: {str(e)}")
        return ['neptune-db:*']

def test_opensearch_permissions():
    """Test OpenSearch permissions."""
    try:
        opensearch = boto3.client('opensearch')
        # List domains to verify access
        opensearch.list_domain_names()
        print("✅ OpenSearch access verified")
        return None
    except Exception as e:
        print(f"❌ Error accessing OpenSearch: {str(e)}")
        return ['opensearch:*']

def get_policy_info(service):
    """Get policy information for a specific service."""
    policies = {
        's3': {
            'name': 'AmazonS3FullAccess',
            'arn': 'arn:aws:iam::aws:policy/AmazonS3FullAccess',
            'description': 'Provides access to Amazon S3',
            'actions': ['s3:*'],
            'resource': '*'
        },
        'bedrock': {
            'name': 'AmazonBedrockFullAccess',
            'arn': 'arn:aws:iam::aws:policy/AmazonBedrockFullAccess',
            'description': 'Provides access to Amazon Bedrock services',
            'actions': ['bedrock:InvokeModel', 'bedrock:ListFoundationModels'],
            'resource': '*'
        },
        'neptune': {
            'name': 'NeptuneFullAccess',
            'arn': 'arn:aws:iam::aws:policy/NeptuneFullAccess',
            'description': 'Provides access to Amazon Neptune',
            'actions': ['neptune-db:*'],
            'resource': '*'
        },
        'opensearch': {
            'name': 'AmazonOpenSearchServiceFullAccess',
            'arn': 'arn:aws:iam::aws:policy/AmazonOpenSearchServiceFullAccess',
            'description': 'Provides access to Amazon OpenSearch Service',
            'actions': ['opensearch:*'],
            'resource': '*'
        }
    }
    return policies.get(service)

def print_missing_policy_instructions(service, missing_permissions=None):
    """Print instructions for a specific missing policy."""
    policy = get_policy_info(service)
    if not policy:
        return
    
    print(f"\n• {policy['name']}")
    print(f"  ARN: {policy['arn']}")
    print(f"  Purpose: {policy['description']}")
    if missing_permissions:
        print("  Missing Actions:")
        for perm in missing_permissions:
            print(f"    - {perm}")

def check_aws_access():
    """Verify AWS access and provide appropriate setup instructions."""
    try:
        # Try to get caller identity
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        
        print("✅ AWS access configured successfully!")
        print(f"Account: {identity['Account']}")
        print(f"Identity ARN: {identity['Arn']}")
        
        print("\n=== Testing Required Permissions ===\n")
        
        # Test each service
        missing_permissions = {}
        service_tests = {
            's3': test_s3_permissions,
            'bedrock': test_bedrock_permissions,
            'neptune': test_neptune_permissions,
            'opensearch': test_opensearch_permissions
        }
        
        for service, test_func in service_tests.items():
            print(f"\nTesting {service.upper()} permissions:")
            missing = test_func()
            if missing:
                missing_permissions[service] = missing
        
        # If permissions are missing, show relevant instructions
        if missing_permissions:
            print("\n❌ Missing permissions detected!")
            print("\n📋 Required Policy Instructions")
            print("----------------------------------------")
            print("Attach these policies to your role:")
            
            for service in missing_permissions:
                print_missing_policy_instructions(service, missing_permissions[service])
                
            print("\n📝 Steps to update permissions:")
            print("1. Go to AWS Console > IAM > Roles")
            if is_running_in_sagemaker():
                role_name = identity['Arn'].split('/')[-1]
                print(f"2. Search for and select: {role_name}")
            print("3. Click 'Attach policies'")
            print("4. Search for and attach the policies listed above")
        else:
            print("\n✅ All required permissions are present!")
        
        return True
        
    except Exception as e:
        print("❌ AWS access not configured!")
        print("Error:", str(e))
        
        print("\nTo configure AWS access, choose one of these methods:")
        print("\n1. AWS CLI (Recommended):")
        print("   Run: aws configure")
        print("   Enter your:")
        print("   - AWS Access Key ID")
        print("   - AWS Secret Access Key")
        print("   - Default region (e.g., us-west-2)")
        print("\n2. Environment Variables:")
        print("   export AWS_ACCESS_KEY_ID=your_access_key")
        print("   export AWS_SECRET_ACCESS_KEY=your_secret_key")
        print("   export AWS_DEFAULT_REGION=your_region")
        print("\n3. Credentials File:")
        print("   Create ~/.aws/credentials with:")
        print("   [default]")
        print("   aws_access_key_id = your_access_key")
        print("   aws_secret_access_key = your_secret_key")
        
        return False
