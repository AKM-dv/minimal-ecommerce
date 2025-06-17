from flask import Blueprint, request, send_from_directory
import os
import json
from datetime import datetime

# Import our modules
from models import Database, SiteConfig
from utils import admin_required, success_response, error_response, get_request_data, save_image

# Create blueprint
config_bp = Blueprint('config', __name__)

# ======================= SITE CONFIGURATION ROUTES =======================

@config_bp.route('/config', methods=['GET'])
@admin_required
def get_site_config():
    try:
        query = "SELECT config_key, value FROM site_config"
        configs = Database.execute_query(query, fetch=True)
        
        config_dict = {}
        for config in configs:
            # Try to parse JSON values, fallback to string
            try:
                config_dict[config['config_key']] = json.loads(config['value'])
            except:
                config_dict[config['config_key']] = config['value']
        
        return success_response(config_dict)
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config', methods=['PUT'])
@admin_required
def update_site_config():
    try:
        data = get_request_data()
        
        for key, value in data.items():
            # Convert value to JSON string for storage
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
            
            SiteConfig.set_config(key, value_str)
        
        return success_response(message='Configuration updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/hero-carousel', methods=['GET'])
@admin_required
def get_hero_carousel():
    try:
        carousel_data = SiteConfig.get_config('hero_carousel')
        
        if carousel_data:
            try:
                carousel = json.loads(carousel_data)
            except:
                carousel = {'slides': []}
        else:
            # Default structure with 5 slots
            carousel = {
                'slides': [
                    {'id': i+1, 'image': '', 'alt_text': '', 'display_order': i+1, 'is_active': False}
                    for i in range(5)
                ]
            }
        
        return success_response(carousel)
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/hero-carousel', methods=['PUT'])
@admin_required
def update_hero_carousel():
    try:
        data = get_request_data()
        slides = data.get('slides', [])
        
        # Validate slides structure
        for slide in slides:
            if not isinstance(slide, dict):
                return error_response('Invalid slide format', 400)
        
        carousel_data = {'slides': slides}
        SiteConfig.set_config('hero_carousel', json.dumps(carousel_data))
        
        return success_response(message='Hero carousel updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/hero-carousel/upload', methods=['POST'])
@admin_required
def upload_carousel_image():
    try:
        if 'file' not in request.files:
            return error_response('No file provided', 400)
        
        file = request.files['file']
        slide_id = request.form.get('slide_id')
        
        if file.filename == '':
            return error_response('No file selected', 400)
        
        filepath = save_image(file, 'carousel', max_size=(1200, 600))
        if not filepath:
            return error_response('Failed to save image', 500)
        
        return success_response({
            'slide_id': slide_id,
            'filepath': filepath,
            'url': f"/uploads/{filepath}"
        }, 'Carousel image uploaded successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/top-offer-bar', methods=['GET'])
@admin_required
def get_top_offer_bar():
    try:
        offer_data = SiteConfig.get_config('top_offer_bar')
        
        if offer_data:
            try:
                offer = json.loads(offer_data)
            except:
                offer = {}
        else:
            offer = {
                'is_enabled': False,
                'text': '',
                'background_color': '#007bff',
                'text_color': '#ffffff',
                'link_url': '',
                'link_text': ''
            }
        
        return success_response(offer)
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/top-offer-bar', methods=['PUT'])
@admin_required
def update_top_offer_bar():
    try:
        data = get_request_data()
        
        offer_config = {
            'is_enabled': data.get('is_enabled', False),
            'text': data.get('text', ''),
            'background_color': data.get('background_color', '#007bff'),
            'text_color': data.get('text_color', '#ffffff'),
            'link_url': data.get('link_url', ''),
            'link_text': data.get('link_text', '')
        }
        
        SiteConfig.set_config('top_offer_bar', json.dumps(offer_config))
        
        return success_response(message='Top offer bar updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/product-instructions', methods=['GET'])
