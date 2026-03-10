import json
import boto3
import os
from botocore.exceptions import ClientError

ses_client = boto3.client('sesv2')
sms_client = boto3.client('pinpoint-sms-voice-v2')
dynamodb = boto3.resource('dynamodb')

TEMPLATES_TABLE_NAME = os.environ.get('TEMPLATES_TABLE_NAME', 'MessageTemplates')
SES_CONFIGURATION_SET = os.environ.get('SES_CONFIGURATION_SET', '')
SMS_CONFIGURATION_SET = os.environ.get('SMS_CONFIGURATION_SET', '')
templates_table = dynamodb.Table(TEMPLATES_TABLE_NAME)

def lambda_handler(event, context):
    """
    Process messages from SQS queue and send via email or SMS.
    Simplified version with flat JSON structure.
    """
    failed_messages = []
    
    for record in event['Records']:
        message_id = record['messageId']
        
        try:
            # Parse the message body - now just one level of JSON!
            message = json.loads(record['body'])
            
            # Debug: Log the parsed message
            print(f"Parsed message: {json.dumps(message)}")
            
            # Process email if configured
            if 'EmailMessage' in message:
                send_emails(message)
            
            # Process SMS if configured
            if 'SMSMessage' in message:
                send_sms_messages(message)
                
        except Exception as e:
            print(f"Error processing message {message_id}: {str(e)}")
            failed_messages.append({"itemIdentifier": message_id})
    
    return {"batchItemFailures": failed_messages}


def send_emails(message):
    """Send emails via Amazon SES"""
    email_config = message['EmailMessage']
    addresses = message.get('Addresses', {})
    
    from_address = email_config.get('FromAddress')
    reply_to = email_config.get('ReplyToAddresses', [from_address])
    global_substitutions = email_config.get('Substitutions', {})
    template_name = email_config.get('TemplateName')
    
    for address, config in addresses.items():
        if config.get('ChannelType') == 'EMAIL':
            try:
                # Merge global and address-specific substitutions
                addr_substitutions = config.get('Substitutions', {})
                merged_subs = {**global_substitutions, **addr_substitutions}
                
                # Get email content - priority: inline > template > default
                if 'MessageBody' in email_config:
                    # Option 1: Inline message body in payload
                    body_html = replace_variables(email_config['MessageBody'], merged_subs)
                    subject = email_config.get('Subject', 'Notification')
                elif template_name:
                    # Option 2: Fetch from DynamoDB template
                    body_html, subject = get_email_template_from_dynamodb(template_name, merged_subs)
                else:
                    # Option 3: Use default hardcoded template
                    subject = email_config.get('Subject', 'Account Alert')
                    body_html = build_email_body(merged_subs)
                
                # Build email parameters
                email_params = {
                    'FromEmailAddress': from_address,
                    'Destination': {'ToAddresses': [address]},
                    'ReplyToAddresses': reply_to,
                    'Content': {
                        'Simple': {
                            'Subject': {'Data': subject},
                            'Body': {'Html': {'Data': body_html}}
                        }
                    }
                }
                
                # Add configuration set - priority: message-level > environment variable
                config_set = email_config.get('ConfigurationSetName', SES_CONFIGURATION_SET)
                if config_set:
                    email_params['ConfigurationSetName'] = config_set
                
                response = ses_client.send_email(**email_params)
                print(f"Email sent to {address}: {response['MessageId']}")
                
            except ClientError as e:
                print(f"Error sending email to {address}: {e.response['Error']['Message']}")
                raise


