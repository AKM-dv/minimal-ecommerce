from flask import Blueprint, request
import os
import json
from datetime import datetime
from PIL import Image

# Import our modules
from models import Database, SiteConfig
from utils import admin_required, success_response, error_response, get_request_data, save_image

# Create blueprint
store_bp = Blueprint('store', __name__)

# ======================= STORE INFORMATION ROUTES =======================

@store_bp.route('/store/business-profile', methods=['GET'])
@admin_required
def get_business_profile():
    try:
        profile_data = SiteConfig.get_config('business_profile')
        
        if profile_data:
            try:
                profile = json.loads(profile_data)
            except:
                profile = {}
        else:
            profile = {
                'business_name': '',
                'owner_name': '',
                'brand_name': '',
                'business_type': '',
                'establishment_year': '',
                'business_description': '',
                'tagline': '',
                'business_category': '',
                'employee_count': '',
                'annual_turnover': '',
                'business_registration_number': '',
                'cin_number': '',
                'udyam_registration': ''
            }
        
        return success_response(profile)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/business-profile', methods=['PUT'])
@admin_required
def update_business_profile():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('business_profile', json.dumps(data))
        
        return success_response(message='Business profile updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/logo', methods=['GET'])
@admin_required
def get_logo_config():
    try:
        logo_data = SiteConfig.get_config('store_logo')
        
        if logo_data:
            try:
                logo = json.loads(logo_data)
            except:
                logo = {}
        else:
            logo = {
                'main_logo': '',
                'favicon': '',
                'logo_variants': {
                    'header_logo': '',
                    'footer_logo': '',
                    'email_logo': '',
                    'invoice_logo': '',
                    'watermark_logo': ''
                }
            }
        
        return success_response(logo)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/logo/upload', methods=['POST'])
