if coupon['customer_eligibility'] == 'new_customers':
            # Check if customer has made any orders
            order_count = Database.execute_query(
                "SELECT COUNT(*) as count FROM orders WHERE customer_id = %s AND payment_status = 'paid'",
                (customer_id,), fetch=True
            )[0]['count']
            
            if order_count > 0:
                return {'eligible': False, 'reason': 'This coupon is only for new customers'}
        
        elif coupon['customer_eligibility'] == 'existing_customers':
            # Check if customer has made orders
            order_count = Database.execute_query(
                "SELECT COUNT(*) as count FROM orders WHERE customer_id = %s AND payment_status = 'paid'",
                (customer_id,), fetch=True
            )[0]['count']
            
            if order_count == 0:
                return {'eligible': False, 'reason': 'This coupon is only for existing customers'}
        
        elif coupon['customer_eligibility'] == 'specific_customers':
            # Check if customer is in allowed list
            allowed = Database.execute_query(
                "SELECT COUNT(*) as count FROM coupon_customers WHERE coupon_id = %s AND customer_id = %s",
                (coupon['id'], customer_id), fetch=True
            )[0]['count']
            
            if allowed == 0:
                return {'eligible': False, 'reason': 'You are not eligible for this coupon'}
        
        elif coupon['customer_eligibility'] == 'customer_groups':
            # Check if customer is in any allowed groups
            group_membership = Database.execute_query(
                """SELECT COUNT(*) as count FROM customer_group_members cgm
                   JOIN coupon_customer_groups ccg ON cgm.group_id = ccg.group_id
                   WHERE ccg.coupon_id = %s AND cgm.customer_id = %s""",
                (coupon['id'], customer_id), fetch=True
            )[0]['count']
            
            if group_membership == 0:
                return {'eligible': False, 'reason': 'You are not in an eligible customer group'}
        
        return {'eligible': True}
        
    except Exception as e:
        return {'eligible': False, 'reason': 'Error checking eligibility'}

