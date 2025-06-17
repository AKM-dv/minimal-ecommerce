from flask import Blueprint, request
import json
from datetime import datetime

# Import our modules
from models import Database, Category
from utils import (admin_required, success_response, error_response, get_request_data, 
                   save_image, ResponseFormatter)

# Create blueprint
categories_bp = Blueprint('categories', __name__)

# ======================= CATEGORIES CRUD ROUTES =======================

@categories_bp.route('/categories', methods=['GET'])
@admin_required
def get_categories():
    try:
        parent_id = request.args.get('parent_id')
        include_children = request.args.get('include_children', 'false').lower() == 'true'
        search = request.args.get('search', '').strip()
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if parent_id == 'null' or parent_id == '':
            where_conditions.append("c.parent_id IS NULL")
        elif parent_id:
            where_conditions.append("c.parent_id = %s")
            params.append(int(parent_id))
        
        if status:
            where_conditions.append("c.is_active = %s")
            params.append(status == 'active')
        
        if search:
            where_conditions.append("(c.name LIKE %s OR c.description LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        if include_children:
            # Get all categories in hierarchical structure
            categories_query = f"""
            WITH RECURSIVE category_tree AS (
                -- Base case: get root categories or specific parent
                SELECT c.*, 0 as level,
                       (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id AND p.status = 'active') as product_count
                FROM categories c
                WHERE {where_clause}
                
                UNION ALL
                
                -- Recursive case: get children
                SELECT c.*, ct.level + 1,
                       (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id AND p.status = 'active') as product_count
                FROM categories c
                INNER JOIN category_tree ct ON c.parent_id = ct.id
                WHERE c.is_active = 1
            )
            SELECT * FROM category_tree
            ORDER BY level, display_order, name
            """
            categories = Database.execute_query(categories_query, params, fetch=True)
        else:
            # Get total count for pagination
            count_query = f"""
            SELECT COUNT(*) as total FROM categories c WHERE {where_clause}
            """
            total = Database.execute_query(count_query, params, fetch=True)[0]['total']
            
            # Get categories with product count
            offset = (page - 1) * per_page
            categories_query = f"""
            SELECT c.*,
                   (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id AND p.status = 'active') as product_count,
                   (SELECT COUNT(*) FROM categories child WHERE child.parent_id = c.id AND child.is_active = 1) as children_count,
                   parent.name as parent_name
            FROM categories c
            LEFT JOIN categories parent ON c.parent_id = parent.id
            WHERE {where_clause}
            ORDER BY c.display_order, c.name
            LIMIT %s OFFSET %s
            """
            params.extend([per_page, offset])
            categories = Database.execute_query(categories_query, params, fetch=True)
        
        # Parse JSON fields
        for category in categories:
            # Parse discount rules
            if category.get('discount_rules'):
                try:
                    category['discount_rules'] = json.loads(category['discount_rules'])
                except:
                    category['discount_rules'] = {}
            
            # Parse page customization
            if category.get('page_customization'):
                try:
                    category['page_customization'] = json.loads(category['page_customization'])
                except:
                    category['page_customization'] = {}
        
        if include_children:
            return success_response(categories)
        else:
            return jsonify(ResponseFormatter.paginated(categories, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@categories_bp.route('/categories', methods=['POST'])
@admin_required
def create_category():
    try:
        data = get_request_data()
        
        # Validate required fields
        name = data.get('name', '').strip()
        if not name:
            return error_response('Category name is required', 400)
        
        # Check for duplicate names at same level
        parent_id = data.get('parent_id')
        if parent_id == 'null' or parent_id == '':
            parent_id = None
        
        duplicate_check = """
        SELECT COUNT(*) as count FROM categories 
        WHERE name = %s AND parent_id %s AND is_active = 1
        """ % ('%s', 'IS NULL' if parent_id is None else '= %s')
        
        params = [name] if parent_id is None else [name, parent_id]
        duplicate_count = Database.execute_query(duplicate_check, params, fetch=True)[0]['count']
        
        if duplicate_count > 0:
            return error_response('Category name already exists at this level', 400)
        
        # Set display order
        display_order = data.get('display_order')
        if not display_order:
            # Get next display order
            order_query = """
            SELECT COALESCE(MAX(display_order), 0) + 1 as next_order 
            FROM categories WHERE parent_id %s
            """ % ('IS NULL' if parent_id is None else '= %s')
            
            order_params = [] if parent_id is None else [parent_id]
            display_order = Database.execute_query(order_query, order_params, fetch=True)[0]['next_order']
        
        # Prepare category data
        category_data = {
            'name': name,
            'description': data.get('description', ''),
            'parent_id': parent_id,
            'image': data.get('image'),
            'display_order': int(display_order),
            'is_active': bool(data.get('is_active', True)),
            'is_featured': bool(data.get('is_featured', False)),
            'meta_title': data.get('meta_title', ''),
            'meta_description': data.get('meta_description', ''),
            'meta_keywords': data.get('meta_keywords', ''),
            'discount_rules': json.dumps(data.get('discount_rules', {})),
            'page_customization': json.dumps(data.get('page_customization', {}))
        }
        
        # Create category
        category_query = """
        INSERT INTO categories (name, description, parent_id, image, display_order, is_active, 
                              is_featured, meta_title, meta_description, meta_keywords, 
                              discount_rules, page_customization, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        category_id = Database.execute_query(category_query, (
            category_data['name'], category_data['description'], category_data['parent_id'],
            category_data['image'], category_data['display_order'], category_data['is_active'],
            category_data['is_featured'], category_data['meta_title'], category_data['meta_description'],
            category_data['meta_keywords'], category_data['discount_rules'], 
            category_data['page_customization'], datetime.now()
        ))
        
        return success_response({'id': category_id}, 'Category created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@categories_bp.route('/categories/<int:category_id>', methods=['GET'])
@admin_required
def get_category(category_id):
    try:
        # Get category details with parent info
        category_query = """
        SELECT c.*, parent.name as parent_name,
               (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id AND p.status = 'active') as product_count,
               (SELECT COUNT(*) FROM categories child WHERE child.parent_id = c.id AND child.is_active = 1) as children_count
        FROM categories c
        LEFT JOIN categories parent ON c.parent_id = parent.id
        WHERE c.id = %s
        """
        
        category_result = Database.execute_query(category_query, (category_id,), fetch=True)
        
        if not category_result:
            return error_response('Category not found', 404)
        
        category = category_result[0]
        
        # Parse JSON fields
        if category.get('discount_rules'):
            try:
                category['discount_rules'] = json.loads(category['discount_rules'])
            except:
                category['discount_rules'] = {}
        
        if category.get('page_customization'):
            try:
                category['page_customization'] = json.loads(category['page_customization'])
            except:
                category['page_customization'] = {}
        
        # Get child categories
        children_query = """
        SELECT id, name, display_order, is_active,
               (SELECT COUNT(*) FROM products p WHERE p.category_id = categories.id AND p.status = 'active') as product_count
        FROM categories 
        WHERE parent_id = %s 
        ORDER BY display_order, name
        """
        children = Database.execute_query(children_query, (category_id,), fetch=True)
        category['children'] = children
        
        return success_response(category)
        
    except Exception as e:
        return error_response(str(e), 500)

@categories_bp.route('/categories/<int:category_id>', methods=['PUT'])
@admin_required
def update_category(category_id):
    try:
        data = get_request_data()
        
        # Check if category exists
        existing_category = Database.execute_query(
            "SELECT * FROM categories WHERE id = %s", (category_id,), fetch=True
        )
        if not existing_category:
            return error_response('Category not found', 404)
        
        # Build update query
        update_fields = []
        params = []
        
        updatable_fields = {
            'name': str, 'description': str, 'parent_id': int, 'image': str,
            'display_order': int, 'is_active': bool, 'is_featured': bool,
            'meta_title': str, 'meta_description': str, 'meta_keywords': str
        }
        
        for field, field_type in updatable_fields.items():
            if field in data:
                if field == 'parent_id' and data[field] in ['null', '', None]:
                    update_fields.append(f"{field} = NULL")
                else:
                    update_fields.append(f"{field} = %s")
                    if field_type == bool:
                        params.append(bool(data[field]))
                    elif field_type == int and data[field] not in [None, '']:
                        params.append(int(data[field]))
                    else:
                        params.append(data[field])
        
        # Handle JSON fields
        if 'discount_rules' in data:
            update_fields.append("discount_rules = %s")
            params.append(json.dumps(data['discount_rules']))
        
        if 'page_customization' in data:
            update_fields.append("page_customization = %s")
            params.append(json.dumps(data['page_customization']))
        
        if not update_fields:
            return error_response('No fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(category_id)
        
        query = f"UPDATE categories SET {', '.join(update_fields)} WHERE id = %s"
        Database.execute_query(query, params)
        
        return success_response(message='Category updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@categories_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    try:
        # Check if category exists
        existing_category = Database.execute_query(
            "SELECT * FROM categories WHERE id = %s", (category_id,), fetch=True
        )
        if not existing_category:
            return error_response('Category not found', 404)
        
        # Check if category has children
        children_count = Database.execute_query(
            "SELECT COUNT(*) as count FROM categories WHERE parent_id = %s", 
            (category_id,), fetch=True
        )[0]['count']
        
        if children_count > 0:
            return error_response('Cannot delete category with child categories', 400)
        
        # Check if category has products
        product_count = Database.execute_query(
            "SELECT COUNT(*) as count FROM products WHERE category_id = %s AND status = 'active'", 
            (category_id,), fetch=True
        )[0]['count']
        
        if product_count > 0:
            return error_response('Cannot delete category with active products', 400)
        
        # Soft delete - set inactive
        query = "UPDATE categories SET is_active = 0, updated_at = %s WHERE id = %s"
        Database.execute_query(query, (datetime.now(), category_id))
        
        return success_response(message='Category deleted successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CATEGORY IMAGE UPLOAD =======================

@categories_bp.route('/categories/<int:category_id>/image', methods=['POST'])
@admin_required
def upload_category_image(category_id):
    try:
        if 'file' not in request.files:
            return error_response('No file provided', 400)
        
        file = request.files['file']
        
        if file.filename == '':
            return error_response('No file selected', 400)
        
        # Check if category exists
        category = Database.execute_query(
            "SELECT * FROM categories WHERE id = %s", (category_id,), fetch=True
        )
        if not category:
            return error_response('Category not found', 404)
        
        # Save image
        filepath = save_image(file, 'categories', max_size=(600, 400))
        if not filepath:
            return error_response('Failed to save image', 500)
        
        # Update category image
        query = "UPDATE categories SET image = %s, updated_at = %s WHERE id = %s"
        Database.execute_query(query, (filepath, datetime.now(), category_id))
        
        return success_response({
            'filepath': filepath,
            'url': f"/uploads/{filepath}"
        }, 'Category image uploaded successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CATEGORY HIERARCHY =======================

@categories_bp.route('/categories/tree', methods=['GET'])
@admin_required
def get_category_tree():
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        # Build tree query
        where_clause = "1=1" if include_inactive else "is_active = 1"
        
        tree_query = f"""
        WITH RECURSIVE category_tree AS (
            -- Base case: root categories
            SELECT id, name, parent_id, display_order, is_active, is_featured,
                   0 as level, CAST(LPAD(display_order, 3, '0') AS CHAR(1000)) as path,
                   (SELECT COUNT(*) FROM products p WHERE p.category_id = categories.id AND p.status = 'active') as product_count
            FROM categories
            WHERE parent_id IS NULL AND {where_clause}
            
            UNION ALL
            
            -- Recursive case: child categories
            SELECT c.id, c.name, c.parent_id, c.display_order, c.is_active, c.is_featured,
                   ct.level + 1, CONCAT(ct.path, '-', LPAD(c.display_order, 3, '0')),
                   (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id AND p.status = 'active') as product_count
            FROM categories c
            INNER JOIN category_tree ct ON c.parent_id = ct.id
            WHERE {where_clause if include_inactive else 'c.is_active = 1'}
        )
        SELECT * FROM category_tree
        ORDER BY path
        """
        
        tree = Database.execute_query(tree_query, fetch=True)
        
        return success_response(tree)
        
    except Exception as e:
        return error_response(str(e), 500)

@categories_bp.route('/categories/<int:category_id>/move', methods=['PUT'])
@admin_required
def move_category(category_id):
    try:
        data = get_request_data()
        new_parent_id = data.get('new_parent_id')
        new_display_order = data.get('new_display_order')
        
        if new_parent_id == 'null' or new_parent_id == '':
            new_parent_id = None
        
        # Check if category exists
        category = Database.execute_query(
            "SELECT * FROM categories WHERE id = %s", (category_id,), fetch=True
        )
        if not category:
            return error_response('Category not found', 404)
        
        # Prevent circular reference (category becoming child of its descendant)
        if new_parent_id:
            circular_check = """
            WITH RECURSIVE category_descendants AS (
                SELECT id FROM categories WHERE id = %s
                UNION ALL
                SELECT c.id FROM categories c
                INNER JOIN category_descendants cd ON c.parent_id = cd.id
            )
            SELECT COUNT(*) as count FROM category_descendants WHERE id = %s
            """
            circular_count = Database.execute_query(
                circular_check, (category_id, new_parent_id), fetch=True
            )[0]['count']
            
            if circular_count > 0:
                return error_response('Cannot move category to its own descendant', 400)
        
        # Set display order if not provided
        if not new_display_order:
            order_query = """
            SELECT COALESCE(MAX(display_order), 0) + 1 as next_order 
            FROM categories WHERE parent_id %s
            """ % ('IS NULL' if new_parent_id is None else '= %s')
            
            order_params = [] if new_parent_id is None else [new_parent_id]
            new_display_order = Database.execute_query(order_query, order_params, fetch=True)[0]['next_order']
        
        # Update category
        if new_parent_id is None:
            query = "UPDATE categories SET parent_id = NULL, display_order = %s, updated_at = %s WHERE id = %s"
            params = (new_display_order, datetime.now(), category_id)
        else:
            query = "UPDATE categories SET parent_id = %s, display_order = %s, updated_at = %s WHERE id = %s"
            params = (new_parent_id, new_display_order, datetime.now(), category_id)
        
        Database.execute_query(query, params)
        
        return success_response(message='Category moved successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BULK OPERATIONS =======================

@categories_bp.route('/categories/bulk-update', methods=['PUT'])
@admin_required
def bulk_update_categories():
    try:
        data = get_request_data()
        category_ids = data.get('category_ids', [])
        updates = data.get('updates', {})
        
        if not category_ids:
            return error_response('Category IDs are required', 400)
        
        if not updates:
            return error_response('Update data is required', 400)
        
        # Build update query
        update_fields = []
        params = []
        
        allowed_bulk_fields = ['is_active', 'is_featured', 'display_order']
        
        for field in allowed_bulk_fields:
            if field in updates:
                update_fields.append(f"{field} = %s")
                params.append(updates[field])
        
        if not update_fields:
            return error_response('No valid fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        
        # Create placeholders for category IDs
        id_placeholders = ','.join(['%s'] * len(category_ids))
        params.extend(category_ids)
        
        query = f"UPDATE categories SET {', '.join(update_fields)} WHERE id IN ({id_placeholders})"
        Database.execute_query(query, params)
        
        return success_response(message=f'{len(category_ids)} categories updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@categories_bp.route('/categories/bulk-delete', methods=['DELETE'])
@admin_required
def bulk_delete_categories():
    try:
        data = get_request_data()
        category_ids = data.get('category_ids', [])
        
        if not category_ids:
            return error_response('Category IDs are required', 400)
        
        # Check for categories with children or products
        id_placeholders = ','.join(['%s'] * len(category_ids))
        
        children_check = f"""
        SELECT COUNT(*) as count FROM categories 
        WHERE parent_id IN ({id_placeholders}) AND is_active = 1
        """
        children_count = Database.execute_query(children_check, category_ids, fetch=True)[0]['count']
        
        if children_count > 0:
            return error_response('Cannot delete categories that have child categories', 400)
        
        products_check = f"""
        SELECT COUNT(*) as count FROM products 
        WHERE category_id IN ({id_placeholders}) AND status = 'active'
        """
        products_count = Database.execute_query(products_check, category_ids, fetch=True)[0]['count']
        
        if products_count > 0:
            return error_response('Cannot delete categories that have active products', 400)
        
        # Soft delete - set inactive
        params = [datetime.now()] + category_ids
        
        query = f"UPDATE categories SET is_active = 0, updated_at = %s WHERE id IN ({id_placeholders})"
        Database.execute_query(query, params)
        
        return success_response(message=f'{len(category_ids)} categories deleted successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= FEATURED CATEGORIES =======================

@categories_bp.route('/categories/featured', methods=['GET'])
@admin_required
def get_featured_categories():
    try:
        featured_query = """
        SELECT c.*, 
               (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id AND p.status = 'active') as product_count
        FROM categories c
        WHERE c.is_featured = 1 AND c.is_active = 1
        ORDER BY c.display_order, c.name
        """
        
        featured_categories = Database.execute_query(featured_query, fetch=True)
        
        # Parse JSON fields
        for category in featured_categories:
            if category.get('discount_rules'):
                try:
                    category['discount_rules'] = json.loads(category['discount_rules'])
                except:
                    category['discount_rules'] = {}
        
        return success_response(featured_categories)
        
    except Exception as e:
        return error_response(str(e), 500)

@categories_bp.route('/categories/<int:category_id>/toggle-featured', methods=['PUT'])
@admin_required
def toggle_featured_category(category_id):
    try:
        # Check if category exists
        category = Database.execute_query(
            "SELECT * FROM categories WHERE id = %s", (category_id,), fetch=True
        )
        if not category:
            return error_response('Category not found', 404)
        
        # Toggle featured status
        new_featured_status = not bool(category[0]['is_featured'])
        
        query = "UPDATE categories SET is_featured = %s, updated_at = %s WHERE id = %s"
        Database.execute_query(query, (new_featured_status, datetime.now(), category_id))
        
        status = 'featured' if new_featured_status else 'unfeatured'
        return success_response(message=f'Category {status} successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CATEGORY DISCOUNT RULES =======================

@categories_bp.route('/categories/<int:category_id>/discount-rules', methods=['GET'])
@admin_required
def get_category_discount_rules(category_id):
    try:
        category = Database.execute_query(
            "SELECT discount_rules FROM categories WHERE id = %s", (category_id,), fetch=True
        )
        
        if not category:
            return error_response('Category not found', 404)
        
        discount_rules = {}
        if category[0]['discount_rules']:
            try:
                discount_rules = json.loads(category[0]['discount_rules'])
            except:
                discount_rules = {}
        
        return success_response(discount_rules)
        
    except Exception as e:
        return error_response(str(e), 500)

@categories_bp.route('/categories/<int:category_id>/discount-rules', methods=['PUT'])
@admin_required
def update_category_discount_rules(category_id):
    try:
        data = get_request_data()
        
        # Check if category exists
        category = Database.execute_query(
            "SELECT * FROM categories WHERE id = %s", (category_id,), fetch=True
        )
        if not category:
            return error_response('Category not found', 404)
        
        # Update discount rules
        query = "UPDATE categories SET discount_rules = %s, updated_at = %s WHERE id = %s"
        Database.execute_query(query, (json.dumps(data), datetime.now(), category_id))
        
        return success_response(message='Category discount rules updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CATEGORY PAGE CUSTOMIZATION =======================

@categories_bp.route('/categories/<int:category_id>/page-customization', methods=['GET'])
@admin_required
def get_category_page_customization(category_id):
    try:
        category = Database.execute_query(
            "SELECT page_customization FROM categories WHERE id = %s", (category_id,), fetch=True
        )
        
        if not category:
            return error_response('Category not found', 404)
        
        page_customization = {}
        if category[0]['page_customization']:
            try:
                page_customization = json.loads(category[0]['page_customization'])
            except:
                page_customization = {}
        
        return success_response(page_customization)
        
    except Exception as e:
        return error_response(str(e), 500)

@categories_bp.route('/categories/<int:category_id>/page-customization', methods=['PUT'])
@admin_required
def update_category_page_customization(category_id):
    try:
        data = get_request_data()
        
        # Check if category exists
        category = Database.execute_query(
            "SELECT * FROM categories WHERE id = %s", (category_id,), fetch=True
        )
        if not category:
            return error_response('Category not found', 404)
        
        # Update page customization
        query = "UPDATE categories SET page_customization = %s, updated_at = %s WHERE id = %s"
        Database.execute_query(query, (json.dumps(data), datetime.now(), category_id))
        
        return success_response(message='Category page customization updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CATEGORY STATISTICS =======================

@categories_bp.route('/categories/stats', methods=['GET'])
@admin_required
def get_categories_stats():
    try:
        stats_query = """
        SELECT 
            COUNT(*) as total_categories,
            SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_categories,
            SUM(CASE WHEN is_featured = 1 AND is_active = 1 THEN 1 ELSE 0 END) as featured_categories,
            SUM(CASE WHEN parent_id IS NULL AND is_active = 1 THEN 1 ELSE 0 END) as root_categories
        FROM categories
        """
        
        stats = Database.execute_query(stats_query, fetch=True)[0]
        
        # Get category with most products
        top_category_query = """
        SELECT c.id, c.name, COUNT(p.id) as product_count
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id AND p.status = 'active'
        WHERE c.is_active = 1
        GROUP BY c.id, c.name
        ORDER BY product_count DESC
        LIMIT 1
        """
        
        top_category = Database.execute_query(top_category_query, fetch=True)
        stats['top_category'] = top_category[0] if top_category else None
        
        return success_response(stats)
        
    except Exception as e:
        return error_response(str(e), 500)