from flask import Blueprint, request, jsonify
import json
from datetime import datetime, timedelta
import uuid
import re
import os

# Import our modules
from models import Database
from utils import (admin_required, success_response, error_response, get_request_data, 
                   ResponseFormatter, save_image)

# Create blueprint
product_reviews_bp = Blueprint('product_reviews', __name__)

# ======================= PRODUCT REVIEWS CRUD ROUTES =======================

@product_reviews_bp.route('/product-reviews', methods=['GET'])
@admin_required
def get_product_reviews():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        product_id = request.args.get('product_id')
        rating = request.args.get('rating')  # 1-5 stars
        status = request.args.get('status')  # approved, pending, rejected, flagged
        verified_only = request.args.get('verified_only', 'false').lower() == 'true'
        has_media = request.args.get('has_media', 'false').lower() == 'true'
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if product_id:
            where_conditions.append("pr.product_id = %s")
            params.append(product_id)
        
        if rating:
            where_conditions.append("pr.rating = %s")
            params.append(int(rating))
        
        if status == 'approved':
            where_conditions.append("pr.is_approved = 1 AND pr.is_flagged = 0")
        elif status == 'pending':
            where_conditions.append("pr.is_approved = 0 AND pr.is_flagged = 0")
        elif status == 'rejected':
            where_conditions.append("pr.is_approved = 0 AND pr.admin_response IS NOT NULL")
        elif status == 'flagged':
            where_conditions.append("pr.is_flagged = 1")
        
        if verified_only:
            where_conditions.append("pr.is_verified_purchase = 1")
        
        if has_media:
            where_conditions.append("(pr.review_images IS NOT NULL OR pr.review_videos IS NOT NULL)")
        
        if search:
            where_conditions.append("(pr.title LIKE %s OR pr.review_text LIKE %s OR c.name LIKE %s OR p.name LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])
        
        if start_date:
            where_conditions.append("DATE(pr.created_at) >= %s")
            params.append(start_date)
        
        if end_date:
            where_conditions.append("DATE(pr.created_at) <= %s")
            params.append(end_date)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Validate sort columns
        valid_sort_columns = ['rating', 'created_at', 'helpfulness_score', 'product_name', 'customer_name']
        if sort_by not in valid_sort_columns:
            sort_by = 'created_at'
        
        sort_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'
        
        # Get total count
        count_query = f"""
        SELECT COUNT(*) as total FROM product_reviews pr 
        LEFT JOIN customers c ON pr.customer_id = c.id
        LEFT JOIN products p ON pr.product_id = p.id
        WHERE {where_clause}
        """
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get reviews with related data
        reviews_query = f"""
        SELECT pr.*, 
               c.name as customer_name, c.email as customer_email,
               p.name as product_name, p.sku as product_sku, p.images as product_images,
               CASE 
                   WHEN pr.is_flagged = 1 THEN 'flagged'
                   WHEN pr.is_approved = 1 THEN 'approved'
                   WHEN pr.admin_response IS NOT NULL THEN 'rejected'
                   ELSE 'pending'
               END as computed_status,
               (SELECT COUNT(*) FROM review_helpfulness rh WHERE rh.review_id = pr.id AND rh.is_helpful = 1) as helpful_votes,
               (SELECT COUNT(*) FROM review_helpfulness rh WHERE rh.review_id = pr.id AND rh.is_helpful = 0) as not_helpful_votes,
               (SELECT COUNT(*) FROM review_reports rr WHERE rr.review_id = pr.id) as report_count
        FROM product_reviews pr
        LEFT JOIN customers c ON pr.customer_id = c.id
        LEFT JOIN products p ON pr.product_id = p.id
        WHERE {where_clause}
        ORDER BY 
            CASE WHEN '{sort_by}' = 'product_name' THEN p.name
                 WHEN '{sort_by}' = 'customer_name' THEN c.name
                 ELSE NULL END {sort_direction},
            CASE WHEN '{sort_by}' = 'rating' THEN pr.rating
                 WHEN '{sort_by}' = 'helpfulness_score' THEN pr.helpfulness_score
                 ELSE NULL END {sort_direction},
            CASE WHEN '{sort_by}' = 'created_at' THEN pr.created_at
                 ELSE NULL END {sort_direction}
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        reviews = Database.execute_query(reviews_query, params, fetch=True)
        
        # Parse JSON fields and add computed data
        for review in reviews:
            # Parse review images
            if review.get('review_images'):
                try:
                    review['review_images'] = json.loads(review['review_images'])
                except:
                    review['review_images'] = []
            else:
                review['review_images'] = []
            
            # Parse review videos
            if review.get('review_videos'):
                try:
                    review['review_videos'] = json.loads(review['review_videos'])
                except:
                    review['review_videos'] = []
            else:
                review['review_videos'] = []
            
            # Parse product images for thumbnail
            if review.get('product_images'):
                try:
                    product_images = json.loads(review['product_images'])
                    review['product_thumbnail'] = product_images[0]['url'] if product_images else ''
                except:
                    review['product_thumbnail'] = ''
                del review['product_images']  # Remove full images array
            else:
                review['product_thumbnail'] = ''
            
            # Add review summary
            if review['review_text'] and len(review['review_text']) > 150:
                review['review_summary'] = review['review_text'][:150] + '...'
            else:
                review['review_summary'] = review['review_text']
            
            # Calculate total votes
            review['total_votes'] = review['helpful_votes'] + review['not_helpful_votes']
            
            # Add time ago
            review['time_ago'] = get_time_ago(review['created_at'])
            
            # Add quality score
            review['quality_score'] = calculate_review_quality_score(review)
        
        return jsonify(ResponseFormatter.paginated(reviews, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@product_reviews_bp.route('/product-reviews/<int:review_id>', methods=['GET'])
@admin_required
def get_product_review(review_id):
    try:
        # Get review details with all related data
        review_query = """
        SELECT pr.*, 
               c.name as customer_name, c.email as customer_email, c.phone as customer_phone,
               p.name as product_name, p.sku as product_sku, p.price as product_price,
               o.order_number, o.created_at as order_date,
               CASE 
                   WHEN pr.is_flagged = 1 THEN 'flagged'
                   WHEN pr.is_approved = 1 THEN 'approved'
                   WHEN pr.admin_response IS NOT NULL THEN 'rejected'
                   ELSE 'pending'
               END as computed_status
        FROM product_reviews pr
        LEFT JOIN customers c ON pr.customer_id = c.id
        LEFT JOIN products p ON pr.product_id = p.id
        LEFT JOIN orders o ON pr.order_id = o.id
        WHERE pr.id = %s
        """
        
        review_result = Database.execute_query(review_query, (review_id,), fetch=True)
        
        if not review_result:
            return error_response('Review not found', 404)
        
        review = review_result[0]
        
        # Parse JSON fields
        if review.get('review_images'):
            try:
                review['review_images'] = json.loads(review['review_images'])
            except:
                review['review_images'] = []
        
        if review.get('review_videos'):
            try:
                review['review_videos'] = json.loads(review['review_videos'])
            except:
                review['review_videos'] = []
        
        # Get helpfulness votes
        helpfulness_query = """
        SELECT 
            SUM(CASE WHEN is_helpful = 1 THEN 1 ELSE 0 END) as helpful_votes,
            SUM(CASE WHEN is_helpful = 0 THEN 1 ELSE 0 END) as not_helpful_votes,
            COUNT(*) as total_votes
        FROM review_helpfulness 
        WHERE review_id = %s
        """
        helpfulness_result = Database.execute_query(helpfulness_query, (review_id,), fetch=True)[0]
        review.update(helpfulness_result)
        
        # Get reports
        reports_query = """
        SELECT rr.*, c.name as reporter_name, c.email as reporter_email
        FROM review_reports rr
        LEFT JOIN customers c ON rr.reported_by = c.id
        WHERE rr.review_id = %s
        ORDER BY rr.reported_at DESC
        """
        reports = Database.execute_query(reports_query, (review_id,), fetch=True)
        review['reports'] = reports
        
        # Get admin responses
        admin_responses_query = """
        SELECT ara.*, a.name as admin_name
        FROM admin_review_actions ara
        LEFT JOIN admins a ON ara.admin_id = a.id
        WHERE ara.review_id = %s
        ORDER BY ara.created_at DESC
        """
        admin_responses = Database.execute_query(admin_responses_query, (review_id,), fetch=True)
        review['admin_responses'] = admin_responses
        
        # Get customer's other reviews for this product
        other_reviews_query = """
        SELECT id, rating, title, created_at, is_approved
        FROM product_reviews
        WHERE customer_id = %s AND product_id = %s AND id != %s
        ORDER BY created_at DESC
        LIMIT 5
        """
        other_reviews = Database.execute_query(other_reviews_query, (
            review['customer_id'], review['product_id'], review_id
        ), fetch=True)
        review['customer_other_reviews'] = other_reviews
        
        # Add quality metrics
        review['quality_score'] = calculate_review_quality_score(review)
        review['sentiment_score'] = analyze_review_sentiment(review['review_text'])
        review['time_ago'] = get_time_ago(review['created_at'])
        
        return success_response(review)
        
    except Exception as e:
        return error_response(str(e), 500)

@product_reviews_bp.route('/product-reviews/<int:review_id>/approve', methods=['PUT'])
@admin_required
def approve_review(review_id):
    try:
        from flask_jwt_extended import get_jwt_identity
        
        # Check if review exists
        review = Database.execute_query(
            "SELECT * FROM product_reviews WHERE id = %s", (review_id,), fetch=True
        )
        if not review:
            return error_response('Review not found', 404)
        
        current_admin = get_jwt_identity()
        
        # Approve review
        Database.execute_query(
            "UPDATE product_reviews SET is_approved = 1, is_flagged = 0, approved_at = %s WHERE id = %s",
            (datetime.now(), review_id)
        )
        
        # Log admin action
        log_admin_review_action(review_id, current_admin['id'], 'approved', 'Review approved by admin')
        
        # Update product rating average
        update_product_rating_average(review[0]['product_id'])
        
        return success_response(message='Review approved successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@product_reviews_bp.route('/product-reviews/<int:review_id>/reject', methods=['PUT'])
@admin_required
def reject_review(review_id):
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        reason = data.get('reason', 'Review rejected by admin')
        
        # Check if review exists
        review = Database.execute_query(
            "SELECT * FROM product_reviews WHERE id = %s", (review_id,), fetch=True
        )
        if not review:
            return error_response('Review not found', 404)
        
        current_admin = get_jwt_identity()
        
        # Reject review
        Database.execute_query(
            "UPDATE product_reviews SET is_approved = 0, is_flagged = 0, admin_response = %s WHERE id = %s",
            (reason, review_id)
        )
        
        # Log admin action
        log_admin_review_action(review_id, current_admin['id'], 'rejected', reason)
        
        # Update product rating average
        update_product_rating_average(review[0]['product_id'])
        
        return success_response(message='Review rejected successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@product_reviews_bp.route('/product-reviews/<int:review_id>/flag', methods=['PUT'])
@admin_required
def flag_review(review_id):
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        reason = data.get('reason', 'Review flagged for review')
        
        # Check if review exists
        review = Database.execute_query(
            "SELECT * FROM product_reviews WHERE id = %s", (review_id,), fetch=True
        )
        if not review:
            return error_response('Review not found', 404)
        
        current_admin = get_jwt_identity()
        
        # Flag review
        Database.execute_query(
            "UPDATE product_reviews SET is_flagged = 1, is_approved = 0, admin_response = %s WHERE id = %s",
            (reason, review_id)
        )
        
        # Log admin action
        log_admin_review_action(review_id, current_admin['id'], 'flagged', reason)
        
        # Update product rating average
        update_product_rating_average(review[0]['product_id'])
        
        return success_response(message='Review flagged successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@product_reviews_bp.route('/product-reviews/<int:review_id>', methods=['DELETE'])
@admin_required
def delete_review(review_id):
    try:
        from flask_jwt_extended import get_jwt_identity
        
        # Check if review exists
        review = Database.execute_query(
            "SELECT * FROM product_reviews WHERE id = %s", (review_id,), fetch=True
        )
        if not review:
            return error_response('Review not found', 404)
        
        current_admin = get_jwt_identity()
        product_id = review[0]['product_id']
        
        # Delete related data first
        Database.execute_query("DELETE FROM review_helpfulness WHERE review_id = %s", (review_id,))
        Database.execute_query("DELETE FROM review_reports WHERE review_id = %s", (review_id,))
        Database.execute_query("DELETE FROM admin_review_actions WHERE review_id = %s", (review_id,))
        
        # Delete the review
        Database.execute_query("DELETE FROM product_reviews WHERE id = %s", (review_id,))
        
        # Update product rating average
        update_product_rating_average(product_id)
        
        return success_response(message='Review deleted successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BULK OPERATIONS =======================

@product_reviews_bp.route('/product-reviews/bulk-action', methods=['PUT'])
@admin_required
def bulk_review_action():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        review_ids = data.get('review_ids', [])
        action = data.get('action')  # approve, reject, flag, delete
        reason = data.get('reason', '')
        
        if not review_ids:
            return error_response('Review IDs are required', 400)
        
        if action not in ['approve', 'reject', 'flag', 'delete']:
            return error_response('Invalid action', 400)
        
        current_admin = get_jwt_identity()
        id_placeholders = ','.join(['%s'] * len(review_ids))
        
        # Get affected product IDs for rating updates
        products_query = f"SELECT DISTINCT product_id FROM product_reviews WHERE id IN ({id_placeholders})"
        affected_products = Database.execute_query(products_query, review_ids, fetch=True)
        
        if action == 'approve':
            query = f"UPDATE product_reviews SET is_approved = 1, is_flagged = 0, approved_at = %s WHERE id IN ({id_placeholders})"
            params = [datetime.now()] + review_ids
            action_note = 'Bulk approved by admin'
        elif action == 'reject':
            query = f"UPDATE product_reviews SET is_approved = 0, is_flagged = 0, admin_response = %s WHERE id IN ({id_placeholders})"
            params = [reason or 'Bulk rejected by admin'] + review_ids
            action_note = reason or 'Bulk rejected by admin'
        elif action == 'flag':
            query = f"UPDATE product_reviews SET is_flagged = 1, is_approved = 0, admin_response = %s WHERE id IN ({id_placeholders})"
            params = [reason or 'Bulk flagged for review'] + review_ids
            action_note = reason or 'Bulk flagged for review'
        elif action == 'delete':
            # Delete related data first
            Database.execute_query(f"DELETE FROM review_helpfulness WHERE review_id IN ({id_placeholders})", review_ids)
            Database.execute_query(f"DELETE FROM review_reports WHERE review_id IN ({id_placeholders})", review_ids)
            Database.execute_query(f"DELETE FROM admin_review_actions WHERE review_id IN ({id_placeholders})", review_ids)
            query = f"DELETE FROM product_reviews WHERE id IN ({id_placeholders})"
            params = review_ids
            action_note = 'Bulk deleted by admin'
        
        Database.execute_query(query, params)
        
        # Log admin actions
        if action != 'delete':
            for review_id in review_ids:
                log_admin_review_action(review_id, current_admin['id'], action, action_note)
        
        # Update product rating averages
        for product in affected_products:
            update_product_rating_average(product['product_id'])
        
        return success_response(message=f'{len(review_ids)} reviews {action}d successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= REVIEW ANALYTICS =======================

@product_reviews_bp.route('/product-reviews/analytics/dashboard', methods=['GET'])
@admin_required
def review_analytics_dashboard():
    try:
        days = int(request.args.get('days', 30))
        
        # Overall review statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_reviews,
            SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END) as approved_reviews,
            SUM(CASE WHEN is_approved = 0 AND admin_response IS NULL THEN 1 ELSE 0 END) as pending_reviews,
            SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END) as flagged_reviews,
            SUM(CASE WHEN is_verified_purchase = 1 THEN 1 ELSE 0 END) as verified_reviews,
            SUM(CASE WHEN review_images IS NOT NULL OR review_videos IS NOT NULL THEN 1 ELSE 0 END) as reviews_with_media,
            AVG(rating) as average_rating,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) THEN 1 ELSE 0 END) as recent_reviews
        FROM product_reviews
        """
        stats = Database.execute_query(stats_query, (days,), fetch=True)[0]
        
        # Convert average rating to float
        if stats['average_rating']:
            stats['average_rating'] = round(float(stats['average_rating']), 2)
        
        # Rating distribution
        rating_distribution_query = """
        SELECT rating, COUNT(*) as count
        FROM product_reviews
        WHERE is_approved = 1
        GROUP BY rating
        ORDER BY rating DESC
        """
        rating_distribution = Database.execute_query(rating_distribution_query, fetch=True)
        
        # Review trends (last 30 days)
        trends_query = """
        SELECT DATE(created_at) as date, 
               COUNT(*) as total_reviews,
               SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END) as approved_reviews,
               AVG(rating) as avg_rating
        FROM product_reviews
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY DATE(created_at)
        ORDER BY date
        """
        trends = Database.execute_query(trends_query, (days,), fetch=True)
        
        # Convert avg_rating to float
        for trend in trends:
            if trend['avg_rating']:
                trend['avg_rating'] = round(float(trend['avg_rating']), 2)
        
        # Top reviewed products
        top_products_query = """
        SELECT p.id, p.name, p.sku,
               COUNT(pr.id) as review_count,
               AVG(pr.rating) as avg_rating,
               SUM(CASE WHEN pr.is_approved = 1 THEN 1 ELSE 0 END) as approved_count
        FROM products p
        LEFT JOIN product_reviews pr ON p.id = pr.product_id AND pr.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        WHERE pr.id IS NOT NULL
        GROUP BY p.id, p.name, p.sku
        ORDER BY review_count DESC
        LIMIT 10
        """
        top_products = Database.execute_query(top_products_query, (days,), fetch=True)
        
        # Convert avg_rating to float
        for product in top_products:
            if product['avg_rating']:
                product['avg_rating'] = round(float(product['avg_rating']), 2)
        
        # Most active reviewers
        active_reviewers_query = """
        SELECT c.id, c.name, c.email,
               COUNT(pr.id) as review_count,
               AVG(pr.rating) as avg_rating,
               SUM(CASE WHEN pr.is_verified_purchase = 1 THEN 1 ELSE 0 END) as verified_count
        FROM customers c
        LEFT JOIN product_reviews pr ON c.id = pr.customer_id AND pr.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        WHERE pr.id IS NOT NULL
        GROUP BY c.id, c.name, c.email
        ORDER BY review_count DESC
        LIMIT 10
        """
        active_reviewers = Database.execute_query(active_reviewers_query, (days,), fetch=True)
        
        # Convert avg_rating to float
        for reviewer in active_reviewers:
            if reviewer['avg_rating']:
                reviewer['avg_rating'] = round(float(reviewer['avg_rating']), 2)
        
        return success_response({
            'days': days,
            'statistics': stats,
            'rating_distribution': rating_distribution,
            'trends': trends,
            'top_products': top_products,
            'active_reviewers': active_reviewers
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= REVIEW MODERATION QUEUE =======================

@product_reviews_bp.route('/product-reviews/moderation-queue', methods=['GET'])
@admin_required
def get_moderation_queue():
    try:
        limit = int(request.args.get('limit', 50))
        priority = request.args.get('priority', 'all')  # high, medium, low, all
        
        # Base query for pending reviews
        where_conditions = ["pr.is_approved = 0", "pr.admin_response IS NULL"]
        params = []
        
        # Add priority filtering
        if priority == 'high':
            where_conditions.append("(pr.is_flagged = 1 OR (SELECT COUNT(*) FROM review_reports WHERE review_id = pr.id) > 0)")
        elif priority == 'medium':
            where_conditions.append("(pr.rating <= 2 OR pr.review_images IS NOT NULL OR pr.review_videos IS NOT NULL)")
        elif priority == 'low':
            where_conditions.append("pr.rating >= 4 AND pr.is_flagged = 0 AND (SELECT COUNT(*) FROM review_reports WHERE review_id = pr.id) = 0")
        
        where_clause = " AND ".join(where_conditions)
        
        queue_query = f"""
        SELECT pr.*, 
               c.name as customer_name, c.email as customer_email,
               p.name as product_name, p.sku as product_sku,
               (SELECT COUNT(*) FROM review_reports rr WHERE rr.review_id = pr.id) as report_count,
               CASE 
                   WHEN pr.is_flagged = 1 OR (SELECT COUNT(*) FROM review_reports WHERE review_id = pr.id) > 0 THEN 'high'
                   WHEN pr.rating <= 2 OR pr.review_images IS NOT NULL OR pr.review_videos IS NOT NULL THEN 'medium'
                   ELSE 'low'
               END as priority_level
        FROM product_reviews pr
        LEFT JOIN customers c ON pr.customer_id = c.id
        LEFT JOIN products p ON pr.product_id = p.id
        WHERE {where_clause}
        ORDER BY 
            CASE 
                WHEN pr.is_flagged = 1 THEN 1
                WHEN (SELECT COUNT(*) FROM review_reports WHERE review_id = pr.id) > 0 THEN 2
                WHEN pr.rating <= 2 THEN 3
                ELSE 4
            END,
            pr.created_at ASC
        LIMIT %s
        """
        params.append(limit)
        
        pending_reviews = Database.execute_query(queue_query, params, fetch=True)
        
        # Add computed fields
        for review in pending_reviews:
            # Parse media files
            if review.get('review_images'):
                try:
                    review['review_images'] = json.loads(review['review_images'])
                except:
                    review['review_images'] = []
            
            if review.get('review_videos'):
                try:
                    review['review_videos'] = json.loads(review['review_videos'])
                except:
                    review['review_videos'] = []
            
            # Add review summary
            if review['review_text'] and len(review['review_text']) > 100:
                review['review_summary'] = review['review_text'][:100] + '...'
            else:
                review['review_summary'] = review['review_text']
            
            # Add quality indicators
            review['quality_score'] = calculate_review_quality_score(review)
            review['potential_fake'] = detect_potential_fake_review(review)
            review['time_ago'] = get_time_ago(review['created_at'])
        
        return success_response({
            'pending_reviews': pending_reviews,
            'count': len(pending_reviews),
            'priority_filter': priority
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= FAKE REVIEW DETECTION =======================

@product_reviews_bp.route('/product-reviews/fake-detection', methods=['GET'])
@admin_required
def get_potential_fake_reviews():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        confidence = request.args.get('confidence', 'medium')  # low, medium, high
        
        offset = (page - 1) * per_page
        
        # Build detection criteria based on confidence level
        suspicious_criteria = []
        
        if confidence in ['low', 'medium', 'high']:
            # Common fake review indicators
            suspicious_criteria.extend([
                "LENGTH(pr.review_text) < 50",  # Very short reviews
                "pr.rating IN (1, 5)",  # Extreme ratings
                "pr.created_at = (SELECT MIN(created_at) FROM product_reviews WHERE customer_id = pr.customer_id)"  # First-time reviewers
            ])
        
        if confidence in ['medium', 'high']:
            suspicious_criteria.extend([
                "pr.review_text REGEXP '[A-Z]{3,}'",  # Excessive caps
                "pr.review_text LIKE '%best%product%' OR pr.review_text LIKE '%amazing%quality%'",  # Generic phrases
                "(SELECT COUNT(*) FROM product_reviews WHERE customer_id = pr.customer_id AND DATE(created_at) = DATE(pr.created_at)) > 1"  # Multiple reviews same day
            ])
        
        if confidence == 'high':
            suspicious_criteria.extend([
                "pr.is_verified_purchase = 0",  # Unverified purchases
                "pr.review_text REGEXP '(excellent|perfect|wonderful|amazing|outstanding){2,}'",  # Repeated superlatives
                "(SELECT COUNT(*) FROM product_reviews WHERE customer_id = pr.customer_id) = 1 AND pr.rating = 5"  # Single 5-star review
            ])
        
        where_clause = f"({' OR '.join(suspicious_criteria)})"
        
        # Get total count
        count_query = f"""
        SELECT COUNT(*) as total FROM product_reviews pr 
        WHERE {where_clause}
        """
        total = Database.execute_query(count_query, fetch=True)[0]['total']
        
        # Get suspicious reviews
        suspicious_query = f"""
        SELECT pr.*, 
               c.name as customer_name, c.email as customer_email,
               p.name as product_name, p.sku as product_sku,
               (SELECT COUNT(*) FROM product_reviews WHERE customer_id = pr.customer_id) as customer_review_count,
               (SELECT COUNT(*) FROM orders WHERE customer_id = pr.customer_id AND payment_status = 'paid') as customer_order_count
        FROM product_reviews pr
        LEFT JOIN customers c ON pr.customer_id = c.id
        LEFT JOIN products p ON pr.product_id = p.id
        WHERE {where_clause}
        ORDER BY pr.created_at DESC
        LIMIT %s OFFSET %s
        """
        suspicious_reviews = Database.execute_query(suspicious_query, [per_page, offset], fetch=True)
        
        # Add fake detection scores
        for review in suspicious_reviews:
            review['fake_probability'] = calculate_fake_probability(review)
            review['suspicious_indicators'] = get_suspicious_indicators(review)
            review['time_ago'] = get_time_ago(review['created_at'])
        
        return jsonify(ResponseFormatter.paginated(suspicious_reviews, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= REVIEW EXPORT =======================

@product_reviews_bp.route('/product-reviews/export', methods=['POST'])
@admin_required
def export_reviews():
    try:
        data = get_request_data()
        export_format = data.get('format', 'csv')  # csv, excel, json
        filters = data.get('filters', {})
        
        # Build query based on filters
        where_conditions = []
        params = []
        
        if filters.get('product_id'):
            where_conditions.append("pr.product_id = %s")
            params.append(filters['product_id'])
        
        if filters.get('status'):
            if filters['status'] == 'approved':
                where_conditions.append("pr.is_approved = 1")
            elif filters['status'] == 'pending':
                where_conditions.append("pr.is_approved = 0 AND pr.admin_response IS NULL")
            elif filters['status'] == 'rejected':
                where_conditions.append("pr.is_approved = 0 AND pr.admin_response IS NOT NULL")
        
        if filters.get('start_date'):
            where_conditions.append("DATE(pr.created_at) >= %s")
            params.append(filters['start_date'])
        
        if filters.get('end_date'):
            where_conditions.append("DATE(pr.created_at) <= %s")
            params.append(filters['end_date'])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Export query
        export_query = f"""
        SELECT pr.id, pr.rating, pr.title, pr.review_text, pr.is_approved, pr.is_verified_purchase,
               pr.helpfulness_score, pr.created_at, pr.approved_at,
               c.name as customer_name, c.email as customer_email,
               p.name as product_name, p.sku as product_sku,
               o.order_number
        FROM product_reviews pr
        LEFT JOIN customers c ON pr.customer_id = c.id
        LEFT JOIN products p ON pr.product_id = p.id
        LEFT JOIN orders o ON pr.order_id = o.id
        WHERE {where_clause}
        ORDER BY pr.created_at DESC
        """
        
        reviews = Database.execute_query(export_query, params, fetch=True)
        
        # Generate export file (simplified for this example)
        export_data = {
            'format': export_format,
            'total_records': len(reviews),
            'exported_at': datetime.now().isoformat(),
            'data': reviews
        }
        
        return success_response(export_data, 'Reviews exported successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= REVIEW STATISTICS =======================

@product_reviews_bp.route('/product-reviews/stats', methods=['GET'])
@admin_required
def get_review_stats():
    try:
        # Overall statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_reviews,
            SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END) as approved_reviews,
            SUM(CASE WHEN is_approved = 0 AND admin_response IS NULL THEN 1 ELSE 0 END) as pending_reviews,
            SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END) as flagged_reviews,
            SUM(CASE WHEN is_verified_purchase = 1 THEN 1 ELSE 0 END) as verified_reviews,
            AVG(rating) as average_rating,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR) THEN 1 ELSE 0 END) as reviews_today,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as reviews_week
        FROM product_reviews
        """
        stats = Database.execute_query(stats_query, fetch=True)[0]
        
        # Convert average rating to float
        if stats['average_rating']:
            stats['average_rating'] = round(float(stats['average_rating']), 2)
        
        # Response time statistics
        response_time_query = """
        SELECT 
            AVG(TIMESTAMPDIFF(HOUR, created_at, approved_at)) as avg_approval_time_hours,
            MIN(TIMESTAMPDIFF(HOUR, created_at, approved_at)) as min_approval_time_hours,
            MAX(TIMESTAMPDIFF(HOUR, created_at, approved_at)) as max_approval_time_hours
        FROM product_reviews
        WHERE approved_at IS NOT NULL
        """
        response_times = Database.execute_query(response_time_query, fetch=True)[0]
        
        # Convert to float
        for key in response_times:
            if response_times[key]:
                response_times[key] = round(float(response_times[key]), 2)
        
        stats.update(response_times)
        
        return success_response(stats)
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= UTILITY FUNCTIONS =======================

def log_admin_review_action(review_id, admin_id, action, note):
    """Log admin actions on reviews"""
    try:
        action_query = """
        INSERT INTO admin_review_actions (review_id, admin_id, action, note, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        Database.execute_query(action_query, (review_id, admin_id, action, note, datetime.now()))
    except:
        pass  # Don't fail main operation if logging fails

def update_product_rating_average(product_id):
    """Update product's average rating"""
    try:
        # Calculate new average from approved reviews
        avg_query = """
        SELECT AVG(rating) as avg_rating, COUNT(*) as review_count
        FROM product_reviews
        WHERE product_id = %s AND is_approved = 1
        """
        result = Database.execute_query(avg_query, (product_id,), fetch=True)[0]
        
        avg_rating = float(result['avg_rating']) if result['avg_rating'] else 0
        review_count = result['review_count']
        
        # Update product table
        update_query = """
        UPDATE products 
        SET average_rating = %s, review_count = %s
        WHERE id = %s
        """
        Database.execute_query(update_query, (avg_rating, review_count, product_id))
        
    except Exception as e:
        pass  # Don't fail if rating update fails

def calculate_review_quality_score(review):
    """Calculate review quality score"""
    try:
        score = 0
        
        # Length scoring
        text_length = len(review.get('review_text', ''))
        if text_length >= 100:
            score += 30
        elif text_length >= 50:
            score += 20
        elif text_length >= 20:
            score += 10
        
        # Title scoring
        if review.get('title') and len(review['title']) > 5:
            score += 15
        
        # Verified purchase
        if review.get('is_verified_purchase'):
            score += 25
        
        # Media attachments
        has_images = review.get('review_images') and len(review.get('review_images', [])) > 0
        has_videos = review.get('review_videos') and len(review.get('review_videos', [])) > 0
        if has_images or has_videos:
            score += 20
        
        # Helpfulness votes
        helpful_votes = review.get('helpful_votes', 0)
        if helpful_votes > 5:
            score += 10
        elif helpful_votes > 0:
            score += 5
        
        return min(score, 100)  # Cap at 100
        
    except:
        return 0

def detect_potential_fake_review(review):
    """Detect potential fake review indicators"""
    try:
        indicators = []
        
        text = review.get('review_text', '').lower()
        
        # Very short reviews
        if len(text) < 30:
            indicators.append('Very short review')
        
        # Excessive caps
        if len(re.findall(r'[A-Z]{3,}', review.get('review_text', ''))):
            indicators.append('Excessive capitalization')
        
        # Generic phrases
        generic_phrases = ['best product', 'amazing quality', 'highly recommend', 'five stars']
        if any(phrase in text for phrase in generic_phrases):
            indicators.append('Generic phrases detected')
        
        # Extreme rating with short text
        if review.get('rating') in [1, 5] and len(text) < 50:
            indicators.append('Extreme rating with minimal text')
        
        # Unverified purchase
        if not review.get('is_verified_purchase'):
            indicators.append('Unverified purchase')
        
        return len(indicators) > 2  # Flag if multiple indicators
        
    except:
        return False

def calculate_fake_probability(review):
    """Calculate probability that review is fake"""
    try:
        probability = 0
        
        # Customer behavior factors
        if review.get('customer_review_count', 0) == 1:
            probability += 0.3  # First-time reviewer
        
        if review.get('customer_order_count', 0) == 0:
            probability += 0.4  # No purchase history
        
        # Review content factors
        text_length = len(review.get('review_text', ''))
        if text_length < 30:
            probability += 0.2
        
        if not review.get('is_verified_purchase'):
            probability += 0.3
        
        # Rating factors
        if review.get('rating') in [1, 5]:
            probability += 0.1
        
        return min(probability, 1.0)  # Cap at 100%
        
    except:
        return 0

def get_suspicious_indicators(review):
    """Get list of suspicious indicators for a review"""
    indicators = []
    
    if review.get('customer_review_count', 0) == 1:
        indicators.append('First-time reviewer')
    
    if not review.get('is_verified_purchase'):
        indicators.append('Unverified purchase')
    
    if len(review.get('review_text', '')) < 30:
        indicators.append('Very short review')
    
    if review.get('rating') in [1, 5]:
        indicators.append('Extreme rating')
    
    return indicators

def analyze_review_sentiment(text):
    """Basic sentiment analysis of review text"""
    try:
        if not text:
            return 0
        
        positive_words = ['good', 'great', 'excellent', 'amazing', 'perfect', 'love', 'awesome', 'fantastic']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'horrible', 'worst', 'poor', 'disappointing']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count + negative_count == 0:
            return 0  # Neutral
        
        sentiment_score = (positive_count - negative_count) / (positive_count + negative_count)
        return round(sentiment_score, 2)
        
    except:
        return 0

def get_time_ago(timestamp):
    """Calculate human-readable time ago"""
    try:
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

# ======================= REVIEW REPORTS MANAGEMENT =======================

@product_reviews_bp.route('/product-reviews/reports', methods=['GET'])
@admin_required
def get_review_reports():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')  # pending, resolved, dismissed
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if status == 'pending':
            where_conditions.append("rr.status = 'pending'")
        elif status == 'resolved':
            where_conditions.append("rr.status = 'resolved'")
        elif status == 'dismissed':
            where_conditions.append("rr.status = 'dismissed'")
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"""
        SELECT COUNT(*) as total FROM review_reports rr WHERE {where_clause}
        """
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get reports
        reports_query = f"""
        SELECT rr.*, 
               c.name as reporter_name, c.email as reporter_email,
               pr.rating, pr.title as review_title, pr.review_text,
               p.name as product_name,
               rc.name as reviewed_customer_name
        FROM review_reports rr
        LEFT JOIN customers c ON rr.reported_by = c.id
        LEFT JOIN product_reviews pr ON rr.review_id = pr.id
        LEFT JOIN products p ON pr.product_id = p.id
        LEFT JOIN customers rc ON pr.customer_id = rc.id
        WHERE {where_clause}
        ORDER BY rr.reported_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        reports = Database.execute_query(reports_query, params, fetch=True)
        
        # Add computed fields
        for report in reports:
            report['time_ago'] = get_time_ago(report['reported_at'])
            if report['review_text'] and len(report['review_text']) > 100:
                report['review_summary'] = report['review_text'][:100] + '...'
            else:
                report['review_summary'] = report['review_text']
        
        return jsonify(ResponseFormatter.paginated(reports, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@product_reviews_bp.route('/product-reviews/reports/<int:report_id>/resolve', methods=['PUT'])
@admin_required
def resolve_review_report(report_id):
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        action = data.get('action')  # dismiss, remove_review, warn_customer
        note = data.get('note', '')
        
        if action not in ['dismiss', 'remove_review', 'warn_customer']:
            return error_response('Invalid action', 400)
        
        current_admin = get_jwt_identity()
        
        # Update report status
        Database.execute_query(
            "UPDATE review_reports SET status = 'resolved', admin_action = %s, admin_note = %s, resolved_by = %s, resolved_at = %s WHERE id = %s",
            (action, note, current_admin['id'], datetime.now(), report_id)
        )
        
        # Take action based on admin decision
        if action == 'remove_review':
            # Get review ID from report
            report = Database.execute_query(
                "SELECT review_id FROM review_reports WHERE id = %s", (report_id,), fetch=True
            )[0]
            
            # Flag the review
            Database.execute_query(
                "UPDATE product_reviews SET is_flagged = 1, is_approved = 0, admin_response = %s WHERE id = %s",
                (f"Review removed due to report: {note}", report['review_id'])
            )
        
        return success_response(message='Report resolved successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= ADMIN RESPONSE TO REVIEWS =======================

@product_reviews_bp.route('/product-reviews/<int:review_id>/respond', methods=['POST'])
@admin_required
def respond_to_review():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        response_text = data.get('response', '').strip()
        
        if not response_text:
            return error_response('Response text is required', 400)
        
        current_admin = get_jwt_identity()
        
        # Add admin response
        response_query = """
        INSERT INTO admin_review_responses (review_id, admin_id, response_text, created_at)
        VALUES (%s, %s, %s, %s)
        """
        
        response_id = Database.execute_query(response_query, (
            review_id, current_admin['id'], response_text, datetime.now()
        ))
        
        # Log admin action
        log_admin_review_action(review_id, current_admin['id'], 'responded', 'Admin response added')
        
        return success_response({
            'response_id': response_id,
            'admin_name': current_admin['name']
        }, 'Response added successfully')
        
    except Exception as e:
        return error_response(str(e), 500)