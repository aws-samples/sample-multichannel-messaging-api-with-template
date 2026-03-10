#!/usr/bin/env python3
"""
Generate JWT tokens for testing the messaging API
"""
import jwt
import datetime
import os
import sys

# Configuration (must match Lambda authorizer settings)
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "messaging-api")


def generate_token(user_id, email=None, customer_id=None, expires_in_hours=24):
    """
    Generate a JWT token
    
    Args:
        user_id: Unique user identifier
        email: User email (optional)
        customer_id: Customer ID (optional)
        expires_in_hours: Token expiration time in hours
    
    Returns:
        JWT token string
    """
    now = datetime.datetime.now(datetime.UTC)
    expiration = now + datetime.timedelta(hours=expires_in_hours)
    
    payload = {
        'sub': user_id,
        'iss': JWT_ISSUER,
        'iat': now,
        'exp': expiration
    }
    
    # Add optional claims
    if email:
        payload['email'] = email
    if customer_id:
        payload['customer_id'] = customer_id
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    return token


if __name__ == '__main__':
    if not JWT_SECRET:
        print("Error: JWT_SECRET environment variable is not set.")
        print("Set it with: export JWT_SECRET=$(aws secretsmanager get-secret-value "
              "--secret-id <stack-name>-jwt-secret --query SecretString --output text)")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python generate_jwt.py <user_id> [email] [customer_id]")
        print("\nExample:")
        print("  python generate_jwt.py user123 user@example.com cust456")
        sys.exit(1)
    
    user_id = sys.argv[1]
    email = sys.argv[2] if len(sys.argv) > 2 else None
    customer_id = sys.argv[3] if len(sys.argv) > 3 else None
    
    token = generate_token(user_id, email, customer_id)
    
    print("\n" + "="*80)
    print("JWT Token Generated Successfully")
    print("="*80)
    print(f"\nUser ID: {user_id}")
    if email:
        print(f"Email: {email}")
    if customer_id:
        print(f"Customer ID: {customer_id}")
    print(f"\nToken (valid for 24 hours):")
    print("-"*80)
    print(token)
    print("-"*80)
    print(f"\nUse in API calls with header:")
    print(f'Authorization: Bearer {token}')
    print("="*80 + "\n")
