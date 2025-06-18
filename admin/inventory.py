from flask import Blueprint, request, jsonify
import json
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import csv
import io

# Import our modules
from models import Database
from utils import (admin_required, success_response, error_response, get_request_data, 
                   ResponseFormatter, save_image)

# Create blueprint
inventory_bp = Blueprint('inventory', __name__)

# ======================= INVENTORY TRACKING ROUTES =======================

@inventory_bp.route('/inventory/stock-levels', methods=['GET'])
@admin_required
def get_stock_levels():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        category_id = request.args.get('category_id')
        status = request.args.get('status')  # in_stock, low_stock, out_of_stock
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'name')
        sort_order = request.args.get('sort_order', 'asc')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = ["p.status = 'active'"]
        params = []
        
        if category_id:
            where_conditions.append("p.category_id = %s")
            params.append(category_id)
        
        if status == 'out_of_stock':
            where_conditions.append("p.stock_quantity = 0")
        elif status == 'low_stock':
            where_conditions.append("p.stock_quantity > 0 AND p.stock_quantity <= p.low_stock_threshold")
        elif status == 'in_stock':
            where_conditions.append("p.stock_quantity > COALESCE(p.low_stock_threshold, 10)")
        
        if search:
            where_conditions.append("(p.name LIKE %s OR p.sku LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param])
        
        where_clause = " AND ".join(where_conditions)
        
        # Validate sort columns
        valid_sort_columns = ['name', 'sku', 'stock_quantity', 'last_restocked', 'category_name']
        if sort_by not in valid_sort_columns:
            sort_by = 'name'
        
        sort_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'
        
        # Get total count
        count_query = f"""
        SELECT COUNT(*) as total FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE {where_clause}
        """
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get stock levels with movement data
        stock_query = f"""
        SELECT p.id, p.name, p.sku, p.stock_quantity, p.price, p.low_stock_threshold,
               p.last_restocked, p.created_at,
               c.name as category_name,
               CASE 
                   WHEN p.stock_quantity = 0 THEN 'out_of_stock'
                   WHEN p.stock_quantity <= COALESCE(p.low_stock_threshold, 10) THEN 'low_stock'
                   ELSE 'in_stock'
               END as stock_status,
               (SELECT SUM(quantity_change) FROM stock_movements sm 
                WHERE sm.product_id = p.id AND sm.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)) as movement_30d,
               (SELECT COUNT(*) FROM order_items oi 
                JOIN orders o ON oi.order_id = o.id 
                WHERE oi.product_id = p.id AND o.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) 
                AND o.payment_status = 'paid') as sales_30d,
               COALESCE(p.stock_quantity * p.price, 0) as stock_value
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE {where_clause}
        ORDER BY 
            CASE WHEN '{sort_by}' = 'category_name' THEN c.name
                 WHEN '{sort_by}' = 'name' THEN p.name
                 WHEN '{sort_by}' = 'sku' THEN p.sku
                 ELSE NULL END {sort_direction},
            CASE WHEN '{sort_by}' = 'stock_quantity' THEN p.stock_quantity
                 ELSE NULL END {sort_direction},
            CASE WHEN '{sort_by}' = 'last_restocked' THEN p.last_restocked
                 ELSE NULL END {sort_direction}
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        stock_levels = Database.execute_query(stock_query, params, fetch=True)
        
        # Convert decimals to float and add computed fields
        for item in stock_levels:
            item['price'] = float(item['price'])
            item['stock_value'] = float(item['stock_value'])
            item['movement_30d'] = item['movement_30d'] or 0
            item['sales_30d'] = item['sales_30d'] or 0
            
            # Calculate days of stock remaining
            if item['sales_30d'] > 0:
                daily_sales = item['sales_30d'] / 30
                item['days_of_stock'] = round(item['stock_quantity'] / daily_sales) if daily_sales > 0 else 999
            else:
                item['days_of_stock'] = 999
        
        return jsonify(ResponseFormatter.paginated(stock_levels, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@inventory_bp.route('/inventory/movements', methods=['GET'])
@admin_required
def get_stock_movements():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        product_id = request.args.get('product_id')
        movement_type = request.args.get('type')  # restock, sale, adjustment, transfer
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if product_id:
            where_conditions.append("sm.product_id = %s")
            params.append(product_id)
        
        if movement_type:
            where_conditions.append("sm.movement_type = %s")
            params.append(movement_type)
        
        if start_date:
            where_conditions.append("DATE(sm.created_at) >= %s")
            params.append(start_date)
        
        if end_date:
            where_conditions.append("DATE(sm.created_at) <= %s")
            params.append(end_date)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM stock_movements sm WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get movements
        movements_query = f"""
        SELECT sm.*, p.name as product_name, p.sku as product_sku,
               a.name as admin_name, s.name as supplier_name,
               po.order_number as purchase_order_number
        FROM stock_movements sm
        LEFT JOIN products p ON sm.product_id = p.id
        LEFT JOIN admins a ON sm.admin_id = a.id
        LEFT JOIN suppliers s ON sm.supplier_id = s.id
        LEFT JOIN purchase_orders po ON sm.reference_id = po.id AND sm.reference_type = 'purchase_order'
        WHERE {where_clause}
        ORDER BY sm.created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        movements = Database.execute_query(movements_query, params, fetch=True)
        
        # Add computed fields
        for movement in movements:
            movement['time_ago'] = get_time_ago(movement['created_at'])
            
            # Format movement description
            if movement['movement_type'] == 'restock':
                movement['description'] = f"Restocked +{movement['quantity_change']} units"
            elif movement['movement_type'] == 'sale':
                movement['description'] = f"Sale -{abs(movement['quantity_change'])} units"
            elif movement['movement_type'] == 'adjustment':
                sign = '+' if movement['quantity_change'] > 0 else ''
                movement['description'] = f"Manual adjustment {sign}{movement['quantity_change']} units"
            elif movement['movement_type'] == 'transfer':
                movement['description'] = f"Transfer {movement['quantity_change']} units"
            else:
                movement['description'] = f"{movement['quantity_change']} units"
        
        return jsonify(ResponseFormatter.paginated(movements, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@inventory_bp.route('/inventory/adjust', methods=['POST'])
@admin_required
def adjust_stock():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['product_id', 'quantity_change', 'reason']
        for field in required_fields:
            if field not in data:
                return error_response(f'{field} is required', 400)
        
        product_id = data['product_id']
        quantity_change = int(data['quantity_change'])
        reason = data['reason']
        notes = data.get('notes', '')
        
        current_admin = get_jwt_identity()
        
        # Get current product stock
        product = Database.execute_query(
            "SELECT stock_quantity, name FROM products WHERE id = %s",
            (product_id,), fetch=True
        )
        
        if not product:
            return error_response('Product not found', 404)
        
        current_stock = product[0]['stock_quantity']
        new_stock = current_stock + quantity_change
        
        if new_stock < 0:
            return error_response('Cannot reduce stock below zero', 400)
        
        # Update product stock
        Database.execute_query(
            "UPDATE products SET stock_quantity = %s, last_restocked = %s WHERE id = %s",
            (new_stock, datetime.now(), product_id)
        )
        
        # Record stock movement
        movement_id = record_stock_movement(
            product_id=product_id,
            movement_type='adjustment',
            quantity_change=quantity_change,
            reference_type='manual_adjustment',
            admin_id=current_admin['id'],
            notes=f"{reason}. {notes}".strip()
        )
        
        return success_response({
            'movement_id': movement_id,
            'previous_stock': current_stock,
            'new_stock': new_stock,
            'quantity_change': quantity_change
        }, 'Stock adjusted successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= SUPPLIER MANAGEMENT =======================

@inventory_bp.route('/inventory/suppliers', methods=['GET'])
@admin_required
def get_suppliers():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        status = request.args.get('status')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if search:
            where_conditions.append("(s.name LIKE %s OR s.email LIKE %s OR s.contact_person LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        if status:
            where_conditions.append("s.is_active = %s")
            params.append(status == 'active')
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM suppliers s WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get suppliers with stats
        suppliers_query = f"""
        SELECT s.*,
               COUNT(DISTINCT po.id) as total_orders,
               COUNT(DISTINCT CASE WHEN po.status = 'completed' THEN po.id END) as completed_orders,
               COALESCE(SUM(CASE WHEN po.status = 'completed' THEN po.total_amount ELSE 0 END), 0) as total_spent,
               MAX(po.created_at) as last_order_date
        FROM suppliers s
        LEFT JOIN purchase_orders po ON s.id = po.supplier_id
        WHERE {where_clause}
        GROUP BY s.id
        ORDER BY s.name
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        suppliers = Database.execute_query(suppliers_query, params, fetch=True)
        
        # Parse JSON fields and convert decimals
        for supplier in suppliers:
            if supplier.get('address'):
                try:
                    supplier['address'] = json.loads(supplier['address'])
                except:
                    supplier['address'] = {}
            
            supplier['total_spent'] = float(supplier['total_spent'])
            supplier['time_since_last_order'] = get_time_ago(supplier['last_order_date']) if supplier['last_order_date'] else 'Never'
        
        return jsonify(ResponseFormatter.paginated(suppliers, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@inventory_bp.route('/inventory/suppliers', methods=['POST'])
@admin_required
def create_supplier():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['name', 'contact_person', 'email']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Create supplier
        supplier_query = """
        INSERT INTO suppliers (name, contact_person, email, phone, address, 
                             payment_terms, tax_id, notes, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        supplier_id = Database.execute_query(supplier_query, (
            data['name'], data['contact_person'], data['email'],
            data.get('phone', ''), json.dumps(data.get('address', {})),
            data.get('payment_terms', ''), data.get('tax_id', ''),
            data.get('notes', ''), bool(data.get('is_active', True)), datetime.now()
        ))
        
        return success_response({
            'id': supplier_id,
            'name': data['name']
        }, 'Supplier created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= PURCHASE ORDERS =======================

@inventory_bp.route('/inventory/purchase-orders', methods=['GET'])
@admin_required
def get_purchase_orders():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        supplier_id = request.args.get('supplier_id')
        search = request.args.get('search', '').strip()
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if status:
            where_conditions.append("po.status = %s")
            params.append(status)
        
        if supplier_id:
            where_conditions.append("po.supplier_id = %s")
            params.append(supplier_id)
        
        if search:
            where_conditions.append("(po.order_number LIKE %s OR s.name LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"""
        SELECT COUNT(*) as total FROM purchase_orders po 
        LEFT JOIN suppliers s ON po.supplier_id = s.id
        WHERE {where_clause}
        """
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get purchase orders
        orders_query = f"""
        SELECT po.*, s.name as supplier_name, s.contact_person,
               (SELECT COUNT(*) FROM purchase_order_items poi WHERE poi.purchase_order_id = po.id) as item_count
        FROM purchase_orders po
        LEFT JOIN suppliers s ON po.supplier_id = s.id
        WHERE {where_clause}
        ORDER BY po.created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        orders = Database.execute_query(orders_query, params, fetch=True)
        
        # Convert decimals and add computed fields
        for order in orders:
            order['total_amount'] = float(order['total_amount'])
            order['time_ago'] = get_time_ago(order['created_at'])
            
            # Add status label and color
            status_info = {
                'draft': {'label': 'Draft', 'color': 'secondary'},
                'sent': {'label': 'Sent', 'color': 'warning'},
                'confirmed': {'label': 'Confirmed', 'color': 'info'},
                'received': {'label': 'Received', 'color': 'primary'},
                'completed': {'label': 'Completed', 'color': 'success'},
                'cancelled': {'label': 'Cancelled', 'color': 'danger'}
            }
            
            order['status_info'] = status_info.get(order['status'], {'label': 'Unknown', 'color': 'secondary'})
        
        return jsonify(ResponseFormatter.paginated(orders, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@inventory_bp.route('/inventory/purchase-orders', methods=['POST'])
@admin_required
def create_purchase_order():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['supplier_id', 'items']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        supplier_id = data['supplier_id']
        items = data['items']
        
        if not items:
            return error_response('At least one item is required', 400)
        
        current_admin = get_jwt_identity()
        
        # Generate order number
        order_number = generate_po_number()
        
        # Calculate total
        total_amount = sum(float(item['unit_cost']) * int(item['quantity']) for item in items)
        
        # Create purchase order
        po_query = """
        INSERT INTO purchase_orders (order_number, supplier_id, total_amount, status,
                                   notes, expected_delivery_date, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        po_id = Database.execute_query(po_query, (
            order_number, supplier_id, total_amount, data.get('status', 'draft'),
            data.get('notes', ''), data.get('expected_delivery_date'),
            current_admin['id'], datetime.now()
        ))
        
        # Create order items
        for item in items:
            item_query = """
            INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity, unit_cost, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """
            Database.execute_query(item_query, (
                po_id, item['product_id'], int(item['quantity']),
                float(item['unit_cost']), datetime.now()
            ))
        
        return success_response({
            'id': po_id,
            'order_number': order_number,
            'total_amount': total_amount
        }, 'Purchase order created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@inventory_bp.route('/inventory/purchase-orders/<int:po_id>/receive', methods=['POST'])
@admin_required
def receive_purchase_order():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        received_items = data.get('items', [])
        
        current_admin = get_jwt_identity()
        
        # Get purchase order
        po = Database.execute_query(
            "SELECT * FROM purchase_orders WHERE id = %s", (po_id,), fetch=True
        )
        
        if not po:
            return error_response('Purchase order not found', 404)
        
        # Process received items
        for item in received_items:
            product_id = item['product_id']
            received_qty = int(item['received_quantity'])
            
            if received_qty > 0:
                # Update product stock
                Database.execute_query(
                    "UPDATE products SET stock_quantity = stock_quantity + %s, last_restocked = %s WHERE id = %s",
                    (received_qty, datetime.now(), product_id)
                )
                
                # Record stock movement
                record_stock_movement(
                    product_id=product_id,
                    movement_type='restock',
                    quantity_change=received_qty,
                    reference_type='purchase_order',
                    reference_id=po_id,
                    admin_id=current_admin['id'],
                    notes=f"Received from PO {po[0]['order_number']}"
                )
        
        # Update purchase order status
        Database.execute_query(
            "UPDATE purchase_orders SET status = %s, received_at = %s WHERE id = %s",
            ('received', datetime.now(), po_id)
        )
        
        return success_response(message='Purchase order received successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= ANALYTICS & REPORTS =======================

@inventory_bp.route('/inventory/analytics/overview', methods=['GET'])
@admin_required
def inventory_overview():
    try:
        days = int(request.args.get('days', 30))
        
        # Stock levels summary
        stock_summary_query = """
        SELECT 
            COUNT(*) as total_products,
            SUM(CASE WHEN stock_quantity = 0 THEN 1 ELSE 0 END) as out_of_stock,
            SUM(CASE WHEN stock_quantity > 0 AND stock_quantity <= COALESCE(low_stock_threshold, 10) THEN 1 ELSE 0 END) as low_stock,
            SUM(CASE WHEN stock_quantity > COALESCE(low_stock_threshold, 10) THEN 1 ELSE 0 END) as in_stock,
            SUM(stock_quantity * price) as total_inventory_value
        FROM products 
        WHERE status = 'active'
        """
        stock_summary = Database.execute_query(stock_summary_query, fetch=True)[0]
        
        # Stock movements trends
        movements_query = """
        SELECT DATE(created_at) as date,
               SUM(CASE WHEN quantity_change > 0 THEN quantity_change ELSE 0 END) as stock_in,
               SUM(CASE WHEN quantity_change < 0 THEN ABS(quantity_change) ELSE 0 END) as stock_out
        FROM stock_movements
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY DATE(created_at)
        ORDER BY date
        """
        movements_trends = Database.execute_query(movements_query, (days,), fetch=True)
        
        # Top selling products (stock depletion)
        top_selling_query = """
        SELECT p.id, p.name, p.sku, p.stock_quantity,
               SUM(oi.quantity) as units_sold,
               SUM(oi.quantity * oi.price) as revenue
        FROM products p
        JOIN order_items oi ON p.id = oi.product_id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
              AND o.payment_status = 'paid'
        GROUP BY p.id, p.name, p.sku, p.stock_quantity
        ORDER BY units_sold DESC
        LIMIT 10
        """
        top_selling = Database.execute_query(top_selling_query, (days,), fetch=True)
        
        # Low stock alerts
        low_stock_query = """
        SELECT p.id, p.name, p.sku, p.stock_quantity, p.low_stock_threshold,
               c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.status = 'active' 
              AND p.stock_quantity <= COALESCE(p.low_stock_threshold, 10)
              AND p.stock_quantity > 0
        ORDER BY p.stock_quantity ASC
        LIMIT 20
        """
        low_stock_alerts = Database.execute_query(low_stock_query, fetch=True)
        
        # Convert decimals
        stock_summary['total_inventory_value'] = float(stock_summary['total_inventory_value'])
        
        for item in top_selling:
            item['revenue'] = float(item['revenue'])
        
        return success_response({
            'days': days,
            'stock_summary': stock_summary,
            'movements_trends': movements_trends,
            'top_selling_products': top_selling,
            'low_stock_alerts': low_stock_alerts
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@inventory_bp.route('/inventory/reports/valuation', methods=['GET'])
@admin_required
def inventory_valuation_report():
    try:
        category_id = request.args.get('category_id')
        
        # Build WHERE conditions
        where_conditions = ["p.status = 'active'"]
        params = []
        
        if category_id:
            where_conditions.append("p.category_id = %s")
            params.append(category_id)
        
        where_clause = " AND ".join(where_conditions)
        
        # Get valuation data
        valuation_query = f"""
        SELECT p.id, p.name, p.sku, p.stock_quantity, p.price,
               (p.stock_quantity * p.price) as stock_value,
               c.name as category_name,
               COALESCE(AVG(sm.unit_cost), p.price) as avg_cost,
               (p.stock_quantity * COALESCE(AVG(sm.unit_cost), p.price)) as cost_value
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN (
            SELECT poi.product_id, poi.unit_cost
            FROM purchase_order_items poi
            JOIN purchase_orders po ON poi.purchase_order_id = po.id
            WHERE po.status = 'completed'
        ) sm ON p.id = sm.product_id
        WHERE {where_clause}
        GROUP BY p.id, p.name, p.sku, p.stock_quantity, p.price, c.name
        HAVING p.stock_quantity > 0
        ORDER BY stock_value DESC
        """
        
        valuation_data = Database.execute_query(valuation_query, params, fetch=True)
        
        # Calculate totals
        total_retail_value = sum(float(item['stock_value']) for item in valuation_data)
        total_cost_value = sum(float(item['cost_value']) for item in valuation_data)
        
        # Convert decimals
        for item in valuation_data:
            item['price'] = float(item['price'])
            item['stock_value'] = float(item['stock_value'])
            item['avg_cost'] = float(item['avg_cost'])
            item['cost_value'] = float(item['cost_value'])
            item['margin'] = item['stock_value'] - item['cost_value']
            item['margin_percentage'] = ((item['price'] - item['avg_cost']) / item['price'] * 100) if item['price'] > 0 else 0
        
        return success_response({
            'valuation_data': valuation_data,
            'summary': {
                'total_products': len(valuation_data),
                'total_retail_value': total_retail_value,
                'total_cost_value': total_cost_value,
                'total_margin': total_retail_value - total_cost_value,
                'avg_margin_percentage': ((total_retail_value - total_cost_value) / total_retail_value * 100) if total_retail_value > 0 else 0
            }
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@inventory_bp.route('/inventory/reports/dead-stock', methods=['GET'])
@admin_required
def dead_stock_report():
    try:
        days_threshold = int(request.args.get('days', 90))
        
        # Find products with no sales in specified period
        dead_stock_query = """
        SELECT p.id, p.name, p.sku, p.stock_quantity, p.price,
               (p.stock_quantity * p.price) as stock_value,
               c.name as category_name,
               DATEDIFF(NOW(), MAX(o.created_at)) as days_since_last_sale,
               p.created_at as date_added,
               DATEDIFF(NOW(), p.created_at) as days_in_inventory
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN order_items oi ON p.id = oi.product_id
        LEFT JOIN orders o ON oi.order_id = o.id AND o.payment_status = 'paid'
        WHERE p.status = 'active' AND p.stock_quantity > 0
        GROUP BY p.id, p.name, p.sku, p.stock_quantity, p.price, c.name, p.created_at
        HAVING (days_since_last_sale IS NULL OR days_since_last_sale > %s)
               AND days_in_inventory > 30
        ORDER BY stock_value DESC
        """
        
        dead_stock = Database.execute_query(dead_stock_query, (days_threshold,), fetch=True)
        
        # Calculate dead stock value
        total_dead_stock_value = sum(float(item['stock_value']) for item in dead_stock)
        
        # Convert decimals
        for item in dead_stock:
            item['price'] = float(item['price'])
            item['stock_value'] = float(item['stock_value'])
            item['days_since_last_sale'] = item['days_since_last_sale'] or 999
        
        return success_response({
            'dead_stock_items': dead_stock,
            'summary': {
                'total_items': len(dead_stock),
                'total_dead_stock_value': total_dead_stock_value,
                'days_threshold': days_threshold
            }
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BULK OPERATIONS =======================

@inventory_bp.route('/inventory/bulk-update', methods=['PUT'])
@admin_required
def bulk_update_inventory():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        updates = data.get('updates', [])
        
        if not updates:
            return error_response('No updates provided', 400)
        
        current_admin = get_jwt_identity()
        updated_count = 0
        
        for update in updates:
            product_id = update.get('product_id')
            new_quantity = update.get('stock_quantity')
            
            if not product_id or new_quantity is None:
                continue
            
            # Get current stock
            current_stock = Database.execute_query(
                "SELECT stock_quantity FROM products WHERE id = %s",
                (product_id,), fetch=True
            )
            
            if not current_stock:
                continue
            
            current_qty = current_stock[0]['stock_quantity']
            quantity_change = int(new_quantity) - current_qty
            
            if quantity_change != 0:
                # Update product stock
                Database.execute_query(
                    "UPDATE products SET stock_quantity = %s, last_restocked = %s WHERE id = %s",
                    (new_quantity, datetime.now(), product_id)
                )
                
                # Record stock movement
                record_stock_movement(
                    product_id=product_id,
                    movement_type='adjustment',
                    quantity_change=quantity_change,
                    reference_type='bulk_update',
                    admin_id=current_admin['id'],
                    notes='Bulk inventory update'
                )
                
                updated_count += 1
        
        return success_response({
            'updated_count': updated_count,
            'total_processed': len(updates)
        }, f'{updated_count} products updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@inventory_bp.route('/inventory/import', methods=['POST'])
@admin_required
def import_inventory():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        if 'file' not in request.files:
            return error_response('No file provided', 400)
        
        file = request.files['file']
        if file.filename == '':
            return error_response('No file selected', 400)
        
        if not file.filename.endswith('.csv'):
            return error_response('Only CSV files are supported', 400)
        
        current_admin = get_jwt_identity()
        
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        imported_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                sku = row.get('sku', '').strip()
                stock_quantity = int(row.get('stock_quantity', 0))
                
                if not sku:
                    errors.append(f"Row {row_num}: SKU is required")
                    continue
                
                # Find product by SKU
                product = Database.execute_query(
                    "SELECT id, stock_quantity FROM products WHERE sku = %s",
                    (sku,), fetch=True
                )
                
                if not product:
                    errors.append(f"Row {row_num}: Product with SKU '{sku}' not found")
                    continue
                
                product_id = product[0]['id']
                current_qty = product[0]['stock_quantity']
                quantity_change = stock_quantity - current_qty
                
                # Update stock
                Database.execute_query(
                    "UPDATE products SET stock_quantity = %s, last_restocked = %s WHERE id = %s",
                    (stock_quantity, datetime.now(), product_id)
                )
                
                # Record movement
                if quantity_change != 0:
                    record_stock_movement(
                        product_id=product_id,
                        movement_type='adjustment',
                        quantity_change=quantity_change,
                        reference_type='csv_import',
                        admin_id=current_admin['id'],
                        notes='CSV import update'
                    )
                
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        return success_response({
            'imported_count': imported_count,
            'total_rows': row_num - 1,
            'errors': errors[:10]  # Limit errors shown
        }, f'Import completed. {imported_count} products updated')
        
    except Exception as e:
        return error_response(str(e), 500)

@inventory_bp.route('/inventory/export', methods=['GET'])
@admin_required
def export_inventory():
    try:
        format_type = request.args.get('format', 'csv')
        category_id = request.args.get('category_id')
        
        # Build WHERE conditions
        where_conditions = ["p.status = 'active'"]
        params = []
        
        if category_id:
            where_conditions.append("p.category_id = %s")
            params.append(category_id)
        
        where_clause = " AND ".join(where_conditions)
        
        # Get inventory data
        export_query = f"""
        SELECT p.id, p.name, p.sku, p.stock_quantity, p.price, p.low_stock_threshold,
               p.last_restocked, c.name as category_name,
               (p.stock_quantity * p.price) as stock_value
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE {where_clause}
        ORDER BY p.name
        """
        
        inventory_data = Database.execute_query(export_query, params, fetch=True)
        
        # Convert decimals for export
        for item in inventory_data:
            item['price'] = float(item['price'])
            item['stock_value'] = float(item['stock_value'])
        
        if format_type == 'csv':
            # Generate CSV content
            output = io.StringIO()
            fieldnames = ['sku', 'name', 'category_name', 'stock_quantity', 'price', 'stock_value', 'last_restocked']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for item in inventory_data:
                writer.writerow({
                    'sku': item['sku'],
                    'name': item['name'],
                    'category_name': item['category_name'] or '',
                    'stock_quantity': item['stock_quantity'],
                    'price': item['price'],
                    'stock_value': item['stock_value'],
                    'last_restocked': item['last_restocked'].strftime('%Y-%m-%d %H:%M:%S') if item['last_restocked'] else ''
                })
            
            csv_content = output.getvalue()
            output.close()
            
            return success_response({
                'format': 'csv',
                'filename': f'inventory_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                'content': csv_content,
                'total_records': len(inventory_data)
            })
        
        else:
            # Return JSON format
            return success_response({
                'format': 'json',
                'data': inventory_data,
                'total_records': len(inventory_data),
                'exported_at': datetime.now().isoformat()
            })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= FORECASTING =======================

@inventory_bp.route('/inventory/forecasting', methods=['GET'])
@admin_required
def inventory_forecasting():
    try:
        product_id = request.args.get('product_id')
        days_ahead = int(request.args.get('days', 30))
        
        if not product_id:
            return error_response('Product ID is required', 400)
        
        # Get historical sales data (last 90 days)
        sales_history_query = """
        SELECT DATE(o.created_at) as sale_date, SUM(oi.quantity) as quantity_sold
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE oi.product_id = %s 
              AND o.payment_status = 'paid'
              AND o.created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
        GROUP BY DATE(o.created_at)
        ORDER BY sale_date
        """
        
        sales_history = Database.execute_query(sales_history_query, (product_id,), fetch=True)
        
        if not sales_history:
            return success_response({
                'product_id': product_id,
                'forecast_days': days_ahead,
                'daily_average': 0,
                'predicted_demand': 0,
                'recommended_reorder': 0,
                'message': 'No sales history available for forecasting'
            })
        
        # Calculate moving average
        total_sold = sum(item['quantity_sold'] for item in sales_history)
        days_with_sales = len(sales_history)
        daily_average = total_sold / max(days_with_sales, 1)
        
        # Simple forecast: daily average * forecast days
        predicted_demand = daily_average * days_ahead
        
        # Get current stock
        current_stock = Database.execute_query(
            "SELECT stock_quantity, low_stock_threshold FROM products WHERE id = %s",
            (product_id,), fetch=True
        )[0]
        
        current_qty = current_stock['stock_quantity']
        low_stock_threshold = current_stock['low_stock_threshold'] or 10
        
        # Calculate recommended reorder quantity
        safety_stock = low_stock_threshold
        recommended_reorder = max(0, int(predicted_demand + safety_stock - current_qty))
        
        # Calculate when stock will run out
        if daily_average > 0:
            days_until_stockout = current_qty / daily_average
        else:
            days_until_stockout = 999
        
        return success_response({
            'product_id': int(product_id),
            'current_stock': current_qty,
            'forecast_days': days_ahead,
            'daily_average_sales': round(daily_average, 2),
            'predicted_demand': int(predicted_demand),
            'recommended_reorder': recommended_reorder,
            'days_until_stockout': round(days_until_stockout, 1),
            'reorder_needed': recommended_reorder > 0,
            'sales_history_days': days_with_sales,
            'total_historical_sales': total_sold
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= UTILITY FUNCTIONS =======================

def record_stock_movement(product_id, movement_type, quantity_change, reference_type, 
                         reference_id=None, supplier_id=None, admin_id=None, notes=''):
    """Record stock movement in history"""
    try:
        movement_query = """
        INSERT INTO stock_movements (product_id, movement_type, quantity_change, reference_type,
                                   reference_id, supplier_id, admin_id, notes, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        return Database.execute_query(movement_query, (
            product_id, movement_type, quantity_change, reference_type,
            reference_id, supplier_id, admin_id, notes, datetime.now()
        ))
        
    except Exception as e:
        return None

def generate_po_number():
    """Generate unique purchase order number"""
    timestamp = datetime.now().strftime('%Y%m%d')
    unique_id = str(uuid.uuid4())[:6].upper()
    return f"PO-{timestamp}-{unique_id}"

def get_time_ago(timestamp):
    """Calculate human-readable time ago"""
    try:
        if not timestamp:
            return "Never"
        
        now = datetime.now()
        diff = now - timestamp
        
        if diff.days > 30:
            return f"{diff.days // 30} month{'s' if diff.days // 30 > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    except:
        return "Unknown"

# ======================= INVENTORY STATISTICS =======================

@inventory_bp.route('/inventory/stats', methods=['GET'])
@admin_required
def get_inventory_stats():
    try:
        # Overall inventory statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_products,
            SUM(CASE WHEN stock_quantity > 0 THEN 1 ELSE 0 END) as products_in_stock,
            SUM(CASE WHEN stock_quantity = 0 THEN 1 ELSE 0 END) as out_of_stock_products,
            SUM(CASE WHEN stock_quantity <= COALESCE(low_stock_threshold, 10) AND stock_quantity > 0 THEN 1 ELSE 0 END) as low_stock_products,
            SUM(stock_quantity) as total_units,
            SUM(stock_quantity * price) as total_inventory_value,
            AVG(stock_quantity) as avg_stock_per_product
        FROM products
        WHERE status = 'active'
        """
        
        stats = Database.execute_query(stats_query, fetch=True)[0]
        
        # Recent stock movements (last 7 days)
        recent_movements_query = """
        SELECT 
            COUNT(*) as total_movements,
            SUM(CASE WHEN quantity_change > 0 THEN quantity_change ELSE 0 END) as stock_additions,
            SUM(CASE WHEN quantity_change < 0 THEN ABS(quantity_change) ELSE 0 END) as stock_reductions,
            COUNT(DISTINCT product_id) as products_affected
        FROM stock_movements
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """
        
        recent_movements = Database.execute_query(recent_movements_query, fetch=True)[0]
        
        # Purchase order statistics
        po_stats_query = """
        SELECT 
            COUNT(*) as total_purchase_orders,
            SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft_orders,
            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent_orders,
            SUM(CASE WHEN status = 'received' THEN 1 ELSE 0 END) as received_orders,
            SUM(total_amount) as total_po_value
        FROM purchase_orders
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        
        po_stats = Database.execute_query(po_stats_query, fetch=True)[0]
        
        # Convert decimals to float
        stats['total_inventory_value'] = float(stats['total_inventory_value'])
        stats['avg_stock_per_product'] = float(stats['avg_stock_per_product'])
        po_stats['total_po_value'] = float(po_stats['total_po_value']) if po_stats['total_po_value'] else 0
        
        # Combine all stats
        combined_stats = {**stats, **recent_movements, **po_stats}
        
        return success_response(combined_stats)
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= LOW STOCK ALERTS =======================

@inventory_bp.route('/inventory/alerts/low-stock', methods=['GET'])
@admin_required
def get_low_stock_alerts():
    try:
        threshold = int(request.args.get('threshold', 10))
        
        alerts_query = """
        SELECT p.id, p.name, p.sku, p.stock_quantity, p.low_stock_threshold,
               p.price, c.name as category_name,
               (SELECT SUM(oi.quantity) FROM order_items oi 
                JOIN orders o ON oi.order_id = o.id 
                WHERE oi.product_id = p.id AND o.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                AND o.payment_status = 'paid') as sales_last_30d
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.status = 'active' 
              AND p.stock_quantity <= COALESCE(p.low_stock_threshold, %s)
              AND p.stock_quantity >= 0
        ORDER BY p.stock_quantity ASC, sales_last_30d DESC
        """
        
        alerts = Database.execute_query(alerts_query, (threshold,), fetch=True)
        
        # Add urgency levels and recommendations
        for alert in alerts:
            alert['price'] = float(alert['price'])
            alert['sales_last_30d'] = alert['sales_last_30d'] or 0
            
            # Calculate urgency
            if alert['stock_quantity'] == 0:
                alert['urgency'] = 'critical'
                alert['urgency_label'] = 'Out of Stock'
                alert['urgency_color'] = 'danger'
            elif alert['stock_quantity'] <= 5:
                alert['urgency'] = 'high'
                alert['urgency_label'] = 'Very Low Stock'
                alert['urgency_color'] = 'warning'
            else:
                alert['urgency'] = 'medium'
                alert['urgency_label'] = 'Low Stock'
                alert['urgency_color'] = 'info'
            
            # Calculate recommended reorder quantity
            if alert['sales_last_30d'] > 0:
                daily_sales = alert['sales_last_30d'] / 30
                alert['recommended_reorder'] = max(50, int(daily_sales * 30))  # 30 days supply
            else:
                alert['recommended_reorder'] = 25  # Default minimum
        
        return success_response({
            'alerts': alerts,
            'total_alerts': len(alerts),
            'critical_count': len([a for a in alerts if a['urgency'] == 'critical']),
            'high_count': len([a for a in alerts if a['urgency'] == 'high']),
            'medium_count': len([a for a in alerts if a['urgency'] == 'medium'])
        })
        
    except Exception as e:
        return error_response(str(e), 500)