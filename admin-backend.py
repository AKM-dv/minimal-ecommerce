# Import and register blueprints
from admin.auth import auth_bp
from admin.dashboard import dashboard_bp
from admin.config import config_bp
from admin.store import store_bp
from admin.products import products_bp
from admin.categories import categories_bp
from admin.orders import orders_bp
from admin.customers import customers_bp
from admin.integrations import integrations_bp
from admin.blog import blog_bp
from admin.blog_comments import blog_comments_bp
from admin.coupons import coupons_bp

# Register all blueprints with URL prefix
app.register_blueprint(auth_bp, url_prefix='/admin/api/v1')
app.register_blueprint(dashboard_bp, url_prefix='/admin/api/v1')
app.register_blueprint(config_bp, url_prefix='/admin/api/v1')
app.register_blueprint(store_bp, url_prefix='/admin/api/v1')
app.register_blueprint(products_bp, url_prefix='/admin/api/v1')
app.register_blueprint(categories_bp, url_prefix='/admin/api/v1')
app.register_blueprint(orders_bp, url_prefix='/admin/api/v1')
app.register_blueprint(customers_bp, url_prefix='/admin/api/v1')
app.register_blueprint(integrations_bp, url_prefix='/admin/api/v1')
app.register_blueprint(blog_bp, url_prefix='/admin/api/v1')
app.register_blueprint(blog_comments_bp, url_prefix='/admin/api/v1')
app.register_blueprint(coupons_bp, url_prefix='/admin/api/v1')

# Register public blog endpoints (without admin prefix for public access)
# These endpoints are for frontend blog functionality (tracking views, shares, comments)
from flask import Blueprint

# Create a separate blueprint for public endpoints
public_bp = Blueprint('public', __name__)

# Import specific public routes from blog_bp
@public_bp.route('/blog/posts/<int:post_id>/track-view', methods=['POST'])
def track_view(post_id):
    from admin.blog import track_blog_view
    return track_blog_view(post_id)

@public_bp.route('/blog/posts/<int:post_id>/share/<platform>', methods=['POST'])
def track_share(post_id, platform):
    from admin.blog import track_social_share
    return track_social_share(post_id, platform)

@public_bp.route('/blog/rss', methods=['GET'])
def rss_feed():
    from admin.blog import generate_rss_feed
    return generate_rss_feed()

# Add public coupon endpoints
@public_bp.route('/coupons/apply', methods=['POST'])
def apply_coupon():
    from admin.coupons import validate_coupon_code
    from utils import success_response, error_response, get_request_data
    
    try:
        data = get_request_data()
        code = data.get('code', '').strip().upper()
        customer_id = data.get('customer_id')
        cart_items = data.get('cart_items', [])
        
        if not code:
            return error_response('Coupon code is required', 400)
        
        validation_result = validate_coupon_code(code, customer_id, cart_items)
        
        if validation_result['valid']:
            return success_response({
                'applied': True,
                'coupon': validation_result['coupon'],
                'discount': validation_result['discount_info']
            }, 'Coupon applied successfully')
        else:
            return error_response(validation_result['error'], 400)
            
    except Exception as e:
        return error_response('Error applying coupon', 500)

@public_bp.route('/coupons/eligible', methods=['GET'])
def get_eligible_coupons():
    from admin.coupons import get_applicable_coupons_for_customer
    from utils import success_response, error_response
    from flask import request
    
    try:
        customer_id = request.args.get('customer_id')
        if not customer_id:
            return error_response('Customer ID is required', 400)
        
        applicable_coupons = get_applicable_coupons_for_customer(int(customer_id))
        
        # Format coupons for public response
        formatted_coupons = []
        for coupon in applicable_coupons:
            formatted_coupons.append({
                'code': coupon['code'],
                'name': coupon['name'],
                'description': coupon['description'],
                'type': coupon['type'],
                'value': float(coupon['value']),
                'minimum_amount': float(coupon['minimum_amount']),
                'valid_until': coupon['valid_until'].isoformat() if coupon['valid_until'] else None
            })
        
        return success_response({
            'coupons': formatted_coupons,
            'count': len(formatted_coupons)
        })
        
    except Exception as e:
        return error_response('Error fetching eligible coupons', 500)

