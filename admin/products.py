class Product:
    @staticmethod
    def create_product(data):
        query = """
        INSERT INTO products (name, description, price, sale_price, sku, stock_quantity, 
                              category_id, images, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            data['name'],
            data['description'],
            data['price'],
            data.get('sale_price'),
            data['sku'],
            data['stock_quantity'],
            data['category_id'],
            json.dumps(data.get('images', [])),
            data.get('status', 'active'),
            datetime.now()
        )
        return Database.execute_query(query, params)
    

from datetime import datetime, timedelta
import json
import bcrypt
from config import Config

class Database:
    @staticmethod
    def get_connection():
        return mysql.connector.connect(**Config.get_db_connection_string())
    
    @staticmethod
    def execute_query(query, params=None, fetch=False):
        conn = Database.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params or ())
            if fetch:
                result = cursor.fetchall()
                return result
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

class Admin:
    @staticmethod
    def create_admin(email, password, name, role='admin'):
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        query = """
        INSERT INTO admins (email, password, name, role, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        return Database.execute_query(query, (email, hashed_password, name, role, datetime.now()))
    
    @staticmethod
    def get_admin_by_email(email):
        query = "SELECT * FROM admins WHERE email = %s AND is_active = 1"
        result = Database.execute_query(query, (email,), fetch=True)
        return result[0] if result else None
    
    @staticmethod
    def verify_password(password, hashed_password):
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

class Customer:
    @staticmethod
    def create_customer(email, password, name, phone=None):
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        query = """
        INSERT INTO customers (email, password, name, phone, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        return Database.execute_query(query, (email, hashed_password, name, phone, datetime.now()))
    
    @staticmethod
    def get_customer_by_email(email):
        query = "SELECT * FROM customers WHERE email = %s AND is_active = 1"
        result = Database.execute_query(query, (email,), fetch=True)
        return result[0] if result else None

class Product:
    @staticmethod
    def create_product(data):
        query = """
        INSERT INTO products (name, description, price, sale_price, sku, stock_quantity, 
                            category_id, images, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            data['name'], data['description'], data['price'], data.get('sale_price'),
            data['sku'], data['stock_quantity'], data['category_id'], 
            json.dumps(data.get('images', [])), data.get('status', 'active'), datetime.now()
        )
        return Database.execute_query(query, params)
    
    @staticmethod
    def get_products(limit=20, offset=0, category_id=None, status='active'):
        where_clause = "WHERE status = %s"
        params = [status]
        
        if category_id:
            where_clause += " AND category_id = %s"
            params.append(category_id)
        
        query = f"""
        SELECT p.*, c.name as category_name 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id 
        {where_clause}
        ORDER BY p.created_at DESC 
        LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return Database.execute_query(query, params, fetch=True)
    
    @staticmethod
    def get_product_by_id(product_id):
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id 
        WHERE p.id = %s
        """
        result = Database.execute_query(query, (product_id,), fetch=True)
        return result[0] if result else None

class Category:
    @staticmethod
    def create_category(name, description=None, parent_id=None, image=None):
        query = """
        INSERT INTO categories (name, description, parent_id, image, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        return Database.execute_query(query, (name, description, parent_id, image, datetime.now()))
    
    @staticmethod
    def get_categories(parent_id=None):
        if parent_id is None:
            query = "SELECT * FROM categories WHERE parent_id IS NULL AND is_active = 1 ORDER BY name"
            params = ()
        else:
            query = "SELECT * FROM categories WHERE parent_id = %s AND is_active = 1 ORDER BY name"
            params = (parent_id,)
        return Database.execute_query(query, params, fetch=True)

class Order:
    @staticmethod
    def create_order(customer_id, total_amount, items, shipping_address):
        # Create order
        order_query = """
        INSERT INTO orders (customer_id, total_amount, status, payment_status, 
                          shipping_address, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        order_id = Database.execute_query(
            order_query, 
            (customer_id, total_amount, 'pending', 'pending', 
             json.dumps(shipping_address), datetime.now())
        )
        
        # Create order items
        for item in items:
            item_query = """
            INSERT INTO order_items (order_id, product_id, quantity, price)
            VALUES (%s, %s, %s, %s)
            """
            Database.execute_query(item_query, (order_id, item['product_id'], 
                                              item['quantity'], item['price']))
        
        return order_id
    
    @staticmethod
    def get_orders(customer_id=None, limit=20, offset=0):
        where_clause = ""
        params = []
        
        if customer_id:
            where_clause = "WHERE customer_id = %s"
            params.append(customer_id)
        
        query = f"""
        SELECT o.*, c.name as customer_name, c.email as customer_email
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        {where_clause}
        ORDER BY o.created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return Database.execute_query(query, params, fetch=True)

class SiteConfig:
    @staticmethod
    def get_config(key):
        query = "SELECT value FROM site_config WHERE config_key = %s"
        result = Database.execute_query(query, (key,), fetch=True)
        return result[0]['value'] if result else None
    
    @staticmethod
    def set_config(key, value):
        query = """
        INSERT INTO site_config (config_key, value, updated_at)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE value = %s, updated_at = %s
        """
        return Database.execute_query(query, (key, value, datetime.now(), value, datetime.now()))