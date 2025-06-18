from flask import Flask, jsonify, Blueprint
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
from admin.coupons import coupons_bp
from admin.product_reviews import product_reviews_bp
from admin.inventory import inventory_bp
from admin.seo import seo_bp  # Import SEO blueprint

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
app.register_blueprint(product_reviews_bp, url_prefix='/admin/api/v1')
app.register_blueprint(inventory_bp, url_prefix='/admin/api/v1')
app.register_blueprint(seo_bp, url_prefix='/admin/api/v1')  # Register SEO blueprint

# Create a separate blueprint for public endpoints
public_bp = Blueprint('public', __name__)

# ======================= PUBLIC BLOG ENDPOINTS =======================

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

# ======================= PUBLIC COUPON ENDPOINTS =======================

@public_bp.route('/coupons/apply', methods=['POST'])
def apply_coupon():
    from admin.coupons import validate_coupon_code
    from utils.response_formatter import success_response, error_response
    from utils.helpers import get_request_data
    
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
                'discount': validation_result.get('discount_info')
            }, 'Coupon applied successfully')
        else:
            return error_response(validation_result['error'], 400)
            
    except Exception as e:
        return error_response('Error applying coupon', 500)

@public_bp.route('/coupons/remove', methods=['POST'])
def remove_coupon():
    from utils.response_formatter import success_response, error_response
    
    try:
        # In a real implementation, you'd remove the coupon from the cart session
        return success_response({
            'removed': True
        }, 'Coupon removed successfully')
        
    except Exception as e:
        return error_response('Error removing coupon', 500)

@public_bp.route('/coupons/eligible', methods=['GET'])
def get_eligible_coupons():
    from admin.coupons import get_applicable_coupons_for_customer
    from utils.response_formatter import success_response, error_response
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
    from utils.database import Database
    from utils.response_formatter import success_response, error_response
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

@public_bp.route('/bulk-discounts/calculate', methods=['POST'])
def calculate_bulk_discounts():
    from utils.database import Database
    from utils.response_formatter import success_response, error_response
    from utils.helpers import get_request_data
    import json
    
    try:
        data = get_request_data()
        cart_items = data.get('cart_items', [])
        
        if not cart_items:
            return success_response({'discount_amount': 0})
        
        # Get active bulk discount rules
        rules_query = """
        SELECT * FROM bulk_discount_rules 
        WHERE is_active = 1 
        ORDER BY created_at DESC
        """
        rules = Database.execute_query(rules_query, fetch=True)
        
        total_discount = 0
        applied_rules = []
        
        for rule in rules:
            try:
                tiers = json.loads(rule['tiers'])
                
                if rule['rule_type'] == 'quantity_based':
                    total_qty = sum(int(item['quantity']) for item in cart_items)
                    
                    # Find applicable tier
                    applicable_tier = None
                    for tier in sorted(tiers, key=lambda x: x['min_qty'], reverse=True):
                        if total_qty >= tier['min_qty']:
                            applicable_tier = tier
                            break
                    
                    if applicable_tier:
                        cart_total = sum(float(item['price']) * int(item['quantity']) for item in cart_items)
                        tier_discount = cart_total * (applicable_tier['discount'] / 100)
                        total_discount += tier_discount
                        applied_rules.append({
                            'rule_name': rule['name'],
                            'tier': applicable_tier,
                            'discount_amount': tier_discount
                        })
                
                elif rule['rule_type'] == 'amount_based':
                    cart_total = sum(float(item['price']) * int(item['quantity']) for item in cart_items)
                    
                    # Find applicable tier
                    applicable_tier = None
                    for tier in sorted(tiers, key=lambda x: x['min_amount'], reverse=True):
                        if cart_total >= tier['min_amount']:
                            applicable_tier = tier
                            break
                    
                    if applicable_tier:
                        tier_discount = cart_total * (applicable_tier['discount'] / 100)
                        total_discount += tier_discount
                        applied_rules.append({
                            'rule_name': rule['name'],
                            'tier': applicable_tier,
                            'discount_amount': tier_discount
                        })
                        
            except:
                continue
        
        return success_response({
            'discount_amount': round(total_discount, 2),
            'applied_rules': applied_rules
        })
        
    except Exception as e:
        return error_response('Error calculating bulk discounts', 500)