@public_bp.route('/flash-sales/active', methods=['GET'])
def get_active_flash_sales():
    from models import Database
    from utils import success_response, error_response
    from datetime import datetime
    
    try:
        # Get active flash sales
        sales_query = """
        SELECT fs.*, 
               TIMESTAMPDIFF(SECOND, NOW(), fs.end_time) as seconds_remaining
        FROM flash_sales fs
        WHERE fs.is_active = 1 
        AND fs.start_time <= NOW() 
        AND fs.end_time > NOW()
        ORDER BY fs.end_time ASC
        """
        
        flash_sales = Database.execute_query(sales_query, fetch=True)
        
        # Format for public response
        formatted_sales = []
        for sale in flash_sales:
            formatted_sales.append({
                'id': sale['id'],
                'name': sale['name'],
                'description': sale['description'],
                'discount_type': sale['discount_type'],
                'discount_value': float(sale['discount_value']),
                'max_discount_amount': float(sale['max_discount_amount']) if sale['max_discount_amount'] else None,
                'target_type': sale['target_type'],
                'banner_text': sale['banner_text'],
                'banner_color': sale['banner_color'],
                'end_time': sale['end_time'].isoformat(),
                'seconds_remaining': max(0, sale['seconds_remaining']),
                'usage_limit': sale['usage_limit'],
                'used_count': sale['used_count']
            })
        
        return success_response({
            'flash_sales': formatted_sales,
            'count': len(formatted_sales)
        })
        
    except Exception as e:
        return error_response('Error fetching active flash sales', 500)

# Register public endpoints
app.register_blueprint(public_bp, url_prefix='/api/v1')from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import os

# Import configuration
from config import Config

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
CORS(app, origins=["http://localhost:3000"])  # React admin frontend
jwt = JWTManager(app)

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Serve uploaded files
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Import and register blueprints
from admin.auth import auth_bp
from admin.dashboard import dashboard_bp
from admin.config import config_bp
from admin.store import store_bp
from admin.products import products_bp
from admin.categories import categories_bp
from admin.orders import orders_bp
from admin.customers import customers_bp
from admin.integrations import integrations_bp
from admin.blog import blog_bp
from admin.blog_comments import blog_comments_bp

# Register all blueprints with URL prefix
app.register_blueprint(auth_bp, url_prefix='/admin/api/v1')
app.register_blueprint(dashboard_bp, url_prefix='/admin/api/v1')
app.register_blueprint(config_bp, url_prefix='/admin/api/v1')
app.register_blueprint(store_bp, url_prefix='/admin/api/v1')
app.register_blueprint(products_bp, url_prefix='/admin/api/v1')
app.register_blueprint(categories_bp, url_prefix='/admin/api/v1')
app.register_blueprint(orders_bp, url_prefix='/admin/api/v1')
app.register_blueprint(customers_bp, url_prefix='/admin/api/v1')
app.register_blueprint(integrations_bp, url_prefix='/admin/api/v1')
app.register_blueprint(blog_bp, url_prefix='/admin/api/v1')
app.register_blueprint(blog_comments_bp, url_prefix='/admin/api/v1')

# Register public blog endpoints (without admin prefix for public access)
# These endpoints are for frontend blog functionality (tracking views, shares, comments)
from flask import Blueprint

# Create a separate blueprint for public blog endpoints
public_blog_bp = Blueprint('public_blog', __name__)

# Import specific public routes from blog_bp
@public_blog_bp.route('/blog/posts/<int:post_id>/track-view', methods=['POST'])
def track_view(post_id):
    from admin.blog import track_blog_view
    return track_blog_view(post_id)

@public_blog_bp.route('/blog/posts/<int:post_id>/share/<platform>', methods=['POST'])
def track_share(post_id, platform):
    from admin.blog import track_social_share
    return track_social_share(post_id, platform)

@public_blog_bp.route('/blog/rss', methods=['GET'])
def rss_feed():
    from admin.blog import generate_rss_feed
    return generate_rss_feed()

# Register public blog endpoints
app.register_blueprint(public_blog_bp, url_prefix='/api/v1')
app.register_blueprint(public_blog_bp, url_prefix='/api/v1')

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    from utils import success_response
    return success_response({
        'status': 'healthy',
        'service': 'E-commerce Admin API',
        'version': '1.0.0',
        'endpoints': {
            'admin': '/admin/api/v1',
            'public': '/api/v1',
            'uploads': '/uploads'
        }
    }, 'API is running successfully')

