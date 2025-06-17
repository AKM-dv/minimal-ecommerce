from flask import Blueprint, request, jsonify
import json
from datetime import datetime, timedelta
import hashlib
import hmac
import base64
from cryptography.fernet import Fernet
import requests
import uuid

# Import our modules
from models import Database, SiteConfig
from utils import (admin_required, success_response, error_response, get_request_data, ResponseFormatter)

# Create blueprint
integrations_bp = Blueprint('integrations', __name__)

# ======================= API INTEGRATIONS MANAGEMENT =======================

@integrations_bp.route('/integrations', methods=['GET'])
@admin_required
def get_all_integrations():
    try:
        # Get all integration configurations
        integrations_query = """
        SELECT * FROM api_integrations 
        ORDER BY service_name, environment
        """
        integrations = Database.execute_query(integrations_query, fetch=True)
        
        # Parse JSON configurations and mask sensitive data
        for integration in integrations:
            if integration['configuration']:
                try:
                    config = json.loads(integration['configuration'])
                    # Mask sensitive keys
                    for key in config:
                        if any(sensitive in key.lower() for sensitive in ['key', 'secret', 'token', 'password']):
                            if config[key]:
                                config[key] = '***' + config[key][-4:] if len(config[key]) > 4 else '****'
                    integration['configuration'] = config
                except:
                    integration['configuration'] = {}
        
        # Group by service type
        grouped_integrations = {}
        for integration in integrations:
            service_type = integration['service_type']
            if service_type not in grouped_integrations:
                grouped_integrations[service_type] = []
            grouped_integrations[service_type].append(integration)
        
        return success_response(grouped_integrations)
        
    except Exception as e:
        return error_response(str(e), 500)

@integrations_bp.route('/integrations/<service_type>', methods=['GET'])
@admin_required
def get_integration_by_type(service_type):
    try:
        integration_query = """
        SELECT * FROM api_integrations 
        WHERE service_type = %s 
        ORDER BY environment
        """
        integrations = Database.execute_query(integration_query, (service_type,), fetch=True)
        
        # Decrypt and parse configurations
        for integration in integrations:
            if integration['configuration']:
                try:
                    config = json.loads(integration['configuration'])
                    # Decrypt sensitive fields
                    config = decrypt_configuration(config)
                    integration['configuration'] = config
                except:
                    integration['configuration'] = {}
        
        return success_response(integrations)
        
    except Exception as e:
        return error_response(str(e), 500)

