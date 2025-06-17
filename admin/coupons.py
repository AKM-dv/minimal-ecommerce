from flask import Blueprint, request, jsonify
import json
import random
import string
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

# Import our modules
from models import Database, SiteConfig
from utils import (admin_required, success_response, error_response, get_request_data, 
                   ResponseFormatter)

# Create blueprint
coupons_bp = Blueprint('coupons', __name__)

# ======================= COUPONS CRUD ROUTES =======================

@coupons_bp.route('/coupons', methods=['GET'])
@admin_required
def get_coupons():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')  # active, inactive, expired, upcoming
        type_filter = request.args.get('type')  # percentage, fixed_amount, buy_x_get_y, free_shipping
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if status == 'active':
            where_conditions.append("c.is_active = 1 AND (c.valid_until IS NULL OR c.valid_until > NOW()) AND c.valid_from <= NOW()")
        elif status == 'inactive':
            where_conditions.append("c.is_active = 0")
        elif status == 'expired':
            where_conditions.append("c.valid_until IS NOT NULL AND c.valid_until <= NOW()")
        elif status == 'upcoming':
            where_conditions.append("c.valid_from > NOW()")
        
        if type_filter:
            where_conditions.append("c.type = %s")
            params.append(type_filter)
        
        if search:
            where_conditions.append("(c.code LIKE %s OR c.name LIKE %s OR c.description LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Validate sort columns
        valid_sort_columns = ['code', 'name', 'type', 'value', 'used_count', 'valid_from', 'valid_until', 'created_at']
        if sort_by not in valid_sort_columns:
            sort_by = 'created_at'
        
        sort_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM coupons c WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get coupons with usage stats
        coupons_query = f"""
        SELECT c.*, a.name as created_by_name,
               CASE 
                   WHEN c.valid_until IS NOT NULL AND c.valid_until <= NOW() THEN 'expired'
                   WHEN c.valid_from > NOW() THEN 'upcoming'
                   WHEN c.is_active = 0 THEN 'inactive'
                   ELSE 'active'
               END as computed_status,
               CASE 
                   WHEN c.usage_limit IS NOT NULL THEN ROUND((c.used_count / c.usage_limit) * 100, 2)
                   ELSE 0
               END as usage_percentage
        FROM coupons c
        LEFT JOIN admins a ON c.created_by = a.id
        WHERE {where_clause}
        ORDER BY c.{sort_by} {sort_direction}
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        coupons = Database.execute_query(coupons_query, params, fetch=True)
        
        # Add computed fields and parse JSON
        for coupon in coupons:
            # Convert Decimal to float
            coupon['value'] = float(coupon['value'])
            if coupon['max_discount_amount']:
                coupon['max_discount_amount'] = float(coupon['max_discount_amount'])
            if coupon['minimum_amount']:
                coupon['minimum_amount'] = float(coupon['minimum_amount'])
            if coupon['maximum_amount']:
                coupon['maximum_amount'] = float(coupon['maximum_amount'])
            
            # Parse buy_x_get_y_config
            if coupon.get('buy_x_get_y_config'):
                try:
                    coupon['buy_x_get_y_config'] = json.loads(coupon['buy_x_get_y_config'])
                except:
                    coupon['buy_x_get_y_config'] = {}
            
            # Add usage info
            if coupon['usage_limit']:
                coupon['remaining_uses'] = max(0, coupon['usage_limit'] - coupon['used_count'])
            else:
                coupon['remaining_uses'] = None
            
            # Add time-based status info
            now = datetime.now()
            if coupon['valid_from'] and coupon['valid_from'] > now:
                coupon['starts_in_days'] = (coupon['valid_from'] - now).days
            else:
                coupon['starts_in_days'] = 0
                
            if coupon['valid_until'] and coupon['valid_until'] > now:
                coupon['expires_in_days'] = (coupon['valid_until'] - now).days
            else:
                coupon['expires_in_days'] = 0
        
        return jsonify(ResponseFormatter.paginated(coupons, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/coupons', methods=['POST'])
@admin_required
def create_coupon():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['name', 'type', 'value']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Generate or validate coupon code
        code = data.get('code', '').strip().upper()
        if not code:
            code = generate_coupon_code(data.get('code_length', 8))
        
        # Check for duplicate code
        existing_coupon = Database.execute_query(
            "SELECT COUNT(*) as count FROM coupons WHERE code = %s",
            (code,), fetch=True
        )[0]['count']
        
        if existing_coupon > 0:
            return error_response('Coupon code already exists', 400)
        
        # Validate discount type and value
        if data['type'] not in ['percentage', 'fixed_amount', 'buy_x_get_y', 'free_shipping']:
            return error_response('Invalid discount type', 400)
        
        if data['type'] == 'percentage' and (float(data['value']) <= 0 or float(data['value']) > 100):
            return error_response('Percentage discount must be between 0 and 100', 400)
        
        if data['type'] == 'fixed_amount' and float(data['value']) <= 0:
            return error_response('Fixed amount must be greater than 0', 400)
        
        # Handle validity dates
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        
        if valid_from:
            try:
                valid_from = datetime.fromisoformat(valid_from.replace('Z', '+00:00'))
            except:
                return error_response('Invalid valid_from date format', 400)
        else:
            valid_from = datetime.now()
        
        if valid_until:
            try:
                valid_until = datetime.fromisoformat(valid_until.replace('Z', '+00:00'))
                if valid_until <= valid_from:
                    return error_response('valid_until must be after valid_from', 400)
            except:
                return error_response('Invalid valid_until date format', 400)
        
        # Get current admin
        current_admin = get_jwt_identity()
        
        # Create coupon
        coupon_query = """
        INSERT INTO coupons (code, name, description, type, value, max_discount_amount,
                           minimum_amount, maximum_amount, minimum_quantity, usage_limit,
                           usage_limit_per_customer, valid_from, valid_until, customer_eligibility,
                           product_eligibility, stackable, auto_apply, requires_shipping_address,
                           buy_x_get_y_config, is_active, priority, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        coupon_id = Database.execute_query(coupon_query, (
            code, data['name'], data.get('description', ''),
            data['type'], float(data['value']), float(data['max_discount_amount']) if data.get('max_discount_amount') else None,
            float(data.get('minimum_amount', 0)), float(data['maximum_amount']) if data.get('maximum_amount') else None,
            int(data.get('minimum_quantity', 1)), int(data['usage_limit']) if data.get('usage_limit') else None,
            int(data.get('usage_limit_per_customer', 1)), valid_from, valid_until,
            data.get('customer_eligibility', 'all'), data.get('product_eligibility', 'all'),
            bool(data.get('stackable', False)), bool(data.get('auto_apply', False)),
            bool(data.get('requires_shipping_address', False)),
            json.dumps(data.get('buy_x_get_y_config', {})) if data.get('buy_x_get_y_config') else None,
            bool(data.get('is_active', True)), int(data.get('priority', 0)),
            current_admin['id'], datetime.now()
        ))
        
        # Handle customer restrictions
        if data.get('customer_ids'):
            for customer_id in data['customer_ids']:
                Database.execute_query(
                    "INSERT INTO coupon_customers (coupon_id, customer_id) VALUES (%s, %s)",
                    (coupon_id, customer_id)
                )
        
        # Handle product restrictions
        if data.get('product_ids'):
            include_exclude = 'include' if data.get('product_eligibility') == 'specific_products' else 'exclude'
            for product_id in data['product_ids']:
                Database.execute_query(
                    "INSERT INTO coupon_products (coupon_id, product_id, include_exclude) VALUES (%s, %s, %s)",
                    (coupon_id, product_id, include_exclude)
                )
        
        # Handle category restrictions
        if data.get('category_ids'):
            include_exclude = 'include' if data.get('product_eligibility') == 'specific_categories' else 'exclude'
            for category_id in data['category_ids']:
                Database.execute_query(
                    "INSERT INTO coupon_categories (coupon_id, category_id, include_exclude) VALUES (%s, %s, %s)",
                    (coupon_id, category_id, include_exclude)
                )
        
        return success_response({
            'id': coupon_id,
            'code': code,
            'type': data['type'],
            'value': data['value']
        }, 'Coupon created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/coupons/<int:coupon_id>', methods=['GET'])
@admin_required
def get_coupon(coupon_id):
    try:
        # Get coupon details
        coupon_query = """
        SELECT c.*, a.name as created_by_name,
               CASE 
                   WHEN c.valid_until IS NOT NULL AND c.valid_until <= NOW() THEN 'expired'
                   WHEN c.valid_from > NOW() THEN 'upcoming'
                   WHEN c.is_active = 0 THEN 'inactive'
                   ELSE 'active'
               END as computed_status
        FROM coupons c
        LEFT JOIN admins a ON c.created_by = a.id
        WHERE c.id = %s
        """
        
        coupon_result = Database.execute_query(coupon_query, (coupon_id,), fetch=True)
        
        if not coupon_result:
            return error_response('Coupon not found', 404)
        
        coupon = coupon_result[0]
        
        # Convert Decimal to float
        coupon['value'] = float(coupon['value'])
        if coupon['max_discount_amount']:
            coupon['max_discount_amount'] = float(coupon['max_discount_amount'])
        if coupon['minimum_amount']:
            coupon['minimum_amount'] = float(coupon['minimum_amount'])
        if coupon['maximum_amount']:
            coupon['maximum_amount'] = float(coupon['maximum_amount'])
        
        # Parse JSON fields
        if coupon.get('buy_x_get_y_config'):
            try:
                coupon['buy_x_get_y_config'] = json.loads(coupon['buy_x_get_y_config'])
            except:
                coupon['buy_x_get_y_config'] = {}
        
        # Get usage statistics
        usage_stats = Database.execute_query(
            """SELECT 
                   COUNT(*) as total_uses,
                   COUNT(DISTINCT customer_id) as unique_customers,
                   SUM(discount_amount) as total_discount_given,
                   AVG(discount_amount) as avg_discount_amount,
                   MAX(usage_date) as last_used_date
               FROM coupon_usage WHERE coupon_id = %s""",
            (coupon_id,), fetch=True
        )[0]
        
        # Convert decimals
        if usage_stats['total_discount_given']:
            usage_stats['total_discount_given'] = float(usage_stats['total_discount_given'])
        if usage_stats['avg_discount_amount']:
            usage_stats['avg_discount_amount'] = float(usage_stats['avg_discount_amount'])
        
        coupon['usage_statistics'] = usage_stats
        
        return success_response(coupon)
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/coupons/<int:coupon_id>', methods=['PUT'])
@admin_required
def update_coupon(coupon_id):
    try:
        data = get_request_data()
        
        # Check if coupon exists
        existing_coupon = Database.execute_query(
            "SELECT * FROM coupons WHERE id = %s", (coupon_id,), fetch=True
        )
        if not existing_coupon:
            return error_response('Coupon not found', 404)
        
        # Build update query
        update_fields = []
        params = []
        
        # Handle basic fields
        basic_fields = {
            'name': str, 'description': str, 'type': str, 'value': float,
            'max_discount_amount': float, 'minimum_amount': float, 'maximum_amount': float,
            'minimum_quantity': int, 'usage_limit': int, 'usage_limit_per_customer': int,
            'customer_eligibility': str, 'product_eligibility': str, 'stackable': bool,
            'auto_apply': bool, 'requires_shipping_address': bool, 'is_active': bool,
            'priority': int
        }
        
        for field, field_type in basic_fields.items():
            if field in data:
                update_fields.append(f"{field} = %s")
                if field_type == bool:
                    params.append(bool(data[field]))
                elif field_type == float:
                    params.append(float(data[field]) if data[field] is not None else None)
                elif field_type == int:
                    params.append(int(data[field]) if data[field] is not None else None)
                else:
                    params.append(data[field])
        
        # Handle code update (with duplicate check)
        if 'code' in data:
            new_code = data['code'].strip().upper()
            duplicate_count = Database.execute_query(
                "SELECT COUNT(*) as count FROM coupons WHERE code = %s AND id != %s",
                (new_code, coupon_id), fetch=True
            )[0]['count']
            
            if duplicate_count > 0:
                return error_response('Coupon code already exists', 400)
            
            update_fields.append("code = %s")
            params.append(new_code)
        
        if not update_fields:
            return error_response('No fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(coupon_id)
        
        query = f"UPDATE coupons SET {', '.join(update_fields)} WHERE id = %s"
        Database.execute_query(query, params)
        
        return success_response(message='Coupon updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/coupons/<int:coupon_id>', methods=['DELETE'])
@admin_required
def delete_coupon(coupon_id):
    try:
        # Check if coupon exists
        existing_coupon = Database.execute_query(
            "SELECT * FROM coupons WHERE id = %s", (coupon_id,), fetch=True
        )
        if not existing_coupon:
            return error_response('Coupon not found', 404)
        
        # Check if coupon has been used
        usage_count = Database.execute_query(
            "SELECT COUNT(*) as count FROM coupon_usage WHERE coupon_id = %s",
            (coupon_id,), fetch=True
        )[0]['count']
        
        if usage_count > 0:
            # Soft delete - deactivate instead of delete
            Database.execute_query(
                "UPDATE coupons SET is_active = 0, updated_at = %s WHERE id = %s",
                (datetime.now(), coupon_id)
            )
            message = 'Coupon deactivated (has usage history)'
        else:
            # Hard delete if no usage
            Database.execute_query("DELETE FROM coupon_customers WHERE coupon_id = %s", (coupon_id,))
            Database.execute_query("DELETE FROM coupon_products WHERE coupon_id = %s", (coupon_id,))
            Database.execute_query("DELETE FROM coupon_categories WHERE coupon_id = %s", (coupon_id,))
            Database.execute_query("DELETE FROM coupons WHERE id = %s", (coupon_id,))
            message = 'Coupon deleted successfully'
        
        return success_response(message=message)
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= COUPON VALIDATION =======================

@coupons_bp.route('/coupons/validate', methods=['POST'])
@admin_required
def validate_coupon():
    """Admin endpoint to validate coupon for testing"""
    try:
        data = get_request_data()
        code = data.get('code', '').strip().upper()
        customer_id = data.get('customer_id')
        cart_items = data.get('cart_items', [])
        
        if not code:
            return error_response('Coupon code is required', 400)
        
        validation_result = validate_coupon_code(code, customer_id, cart_items)
        
        return success_response(validation_result)
        
    except Exception as e:
        return error_response(str(e), 500)

def validate_coupon_code(code, customer_id=None, cart_items=None):
    """Validate coupon code and calculate discount"""
    try:
        # Get coupon details
        coupon = Database.execute_query(
            """SELECT * FROM coupons WHERE code = %s AND is_active = 1 
               AND valid_from <= NOW() AND (valid_until IS NULL OR valid_until > NOW())""",
            (code,), fetch=True
        )
        
        if not coupon:
            return {
                'valid': False,
                'error': 'Invalid or expired coupon code',
                'error_code': 'INVALID_COUPON'
            }
        
        coupon = coupon[0]
        
        # Check usage limit
        if coupon['usage_limit'] and coupon['used_count'] >= coupon['usage_limit']:
            return {
                'valid': False,
                'error': 'Coupon usage limit exceeded',
                'error_code': 'USAGE_LIMIT_EXCEEDED'
            }
        
        # Calculate discount if cart items provided
        discount_info = None
        if cart_items:
            cart_total = sum(float(item['price']) * int(item['quantity']) for item in cart_items)
            if cart_total < float(coupon['minimum_amount']):
                return {
                    'valid': False,
                    'error': f'Minimum order amount of ₹{coupon["minimum_amount"]} required',
                    'error_code': 'MINIMUM_AMOUNT_NOT_MET'
                }
        
        return {
            'valid': True,
            'coupon': {
                'id': coupon['id'],
                'code': coupon['code'],
                'name': coupon['name'],
                'type': coupon['type'],
                'value': float(coupon['value']),
                'description': coupon['description']
            }
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': 'Error validating coupon',
            'error_code': 'VALIDATION_ERROR'
        }

# ======================= CODE GENERATION =======================

@coupons_bp.route('/coupons/generate-code', methods=['POST'])
@admin_required
def generate_code_endpoint():
    try:
        data = get_request_data()
        length = int(data.get('length', 8))
        prefix = data.get('prefix', '').upper()
        suffix = data.get('suffix', '').upper()
        type_code = data.get('type', 'random')  # random, readable, numeric
        
        if length < 4 or length > 20:
            return error_response('Code length must be between 4 and 20', 400)
        
        # Generate multiple code options
        codes = []
        for _ in range(5):
            code = generate_coupon_code(length, prefix, suffix, type_code)
            # Check if code already exists
            existing = Database.execute_query(
                "SELECT COUNT(*) as count FROM coupons WHERE code = %s",
                (code,), fetch=True
            )[0]['count']
            
            if existing == 0:
                codes.append(code)
        
        return success_response({
            'generated_codes': codes,
            'length': length,
            'prefix': prefix,
            'suffix': suffix,
            'type': type_code
        })
        
    except Exception as e:
        return error_response(str(e), 500)

def generate_coupon_code(length=8, prefix='', suffix='', code_type='random'):
    """Generate unique coupon code"""
    try:
        available_length = length - len(prefix) - len(suffix)
        if available_length < 3:
            available_length = 3
        
        if code_type == 'numeric':
            code_part = ''.join(random.choices(string.digits, k=available_length))
        elif code_type == 'readable':
            # Exclude confusing characters
            chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
            code_part = ''.join(random.choices(chars, k=available_length))
        else:  # random
            code_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=available_length))
        
        return f"{prefix}{code_part}{suffix}"
        
    except Exception as e:
        return f"CODE{random.randint(1000, 9999)}"