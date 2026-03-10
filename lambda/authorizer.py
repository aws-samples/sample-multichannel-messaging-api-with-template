import json
import jwt
import os
import boto3
from jwt import PyJWKClient

# Initialize clients
secrets_client = boto3.client('secretsmanager')

# JWT Configuration
JWT_SECRET_ARN = os.environ.get('JWT_SECRET_ARN')
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
JWT_ISSUER = os.environ.get('JWT_ISSUER', 'messaging-api')
JWKS_URL = os.environ.get('JWKS_URL', '')

# Cache for JWT secret (loaded once per Lambda container)
_jwt_secret_cache = None


def get_jwt_secret():
    """
    Retrieve JWT secret from Secrets Manager
    Uses caching to avoid repeated API calls
    """
    global _jwt_secret_cache
    
    if _jwt_secret_cache is None:
        try:
            response = secrets_client.get_secret_value(SecretId=JWT_SECRET_ARN)
            _jwt_secret_cache = response['SecretString']
        except Exception as e:
            print(f"Error retrieving JWT secret: {str(e)}")
            raise
    
    return _jwt_secret_cache


def lambda_handler(event, context):
    """
    Lambda Authorizer for API Gateway
    Validates JWT tokens and returns IAM policy
    """
    token = event.get('authorizationToken', '')
    method_arn = event['methodArn']
    
    # Remove 'Bearer ' prefix if present
    if token.startswith('Bearer '):
        token = token[7:]
    
    try:
        # Get JWT secret from Secrets Manager
        jwt_secret = get_jwt_secret()
        
        # Validate and decode JWT
        if JWKS_URL:
            # Use JWKS for validation (Auth0, Cognito, etc.)
            payload = validate_jwt_with_jwks(token)
        else:
            # Use shared secret for validation
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER
            )
        
        # Extract principal ID (user identifier)
        principal_id = payload.get('sub', 'user')
        
        # Generate allow policy
        policy = generate_policy(principal_id, 'Allow', method_arn, payload)
        
        return policy
        
    except jwt.ExpiredSignatureError:
        print("Token expired")
        raise Exception('Unauthorized: Token expired')
    except jwt.InvalidTokenError as e:
        print(f"Invalid token: {str(e)}")
        raise Exception('Unauthorized: Invalid token')
    except Exception as e:
        print(f"Authorization error: {str(e)}")
        raise Exception('Unauthorized')


def validate_jwt_with_jwks(token):
    """
    Validate JWT using JWKS endpoint
    Used for Auth0, Cognito, and other OIDC providers
    """
    jwks_client = PyJWKClient(JWKS_URL)
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=JWT_ISSUER
    )
    
    return payload


def generate_policy(principal_id, effect, resource, context=None):
    """
    Generate IAM policy for API Gateway
    """
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
    }
    
    # Add context to pass to downstream Lambda
    if context:
        policy['context'] = {
            'userId': context.get('sub', ''),
            'email': context.get('email', ''),
            'customerId': context.get('customer_id', '')
        }
    
    return policy
