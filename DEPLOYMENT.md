# Serverless Multi-Channel Messaging API with Template Management - Deployment Guide

A serverless AWS solution for sending email and SMS notifications through a single REST API with reliable message queuing and DynamoDB-backed template management.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Initial Setup](#initial-setup)
5. [Deployment Steps](#deployment-steps)
6. [Post-Deployment Configuration](#post-deployment-configuration)
7. [Testing Your Deployment](#testing-your-deployment)
8. [Using the API](#using-the-api)
9. [Key Features](#key-features)
10. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
11. [Production Checklist](#production-checklist)

---

## Overview

This system provides a complete infrastructure for:

- **Email Delivery**: Send emails via Amazon SES with template support
- **SMS Delivery**: Send SMS messages via AWS End User Messaging
- **Template Management**: Store and reuse message templates in DynamoDB
- **Reliable Processing**: SQS queuing ensures messages aren't lost
- **Secure API**: JWT-based authentication for all API operations
- **Automatic Retries**: Failed messages retry up to 3 times before moving to dead letter queue

### How It Works

1. **Client sends** message request to REST API with JWT token
2. **API Gateway validates** JWT token via Lambda Authorizer
3. **API Gateway queues** message in SQS (returns immediately)
4. **SQS triggers** Lambda function to process messages
5. **Lambda retrieves** templates from DynamoDB (if using templates)
6. **Lambda sends** via Amazon SES (email) or AWS End User Messaging (SMS)
7. **Failed messages** retry automatically or move to dead letter queue

---

## Architecture

![Multichannel Messaging API Architecture](multichannel-messaging-api.png)

### Key Components

**API Gateway** - REST API with JWT authentication
- Single POST endpoint for message submission
- JWT authorizer validates all requests
- Direct SQS integration (no Lambda proxy)

**Lambda Functions**
- JWT Authorizer - Validates authentication tokens
- Message Processor - Sends emails and SMS messages

**SQS Queues**
- Messages Queue - Buffers incoming message requests
- Dead Letter Queue - Captures failed messages after 3 retries

**DynamoDB Table**
- Message Templates - Stores reusable email/SMS templates

**AWS Secrets Manager**
- JWT Secret - Securely stores authentication secret (cached in Lambda memory per AWS recommended practices)

**Amazon SES** - Email delivery service

**AWS End User Messaging** - SMS delivery service

### Architecture Highlights

**Serverless** - No servers to manage, automatic scaling
- Lambda functions for compute
- DynamoDB for template storage (on-demand billing)
- API Gateway for REST API
- SQS for reliable message queuing

**Secure** - Multiple layers of security
- JWT authentication on all endpoints
- Secrets stored in AWS Secrets Manager (cached in Lambda memory for performance - an AWS recommended practice)
- Lambda container isolation helps keep cached secrets secure and ephemeral
- IAM roles with least privilege
- HTTPS encryption in transit
- KMS customer-managed key encryption at rest for all data stores

**Reliable** - Built for resilience
- SQS queuing decouples API from delivery
- Automatic retries (up to 3 attempts)
- Dead Letter Queue for failed messages
- CloudWatch alarm for DLQ monitoring

**Cost-Effective** - Pay only for usage
- On-demand DynamoDB billing
- Lambda charged per invocation
- SQS minimal cost
- SES/SMS charged per message

---

## Prerequisites

Before you begin, verify you have the following:

### Required Software

1. **AWS Account** with administrative access
   - Sign up at https://aws.amazon.com if you don't have one

2. **AWS CLI** (version 2.x or later)
   - Download: https://aws.amazon.com/cli/
   - Verify installation:
     ```bash
     aws --version
     ```

3. **AWS SAM CLI** (version 1.x or later)
   - Install via pip:
     ```bash
     pip install aws-sam-cli
     ```
   - Verify installation:
     ```bash
     sam --version
     ```

4. **Python 3.12 or later**
   - Download: https://www.python.org/downloads/
   - Verify installation:
     ```bash
     python --version
     ```

5. **PyJWT Library** (for generating tokens)
   - Install:
     ```bash
     pip install PyJWT
     ```

### AWS Account Preparation

1. **Configure AWS CLI** with your credentials:
   ```bash
   aws configure
   ```

   You'll be prompted for:
   - AWS Access Key ID
   - AWS Secret Access Key
   - Default region (e.g., `us-east-1`)
   - Default output format (use `json`)

2. **Verify AWS CLI access**:
   ```bash
   aws sts get-caller-identity
   ```

   This should return your account information.

### AWS Service Requirements

- Verified email addresses in Amazon SES
- SMS origination number in AWS End User Messaging (if sending SMS)

---

## Initial Setup

### Step 1: Clone or Extract the Package

Clone the repository or extract the package to a working directory:

```bash
git clone <repository-url>
cd multichannel-messaging-api-with-template
```

You should see:
- `template.yaml` - SAM infrastructure template
- `lambda/` - Lambda function code
- `README.md` - API documentation
- `AUTHENTICATION.md` - JWT authentication guide
- `DEPLOYMENT.md` - This deployment guide
- `generate_jwt.py` - Token generation script

### Step 2: Generate a Strong JWT Secret

**CRITICAL:** Do NOT use the default secret in production!

Generate a cryptographically secure random secret:

**Option 1: Using Python**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Option 2: Using OpenSSL (Linux/Mac)**
```bash
openssl rand -base64 32
```

**Option 3: Using PowerShell (Windows)**
```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))
```

**Save this secret securely!** You'll need it for:
- Deployment (next step)
- Generating JWT tokens
- Your application configuration

---

## Deployment Steps

### Step 3: Build the Application

```bash
sam build
```

If you see errors, ensure:
- You're in the correct directory
- Python 3.12 is installed
- SAM CLI is properly installed

### Step 4: Deploy to AWS

```bash
sam deploy --guided
```

#### Deployment Prompts and Recommended Answers

1. **Stack Name**: `my-messaging-api` (or your preferred name)
2. **AWS Region**: Your preferred region (e.g., `us-east-1`)
3. **Parameter JWTSecret**: **Paste your generated secret** from Step 2
4. **Confirm changes before deploy**: `Y`
5. **Allow SAM CLI IAM role creation**: `Y`
6. **Disable rollback**: `N`
7. **AuthorizerFunction has no authentication**: `y` (expected - the authorizer itself doesn't need auth)
8. **Save arguments to configuration file**: `Y`
9. **SAM configuration file**: Press Enter (accept default)
10. **SAM configuration environment**: Press Enter (accept default)

### Step 5: Save Your Outputs

When deployment completes, save the output values:

```
Key                 ApiEndpoint
Value               https://abc123xyz.execute-api.us-east-1.amazonaws.com/dev/

Key                 JWTSecretArn
Value               arn:aws:secretsmanager:us-east-1:123456789012:secret:my-messaging-api-jwt-secret-AbCdEf

Key                 MessagesQueueUrl
Value               https://sqs.us-east-1.amazonaws.com/123456789012/MessagesQueue

Key                 DeadLetterQueueUrl
Value               https://sqs.us-east-1.amazonaws.com/123456789012/MessagesDeadLetterQueue
```

You'll need these for API calls, monitoring, and secret rotation.

---

## Post-Deployment Configuration

### Step 6: Verify Email Addresses in Amazon SES

#### For Sandbox Mode (Testing)

```bash
# Verify sender email
aws sesv2 create-email-identity \
  --email-identity your-sender@example.com \
  --region <your-region>

# Verify recipient email (required in sandbox mode)
aws sesv2 create-email-identity \
  --email-identity recipient@example.com \
  --region <your-region>
```

Check your email for verification links from Amazon SES and click them.

#### For Production (Sending to Any Email)

1. Go to AWS Console → Amazon SES → Account dashboard
2. Click "Request production access"
3. Fill out the form and submit (usually approved within 24 hours)

### Step 7: Configure SMS (Optional)

#### Option A: Using AWS Console

1. Go to AWS Console → AWS End User Messaging
2. Click "Phone numbers" → "Request phone number"
3. Choose country, number type (Toll-free or 10DLC), and message type (Transactional)
4. Complete registration and note your phone number or pool ID

#### Option B: Using AWS CLI

```bash
aws pinpoint-sms-voice-v2 request-phone-number \
  --iso-country-code US \
  --message-type TRANSACTIONAL \
  --number-type TOLL_FREE \
  --region <your-region>
```

### Step 8: Add Message Templates (Optional)

#### SMS Template

```bash
aws dynamodb put-item \
  --table-name MessageTemplates \
  --region <your-region> \
  --item '{
    "TemplateName": {"S": "alert-template"},
    "MessageBody": {"S": "Alert: Your {productName} account ending in {membershipNumber} has a low balance of ${accountBalance}"}
  }'
```

#### Email Template

```bash
aws dynamodb put-item \
  --table-name MessageTemplates \
  --region <your-region> \
  --item '{
    "TemplateName": {"S": "email-alert-template"},
    "MessageBody": {"S": "<html><body><h2>Account Alert</h2><p>Your {productName} account ending in {membershipNumber} has a low balance of ${accountBalance}.</p><p>Please take action to avoid service interruptions.</p></body></html>"},
    "Subject": {"S": "Low Balance Alert - {productName}"}
  }'
```

#### Verify Templates

```bash
aws dynamodb scan --table-name MessageTemplates --region <your-region>
```

**Template Size Limits:**
- DynamoDB has a 400 KB limit per item (including attribute names and values)
- This is sufficient for most email and SMS templates
- Typical email templates: 5-20 KB
- Typical SMS templates: < 1 KB
- If you need larger templates, consider storing them in [Amazon SES](https://docs.aws.amazon.com/ses/latest/APIReference-V2/API_CreateEmailTemplate.html) and referencing the template in DynamoDB

---

## Testing Your Deployment

### Step 9: Generate a Test JWT Token

```bash
export JWT_SECRET="your-actual-secret-from-step-2"
python generate_jwt.py test-user test@example.com customer-001
```

Copy the generated token for use in API calls.

### Step 10: Test Email Sending

```bash
curl -X POST "YOUR_API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "TraceId": "test-001",
    "EmailMessage": {
      "FromAddress": "your-verified-sender@example.com",
      "Subject": "Test Email from Messaging API"
    },
    "Addresses": {
      "your-verified-recipient@example.com": {
        "ChannelType": "EMAIL"
      }
    }
  }'
```

Expected response:
```json
{
  "status": "Message sent to queue"
}
```

### Step 11: Test SMS Sending (Optional)

```bash
curl -X POST "YOUR_API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "TraceId": "test-002",
    "SMSMessage": {
      "MessageType": "TRANSACTIONAL",
      "OriginationNumber": "YOUR_PHONE_NUMBER_OR_POOL_ID",
      "MessageBody": "Test SMS from Messaging API"
    },
    "Addresses": {
      "+1234567890": {
        "ChannelType": "SMS"
      }
    }
  }'
```

### Step 12: Test with Template

```bash
curl -X POST "YOUR_API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "TraceId": "test-003",
    "EmailMessage": {
      "FromAddress": "your-verified-sender@example.com",
      "TemplateName": "email-alert-template"
    },
    "Addresses": {
      "your-verified-recipient@example.com": {
        "ChannelType": "EMAIL",
        "Substitutions": {
          "productName": "CHEQUING",
          "membershipNumber": "****5493",
          "accountBalance": "100.00"
        }
      }
    }
  }'
```

---

## Using the API

### Authentication

All API requests require a JWT token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### API Endpoint

```
POST https://your-api-endpoint.execute-api.<region>.amazonaws.com/dev/
```

### Request Format

```json
{
  "TraceId": "unique-identifier",
  "EmailMessage": {
    "FromAddress": "sender@example.com",
    "Subject": "Subject line",
    "MessageBody": "Optional inline message",
    "TemplateName": "Optional template name",
    "Substitutions": {
      "variable": "value"
    }
  },
  "SMSMessage": {
    "MessageType": "TRANSACTIONAL",
    "OriginationNumber": "phone-number-or-pool-id",
    "MessageBody": "Optional inline message",
    "TemplateName": "Optional template name"
  },
  "Addresses": {
    "recipient@example.com": {
      "ChannelType": "EMAIL"
    },
    "+1234567890": {
      "ChannelType": "SMS",
      "Substitutions": {
        "variable": "value"
      }
    }
  }
}
```

### Integration Examples

#### Python

```python
import requests
import jwt
import datetime
import os

# Configuration
API_ENDPOINT = "https://your-api-endpoint.execute-api.us-east-1.amazonaws.com/dev/"
JWT_SECRET = os.environ.get('JWT_SECRET')

# Generate token
def generate_token(user_id):
    payload = {
        'sub': user_id,
        'iss': 'messaging-api',
        'iat': datetime.datetime.now(datetime.UTC),
        'exp': datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

# Send message
def send_message(trace_id, from_email, to_email, subject):
    token = generate_token('user123')

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }

    payload = {
        'TraceId': trace_id,
        'EmailMessage': {
            'FromAddress': from_email,
            'Subject': subject
        },
        'Addresses': {
            to_email: {
                'ChannelType': 'EMAIL'
            }
        }
    }

    response = requests.post(API_ENDPOINT, headers=headers, json=payload)
    return response.json()

# Usage
result = send_message('test-001', 'sender@example.com', 'recipient@example.com', 'Test')
print(result)
```

#### Node.js

```javascript
const jwt = require('jsonwebtoken');
const axios = require('axios');

const API_ENDPOINT = 'https://your-api-endpoint.execute-api.us-east-1.amazonaws.com/dev/';
const JWT_SECRET = process.env.JWT_SECRET;

function generateToken(userId) {
  const payload = {
    sub: userId,
    iss: 'messaging-api',
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + (24 * 60 * 60)
  };
  return jwt.sign(payload, JWT_SECRET, { algorithm: 'HS256' });
}

async function sendMessage(traceId, fromEmail, toEmail, subject) {
  const token = generateToken('user123');

  const response = await axios.post(
    API_ENDPOINT,
    {
      TraceId: traceId,
      EmailMessage: { FromAddress: fromEmail, Subject: subject },
      Addresses: { [toEmail]: { ChannelType: 'EMAIL' } }
    },
    {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    }
  );
  return response.data;
}

sendMessage('test-001', 'sender@example.com', 'recipient@example.com', 'Test')
  .then(result => console.log(result))
  .catch(error => console.error(error));
```

---

## Key Features

### Template System

Store reusable templates in DynamoDB with `{variable}` placeholders:

```json
{
  "TemplateName": "alert-template",
  "MessageBody": "Alert: Your {productName} account ending in {membershipNumber} has a low balance of ${accountBalance}"
}
```

### Multi-Channel Support

Send to email, SMS, or both in a single request by including both `EmailMessage` and `SMSMessage` in the payload.

### Configuration Set Support

Track delivery metrics using Configuration Sets:

- **Deployment-level defaults**: Set `SESConfigurationSet` and `SMSConfigurationSet` parameters during deployment
- **Per-message override**: Include `ConfigurationSetName` in `EmailMessage` or `SMSMessage` to override defaults

### Flexible Substitutions

Both simple string and array formats are supported:

```json
{
  "Substitutions": {
    "productName": "CHEQUING",
    "accountBalance": "100.00"
  }
}
```

### Batch Processing

Lambda processes up to 10 messages per invocation with partial batch failure support — only failed messages are retried.

### Dead Letter Queue

Failed messages are preserved for 14 days in the DLQ. A CloudWatch alarm monitors the DLQ and triggers SNS notifications when messages arrive.

---

## Monitoring and Troubleshooting

### Check Queue Depth

```bash
aws sqs get-queue-attributes \
  --queue-url YOUR_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages \
  --region <your-region>
```

### Check Dead Letter Queue

```bash
aws sqs get-queue-attributes \
  --queue-url YOUR_DLQ_URL \
  --attribute-names ApproximateNumberOfMessages \
  --region <your-region>
```

### View Lambda Logs

```bash
# Message Processor logs
aws logs tail /aws/lambda/MessageProcessor --follow --region <your-region>

# Authorizer logs
aws logs tail /aws/lambda/JWTAuthorizer --follow --region <your-region>
```

### Common Issues

#### 401 Unauthorized
- Verify `Authorization: Bearer <token>` header format
- Generate a fresh token
- Confirm JWT secret matches deployment
- Check token hasn't expired (default: 24 hours)

#### Email Not Sending
- Verify sender email in SES: `aws sesv2 list-email-identities --region <your-region>`
- Check SES sandbox status: `aws sesv2 get-account --region <your-region>`
- Check Lambda logs and recipient spam folder

#### SMS Not Sending
- Verify phone number format includes `+` country code
- Check origination number: `aws pinpoint-sms-voice-v2 describe-phone-numbers --region <your-region>`
- Check Lambda logs and SMS quota

#### Messages in Dead Letter Queue
- View DLQ messages: `aws sqs receive-message --queue-url YOUR_DLQ_URL --max-number-of-messages 10 --region <your-region>`
- Check Lambda logs for errors
- Fix the underlying issue, then redrive via AWS Console: SQS → Select DLQ → Start DLQ redrive

---

## Handling Failed Messages

### Redrive from Console

1. Go to SQS Console
2. Select Dead Letter Queue
3. Click "Start DLQ redrive"
4. Choose destination (main queue)

### Manual Inspection

```bash
aws sqs receive-message \
  --queue-url <your-dlq-url> \
  --max-number-of-messages 10 \
  --region <your-region>
```

---

## Production Checklist

### Security
- [ ] Strong JWT secret generated (32+ characters)
- [ ] JWT secret stored securely (not in code)
- [ ] Different secrets for dev/staging/production
- [ ] API Gateway throttling configured
- [ ] IAM permissions reviewed (least privilege)

### Amazon SES
- [ ] Production access requested and approved
- [ ] Sender email addresses verified
- [ ] SPF/DKIM/DMARC configured for your domain
- [ ] Bounce and complaint handling configured

### AWS End User Messaging
- [ ] Phone number or sender ID registered
- [ ] 10DLC registration completed (US)
- [ ] SMS quota sufficient for your volume
- [ ] Opt-out handling implemented
- [ ] Compliance requirements met (TCPA, etc.)

### Monitoring
- [ ] CloudWatch alarms configured with SNS notifications
- [ ] Log retention configured
- [ ] Dashboard created for key metrics

### Testing
- [ ] Load testing completed
- [ ] Failure scenarios tested
- [ ] DLQ redrive process tested
- [ ] Multi-channel sending tested

### Backup and Recovery
- [ ] DynamoDB point-in-time recovery enabled
- [ ] CloudFormation template backed up
- [ ] Rollback procedure tested

---

## Cleanup

To remove all resources:

```bash
sam delete --stack-name my-messaging-api --region <your-region>
```

**Note:** The Secrets Manager secret will be scheduled for deletion (7-30 days) but not immediately deleted.

---

## Support Resources

- **README.md** - API usage examples and quick reference
- **AUTHENTICATION.md** - Detailed JWT authentication guide
- **AWS Documentation**:
  - [Amazon SQS](https://docs.aws.amazon.com/sqs/)
  - [AWS Lambda](https://docs.aws.amazon.com/lambda/)
  - [Amazon SES](https://docs.aws.amazon.com/ses/)
  - [AWS End User Messaging](https://docs.aws.amazon.com/sms-voice/)
  - [API Gateway](https://docs.aws.amazon.com/apigateway/)
