from flask import Blueprint, request, jsonify, make_response
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re
import requests
from urllib.parse import urljoin, urlparse
import os

# Import our modules
from models import Database, SiteConfig
from utils import (admin_required, success_response, error_response, get_request_data, 
                   ResponseFormatter)

# Create blueprint
seo_bp = Blueprint('seo', __name__)

# ======================= GLOBAL SEO SETTINGS =======================

@seo_bp.route('/seo/global-settings', methods=['GET'])
@admin_required
def get_global_seo_settings():
    try:
        settings_data = SiteConfig.get_config('global_seo_settings')
        
        if settings_data:
            try:
                settings = json.loads(settings_data)
            except:
                settings = {}
        else:
            settings = {
                'site_title': '',
                'site_description': '',
                'site_keywords': '',
                'default_meta_title_template': '{page_title} | {site_name}',
                'default_meta_description_template': '{page_description}',
                'canonical_url': '',
                'default_og_image': '',
                'twitter_handle': '',
                'google_analytics_id': '',
                'google_search_console_code': '',
                'google_tag_manager_id': '',
                'facebook_app_id': '',
                'robots_directives': {
                    'index': True,
                    'follow': True,
                    'max_snippet': -1,
                    'max_image_preview': 'large',
                    'max_video_preview': -1
                },
                'structured_data': {
                    'organization_enabled': True,
                    'website_enabled': True,
                    'breadcrumbs_enabled': True,
                    'product_enabled': True,
                    'article_enabled': True,
                    'local_business_enabled': False
                },
                'sitemap_settings': {
                    'include_products': True,
                    'include_categories': True,
                    'include_blog_posts': True,
                    'include_pages': True,
                    'update_frequency': 'weekly',
                    'priority_pages': 1.0,
                    'priority_products': 0.8,
                    'priority_categories': 0.7,
                    'priority_blog': 0.6
                }
            }
        
        return success_response(settings)
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/global-settings', methods=['PUT'])
@admin_required
def update_global_seo_settings():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('global_seo_settings', json.dumps(data))
        
        return success_response(message='Global SEO settings updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= PAGE-WISE META TAGS =======================

@seo_bp.route('/seo/pages', methods=['GET'])
@admin_required
def get_seo_pages():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        page_type = request.args.get('type')  # product, category, blog, custom
        search = request.args.get('search', '').strip()
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if page_type:
            where_conditions.append("sp.page_type = %s")
            params.append(page_type)
        
        if search:
            where_conditions.append("(sp.page_title LIKE %s OR sp.page_url LIKE %s OR sp.meta_title LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM seo_pages sp WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get SEO pages
        pages_query = f"""
        SELECT sp.*, 
               CASE 
                   WHEN sp.seo_score >= 80 THEN 'excellent'
                   WHEN sp.seo_score >= 60 THEN 'good'
                   WHEN sp.seo_score >= 40 THEN 'needs_improvement'
                   ELSE 'poor'
               END as seo_grade,
               sp.last_audited,
               DATEDIFF(NOW(), sp.last_audited) as days_since_audit
        FROM seo_pages sp
        WHERE {where_clause}
        ORDER BY sp.updated_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        pages = Database.execute_query(pages_query, params, fetch=True)
        
        # Parse JSON fields and add computed data
        for page_data in pages:
            # Parse JSON fields
            if page_data.get('meta_tags'):
                try:
                    page_data['meta_tags'] = json.loads(page_data['meta_tags'])
                except:
                    page_data['meta_tags'] = {}
            
            if page_data.get('open_graph_tags'):
                try:
                    page_data['open_graph_tags'] = json.loads(page_data['open_graph_tags'])
                except:
                    page_data['open_graph_tags'] = {}
            
            if page_data.get('twitter_card_tags'):
                try:
                    page_data['twitter_card_tags'] = json.loads(page_data['twitter_card_tags'])
                except:
                    page_data['twitter_card_tags'] = {}
            
            if page_data.get('structured_data'):
                try:
                    page_data['structured_data'] = json.loads(page_data['structured_data'])
                except:
                    page_data['structured_data'] = {}
            
            # Add status indicators
            page_data['needs_audit'] = not page_data['last_audited'] or page_data['days_since_audit'] > 30
            page_data['has_issues'] = page_data['seo_score'] < 60
        
        return jsonify(ResponseFormatter.paginated(pages, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/pages', methods=['POST'])
@admin_required
def create_seo_page():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['page_url', 'page_title', 'page_type']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Check for duplicate URL
        existing_page = Database.execute_query(
            "SELECT COUNT(*) as count FROM seo_pages WHERE page_url = %s",
            (data['page_url'],), fetch=True
        )[0]['count']
        
        if existing_page > 0:
            return error_response('Page URL already exists', 400)
        
        # Create SEO page
        page_query = """
        INSERT INTO seo_pages (page_url, page_title, page_type, meta_title, meta_description,
                             meta_keywords, meta_tags, open_graph_tags, twitter_card_tags,
                             structured_data, canonical_url, robots_directive, 
                             focus_keyword, is_indexable, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        page_id = Database.execute_query(page_query, (
            data['page_url'], data['page_title'], data['page_type'],
            data.get('meta_title', ''), data.get('meta_description', ''),
            data.get('meta_keywords', ''), json.dumps(data.get('meta_tags', {})),
            json.dumps(data.get('open_graph_tags', {})), json.dumps(data.get('twitter_card_tags', {})),
            json.dumps(data.get('structured_data', {})), data.get('canonical_url', ''),
            data.get('robots_directive', 'index,follow'), data.get('focus_keyword', ''),
            bool(data.get('is_indexable', True)), datetime.now()
        ))
        
        # Run initial SEO audit
        audit_seo_page(page_id)
        
        return success_response({
            'id': page_id,
            'page_url': data['page_url']
        }, 'SEO page created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/pages/<int:page_id>', methods=['GET'])
@admin_required
def get_seo_page(page_id):
    try:
        page_query = """
        SELECT sp.*,
               CASE 
                   WHEN sp.seo_score >= 80 THEN 'excellent'
                   WHEN sp.seo_score >= 60 THEN 'good'
                   WHEN sp.seo_score >= 40 THEN 'needs_improvement'
                   ELSE 'poor'
               END as seo_grade
        FROM seo_pages sp
        WHERE sp.id = %s
        """
        
        page_result = Database.execute_query(page_query, (page_id,), fetch=True)
        
        if not page_result:
            return error_response('SEO page not found', 404)
        
        page_data = page_result[0]
        
        # Parse JSON fields
        json_fields = ['meta_tags', 'open_graph_tags', 'twitter_card_tags', 'structured_data']
        for field in json_fields:
            if page_data.get(field):
                try:
                    page_data[field] = json.loads(page_data[field])
                except:
                    page_data[field] = {}
        
        # Get audit history
        audit_history = Database.execute_query(
            """SELECT * FROM seo_audits WHERE page_id = %s 
               ORDER BY audit_date DESC LIMIT 10""",
            (page_id,), fetch=True
        )
        
        for audit in audit_history:
            if audit.get('audit_results'):
                try:
                    audit['audit_results'] = json.loads(audit['audit_results'])
                except:
                    audit['audit_results'] = {}
        
        page_data['audit_history'] = audit_history
        
        return success_response(page_data)
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/pages/<int:page_id>', methods=['PUT'])
@admin_required
def update_seo_page(page_id):
    try:
        data = get_request_data()
        
        # Check if page exists
        existing_page = Database.execute_query(
            "SELECT * FROM seo_pages WHERE id = %s", (page_id,), fetch=True
        )
        if not existing_page:
            return error_response('SEO page not found', 404)
        
        # Build update query
        update_fields = []
        params = []
        
        updatable_fields = {
            'page_title': str, 'meta_title': str, 'meta_description': str,
            'meta_keywords': str, 'canonical_url': str, 'robots_directive': str,
            'focus_keyword': str, 'is_indexable': bool
        }
        
        for field, field_type in updatable_fields.items():
            if field in data:
                update_fields.append(f"{field} = %s")
                if field_type == bool:
                    params.append(bool(data[field]))
                else:
                    params.append(data[field])
        
        # Handle JSON fields
        json_fields = ['meta_tags', 'open_graph_tags', 'twitter_card_tags', 'structured_data']
        for field in json_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                params.append(json.dumps(data[field]))
        
        if not update_fields:
            return error_response('No fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(page_id)
        
        query = f"UPDATE seo_pages SET {', '.join(update_fields)} WHERE id = %s"
        Database.execute_query(query, params)
        
        # Run SEO audit after update
        audit_seo_page(page_id)
        
        return success_response(message='SEO page updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= SITEMAP GENERATION =======================

@seo_bp.route('/seo/sitemap/generate', methods=['POST'])
@admin_required
def generate_sitemap():
    try:
        data = get_request_data()
        base_url = data.get('base_url') or SiteConfig.get_config('site_url') or 'https://example.com'
        
        # Get sitemap settings
        global_settings = SiteConfig.get_config('global_seo_settings')
        if global_settings:
            try:
                settings = json.loads(global_settings)
                sitemap_settings = settings.get('sitemap_settings', {})
            except:
                sitemap_settings = {}
        else:
            sitemap_settings = {}
        
        # Create XML sitemap
        urlset = ET.Element('urlset')
        urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        
        # Add homepage
        url_elem = ET.SubElement(urlset, 'url')
        ET.SubElement(url_elem, 'loc').text = base_url
        ET.SubElement(url_elem, 'lastmod').text = datetime.now().strftime('%Y-%m-%d')
        ET.SubElement(url_elem, 'changefreq').text = 'weekly'
        ET.SubElement(url_elem, 'priority').text = '1.0'
        
        urls_added = 1
        
        # Add pages
        if sitemap_settings.get('include_pages', True):
            pages = Database.execute_query(
                "SELECT page_url, updated_at FROM seo_pages WHERE is_indexable = 1",
                fetch=True
            )
            for page in pages:
                url_elem = ET.SubElement(urlset, 'url')
                ET.SubElement(url_elem, 'loc').text = urljoin(base_url, page['page_url'])
                if page['updated_at']:
                    ET.SubElement(url_elem, 'lastmod').text = page['updated_at'].strftime('%Y-%m-%d')
                ET.SubElement(url_elem, 'changefreq').text = sitemap_settings.get('update_frequency', 'weekly')
                ET.SubElement(url_elem, 'priority').text = str(sitemap_settings.get('priority_pages', 1.0))
                urls_added += 1
        
        # Add products
        if sitemap_settings.get('include_products', True):
            products = Database.execute_query(
                "SELECT id, updated_at FROM products WHERE status = 'active'",
                fetch=True
            )
            for product in products:
                url_elem = ET.SubElement(urlset, 'url')
                ET.SubElement(url_elem, 'loc').text = f"{base_url}/products/{product['id']}"
                if product['updated_at']:
                    ET.SubElement(url_elem, 'lastmod').text = product['updated_at'].strftime('%Y-%m-%d')
                ET.SubElement(url_elem, 'changefreq').text = 'weekly'
                ET.SubElement(url_elem, 'priority').text = str(sitemap_settings.get('priority_products', 0.8))
                urls_added += 1
        
        # Add categories
        if sitemap_settings.get('include_categories', True):
            categories = Database.execute_query(
                "SELECT id, updated_at FROM categories WHERE is_active = 1",
                fetch=True
            )
            for category in categories:
                url_elem = ET.SubElement(urlset, 'url')
                ET.SubElement(url_elem, 'loc').text = f"{base_url}/categories/{category['id']}"
                if category['updated_at']:
                    ET.SubElement(url_elem, 'lastmod').text = category['updated_at'].strftime('%Y-%m-%d')
                ET.SubElement(url_elem, 'changefreq').text = 'weekly'
                ET.SubElement(url_elem, 'priority').text = str(sitemap_settings.get('priority_categories', 0.7))
                urls_added += 1
        
        # Add blog posts
        if sitemap_settings.get('include_blog_posts', True):
            blog_posts = Database.execute_query(
                "SELECT slug, published_at FROM blog_posts WHERE status = 'published'",
                fetch=True
            )
            for post in blog_posts:
                url_elem = ET.SubElement(urlset, 'url')
                ET.SubElement(url_elem, 'loc').text = f"{base_url}/blog/{post['slug']}"
                if post['published_at']:
                    ET.SubElement(url_elem, 'lastmod').text = post['published_at'].strftime('%Y-%m-%d')
                ET.SubElement(url_elem, 'changefreq').text = 'monthly'
                ET.SubElement(url_elem, 'priority').text = str(sitemap_settings.get('priority_blog', 0.6))
                urls_added += 1
        
        # Generate XML content
        tree = ET.ElementTree(urlset)
        ET.indent(tree, space="  ", level=0)
        
        # Save sitemap
        sitemap_path = 'uploads/sitemap.xml'
        os.makedirs(os.path.dirname(sitemap_path), exist_ok=True)
        tree.write(sitemap_path, encoding='utf-8', xml_declaration=True)
        
        # Update sitemap generation record
        sitemap_query = """
        INSERT INTO sitemap_generations (urls_count, file_path, generated_at)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE 
        urls_count = VALUES(urls_count), 
        file_path = VALUES(file_path), 
        generated_at = VALUES(generated_at)
        """
        Database.execute_query(sitemap_query, (urls_added, sitemap_path, datetime.now()))
        
        return success_response({
            'urls_added': urls_added,
            'file_path': sitemap_path,
            'sitemap_url': f"{base_url}/sitemap.xml",
            'generated_at': datetime.now().isoformat()
        }, 'Sitemap generated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/sitemap/status', methods=['GET'])
@admin_required
def get_sitemap_status():
    try:
        # Get latest sitemap generation
        sitemap_query = """
        SELECT * FROM sitemap_generations 
        ORDER BY generated_at DESC 
        LIMIT 1
        """
        sitemap_result = Database.execute_query(sitemap_query, fetch=True)
        
        if sitemap_result:
            sitemap_data = sitemap_result[0]
            
            # Check if file exists
            file_exists = os.path.exists(sitemap_data['file_path'])
            
            # Calculate time since last generation
            last_generated = sitemap_data['generated_at']
            time_since = datetime.now() - last_generated
            
            return success_response({
                'last_generated': last_generated.isoformat(),
                'urls_count': sitemap_data['urls_count'],
                'file_path': sitemap_data['file_path'],
                'file_exists': file_exists,
                'days_since_generation': time_since.days,
                'needs_regeneration': time_since.days > 7
            })
        else:
            return success_response({
                'last_generated': None,
                'urls_count': 0,
                'file_exists': False,
                'needs_regeneration': True
            })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= ROBOTS.TXT MANAGEMENT =======================

@seo_bp.route('/seo/robots', methods=['GET'])
@admin_required
def get_robots_txt():
    try:
        robots_content = SiteConfig.get_config('robots_txt_content')
        
        if not robots_content:
            # Generate default robots.txt
            base_url = SiteConfig.get_config('site_url') or 'https://example.com'
            robots_content = f"""User-agent: *
Allow: /

# Sitemaps
Sitemap: {base_url}/sitemap.xml

# Disallow admin and private areas
Disallow: /admin/
Disallow: /api/
Disallow: /uploads/private/

# Disallow search and filter URLs
Disallow: /*?*
Disallow: /search*
Disallow: /*sort=*
Disallow: /*filter=*

# Allow important files
Allow: /robots.txt
Allow: /sitemap.xml
Allow: /*.css
Allow: /*.js
Allow: /*.png
Allow: /*.jpg
Allow: /*.jpeg
Allow: /*.gif
Allow: /*.svg

# Crawl delay
Crawl-delay: 1"""
        
        return success_response({
            'content': robots_content,
            'last_updated': SiteConfig.get_config('robots_txt_updated') or None
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/robots', methods=['PUT'])
@admin_required
def update_robots_txt():
    try:
        data = get_request_data()
        content = data.get('content', '')
        
        if not content.strip():
            return error_response('Robots.txt content is required', 400)
        
        # Validate robots.txt format (basic validation)
        if not validate_robots_txt(content):
            return error_response('Invalid robots.txt format', 400)
        
        # Save content
        SiteConfig.set_config('robots_txt_content', content)
        SiteConfig.set_config('robots_txt_updated', datetime.now().isoformat())
        
        # Write to file
        robots_path = 'uploads/robots.txt'
        os.makedirs(os.path.dirname(robots_path), exist_ok=True)
        with open(robots_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return success_response(message='Robots.txt updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= SCHEMA MARKUP =======================

@seo_bp.route('/seo/schema/templates', methods=['GET'])
@admin_required
def get_schema_templates():
    try:
        templates = {
            'organization': {
                '@context': 'https://schema.org',
                '@type': 'Organization',
                'name': '',
                'url': '',
                'logo': '',
                'description': '',
                'address': {
                    '@type': 'PostalAddress',
                    'streetAddress': '',
                    'addressLocality': '',
                    'addressRegion': '',
                    'postalCode': '',
                    'addressCountry': ''
                },
                'contactPoint': {
                    '@type': 'ContactPoint',
                    'telephone': '',
                    'contactType': 'customer service'
                },
                'sameAs': []
            },
            'product': {
                '@context': 'https://schema.org',
                '@type': 'Product',
                'name': '',
                'description': '',
                'image': [],
                'brand': {
                    '@type': 'Brand',
                    'name': ''
                },
                'offers': {
                    '@type': 'Offer',
                    'price': '',
                    'priceCurrency': 'INR',
                    'availability': 'https://schema.org/InStock',
                    'seller': {
                        '@type': 'Organization',
                        'name': ''
                    }
                },
                'aggregateRating': {
                    '@type': 'AggregateRating',
                    'ratingValue': '',
                    'reviewCount': ''
                }
            },
            'article': {
                '@context': 'https://schema.org',
                '@type': 'Article',
                'headline': '',
                'description': '',
                'image': '',
                'author': {
                    '@type': 'Person',
                    'name': ''
                },
                'publisher': {
                    '@type': 'Organization',
                    'name': '',
                    'logo': {
                        '@type': 'ImageObject',
                        'url': ''
                    }
                },
                'datePublished': '',
                'dateModified': ''
            },
            'breadcrumbList': {
                '@context': 'https://schema.org',
                '@type': 'BreadcrumbList',
                'itemListElement': []
            },
            'localBusiness': {
                '@context': 'https://schema.org',
                '@type': 'LocalBusiness',
                'name': '',
                'description': '',
                'url': '',
                'telephone': '',
                'address': {
                    '@type': 'PostalAddress',
                    'streetAddress': '',
                    'addressLocality': '',
                    'addressRegion': '',
                    'postalCode': '',
                    'addressCountry': ''
                },
                'openingHoursSpecification': []
            }
        }
        
        return success_response(templates)
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/schema/validate', methods=['POST'])
@admin_required
def validate_schema_markup():
    try:
        data = get_request_data()
        schema_data = data.get('schema')
        
        if not schema_data:
            return error_response('Schema data is required', 400)
        
        # Basic JSON validation
        try:
            if isinstance(schema_data, str):
                json.loads(schema_data)
            elif isinstance(schema_data, dict):
                json.dumps(schema_data)
            else:
                return error_response('Invalid schema format', 400)
        except json.JSONDecodeError:
            return error_response('Invalid JSON format', 400)
        
        # Validate required schema.org fields
        validation_results = validate_schema_structure(schema_data)
        
        return success_response({
            'is_valid': validation_results['is_valid'],
            'errors': validation_results['errors'],
            'warnings': validation_results['warnings'],
            'suggestions': validation_results['suggestions']
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= SEO AUDIT =======================

@seo_bp.route('/seo/audit/run', methods=['POST'])
@admin_required
def run_seo_audit():
    try:
        data = get_request_data()
        page_ids = data.get('page_ids', [])
        audit_type = data.get('type', 'full')  # full, quick, technical
        
        if not page_ids:
            # Audit all pages if none specified
            all_pages = Database.execute_query(
                "SELECT id FROM seo_pages WHERE is_indexable = 1", fetch=True
            )
            page_ids = [page['id'] for page in all_pages]
        
        audit_results = []
        
        for page_id in page_ids:
            try:
                result = audit_seo_page(page_id, audit_type)
                audit_results.append({
                    'page_id': page_id,
                    'score': result['score'],
                    'grade': result['grade'],
                    'issues_found': len(result['issues'])
                })
            except Exception as e:
                audit_results.append({
                    'page_id': page_id,
                    'error': str(e)
                })
        
        return success_response({
            'audited_pages': len(audit_results),
            'results': audit_results,
            'audit_type': audit_type,
            'completed_at': datetime.now().isoformat()
        }, 'SEO audit completed')
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/audit/reports', methods=['GET'])
@admin_required
def get_audit_reports():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        days = int(request.args.get('days', 30))
        
        offset = (page - 1) * per_page
        
        # Get audit reports
        reports_query = """
        SELECT sa.*, sp.page_title, sp.page_url, sp.page_type
        FROM seo_audits sa
        LEFT JOIN seo_pages sp ON sa.page_id = sp.id
        WHERE sa.audit_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY sa.audit_date DESC
        LIMIT %s OFFSET %s
        """
        
        reports = Database.execute_query(reports_query, (days, per_page, offset), fetch=True)
        
        # Get total count
        count_query = """
        SELECT COUNT(*) as total FROM seo_audits 
        WHERE audit_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        total = Database.execute_query(count_query, (days,), fetch=True)[0]['total']
        
        # Parse audit results
        for report in reports:
            if report.get('audit_results'):
                try:
                    report['audit_results'] = json.loads(report['audit_results'])
                except:
                    report['audit_results'] = {}
            
            # Add grade and status
            if report['seo_score'] >= 80:
                report['grade'] = 'excellent'
                report['status_color'] = 'success'
            elif report['seo_score'] >= 60:
                report['grade'] = 'good'
                report['status_color'] = 'info'
            elif report['seo_score'] >= 40:
                report['grade'] = 'needs_improvement'
                report['status_color'] = 'warning'
            else:
                report['grade'] = 'poor'
                report['status_color'] = 'danger'
            
            report['time_ago'] = get_time_ago(report['audit_date'])
        
        return jsonify(ResponseFormatter.paginated(reports, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= KEYWORD TRACKING =======================

@seo_bp.route('/seo/keywords', methods=['GET'])
@admin_required
def get_keywords():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if search:
            where_conditions.append("(sk.keyword LIKE %s OR sk.target_url LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM seo_keywords sk WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get keywords with latest rankings
        keywords_query = f"""
        SELECT sk.*,
               skr.position as current_position,
               skr.search_volume,
               skr.tracked_date as last_tracked,
               LAG(skr.position) OVER (PARTITION BY sk.id ORDER BY skr.tracked_date DESC) as previous_position
        FROM seo_keywords sk
        LEFT JOIN (
            SELECT skr1.*
            FROM seo_keyword_rankings skr1
            INNER JOIN (
                SELECT keyword_id, MAX(tracked_date) as max_date
                FROM seo_keyword_rankings
                GROUP BY keyword_id
            ) skr2 ON skr1.keyword_id = skr2.keyword_id AND skr1.tracked_date = skr2.max_date
        ) skr ON sk.id = skr.keyword_id
        WHERE {where_clause}
        ORDER BY sk.priority DESC, sk.created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        keywords = Database.execute_query(keywords_query, params, fetch=True)
        
        # Add computed fields
        for keyword in keywords:
            # Calculate position change
            if keyword['current_position'] and keyword['previous_position']:
                keyword['position_change'] = keyword['previous_position'] - keyword['current_position']
            else:
                keyword['position_change'] = 0
            
            # Add trend indicator
            if keyword['position_change'] > 0:
                keyword['trend'] = 'up'
                keyword['trend_color'] = 'success'
            elif keyword['position_change'] < 0:
                keyword['trend'] = 'down'
                keyword['trend_color'] = 'danger'
            else:
                keyword['trend'] = 'stable'
                keyword['trend_color'] = 'secondary'
            
            # Add performance status
            if keyword['current_position']:
                if keyword['current_position'] <= 3:
                    keyword['performance'] = 'excellent'
                elif keyword['current_position'] <= 10:
                    keyword['performance'] = 'good'
                elif keyword['current_position'] <= 30:
                    keyword['performance'] = 'average'
                else:
                    keyword['performance'] = 'poor'
            else:
                keyword['performance'] = 'not_ranked'
            
            keyword['last_tracked_ago'] = get_time_ago(keyword['last_tracked']) if keyword['last_tracked'] else 'Never'
        
        return jsonify(ResponseFormatter.paginated(keywords, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/keywords', methods=['POST'])
@admin_required
def add_keyword():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['keyword', 'target_url']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Check for duplicate keyword
        existing_keyword = Database.execute_query(
            "SELECT COUNT(*) as count FROM seo_keywords WHERE keyword = %s AND target_url = %s",
            (data['keyword'], data['target_url']), fetch=True
        )[0]['count']
        
        if existing_keyword > 0:
            return error_response('Keyword already exists for this URL', 400)
        
        # Create keyword
        keyword_query = """
        INSERT INTO seo_keywords (keyword, target_url, search_intent, priority, 
                                notes, is_tracking_enabled, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        keyword_id = Database.execute_query(keyword_query, (
            data['keyword'], data['target_url'], data.get('search_intent', 'informational'),
            int(data.get('priority', 5)), data.get('notes', ''),
            bool(data.get('is_tracking_enabled', True)), datetime.now()
        ))
        
        # Get initial ranking
        try:
            track_keyword_ranking(keyword_id)
        except:
            pass  # Don't fail if initial tracking fails
        
        return success_response({
            'id': keyword_id,
            'keyword': data['keyword']
        }, 'Keyword added successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/keywords/<int:keyword_id>/rankings', methods=['GET'])
@admin_required
def get_keyword_rankings(keyword_id):
    try:
        days = int(request.args.get('days', 30))
        
        # Get ranking history
        rankings_query = """
        SELECT skr.*, sk.keyword, sk.target_url
        FROM seo_keyword_rankings skr
        LEFT JOIN seo_keywords sk ON skr.keyword_id = sk.id
        WHERE skr.keyword_id = %s 
              AND skr.tracked_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY skr.tracked_date DESC
        """
        
        rankings = Database.execute_query(rankings_query, (keyword_id, days), fetch=True)
        
        # Calculate statistics
        if rankings:
            positions = [r['position'] for r in rankings if r['position']]
            stats = {
                'current_position': rankings[0]['position'] if rankings[0]['position'] else None,
                'best_position': min(positions) if positions else None,
                'worst_position': max(positions) if positions else None,
                'average_position': sum(positions) / len(positions) if positions else None,
                'total_data_points': len(rankings)
            }
        else:
            stats = {
                'current_position': None,
                'best_position': None,
                'worst_position': None,
                'average_position': None,
                'total_data_points': 0
            }
        
        return success_response({
            'keyword_id': keyword_id,
            'days': days,
            'rankings': rankings,
            'statistics': stats
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= ANALYTICS INTEGRATION =======================

@seo_bp.route('/seo/analytics/google', methods=['GET'])
@admin_required
def get_google_analytics_settings():
    try:
        settings_data = SiteConfig.get_config('google_analytics_settings')
        
        if settings_data:
            try:
                settings = json.loads(settings_data)
            except:
                settings = {}
        else:
            settings = {
                'ga_tracking_id': '',
                'gtm_container_id': '',
                'enhanced_ecommerce': False,
                'anonymize_ip': True,
                'track_user_id': False,
                'custom_dimensions': [],
                'goals': [],
                'events_to_track': {
                    'page_views': True,
                    'product_views': True,
                    'add_to_cart': True,
                    'purchase': True,
                    'search': True,
                    'downloads': False,
                    'form_submissions': True
                }
            }
        
        return success_response(settings)
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/analytics/google', methods=['PUT'])
@admin_required
def update_google_analytics_settings():
    try:
        data = get_request_data()
        
        SiteConfig.set_config('google_analytics_settings', json.dumps(data))
        
        return success_response(message='Google Analytics settings updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/search-console/settings', methods=['GET'])
@admin_required
def get_search_console_settings():
    try:
        settings_data = SiteConfig.get_config('search_console_settings')
        
        if settings_data:
            try:
                settings = json.loads(settings_data)
            except:
                settings = {}
        else:
            settings = {
                'property_url': '',
                'verification_code': '',
                'api_credentials': {},
                'auto_submit_sitemap': True,
                'track_indexing_status': True,
                'monitor_crawl_errors': True,
                'alert_on_issues': True
            }
        
        return success_response(settings)
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/search-console/submit-sitemap', methods=['POST'])
@admin_required
def submit_sitemap_to_search_console():
    try:
        data = get_request_data()
        sitemap_url = data.get('sitemap_url')
        
        if not sitemap_url:
            base_url = SiteConfig.get_config('site_url') or 'https://example.com'
            sitemap_url = f"{base_url}/sitemap.xml"
        
        # This would integrate with Google Search Console API
        # For now, return success with instructions
        
        return success_response({
            'sitemap_url': sitemap_url,
            'status': 'submitted',
            'instructions': 'To complete setup, manually submit the sitemap in Google Search Console'
        }, 'Sitemap submission initiated')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= SEO ANALYTICS DASHBOARD =======================

@seo_bp.route('/seo/dashboard', methods=['GET'])
@admin_required
def seo_dashboard():
    try:
        days = int(request.args.get('days', 30))
        
        # Overall SEO health
        seo_health_query = """
        SELECT 
            COUNT(*) as total_pages,
            AVG(seo_score) as avg_seo_score,
            SUM(CASE WHEN seo_score >= 80 THEN 1 ELSE 0 END) as excellent_pages,
            SUM(CASE WHEN seo_score >= 60 AND seo_score < 80 THEN 1 ELSE 0 END) as good_pages,
            SUM(CASE WHEN seo_score < 60 THEN 1 ELSE 0 END) as needs_improvement_pages,
            COUNT(CASE WHEN last_audited IS NULL OR last_audited < DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) as pages_need_audit
        FROM seo_pages
        WHERE is_indexable = 1
        """
        seo_health = Database.execute_query(seo_health_query, fetch=True)[0]
        
        # Keyword performance
        keyword_performance_query = """
        SELECT 
            COUNT(DISTINCT sk.id) as total_keywords,
            COUNT(CASE WHEN skr.position <= 10 THEN 1 END) as top_10_keywords,
            COUNT(CASE WHEN skr.position <= 3 THEN 1 END) as top_3_keywords,
            AVG(skr.position) as avg_position
        FROM seo_keywords sk
        LEFT JOIN (
            SELECT DISTINCT keyword_id, position,
                   ROW_NUMBER() OVER (PARTITION BY keyword_id ORDER BY tracked_date DESC) as rn
            FROM seo_keyword_rankings
        ) skr ON sk.id = skr.keyword_id AND skr.rn = 1
        WHERE sk.is_tracking_enabled = 1
        """
        keyword_perf = Database.execute_query(keyword_performance_query, fetch=True)[0]
        
        # Recent audit activity
        recent_audits_query = """
        SELECT DATE(audit_date) as audit_date, 
               COUNT(*) as audits_count,
               AVG(seo_score) as avg_score
        FROM seo_audits
        WHERE audit_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY DATE(audit_date)
        ORDER BY audit_date DESC
        """
        recent_audits = Database.execute_query(recent_audits_query, (days,), fetch=True)
        
        # Top issues
        top_issues_query = """
        SELECT 
            JSON_EXTRACT(audit_results, '$.issues') as issues,
            COUNT(*) as frequency
        FROM seo_audits
        WHERE audit_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
              AND JSON_EXTRACT(audit_results, '$.issues') IS NOT NULL
        GROUP BY JSON_EXTRACT(audit_results, '$.issues')
        ORDER BY frequency DESC
        LIMIT 10
        """
        # Note: This query might need adjustment based on your JSON structure
        
        # Sitemap status
        sitemap_status_query = """
        SELECT * FROM sitemap_generations 
        ORDER BY generated_at DESC 
        LIMIT 1
        """
        sitemap_status = Database.execute_query(sitemap_status_query, fetch=True)
        
        # Convert averages to float
        if seo_health['avg_seo_score']:
            seo_health['avg_seo_score'] = round(float(seo_health['avg_seo_score']), 1)
        if keyword_perf['avg_position']:
            keyword_perf['avg_position'] = round(float(keyword_perf['avg_position']), 1)
        
        return success_response({
            'days': days,
            'seo_health': seo_health,
            'keyword_performance': keyword_perf,
            'recent_audits': recent_audits,
            'sitemap_status': sitemap_status[0] if sitemap_status else None,
            'recommendations': generate_seo_recommendations(seo_health, keyword_perf)
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= UTILITY FUNCTIONS =======================

def audit_seo_page(page_id, audit_type='full'):
    """Perform SEO audit on a specific page"""
    try:
        # Get page data
        page = Database.execute_query(
            "SELECT * FROM seo_pages WHERE id = %s", (page_id,), fetch=True
        )[0]
        
        score = 0
        issues = []
        suggestions = []
        
        # Meta title check (20 points)
        if page['meta_title']:
            title_length = len(page['meta_title'])
            if 30 <= title_length <= 60:
                score += 20
            elif title_length > 0:
                score += 10
                if title_length < 30:
                    issues.append('Meta title too short (< 30 characters)')
                else:
                    issues.append('Meta title too long (> 60 characters)')
        else:
            issues.append('Missing meta title')
        
        # Meta description check (20 points)
        if page['meta_description']:
            desc_length = len(page['meta_description'])
            if 120 <= desc_length <= 160:
                score += 20
            elif desc_length > 0:
                score += 10
                if desc_length < 120:
                    issues.append('Meta description too short (< 120 characters)')
                else:
                    issues.append('Meta description too long (> 160 characters)')
        else:
            issues.append('Missing meta description')
        
        # Focus keyword check (15 points)
        if page['focus_keyword']:
            score += 15
            keyword = page['focus_keyword'].lower()
            
            # Check keyword in title
            if page['meta_title'] and keyword in page['meta_title'].lower():
                score += 5
            else:
                suggestions.append('Include focus keyword in meta title')
            
            # Check keyword in description
            if page['meta_description'] and keyword in page['meta_description'].lower():
                score += 5
            else:
                suggestions.append('Include focus keyword in meta description')
        else:
            issues.append('Missing focus keyword')
        
        # Open Graph tags check (10 points)
        if page['open_graph_tags']:
            try:
                og_tags = json.loads(page['open_graph_tags'])
                if og_tags.get('og:title') and og_tags.get('og:description'):
                    score += 10
                else:
                    score += 5
                    suggestions.append('Complete Open Graph tags (title, description, image)')
            except:
                suggestions.append('Fix Open Graph tags format')
        else:
            suggestions.append('Add Open Graph tags for social media')
        
        # Canonical URL check (10 points)
        if page['canonical_url']:
            score += 10
        else:
            suggestions.append('Add canonical URL to prevent duplicate content')
        
        # Robots directive check (10 points)
        if page['robots_directive'] and 'index' in page['robots_directive']:
            score += 10
        else:
            issues.append('Page set to noindex or missing robots directive')
        
        # Structured data check (10 points)
        if page['structured_data']:
            try:
                structured_data = json.loads(page['structured_data'])
                if structured_data and structured_data.get('@type'):
                    score += 10
                else:
                    score += 5
                    suggestions.append('Add proper structured data markup')
            except:
                suggestions.append('Fix structured data format')
        else:
            suggestions.append('Add structured data markup')
        
        # Determine grade
        if score >= 80:
            grade = 'excellent'
        elif score >= 60:
            grade = 'good'
        elif score >= 40:
            grade = 'needs_improvement'
        else:
            grade = 'poor'
        
        # Update page score
        Database.execute_query(
            "UPDATE seo_pages SET seo_score = %s, last_audited = %s WHERE id = %s",
            (score, datetime.now(), page_id)
        )
        
        # Save audit results
        audit_results = {
            'score': score,
            'grade': grade,
            'issues': issues,
            'suggestions': suggestions,
            'audit_type': audit_type
        }
        
        Database.execute_query(
            "INSERT INTO seo_audits (page_id, seo_score, audit_results, audit_date) VALUES (%s, %s, %s, %s)",
            (page_id, score, json.dumps(audit_results), datetime.now())
        )
        
        return audit_results
        
    except Exception as e:
        raise e

def validate_robots_txt(content):
    """Basic robots.txt validation"""
    try:
        lines = content.strip().split('\n')
        has_user_agent = False
        
        for line in lines:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            
            if line.lower().startswith('user-agent:'):
                has_user_agent = True
            elif line.lower().startswith(('allow:', 'disallow:', 'sitemap:', 'crawl-delay:')):
                continue
            else:
                # Unknown directive, might be invalid
                return False
        
        return has_user_agent
        
    except:
        return False

def validate_schema_structure(schema_data):
    """Validate schema.org structured data"""
    try:
        if isinstance(schema_data, str):
            schema_data = json.loads(schema_data)
        
        errors = []
        warnings = []
        suggestions = []
        
        # Check required fields
        if '@context' not in schema_data:
            errors.append('Missing @context field')
        elif schema_data['@context'] != 'https://schema.org':
            warnings.append('Recommended @context is https://schema.org')
        
        if '@type' not in schema_data:
            errors.append('Missing @type field')
        
        # Type-specific validation
        schema_type = schema_data.get('@type', '')
        
        if schema_type == 'Product':
            required_fields = ['name', 'description', 'offers']
            for field in required_fields:
                if field not in schema_data:
                    errors.append(f'Missing required field for Product: {field}')
        
        elif schema_type == 'Organization':
            required_fields = ['name', 'url']
            for field in required_fields:
                if field not in schema_data:
                    errors.append(f'Missing required field for Organization: {field}')
        
        elif schema_type == 'Article':
            required_fields = ['headline', 'author', 'datePublished']
            for field in required_fields:
                if field not in schema_data:
                    errors.append(f'Missing required field for Article: {field}')
        
        # General suggestions
        if 'image' not in schema_data and schema_type in ['Product', 'Article', 'Organization']:
            suggestions.append('Consider adding an image for better rich snippets')
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'suggestions': suggestions
        }
        
    except Exception as e:
        return {
            'is_valid': False,
            'errors': [f'Validation error: {str(e)}'],
            'warnings': [],
            'suggestions': []
        }

def track_keyword_ranking(keyword_id):
    """Track keyword ranking position (placeholder - would integrate with SEO APIs)"""
    try:
        # This would integrate with real SEO APIs like SEMrush, Ahrefs, or SERPApi
        # For now, return mock data
        
        import random
        mock_position = random.randint(1, 100) if random.random() > 0.3 else None
        mock_search_volume = random.randint(100, 10000)
        
        Database.execute_query(
            """INSERT INTO seo_keyword_rankings (keyword_id, position, search_volume, tracked_date)
               VALUES (%s, %s, %s, %s)""",
            (keyword_id, mock_position, mock_search_volume, datetime.now())
        )
        
        return True
        
    except Exception as e:
        return False

def generate_seo_recommendations(seo_health, keyword_perf):
    """Generate SEO recommendations based on data"""
    recommendations = []
    
    # SEO score recommendations
    if seo_health['avg_seo_score'] < 60:
        recommendations.append({
            'type': 'critical',
            'title': 'Improve Overall SEO Health',
            'description': 'Your average SEO score is below 60. Focus on meta tags, content optimization, and technical SEO.',
            'priority': 'high'
        })
    
    if seo_health['pages_need_audit'] > 0:
        recommendations.append({
            'type': 'maintenance',
            'title': 'Run SEO Audits',
            'description': f'{seo_health["pages_need_audit"]} pages need SEO auditing. Regular audits help maintain SEO health.',
            'priority': 'medium'
        })
    
    # Keyword recommendations
    if keyword_perf['total_keywords'] < 10:
        recommendations.append({
            'type': 'growth',
            'title': 'Add More Keywords',
            'description': 'Track more keywords to improve search visibility. Aim for 20-50 relevant keywords.',
            'priority': 'medium'
        })
    
    if keyword_perf['top_10_keywords'] == 0:
        recommendations.append({
            'type': 'optimization',
            'title': 'Improve Keyword Rankings',
            'description': 'No keywords ranking in top 10. Focus on content optimization and link building.',
            'priority': 'high'
        })
    
    return recommendations

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

# ======================= PUBLIC ENDPOINTS =======================

@seo_bp.route('/seo/robots.txt', methods=['GET'])
def serve_robots_txt():
    """Serve robots.txt file (public endpoint)"""
    try:
        robots_content = SiteConfig.get_config('robots_txt_content')
        
        if not robots_content:
            # Generate default robots.txt
            base_url = request.host_url.rstrip('/')
            robots_content = f"""User-agent: *
Allow: /

Sitemap: {base_url}/sitemap.xml

Disallow: /admin/
Disallow: /api/
"""
        
        response = make_response(robots_content)
        response.headers['Content-Type'] = 'text/plain'
        return response
        
    except Exception as e:
        response = make_response("User-agent: *\nAllow: /")
        response.headers['Content-Type'] = 'text/plain'
        return response

@seo_bp.route('/seo/sitemap.xml', methods=['GET'])
def serve_sitemap():
    """Serve sitemap.xml file (public endpoint)"""
    try:
        sitemap_path = 'uploads/sitemap.xml'
        
        if os.path.exists(sitemap_path):
            with open(sitemap_path, 'r', encoding='utf-8') as f:
                sitemap_content = f.read()
            
            response = make_response(sitemap_content)
            response.headers['Content-Type'] = 'application/xml'
            return response
        else:
            # Generate basic sitemap on-the-fly
            base_url = request.host_url.rstrip('/')
            
            urlset = ET.Element('urlset')
            urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
            
            # Add homepage
            url_elem = ET.SubElement(urlset, 'url')
            ET.SubElement(url_elem, 'loc').text = base_url
            ET.SubElement(url_elem, 'lastmod').text = datetime.now().strftime('%Y-%m-%d')
            ET.SubElement(url_elem, 'changefreq').text = 'weekly'
            ET.SubElement(url_elem, 'priority').text = '1.0'
            
            xml_content = ET.tostring(urlset, encoding='unicode')
            xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
            
            response = make_response(xml_declaration + xml_content)
            response.headers['Content-Type'] = 'application/xml'
            return response
        
    except Exception as e:
        response = make_response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>')
        response.headers['Content-Type'] = 'application/xml'
        return response

# ======================= SEO STATISTICS =======================

@seo_bp.route('/seo/stats', methods=['GET'])
@admin_required
def get_seo_stats():
    try:
        # Overall SEO statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_pages,
            AVG(seo_score) as avg_seo_score,
            SUM(CASE WHEN seo_score >= 80 THEN 1 ELSE 0 END) as excellent_pages,
            SUM(CASE WHEN seo_score >= 60 AND seo_score < 80 THEN 1 ELSE 0 END) as good_pages,
            SUM(CASE WHEN seo_score < 60 THEN 1 ELSE 0 END) as poor_pages,
            COUNT(CASE WHEN last_audited >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 END) as recently_audited
        FROM seo_pages
        WHERE is_indexable = 1
        """
        
        stats = Database.execute_query(stats_query, fetch=True)[0]
        
        # Keyword statistics
        keyword_stats = Database.execute_query(keyword_stats_query, fetch=True)[0]
        
        # Audit statistics
        audit_stats_query = """
        SELECT 
            COUNT(*) as total_audits,
            COUNT(CASE WHEN audit_date >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) as audits_last_30d,
            AVG(seo_score) as avg_audit_score
        FROM seo_audits
        """
        
        audit_stats = Database.execute_query(audit_stats_query, fetch=True)[0]
        
        # Convert averages to float
        if stats['avg_seo_score']:
            stats['avg_seo_score'] = round(float(stats['avg_seo_score']), 1)
        if keyword_stats['avg_position']:
            keyword_stats['avg_position'] = round(float(keyword_stats['avg_position']), 1)
        if audit_stats['avg_audit_score']:
            audit_stats['avg_audit_score'] = round(float(audit_stats['avg_audit_score']), 1)
        
        # Combine all statistics
        combined_stats = {**stats, **keyword_stats, **audit_stats}
        
        return success_response(combined_stats)
        
    except Exception as e:
        return error_response(str(e), 500)_query = """
        SELECT 
            COUNT(*) as total_keywords,
            COUNT(CASE WHEN is_tracking_enabled = 1 THEN 1 END) as tracked_keywords,
            AVG(skr.position) as avg_position
        FROM seo_keywords sk
        LEFT JOIN (
            SELECT DISTINCT keyword_id, position,
                   ROW_NUMBER() OVER (PARTITION BY keyword_id ORDER BY tracked_date DESC) as rn
            FROM seo_keyword_rankings
        ) skr ON sk.id = skr.keyword_id AND skr.rn = 1
        """
        
        keyword_stats