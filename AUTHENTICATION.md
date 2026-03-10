# JWT Authentication Guide

This API uses JWT (JSON Web Token) authentication to secure all endpoints. This guide explains how the authentication system works and how to use it.

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Secret Management](#secret-management)
- [Generating Tokens](#generating-tokens)
- [Using Tokens](#using-tokens)
- [Token Structure](#token-structure)
- [Security Recommended Practices](#security-recommended-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Every API request must include a valid JWT token in the `Authorization` header. The token proves the request is from an authorized client and hasn't been tampered with.

**Key Concepts:**
- **JWT Secret:** A shared secret key used to sign and verify tokens
- **Token:** A time-limited credential that grants API access
- **Claims:** Information embedded in the token (user ID, email, etc.)
- **Signature:** Cryptographic proof the token is valid

## How It Works

```
┌─────────────┐                                    ┌──────────────────┐
│   Client    │                                    │   API Gateway    │
│             │                                    │                  │
│ 1. Generate │                                    │                  │
│    JWT      │─────2. Send Request with JWT ─────>│                  │
│    Token    │      Authorization: Bearer <token> │                  │
│             │                                    │                  │
└─────────────┘                                    └────────┬─────────┘
                                                            │
                                                            │ 3. Validate
                                                            ▼
                                                   ┌──────────────────┐
                                                   │ Lambda Authorizer│
                                                   │                  │
                                                   │• Get secret from │
                                                   │  Secrets Manager │
                                                   │• Verify signature│
                                                   │• Check expiration│
                                                   │                  │
                                                   └────────┬─────────┘
                                                            │
                                    ┌───────────────────────┴─────────────────────┐
                                    │                                             │
                                    ▼ Valid                                       ▼ Invalid
                           ┌─────────────────┐                          ┌─────────────────┐
                           │  Allow Request  │                          │  Deny Request   │
                           │                 │                          │                 │
                           │  Forward to     │                          │  Return 401     │
                           │  Backend        │                          │  Unauthorized   │
                           └─────────────────┘                          └─────────────────┘
```

## Architecture

### Components

1. **API Gateway**
   - Receives all API requests
   - Triggers Lambda Authorizer before processing
   - Caches authorization decisions (5 minutes)

2. **Lambda Authorizer**
   - Validates JWT tokens
   - Retrieves secret from Secrets Manager (cached in Lambda memory)
   - Returns Allow/Deny policy to API Gateway
   - Passes token claims (`userId`, `email`, `customerId`) as context to downstream services via the API Gateway authorizer response
   - **Security Note:** Secret caching is an AWS recommended practice - Lambda containers are isolated and ephemeral, which supports secure memory caching when combined with proper secret management practices

3. **AWS Secrets Manager**
   - Stores JWT secret securely
   - Encrypted at rest with KMS
   - Access controlled by IAM

4. **Client Application**
   - Generates JWT tokens using shared secret
   - Includes token in every API request
   - Regenerates tokens when expired

## Secret Management

### Server Side (API Provider)

**Location:** AWS Secrets Manager

**Secret ARN:**
```
arn:aws:secretsmanager:<your-region>:<your-account-id>:secret:my-messaging-api-jwt-secret-<unique-id>
```

**Access:**
- Only Lambda Authorizer has permission to read
- Encrypted at rest with AWS KMS
- Cached in Lambda memory for performance (secure due to container isolation - see shared responsibility note below)
- Audit trail in CloudWatch Logs

**Why Caching Can Be Implemented Securely:**
The JWT secret is cached in Lambda container memory to avoid repeated Secrets Manager API calls. When combined with proper security practices, this approach is secure because:
- Lambda containers are isolated from each other
- Containers are ephemeral (destroyed after inactivity)
- Secrets never persist to disk, only in memory
- Avoids $0.05 per 10,000 API calls and 100-200ms latency per request
- AWS recommended practice for Lambda + Secrets Manager

**Customer Responsibility:** You are responsible for implementing secret rotation policies, least-privilege IAM roles, CloudWatch monitoring, and regular security reviews to maintain the security of cached secrets.

**Rotation:**
```bash
# Update the secret
aws secretsmanager update-secret \
  --secret-id my-messaging-api-jwt-secret \
  --secret-string "new-secret-key-here" \
  --region <your-region>

# Lambda containers automatically pick up new secret as they recycle
# Or force immediate update by deploying a new function version
```

### Client Side (API Consumer)

**Storage Options:**

1. **Environment Variables** (Recommended for apps)
   ```bash
   export JWT_SECRET="your-secret-key"
   ```

2. **Configuration Files** (Never commit to git!)
   ```yaml
   # config.yaml
   jwt:
     secret: "your-secret-key"
     issuer: "messaging-api"
   ```

3. **Secrets Manager** (Recommended for production)
   - AWS Secrets Manager
   - 3rd party security vaults (e.g. Hashicorp Vault)

4. **Container Secrets**
   - Docker secrets
   - Kubernetes secrets

**⚠️ NEVER:**
- Hardcode in source code
- Commit to version control
- Share via email or chat
- Log or print to console

## Generating Tokens

### Prerequisites

Install PyJWT library:
```bash
pip install PyJWT
```

### Basic Token Generation

```python
import jwt
import datetime

# Configuration (must match API settings)
JWT_SECRET = os.environ.get('JWT_SECRET')  # Get from secure storage - never hardcode
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "messaging-api"

# Create token
def generate_token(user_id, email=None, customer_id=None, expires_in_hours=24):
    now = datetime.datetime.now(datetime.UTC)
    expiration = now + datetime.timedelta(hours=expires_in_hours)
    
    payload = {
        'sub': user_id,           # Subject (user identifier) - REQUIRED
        'iss': JWT_ISSUER,        # Issuer - REQUIRED
        'iat': now,               # Issued at - REQUIRED
        'exp': expiration,        # Expiration - REQUIRED
        'email': email,           # Optional
        'customer_id': customer_id  # Optional
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

# Example usage
token = generate_token(
    user_id='user123',
    email='user@example.com',
    customer_id='cust-001'
)

print(f"Token: {token}")
```

### Using the Provided Script

```bash
# Generate token with user ID only
python generate_jwt.py user123

# Generate token with email
python generate_jwt.py user123 user@example.com

# Generate token with email and customer ID
python generate_jwt.py user123 user@example.com cust-001
```

### Token Expiration

**Default:** 24 hours

**Customize:**
```python
# 1 hour token
token = generate_token(user_id='user123', expires_in_hours=1)

# 7 day token
token = generate_token(user_id='user123', expires_in_hours=168)
```

**Recommended Practices:**
- Short-lived tokens (1-24 hours) for better security
- Longer tokens (7 days) for convenience
- Implement token refresh for long-running applications

## Using Tokens

### HTTP Request Format

```http
POST /dev/ HTTP/1.1
Host: your-api-endpoint.execute-api.us-west-2.amazonaws.com
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

{
  "TraceId": "12345",
  "EmailMessage": {
    "FromAddress": "sender@example.com",
    "Subject": "Test"
  },
  "Addresses": {
    "recipient@example.com": {
      "ChannelType": "EMAIL"
    }
  }
}
```

### cURL Example

```bash
curl -X POST "https://your-api-endpoint/dev/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "TraceId": "12345",
    "EmailMessage": {
      "FromAddress": "sender@example.com",
      "Subject": "Test"
    },
    "Addresses": {
      "recipient@example.com": {
        "ChannelType": "EMAIL"
      }
    }
  }'
```

### Python Example

```python
import requests
import jwt
import datetime

# Generate token
def generate_token(user_id):
    JWT_SECRET = os.environ.get('JWT_SECRET')  # Never hardcode secrets
    JWT_ISSUER = "messaging-api"
    
    payload = {
        'sub': user_id,
        'iss': JWT_ISSUER,
        'iat': datetime.datetime.now(datetime.UTC),
        'exp': datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=24)
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

# Make API request
token = generate_token('user123')

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {token}'
}

payload = {
    'TraceId': '12345',
    'EmailMessage': {
        'FromAddress': 'sender@example.com',
        'Subject': 'Test'
    },
    'Addresses': {
        'recipient@example.com': {
            'ChannelType': 'EMAIL'
        }
    }
}

response = requests.post(
    'https://your-api-endpoint/dev/',
    headers=headers,
    json=payload
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

### JavaScript/Node.js Example

```javascript
const jwt = require('jsonwebtoken');
const axios = require('axios');

// Generate token
function generateToken(userId) {
  const JWT_SECRET = process.env.JWT_SECRET;
  const JWT_ISSUER = 'messaging-api';
  
  const payload = {
    sub: userId,
    iss: JWT_ISSUER,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + (24 * 60 * 60) // 24 hours
  };
  
  return jwt.sign(payload, JWT_SECRET, { algorithm: 'HS256' });
}

// Make API request
async function sendMessage() {
  const token = generateToken('user123');
  
  const response = await axios.post(
    'https://your-api-endpoint/dev/',
    {
      TraceId: '12345',
      EmailMessage: {
        FromAddress: 'sender@example.com',
        Subject: 'Test'
      },
      Addresses: {
        'recipient@example.com': {
          ChannelType: 'EMAIL'
        }
      }
    },
    {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    }
  );
  
  console.log('Status:', response.status);
  console.log('Response:', response.data);
}

sendMessage();
```

## Token Structure

A JWT token has three parts separated by dots (`.`):

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMTIzIiwiaXNzIjoibWVzc2FnaW5nLWFwaSIsImlhdCI6MTc2OTExNjEwMSwiZXhwIjoxNzY5MjAyNTAxfQ.[EXAMPLE_SIGNATURE_REDACTED]
│                                      │                                                                                                                                    │
└─ Header                              └─ Payload (Claims)                                                                                                                  └─ Signature
```

### Header

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

- `alg`: Algorithm used for signing (HS256 = HMAC-SHA256)
- `typ`: Token type (always JWT)

### Payload (Claims)

```json
{
  "sub": "user123",
  "iss": "messaging-api",
  "iat": 1769116101,
  "exp": 1769202501,
  "email": "user@example.com",
  "customer_id": "cust-001"
}
```

**Required Claims:**
- `sub` (subject): User identifier
- `iss` (issuer): Must be "messaging-api"
- `iat` (issued at): Token creation timestamp
- `exp` (expiration): Token expiration timestamp

**Optional Claims:**
- `email`: User email address
- `customer_id`: Customer identifier for tenant/customer-level context
- Any custom claims you need

**How optional claims flow through the system:**

When the Lambda authorizer validates a token, it extracts `sub`, `email`, and `customer_id` from the JWT payload and forwards them as context values (`userId`, `email`, `customerId`) in the API Gateway authorizer response. This makes them available to any downstream service behind the gateway.

The message processor Lambda does not currently use `customer_id`, so it serves as a pass-through claim that downstream consumers can leverage for tenant isolation, customer-scoped logging, or access control.

### Signature

```
HMACSHA256(
  base64UrlEncode(header) + "." + base64UrlEncode(payload),
  JWT_SECRET
)
```

The signature proves:
1. Token was created by someone with the secret
2. Token hasn't been modified
3. Token is authentic

## Security Recommended Practices

### Secret Management

✅ **DO:**
- Store secrets in secure vaults (AWS Secrets Manager, etc.)
- Use environment variables for configuration
- Rotate secrets periodically
- Use different secrets for dev/staging/production
- Limit secret access to only necessary services

❌ **DON'T:**
- Hardcode secrets in source code
- Commit secrets to version control
- Share secrets via email or chat
- Log secrets to console or files
- Use weak or predictable secrets

### Token Handling

✅ **DO:**
- Use HTTPS for all API requests
- Set appropriate token expiration times
- Validate tokens on every request
- Cache tokens to avoid regenerating
- Implement token refresh mechanism

❌ **DON'T:**
- Send tokens over HTTP (unencrypted)
- Store tokens in localStorage (XSS risk)
- Use tokens after expiration
- Share tokens between users
- Log tokens in application logs

### Secret Strength

**Good Secret:**
```
aB3$xK9#mP2@qL7&nR5!wT8^yU4*zV6
```
- 32+ characters
- Mix of uppercase, lowercase, numbers, symbols
- Random and unpredictable

**Bad Secret:**
```
password123
```
- Too short
- Predictable
- Easy to guess

**Generate Strong Secret:**
```bash
# Linux/Mac
openssl rand -base64 32

# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Network Security

- Always use HTTPS
- Enable API Gateway throttling
- Implement rate limiting
- Monitor for suspicious activity
- Use WAF for additional protection

## Troubleshooting

### 401 Unauthorized

**Cause:** Missing or invalid token

**Solutions:**
- Ensure `Authorization` header is present
- Check token format: `Bearer <token>`
- Verify token hasn't expired
- Confirm secret matches on both sides

**Test:**
```bash
# Check if token is included
curl -v https://your-api-endpoint/dev/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Look for Authorization header in output
```

### 403 Forbidden

**Cause:** Token is valid but lacks permissions

**Solutions:**
- Check token claims match requirements
- Verify issuer is "messaging-api"
- Ensure user has necessary permissions

### 500 Internal Server Error

**Cause:** Authorizer failed to validate token

**Common Issues:**
- Malformed token (not proper JWT format)
- Wrong algorithm
- Secret mismatch
- Authorizer Lambda error

**Debug:**
```bash
# Check Lambda Authorizer logs
aws logs tail /aws/lambda/JWTAuthorizer --follow --region <your-region>
```

### Token Expired

**Error:** `Token expired`

**Solution:**
```python
# Generate new token
token = generate_token('user123')

# Use new token in request
```

### Invalid Signature

**Error:** `Invalid token: Signature verification failed`

**Cause:** Secret mismatch

**Solution:**
- Verify you're using the correct secret
- Check for typos or extra spaces
- Ensure secret hasn't been rotated

### Token Caching Issues

**Problem:** Old tokens still work after secret rotation

**Cause:** API Gateway caches authorization decisions for 5 minutes

**Solution:**
- Wait 5 minutes for cache to expire
- Or create new API Gateway deployment:
  ```bash
  aws apigateway create-deployment \
    --rest-api-id YOUR_API_ID \
    --stage-name dev \
    --region <your-region>
  ```

## Additional Resources

- [JWT.io](https://jwt.io/) - Decode and verify tokens
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)
- [API Gateway Lambda Authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html)

## Support

For issues or questions:
1. Check CloudWatch Logs for Lambda Authorizer
2. Verify token structure at jwt.io
3. Test with a freshly generated token
4. Review this documentation
