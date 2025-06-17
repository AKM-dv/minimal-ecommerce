from flask import Flask, jsonify
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
                'comments': 'Moderation system with spam detection',
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
    print("   • Blog Management (NEW)")
    print("   • API Integrations")
    print("=" * 60)
    print("📝 Blog Features:")
    print("   • Rich text editor support")
    print("   • Comment moderation system")
    print("   • Analytics & engagement tracking")
    print("   • SEO optimization scoring")
    print("   • Post scheduling")
    print("   • Categories & tags management")
    print("   • Newsletter subscriber management")
    print("   • RSS feed generation")
    print("   • Social media share tracking")
    print("=" * 60)
    
    # Run the application
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=5001,
        threaded=True
    )