def send_sms_messages(message):
    """Send SMS messages via End User Messaging"""
    sms_config = message['SMSMessage']
    addresses = message.get('Addresses', {})
    
    message_type = sms_config.get('MessageType', 'TRANSACTIONAL')
    origination_number = sms_config.get('OriginationNumber')
    template_name = sms_config.get('TemplateName')
    
    for address, config in addresses.items():
        if config.get('ChannelType') == 'SMS':
            try:
                # Clean up phone number - remove spaces and ensure it starts with +
                clean_address = address.strip()
                if not clean_address.startswith('+'):
                    clean_address = '+' + clean_address
                
                # Get substitutions
                substitutions = config.get('Substitutions', {})
                
                # Get SMS content - priority: inline > template > default
                if 'MessageBody' in sms_config:
                    # Option 1: Inline message body in payload
                    message_body = replace_variables(sms_config['MessageBody'], substitutions)
                elif template_name:
                    # Option 2: Fetch from DynamoDB template
                    message_body = get_sms_template_from_dynamodb(template_name, substitutions)
                else:
                    # Option 3: Use default hardcoded template
                    message_body = build_sms_body(substitutions)
                
                # Build SMS parameters
                sms_params = {
                    'DestinationPhoneNumber': clean_address,
                    'OriginationIdentity': origination_number,
                    'MessageBody': message_body,
                    'MessageType': message_type
                }
                
                # Add configuration set - priority: message-level > environment variable
                config_set = sms_config.get('ConfigurationSetName', SMS_CONFIGURATION_SET)
                if config_set:
                    sms_params['ConfigurationSetName'] = config_set
                
                response = sms_client.send_text_message(**sms_params)
                print(f"SMS sent to {clean_address}: {response['MessageId']}")
                
            except ClientError as e:
                print(f"Error sending SMS to {address}: {e.response['Error']['Message']}")
                raise


def get_email_template_from_dynamodb(template_name, substitutions):
    """Retrieve and render email template from DynamoDB"""
    try:
        response = templates_table.get_item(Key={'TemplateName': template_name})
        
        if 'Item' not in response:
            print(f"Email template {template_name} not found, using default")
            return build_email_body(substitutions), "Account Alert"
        
        template_body = response['Item']['MessageBody']
        subject = response['Item'].get('Subject', 'Notification')
        
        # Replace {variable} placeholders with actual values
        rendered_body = replace_variables(template_body, substitutions)
        rendered_subject = replace_variables(subject, substitutions)
        
        return rendered_body, rendered_subject
        
    except ClientError as e:
        print(f"Error reading email template from DynamoDB: {e.response['Error']['Message']}")
        return build_email_body(substitutions), "Account Alert"


def get_sms_template_from_dynamodb(template_name, substitutions):
    """Retrieve and render SMS template from DynamoDB"""
    try:
        response = templates_table.get_item(Key={'TemplateName': template_name})
        
        if 'Item' not in response:
            print(f"SMS template {template_name} not found, using default")
            return build_sms_body(substitutions)
        
        template_body = response['Item']['MessageBody']
        
        # Replace {variable} placeholders with actual values
        return replace_variables(template_body, substitutions)
        
    except ClientError as e:
        print(f"Error reading SMS template from DynamoDB: {e.response['Error']['Message']}")
        return build_sms_body(substitutions)


def replace_variables(template, substitutions):
    """Replace {variable} placeholders with actual values from substitutions"""
    result = template
    for key, value in substitutions.items():
        # Handle both string and list values
        if isinstance(value, list):
            value = value[0] if value else ''
        result = result.replace(f'{{{key}}}', str(value))
    return result


def build_email_body(substitutions):
    """Build HTML email body with substitutions"""
    # Extract values (handle both dict and list formats)
    def get_value(key, default):
        val = substitutions.get(key, default)
        return val[0] if isinstance(val, list) else val
    
    product = get_value('productName', 'Account')
    membership = get_value('membershipNumber', '****')
    threshold = get_value('threshold', '0.00')
    
    return f"""
    <html>
    <body>
        <h2>Account Alert</h2>
        <p>Your {product} account ending in {membership} has a low balance of ${threshold}.</p>
        <p>Please take action to avoid any service interruptions.</p>
    </body>
    </html>
    """


def build_sms_body(substitutions):
    """Build SMS message body with substitutions"""
    def get_value(key, default):
        val = substitutions.get(key, default)
        return val[0] if isinstance(val, list) else val
    
    product = get_value('productName', 'Account')
    membership = get_value('membershipNumber', '****')
    threshold = get_value('threshold', '0.00')
    
    return f"Alert: Your {product} account ending in {membership} has a low balance of ${threshold}"