@admin_required
def get_product_instructions():
    try:
        instructions_data = SiteConfig.get_config('product_instructions')
        
        if instructions_data:
            try:
                instructions = json.loads(instructions_data)
            except:
                instructions = {'points': []}
        else:
            instructions = {
                'title': 'Product Handling Instructions',
                'points': [
                    'Handle with care',
                    'Store in cool, dry place',
                    'Check product before use'
                ]
            }
        
        return success_response(instructions)
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/product-instructions', methods=['PUT'])
@admin_required
def update_product_instructions():
    try:
        data = get_request_data()
        
        instructions = {
            'title': data.get('title', 'Product Handling Instructions'),
            'points': data.get('points', [])
        }
        
        SiteConfig.set_config('product_instructions', json.dumps(instructions))
        
        return success_response(message='Product instructions updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/maintenance-mode', methods=['GET'])
@admin_required
def get_maintenance_mode():
    try:
        maintenance_data = SiteConfig.get_config('maintenance_mode')
        
        if maintenance_data:
            try:
                maintenance = json.loads(maintenance_data)
            except:
                maintenance = {'enabled': False}
        else:
            maintenance = {
                'enabled': False,
                'title': 'Site Under Maintenance',
                'message': 'We are currently performing scheduled maintenance. Please check back soon.',
                'estimated_time': ''
            }
        
        return success_response(maintenance)
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/maintenance-mode', methods=['PUT'])
@admin_required
def update_maintenance_mode():
    try:
        data = get_request_data()
        
        maintenance = {
            'enabled': data.get('enabled', False),
            'title': data.get('title', 'Site Under Maintenance'),
            'message': data.get('message', 'We are currently performing scheduled maintenance. Please check back soon.'),
            'estimated_time': data.get('estimated_time', '')
        }
        
        SiteConfig.set_config('maintenance_mode', json.dumps(maintenance))
        
        return success_response(message='Maintenance mode updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/announcements', methods=['GET'])
@admin_required
def get_announcements():
    try:
        announcements_data = SiteConfig.get_config('site_announcements')
        
        if announcements_data:
            try:
                announcements = json.loads(announcements_data)
            except:
                announcements = {'items': []}
        else:
            announcements = {
                'items': [],
                'display_type': 'banner'  # banner, popup, notification
            }
        
        return success_response(announcements)
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/announcements', methods=['PUT'])
@admin_required
def update_announcements():
    try:
        data = get_request_data()
        
        announcements = {
            'items': data.get('items', []),
            'display_type': data.get('display_type', 'banner')
        }
        
        SiteConfig.set_config('site_announcements', json.dumps(announcements))
        
        return success_response(message='Site announcements updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/footer', methods=['GET'])
@admin_required
def get_footer_content():
    try:
        footer_data = SiteConfig.get_config('footer_content')
        
        if footer_data:
            try:
                footer = json.loads(footer_data)
            except:
                footer = {}
        else:
            footer = {
                'company_description': '',
                'contact_info': {
                    'address': '',
                    'phone': '',
                    'email': '',
                    'working_hours': ''
                },
                'social_links': {
                    'facebook': '',
                    'twitter': '',
                    'instagram': '',
                    'linkedin': '',
                    'youtube': ''
                },
                'quick_links': [
                    {'title': 'About Us', 'url': '/about'},
                    {'title': 'Contact', 'url': '/contact'},
                    {'title': 'Privacy Policy', 'url': '/privacy'},
                    {'title': 'Terms & Conditions', 'url': '/terms'}
                ],
                'copyright_text': '© 2025 Your Store Name. All rights reserved.'
            }
        
        return success_response(footer)
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/footer', methods=['PUT'])
@admin_required
def update_footer_content():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('footer_content', json.dumps(data))
        
        return success_response(message='Footer content updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/currency-timezone', methods=['GET'])
