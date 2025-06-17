import os
import uuid
from datetime import datetime
from PIL import Image
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from functools import wraps
import re

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            verify_jwt_in_request()
            current_user = get_jwt_identity()
            if not current_user or current_user.get('role') != 'admin':
                return jsonify({'error': 'Admin access required'}), 403
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': 'Invalid token'}), 401
    return decorated_function

def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            verify_jwt_in_request()
            current_user = get_jwt_identity()
            if not current_user:
                return jsonify({'error': 'Authentication required'}), 401
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': 'Invalid token'}), 401
    return decorated_function

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    # At least 8 characters, 1 uppercase, 1 lowercase, 1 number
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    return True

def generate_sku():
    return f"SKU{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"

def allowed_file(filename, allowed_extensions={'png', 'jpg', 'jpeg', 'gif', 'webp'}):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_image(file, folder='products', max_size=(800, 800)):
    if not file or not allowed_file(file.filename):
        return None
    
    # Create upload directory if it doesn't exist
    upload_dir = os.path.join('uploads', folder)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    filename = f"{uuid.uuid4()}.{file.filename.rsplit('.', 1)[1].lower()}"
    filepath = os.path.join(upload_dir, filename)
    
    # Save and resize image
    try:
        image = Image.open(file.stream)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        image.save(filepath, optimize=True, quality=85)
        return f"{folder}/{filename}"
    except Exception as e:
        return None

def paginate_results(query_results, page=1, per_page=20):
    total = len(query_results)
    start = (page - 1) * per_page
    end = start + per_page
    
    return {
        'items': query_results[start:end],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    }

def success_response(data=None, message="Success"):
    response = {'success': True, 'message': message}
    if data is not None:
        response['data'] = data
    return jsonify(response)

def error_response(message="Error", code=400):
    return jsonify({'success': False, 'error': message}), code

def get_request_data():
    """Get JSON data from request"""
    try:
        return request.get_json() or {}
    except:
        return {}

def calculate_discount_price(original_price, discount_percentage):
    """Calculate discounted price"""
    if discount_percentage and 0 < discount_percentage < 100:
        return original_price * (1 - discount_percentage / 100)
    return original_price

def format_currency(amount, currency_symbol="₹"):
    """Format currency display"""
    return f"{currency_symbol}{amount:,.2f}"

class ResponseFormatter:
    @staticmethod
    def success(data=None, message="Success"):
        response = {'success': True, 'message': message}
        if data is not None:
            response['data'] = data
        return response
    
    @staticmethod
    def error(message="Error"):
        return {'success': False, 'error': message}
    
    @staticmethod
    def paginated(items, total, page, per_page):
        return {
            'success': True,
            'data': {
                'items': items,
                'pagination': {
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'pages': (total + per_page - 1) // per_page
                }
            }
        }