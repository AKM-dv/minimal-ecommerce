from flask import Blueprint, request
import json
from datetime import datetime

# Import our modules
from models import Database
from utils import (admin_required, success_response, error_response, get_request_data, 
                   ResponseFormatter, validate_email)

# Create blueprint for blog comments management
blog_comments_bp = Blueprint('blog_comments', __name__)

# ======================= BLOG COMMENTS MANAGEMENT =======================

@blog_comments_bp.route('/blog/comments', methods=['GET'])
@admin_required
def get_blog_comments():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        post_id = request.args.get('post_id')
        status = request.args.get('status')  # approved, pending, spam
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if post_id:
            where_conditions.append("bc.post_id = %s")
            params.append(post_id)
        
        if status == 'approved':
            where_conditions.append("bc.is_approved = 1 AND bc.is_spam = 0")
        elif status == 'pending':
            where_conditions.append("bc.is_approved = 0 AND bc.is_spam = 0")
        elif status == 'spam':
            where_conditions.append("bc.is_spam = 1")
        
        if search:
            where_conditions.append("(bc.author_name LIKE %s OR bc.author_email LIKE %s OR bc.content LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Validate sort columns
        valid_sort_columns = ['author_name', 'created_at', 'post_title']
        if sort_by not in valid_sort_columns:
            sort_by = 'created_at'
        
        sort_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'
        
        # Get total count
        count_query = f"""
        SELECT COUNT(*) as total FROM blog_comments bc 
        LEFT JOIN blog_posts bp ON bc.post_id = bp.id
        WHERE {where_clause}
        """
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get comments with post info
        comments_query = f"""
        SELECT bc.*, bp.title as post_title, bp.slug as post_slug,
               (SELECT COUNT(*) FROM blog_comments replies WHERE replies.parent_id = bc.id) as reply_count
        FROM blog_comments bc
        LEFT JOIN blog_posts bp ON bc.post_id = bp.id
        WHERE {where_clause}
        ORDER BY bc.{sort_by} {sort_direction}
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        comments = Database.execute_query(comments_query, params, fetch=True)
        
        # Add status labels and computed fields
        for comment in comments:
            if comment['is_spam']:
                comment['status'] = 'spam'
                comment['status_label'] = 'Spam'
                comment['status_color'] = 'danger'
            elif comment['is_approved']:
                comment['status'] = 'approved'
                comment['status_label'] = 'Approved'
                comment['status_color'] = 'success'
            else:
                comment['status'] = 'pending'
                comment['status_label'] = 'Pending'
                comment['status_color'] = 'warning'
            
            # Add time ago
            comment['time_ago'] = get_time_ago(comment['created_at'])
            
            # Truncate content for list view
            if comment['content'] and len(comment['content']) > 150:
                comment['content_preview'] = comment['content'][:150] + '...'
            else:
                comment['content_preview'] = comment['content']
        
        return jsonify(ResponseFormatter.paginated(comments, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_comments_bp.route('/blog/comments/<int:comment_id>', methods=['GET'])
@admin_required
def get_blog_comment(comment_id):
    try:
        # Get comment with post info and replies
        comment_query = """
        SELECT bc.*, bp.title as post_title, bp.slug as post_slug, bp.id as post_id
        FROM blog_comments bc
        LEFT JOIN blog_posts bp ON bc.post_id = bp.id
        WHERE bc.id = %s
        """
        
        comment_result = Database.execute_query(comment_query, (comment_id,), fetch=True)
        
        if not comment_result:
            return error_response('Comment not found', 404)
        
        comment = comment_result[0]
        
        # Get replies (threaded comments)
        replies_query = """
        SELECT * FROM blog_comments
        WHERE parent_id = %s
        ORDER BY created_at ASC
        """
        replies = Database.execute_query(replies_query, (comment_id,), fetch=True)
        
        # Add status info to main comment and replies
        for item in [comment] + replies:
            if item['is_spam']:
                item['status'] = 'spam'
                item['status_label'] = 'Spam'
                item['status_color'] = 'danger'
            elif item['is_approved']:
                item['status'] = 'approved'
                item['status_label'] = 'Approved'
                item['status_color'] = 'success'
            else:
                item['status'] = 'pending'
                item['status_label'] = 'Pending'
                item['status_color'] = 'warning'
            
            item['time_ago'] = get_time_ago(item['created_at'])
        
        comment['replies'] = replies
        comment['reply_count'] = len(replies)
        
        return success_response(comment)
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_comments_bp.route('/blog/comments', methods=['POST'])
@admin_required
def create_comment_reply():
    """Admin can create replies to comments"""
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['post_id', 'content', 'author_name', 'author_email']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Validate email
        if not validate_email(data['author_email']):
            return error_response('Invalid email format', 400)
        
        # Check if post exists
        post = Database.execute_query(
            "SELECT id FROM blog_posts WHERE id = %s", (data['post_id'],), fetch=True
        )
        if not post:
            return error_response('Blog post not found', 404)
        
        # Check if parent comment exists (for replies)
        parent_id = data.get('parent_id')
        if parent_id:
            parent_comment = Database.execute_query(
                "SELECT id FROM blog_comments WHERE id = %s", (parent_id,), fetch=True
            )
            if not parent_comment:
                return error_response('Parent comment not found', 404)
        
        # Get admin info
        current_admin = get_jwt_identity()
        
        # Create comment
        comment_query = """
        INSERT INTO blog_comments (post_id, parent_id, author_name, author_email, 
                                 author_website, content, is_approved, ip_address, 
                                 user_agent, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        comment_id = Database.execute_query(comment_query, (
            data['post_id'], parent_id, data['author_name'], data['author_email'],
            data.get('author_website', ''), data['content'], True,  # Auto-approve admin comments
            request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
            request.headers.get('User-Agent', ''), datetime.now()
        ))
        
        return success_response({
            'id': comment_id,
            'status': 'approved',
            'created_by_admin': True
        }, 'Comment created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_comments_bp.route('/blog/comments/<int:comment_id>/approve', methods=['PUT'])
@admin_required
def approve_comment(comment_id):
    try:
        # Check if comment exists
        comment = Database.execute_query(
            "SELECT * FROM blog_comments WHERE id = %s", (comment_id,), fetch=True
        )
        if not comment:
            return error_response('Comment not found', 404)
        
        # Approve comment
        Database.execute_query(
            "UPDATE blog_comments SET is_approved = 1, is_spam = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), comment_id)
        )
        
        return success_response(message='Comment approved successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_comments_bp.route('/blog/comments/<int:comment_id>/reject', methods=['PUT'])
@admin_required
def reject_comment(comment_id):
    try:
        # Check if comment exists
        comment = Database.execute_query(
            "SELECT * FROM blog_comments WHERE id = %s", (comment_id,), fetch=True
        )
        if not comment:
            return error_response('Comment not found', 404)
        
        # Reject comment (mark as not approved)
        Database.execute_query(
            "UPDATE blog_comments SET is_approved = 0, is_spam = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), comment_id)
        )
        
        return success_response(message='Comment rejected successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_comments_bp.route('/blog/comments/<int:comment_id>/spam', methods=['PUT'])
@admin_required
def mark_comment_spam(comment_id):
    try:
        # Check if comment exists
        comment = Database.execute_query(
            "SELECT * FROM blog_comments WHERE id = %s", (comment_id,), fetch=True
        )
        if not comment:
            return error_response('Comment not found', 404)
        
        # Mark as spam
        Database.execute_query(
            "UPDATE blog_comments SET is_spam = 1, is_approved = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), comment_id)
        )
        
        return success_response(message='Comment marked as spam')
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_comments_bp.route('/blog/comments/<int:comment_id>', methods=['PUT'])
@admin_required
def update_comment(comment_id):
    try:
        data = get_request_data()
        
        # Check if comment exists
        comment = Database.execute_query(
            "SELECT * FROM blog_comments WHERE id = %s", (comment_id,), fetch=True
        )
        if not comment:
            return error_response('Comment not found', 404)
        
        # Build update query
        update_fields = []
        params = []
        
        # Allow updating content, author info, and status
        updatable_fields = ['content', 'author_name', 'author_email', 'author_website']
        for field in updatable_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                params.append(data[field])
        
        # Handle status updates
        if 'is_approved' in data:
            update_fields.append("is_approved = %s")
            params.append(bool(data['is_approved']))
        
        if 'is_spam' in data:
            update_fields.append("is_spam = %s")
            params.append(bool(data['is_spam']))
        
        if not update_fields:
            return error_response('No fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(comment_id)
        
        query = f"UPDATE blog_comments SET {', '.join(update_fields)} WHERE id = %s"
        Database.execute_query(query, params)
        
        return success_response(message='Comment updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_comments_bp.route('/blog/comments/<int:comment_id>', methods=['DELETE'])
@admin_required
def delete_comment(comment_id):
    try:
        # Check if comment exists
        comment = Database.execute_query(
            "SELECT * FROM blog_comments WHERE id = %s", (comment_id,), fetch=True
        )
        if not comment:
            return error_response('Comment not found', 404)
        
        # Delete replies first (cascade delete)
        Database.execute_query("DELETE FROM blog_comments WHERE parent_id = %s", (comment_id,))
        
        # Delete the comment
        Database.execute_query("DELETE FROM blog_comments WHERE id = %s", (comment_id,))
        
        return success_response(message='Comment and its replies deleted successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_comments_bp.route('/blog/comments/bulk-action', methods=['PUT'])
@admin_required
def bulk_comment_action():
    try:
        data = get_request_data()
        comment_ids = data.get('comment_ids', [])
        action = data.get('action')  # approve, reject, spam, delete
        
        if not comment_ids:
            return error_response('Comment IDs are required', 400)
        
        if action not in ['approve', 'reject', 'spam', 'delete']:
            return error_response('Invalid action', 400)
        
        id_placeholders = ','.join(['%s'] * len(comment_ids))
        
        if action == 'approve':
            query = f"UPDATE blog_comments SET is_approved = 1, is_spam = 0, updated_at = %s WHERE id IN ({id_placeholders})"
            params = [datetime.now()] + comment_ids
        elif action == 'reject':
            query = f"UPDATE blog_comments SET is_approved = 0, is_spam = 0, updated_at = %s WHERE id IN ({id_placeholders})"
            params = [datetime.now()] + comment_ids
        elif action == 'spam':
            query = f"UPDATE blog_comments SET is_spam = 1, is_approved = 0, updated_at = %s WHERE id IN ({id_placeholders})"
            params = [datetime.now()] + comment_ids
        elif action == 'delete':
            # Delete replies first
            Database.execute_query(f"DELETE FROM blog_comments WHERE parent_id IN ({id_placeholders})", comment_ids)
            query = f"DELETE FROM blog_comments WHERE id IN ({id_placeholders})"
            params = comment_ids
        
        Database.execute_query(query, params)
        
        return success_response(message=f'{len(comment_ids)} comments {action}d successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= COMMENT STATISTICS =======================

@blog_comments_bp.route('/blog/comments/stats', methods=['GET'])
@admin_required
def get_comment_stats():
    try:
        # Overall comment statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_comments,
            SUM(CASE WHEN is_approved = 1 AND is_spam = 0 THEN 1 ELSE 0 END) as approved_comments,
            SUM(CASE WHEN is_approved = 0 AND is_spam = 0 THEN 1 ELSE 0 END) as pending_comments,
            SUM(CASE WHEN is_spam = 1 THEN 1 ELSE 0 END) as spam_comments,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR) THEN 1 ELSE 0 END) as comments_today,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as comments_week
        FROM blog_comments
        """
        stats = Database.execute_query(stats_query, fetch=True)[0]
        
        # Comment trends (last 30 days)
        trends_query = """
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM blog_comments
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY DATE(created_at)
        ORDER BY date
        """
        trends = Database.execute_query(trends_query, fetch=True)
        
        # Top commented posts
        top_posts_query = """
        SELECT bp.id, bp.title, bp.slug, COUNT(bc.id) as comment_count
        FROM blog_posts bp
        LEFT JOIN blog_comments bc ON bp.id = bc.post_id AND bc.is_approved = 1
        WHERE bp.status = 'published'
        GROUP BY bp.id, bp.title, bp.slug
        HAVING comment_count > 0
        ORDER BY comment_count DESC
        LIMIT 10
        """
        top_posts = Database.execute_query(top_posts_query, fetch=True)
        
        # Most active commenters
        active_commenters_query = """
        SELECT author_name, author_email, COUNT(*) as comment_count
        FROM blog_comments
        WHERE is_approved = 1 AND is_spam = 0
        GROUP BY author_name, author_email
        ORDER BY comment_count DESC
        LIMIT 10
        """
        active_commenters = Database.execute_query(active_commenters_query, fetch=True)
        
        return success_response({
            'statistics': stats,
            'trends': trends,
            'top_posts': top_posts,
            'active_commenters': active_commenters
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= COMMENT MODERATION =======================

@blog_comments_bp.route('/blog/comments/moderation-queue', methods=['GET'])
@admin_required
def get_moderation_queue():
    try:
        limit = int(request.args.get('limit', 50))
        
        # Get pending comments that need moderation
        queue_query = """
        SELECT bc.*, bp.title as post_title, bp.slug as post_slug
        FROM blog_comments bc
        LEFT JOIN blog_posts bp ON bc.post_id = bp.id
        WHERE bc.is_approved = 0 AND bc.is_spam = 0
        ORDER BY bc.created_at ASC
        LIMIT %s
        """
        
        pending_comments = Database.execute_query(queue_query, (limit,), fetch=True)
        
        # Add computed fields
        for comment in pending_comments:
            comment['time_ago'] = get_time_ago(comment['created_at'])
            comment['content_preview'] = comment['content'][:150] + '...' if len(comment['content']) > 150 else comment['content']
            comment['needs_attention'] = check_comment_needs_attention(comment)
        
        return success_response({
            'pending_comments': pending_comments,
            'count': len(pending_comments)
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= UTILITY FUNCTIONS =======================

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

def check_comment_needs_attention(comment):
    """Check if comment needs special attention (potential spam indicators)"""
    try:
        content = comment['content'].lower()
        author_email = comment['author_email'].lower()
        
        # Simple spam indicators
        spam_keywords = ['buy now', 'click here', 'free money', 'viagra', 'casino', 'loan', 'discount']
        suspicious_patterns = [
            len(content) < 10,  # Very short comment
            any(keyword in content for keyword in spam_keywords),
            'http' in content and content.count('http') > 2,  # Multiple links
            author_email.count('@') != 1,  # Invalid email pattern
        ]
        
        return any(suspicious_patterns)
    except:
        return False