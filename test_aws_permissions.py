"""Test AWS credentials and permissions for the benchmarking setup."""
import boto3
from botocore.exceptions import ClientError
import json

def test_aws_permissions():
    """Test AWS credentials and permissions."""
    required_services = {
        's3': ['ListBuckets', 'GetObject', 'PutObject'],
        'bedrock-runtime': ['InvokeModel']
    }
    
    missing_permissions = {}
    
    for service, actions in required_services.items():
        try:
            # Create a client for the service
            client = boto3.client(service)
            
            # Get the caller identity to verify credentials work
            sts = boto3.client('sts')
            sts.get_caller_identity()
            
            # Test specific permissions
            iam = boto3.client('iam')
            for action in actions:
                try:
                    response = iam.simulate_principal_policy(
                        PolicySourceArn=sts.get_caller_identity()['Arn'],
                        ActionNames=[f'{service}:{action}']
                    )
                    if response['EvaluationResults'][0]['EvalDecision'] != 'allowed':
                        if service not in missing_permissions:
                            missing_permissions[service] = []
                        missing_permissions[service].append(action)
                except Exception as e:
                    print(f"Warning: Could not check {action} permission: {str(e)}")
                    
        except Exception as e:
            print(f"❌ Error accessing {service}: {str(e)}")
            missing_permissions[service] = actions
    
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
