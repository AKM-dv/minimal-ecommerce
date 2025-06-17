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

app.register_blueprint(auth_bp, url_prefix='/admin/api/v1')
app.register_blueprint(dashboard_bp, url_prefix='/admin/api/v1')
app.register_blueprint(config_bp, url_prefix='/admin/api/v1')
app.register_blueprint(store_bp, url_prefix='/admin/api/v1')
app.register_blueprint(products_bp, url_prefix='/admin/api/v1')
app.register_blueprint(categories_bp, url_prefix='/admin/api/v1')
app.register_blueprint(orders_bp, url_prefix='/admin/api/v1')
app.register_blueprint(customers_bp, url_prefix='/admin/api/v1')

# Error handlers
@app.errorhandler(404)
def not_found(error):
    from utils import error_response
    return error_response('Endpoint not found', 404)

@app.errorhandler(500)
def internal_error(error):
    from utils import error_response
    return error_response('Internal server error', 500)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)