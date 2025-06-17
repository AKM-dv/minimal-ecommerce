from flask import Blueprint, request
import json
from datetime import datetime, timedelta
import uuid
import secrets

# Import our modules
from models import Database, Customer
from utils import (admin_required, success_response, error_response, get_request_data, 
                   ResponseFormatter, validate_email, validate_password)

# Create blueprint
customers_bp = Blueprint('customers', __name__)

# ======================= CUSTOMERS MANAGEMENT ROUTES =======================

@customers_bp.route('/customers', methods=['GET'])
@admin_required
def get_customers():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        segment = request.args.get('segment')  # VIP, regular, new
        status = request.args.get('status')
        registration_date = request.args.get('registration_date')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if search:
            where_conditions.append("(c.name LIKE %s OR c.email LIKE %s OR c.phone LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        if status:
            if status == 'active':
                where_conditions.append("c.is_active = 1")
            elif status == 'inactive':
                where_conditions.append("c.is_active = 0")
            elif status == 'verified':
                where_conditions.append("c.email_verified = 1")
            elif status == 'unverified':
                where_conditions.append("c.email_verified = 0")
        
        if registration_date:
            where_conditions.append("DATE(c.created_at) >= %s")
            params.append(registration_date)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Validate sort columns
        valid_sort_columns = ['name', 'email', 'created_at']
        if sort_by not in valid_sort_columns:
            sort_by = 'created_at'
        
        sort_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM customers c WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get customers with analytics
        customers_query = f"""
        SELECT c.*,
               COALESCE(order_stats.order_count, 0) as order_count,
               COALESCE(order_stats.total_spent, 0) as total_spent,
               COALESCE(order_stats.avg_order_value, 0) as avg_order_value,
               order_stats.last_order_date,
               CASE 
                   WHEN order_stats.total_spent >= 50000 THEN 'VIP'
                   WHEN order_stats.total_spent >= 10000 THEN 'regular'
                   ELSE 'new'
               END as segment
        FROM customers c
        LEFT JOIN (
            SELECT customer_id,
                   COUNT(*) as order_count,
                   SUM(total_amount) as total_spent,
                   AVG(total_amount) as avg_order_value,
                   MAX(created_at) as last_order_date
            FROM orders
            WHERE payment_status = 'paid'
            GROUP BY customer_id
        ) order_stats ON c.id = order_stats.customer_id
        WHERE {where_clause}
        """
        
        # Add segment filtering if specified
        if segment:
            if segment == 'VIP':
                customers_query += " HAVING segment = 'VIP'"
            elif segment == 'regular':
                customers_query += " HAVING segment = 'regular'"
            elif segment == 'new':
                customers_query += " HAVING segment = 'new'"
        
        customers_query += f" ORDER BY c.{sort_by} {sort_direction} LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        customers = Database.execute_query(customers_query, params, fetch=True)
        
        # Convert decimal values to float
        for customer in customers:
            customer['total_spent'] = float(customer['total_spent']) if customer['total_spent'] else 0
            customer['avg_order_value'] = float(customer['avg_order_value']) if customer['avg_order_value'] else 0
        
        return jsonify(ResponseFormatter.paginated(customers, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@customers_bp.route('/customers/<int:customer_id>', methods=['GET'])
@admin_required
def get_customer(customer_id):
    try:
        # Get customer details with analytics
        customer_query = """
        SELECT c.*,
               COALESCE(order_stats.order_count, 0) as order_count,
               COALESCE(order_stats.total_spent, 0) as total_spent,
               COALESCE(order_stats.avg_order_value, 0) as avg_order_value,
               order_stats.last_order_date,
               order_stats.first_order_date,
               CASE 
                   WHEN order_stats.total_spent >= 50000 THEN 'VIP'
                   WHEN order_stats.total_spent >= 10000 THEN 'regular'
                   ELSE 'new'
               END as segment
        FROM customers c
        LEFT JOIN (
            SELECT customer_id,
                   COUNT(*) as order_count,
                   SUM(total_amount) as total_spent,
                   AVG(total_amount) as avg_order_value,
                   MAX(created_at) as last_order_date,
                   MIN(created_at) as first_order_date
            FROM orders
            WHERE payment_status = 'paid'
            GROUP BY customer_id
        ) order_stats ON c.id = order_stats.customer_id
        WHERE c.id = %s
        """
        
        customer_result = Database.execute_query(customer_query, (customer_id,), fetch=True)
        
        if not customer_result:
            return error_response('Customer not found', 404)
        
        customer = customer_result[0]
        
        # Get customer addresses
        addresses_query = """
        SELECT * FROM customer_addresses 
        WHERE customer_id = %s 
        ORDER BY is_default DESC, created_at DESC
        """
        addresses = Database.execute_query(addresses_query, (customer_id,), fetch=True)
        
        # Get recent orders
        orders_query = """
        SELECT id, order_number, total_amount, status, payment_status, created_at
        FROM orders 
        WHERE customer_id = %s 
        ORDER BY created_at DESC 
        LIMIT 10
        """
        recent_orders = Database.execute_query(orders_query, (customer_id,), fetch=True)
        
        # Convert decimal values to float
        customer['total_spent'] = float(customer['total_spent']) if customer['total_spent'] else 0
        customer['avg_order_value'] = float(customer['avg_order_value']) if customer['avg_order_value'] else 0
        
        for order in recent_orders:
            order['total_amount'] = float(order['total_amount'])
        
        customer['addresses'] = addresses
        customer['recent_orders'] = recent_orders
        
        return success_response(customer)
        
    except Exception as e:
        return error_response(str(e), 500)

@customers_bp.route('/customers', methods=['POST'])
@admin_required
def create_customer():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['name', 'email']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        email = data['email'].strip().lower()
        
        # Validate email format
        if not validate_email(email):
            return error_response('Invalid email format', 400)
        
        # Check for duplicate email
        existing_customer = Customer.get_customer_by_email(email)
        if existing_customer:
            return error_response('Customer with this email already exists', 400)
        
        # Generate temporary password if not provided
        password = data.get('password')
        if not password:
            password = secrets.token_urlsafe(12)
        
        # Validate password if provided
        if not validate_password(password):
            return error_response('Password must be at least 8 characters with uppercase, lowercase, and number', 400)
        
        # Create customer
        customer_id = Customer.create_customer(
            email=email,
            password=password,
            name=data['name'],
            phone=data.get('phone')
        )
        
        # Set email verification status if specified
        if data.get('email_verified'):
            Database.execute_query(
                "UPDATE customers SET email_verified = 1 WHERE id = %s",
                (customer_id,)
            )
        
        return success_response({
            'id': customer_id,
            'email': email,
            'temporary_password': password if not data.get('password') else None
        }, 'Customer created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@customers_bp.route('/customers/<int:customer_id>', methods=['PUT'])
@admin_required
def update_customer(customer_id):
    try:
        data = get_request_data()
        
        # Check if customer exists
        existing_customer = Database.execute_query(
            "SELECT * FROM customers WHERE id = %s", (customer_id,), fetch=True
        )
        if not existing_customer:
            return error_response('Customer not found', 404)
        
        # Build update query
        update_fields = []
        params = []
        
        updatable_fields = {
            'name': str, 'phone': str, 'is_active': bool, 'email_verified': bool,
            'date_of_birth': str, 'gender': str
        }
        
        for field, field_type in updatable_fields.items():
            if field in data:
                update_fields.append(f"{field} = %s")
                if field_type == bool:
                    params.append(bool(data[field]))
                else:
                    params.append(data[field])
        
        # Handle email update separately (needs validation)
        if 'email' in data:
            new_email = data['email'].strip().lower()
            if not validate_email(new_email):
                return error_response('Invalid email format', 400)
            
            # Check for duplicate email (excluding current customer)
            duplicate_check = Database.execute_query(
                "SELECT COUNT(*) as count FROM customers WHERE email = %s AND id != %s",
                (new_email, customer_id), fetch=True
            )[0]['count']
            
            if duplicate_check > 0:
                return error_response('Email already exists', 400)
            
            update_fields.append("email = %s")
            params.append(new_email)
            
            # Reset email verification if email changed
            update_fields.append("email_verified = 0")
        
        if not update_fields:
            return error_response('No fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(customer_id)
        
        query = f"UPDATE customers SET {', '.join(update_fields)} WHERE id = %s"
        Database.execute_query(query, params)
        
        return success_response(message='Customer updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@customers_bp.route('/customers/<int:customer_id>', methods=['DELETE'])
@admin_required
def delete_customer(customer_id):
    try:
        # Check if customer exists
        existing_customer = Database.execute_query(
            "SELECT * FROM customers WHERE id = %s", (customer_id,), fetch=True
        )
        if not existing_customer:
            return error_response('Customer not found', 404)
        
        # Check if customer has orders
        order_count = Database.execute_query(
            "SELECT COUNT(*) as count FROM orders WHERE customer_id = %s",
            (customer_id,), fetch=True
        )[0]['count']
        
        if order_count > 0:
            # Soft delete - deactivate instead of delete
            Database.execute_query(
                "UPDATE customers SET is_active = 0, updated_at = %s WHERE id = %s",
                (datetime.now(), customer_id)
            )
            message = 'Customer deactivated (has order history)'
        else:
            # Hard delete if no orders
            Database.execute_query("DELETE FROM customers WHERE id = %s", (customer_id,))
            message = 'Customer deleted successfully'
        
        return success_response(message=message)
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CUSTOMER ADDRESSES =======================

@customers_bp.route('/customers/<int:customer_id>/addresses', methods=['GET'])
@admin_required
def get_customer_addresses(customer_id):
    try:
        addresses_query = """
        SELECT * FROM customer_addresses 
        WHERE customer_id = %s 
        ORDER BY is_default DESC, created_at DESC
        """
        addresses = Database.execute_query(addresses_query, (customer_id,), fetch=True)
        
        return success_response(addresses)
        
    except Exception as e:
        return error_response(str(e), 500)

@customers_bp.route('/customers/<int:customer_id>/addresses', methods=['POST'])
@admin_required
def add_customer_address(customer_id):
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'address_line_1', 'city', 'state', 'postal_code', 'country']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Check if customer exists
        customer = Database.execute_query(
            "SELECT * FROM customers WHERE id = %s", (customer_id,), fetch=True
        )
        if not customer:
            return error_response('Customer not found', 404)
        
        # If this is set as default, unset other defaults
        if data.get('is_default'):
            Database.execute_query(
                "UPDATE customer_addresses SET is_default = 0 WHERE customer_id = %s",
                (customer_id,)
            )
        
        # Create address
        address_query = """
        INSERT INTO customer_addresses (customer_id, type, first_name, last_name, company,
                                      address_line_1, address_line_2, city, state, postal_code,
                                      country, phone, is_default, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        address_id = Database.execute_query(address_query, (
            customer_id, data.get('type', 'shipping'), data['first_name'], data['last_name'],
            data.get('company', ''), data['address_line_1'], data.get('address_line_2', ''),
            data['city'], data['state'], data['postal_code'], data['country'],
            data.get('phone', ''), bool(data.get('is_default', False)), datetime.now()
        ))
        
        return success_response({'id': address_id}, 'Address added successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CUSTOMER SEGMENTATION =======================

@customers_bp.route('/customers/segments', methods=['GET'])
@admin_required
def get_customer_segments():
    try:
        segments_query = """
        SELECT 
            CASE 
                WHEN COALESCE(order_stats.total_spent, 0) >= 50000 THEN 'VIP'
                WHEN COALESCE(order_stats.total_spent, 0) >= 10000 THEN 'regular'
                ELSE 'new'
            END as segment,
            COUNT(*) as customer_count,
            AVG(COALESCE(order_stats.total_spent, 0)) as avg_spent,
            SUM(COALESCE(order_stats.total_spent, 0)) as total_revenue
        FROM customers c
        LEFT JOIN (
            SELECT customer_id, SUM(total_amount) as total_spent
            FROM orders
            WHERE payment_status = 'paid'
            GROUP BY customer_id
        ) order_stats ON c.id = order_stats.customer_id
        WHERE c.is_active = 1
        GROUP BY segment
        ORDER BY 
            CASE segment 
                WHEN 'VIP' THEN 1 
                WHEN 'regular' THEN 2 
                WHEN 'new' THEN 3 
            END
        """
        
        segments = Database.execute_query(segments_query, fetch=True)
        
        # Convert decimal values to float
        for segment in segments:
            segment['avg_spent'] = float(segment['avg_spent'])
            segment['total_revenue'] = float(segment['total_revenue'])
        
        return success_response(segments)
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BULK OPERATIONS =======================

@customers_bp.route('/customers/bulk-update', methods=['PUT'])
@admin_required
def bulk_update_customers():
    try:
        data = get_request_data()
        customer_ids = data.get('customer_ids', [])
        updates = data.get('updates', {})
        
        if not customer_ids:
            return error_response('Customer IDs are required', 400)
        
        if not updates:
            return error_response('Update data is required', 400)
        
        # Build update query
        update_fields = []
        params = []
        
        allowed_bulk_fields = ['is_active', 'email_verified']
        
        for field in allowed_bulk_fields:
            if field in updates:
                update_fields.append(f"{field} = %s")
                params.append(bool(updates[field]))
        
        if not update_fields:
            return error_response('No valid fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        
        # Create placeholders for customer IDs
        id_placeholders = ','.join(['%s'] * len(customer_ids))
        params.extend(customer_ids)
        
        query = f"UPDATE customers SET {', '.join(update_fields)} WHERE id IN ({id_placeholders})"
        Database.execute_query(query, params)
        
        return success_response(message=f'{len(customer_ids)} customers updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CUSTOMER ANALYTICS =======================

@customers_bp.route('/customers/analytics/summary', methods=['GET'])
@admin_required
def get_customers_analytics():
    try:
        days = int(request.args.get('days', 30))
        
        # Customer registration trends
        registration_query = """
        SELECT DATE(created_at) as date, COUNT(*) as registrations
        FROM customers
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY DATE(created_at)
        ORDER BY date
        """
        registration_trends = Database.execute_query(registration_query, (days,), fetch=True)
        
        # Customer segments summary
        segments_summary_query = """
        SELECT 
            CASE 
                WHEN COALESCE(order_stats.total_spent, 0) >= 50000 THEN 'VIP'
                WHEN COALESCE(order_stats.total_spent, 0) >= 10000 THEN 'regular'
                ELSE 'new'
            END as segment,
            COUNT(*) as count
        FROM customers c
        LEFT JOIN (
            SELECT customer_id, SUM(total_amount) as total_spent
            FROM orders WHERE payment_status = 'paid'
            GROUP BY customer_id
        ) order_stats ON c.id = order_stats.customer_id
        WHERE c.is_active = 1
        GROUP BY segment
        """
        segments_summary = Database.execute_query(segments_summary_query, fetch=True)
        
        # Customer activity stats
        activity_query = """
        SELECT 
            SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_customers,
            SUM(CASE WHEN email_verified = 1 THEN 1 ELSE 0 END) as verified_customers,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as new_customers_30d,
            COUNT(*) as total_customers
        FROM customers
        """
        activity_stats = Database.execute_query(activity_query, fetch=True)[0]
        
        return success_response({
            'days': days,
            'registration_trends': registration_trends,
            'segments_summary': segments_summary,
            'activity_stats': activity_stats
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CUSTOMER STATS =======================

@customers_bp.route('/customers/stats', methods=['GET'])
@admin_required
def get_customers_stats():
    try:
        stats_query = """
        SELECT 
            COUNT(*) as total_customers,
            SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_customers,
            SUM(CASE WHEN email_verified = 1 THEN 1 ELSE 0 END) as verified_customers,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as new_customers_30d,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as new_customers_7d
        FROM customers
        """
        
        stats = Database.execute_query(stats_query, fetch=True)[0]
        
        # Get average customer metrics
        avg_metrics_query = """
        SELECT 
            AVG(COALESCE(order_stats.order_count, 0)) as avg_orders_per_customer,
            AVG(COALESCE(order_stats.total_spent, 0)) as avg_spent_per_customer
        FROM customers c
        LEFT JOIN (
            SELECT customer_id, COUNT(*) as order_count, SUM(total_amount) as total_spent
            FROM orders WHERE payment_status = 'paid'
            GROUP BY customer_id
        ) order_stats ON c.id = order_stats.customer_id
        WHERE c.is_active = 1
        """
        
        avg_metrics = Database.execute_query(avg_metrics_query, fetch=True)[0]
        
        # Convert decimal values to float
        avg_metrics['avg_orders_per_customer'] = float(avg_metrics['avg_orders_per_customer']) if avg_metrics['avg_orders_per_customer'] else 0
        avg_metrics['avg_spent_per_customer'] = float(avg_metrics['avg_spent_per_customer']) if avg_metrics['avg_spent_per_customer'] else 0
        
        # Combine stats
        stats.update(avg_metrics)
        
        return success_response(stats)
        
    except Exception as e:
        return error_response(str(e), 500)