# API information endpoint
@app.route('/admin/api/v1/info', methods=['GET'])
def api_info():
    from utils import success_response
    return success_response({
        'name': 'E-commerce Admin API',
        'version': '1.0.0',
        'description': 'Comprehensive e-commerce administration backend',
        'modules': [
            'Authentication & Authorization',
            'Dashboard Analytics',
            'Site Configuration',
            'Store Management',
            'Product Management',
            'Category Management', 
            'Order Management',
            'Customer Management',
            'Blog Management',
            'API Integrations'
        ],
        'features': {
            'blog': {
                'posts': 'Full CRUD with rich text editing',
                'comments': 'Advanced moderation system with spam detection',
                'threaded_comments': 'Reply system with nested conversations',
                'moderation_queue': 'Streamlined comment approval workflow',
                'analytics': 'Views, engagement, and performance tracking',
                'seo': 'Automated SEO scoring and optimization',
                'scheduling': 'Post scheduling and publishing',
                'categories_tags': 'Flexible categorization and tagging',
                'newsletter': 'Subscriber management',
                'rss': 'Automated RSS feed generation',
                'social_sharing': 'Social media share tracking',
            'coupons_discounts': {
                'percentage_discounts': 'Percentage-based discount coupons',
                'fixed_amount_discounts': 'Fixed amount discount coupons',
                'buy_x_get_y': 'Buy X Get Y promotional offers',
                'free_shipping': 'Free shipping coupons',
                'customer_targeting': 'Customer group and individual targeting',
                'product_targeting': 'Product and category-specific discounts',
                'usage_limits': 'Global and per-customer usage restrictions',
                'time_based_offers': 'Flash sales and scheduled promotions',
                'bulk_discounts': 'Quantity and amount-based bulk discounts',
                'first_buyer_promos': 'New customer welcome offers',
                'code_generation': 'Automated coupon code generation',
                'analytics': 'ROI tracking and performance analytics',
                'bulk_operations': 'Mass coupon management operations'
            },
            'integrations': {
                'payment': 'Razorpay, PhonePe support',
                'shipping': 'Shiprocket integration',
                'webhooks': 'Real-time event handling',
                'security': 'Encrypted API key storage'
            },
            'analytics': {
                'dashboard': 'Real-time business metrics',
                'customers': 'Segmentation and lifetime value',
                'products': 'Inventory and sales analytics',
                'orders': 'Order lifecycle tracking'
            }
        }
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    from utils import error_response
    return error_response('Endpoint not found', 404)

@app.errorhandler(500)
def internal_error(error):
    from utils import error_response
    return error_response('Internal server error', 500)

@app.errorhandler(400)
def bad_request(error):
    from utils import error_response
    return error_response('Bad request', 400)

@app.errorhandler(401)
def unauthorized(error):
    from utils import error_response
    return error_response('Unauthorized access', 401)

@app.errorhandler(403)
def forbidden(error):
    from utils import error_response
    return error_response('Access forbidden', 403)

@app.errorhandler(405)
def method_not_allowed(error):
    from utils import error_response
    return error_response('Method not allowed', 405)

# JWT error handlers
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    from utils import error_response
    return error_response('Token has expired', 401)

@jwt.invalid_token_loader
def invalid_token_callback(error):
    from utils import error_response
    return error_response('Invalid token', 401)

@jwt.unauthorized_loader
def missing_token_callback(error):
    from utils import error_response
    return error_response('Authorization token is required', 401)

# Request middleware for logging (optional)
@app.before_request
def before_request():
    """Log requests for debugging (optional)"""
    pass

@app.after_request
def after_request(response):
    """Add security headers and CORS"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# Development configuration
if __name__ == '__main__':
    # Check if all required environment variables are set
    required_env_vars = ['DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file or environment configuration")
    
    # Print startup information
    print("=" * 60)
    print("🚀 E-COMMERCE ADMIN API STARTING")
    print("=" * 60)
    print(f"📡 Admin Panel: http://localhost:5001/admin/api/v1")
    print(f"🌐 Public API: http://localhost:5001/api/v1")
    print(f"📊 Health Check: http://localhost:5001/health")
    print(f"📁 File Uploads: http://localhost:5001/uploads/")
    print(f"📝 API Info: http://localhost:5001/admin/api/v1/info")
    print("=" * 60)
    print("🔧 Available Modules:")
    print("   • Authentication & Authorization")
    print("   • Dashboard Analytics") 
    print("   • Site Configuration")
    print("   • Store Management")
    print("   • Product Management")
    print("   • Category Management")
    print("   • Order Management")
    print("   • Customer Management")
    print("   • Blog Management")
    print("   • Blog Comments Management")
    print("   • Coupons & Discounts (NEW)")
    print("   • API Integrations")
    print("=" * 60)
    print("💰 Coupons & Discounts Features:")
    print("   • Percentage & fixed amount discounts")
    print("   • Minimum/maximum order requirements")
    print("   • Usage limits & customer restrictions")
    print("   • Product & category targeting")
    print("   • Time-based offers (flash sales)")
    print("   • First-time buyer promotions")
    print("   • Bulk purchase discounts")
    print("   • Buy X Get Y offers")
    print("   • Customer group targeting")
    print("   • Coupon code generation")
    print("   • Advanced analytics & ROI tracking")
    print("   • Bulk operations & management")
    print("   • Auto-apply & stackable coupons")
    print("=" * 60)
    print("📝 Blog Features:")
    print("   • Rich text editor support")
    print("   • Comment moderation system")
    print("   • Threaded comments & replies")
    print("   • Spam detection & filtering")
    print("   • Analytics & engagement tracking")
    print("   • SEO optimization scoring")
    print("   • Post scheduling")
    print("   • Categories & tags management")
    print("   • Newsletter subscriber management")
    print("   • RSS feed generation")
    print("   • Social media share tracking")
    print("   • Comment moderation queue")
    print("   • Bulk comment operations")
    print("=" * 60)
    
    # Run the application
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=5001,
        threaded=True
    )