def calculate_coupon_discount(coupon, cart_items, customer_id=None):
    """Calculate discount amount for given cart items"""
    try:
        if coupon['type'] == 'free_shipping':
            return {
                'discount_amount': 0,
                'free_shipping': True,
                'applicable_items': len(cart_items)
            }
        
        # Filter applicable items based on product/category restrictions
        applicable_items = []
        
        if coupon['product_eligibility'] == 'all':
            applicable_items = cart_items
        else:
            # Get product restrictions
            if coupon['product_eligibility'] in ['specific_products', 'exclude_products']:
                restricted_products = Database.execute_query(
                    "SELECT product_id, include_exclude FROM coupon_products WHERE coupon_id = %s",
                    (coupon['id'],), fetch=True
                )
                restricted_product_ids = [r['product_id'] for r in restricted_products]
                include_exclude = restricted_products[0]['include_exclude'] if restricted_products else 'include'
                
                for item in cart_items:
                    if include_exclude == 'include' and item['product_id'] in restricted_product_ids:
                        applicable_items.append(item)
                    elif include_exclude == 'exclude' and item['product_id'] not in restricted_product_ids:
                        applicable_items.append(item)
            
            # Get category restrictions
            elif coupon['product_eligibility'] in ['specific_categories', 'exclude_categories']:
                restricted_categories = Database.execute_query(
                    """SELECT cc.category_id, cc.include_exclude, cc.include_subcategories
                       FROM coupon_categories cc WHERE cc.coupon_id = %s""",
                    (coupon['id'],), fetch=True
                )
                
                for item in cart_items:
                    # Get product's category
                    product_category = Database.execute_query(
                        "SELECT category_id FROM products WHERE id = %s",
                        (item['product_id'],), fetch=True
                    )
                    
                    if product_category:
                        product_category_id = product_category[0]['category_id']
                        
                        for restriction in restricted_categories:
                            include_exclude = restriction['include_exclude']
                            
                            if include_exclude == 'include' and product_category_id == restriction['category_id']:
                                applicable_items.append(item)
                                break
                            elif include_exclude == 'exclude' and product_category_id != restriction['category_id']:
                                applicable_items.append(item)
                                break
        
        if not applicable_items:
            return {
                'discount_amount': 0,
                'applicable_items': 0,
                'reason': 'No applicable items in cart'
            }
        
        # Calculate discount based on type
        applicable_total = sum(float(item['price']) * int(item['quantity']) for item in applicable_items)
        discount_amount = 0
        
        if coupon['type'] == 'percentage':
            discount_amount = applicable_total * (float(coupon['value']) / 100)
            if coupon['max_discount_amount']:
                discount_amount = min(discount_amount, float(coupon['max_discount_amount']))
        
        elif coupon['type'] == 'fixed_amount':
            discount_amount = min(float(coupon['value']), applicable_total)
        
        elif coupon['type'] == 'buy_x_get_y':
            # Implementation for buy X get Y offers
            if coupon['buy_x_get_y_config']:
                try:
                    config = json.loads(coupon['buy_x_get_y_config'])
                    buy_qty = config.get('buy_quantity', 1)
                    get_qty = config.get('get_quantity', 1) 
                    get_discount = config.get('get_discount', 100)  # Percentage discount on free items
                    
                    total_qty = sum(int(item['quantity']) for item in applicable_items)
                    free_items = (total_qty // buy_qty) * get_qty
                    
                    if free_items > 0:
                        # Apply discount to cheapest items
                        sorted_items = sorted(applicable_items, key=lambda x: float(x['price']))
                        remaining_free = free_items
                        
                        for item in sorted_items:
                            if remaining_free <= 0:
                                break
                            
                            item_free_qty = min(remaining_free, int(item['quantity']))
                            item_discount = float(item['price']) * item_free_qty * (get_discount / 100)
                            discount_amount += item_discount
                            remaining_free -= item_free_qty
                
                except:
                    discount_amount = 0
        
        return {
            'discount_amount': round(discount_amount, 2),
            'applicable_items': len(applicable_items),
            'applicable_total': applicable_total,
            'discount_percentage': round((discount_amount / applicable_total) * 100, 2) if applicable_total > 0 else 0
        }
        
    except Exception as e:
        return {
            'discount_amount': 0,
            'applicable_items': 0,
            'error': str(e)
        }

# ======================= COUPON CODE GENERATION =======================

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

# ======================= FLASH SALES MANAGEMENT =======================

@coupons_bp.route('/flash-sales', methods=['GET'])
@admin_required
def get_flash_sales():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')  # active, upcoming, expired, inactive
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if status == 'active':
            where_conditions.append("fs.is_active = 1 AND fs.start_time <= NOW() AND fs.end_time > NOW()")
        elif status == 'upcoming':
            where_conditions.append("fs.is_active = 1 AND fs.start_time > NOW()")
        elif status == 'expired':
            where_conditions.append("fs.end_time <= NOW()")
        elif status == 'inactive':
            where_conditions.append("fs.is_active = 0")
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM flash_sales fs WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get flash sales
        sales_query = f"""
        SELECT fs.*,
               CASE 
                   WHEN fs.end_time <= NOW() THEN 'expired'
                   WHEN fs.start_time > NOW() THEN 'upcoming'
                   WHEN fs.is_active = 0 THEN 'inactive'
                   ELSE 'active'
               END as computed_status
        FROM flash_sales fs
        WHERE {where_clause}
        ORDER BY fs.created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        flash_sales = Database.execute_query(sales_query, params, fetch=True)
        
        # Convert decimals and add computed fields
        for sale in flash_sales:
            sale['discount_value'] = float(sale['discount_value'])
            if sale['max_discount_amount']:
                sale['max_discount_amount'] = float(sale['max_discount_amount'])
            
            # Add time calculations
            now = datetime.now()
            if sale['start_time'] > now:
                sale['starts_in_hours'] = int((sale['start_time'] - now).total_seconds() / 3600)
            else:
                sale['starts_in_hours'] = 0
                
            if sale['end_time'] > now:
                sale['ends_in_hours'] = int((sale['end_time'] - now).total_seconds() / 3600)
            else:
                sale['ends_in_hours'] = 0
        
        return jsonify(ResponseFormatter.paginated(flash_sales, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/flash-sales', methods=['POST'])
@admin_required
def create_flash_sale():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['name', 'start_time', 'end_time', 'discount_type', 'discount_value']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Parse dates
        try:
            start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
        except:
            return error_response('Invalid date format', 400)
        
        if end_time <= start_time:
            return error_response('End time must be after start time', 400)
        
        # Create flash sale
        sale_query = """
        INSERT INTO flash_sales (name, description, start_time, end_time, discount_type,
                               discount_value, max_discount_amount, target_type, usage_limit,
                               is_active, banner_text, banner_color, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        sale_id = Database.execute_query(sale_query, (
            data['name'], data.get('description', ''), start_time, end_time,
            data['discount_type'], float(data['discount_value']),
            float(data['max_discount_amount']) if data.get('max_discount_amount') else None,
            data.get('target_type', 'all_products'), int(data['usage_limit']) if data.get('usage_limit') else None,
            bool(data.get('is_active', True)), data.get('banner_text', ''),
            data.get('banner_color', '#ff4444'), datetime.now()
        ))
        
        # Handle product targeting
        if data.get('product_ids'):
            for product_id in data['product_ids']:
                Database.execute_query(
                    "INSERT INTO flash_sale_products (flash_sale_id, product_id) VALUES (%s, %s)",
                    (sale_id, product_id)
                )
        
        # Handle category targeting
        if data.get('category_ids'):
            for category_id in data['category_ids']:
                Database.execute_query(
                    "INSERT INTO flash_sale_categories (flash_sale_id, category_id, include_subcategories) VALUES (%s, %s, %s)",
                    (sale_id, category_id, bool(data.get('include_subcategories', True)))
                )
        
        return success_response({
            'id': sale_id,
            'name': data['name'],
            'discount_type': data['discount_type'],
            'discount_value': data['discount_value']
        }, 'Flash sale created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BULK DISCOUNT RULES =======================

@coupons_bp.route('/bulk-discounts', methods=['GET'])
@admin_required
def get_bulk_discount_rules():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if status == 'active':
            where_conditions.append("bdr.is_active = 1")
        elif status == 'inactive':
            where_conditions.append("bdr.is_active = 0")
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM bulk_discount_rules bdr WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get bulk discount rules
        rules_query = f"""
        SELECT bdr.*
        FROM bulk_discount_rules bdr
        WHERE {where_clause}
        ORDER BY bdr.created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        rules = Database.execute_query(rules_query, params, fetch=True)
        
        # Parse JSON tiers
        for rule in rules:
            if rule.get('tiers'):
                try:
                    rule['tiers'] = json.loads(rule['tiers'])
                except:
                    rule['tiers'] = []
        
        return jsonify(ResponseFormatter.paginated(rules, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/bulk-discounts', methods=['POST'])
@admin_required
def create_bulk_discount_rule():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['name', 'rule_type', 'tiers']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        if data['rule_type'] not in ['quantity_based', 'amount_based']:
            return error_response('Invalid rule type', 400)
        
        # Validate tiers
        tiers = data.get('tiers', [])
        if not tiers or not isinstance(tiers, list):
            return error_response('Tiers must be a non-empty array', 400)
        
        # Create bulk discount rule
        rule_query = """
        INSERT INTO bulk_discount_rules (name, description, rule_type, target_type, tiers, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        rule_id = Database.execute_query(rule_query, (
            data['name'], data.get('description', ''), data['rule_type'],
            data.get('target_type', 'all_products'), json.dumps(tiers),
            bool(data.get('is_active', True)), datetime.now()
        ))
        
        # Handle product targeting
        if data.get('product_ids'):
            for product_id in data['product_ids']:
                Database.execute_query(
                    "INSERT INTO bulk_discount_products (rule_id, product_id) VALUES (%s, %s)",
                    (rule_id, product_id)
                )
        
        # Handle category targeting
        if data.get('category_ids'):
            for category_id in data['category_ids']:
                Database.execute_query(
                    "INSERT INTO bulk_discount_categories (rule_id, category_id, include_subcategories) VALUES (%s, %s, %s)",
                    (rule_id, category_id, bool(data.get('include_subcategories', True)))
                )
        
        return success_response({
            'id': rule_id,
            'name': data['name'],
            'rule_type': data['rule_type']
        }, 'Bulk discount rule created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CUSTOMER GROUPS =======================

@coupons_bp.route('/customer-groups', methods=['GET'])
@admin_required
def get_customer_groups():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if status == 'active':
            where_conditions.append("cg.is_active = 1")
        elif status == 'inactive':
            where_conditions.append("cg.is_active = 0")
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM customer_groups cg WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get customer groups
        groups_query = f"""
        SELECT cg.*,
               (SELECT COUNT(*) FROM customer_group_members cgm WHERE cgm.group_id = cg.id) as member_count
        FROM customer_groups cg
        WHERE {where_clause}
        ORDER BY cg.created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        groups = Database.execute_query(groups_query, params, fetch=True)
        
        # Parse JSON criteria
        for group in groups:
            if group.get('criteria'):
                try:
                    group['criteria'] = json.loads(group['criteria'])
                except:
                    group['criteria'] = {}
        
        return jsonify(ResponseFormatter.paginated(groups, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/customer-groups', methods=['POST'])
@admin_required
def create_customer_group():
    try:
        data = get_request_data()
        
        # Validate required fields
        if not data.get('name'):
            return error_response('Group name is required', 400)
        
        # Create customer group
        group_query = """
        INSERT INTO customer_groups (name, description, criteria, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        group_id = Database.execute_query(group_query, (
            data['name'], data.get('description', ''),
            json.dumps(data.get('criteria', {})),
            bool(data.get('is_active', True)), datetime.now()
        ))
        
        return success_response({
            'id': group_id,
            'name': data['name']
        }, 'Customer group created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= COUPON ANALYTICS =======================

@coupons_bp.route('/coupons/analytics/dashboard', methods=['GET'])
@admin_required
def coupon_analytics_dashboard():
    try:
        days = int(request.args.get('days', 30))
        
        # Overall coupon statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_coupons,
            SUM(CASE WHEN is_active = 1 AND (valid_until IS NULL OR valid_until > NOW()) AND valid_from <= NOW() THEN 1 ELSE 0 END) as active_coupons,
            SUM(CASE WHEN valid_until IS NOT NULL AND valid_until <= NOW() THEN 1 ELSE 0 END) as expired_coupons,
            SUM(used_count) as total_usage,
            (SELECT COUNT(*) FROM coupon_usage WHERE usage_date >= DATE_SUB(NOW(), INTERVAL %s DAY)) as recent_usage
        FROM coupons
        """
        stats = Database.execute_query(stats_query, (days,), fetch=True)[0]
        
        # Discount given statistics
        discount_stats_query = """
        SELECT 
            COUNT(*) as total_orders_with_coupons,
            SUM(discount_amount) as total_discount_given,
            AVG(discount_amount) as avg_discount_amount,
            SUM(original_order_amount) as total_order_value,
            AVG(original_order_amount) as avg_order_value
        FROM coupon_usage
        WHERE usage_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        discount_stats = Database.execute_query(discount_stats_query, (days,), fetch=True)[0]
        
        # Convert decimals
        if discount_stats['total_discount_given']:
            discount_stats['total_discount_given'] = float(discount_stats['total_discount_given'])
        if discount_stats['avg_discount_amount']:
            discount_stats['avg_discount_amount'] = float(discount_stats['avg_discount_amount'])
        if discount_stats['total_order_value']:
            discount_stats['total_order_value'] = float(discount_stats['total_order_value'])
        if discount_stats['avg_order_value']:
            discount_stats['avg_order_value'] = float(discount_stats['avg_order_value'])
        
        # Top performing coupons
        top_coupons_query = """
        SELECT c.id, c.code, c.name, c.type, 
               COUNT(cu.id) as usage_count,
               SUM(cu.discount_amount) as total_discount,
               AVG(cu.discount_amount) as avg_discount
        FROM coupons c
        LEFT JOIN coupon_usage cu ON c.id = cu.coupon_id AND cu.usage_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        WHERE c.is_active = 1
        GROUP BY c.id, c.code, c.name, c.type
        HAVING usage_count > 0
        ORDER BY usage_count DESC
        LIMIT 10
        """
        top_coupons = Database.execute_query(top_coupons_query, (days,), fetch=True)
        
        # Convert decimals in top coupons
        for coupon in top_coupons:
            if coupon['total_discount']:
                coupon['total_discount'] = float(coupon['total_discount'])
            if coupon['avg_discount']:
                coupon['avg_discount'] = float(coupon['avg_discount'])
        
        # Daily usage trends
        trends_query = """
        SELECT DATE(usage_date) as date, 
               COUNT(*) as usage_count,
               SUM(discount_amount) as total_discount
        FROM coupon_usage
        WHERE usage_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY DATE(usage_date)
        ORDER BY date
        """
        usage_trends = Database.execute_query(trends_query, (days,), fetch=True)
        
        # Convert decimals in trends
        for trend in usage_trends:
            trend['total_discount'] = float(trend['total_discount'])
        
        # Coupon type breakdown
        type_breakdown_query = """
        SELECT c.type, 
               COUNT(cu.id) as usage_count,
               SUM(cu.discount_amount) as total_discount
        FROM coupons c
        LEFT JOIN coupon_usage cu ON c.id = cu.coupon_id AND cu.usage_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        WHERE c.is_active = 1
        GROUP BY c.type
        ORDER BY usage_count DESC
        """
        type_breakdown = Database.execute_query(type_breakdown_query, (days,), fetch=True)
        
        # Convert decimals in type breakdown
        for breakdown in type_breakdown:
            if breakdown['total_discount']:
                breakdown['total_discount'] = float(breakdown['total_discount'])
        
        return success_response({
            'days': days,
            'statistics': {**stats, **discount_stats},
            'top_coupons': top_coupons,
            'usage_trends': usage_trends,
            'type_breakdown': type_breakdown
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BULK OPERATIONS =======================

@coupons_bp.route('/coupons/bulk-update', methods=['PUT'])
@admin_required
def bulk_update_coupons():
    try:
        data = get_request_data()
        coupon_ids = data.get('coupon_ids', [])
        updates = data.get('updates', {})
        
        if not coupon_ids:
            return error_response('Coupon IDs are required', 400)
        
        if not updates:
            return error_response('Update data is required', 400)
        
        # Build update query
        update_fields = []
        params = []
        
        allowed_bulk_fields = ['is_active', 'priority']
        
        for field in allowed_bulk_fields:
            if field in updates:
                update_fields.append(f"{field} = %s")
                if field == 'is_active':
                    params.append(bool(updates[field]))
                else:
                    params.append(updates[field])
        
        if not update_fields:
            return error_response('No valid fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        
        # Create placeholders for coupon IDs
        id_placeholders = ','.join(['%s'] * len(coupon_ids))
        params.extend(coupon_ids)
        
        query = f"UPDATE coupons SET {', '.join(update_fields)} WHERE id IN ({id_placeholders})"
        Database.execute_query(query, params)
        
        return success_response(message=f'{len(coupon_ids)} coupons updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/coupons/bulk-generate', methods=['POST'])
@admin_required
def bulk_generate_coupons():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['count', 'name_template', 'type', 'value']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        count = int(data['count'])
        if count < 1 or count > 100:
            return error_response('Count must be between 1 and 100', 400)
        
        # Generate coupon settings
        base_settings = {
            'type': data['type'],
            'value': float(data['value']),
            'minimum_amount': float(data.get('minimum_amount', 0)),
            'usage_limit_per_customer': int(data.get('usage_limit_per_customer', 1)),
            'valid_fromfrom flask import Blueprint, request
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
        
        # Prepare coupon data
        coupon_data = {
            'code': code,
            'name': data['name'],
            'description': data.get('description', ''),
            'type': data['type'],
            'value': float(data['value']),
            'max_discount_amount': float(data['max_discount_amount']) if data.get('max_discount_amount') else None,
            'minimum_amount': float(data.get('minimum_amount', 0)),
            'maximum_amount': float(data['maximum_amount']) if data.get('maximum_amount') else None,
            'minimum_quantity': int(data.get('minimum_quantity', 1)),
            'usage_limit': int(data['usage_limit']) if data.get('usage_limit') else None,
            'usage_limit_per_customer': int(data.get('usage_limit_per_customer', 1)),
            'valid_from': valid_from,
            'valid_until': valid_until,
            'customer_eligibility': data.get('customer_eligibility', 'all'),
            'product_eligibility': data.get('product_eligibility', 'all'),
            'stackable': bool(data.get('stackable', False)),
            'auto_apply': bool(data.get('auto_apply', False)),
            'requires_shipping_address': bool(data.get('requires_shipping_address', False)),
            'buy_x_get_y_config': json.dumps(data.get('buy_x_get_y_config', {})) if data.get('buy_x_get_y_config') else None,
            'is_active': bool(data.get('is_active', True)),
            'priority': int(data.get('priority', 0)),
            'created_by': current_admin['id']
        }
        
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
            coupon_data['code'], coupon_data['name'], coupon_data['description'],
            coupon_data['type'], coupon_data['value'], coupon_data['max_discount_amount'],
            coupon_data['minimum_amount'], coupon_data['maximum_amount'], coupon_data['minimum_quantity'],
            coupon_data['usage_limit'], coupon_data['usage_limit_per_customer'],
            coupon_data['valid_from'], coupon_data['valid_until'], coupon_data['customer_eligibility'],
            coupon_data['product_eligibility'], coupon_data['stackable'], coupon_data['auto_apply'],
            coupon_data['requires_shipping_address'], coupon_data['buy_x_get_y_config'],
            coupon_data['is_active'], coupon_data['priority'], coupon_data['created_by'], datetime.now()
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
        
        # Get customer restrictions
        customer_restrictions = Database.execute_query(
            """SELECT cc.customer_id, c.name, c.email 
               FROM coupon_customers cc 
               LEFT JOIN customers c ON cc.customer_id = c.id 
               WHERE cc.coupon_id = %s""",
            (coupon_id,), fetch=True
        )
        coupon['restricted_customers'] = customer_restrictions
        
        # Get product restrictions
        product_restrictions = Database.execute_query(
            """SELECT cp.product_id, cp.include_exclude, p.name, p.sku 
               FROM coupon_products cp 
               LEFT JOIN products p ON cp.product_id = p.id 
               WHERE cp.coupon_id = %s""",
            (coupon_id,), fetch=True
        )
        coupon['restricted_products'] = product_restrictions
        
        # Get category restrictions
        category_restrictions = Database.execute_query(
            """SELECT cc.category_id, cc.include_exclude, cc.include_subcategories, cat.name 
               FROM coupon_categories cc 
               LEFT JOIN categories cat ON cc.category_id = cat.id 
               WHERE cc.coupon_id = %s""",
            (coupon_id,), fetch=True
        )
        coupon['restricted_categories'] = category_restrictions
        
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
        
        # Get recent usage history
        recent_usage = Database.execute_query(
            """SELECT cu.*, c.name as customer_name, c.email as customer_email, o.order_number
               FROM coupon_usage cu
               LEFT JOIN customers c ON cu.customer_id = c.id
               LEFT JOIN orders o ON cu.order_id = o.id
               WHERE cu.coupon_id = %s
               ORDER BY cu.usage_date DESC
               LIMIT 10""",
            (coupon_id,), fetch=True
        )
        
        # Convert decimals in usage history
        for usage in recent_usage:
            usage['discount_amount'] = float(usage['discount_amount'])
            usage['original_order_amount'] = float(usage['original_order_amount'])
            usage['final_order_amount'] = float(usage['final_order_amount'])
        
        coupon['recent_usage'] = recent_usage
        
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
        
        # Handle date fields
        if 'valid_from' in data:
            try:
                valid_from = datetime.fromisoformat(data['valid_from'].replace('Z', '+00:00'))
                update_fields.append("valid_from = %s")
                params.append(valid_from)
            except:
                return error_response('Invalid valid_from date format', 400)
        
        if 'valid_until' in data:
            if data['valid_until']:
                try:
                    valid_until = datetime.fromisoformat(data['valid_until'].replace('Z', '+00:00'))
                    update_fields.append("valid_until = %s")
                    params.append(valid_until)
                except:
                    return error_response('Invalid valid_until date format', 400)
            else:
                update_fields.append("valid_until = NULL")
        
        # Handle JSON fields
        if 'buy_x_get_y_config' in data:
            update_fields.append("buy_x_get_y_config = %s")
            params.append(json.dumps(data['buy_x_get_y_config']) if data['buy_x_get_y_config'] else None)
        
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
        
        # Update customer restrictions if provided
        if 'customer_ids' in data:
            Database.execute_query("DELETE FROM coupon_customers WHERE coupon_id = %s", (coupon_id,))
            for customer_id in data['customer_ids']:
                Database.execute_query(
                    "INSERT INTO coupon_customers (coupon_id, customer_id) VALUES (%s, %s)",
                    (coupon_id, customer_id)
                )
        
        # Update product restrictions if provided
        if 'product_ids' in data:
            Database.execute_query("DELETE FROM coupon_products WHERE coupon_id = %s", (coupon_id,))
            include_exclude = 'include' if data.get('product_eligibility') == 'specific_products' else 'exclude'
            for product_id in data['product_ids']:
                Database.execute_query(
                    "INSERT INTO coupon_products (coupon_id, product_id, include_exclude) VALUES (%s, %s, %s)",
                    (coupon_id, product_id, include_exclude)
                )
        
        # Update category restrictions if provided
        if 'category_ids' in data:
            Database.execute_query("DELETE FROM coupon_categories WHERE coupon_id = %s", (coupon_id,))
            include_exclude = 'include' if data.get('product_eligibility') == 'specific_categories' else 'exclude'
            for category_id in data['category_ids']:
                Database.execute_query(
                    "INSERT INTO coupon_categories (coupon_id, category_id, include_exclude) VALUES (%s, %s, %s)",
                    (coupon_id, category_id, include_exclude)
                )
        
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

# ======================= COUPON VALIDATION & APPLICATION =======================

@coupons_bp.route('/coupons/validate', methods=['POST'])
@admin_required
def validate_coupon():
    """Admin endpoint to validate coupon for testing"""
    try:
        data = get_request_data()
        code = data.get('code', '').strip().upper()
        customer_id = data.get('customer_id')
        cart_items = data.get('cart_items', [])  # [{product_id, quantity, price}]
        
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
        
        # Check customer-specific usage limit
        if customer_id and coupon['usage_limit_per_customer']:
            customer_usage = Database.execute_query(
                "SELECT COUNT(*) as count FROM coupon_usage WHERE coupon_id = %s AND customer_id = %s",
                (coupon['id'], customer_id), fetch=True
            )[0]['count']
            
            if customer_usage >= coupon['usage_limit_per_customer']:
                return {
                    'valid': False,
                    'error': 'You have already used this coupon',
                    'error_code': 'CUSTOMER_USAGE_EXCEEDED'
                }
        
        # Check customer eligibility
        if customer_id:
            eligibility_check = check_customer_eligibility(coupon, customer_id)
            if not eligibility_check['eligible']:
                return {
                    'valid': False,
                    'error': eligibility_check['reason'],
                    'error_code': 'CUSTOMER_NOT_ELIGIBLE'
                }
        
        # Calculate discount if cart items provided
        discount_info = None
        if cart_items:
            discount_info = calculate_coupon_discount(coupon, cart_items, customer_id)
            
            # Check minimum amount requirement
            cart_total = sum(float(item['price']) * int(item['quantity']) for item in cart_items)
            if cart_total < float(coupon['minimum_amount']):
                return {
                    'valid': False,
                    'error': f'Minimum order amount of ₹{coupon["minimum_amount"]} required',
                    'error_code': 'MINIMUM_AMOUNT_NOT_MET',
                    'minimum_amount': float(coupon['minimum_amount']),
                    'current_amount': cart_total
                }
            
            # Check maximum amount restriction
            if coupon['maximum_amount'] and cart_total > float(coupon['maximum_amount']):
                return {
                    'valid': False,
                    'error': f'Maximum order amount of ₹{coupon["maximum_amount"]} exceeded',
                    'error_code': 'MAXIMUM_AMOUNT_EXCEEDED'
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
            },
            'discount_info': discount_info
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': 'Error validating coupon',
            'error_code': 'VALIDATION_ERROR'
        }

def check_customer_eligibility(coupon, customer_id):
    """Check if customer is eligible for the coupon"""
    try:
        if coupon['customer_eligibility'] == 'all':
            return {'eligible': True}
        
        if coupon['customer_eligibility'] == 'new_customers':
            # Check if customer has