@admin_required
def get_currency_timezone():
    try:
        settings = {
            'currency': SiteConfig.get_config('currency') or 'INR',
            'currency_symbol': SiteConfig.get_config('currency_symbol') or '₹',
            'currency_position': SiteConfig.get_config('currency_position') or 'before',
            'timezone': SiteConfig.get_config('timezone') or 'Asia/Kolkata',
            'date_format': SiteConfig.get_config('date_format') or 'DD/MM/YYYY',
            'time_format': SiteConfig.get_config('time_format') or '24'
        }
        
        return success_response(settings)
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/currency-timezone', methods=['PUT'])
@admin_required
def update_currency_timezone():
    try:
        data = get_request_data()
        
        for key, value in data.items():
            SiteConfig.set_config(key, str(value))
        
        return success_response(message='Currency and timezone settings updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/tax-settings', methods=['GET'])
@admin_required
def get_tax_settings():
    try:
        tax_data = SiteConfig.get_config('tax_settings')
        
        if tax_data:
            try:
                tax_settings = json.loads(tax_data)
            except:
                tax_settings = {}
        else:
            tax_settings = {
                'tax_enabled': True,
                'tax_inclusive': False,
                'default_tax_rate': 18.0,
                'tax_name': 'GST',
                'tax_registration_number': '',
                'tax_rates': [
                    {'name': 'Standard Rate', 'rate': 18.0, 'description': 'Standard GST rate'},
                    {'name': 'Reduced Rate', 'rate': 5.0, 'description': 'Reduced GST rate'}
                ]
            }
        
        return success_response(tax_settings)
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/tax-settings', methods=['PUT'])
@admin_required
def update_tax_settings():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('tax_settings', json.dumps(data))
        
        return success_response(message='Tax settings updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/policies', methods=['GET'])
@admin_required
def get_policies():
    try:
        policies = {
            'shipping_policy': SiteConfig.get_config('shipping_policy') or '',
            'return_refund_policy': SiteConfig.get_config('return_refund_policy') or '',
            'terms_conditions': SiteConfig.get_config('terms_conditions') or '',
            'privacy_policy': SiteConfig.get_config('privacy_policy') or ''
        }
        
        return success_response(policies)
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/policies', methods=['PUT'])
@admin_required
def update_policies():
    try:
        data = get_request_data()
        
        policy_types = ['shipping_policy', 'return_refund_policy', 'terms_conditions', 'privacy_policy']
        
        for policy_type in policy_types:
            if policy_type in data:
                SiteConfig.set_config(policy_type, data[policy_type])
        
        return success_response(message='Policies updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/policy/<policy_type>', methods=['GET'])
@admin_required
def get_specific_policy(policy_type):
    try:
        valid_policies = ['shipping_policy', 'return_refund_policy', 'terms_conditions', 'privacy_policy']
        
        if policy_type not in valid_policies:
            return error_response('Invalid policy type', 400)
        
        policy_content = SiteConfig.get_config(policy_type) or ''
        
        return success_response({
            'type': policy_type,
            'content': policy_content
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@config_bp.route('/config/policy/<policy_type>', methods=['PUT'])
@admin_required
def update_specific_policy(policy_type):
    try:
        valid_policies = ['shipping_policy', 'return_refund_policy', 'terms_conditions', 'privacy_policy']
        
        if policy_type not in valid_policies:
            return error_response('Invalid policy type', 400)
        
        data = get_request_data()
        content = data.get('content', '')
        
        SiteConfig.set_config(policy_type, content)
        
        return success_response(message=f'{policy_type.replace("_", " ").title()} updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# File upload for general site assets
@config_bp.route('/config/upload', methods=['POST'])
@admin_required
def upload_site_asset():
    try:
        if 'file' not in request.files:
            return error_response('No file provided', 400)
        
        file = request.files['file']
        folder = request.form.get('folder', 'site_assets')
        
        if file.filename == '':
            return error_response('No file selected', 400)
        
        filepath = save_image(file, folder)
        if not filepath:
            return error_response('Failed to save file', 500)
        
        return success_response({
            'filepath': filepath,
            'url': f"/uploads/{filepath}"
        }, 'Site asset uploaded successfully')
        
    except Exception as e:
        return error_response(str(e), 500)