# ======================= PUBLIC SEO ENDPOINTS =======================

@public_bp.route('/robots.txt', methods=['GET'])
def serve_robots_txt():
    """Serve robots.txt file for SEO"""
    from admin.seo import serve_robots_txt
    return serve_robots_txt()

@public_bp.route('/sitemap.xml', methods=['GET'])
def serve_sitemap():
    """Serve sitemap.xml file for SEO"""
    from admin.seo import serve_sitemap
    return serve_sitemap()

# Register public endpoints
app.register_blueprint(public_bp, url_prefix='/api/v1')

# ======================= MAIN ENDPOINTS =======================

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    from utils.response_formatter import success_response
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
    from utils.response_formatter import success_response
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
            'Coupons & Discounts',
            'Product Reviews',
            'Inventory Management',
            'SEO Management',  # Added SEO module
            'API Integrations'
        ],
        'features': {
            'seo_management': {
                'meta_tags': 'Complete meta tags management (title, description, keywords)',
                'open_graph': 'Open Graph and Twitter Card meta tags',
                'structured_data': 'Schema.org structured data support',
                'robots_txt': 'Dynamic robots.txt generation and management',
                'sitemap_xml': 'Automated XML sitemap generation',
                'keyword_tracking': 'SEO keyword monitoring and ranking',
                'page_audits': 'Automated SEO page auditing and scoring',
                'recommendations': 'AI-powered SEO optimization suggestions',
                'canonical_urls': 'Canonical URL management for duplicate content',
                'robots_directives': 'Page-level robots directive control',
                'content_analysis': 'SEO content analysis and optimization',
                'competitor_tracking': 'Competitor SEO monitoring',
                'backlink_analysis': 'Backlink tracking and analysis',
                'technical_seo': 'Technical SEO audit and recommendations'
            },
            'inventory_management': {
                'real_time_tracking': 'Live stock level monitoring across all products',
                'movement_history': 'Complete audit trail of all stock movements',
                'low_stock_alerts': 'Automated alerts for products below threshold',
                'bulk_operations': 'Mass inventory updates and adjustments',
                'import_export': 'CSV import/export for inventory data',
                'supplier_management': 'Complete supplier database and relationships',
                'purchase_orders': 'Full PO lifecycle from creation to receiving',
                'stock_adjustments': 'Manual adjustments with approval workflow',
                'valuation_reports': 'Inventory valuation and margin analysis',
                'dead_stock_analysis': 'Identification of slow-moving inventory',
                'abc_analysis': 'Automated ABC classification for inventory optimization',
                'forecasting': 'Demand forecasting based on sales history',
                'cycle_counting': 'Systematic inventory counting and variance tracking',
                'multi_location': 'Support for multiple warehouses and locations',
                'transfer_management': 'Inter-location stock transfers',
                'cost_tracking': 'FIFO/LIFO/Average cost methods',
                'reorder_automation': 'Intelligent reorder point calculations'
            },
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
                'social_sharing': 'Social media share tracking'
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
                'orders': 'Order lifecycle tracking',
                'seo': 'SEO performance tracking and analytics'
            }
        },
        'seo_endpoints': {
            'dashboard': '/admin/api/v1/seo/dashboard',
            'pages': '/admin/api/v1/seo/pages',
            'keywords': '/admin/api/v1/seo/keywords',
            'sitemap': '/admin/api/v1/seo/sitemap/generate',
            'robots': '/admin/api/v1/seo/robots',
            'audit': '/admin/api/v1/seo/audit/run',
            'schema': '/admin/api/v1/seo/schema/templates',
            'public_robots': '/api/v1/robots.txt',
            'public_sitemap': '/api/v1/sitemap.xml'
        },
        'inventory_endpoints': {
            'stock_management': [
                '/admin/api/v1/inventory/stock-levels',
                '/admin/api/v1/inventory/movements',
                '/admin/api/v1/inventory/adjust'
            ],
            'supplier_management': [
                '/admin/api/v1/inventory/suppliers',
                '/admin/api/v1/inventory/suppliers/{id}'
            ],
            'purchase_orders': [
                '/admin/api/v1/inventory/purchase-orders',
                '/admin/api/v1/inventory/purchase-orders/{id}/receive'
            ],
            'analytics_reports': [
                '/admin/api/v1/inventory/analytics/overview',
                '/admin/api/v1/inventory/reports/valuation',
                '/admin/api/v1/inventory/reports/dead-stock'
            ],
            'bulk_operations': [
                '/admin/api/v1/inventory/bulk-update',
                '/admin/api/v1/inventory/import',
                '/admin/api/v1/inventory/export'
            ],
            'forecasting': [
                '/admin/api/v1/inventory/forecasting'
            ],
            'alerts': [
                '/admin/api/v1/inventory/alerts/low-stock'
            ]
        },
        'public_endpoints': {
            'blog_tracking': ['/api/v1/blog/posts/{id}/track-view', '/api/v1/blog/posts/{id}/share/{platform}'],
            'coupons': ['/api/v1/coupons/apply', '/api/v1/coupons/eligible', '/api/v1/coupons/remove'],
            'flash_sales': ['/api/v1/flash-sales/active'],
            'bulk_discounts': ['/api/v1/bulk-discounts/calculate'],
            'rss': ['/api/v1/blog/rss'],
            'seo': ['/api/v1/robots.txt', '/api/v1/sitemap.xml']
        },
        'admin_endpoints': {
            'auth': '/admin/api/v1/auth/*',
            'dashboard': '/admin/api/v1/dashboard/*',
            'config': '/admin/api/v1/config/*',
            'store': '/admin/api/v1/store/*',
            'products': '/admin/api/v1/products/*',
            'categories': '/admin/api/v1/categories/*',
            'orders': '/admin/api/v1/orders/*',
            'customers': '/admin/api/v1/customers/*',
            'blog': '/admin/api/v1/blog/*',
            'coupons': '/admin/api/v1/coupons/*',
            'integrations': '/admin/api/v1/integrations/*',
            'inventory': '/admin/api/v1/inventory/*',
            'seo': '/admin/api/v1/seo/*'
        }
    })

