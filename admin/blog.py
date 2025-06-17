from flask import Blueprint, request
import json
from datetime import datetime, timedelta
from slugify import slugify
import re

# Import our modules
from models import Database, SiteConfig
from utils import (admin_required, success_response, error_response, get_request_data, 
                   save_image, ResponseFormatter)

# Create blueprint
blog_bp = Blueprint('blog', __name__)

# ======================= BLOG POSTS CRUD ROUTES =======================

@blog_bp.route('/blog/posts', methods=['GET'])
@admin_required
def get_blog_posts():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')  # draft, published
        search = request.args.get('search', '').strip()
        author_id = request.args.get('author_id')
        category = request.args.get('category')
        tag = request.args.get('tag')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        scheduled = request.args.get('scheduled', 'false').lower() == 'true'
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if status:
            if status == 'scheduled':
                where_conditions.append("bp.status = 'published' AND bp.published_at > NOW()")
            else:
                where_conditions.append("bp.status = %s")
                params.append(status)
        
        if search:
            where_conditions.append("(bp.title LIKE %s OR bp.content LIKE %s OR bp.excerpt LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        if author_id:
            where_conditions.append("bp.author_id = %s")
            params.append(author_id)
        
        if category:
            where_conditions.append("JSON_CONTAINS(bp.categories, %s)")
            params.append(f'"{category}"')
        
        if tag:
            where_conditions.append("JSON_CONTAINS(bp.tags, %s)")
            params.append(f'"{tag}"')
        
        if scheduled:
            where_conditions.append("bp.status = 'published' AND bp.published_at > NOW()")
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Validate sort columns
        valid_sort_columns = ['title', 'status', 'published_at', 'created_at', 'views']
        if sort_by not in valid_sort_columns:
            sort_by = 'created_at'
        
        sort_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'
        
        # Get total count
        count_query = f"""
        SELECT COUNT(*) as total FROM blog_posts bp 
        LEFT JOIN admins a ON bp.author_id = a.id
        WHERE {where_clause}
        """
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get blog posts with author info
        posts_query = f"""
        SELECT bp.*, a.name as author_name,
               (SELECT COUNT(*) FROM blog_comments bc WHERE bc.post_id = bp.id AND bc.is_approved = 1) as comment_count
        FROM blog_posts bp
        LEFT JOIN admins a ON bp.author_id = a.id
        WHERE {where_clause}
        ORDER BY bp.{sort_by} {sort_direction}
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        posts = Database.execute_query(posts_query, params, fetch=True)
        
        # Parse JSON fields and add computed fields
        for post in posts:
            # Parse categories and tags
            if post.get('categories'):
                try:
                    post['categories'] = json.loads(post['categories'])
                except:
                    post['categories'] = []
            else:
                post['categories'] = []
            
            if post.get('tags'):
                try:
                    post['tags'] = json.loads(post['tags'])
                except:
                    post['tags'] = []
            else:
                post['tags'] = []
            
            # Parse meta fields
            if post.get('meta_data'):
                try:
                    post['meta_data'] = json.loads(post['meta_data'])
                except:
                    post['meta_data'] = {}
            
            # Add status labels
            if post['status'] == 'published' and post['published_at'] and post['published_at'] > datetime.now():
                post['status_label'] = 'Scheduled'
                post['is_scheduled'] = True
            else:
                post['status_label'] = post['status'].title()
                post['is_scheduled'] = False
            
            # Add reading time estimate
            if post['content']:
                word_count = len(post['content'].split())
                post['reading_time'] = max(1, round(word_count / 200))  # 200 words per minute
            else:
                post['reading_time'] = 1
        
        return jsonify(ResponseFormatter.paginated(posts, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/posts', methods=['POST'])
@admin_required
def create_blog_post():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        
        # Validate required fields
        title = data.get('title', '').strip()
        if not title:
            return error_response('Post title is required', 400)
        
        content = data.get('content', '').strip()
        if not content:
            return error_response('Post content is required', 400)
        
        # Generate slug
        slug = data.get('slug', '').strip()
        if not slug:
            slug = slugify(title)
        else:
            slug = slugify(slug)
        
        # Check for duplicate slug
        existing_slug = Database.execute_query(
            "SELECT COUNT(*) as count FROM blog_posts WHERE slug = %s",
            (slug,), fetch=True
        )[0]['count']
        
        if existing_slug > 0:
            slug = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M')}"
        
        # Get current admin as author
        current_admin = get_jwt_identity()
        author_id = current_admin['id']
        
        # Handle publishing
        status = data.get('status', 'draft')
        published_at = None
        
        if status == 'published':
            scheduled_time = data.get('published_at')
            if scheduled_time:
                try:
                    published_at = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                except:
                    published_at = datetime.now()
            else:
                published_at = datetime.now()
        
        # Prepare blog post data
        post_data = {
            'title': title,
            'slug': slug,
            'content': content,
            'excerpt': data.get('excerpt', '')[:500],  # Limit excerpt length
            'featured_image': data.get('featured_image'),
            'status': status,
            'author_id': author_id,
            'published_at': published_at,
            'categories': json.dumps(data.get('categories', [])),
            'tags': json.dumps(data.get('tags', [])),
            'meta_data': json.dumps({
                'meta_title': data.get('meta_title', title)[:60],
                'meta_description': data.get('meta_description', '')[:160],
                'meta_keywords': data.get('meta_keywords', ''),
                'allow_comments': bool(data.get('allow_comments', True)),
                'is_featured': bool(data.get('is_featured', False)),
                'seo_score': calculate_seo_score(title, content, data.get('meta_description', ''))
            })
        }
        
        # Create blog post
        post_query = """
        INSERT INTO blog_posts (title, slug, content, excerpt, featured_image, status, author_id,
                              published_at, categories, tags, meta_data, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        post_id = Database.execute_query(post_query, (
            post_data['title'], post_data['slug'], post_data['content'],
            post_data['excerpt'], post_data['featured_image'], post_data['status'],
            post_data['author_id'], post_data['published_at'], post_data['categories'],
            post_data['tags'], post_data['meta_data'], datetime.now()
        ))
        
        return success_response({
            'id': post_id,
            'slug': slug,
            'status': status
        }, 'Blog post created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/posts/<int:post_id>', methods=['GET'])
@admin_required
def get_blog_post(post_id):
    try:
        # Get blog post with author info
        post_query = """
        SELECT bp.*, a.name as author_name, a.email as author_email,
               (SELECT COUNT(*) FROM blog_comments bc WHERE bc.post_id = bp.id AND bc.is_approved = 1) as comment_count,
               (SELECT COUNT(*) FROM blog_post_views bpv WHERE bpv.post_id = bp.id) as total_views
        FROM blog_posts bp
        LEFT JOIN admins a ON bp.author_id = a.id
        WHERE bp.id = %s
        """
        
        post_result = Database.execute_query(post_query, (post_id,), fetch=True)
        
        if not post_result:
            return error_response('Blog post not found', 404)
        
        post = post_result[0]
        
        # Parse JSON fields
        if post.get('categories'):
            try:
                post['categories'] = json.loads(post['categories'])
            except:
                post['categories'] = []
        
        if post.get('tags'):
            try:
                post['tags'] = json.loads(post['tags'])
            except:
                post['tags'] = []
        
        if post.get('meta_data'):
            try:
                post['meta_data'] = json.loads(post['meta_data'])
            except:
                post['meta_data'] = {}
        
        # Add computed fields
        if post['content']:
            word_count = len(post['content'].split())
            post['reading_time'] = max(1, round(word_count / 200))
            post['word_count'] = word_count
        else:
            post['reading_time'] = 1
            post['word_count'] = 0
        
        # Get related posts (same categories/tags)
        if post['categories'] or post['tags']:
            related_query = """
            SELECT id, title, slug, featured_image, published_at
            FROM blog_posts
            WHERE id != %s AND status = 'published'
            AND (JSON_OVERLAPS(categories, %s) OR JSON_OVERLAPS(tags, %s))
            ORDER BY published_at DESC
            LIMIT 5
            """
            related_posts = Database.execute_query(
                related_query, 
                (post_id, json.dumps(post['categories']), json.dumps(post['tags'])), 
                fetch=True
            )
            post['related_posts'] = related_posts
        else:
            post['related_posts'] = []
        
        return success_response(post)
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/posts/<int:post_id>', methods=['PUT'])
@admin_required
def update_blog_post(post_id):
    try:
        data = get_request_data()
        
        # Check if post exists
        existing_post = Database.execute_query(
            "SELECT * FROM blog_posts WHERE id = %s", (post_id,), fetch=True
        )
        if not existing_post:
            return error_response('Blog post not found', 404)
        
        # Build update query
        update_fields = []
        params = []
        
        # Handle slug update
        if 'title' in data or 'slug' in data:
            if 'slug' in data and data['slug'].strip():
                new_slug = slugify(data['slug'].strip())
            elif 'title' in data:
                new_slug = slugify(data['title'])
            else:
                new_slug = existing_post[0]['slug']
            
            # Check for duplicate slug (excluding current post)
            duplicate_count = Database.execute_query(
                "SELECT COUNT(*) as count FROM blog_posts WHERE slug = %s AND id != %s",
                (new_slug, post_id), fetch=True
            )[0]['count']
            
            if duplicate_count > 0:
                new_slug = f"{new_slug}-{datetime.now().strftime('%Y%m%d%H%M')}"
            
            update_fields.append("slug = %s")
            params.append(new_slug)
        
        # Handle basic fields
        basic_fields = ['title', 'content', 'excerpt', 'featured_image', 'status']
        for field in basic_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                params.append(data[field])
        
        # Handle JSON fields
        if 'categories' in data:
            update_fields.append("categories = %s")
            params.append(json.dumps(data['categories']))
        
        if 'tags' in data:
            update_fields.append("tags = %s")
            params.append(json.dumps(data['tags']))
        
        # Handle meta data
        if any(key in data for key in ['meta_title', 'meta_description', 'meta_keywords', 'allow_comments', 'is_featured']):
            existing_meta = {}
            if existing_post[0].get('meta_data'):
                try:
                    existing_meta = json.loads(existing_post[0]['meta_data'])
                except:
                    existing_meta = {}
            
            meta_data = existing_meta.copy()
            if 'meta_title' in data:
                meta_data['meta_title'] = data['meta_title'][:60]
            if 'meta_description' in data:
                meta_data['meta_description'] = data['meta_description'][:160]
            if 'meta_keywords' in data:
                meta_data['meta_keywords'] = data['meta_keywords']
            if 'allow_comments' in data:
                meta_data['allow_comments'] = bool(data['allow_comments'])
            if 'is_featured' in data:
                meta_data['is_featured'] = bool(data['is_featured'])
            
            # Recalculate SEO score
            title = data.get('title', existing_post[0]['title'])
            content = data.get('content', existing_post[0]['content'])
            meta_desc = meta_data.get('meta_description', '')
            meta_data['seo_score'] = calculate_seo_score(title, content, meta_desc)
            
            update_fields.append("meta_data = %s")
            params.append(json.dumps(meta_data))
        
        # Handle publishing status and scheduling
        if 'status' in data:
            if data['status'] == 'published':
                scheduled_time = data.get('published_at')
                if scheduled_time:
                    try:
                        published_at = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                    except:
                        published_at = datetime.now()
                else:
                    # If no published_at provided and post wasn't published before, set to now
                    if existing_post[0]['status'] != 'published':
                        published_at = datetime.now()
                    else:
                        published_at = existing_post[0]['published_at']
                
                update_fields.append("published_at = %s")
                params.append(published_at)
        
        if not update_fields:
            return error_response('No fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(post_id)
        
        query = f"UPDATE blog_posts SET {', '.join(update_fields)} WHERE id = %s"
        Database.execute_query(query, params)
        
        return success_response(message='Blog post updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/posts/<int:post_id>', methods=['DELETE'])
@admin_required
def delete_blog_post(post_id):
    try:
        # Check if post exists
        existing_post = Database.execute_query(
            "SELECT * FROM blog_posts WHERE id = %s", (post_id,), fetch=True
        )
        if not existing_post:
            return error_response('Blog post not found', 404)
        
        # Delete associated comments
        Database.execute_query("DELETE FROM blog_comments WHERE post_id = %s", (post_id,))
        
        # Delete view records
        Database.execute_query("DELETE FROM blog_post_views WHERE post_id = %s", (post_id,))
        
        # Delete social shares
        Database.execute_query("DELETE FROM blog_social_shares WHERE post_id = %s", (post_id,))
        
        # Delete the post
        Database.execute_query("DELETE FROM blog_posts WHERE id = %s", (post_id,))
        
        return success_response(message='Blog post deleted successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BLOG MEDIA UPLOAD =======================

@blog_bp.route('/blog/posts/<int:post_id>/featured-image', methods=['POST'])
@admin_required
def upload_featured_image(post_id):
    try:
        if 'file' not in request.files:
            return error_response('No file provided', 400)
        
        file = request.files['file']
        
        if file.filename == '':
            return error_response('No file selected', 400)
        
        # Check if post exists
        post = Database.execute_query(
            "SELECT * FROM blog_posts WHERE id = %s", (post_id,), fetch=True
        )
        if not post:
            return error_response('Blog post not found', 404)
        
        # Save image
        filepath = save_image(file, 'blog', max_size=(1200, 800))
        if not filepath:
            return error_response('Failed to save image', 500)
        
        # Update post featured image
        query = "UPDATE blog_posts SET featured_image = %s, updated_at = %s WHERE id = %s"
        Database.execute_query(query, (filepath, datetime.now(), post_id))
        
        return success_response({
            'filepath': filepath,
            'url': f"/uploads/{filepath}"
        }, 'Featured image uploaded successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BLOG CATEGORIES & TAGS =======================

@blog_bp.route('/blog/categories', methods=['GET'])
@admin_required
def get_blog_categories():
    try:
        # Get all unique categories from blog posts
        categories = []
        posts = Database.execute_query(
            "SELECT categories FROM blog_posts WHERE status = 'published' AND categories IS NOT NULL",
            fetch=True
        )
        category_counts = {}
        for post in posts:
            if post['categories']:
                try:
                    post_categories = json.loads(post['categories'])
                    for cat in post_categories:
                        category_counts[cat] = category_counts.get(cat, 0) + 1
                except:
                    continue
        
        categories = [
            {'category': cat, 'post_count': count}
            for cat, count in sorted(category_counts.items(), key=lambda x: (-x[1], x[0]))
        ]
        
        return success_response(categories)
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/tags', methods=['GET'])
@admin_required
def get_blog_tags():
    try:
        # Get all unique tags from blog posts
        tags = []
        posts = Database.execute_query(
            "SELECT tags FROM blog_posts WHERE status = 'published' AND tags IS NOT NULL",
            fetch=True
        )
        tag_counts = {}
        for post in posts:
            if post['tags']:
                try:
                    post_tags = json.loads(post['tags'])
                    for tag in post_tags:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
                except:
                    continue
        
        tags = [
            {'tag': tag, 'post_count': count}
            for tag, count in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
        ]
        
        return success_response(tags)
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BLOG COMMENTS MANAGEMENT =======================

@blog_bp.route('/blog/comments', methods=['GET'])
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
        
        # Add status labels
        for comment in comments:
            if comment['is_spam']:
                comment['status'] = 'spam'
                comment['status_label'] = 'Spam'
            elif comment['is_approved']:
                comment['status'] = 'approved'
                comment['status_label'] = 'Approved'
            else:
                comment['status'] = 'pending'
                comment['status_label'] = 'Pending'
        
        return jsonify(ResponseFormatter.paginated(comments, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/comments/<int:comment_id>/approve', methods=['PUT'])
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

@blog_bp.route('/blog/comments/<int:comment_id>/reject', methods=['PUT'])
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

@blog_bp.route('/blog/comments/<int:comment_id>/spam', methods=['PUT'])
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

@blog_bp.route('/blog/comments/<int:comment_id>', methods=['DELETE'])
@admin_required
def delete_comment(comment_id):
    try:
        # Check if comment exists
        comment = Database.execute_query(
            "SELECT * FROM blog_comments WHERE id = %s", (comment_id,), fetch=True
        )
        if not comment:
            return error_response('Comment not found', 404)
        
        # Delete replies first
        Database.execute_query("DELETE FROM blog_comments WHERE parent_id = %s", (comment_id,))
        
        # Delete the comment
        Database.execute_query("DELETE FROM blog_comments WHERE id = %s", (comment_id,))
        
        return success_response(message='Comment deleted successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/comments/bulk-action', methods=['PUT'])
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

# ======================= BLOG ANALYTICS =======================

@blog_bp.route('/blog/analytics/dashboard', methods=['GET'])
@admin_required
def blog_analytics_dashboard():
    try:
        days = int(request.args.get('days', 30))
        
        # Post statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_posts,
            SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published_posts,
            SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft_posts,
            SUM(CASE WHEN status = 'published' AND published_at > NOW() THEN 1 ELSE 0 END) as scheduled_posts,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) THEN 1 ELSE 0 END) as recent_posts
        FROM blog_posts
        """
        stats = Database.execute_query(stats_query, (days,), fetch=True)[0]
        
        # View statistics
        views_query = """
        SELECT 
            COUNT(*) as total_views,
            COUNT(DISTINCT post_id) as viewed_posts,
            SUM(CASE WHEN view_date >= DATE_SUB(NOW(), INTERVAL %s DAY) THEN 1 ELSE 0 END) as recent_views
        FROM blog_post_views
        """
        views_stats = Database.execute_query(views_query, (days,), fetch=True)[0]
        
        # Top posts by views
        top_posts_query = """
        SELECT bp.id, bp.title, bp.slug, COUNT(bpv.id) as view_count
        FROM blog_posts bp
        LEFT JOIN blog_post_views bpv ON bp.id = bpv.post_id 
            AND bpv.view_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        WHERE bp.status = 'published'
        GROUP BY bp.id, bp.title, bp.slug
        ORDER BY view_count DESC
        LIMIT 10
        """
        top_posts = Database.execute_query(top_posts_query, (days,), fetch=True)
        
        # Views trend
        trend_query = """
        SELECT DATE(view_date) as date, COUNT(*) as views
        FROM blog_post_views
        WHERE view_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY DATE(view_date)
        ORDER BY date
        """
        views_trend = Database.execute_query(trend_query, (days,), fetch=True)
        
        return success_response({
            'days': days,
            'statistics': {**stats, **views_stats},
            'top_posts': top_posts,
            'views_trend': views_trend
        })
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/posts/<int:post_id>/analytics', methods=['GET'])
@admin_required
def get_post_analytics(post_id):
    try:
        days = int(request.args.get('days', 30))
        
        # View trends
        views_query = """
        SELECT view_date as date, COUNT(*) as views
        FROM blog_post_views
        WHERE post_id = %s AND view_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY view_date
        ORDER BY view_date
        """
        views_data = Database.execute_query(views_query, (post_id, days), fetch=True)
        
        # Top referrers
        referrers_query = """
        SELECT referrer, COUNT(*) as count
        FROM blog_post_views
        WHERE post_id = %s AND view_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        AND referrer IS NOT NULL AND referrer != ''
        GROUP BY referrer
        ORDER BY count DESC
        LIMIT 10
        """
        referrers = Database.execute_query(referrers_query, (post_id, days), fetch=True)
        
        # Comment analytics
        comments_query = """
        SELECT 
            COUNT(*) as total_comments,
            SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END) as approved_comments,
            SUM(CASE WHEN is_spam = 1 THEN 1 ELSE 0 END) as spam_comments
        FROM blog_comments
        WHERE post_id = %s
        """
        comments_stats = Database.execute_query(comments_query, (post_id,), fetch=True)[0]
        
        # Social shares
        shares_query = """
        SELECT platform, share_count
        FROM blog_social_shares
        WHERE post_id = %s
        ORDER BY share_count DESC
        """
        social_shares = Database.execute_query(shares_query, (post_id,), fetch=True)
        
        return success_response({
            'days': days,
            'views_trend': views_data,
            'top_referrers': referrers,
            'comments_stats': comments_stats,
            'social_shares': social_shares
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BLOG TRACKING (Public Endpoints) =======================

@blog_bp.route('/blog/posts/<int:post_id>/track-view', methods=['POST'])
def track_blog_view(post_id):
    """Track blog post view (public endpoint for frontend)"""
    try:
        # Get client info
        ip_address = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        referrer = request.headers.get('Referer', '')
        session_id = request.headers.get('X-Session-ID', '')
        
        today = datetime.now().date()
        
        # Try to insert view record (will fail silently if duplicate)
        try:
            Database.execute_query(
                """INSERT INTO blog_post_views (post_id, ip_address, user_agent, referrer, 
                   view_date, session_id) VALUES (%s, %s, %s, %s, %s, %s)""",
                (post_id, ip_address, user_agent, referrer, today, session_id)
            )
            
            # Update post view count
            Database.execute_query(
                "UPDATE blog_posts SET views = views + 1 WHERE id = %s",
                (post_id,)
            )
            
        except:
            # Duplicate view, ignore
            pass
        
        return success_response(message='View tracked')
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/posts/<int:post_id>/share/<platform>', methods=['POST'])
def track_social_share(post_id, platform):
    """Track social media shares (public endpoint)"""
    try:
        valid_platforms = ['facebook', 'twitter', 'linkedin', 'pinterest', 'whatsapp', 'telegram', 'email']
        
        if platform not in valid_platforms:
            return error_response('Invalid platform', 400)
        
        # Update or create share record
        Database.execute_query(
            """INSERT INTO blog_social_shares (post_id, platform, share_count)
               VALUES (%s, %s, 1)
               ON DUPLICATE KEY UPDATE share_count = share_count + 1, last_updated = NOW()""",
            (post_id, platform)
        )
        
        return success_response(message='Share tracked')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= RSS FEED GENERATION =======================

@blog_bp.route('/blog/rss', methods=['GET'])
def generate_rss_feed():
    try:
        # Get published posts for RSS
        posts_query = """
        SELECT title, slug, excerpt, content, published_at, author_id
        FROM blog_posts
        WHERE status = 'published' AND published_at <= NOW()
        ORDER BY published_at DESC
        LIMIT 20
        """
        posts = Database.execute_query(posts_query, fetch=True)
        
        # Get site config for RSS metadata
        site_name = SiteConfig.get_config('site_name') or 'Blog'
        site_description = SiteConfig.get_config('site_description') or 'Latest blog posts'
        
        # Generate RSS XML
        rss_items = []
        for post in posts:
            # Clean content for RSS (remove HTML tags for description)
            clean_content = re.sub(r'<[^>]+>', '', post['content'][:500])
            
            rss_items.append({
                'title': post['title'],
                'link': f"/blog/{post['slug']}",
                'description': post['excerpt'] or clean_content,
                'pub_date': post['published_at'].strftime('%a, %d %b %Y %H:%M:%S GMT') if post['published_at'] else ''
            })
        
        return success_response({
            'site_name': site_name,
            'site_description': site_description,
            'items': rss_items,
            'generated_at': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= NEWSLETTER MANAGEMENT =======================

@blog_bp.route('/blog/newsletter/subscribers', methods=['GET'])
@admin_required
def get_newsletter_subscribers():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        status = request.args.get('status')  # subscribed, unsubscribed, unverified
        search = request.args.get('search', '').strip()
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if status == 'subscribed':
            where_conditions.append("is_subscribed = 1 AND is_verified = 1")
        elif status == 'unsubscribed':
            where_conditions.append("is_subscribed = 0")
        elif status == 'unverified':
            where_conditions.append("is_verified = 0")
        
        if search:
            where_conditions.append("(email LIKE %s OR name LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM blog_newsletter_subscribers WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get subscribers
        subscribers_query = f"""
        SELECT * FROM blog_newsletter_subscribers
        WHERE {where_clause}
        ORDER BY subscription_date DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        subscribers = Database.execute_query(subscribers_query, params, fetch=True)
        
        # Parse preferences
        for subscriber in subscribers:
            if subscriber.get('preferences'):
                try:
                    subscriber['preferences'] = json.loads(subscriber['preferences'])
                except:
                    subscriber['preferences'] = {}
        
        return jsonify(ResponseFormatter.paginated(subscribers, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/newsletter/stats', methods=['GET'])
@admin_required
def get_newsletter_stats():
    try:
        stats_query = """
        SELECT 
            COUNT(*) as total_subscribers,
            SUM(CASE WHEN is_subscribed = 1 AND is_verified = 1 THEN 1 ELSE 0 END) as active_subscribers,
            SUM(CASE WHEN is_subscribed = 0 THEN 1 ELSE 0 END) as unsubscribed,
            SUM(CASE WHEN is_verified = 0 THEN 1 ELSE 0 END) as unverified,
            SUM(CASE WHEN subscription_date >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as new_subscribers_30d
        FROM blog_newsletter_subscribers
        """
        
        stats = Database.execute_query(stats_query, fetch=True)[0]
        
        # Growth trend
        growth_query = """
        SELECT DATE(subscription_date) as date, COUNT(*) as new_subscribers
        FROM blog_newsletter_subscribers
        WHERE subscription_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY DATE(subscription_date)
        ORDER BY date
        """
        growth_trend = Database.execute_query(growth_query, fetch=True)
        
        return success_response({
            'stats': stats,
            'growth_trend': growth_trend
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BULK OPERATIONS =======================

@blog_bp.route('/blog/posts/bulk-update', methods=['PUT'])
@admin_required
def bulk_update_posts():
    try:
        data = get_request_data()
        post_ids = data.get('post_ids', [])
        updates = data.get('updates', {})
        
        if not post_ids:
            return error_response('Post IDs are required', 400)
        
        if not updates:
            return error_response('Update data is required', 400)
        
        # Build update query
        update_fields = []
        params = []
        
        allowed_bulk_fields = ['status', 'categories', 'tags']
        
        for field in allowed_bulk_fields:
            if field in updates:
                if field in ['categories', 'tags']:
                    update_fields.append(f"{field} = %s")
                    params.append(json.dumps(updates[field]))
                else:
                    update_fields.append(f"{field} = %s")
                    params.append(updates[field])
        
        # Handle bulk publishing
        if updates.get('status') == 'published':
            update_fields.append("published_at = COALESCE(published_at, %s)")
            params.append(datetime.now())
        
        if not update_fields:
            return error_response('No valid fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        
        # Create placeholders for post IDs
        id_placeholders = ','.join(['%s'] * len(post_ids))
        params.extend(post_ids)
        
        query = f"UPDATE blog_posts SET {', '.join(update_fields)} WHERE id IN ({id_placeholders})"
        Database.execute_query(query, params)
        
        return success_response(message=f'{len(post_ids)} blog posts updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= SEARCH & ARCHIVE =======================

@blog_bp.route('/blog/search', methods=['GET'])
@admin_required
def search_blog_posts():
    try:
        query = request.args.get('q', '').strip()
        category = request.args.get('category')
        tag = request.args.get('tag')
        author_id = request.args.get('author_id')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        if not query and not category and not tag and not author_id:
            return error_response('Search query or filter is required', 400)
        
        offset = (page - 1) * per_page
        
        # Build search conditions
        where_conditions = ["bp.status = 'published'"]
        params = []
        
        if query:
            where_conditions.append("(bp.title LIKE %s OR bp.content LIKE %s OR bp.excerpt LIKE %s)")
            search_param = f"%{query}%"
            params.extend([search_param, search_param, search_param])
        
        if category:
            where_conditions.append("JSON_CONTAINS(bp.categories, %s)")
            params.append(f'"{category}"')
        
        if tag:
            where_conditions.append("JSON_CONTAINS(bp.tags, %s)")
            params.append(f'"{tag}"')
        
        if author_id:
            where_conditions.append("bp.author_id = %s")
            params.append(author_id)
        
        if date_from:
            where_conditions.append("DATE(bp.published_at) >= %s")
            params.append(date_from)
        
        if date_to:
            where_conditions.append("DATE(bp.published_at) <= %s")
            params.append(date_to)
        
        where_clause = " AND ".join(where_conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM blog_posts bp WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get search results
        search_query = f"""
        SELECT bp.id, bp.title, bp.slug, bp.excerpt, bp.featured_image, bp.published_at,
               bp.categories, bp.tags, a.name as author_name,
               (SELECT COUNT(*) FROM blog_comments bc WHERE bc.post_id = bp.id AND bc.is_approved = 1) as comment_count
        FROM blog_posts bp
        LEFT JOIN admins a ON bp.author_id = a.id
        WHERE {where_clause}
        ORDER BY bp.published_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        results = Database.execute_query(search_query, params, fetch=True)
        
        # Parse JSON fields
        for post in results:
            if post.get('categories'):
                try:
                    post['categories'] = json.loads(post['categories'])
                except:
                    post['categories'] = []
            
            if post.get('tags'):
                try:
                    post['tags'] = json.loads(post['tags'])
                except:
                    post['tags'] = []
        
        return jsonify(ResponseFormatter.paginated(results, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@blog_bp.route('/blog/archive', methods=['GET'])
@admin_required
def get_blog_archive():
    try:
        # Get posts grouped by year and month
        archive_query = """
        SELECT 
            YEAR(published_at) as year,
            MONTH(published_at) as month,
            MONTHNAME(published_at) as month_name,
            COUNT(*) as post_count
        FROM blog_posts
        WHERE status = 'published' AND published_at <= NOW()
        GROUP BY YEAR(published_at), MONTH(published_at)
        ORDER BY year DESC, month DESC
        """
        
        archive_data = Database.execute_query(archive_query, fetch=True)
        
        # Group by year
        grouped_archive = {}
        for item in archive_data:
            year = item['year']
            if year not in grouped_archive:
                grouped_archive[year] = {
                    'year': year,
                    'total_posts': 0,
                    'months': []
                }
            
            grouped_archive[year]['months'].append({
                'month': item['month'],
                'month_name': item['month_name'],
                'post_count': item['post_count']
            })
            grouped_archive[year]['total_posts'] += item['post_count']
        
        # Convert to list and sort
        archive_list = list(grouped_archive.values())
        archive_list.sort(key=lambda x: x['year'], reverse=True)
        
        return success_response(archive_list)
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= UTILITY FUNCTIONS =======================

def calculate_seo_score(title, content, meta_description):
    """Calculate basic SEO score for blog post"""
    score = 0
    
    # Title length (1-60 characters is optimal)
    if 1 <= len(title) <= 60:
        score += 20
    elif len(title) <= 70:
        score += 15
    
    # Meta description (120-160 characters is optimal)
    if 120 <= len(meta_description) <= 160:
        score += 20
    elif 100 <= len(meta_description) <= 180:
        score += 15
    
    # Content length (300+ words is good)
    word_count = len(content.split())
    if word_count >= 300:
        score += 20
    elif word_count >= 150:
        score += 10
    
    # Title in content (good for SEO)
    if title.lower() in content.lower():
        score += 15
    
    # Basic readability check (sentence length)
    sentences = re.split(r'[.!?]+', content)
    avg_sentence_length = sum(len(s.split()) for s in sentences if s.strip()) / max(len([s for s in sentences if s.strip()]), 1)
    if 15 <= avg_sentence_length <= 25:
        score += 15
    elif 10 <= avg_sentence_length <= 30:
        score += 10
    
    # Headers in content (H2, H3 tags)
    if re.search(r'<h[23]', content, re.IGNORECASE):
        score += 10
    
    return min(score, 100)  # Cap at 100