@admin_required
def upload_logo():
    try:
        if 'file' not in request.files:
            return error_response('No file provided', 400)
        
        file = request.files['file']
        logo_type = request.form.get('logo_type', 'main_logo')  # main_logo, favicon, header_logo, etc.
        
        if file.filename == '':
            return error_response('No file selected', 400)
        
        # Different sizes for different logo types
        size_configs = {
            'main_logo': (300, 100),
            'favicon': (32, 32),
            'header_logo': (200, 60),
            'footer_logo': (150, 50),
            'email_logo': (200, 80),
            'invoice_logo': (250, 80),
            'watermark_logo': (100, 100)
        }
        
        max_size = size_configs.get(logo_type, (300, 100))
        
        # Save logo with specific naming
        filepath = save_logo_variant(file, logo_type, max_size)
        if not filepath:
            return error_response('Failed to save logo', 500)
        
        # Update logo config
        logo_data = SiteConfig.get_config('store_logo')
        if logo_data:
            try:
                logo_config = json.loads(logo_data)
            except:
                logo_config = {'logo_variants': {}}
        else:
            logo_config = {'logo_variants': {}}
        
        if logo_type == 'main_logo' or logo_type == 'favicon':
            logo_config[logo_type] = filepath
        else:
            logo_config['logo_variants'][logo_type] = filepath
        
        SiteConfig.set_config('store_logo', json.dumps(logo_config))
        
        return success_response({
            'logo_type': logo_type,
            'filepath': filepath,
            'url': f"/uploads/{filepath}"
        }, f'{logo_type.replace("_", " ").title()} uploaded successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

def save_logo_variant(file, logo_type, max_size):
    """Save logo with specific naming and sizing"""
    try:
        if not file or file.filename == '':
            return None
        
        # Create logo directory
        upload_dir = os.path.join('uploads', 'logos')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate filename based on logo type
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{logo_type}.{file_extension}"
        filepath = os.path.join(upload_dir, filename)
        
        # Save and resize image
        image = Image.open(file.stream)
        
        # Maintain aspect ratio while resizing
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # For favicon, convert to ICO if needed
        if logo_type == 'favicon' and file_extension != 'ico':
            filename = f"favicon.ico"
            filepath = os.path.join(upload_dir, filename)
        
        image.save(filepath, optimize=True, quality=90)
        return f"logos/{filename}"
        
    except Exception as e:
        return None

@store_bp.route('/store/contact-info', methods=['GET'])
@admin_required
def get_contact_info():
    try:
        contact_data = SiteConfig.get_config('contact_information')
        
        if contact_data:
            try:
                contact = json.loads(contact_data)
            except:
                contact = {}
        else:
            contact = {
                'primary_phone': '',
                'secondary_phone': '',
                'whatsapp_number': '',
                'primary_email': '',
                'support_email': '',
                'sales_email': '',
                'website_url': '',
                'customer_service_hours': '',
                'emergency_contact': ''
            }
        
        return success_response(contact)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/contact-info', methods=['PUT'])
@admin_required
def update_contact_info():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('contact_information', json.dumps(data))
        
        return success_response(message='Contact information updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/addresses', methods=['GET'])
@admin_required
def get_store_addresses():
    try:
        addresses_data = SiteConfig.get_config('store_addresses')
        
        if addresses_data:
            try:
                addresses = json.loads(addresses_data)
            except:
                addresses = {}
        else:
            addresses = {
                'billing_address': {
                    'company_name': '',
                    'address_line_1': '',
                    'address_line_2': '',
                    'city': '',
                    'state': '',
                    'postal_code': '',
                    'country': '',
                    'landmark': ''
                },
                'shipping_address': {
                    'company_name': '',
                    'address_line_1': '',
                    'address_line_2': '',
                    'city': '',
                    'state': '',
                    'postal_code': '',
                    'country': '',
                    'landmark': ''
                },
                'store_locations': []
            }
        
        return success_response(addresses)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/addresses', methods=['PUT'])
@admin_required
def update_store_addresses():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('store_addresses', json.dumps(data))
        
        return success_response(message='Store addresses updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/social-media', methods=['GET'])
@admin_required
def get_social_media():
    try:
        social_data = SiteConfig.get_config('social_media_links')
        
        if social_data:
            try:
                social = json.loads(social_data)
            except:
                social = {}
        else:
            social = {
                'facebook': {'url': '', 'enabled': False},
                'instagram': {'url': '', 'enabled': False},
                'twitter': {'url': '', 'enabled': False},
                'linkedin': {'url': '', 'enabled': False},
                'youtube': {'url': '', 'enabled': False},
                'pinterest': {'url': '', 'enabled': False},
                'tiktok': {'url': '', 'enabled': False},
                'snapchat': {'url': '', 'enabled': False},
                'whatsapp': {'number': '', 'enabled': False, 'message': 'Hello! I am interested in your products.'},
                'telegram': {'url': '', 'enabled': False}
            }
        
        return success_response(social)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/social-media', methods=['PUT'])
@admin_required
def update_social_media():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('social_media_links', json.dumps(data))
        
        return success_response(message='Social media links updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/business-hours', methods=['GET'])
@admin_required
def get_business_hours():
    try:
        hours_data = SiteConfig.get_config('business_hours')
        
        if hours_data:
            try:
                hours = json.loads(hours_data)
            except:
                hours = {}
        else:
            hours = {
                'monday': {'open': '09:00', 'close': '18:00', 'is_open': True},
                'tuesday': {'open': '09:00', 'close': '18:00', 'is_open': True},
                'wednesday': {'open': '09:00', 'close': '18:00', 'is_open': True},
                'thursday': {'open': '09:00', 'close': '18:00', 'is_open': True},
                'friday': {'open': '09:00', 'close': '18:00', 'is_open': True},
                'saturday': {'open': '10:00', 'close': '16:00', 'is_open': True},
                'sunday': {'open': '10:00', 'close': '16:00', 'is_open': False},
                'timezone': 'Asia/Kolkata',
                'special_hours': []
            }
        
        return success_response(hours)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/business-hours', methods=['PUT'])
@admin_required
def update_business_hours():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('business_hours', json.dumps(data))
        
        return success_response(message='Business hours updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/tax-registration', methods=['GET'])
@admin_required
def get_tax_registration():
    try:
        tax_data = SiteConfig.get_config('tax_registration')
        
        if tax_data:
            try:
                tax = json.loads(tax_data)
            except:
                tax = {}
        else:
            tax = {
                'gstin': '',
                'pan_number': '',
                'tan_number': '',
                'vat_number': '',
                'service_tax_number': '',
                'import_export_code': '',
                'msme_registration': '',
                'trade_license': '',
                'registration_documents': []
            }
        
        return success_response(tax)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/tax-registration', methods=['PUT'])
@admin_required
def update_tax_registration():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('tax_registration', json.dumps(data))
        
        return success_response(message='Tax registration details updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/bank-details', methods=['GET'])
@admin_required
def get_bank_details():
    try:
        bank_data = SiteConfig.get_config('bank_account_details')
        
        if bank_data:
            try:
                bank = json.loads(bank_data)
            except:
                bank = {}
        else:
            bank = {
                'primary_account': {
                    'bank_name': '',
                    'account_holder_name': '',
                    'account_number': '',
                    'ifsc_code': '',
                    'branch_name': '',
                    'account_type': '',
                    'swift_code': ''
                },
                'secondary_account': {
                    'bank_name': '',
                    'account_holder_name': '',
                    'account_number': '',
                    'ifsc_code': '',
                    'branch_name': '',
                    'account_type': '',
                    'swift_code': ''
                },
                'payment_gateways': {
                    'razorpay_merchant_id': '',
                    'payu_merchant_id': '',
                    'phonepe_merchant_id': '',
                    'stripe_account_id': ''
                }
            }
        
        return success_response(bank)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/bank-details', methods=['PUT'])
@admin_required
def update_bank_details():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('bank_account_details', json.dumps(data))
        
        return success_response(message='Bank account details updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/description', methods=['GET'])
@admin_required
def get_store_description():
    try:
        description_data = SiteConfig.get_config('store_description')
        
        if description_data:
            try:
                description = json.loads(description_data)
            except:
                description = {'content': description_data}
        else:
            description = {
                'short_description': '',
                'detailed_description': '',
                'mission_statement': '',
                'vision_statement': '',
                'core_values': [],
                'unique_selling_points': [],
                'history': '',
                'achievements': []
            }
        
        return success_response(description)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/description', methods=['PUT'])
@admin_required
def update_store_description():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('store_description', json.dumps(data))
        
        return success_response(message='Store description updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/about-us', methods=['GET'])
@admin_required
def get_about_us():
    try:
        about_data = SiteConfig.get_config('about_us_content')
        
        if about_data:
            try:
                about = json.loads(about_data)
            except:
                about = {'content': about_data}
        else:
            about = {
                'page_title': 'About Us',
                'hero_content': {
                    'headline': '',
                    'subheadline': '',
                    'hero_image': ''
                },
                'main_content': '',
                'team_section': {
                    'title': 'Our Team',
                    'description': '',
                    'team_members': []
                },
                'milestones': [],
                'certifications': [],
                'gallery': []
            }
        
        return success_response(about)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/about-us', methods=['PUT'])
@admin_required
def update_about_us():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('about_us_content', json.dumps(data))
        
        return success_response(message='About us content updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/policies', methods=['GET'])
@admin_required
def get_store_policies():
    try:
        policies_data = SiteConfig.get_config('store_policies')
        
        if policies_data:
            try:
                policies = json.loads(policies_data)
            except:
                policies = {}
        else:
            policies = {
                'customer_service_policy': '',
                'quality_assurance_policy': '',
                'data_protection_policy': '',
                'cookie_policy': '',
                'accessibility_policy': '',
                'environmental_policy': '',
                'code_of_conduct': '',
                'supplier_policy': '',
                'complaint_handling_policy': ''
            }
        
        return success_response(policies)
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/policies', methods=['PUT'])
@admin_required
def update_store_policies():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('store_policies', json.dumps(data))
        
        return success_response(message='Store policies updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/policy/<policy_type>', methods=['GET'])
@admin_required
def get_specific_store_policy(policy_type):
    try:
        policies_data = SiteConfig.get_config('store_policies')
        
        if policies_data:
            try:
                policies = json.loads(policies_data)
                policy_content = policies.get(policy_type, '')
            except:
                policy_content = ''
        else:
            policy_content = ''
        
        return success_response({
            'type': policy_type,
            'content': policy_content
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@store_bp.route('/store/policy/<policy_type>', methods=['PUT'])
@admin_required
def update_specific_store_policy(policy_type):
    try:
        data = get_request_data()
        content = data.get('content', '')
        
        # Get existing policies
        policies_data = SiteConfig.get_config('store_policies')
        if policies_data:
            try:
                policies = json.loads(policies_data)
            except:
                policies = {}
        else:
            policies = {}
        
        # Update specific policy
        policies[policy_type] = content
        
        SiteConfig.set_config('store_policies', json.dumps(policies))
        
        return success_response(message=f'{policy_type.replace("_", " ").title()} updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# Document upload for tax registration and other store documents
@store_bp.route('/store/upload-document', methods=['POST'])
@admin_required
def upload_store_document():
    try:
        if 'file' not in request.files:
            return error_response('No file provided', 400)
        
        file = request.files['file']
        document_type = request.form.get('document_type', 'general')
        
        if file.filename == '':
            return error_response('No file selected', 400)
        
        # Save document
        filepath = save_image(file, f'documents/{document_type}')
        if not filepath:
            return error_response('Failed to save document', 500)
        
        return success_response({
            'document_type': document_type,
            'filepath': filepath,
            'url': f"/uploads/{filepath}"
        }, 'Document uploaded successfully')
        
    except Exception as e:
        return error_response(str(e), 500)