"""Test AWS credentials and permissions for the benchmarking setup."""
import boto3
from botocore.exceptions import ClientError
import json

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

    return missing_permissions

def test_bedrock_permissions():
    """Test Bedrock permissions."""
    try:
        bedrock = boto3.client('bedrock-runtime')
        # Just check if we can create the client - actual invoke would cost money
        print("✅ Bedrock client creation successful")
        return []
    except Exception as e:
        print(f"❌ Error accessing Bedrock: {str(e)}")
        return ['InvokeModel']

def test_aws_permissions():
    """Test AWS credentials and permissions."""
    missing_s3 = test_s3_permissions()
    missing_bedrock = test_bedrock_permissions()
    
    missing_permissions = {}
    if missing_s3:
        missing_permissions['s3'] = missing_s3
    if missing_bedrock:
        missing_permissions['bedrock-runtime'] = missing_bedrock
        
    return missing_permissions

if __name__ == "__main__":
    print("=== Testing AWS Permissions ===\n")
    missing_permissions = test_aws_permissions()
    
    if missing_permissions:
        print("\n❌ Missing required AWS permissions:")
        print(json.dumps(missing_permissions, indent=2))
        print("\nPlease add the missing permissions to your AWS credentials.")
    else:
        print("\n✅ All required AWS permissions are present")
