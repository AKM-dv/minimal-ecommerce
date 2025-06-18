from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required
from datetime import datetime, timedelta
import json
import os
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

from utils.database import Database
from utils.response_formatter import ResponseFormatter, success_response, error_response
from utils.helpers import get_request_data
from utils.validation import validate_required_fields
from admin.auth import admin_required
from admin.config import SiteConfig

# Create SEO blueprint
seo_bp = Blueprint('seo', __name__)

# ======================= SEO DASHBOARD =======================

@seo_bp.route('/seo/dashboard', methods=['GET'])
@admin_required
def get_seo_dashboard():
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
        
        # Top issues (simplified)
        top_issues_query = """
        SELECT 
            issue_type,
            severity,
            COUNT(*) as frequency
        FROM seo_issues
        WHERE detected_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
              AND status = 'open'
        GROUP BY issue_type, severity
        ORDER BY frequency DESC
        LIMIT 10
        """
        top_issues = Database.execute_query(top_issues_query, (days,), fetch=True)
        
        # Generate recommendations
        recommendations = generate_seo_recommendations(seo_health, keyword_perf)
        
        return success_response({
            'seo_health': seo_health,
            'keyword_performance': keyword_perf,
            'recent_audits': recent_audits,
            'top_issues': top_issues,
            'recommendations': recommendations,
            'period_days': days
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= SEO PAGES MANAGEMENT =======================

@seo_bp.route('/seo/pages', methods=['GET'])
@admin_required
def get_seo_pages():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '')
        page_type = request.args.get('type', '')
        score_filter = request.args.get('score_filter', '')
        
        offset = (page - 1) * per_page
        
        # Build query conditions
        conditions = ["1=1"]
        params = []
        
        if search:
            conditions.append("(page_url LIKE %s OR page_title LIKE %s OR meta_title LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        if page_type:
            conditions.append("page_type = %s")
            params.append(page_type)
        
        if score_filter:
            if score_filter == 'excellent':
                conditions.append("seo_score >= 80")
            elif score_filter == 'good':
                conditions.append("seo_score >= 60 AND seo_score < 80")
            elif score_filter == 'needs_improvement':
                conditions.append("seo_score < 60")
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM seo_pages WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get pages
        pages_query = f"""
        SELECT *,
               CASE 
                   WHEN seo_score >= 80 THEN 'excellent'
                   WHEN seo_score >= 60 THEN 'good'
                   WHEN seo_score >= 40 THEN 'needs_improvement'
                   ELSE 'poor'
               END as seo_grade,
               DATEDIFF(NOW(), last_audited) as days_since_audit
        FROM seo_pages 
        WHERE {where_clause}
        ORDER BY seo_score DESC, updated_at DESC
        LIMIT %s OFFSET %s
        """
        
        params.extend([per_page, offset])
        pages = Database.execute_query(pages_query, params, fetch=True)
        
        # Process page data
        for page_data in pages:
            # Parse JSON fields
            json_fields = ['meta_tags', 'open_graph_tags', 'twitter_card_tags', 'structured_data']
            for field in json_fields:
                if page_data.get(field):
                    try:
                        page_data[field] = json.loads(page_data[field])
                    except:
                        page_data[field] = {}
            
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
        SELECT *,
               CASE 
                   WHEN seo_score >= 80 THEN 'excellent'
                   WHEN seo_score >= 60 THEN 'good'
                   WHEN seo_score >= 40 THEN 'needs_improvement'
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

@seo_bp.route('/seo/pages/<int:page_id>', methods=['DELETE'])
@admin_required
def delete_seo_page(page_id):
    try:
        # Check if page exists
        existing_page = Database.execute_query(
            "SELECT * FROM seo_pages WHERE id = %s", (page_id,), fetch=True
        )
        if not existing_page:
            return error_response('SEO page not found', 404)
        
        # Delete page (cascade will handle related records)
        Database.execute_query("DELETE FROM seo_pages WHERE id = %s", (page_id,))
        
        return success_response(message='SEO page deleted successfully')
        
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
        
        # Add SEO pages
        pages = Database.execute_query(
            "SELECT page_url, updated_at, page_type FROM seo_pages WHERE is_indexable = 1",
            fetch=True
        )
        
        for page in pages:
            url_elem = ET.SubElement(urlset, 'url')
            full_url = urljoin(base_url, page['page_url'])
            ET.SubElement(url_elem, 'loc').text = full_url
            
            if page['updated_at']:
                ET.SubElement(url_elem, 'lastmod').text = page['updated_at'].strftime('%Y-%m-%d')
            
            # Set change frequency based on page type
            if page['page_type'] == 'homepage':
                ET.SubElement(url_elem, 'changefreq').text = 'daily'
                ET.SubElement(url_elem, 'priority').text = '1.0'
            elif page['page_type'] == 'product':
                ET.SubElement(url_elem, 'changefreq').text = 'weekly'
                ET.SubElement(url_elem, 'priority').text = '0.8'
            elif page['page_type'] == 'category':
                ET.SubElement(url_elem, 'changefreq').text = 'weekly'
                ET.SubElement(url_elem, 'priority').text = '0.7'
            elif page['page_type'] == 'blog':
                ET.SubElement(url_elem, 'changefreq').text = 'monthly'
                ET.SubElement(url_elem, 'priority').text = '0.6'
            else:
                ET.SubElement(url_elem, 'changefreq').text = 'monthly'
                ET.SubElement(url_elem, 'priority').text = '0.5'
        
        # Generate XML content
        xml_content = ET.tostring(urlset, encoding='unicode')
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        final_xml = xml_declaration + xml_content
        
        # Save to file
        sitemap_path = 'uploads/sitemap.xml'
        os.makedirs(os.path.dirname(sitemap_path), exist_ok=True)
        with open(sitemap_path, 'w', encoding='utf-8') as f:
            f.write(final_xml)
        
        # Record generation
        Database.execute_query(
            """INSERT INTO sitemap_generations (urls_count, file_path, file_size, 
                                              generation_status, generated_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (len(pages) + 1, sitemap_path, len(final_xml.encode('utf-8')), 'completed', datetime.now())
        )
        
        # Update config
        SiteConfig.set_config('sitemap_last_generated', datetime.now().isoformat())
        
        return success_response({
            'urls_count': len(pages) + 1,
            'file_size': len(final_xml.encode('utf-8')),
            'file_path': sitemap_path,
            'generated_at': datetime.now().isoformat()
        }, 'Sitemap generated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/sitemap/status', methods=['GET'])
@admin_required
def get_sitemap_status():
    try:
        # Get latest generation
        latest_generation = Database.execute_query(
            "SELECT * FROM sitemap_generations ORDER BY generated_at DESC LIMIT 1",
            fetch=True
        )
        
        sitemap_path = 'uploads/sitemap.xml'
        exists = os.path.exists(sitemap_path)
        
        return success_response({
            'exists': exists,
            'latest_generation': latest_generation[0] if latest_generation else None,
            'last_generated': SiteConfig.get_config('sitemap_last_generated'),
            'file_path': sitemap_path if exists else None
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
            base_url = request.host_url.rstrip('/')
            robots_content = f"""User-agent: *
Allow: /

# Sitemap location
Sitemap: {base_url}/sitemap.xml

# Disallow admin areas
Disallow: /admin/
Disallow: /api/

# Disallow search and filter URLs
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
                }
            },
            'product': {
                '@context': 'https://schema.org',
                '@type': 'Product',
                'name': '',
                'description': '',
                'brand': {
                    '@type': 'Brand',
                    'name': ''
                },
                'offers': {
                    '@type': 'Offer',
                    'price': '',
                    'priceCurrency': 'INR',
                    'availability': 'https://schema.org/InStock'
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
                'author': {
                    '@type': 'Person',
                    'name': ''
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
        SELECT sa.*, sp.page_url, sp.page_title
        FROM seo_audits sa
        JOIN seo_pages sp ON sa.page_id = sp.id
        WHERE sa.audit_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY sa.audit_date DESC
        LIMIT %s OFFSET %s
        """
        
        reports = Database.execute_query(reports_query, (days, per_page, offset), fetch=True)
        
        # Get total count
        count_query = """
        SELECT COUNT(*) as total
        FROM seo_audits sa
        WHERE sa.audit_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        total = Database.execute_query(count_query, (days,), fetch=True)[0]['total']
        
        # Process audit results
        for report in reports:
            if report.get('audit_results'):
                try:
                    report['audit_results'] = json.loads(report['audit_results'])
                except:
                    report['audit_results'] = {}
        
        return jsonify(ResponseFormatter.paginated(reports, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= KEYWORDS MANAGEMENT =======================

@seo_bp.route('/seo/keywords', methods=['GET'])
@admin_required
def get_keywords():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '')
        
        offset = (page - 1) * per_page
        
        # Build query conditions
        conditions = ["1=1"]
        params = []
        
        if search:
            conditions.append("(keyword LIKE %s OR target_url LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param])
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM seo_keywords WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get keywords with latest ranking
        keywords_query = f"""
        SELECT sk.*, 
               skr.position as current_position,
               skr.search_volume,
               skr.tracked_date as last_tracked
        FROM seo_keywords sk
        LEFT JOIN (
            SELECT DISTINCT keyword_id, position, search_volume, tracked_date,
                   ROW_NUMBER() OVER (PARTITION BY keyword_id ORDER BY tracked_date DESC) as rn
            FROM seo_keyword_rankings
        ) skr ON sk.id = skr.keyword_id AND skr.rn = 1
        WHERE {where_clause}
        ORDER BY sk.priority DESC, sk.created_at DESC
        LIMIT %s OFFSET %s
        """
        
        params.extend([per_page, offset])
        keywords = Database.execute_query(keywords_query, params, fetch=True)
        
        return jsonify(ResponseFormatter.paginated(keywords, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/keywords', methods=['POST'])
@admin_required
def create_keyword():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['keyword', 'target_url']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Check for duplicate
        existing_keyword = Database.execute_query(
            "SELECT COUNT(*) as count FROM seo_keywords WHERE keyword = %s AND target_url = %s",
            (data['keyword'], data['target_url']), fetch=True
        )[0]['count']
        
        if existing_keyword > 0:
            return error_response('Keyword already exists for this URL', 400)
        
        # Create keyword
        keyword_id = Database.execute_query(
            """INSERT INTO seo_keywords (keyword, target_url, search_intent, priority, 
                                       notes, is_tracking_enabled, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (data['keyword'], data['target_url'], data.get('search_intent', 'informational'),
             data.get('priority', 5), data.get('notes', ''), 
             bool(data.get('is_tracking_enabled', True)), datetime.now())
        )
        
        # Start tracking if enabled
        if data.get('is_tracking_enabled', True):
            track_keyword_ranking(keyword_id)
        
        return success_response({
            'id': keyword_id,
            'keyword': data['keyword']
        }, 'Keyword created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/keywords/<int:keyword_id>', methods=['PUT'])
@admin_required
def update_keyword(keyword_id):
    try:
        data = get_request_data()
        
        # Check if keyword exists
        existing_keyword = Database.execute_query(
            "SELECT * FROM seo_keywords WHERE id = %s", (keyword_id,), fetch=True
        )
        if not existing_keyword:
            return error_response('Keyword not found', 404)
        
        # Build update query
        update_fields = []
        params = []
        
        updatable_fields = ['keyword', 'target_url', 'search_intent', 'priority', 'notes', 'is_tracking_enabled']
        
        for field in updatable_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                if field == 'is_tracking_enabled':
                    params.append(bool(data[field]))
                else:
                    params.append(data[field])
        
        if not update_fields:
            return error_response('No fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(keyword_id)
        
        query = f"UPDATE seo_keywords SET {', '.join(update_fields)} WHERE id = %s"
        Database.execute_query(query, params)
        
        return success_response(message='Keyword updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@seo_bp.route('/seo/keywords/<int:keyword_id>', methods=['DELETE'])
@admin_required
def delete_keyword(keyword_id):
    try:
        # Check if keyword exists
        existing_keyword = Database.execute_query(
            "SELECT * FROM seo_keywords WHERE id = %s", (keyword_id,), fetch=True
        )
        if not existing_keyword:
            return error_response('Keyword not found', 404)
        
        # Delete keyword (cascade will handle rankings)
        Database.execute_query("DELETE FROM seo_keywords WHERE id = %s", (keyword_id,))
        
        return success_response(message='Keyword deleted successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

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
            SUM(CASE WHEN seo_score < 60 THEN 1 ELSE 0 END) as needs_improvement_pages
        FROM seo_pages
        WHERE is_indexable = 1
        """
        
        stats = Database.execute_query(stats_query, fetch=True)[0]
        
        # Keyword statistics
        keyword_stats_query = """
        SELECT 
            COUNT(*) as total_keywords,
            COUNT(CASE WHEN is_tracking_enabled = 1 THEN 1 END) as tracking_enabled,
            AVG(priority) as avg_priority
        FROM seo_keywords
        """
        
        keyword_stats = Database.execute_query(keyword_stats_query, fetch=True)[0]
        
        # Recent audit statistics
        audit_stats_query = """
        SELECT 
            COUNT(*) as total_audits,
            AVG(seo_score) as avg_audit_score
        FROM seo_audits
        WHERE audit_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        
        audit_stats = Database.execute_query(audit_stats_query, fetch=True)[0]
        
        return success_response({
            'page_stats': stats,
            'keyword_stats': keyword_stats,
            'audit_stats': audit_stats
        })
        
    except Exception as e:
        return error_response(str(e), 500)

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

# ======================= HELPER FUNCTIONS =======================

def audit_seo_page(page_id, audit_type='full'):
    """Perform SEO audit on a page"""
    try:
        # Get page data
        page_data = Database.execute_query(
            "SELECT * FROM seo_pages WHERE id = %s", (page_id,), fetch=True
        )[0]
        
        score = 0
        issues = []
        suggestions = []
        
        # Basic SEO checks
        if page_data['meta_title']:
            score += 20
            if len(page_data['meta_title']) > 60:
                issues.append('Meta title too long (over 60 characters)')
            elif len(page_data['meta_title']) < 30:
                suggestions.append('Consider making meta title longer (30-60 characters)')
        else:
            issues.append('Missing meta title')
        
        if page_data['meta_description']:
            score += 20
            if len(page_data['meta_description']) > 160:
                issues.append('Meta description too long (over 160 characters)')
            elif len(page_data['meta_description']) < 120:
                suggestions.append('Consider making meta description longer (120-160 characters)')
        else:
            issues.append('Missing meta description')
        
        if page_data['focus_keyword']:
            score += 15
            # Check if keyword is in title
            if page_data['meta_title'] and page_data['focus_keyword'].lower() in page_data['meta_title'].lower():
                score += 10
            else:
                suggestions.append('Include focus keyword in meta title')
            
            # Check if keyword is in description
            if page_data['meta_description'] and page_data['focus_keyword'].lower() in page_data['meta_description'].lower():
                score += 10
            else:
                suggestions.append('Include focus keyword in meta description')
        else:
            suggestions.append('Set a focus keyword for this page')
        
        if page_data['canonical_url']:
            score += 10
        else:
            suggestions.append('Add canonical URL to avoid duplicate content issues')
        
        # Check structured data
        if page_data['structured_data']:
            try:
                structured_data = json.loads(page_data['structured_data'])
                if structured_data and structured_data.get('@type'):
                    score += 15
                else:
                    suggestions.append('Add valid structured data markup')
            except:
                issues.append('Invalid structured data JSON')
        else:
            suggestions.append('Add structured data markup for better rich snippets')
        
        # Check robots directive
        if page_data['robots_directive'] and 'noindex' not in page_data['robots_directive']:
            score += 10
        elif 'noindex' in page_data['robots_directive']:
            issues.append('Page is set to noindex')
        
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
    if keyword_perf['total_keywords'] < 20:
        recommendations.append({
            'type': 'optimization',
            'title': 'Expand Keyword Strategy',
            'description': 'You have fewer than 20 keywords tracked. Aim for 20-50 relevant keywords.',
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