# ======================= ERROR HANDLERS =======================

@app.errorhandler(404)
def not_found(error):
    from utils.response_formatter import error_response
    return error_response('Endpoint not found', 404)

@app.errorhandler(500)
def internal_error(error):
    from utils.response_formatter import error_response
    return error_response('Internal server error', 500)

@app.errorhandler(400)
def bad_request(error):
    from utils.response_formatter import error_response
    return error_response('Bad request', 400)

@app.errorhandler(401)
def unauthorized(error):
    from utils.response_formatter import error_response
    return error_response('Unauthorized access', 401)

@app.errorhandler(403)
def forbidden(error):
    from utils.response_formatter import error_response
    return error_response('Access forbidden', 403)

@app.errorhandler(405)
def method_not_allowed(error):
    from utils.response_formatter import error_response
    return error_response('Method not allowed', 405)

# ======================= JWT ERROR HANDLERS =======================

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    from utils.response_formatter import error_response
    return error_response('Token has expired', 401)

@jwt.invalid_token_loader
def invalid_token_callback(error):
    from utils.response_formatter import error_response
    return error_response('Invalid token', 401)

@jwt.unauthorized_loader
def missing_token_callback(error):
    from utils.response_formatter import error_response
    return error_response('Authorization token is required', 401)

# ======================= REQUEST MIDDLEWARE =======================

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

# ======================= WEBHOOK ENDPOINTS =======================

@app.route('/webhooks/razorpay', methods=['POST'])
def razorpay_webhook():
    from admin.integrations import handle_webhook
    return handle_webhook('razorpay')

@app.route('/webhooks/phonepe', methods=['POST'])
def phonepe_webhook():
    from admin.integrations import handle_webhook
    return handle_webhook('phonepe')

