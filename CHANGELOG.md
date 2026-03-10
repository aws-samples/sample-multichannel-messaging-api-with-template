# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-02

### Added
- REST API Gateway with JWT authentication for secure message submission
- SQS-based message queuing with dead letter queue and automatic retries
- Lambda message processor for sending email (Amazon SES) and SMS (AWS End User Messaging)
- DynamoDB-backed template management with variable substitution
- Inline message body support as an alternative to stored templates
- Multi-channel delivery (email and SMS) in a single API request
- Per-message Configuration Set override for SES and SMS tracking
- Optional deployment-level SES and SMS Configuration Set parameters
- KMS customer-managed key for encryption across all resources
- CloudWatch alarm with SNS notifications for DLQ monitoring
- JWT token generation script (`generate_jwt.py`) for testing
- `customer_id` optional JWT claim forwarded as context to downstream services
- LICENSE, CODE_OF_CONDUCT, and CONTRIBUTING documentation