@integrations_bp.route('/integrations', methods=['POST'])
@admin_required
def create_integration():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['service_name', 'service_type', 'environment']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Encrypt sensitive configuration data
        config = data.get('configuration', {})
        encrypted_config = encrypt_configuration(config)
        
        # Create integration
        integration_query = """
        INSERT INTO api_integrations (service_name, service_type, environment, configuration,
                                    is_active, is_test_mode, webhook_url, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        integration_id = Database.execute_query(integration_query, (
            data['service_name'], data['service_type'], data['environment'],
            json.dumps(encrypted_config), bool(data.get('is_active', True)),
            bool(data.get('is_test_mode', True)), data.get('webhook_url'), datetime.now()
        ))
        
        # Log the creation
        log_api_activity(
            integration_id=integration_id,
            activity_type='integration_created',
            description=f'{data["service_name"]} integration created'
        )
        
        return success_response({'id': integration_id}, 'Integration created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= UTILITY FUNCTIONS =======================

def get_encryption_key():
    """Get or create encryption key for sensitive data"""
    encryption_key = SiteConfig.get_config('encryption_key')
    if not encryption_key:
        key = Fernet.generate_key()
        SiteConfig.set_config('encryption_key', key.decode())
        return key
    return encryption_key.encode()

def encrypt_configuration(config):
    """Encrypt sensitive configuration data"""
    try:
        fernet = Fernet(get_encryption_key())
        encrypted_config = {}
        
        for key, value in config.items():
            if any(sensitive in key.lower() for sensitive in ['key', 'secret', 'token', 'password']):
                if value:
                    encrypted_config[key] = fernet.encrypt(str(value).encode()).decode()
                else:
                    encrypted_config[key] = value
            else:
                encrypted_config[key] = value
        
        return encrypted_config
    except Exception as e:
        return config

def decrypt_configuration(config):
    """Decrypt sensitive configuration data"""
    try:
        fernet = Fernet(get_encryption_key())
        decrypted_config = {}
        
        for key, value in config.items():
            if any(sensitive in key.lower() for sensitive in ['key', 'secret', 'token', 'password']):
                if value and isinstance(value, str):
                    try:
                        decrypted_config[key] = fernet.decrypt(value.encode()).decode()
                    except:
                        decrypted_config[key] = value
                else:
                    decrypted_config[key] = value
            else:
                decrypted_config[key] = value
        
        return decrypted_config
    except Exception as e:
        return config

def get_integration_config(service_type, service_name):
    """Get integration configuration"""
    try:
        integration = Database.execute_query(
            "SELECT * FROM api_integrations WHERE service_type = %s AND service_name = %s AND is_active = 1",
            (service_type, service_name), fetch=True
        )
        
        if not integration:
            return None
        
        config = json.loads(integration[0]['configuration'])
        return {
            'id': integration[0]['id'],
            'configuration': decrypt_configuration(config),
            'is_active': integration[0]['is_active'],
            'is_test_mode': integration[0]['is_test_mode']
        }
    except:
        return None

def update_or_create_integration(service_name, service_type, configuration, environment='live', is_active=True, webhook_url=None):
    """Update existing integration or create new one"""
    try:
        # Check if integration exists
        existing = Database.execute_query(
            "SELECT id FROM api_integrations WHERE service_name = %s AND service_type = %s AND environment = %s",
            (service_name, service_type, environment), fetch=True
        )
        
        encrypted_config = encrypt_configuration(configuration)
        
        if existing:
            # Update existing
            integration_id = existing[0]['id']
            Database.execute_query(
                "UPDATE api_integrations SET configuration = %s, is_active = %s, webhook_url = %s, updated_at = %s WHERE id = %s",
                (json.dumps(encrypted_config), is_active, webhook_url, datetime.now(), integration_id)
            )
        else:
            # Create new
            integration_id = Database.execute_query(
                "INSERT INTO api_integrations (service_name, service_type, environment, configuration, is_active, webhook_url, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (service_name, service_type, environment, json.dumps(encrypted_config), is_active, webhook_url, datetime.now())
            )
        
        return integration_id
    except Exception as e:
        raise e

def log_api_activity(integration_id=None, activity_type='general', description='', request_data=None, response_data=None, status_code=None, response_time=None):
    """Log API activity"""
    try:
        Database.execute_query(
            "INSERT INTO api_logs (integration_id, activity_type, description, request_data, response_data, status_code, response_time, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (integration_id, activity_type, description, 
             json.dumps(request_data) if request_data else None,
             json.dumps(response_data) if response_data else None,
             status_code, response_time, datetime.now())
        )
    except:
        pass  # Don't fail main operation if logging fails

# ======================= PAYMENT GATEWAY INTEGRATIONS =======================

@integrations_bp.route('/integrations/payment/razorpay', methods=['GET'])
@admin_required
def get_razorpay_config():
    try:
        config = get_integration_config('payment', 'razorpay')
        return success_response(config)
    except Exception as e:
        return error_response(str(e), 500)

@integrations_bp.route('/integrations/payment/razorpay', methods=['PUT'])
@admin_required
def update_razorpay_config():
    try:
        data = get_request_data()
        
        razorpay_config = {
            'key_id': data.get('key_id'),
            'key_secret': data.get('key_secret'),
            'webhook_secret': data.get('webhook_secret'),
            'currency': data.get('currency', 'INR'),
            'auto_capture': bool(data.get('auto_capture', True)),
            'payment_methods': data.get('payment_methods', ['card', 'netbanking', 'wallet', 'upi'])
        }
        
        integration_id = update_or_create_integration(
            service_name='razorpay',
            service_type='payment',
            configuration=razorpay_config,
            environment=data.get('environment', 'test'),
            is_active=bool(data.get('is_active', True)),
            webhook_url=data.get('webhook_url')
        )
        
        return success_response({'integration_id': integration_id}, 'Razorpay configuration updated')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= WEBHOOK HANDLING =======================

@integrations_bp.route('/webhooks/<service_name>', methods=['POST'])
def handle_webhook(service_name):
    try:
        # Get integration config for webhook verification
        integration = Database.execute_query(
            "SELECT * FROM api_integrations WHERE service_name = %s AND is_active = 1",
            (service_name,), fetch=True
        )
        
        if not integration:
            return error_response('Integration not found', 404)
        
        config = json.loads(integration[0]['configuration'])
        config = decrypt_configuration(config)
        
        # Log webhook received
        log_api_activity(
            integration_id=integration[0]['id'],
            activity_type='webhook_received',
            description=f'Webhook received from {service_name}',
            request_data=request.get_json()
        )
        
        return success_response(message='Webhook processed successfully')
        
    except Exception as e:
        log_api_activity(
            activity_type='webhook_error',
            description=f'Webhook processing failed for {service_name}: {str(e)}',
            request_data=request.get_json()
        )
        return error_response(str(e), 500)

# ======================= API MONITORING =======================

@integrations_bp.route('/integrations/logs', methods=['GET'])
@admin_required
def get_api_logs():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        integration_id = request.args.get('integration_id')
        activity_type = request.args.get('activity_type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if integration_id:
            where_conditions.append("integration_id = %s")
            params.append(integration_id)
        
        if activity_type:
            where_conditions.append("activity_type = %s")
            params.append(activity_type)
        
        if start_date:
            where_conditions.append("DATE(created_at) >= %s")
            params.append(start_date)
        
        if end_date:
            where_conditions.append("DATE(created_at) <= %s")
            params.append(end_date)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM api_logs WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get logs
        logs_query = f"""
        SELECT al.*, ai.service_name, ai.service_type
        FROM api_logs al
        LEFT JOIN api_integrations ai ON al.integration_id = ai.id
        WHERE {where_clause}
        ORDER BY al.created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        logs = Database.execute_query(logs_query, params, fetch=True)
        
        # Parse JSON fields
        for log in logs:
            if log['request_data']:
                try:
                    log['request_data'] = json.loads(log['request_data'])
                except:
                    log['request_data'] = {}
            
            if log['response_data']:
                try:
                    log['response_data'] = json.loads(log['response_data'])
                except:
                    log['response_data'] = {}
        
        return jsonify(ResponseFormatter.paginated(logs, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@integrations_bp.route('/integrations/health-check', methods=['GET'])
@admin_required
def check_integration_health():
    try:
        health_status = {
            'razorpay': {'status': 'not_configured'},
            'phonepe': {'status': 'not_configured'},
            'shiprocket': {'status': 'not_configured'}
        }
        
        return success_response(health_status)
        
    except Exception as e:
        return error_response(str(e), 500)