@app.route('/webhooks/shiprocket', methods=['POST'])
def shiprocket_webhook():
    from admin.integrations import handle_webhook
    return handle_webhook('shiprocket')

# ======================= DEVELOPMENT CONFIGURATION =======================

if __name__ == '__main__':
    # Check if all required environment variables are set
    required_env_vars = ['DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file or environment configuration")
    
    # Print startup information
    print("=" * 70)
    print("🚀 E-COMMERCE ADMIN API STARTING")
    print("=" * 70)
    print(f"📡 Admin Panel: http://localhost:5001/admin/api/v1")
    print(f"🌐 Public API: http://localhost:5001/api/v1")
    print(f"📊 Health Check: http://localhost:5001/health")
    print(f"📁 File Uploads: http://localhost:5001/uploads/")
    print(f"📝 API Info: http://localhost:5001/admin/api/v1/info")
    print("=" * 70)
    print("🔧 Available Admin Modules:")
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
    print("   • Coupons & Discounts")
    print("   • Product Reviews")
    print("   • Inventory Management")
    print("   • SEO Management")  # Added SEO
    print("   • API Integrations")
    print("=" * 70)
    print("🌐 Public API Endpoints:")
    print("   • Blog post view tracking")
    print("   • Social media share tracking")
    print("   • RSS feed generation")
    print("   • Coupon validation & application")
    print("   • Eligible coupons for customers")
    print("   • Active flash sales")
    print("   • Bulk discount calculations")
    print("   • SEO robots.txt serving")
    print("   • SEO sitemap.xml serving")
    print("=" * 70)
    print("🔍 SEO Management Features:")
    print("   • Meta tags management (title, description, keywords)")
    print("   • Open Graph & Twitter Card tags")
    print("   • Structured data (Schema.org) support")
    print("   • Robots.txt dynamic generation")
    print("   • XML sitemap automation")
    print("   • Keyword tracking & ranking")
    print("   • Page-wise SEO auditing")
    print("   • SEO recommendations engine")
    print("   • Content analysis & optimization")
    print("   • Canonical URL management")
    print("   • SEO analytics dashboard")
    print("=" * 70)
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
    print("=" * 70)
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
    print("=" * 70)
    print("📦 Inventory Management Features:")
    print("   • Real-time stock tracking")
    print("   • Movement history & audit trails")
    print("   • Low stock alerts & automation")
    print("   • Supplier management")
    print("   • Purchase order lifecycle")
    print("   • Stock adjustments & approvals")
    print("   • Valuation & margin analysis")
    print("   • ABC analysis & forecasting")
    print("   • Multi-location support")
    print("   • Bulk operations & CSV import/export")
    print("=" * 70)
    print("🔗 Webhook Endpoints:")
    print("   • /webhooks/razorpay")
    print("   • /webhooks/phonepe")
    print("   • /webhooks/shiprocket")
    print("=" * 70)
    print("📊 SEO API Endpoints:")
    print("   • GET  /admin/api/v1/seo/dashboard - SEO analytics")
    print("   • GET  /admin/api/v1/seo/pages - SEO pages management")
    print("   • POST /admin/api/v1/seo/pages - Create SEO page")
    print("   • PUT  /admin/api/v1/seo/pages/{id} - Update SEO page")
    print("   • GET  /admin/api/v1/seo/keywords - Keywords management")
    print("   • POST /admin/api/v1/seo/keywords - Add keyword")
    print("   • POST /admin/api/v1/seo/sitemap/generate - Generate sitemap")
    print("   • GET  /admin/api/v1/seo/robots - Manage robots.txt")
    print("   • POST /admin/api/v1/seo/audit/run - Run SEO audit")
    print("   • GET  /admin/api/v1/seo/schema/templates - Schema templates")
    print("   • POST /admin/api/v1/seo/schema/validate - Validate schema")
    print("   • GET  /api/v1/robots.txt - Public robots.txt")
    print("   • GET  /api/v1/sitemap.xml - Public sitemap.xml")
    print("=" * 70)
    
    # Run the application
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=5001,
        threaded=True
    )