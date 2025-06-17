from flask import Blueprint, request
import json
from datetime import datetime, timedelta
import uuid

# Import our modules
from models import Database, Order
from utils import (admin_required, success_response, error_response, get_request_data, 
                   ResponseFormatter)

# Create blueprint
orders_bp = Blueprint('orders', __name__)

# ======================= ORDER MANAGEMENT ROUTES =======================

@orders_bp.route('/orders', methods=['GET'])
@admin_required
def get_orders():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        payment_status = request.args.get('payment_status')
        search = request.args.get('search', '').strip()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        customer_id = request.args.get('customer_id')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if status:
            where_conditions.append("o.status = %s")
            params.append(status)
            
        if payment_status:
            where_conditions.append("o.payment_status = %s")
            params.append(payment_status)
            
        if customer_id:
            where_conditions.append("o.customer_id = %s")
            params.append(customer_id)
            
        if search:
            where_conditions.append("(o.order_number LIKE %s OR c.name LIKE %s OR c.email LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
            
        if start_date:
            where_conditions.append("DATE(o.created_at) >= %s")
            params.append(start_date)
            
        if end_date:
            where_conditions.append("DATE(o.created_at) <= %s")
            params.append(end_date)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Validate sort columns
        valid_sort_columns = ['order_number', 'total_amount', 'status', 'payment_status', 'created_at']
        if sort_by not in valid_sort_columns:
            sort_by = 'created_at'
        
        sort_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'
        
        # Get total count
        count_query = f"""
        SELECT COUNT(*) as total FROM orders o 
        LEFT JOIN customers c ON o.customer_id = c.id 
        WHERE {where_clause}
        """
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get orders with customer info
        orders_query = f"""
        SELECT o.*, c.name as customer_name, c.email as customer_email, c.phone as customer_phone,
               (SELECT COUNT(*) FROM order_items oi WHERE oi.order_id = o.id) as item_count,
               (SELECT COUNT(*) FROM order_notes on WHERE on.order_id = o.id) as notes_count
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE {where_clause}
        ORDER BY o.{sort_by} {sort_direction}
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        orders = Database.execute_query(orders_query, params, fetch=True)
        
        # Parse JSON fields and format data
        for order in orders:
            # Parse addresses
            if order['shipping_address']:
                try:
                    order['shipping_address'] = json.loads(order['shipping_address'])
                except:
                    order['shipping_address'] = {}
                    
            if order['billing_address']:
                try:
                    order['billing_address'] = json.loads(order['billing_address'])
                except:
                    order['billing_address'] = {}
            
            # Parse tracking info
            if order.get('tracking_info'):
                try:
                    order['tracking_info'] = json.loads(order['tracking_info'])
                except:
                    order['tracking_info'] = {}
            
            # Convert decimal to float
            order['total_amount'] = float(order['total_amount'])
            if order.get('shipping_cost'):
                order['shipping_cost'] = float(order['shipping_cost'])
            if order.get('tax_amount'):
                order['tax_amount'] = float(order['tax_amount'])
        
        return jsonify(ResponseFormatter.paginated(orders, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@orders_bp.route('/orders/<int:order_id>', methods=['GET'])
@admin_required
def get_order(order_id):
    try:
        # Get order details with customer info
        order_query = """
        SELECT o.*, c.name as customer_name, c.email as customer_email, c.phone as customer_phone
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.id = %s
        """
        order_result = Database.execute_query(order_query, (order_id,), fetch=True)
        
        if not order_result:
            return error_response('Order not found', 404)
        
        order = order_result[0]
        
        # Get order items with product details
        items_query = """
        SELECT oi.*, p.name as product_name, p.images as product_images, p.sku as product_sku,
               pv.variant_type, pv.variant_value
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        LEFT JOIN product_variants pv ON oi.variant_id = pv.id
        WHERE oi.order_id = %s
        ORDER BY oi.id
        """
        items = Database.execute_query(items_query, (order_id,), fetch=True)
        
        # Get order notes
        notes_query = """
        SELECT on.*, a.name as admin_name
        FROM order_notes on
        LEFT JOIN admins a ON on.admin_id = a.id
        WHERE on.order_id = %s
        ORDER BY on.created_at ASC
        """
        notes = Database.execute_query(notes_query, (order_id,), fetch=True)
        
        # Get order status history
        status_history_query = """
        SELECT * FROM order_status_history
        WHERE order_id = %s
        ORDER BY created_at ASC
        """
        status_history = Database.execute_query(status_history_query, (order_id,), fetch=True)
        
        # Parse JSON fields
        if order['shipping_address']:
            try:
                order['shipping_address'] = json.loads(order['shipping_address'])
            except:
                order['shipping_address'] = {}
                
        if order['billing_address']:
            try:
                order['billing_address'] = json.loads(order['billing_address'])
            except:
                order['billing_address'] = {}
        
        if order.get('tracking_info'):
            try:
                order['tracking_info'] = json.loads(order['tracking_info'])
            except:
                order['tracking_info'] = {}
        
        # Parse product images and convert prices
        for item in items:
            if item['product_images']:
                try:
                    images = json.loads(item['product_images'])
                    item['product_image'] = images[0]['url'] if images else ''
                except:
                    item['product_image'] = ''
            else:
                item['product_image'] = ''
            
            item['price'] = float(item['price'])
            item['total'] = float(item['price']) * int(item['quantity'])
            del item['product_images']  # Remove full images array
        
        # Convert decimal amounts to float
        order['total_amount'] = float(order['total_amount'])
        if order.get('shipping_cost'):
            order['shipping_cost'] = float(order['shipping_cost'])
        if order.get('tax_amount'):
            order['tax_amount'] = float(order['tax_amount'])
        if order.get('discount_amount'):
            order['discount_amount'] = float(order['discount_amount'])
        
        order['items'] = items
        order['notes'] = notes
        order['status_history'] = status_history
        
        return success_response(order)
        
    except Exception as e:
        return error_response(str(e), 500)

@orders_bp.route('/orders', methods=['POST'])
@admin_required
def create_order():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['customer_id', 'items', 'shipping_address']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        customer_id = data['customer_id']
        items = data['items']
        shipping_address = data['shipping_address']
        billing_address = data.get('billing_address', shipping_address)
        
        # Generate order number
        order_number = generate_order_number()
        
        # Calculate totals
        subtotal = 0
        for item in items:
            if not all(k in item for k in ('product_id', 'quantity', 'price')):
                return error_response('Invalid item data', 400)
            subtotal += float(item['price']) * int(item['quantity'])
        
        shipping_cost = float(data.get('shipping_cost', 0))
        tax_amount = float(data.get('tax_amount', 0))
        discount_amount = float(data.get('discount_amount', 0))
        total_amount = subtotal + shipping_cost + tax_amount - discount_amount
        
        # Create order
        order_query = """
        INSERT INTO orders (order_number, customer_id, total_amount, subtotal, shipping_cost, 
                          tax_amount, discount_amount, status, payment_status, payment_method,
                          shipping_address, billing_address, notes, coupon_code, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        order_id = Database.execute_query(order_query, (
            order_number, customer_id, total_amount, subtotal, shipping_cost,
            tax_amount, discount_amount, data.get('status', 'pending'),
            data.get('payment_status', 'pending'), data.get('payment_method'),
            json.dumps(shipping_address), json.dumps(billing_address),
            data.get('notes', ''), data.get('coupon_code'), datetime.now()
        ))
        
        # Create order items
        for item in items:
            item_query = """
            INSERT INTO order_items (order_id, product_id, variant_id, quantity, price, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            Database.execute_query(item_query, (
                order_id, item['product_id'], item.get('variant_id'),
                item['quantity'], item['price'], datetime.now()
            ))
        
        # Create initial status history entry
        add_status_history(order_id, 'pending', 'Order created')
        
        return success_response({'id': order_id, 'order_number': order_number}, 'Order created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

def generate_order_number():
    """Generate unique order number"""
    timestamp = datetime.now().strftime('%Y%m%d')
    unique_id = str(uuid.uuid4())[:8].upper()
    return f"ORD-{timestamp}-{unique_id}"

def add_status_history(order_id, status, note=''):
    """Add order status history entry"""
    try:
        history_query = """
        INSERT INTO order_status_history (order_id, status, note, created_at)
        VALUES (%s, %s, %s, %s)
        """
        Database.execute_query(history_query, (order_id, status, note, datetime.now()))
    except:
        pass  # Don't fail order creation if status history fails

# ======================= ORDER STATUS MANAGEMENT =======================

@orders_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status(order_id):
    try:
        data = get_request_data()
        new_status = data.get('status')
        note = data.get('note', '')
        
        valid_statuses = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'returned']
        if new_status not in valid_statuses:
            return error_response('Invalid status', 400)
        
        # Check if order exists
        order = Database.execute_query("SELECT * FROM orders WHERE id = %s", (order_id,), fetch=True)
        if not order:
            return error_response('Order not found', 404)
        
        old_status = order[0]['status']
        
        # Update order status
        query = "UPDATE orders SET status = %s, updated_at = %s WHERE id = %s"
        Database.execute_query(query, (new_status, datetime.now(), order_id))
        
        # Add status history
        history_note = note or f"Status changed from {old_status} to {new_status}"
        add_status_history(order_id, new_status, history_note)
        
        # TODO: Send email notification to customer
        
        return success_response(message='Order status updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@orders_bp.route('/orders/<int:order_id>/payment-status', methods=['PUT'])
@admin_required
def update_payment_status(order_id):
    try:
        data = get_request_data()
        new_payment_status = data.get('payment_status')
        
        valid_payment_statuses = ['pending', 'paid', 'failed', 'refunded', 'partially_refunded']
        if new_payment_status not in valid_payment_statuses:
            return error_response('Invalid payment status', 400)
        
        # Check if order exists
        order = Database.execute_query("SELECT * FROM orders WHERE id = %s", (order_id,), fetch=True)
        if not order:
            return error_response('Order not found', 404)
        
        # Update payment status
        query = "UPDATE orders SET payment_status = %s, updated_at = %s WHERE id = %s"
        Database.execute_query(query, (new_payment_status, datetime.now(), order_id))
        
        # Add note
        note = f"Payment status changed to {new_payment_status}"
        if data.get('note'):
            note += f" - {data['note']}"
        
        add_order_note(order_id, note, is_internal=True)
        
        return success_response(message='Payment status updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= ORDER NOTES =======================

@orders_bp.route('/orders/<int:order_id>/notes', methods=['GET'])
@admin_required
def get_order_notes(order_id):
    try:
        notes_query = """
        SELECT on.*, a.name as admin_name
        FROM order_notes on
        LEFT JOIN admins a ON on.admin_id = a.id
        WHERE on.order_id = %s
        ORDER BY on.created_at DESC
        """
        notes = Database.execute_query(notes_query, (order_id,), fetch=True)
        
        return success_response(notes)
        
    except Exception as e:
        return error_response(str(e), 500)

@orders_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
@admin_required
def add_order_note_endpoint(order_id):
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        note = data.get('note', '').strip()
        is_internal = bool(data.get('is_internal', True))
        
        if not note:
            return error_response('Note content is required', 400)
        
        # Check if order exists
        order = Database.execute_query("SELECT * FROM orders WHERE id = %s", (order_id,), fetch=True)
        if not order:
            return error_response('Order not found', 404)
        
        current_admin = get_jwt_identity()
        admin_id = current_admin['id']
        
        note_id = add_order_note(order_id, note, admin_id, is_internal)
        
        return success_response({'id': note_id}, 'Note added successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

def add_order_note(order_id, note, admin_id=None, is_internal=True):
    """Add order note"""
    note_query = """
    INSERT INTO order_notes (order_id, admin_id, note, is_internal, created_at)
    VALUES (%s, %s, %s, %s, %s)
    """
    return Database.execute_query(note_query, (order_id, admin_id, note, is_internal, datetime.now()))

# ======================= BULK OPERATIONS =======================

@orders_bp.route('/orders/bulk-update', methods=['PUT'])
@admin_required
def bulk_update_orders():
    try:
        data = get_request_data()
        order_ids = data.get('order_ids', [])
        updates = data.get('updates', {})
        
        if not order_ids:
            return error_response('Order IDs are required', 400)
        
        if not updates:
            return error_response('Update data is required', 400)
        
        # Build update query
        update_fields = []
        params = []
        
        allowed_bulk_fields = ['status', 'payment_status']
        
        for field in allowed_bulk_fields:
            if field in updates:
                update_fields.append(f"{field} = %s")
                params.append(updates[field])
        
        if not update_fields:
            return error_response('No valid fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        
        # Create placeholders for order IDs
        id_placeholders = ','.join(['%s'] * len(order_ids))
        params.extend(order_ids)
        
        query = f"UPDATE orders SET {', '.join(update_fields)} WHERE id IN ({id_placeholders})"
        Database.execute_query(query, params)
        
        # Add status history for each order if status was updated
        if 'status' in updates:
            for order_id in order_ids:
                add_status_history(order_id, updates['status'], 'Bulk status update')
        
        return success_response(message=f'{len(order_ids)} orders updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@orders_bp.route('/orders/bulk-export', methods=['POST'])
@admin_required
def bulk_export_orders():
    try:
        data = get_request_data()
        order_ids = data.get('order_ids', [])
        export_format = data.get('format', 'csv')  # csv, excel
        
        if not order_ids:
            return error_response('Order IDs are required', 400)
        
        # Get order data for export
        id_placeholders = ','.join(['%s'] * len(order_ids))
        
        export_query = f"""
        SELECT o.order_number, o.created_at, o.status, o.payment_status, o.total_amount,
               c.name as customer_name, c.email as customer_email
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.id IN ({id_placeholders})
        ORDER BY o.created_at DESC
        """
        
        orders = Database.execute_query(export_query, order_ids, fetch=True)
        
        # Convert decimal to float for export
        for order in orders:
            order['total_amount'] = float(order['total_amount'])
        
        # TODO: Generate actual file based on format
        # For now, return data structure
        
        return success_response({
            'format': export_format,
            'order_count': len(orders),
            'data': orders
        }, 'Export data prepared successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= ORDER TRACKING =======================

@orders_bp.route('/orders/<int:order_id>/tracking', methods=['GET'])
@admin_required
def get_order_tracking(order_id):
    try:
        order = Database.execute_query(
            "SELECT tracking_info FROM orders WHERE id = %s", (order_id,), fetch=True
        )
        
        if not order:
            return error_response('Order not found', 404)
        
        tracking_info = {}
        if order[0]['tracking_info']:
            try:
                tracking_info = json.loads(order[0]['tracking_info'])
            except:
                tracking_info = {}
        
        return success_response(tracking_info)
        
    except Exception as e:
        return error_response(str(e), 500)

@orders_bp.route('/orders/<int:order_id>/tracking', methods=['PUT'])
@admin_required
def update_order_tracking(order_id):
    try:
        data = get_request_data()
        
        # Check if order exists
        order = Database.execute_query("SELECT * FROM orders WHERE id = %s", (order_id,), fetch=True)
        if not order:
            return error_response('Order not found', 404)
        
        tracking_info = {
            'tracking_number': data.get('tracking_number', ''),
            'carrier': data.get('carrier', ''),
            'tracking_url': data.get('tracking_url', ''),
            'estimated_delivery': data.get('estimated_delivery'),
            'last_updated': datetime.now().isoformat()
        }
        
        # Update tracking info
        query = "UPDATE orders SET tracking_info = %s, updated_at = %s WHERE id = %s"
        Database.execute_query(query, (json.dumps(tracking_info), datetime.now(), order_id))
        
        # Add note
        note = f"Tracking updated - {tracking_info['carrier']}: {tracking_info['tracking_number']}"
        add_order_note(order_id, note, is_internal=True)
        
        return success_response(message='Order tracking updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= RETURNS & REFUNDS =======================

@orders_bp.route('/orders/<int:order_id>/return', methods=['POST'])
@admin_required
def process_return(order_id):
    try:
        data = get_request_data()
        
        # Check if order exists and is eligible for return
        order = Database.execute_query("SELECT * FROM orders WHERE id = %s", (order_id,), fetch=True)
        if not order:
            return error_response('Order not found', 404)
        
        if order[0]['status'] not in ['delivered']:
            return error_response('Order is not eligible for return', 400)
        
        return_reason = data.get('reason', '')
        return_amount = float(data.get('return_amount', order[0]['total_amount']))
        
        # Create return record
        return_query = """
        INSERT INTO order_returns (order_id, return_amount, reason, status, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        return_id = Database.execute_query(return_query, (
            order_id, return_amount, return_reason, 'pending', datetime.now()
        ))
        
        # Update order status
        Database.execute_query(
            "UPDATE orders SET status = 'returned', updated_at = %s WHERE id = %s",
            (datetime.now(), order_id)
        )
        
        # Add status history
        add_status_history(order_id, 'returned', f'Return initiated - {return_reason}')
        
        return success_response({'return_id': return_id}, 'Return processed successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@orders_bp.route('/orders/<int:order_id>/refund', methods=['POST'])
@admin_required
def process_refund(order_id):
    try:
        data = get_request_data()
        
        # Check if order exists
        order = Database.execute_query("SELECT * FROM orders WHERE id = %s", (order_id,), fetch=True)
        if not order:
            return error_response('Order not found', 404)
        
        refund_amount = float(data.get('refund_amount', order[0]['total_amount']))
        refund_reason = data.get('reason', '')
        
        # Create refund record
        refund_query = """
        INSERT INTO order_refunds (order_id, refund_amount, reason, status, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        refund_id = Database.execute_query(refund_query, (
            order_id, refund_amount, refund_reason, 'pending', datetime.now()
        ))
        
        # Update payment status
        total_amount = float(order[0]['total_amount'])
        if refund_amount >= total_amount:
            new_payment_status = 'refunded'
        else:
            new_payment_status = 'partially_refunded'
        
        Database.execute_query(
            "UPDATE orders SET payment_status = %s, updated_at = %s WHERE id = %s",
            (new_payment_status, datetime.now(), order_id)
        )
        
        # Add note
        add_order_note(order_id, f'Refund of ₹{refund_amount} initiated - {refund_reason}', is_internal=True)
        
        return success_response({'refund_id': refund_id}, 'Refund processed successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= ORDER ANALYTICS =======================

@orders_bp.route('/orders/analytics/summary', methods=['GET'])
@admin_required
def get_orders_analytics():
    try:
        days = int(request.args.get('days', 30))
        
        # Order status distribution
        status_query = """
        SELECT status, COUNT(*) as count, SUM(total_amount) as total_amount
        FROM orders
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY status
        ORDER BY count DESC
        """
        status_data = Database.execute_query(status_query, (days,), fetch=True)
        
        # Payment status distribution
        payment_query = """
        SELECT payment_status, COUNT(*) as count, SUM(total_amount) as total_amount
        FROM orders
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY payment_status
        ORDER BY count DESC
        """
        payment_data = Database.execute_query(payment_query, (days,), fetch=True)
        
        # Daily order trends
        trends_query = """
        SELECT DATE(created_at) as date, 
               COUNT(*) as order_count,
               SUM(total_amount) as total_revenue
        FROM orders
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY DATE(created_at)
        ORDER BY date
        """
        trends_data = Database.execute_query(trends_query, (days,), fetch=True)
        
        # Convert decimals to float
        for item in status_data:
            item['total_amount'] = float(item['total_amount'])
        for item in payment_data:
            item['total_amount'] = float(item['total_amount'])
        for item in trends_data:
            item['total_revenue'] = float(item['total_revenue'])
        
        return success_response({
            'days': days,
            'status_distribution': status_data,
            'payment_distribution': payment_data,
            'daily_trends': trends_data
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@orders_bp.route('/orders/analytics/top-customers', methods=['GET'])
@admin_required
def get_top_customers():
    try:
        limit = int(request.args.get('limit', 10))
        days = int(request.args.get('days', 30))
        
        top_customers_query = """
        SELECT c.id, c.name, c.email,
               COUNT(o.id) as order_count,
               SUM(o.total_amount) as total_spent
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
              AND o.payment_status = 'paid'
        GROUP BY c.id, c.name, c.email
        ORDER BY total_spent DESC
        LIMIT %s
        """
        
        top_customers = Database.execute_query(top_customers_query, (days, limit), fetch=True)
        
        # Convert decimal to float
        for customer in top_customers:
            customer['total_spent'] = float(customer['total_spent'])
        
        return success_response({
            'days': days,
            'customers': top_customers
        })
        
    except Exception as e:
        return error_response(str(e), 500)