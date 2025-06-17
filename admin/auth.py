from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity
from datetime import timedelta

# Import our modules
from models import Admin
from utils import admin_required, validate_email, success_response, error_response, get_request_data

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# ======================= AUTHENTICATION ROUTES =======================

@auth_bp.route('/auth/login', methods=['POST'])
def admin_login():
    try:
        data = get_request_data()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return error_response('Email and password required', 400)
        
        if not validate_email(email):
            return error_response('Invalid email format', 400)
        
        admin = Admin.get_admin_by_email(email)
        if not admin or not Admin.verify_password(password, admin['password']):
            return error_response('Invalid credentials', 401)
        
        # Create JWT token
        token_data = {
            'id': admin['id'],
            'email': admin['email'],
            'name': admin['name'],
            'role': admin['role']
        }
        access_token = create_access_token(identity=token_data, expires_delta=timedelta(hours=8))
        
        return success_response({
            'token': access_token,
            'admin': {
                'id': admin['id'],
                'email': admin['email'],
                'name': admin['name'],
                'role': admin['role']
            }
        }, 'Login successful')
        
    except Exception as e:
        return error_response(f'Login failed: {str(e)}', 500)

@auth_bp.route('/auth/profile', methods=['GET'])
@admin_required
def admin_profile():
    try:
        current_admin = get_jwt_identity()
        return success_response(current_admin, 'Profile retrieved successfully')
    except Exception as e:
        return error_response(str(e), 500)

@auth_bp.route('/auth/logout', methods=['POST'])
@admin_required
def admin_logout():
    try:
        # In JWT, logout is handled client-side by removing token
        return success_response(message='Logout successful')
    except Exception as e:
        return error_response(str(e), 500)

@auth_bp.route('/health', methods=['GET'])
def health_check():
    return success_response({'status': 'Admin authentication running'}, 'Health check passed')