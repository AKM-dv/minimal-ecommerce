from flask import Blueprint, request
from datetime import datetime, timedelta

# Import our modules
from models import Database
from utils import admin_required, success_response, error_response

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__)

# ======================= DASHBOARD ROUTES =======================

@dashboard_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def dashboard_stats():
    try:
        today = datetime.now().date()
        
        # Real-time order count
        today_orders_query = "SELECT COUNT(*) as count FROM orders WHERE DATE(created_at) = %s"
        today_orders = Database.execute_query(today_orders_query, (today,), fetch=True)[0]['count']
        
        week_orders_query = "SELECT COUNT(*) as count FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        week_orders = Database.execute_query(week_orders_query, fetch=True)[0]['count']
        
        month_orders_query = "SELECT COUNT(*) as count FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        month_orders = Database.execute_query(month_orders_query, fetch=True)[0]['count']
        
        # Total revenue analytics
        today_revenue_query = "SELECT COALESCE(SUM(total_amount), 0) as revenue FROM orders WHERE DATE(created_at) = %s AND payment_status = 'paid'"
        today_revenue = Database.execute_query(today_revenue_query, (today,), fetch=True)[0]['revenue']
        
        week_revenue_query = "SELECT COALESCE(SUM(total_amount), 0) as revenue FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) AND payment_status = 'paid'"
        week_revenue = Database.execute_query(week_revenue_query, fetch=True)[0]['revenue']
        
        month_revenue_query = "SELECT COALESCE(SUM(total_amount), 0) as revenue FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) AND payment_status = 'paid'"
        month_revenue = Database.execute_query(month_revenue_query, fetch=True)[0]['revenue']
        
        # Customer count and new registrations
        total_customers_query = "SELECT COUNT(*) as count FROM customers WHERE is_active = 1"
        total_customers = Database.execute_query(total_customers_query, fetch=True)[0]['count']
        
        new_customers_today_query = "SELECT COUNT(*) as count FROM customers WHERE DATE(created_at) = %s"
        new_customers_today = Database.execute_query(new_customers_today_query, (today,), fetch=True)[0]['count']
        
        new_customers_week_query = "SELECT COUNT(*) as count FROM customers WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        new_customers_week = Database.execute_query(new_customers_week_query, fetch=True)[0]['count']
        
        new_customers_month_query = "SELECT COUNT(*) as count FROM customers WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        new_customers_month = Database.execute_query(new_customers_month_query, fetch=True)[0]['count']
        
        # Product inventory status
        total_products_query = "SELECT COUNT(*) as count FROM products WHERE status = 'active'"
        total_products = Database.execute_query(total_products_query, fetch=True)[0]['count']
        
        low_stock_query = "SELECT COUNT(*) as count FROM products WHERE stock_quantity <= 10 AND status = 'active'"
        low_stock_count = Database.execute_query(low_stock_query, fetch=True)[0]['count']
        
        out_of_stock_query = "SELECT COUNT(*) as count FROM products WHERE stock_quantity = 0 AND status = 'active'"
        out_of_stock_count = Database.execute_query(out_of_stock_query, fetch=True)[0]['count']
        
        return success_response({
            'orders': {
                'today': today_orders,
                'week': week_orders,
                'month': month_orders
            },
            'revenue': {
                'today': float(today_revenue),
                'week': float(week_revenue),
                'month': float(month_revenue)
            },
            'customers': {
                'total': total_customers,
                'new_today': new_customers_today,
                'new_week': new_customers_week,
                'new_month': new_customers_month
            },
            'inventory': {
                'total_products': total_products,
                'low_stock': low_stock_count,
                'out_of_stock': out_of_stock_count
            }
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@dashboard_bp.route('/dashboard/revenue-analytics', methods=['GET'])
@admin_required
def revenue_analytics():
    try:
        # Get date range from query params
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        period = request.args.get('period', 'daily')  # daily, weekly, monthly
        
        # Default to last 30 days if no date range provided
        if not start_date or not end_date:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
        
        if period == 'daily':
            revenue_query = """
            SELECT DATE(created_at) as date, COALESCE(SUM(total_amount), 0) as revenue
            FROM orders 
            WHERE DATE(created_at) BETWEEN %s AND %s AND payment_status = 'paid'
            GROUP BY DATE(created_at)
            ORDER BY date
            """
        elif period == 'weekly':
            revenue_query = """
            SELECT YEARWEEK(created_at, 1) as week, COALESCE(SUM(total_amount), 0) as revenue
            FROM orders 
            WHERE DATE(created_at) BETWEEN %s AND %s AND payment_status = 'paid'
            GROUP BY YEARWEEK(created_at, 1)
            ORDER BY week
            """
        else:  # monthly
            revenue_query = """
            SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COALESCE(SUM(total_amount), 0) as revenue
            FROM orders 
            WHERE DATE(created_at) BETWEEN %s AND %s AND payment_status = 'paid'
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month
            """
        
        revenue_data = Database.execute_query(revenue_query, (start_date, end_date), fetch=True)
        
        # Convert Decimal to float for JSON serialization
        for item in revenue_data:
            item['revenue'] = float(item['revenue'])
        
        return success_response({
            'period': period,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'data': revenue_data
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@dashboard_bp.route('/dashboard/low-stock-alerts', methods=['GET'])
@admin_required
def low_stock_alerts():
    try:
        threshold = int(request.args.get('threshold', 10))
        
        low_stock_query = """
        SELECT p.id, p.name, p.sku, p.stock_quantity, p.price, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.stock_quantity <= %s AND p.status = 'active'
        ORDER BY p.stock_quantity ASC, p.name
        """
        
        low_stock_products = Database.execute_query(low_stock_query, (threshold,), fetch=True)
        
        # Convert Decimal to float
        for product in low_stock_products:
            product['price'] = float(product['price'])
        
        return success_response({
            'threshold': threshold,
            'products': low_stock_products,
            'count': len(low_stock_products)
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@dashboard_bp.route('/dashboard/top-selling-products', methods=['GET'])
@admin_required
def top_selling_products():
    try:
        limit = int(request.args.get('limit', 10))
        days = int(request.args.get('days', 30))
        
        top_products_query = """
        SELECT p.id, p.name, p.sku, p.price, 
               SUM(oi.quantity) as total_sold,
               SUM(oi.quantity * oi.price) as total_revenue,
               c.name as category_name
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN orders o ON oi.order_id = o.id
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) 
              AND o.payment_status = 'paid'
        GROUP BY p.id, p.name, p.sku, p.price, c.name
        ORDER BY total_sold DESC
        LIMIT %s
        """
        
        top_products = Database.execute_query(top_products_query, (days, limit), fetch=True)
        
        # Convert Decimal to float
        for product in top_products:
            product['price'] = float(product['price'])
            product['total_revenue'] = float(product['total_revenue'])
        
        return success_response({
            'days': days,
            'products': top_products
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@dashboard_bp.route('/dashboard/order-status-distribution', methods=['GET'])
@admin_required
def order_status_distribution():
    try:
        days = int(request.args.get('days', 30))
        
        status_query = """
        SELECT status, COUNT(*) as count
        FROM orders
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY status
        ORDER BY count DESC
        """
        
        status_data = Database.execute_query(status_query, (days,), fetch=True)
        
        return success_response({
            'days': days,
            'distribution': status_data
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@dashboard_bp.route('/dashboard/payment-method-stats', methods=['GET'])
@admin_required
def payment_method_stats():
    try:
        days = int(request.args.get('days', 30))
        
        payment_query = """
        SELECT payment_method, 
               COUNT(*) as order_count,
               SUM(total_amount) as total_amount
        FROM orders
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) 
              AND payment_status = 'paid'
              AND payment_method IS NOT NULL
        GROUP BY payment_method
        ORDER BY total_amount DESC
        """
        
        payment_data = Database.execute_query(payment_query, (days,), fetch=True)
        
        # Convert Decimal to float
        for item in payment_data:
            item['total_amount'] = float(item['total_amount'])
        
        return success_response({
            'days': days,
            'payment_methods': payment_data
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@dashboard_bp.route('/dashboard/return-refund-rate', methods=['GET'])
@admin_required
def return_refund_rate():
    try:
        days = int(request.args.get('days', 30))
        
        # Total orders
        total_orders_query = """
        SELECT COUNT(*) as total FROM orders 
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        total_orders = Database.execute_query(total_orders_query, (days,), fetch=True)[0]['total']
        
        # Returned orders
        returned_orders_query = """
        SELECT COUNT(*) as returned FROM orders 
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) AND status = 'returned'
        """
        returned_orders = Database.execute_query(returned_orders_query, (days,), fetch=True)[0]['returned']
        
        # Refunded orders
        refunded_orders_query = """
        SELECT COUNT(*) as refunded FROM orders 
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) AND payment_status = 'refunded'
        """
        refunded_orders = Database.execute_query(refunded_orders_query, (days,), fetch=True)[0]['refunded']
        
        # Calculate rates
        return_rate = (returned_orders / total_orders * 100) if total_orders > 0 else 0
        refund_rate = (refunded_orders / total_orders * 100) if total_orders > 0 else 0
        
        return success_response({
            'days': days,
            'total_orders': total_orders,
            'returned_orders': returned_orders,
            'refunded_orders': refunded_orders,
            'return_rate': round(return_rate, 2),
            'refund_rate': round(refund_rate, 2)
        })
        
    except Exception as e:
        return error_response(str(e), 500)