-- Create database
CREATE DATABASE IF NOT EXISTS ecommerce_db;
USE ecommerce_db;

-- Admins table
CREATE TABLE admins (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role ENUM('admin', 'super_admin') DEFAULT 'admin',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Customers table
CREATE TABLE customers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    gender ENUM('male', 'female', 'other'),
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    email_verified_at TIMESTAMP NULL,
    email_verification_token VARCHAR(255),
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMP NULL,
    last_login_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Categories table
CREATE TABLE categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id INT,
    image VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    is_featured BOOLEAN DEFAULT FALSE,
    display_order INT DEFAULT 0,
    meta_title VARCHAR(255),
    meta_description TEXT,
    meta_keywords TEXT,
    discount_rules JSON,
    page_customization JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
);

-- Products table
CREATE TABLE products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    sale_price DECIMAL(10,2),
    sku VARCHAR(100) UNIQUE NOT NULL,
    stock_quantity INT DEFAULT 0,
    category_id INT,
    images JSON,
    status ENUM('active', 'inactive', 'draft') DEFAULT 'active',
    is_featured BOOLEAN DEFAULT FALSE,
    weight DECIMAL(8,2),
    dimensions VARCHAR(100),
    tags JSON,
    meta_title VARCHAR(255),
    meta_description TEXT,
    meta_keywords TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);

-- Product variants table
CREATE TABLE product_variants (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    variant_type VARCHAR(50) NOT NULL, -- size, color, material
    variant_value VARCHAR(100) NOT NULL,
    price_adjustment DECIMAL(10,2) DEFAULT 0,
    stock_quantity INT DEFAULT 0,
    sku VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- Orders table
CREATE TABLE orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id INT NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2),
    shipping_cost DECIMAL(10,2) DEFAULT 0,
    tax_amount DECIMAL(10,2) DEFAULT 0,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    status ENUM('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'returned') DEFAULT 'pending',
    payment_status ENUM('pending', 'paid', 'failed', 'refunded', 'partially_refunded') DEFAULT 'pending',
    payment_method VARCHAR(50),
    shipping_address JSON NOT NULL,
    billing_address JSON,
    tracking_info JSON,
    notes TEXT,
    coupon_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

-- Order items table
CREATE TABLE order_items (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    variant_id INT,
    quantity INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE SET NULL
);

-- Customer addresses table
CREATE TABLE customer_addresses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    type ENUM('shipping', 'billing', 'both') DEFAULT 'shipping',
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    company VARCHAR(255),
    address_line_1 VARCHAR(255) NOT NULL,
    address_line_2 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    country VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

-- Order notes table
CREATE TABLE order_notes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    admin_id INT,
    note TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE SET NULL
);

-- Order status history table
CREATE TABLE order_status_history (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    status VARCHAR(50) NOT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

-- Order returns table
CREATE TABLE order_returns (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    return_amount DECIMAL(10,2) NOT NULL,
    reason TEXT,
    status ENUM('pending', 'approved', 'rejected', 'completed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

-- Order refunds table
CREATE TABLE order_refunds (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    refund_amount DECIMAL(10,2) NOT NULL,
    reason TEXT,
    status ENUM('pending', 'processed', 'failed') DEFAULT 'pending',
    transaction_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

-- Customer wishlists table
CREATE TABLE customer_wishlists (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    product_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY unique_customer_product (customer_id, product_id)
);

-- Customer support tickets table
CREATE TABLE customer_support_tickets (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    subject VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    status ENUM('open', 'in_progress', 'resolved', 'closed') DEFAULT 'open',
    priority ENUM('low', 'medium', 'high', 'urgent') DEFAULT 'medium',
    assigned_admin_id INT,
    resolution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_admin_id) REFERENCES admins(id) ON DELETE SET NULL
);

-- Customer newsletter subscriptions table
CREATE TABLE customer_newsletter_subscriptions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    subscribed BOOLEAN DEFAULT TRUE,
    subscription_preferences JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

-- Customer communications table
CREATE TABLE customer_communications (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    admin_id INT,
    type ENUM('email', 'sms', 'phone', 'note', 'account_created', 'profile_updated', 'password_reset', 'email_verified', 'verification_sent', 'newsletter_update') DEFAULT 'note',
    message TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE SET NULL
);

-- Coupons table
CREATE TABLE coupons (
    id INT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    type ENUM('percentage', 'fixed') NOT NULL,
    value DECIMAL(10,2) NOT NULL,
    minimum_amount DECIMAL(10,2) DEFAULT 0,
    usage_limit INT,
    used_count INT DEFAULT 0,
    valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product reviews table
CREATE TABLE product_reviews (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    customer_id INT NOT NULL,
    order_id INT,
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(255),
    review TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    is_approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
);

-- Blog posts table
CREATE TABLE blog_posts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    excerpt TEXT,
    featured_image VARCHAR(500),
    status ENUM('draft', 'published') DEFAULT 'draft',
    author_id INT NOT NULL,
    published_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES admins(id) ON DELETE CASCADE
);

-- Site configuration table
CREATE TABLE site_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Insert default admin
INSERT INTO admins (email, password, name, role) VALUES 
('admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.xgX9N8fm', 'Admin User', 'super_admin');
-- Default password: admin123

-- API integrations table
CREATE TABLE api_integrations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    service_name VARCHAR(100) NOT NULL,
    service_type ENUM('payment', 'shipping', 'notification', 'analytics', 'other') NOT NULL,
    environment ENUM('test', 'live') DEFAULT 'test',
    configuration JSON NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_test_mode BOOLEAN DEFAULT TRUE,
    webhook_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_service_type (service_type),
    INDEX idx_service_name (service_name)
);

-- API logs table
CREATE TABLE api_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    integration_id INT,
    activity_type VARCHAR(100) NOT NULL,
    description TEXT,
    request_data JSON,
    response_data JSON,
    status_code INT,
    response_time DECIMAL(10,3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES api_integrations(id) ON DELETE SET NULL,
    INDEX idx_activity_type (activity_type),
    INDEX idx_created_at (created_at),
    INDEX idx_integration_id (integration_id)
);

-- Custom API endpoints table
CREATE TABLE custom_api_endpoints (
    id INT PRIMARY KEY AUTO_INCREMENT,
    endpoint_name VARCHAR(100) NOT NULL,
    endpoint_url VARCHAR(500) NOT NULL,
    method ENUM('GET', 'POST', 'PUT', 'DELETE', 'PATCH') NOT NULL,
    headers JSON,
    configuration JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_endpoint_name (endpoint_name),
    INDEX idx_is_active (is_active)
);

-- Insert default site configurations
INSERT INTO site_config (config_key, value) VALUES 
('site_name', 'My Ecommerce Store'),
('site_description', 'Best online shopping experience'),
('currency', 'INR'),
('currency_symbol', '₹'),
('maintenance_mode', 'false'),
('items_per_page', '20');

-- Create indexes for better performance
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_status ON products(status);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_payment_status ON orders(payment_status);
CREATE INDEX idx_orders_created_at ON orders(created_at);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_order_notes_order ON order_notes(order_id);
CREATE INDEX idx_order_status_history_order ON order_status_history(order_id);
CREATE INDEX idx_order_returns_order ON order_returns(order_id);
CREATE INDEX idx_order_refunds_order ON order_refunds(order_id);
CREATE INDEX idx_customer_addresses_customer ON customer_addresses(customer_id);
CREATE INDEX idx_customer_wishlists_customer ON customer_wishlists(customer_id);
CREATE INDEX idx_customer_wishlists_product ON customer_wishlists(product_id);
CREATE INDEX idx_customer_support_tickets_customer ON customer_support_tickets(customer_id);
CREATE INDEX idx_customer_support_tickets_status ON customer_support_tickets(status);
CREATE INDEX idx_customer_newsletter_customer ON customer_newsletter_subscriptions(customer_id);
CREATE INDEX idx_customer_communications_customer ON customer_communications(customer_id);
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_created_at ON customers(created_at);




-- Additional tables for Blog Section (add to your existing database_scheme.sql)

-- Blog posts table (already exists in your schema, but with additional fields)
ALTER TABLE blog_posts 
ADD COLUMN categories JSON AFTER tags,
ADD COLUMN tags JSON AFTER categories,
ADD COLUMN meta_data JSON AFTER tags,
ADD COLUMN views INT DEFAULT 0 AFTER meta_data,
ADD COLUMN allow_comments BOOLEAN DEFAULT TRUE AFTER views,
ADD COLUMN is_featured BOOLEAN DEFAULT FALSE AFTER allow_comments;

-- Blog comments table
CREATE TABLE blog_comments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    post_id INT NOT NULL,
    parent_id INT NULL,
    author_name VARCHAR(255) NOT NULL,
    author_email VARCHAR(255) NOT NULL,
    author_website VARCHAR(255),
    content TEXT NOT NULL,
    is_approved BOOLEAN DEFAULT FALSE,
    is_spam BOOLEAN DEFAULT FALSE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES blog_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES blog_comments(id) ON DELETE CASCADE,
    INDEX idx_post_id (post_id),
    INDEX idx_parent_id (parent_id),
    INDEX idx_approved (is_approved),
    INDEX idx_created_at (created_at)
);

-- Blog post views tracking
CREATE TABLE blog_post_views (
    id INT PRIMARY KEY AUTO_INCREMENT,
    post_id INT NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    referrer VARCHAR(500),
    view_date DATE NOT NULL,
    view_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR(100),
    FOREIGN KEY (post_id) REFERENCES blog_posts(id) ON DELETE CASCADE,
    INDEX idx_post_id (post_id),
    INDEX idx_view_date (view_date),
    INDEX idx_session_id (session_id),
    UNIQUE KEY unique_view (post_id, ip_address, view_date, session_id)
);

-- Blog categories (separate table for better management)
CREATE TABLE blog_categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    slug VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(7) DEFAULT '#007bff',
    is_active BOOLEAN DEFAULT TRUE,
    post_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_slug (slug),
    INDEX idx_active (is_active)
);

-- Blog tags (separate table for better management)
CREATE TABLE blog_tags (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    slug VARCHAR(255) NOT NULL UNIQUE,
    color VARCHAR(7) DEFAULT '#6c757d',
    post_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_slug (slug)
);

-- Blog post-category relationships
CREATE TABLE blog_post_categories (
    post_id INT NOT NULL,
    category_id INT NOT NULL,
    PRIMARY KEY (post_id, category_id),
    FOREIGN KEY (post_id) REFERENCES blog_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES blog_categories(id) ON DELETE CASCADE
);

-- Blog post-tag relationships
CREATE TABLE blog_post_tags (
    post_id INT NOT NULL,
    tag_id INT NOT NULL,
    PRIMARY KEY (post_id, tag_id),
    FOREIGN KEY (post_id) REFERENCES blog_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES blog_tags(id) ON DELETE CASCADE
);

-- Blog social shares tracking
CREATE TABLE blog_social_shares (
    id INT PRIMARY KEY AUTO_INCREMENT,
    post_id INT NOT NULL,
    platform ENUM('facebook', 'twitter', 'linkedin', 'pinterest', 'whatsapp', 'telegram', 'email') NOT NULL,
    share_count INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES blog_posts(id) ON DELETE CASCADE,
    UNIQUE KEY unique_post_platform (post_id, platform),
    INDEX idx_post_id (post_id)
);

-- Blog newsletter subscribers
CREATE TABLE blog_newsletter_subscribers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    is_subscribed BOOLEAN DEFAULT TRUE,
    subscription_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    unsubscription_date TIMESTAMP NULL,
    verification_token VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    preferences JSON,
    INDEX idx_email (email),
    INDEX idx_subscribed (is_subscribed)
);

-- Blog analytics summary (daily aggregation)
CREATE TABLE blog_analytics_daily (
    id INT PRIMARY KEY AUTO_INCREMENT,
    post_id INT NOT NULL,
    analytics_date DATE NOT NULL,
    unique_views INT DEFAULT 0,
    total_views INT DEFAULT 0,
    total_comments INT DEFAULT 0,
    total_shares INT DEFAULT 0,
    bounce_rate DECIMAL(5,2) DEFAULT 0,
    avg_time_on_page INT DEFAULT 0,
    FOREIGN KEY (post_id) REFERENCES blog_posts(id) ON DELETE CASCADE,
    UNIQUE KEY unique_post_date (post_id, analytics_date),
    INDEX idx_date (analytics_date)
);

-- Insert some default blog categories
INSERT INTO blog_categories (name, slug, description, color) VALUES
('Technology', 'technology', 'Posts about technology and innovation', '#007bff'),
('Business', 'business', 'Business insights and strategies', '#28a745'),
('Lifestyle', 'lifestyle', 'Lifestyle and personal development', '#ffc107'),
('News', 'news', 'Latest news and updates', '#dc3545'),
('Tutorials', 'tutorials', 'How-to guides and tutorials', '#6f42c1');

-- Insert some default blog tags
INSERT INTO blog_tags (name, slug, color) VALUES
('AI', 'ai', '#007bff'),
('Machine Learning', 'machine-learning', '#007bff'),
('E-commerce', 'ecommerce', '#28a745'),
('Marketing', 'marketing', '#fd7e14'),
('SEO', 'seo', '#20c997'),
('Web Development', 'web-development', '#6f42c1'),
('Mobile', 'mobile', '#e83e8c'),
('Security', 'security', '#dc3545'),
('Analytics', 'analytics', '#17a2b8'),
('Social Media', 'social-media', '#6c757d');

-- Create indexes for better performance
CREATE INDEX idx_blog_posts_status_published ON blog_posts(status, published_at);
CREATE INDEX idx_blog_posts_author ON blog_posts(author_id);
CREATE INDEX idx_blog_posts_featured ON blog_posts(is_featured);
CREATE INDEX idx_blog_posts_slug ON blog_posts(slug);
CREATE INDEX idx_blog_comments_post_approved ON blog_comments(post_id, is_approved);
CREATE INDEX idx_blog_views_post_date ON blog_post_views(post_id, view_date);


-- Enhanced Coupons/Discounts Database Schema
-- Update your existing coupons table and add new tables

-- Drop existing simple coupons table if exists
DROP TABLE IF EXISTS coupons;

-- Enhanced coupons table with advanced features
CREATE TABLE coupons (
    id INT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Discount Configuration
    type ENUM('percentage', 'fixed_amount', 'buy_x_get_y', 'free_shipping') NOT NULL,
    value DECIMAL(10,2) NOT NULL,
    max_discount_amount DECIMAL(10,2) NULL, -- Max discount for percentage coupons
    
    -- Conditions
    minimum_amount DECIMAL(10,2) DEFAULT 0,
    maximum_amount DECIMAL(10,2) NULL,
    minimum_quantity INT DEFAULT 1,
    
    -- Usage Limits
    usage_limit INT NULL, -- Total usage limit
    usage_limit_per_customer INT DEFAULT 1,
    used_count INT DEFAULT 0,
    
    -- Validity
    valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP NULL,
    
    -- Targeting
    customer_eligibility ENUM('all', 'new_customers', 'existing_customers', 'specific_customers', 'customer_groups') DEFAULT 'all',
    product_eligibility ENUM('all', 'specific_products', 'specific_categories', 'exclude_products', 'exclude_categories') DEFAULT 'all',
    
    -- Advanced Settings
    stackable BOOLEAN DEFAULT FALSE, -- Can be combined with other coupons
    auto_apply BOOLEAN DEFAULT FALSE, -- Automatically apply if conditions met
    requires_shipping_address BOOLEAN DEFAULT FALSE,
    
    -- Buy X Get Y Configuration (JSON)
    buy_x_get_y_config JSON NULL, -- {buy_quantity: 2, get_quantity: 1, get_discount: 100}
    
    -- Status and Metadata
    is_active BOOLEAN DEFAULT TRUE,
    priority INT DEFAULT 0, -- Higher priority applied first
    created_by INT, -- Admin who created it
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (created_by) REFERENCES admins(id) ON DELETE SET NULL,
    INDEX idx_code (code),
    INDEX idx_active (is_active),
    INDEX idx_valid_dates (valid_from, valid_until),
    INDEX idx_type (type)
);

-- Coupon customer restrictions (for specific customer targeting)
CREATE TABLE coupon_customers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    coupon_id INT NOT NULL,
    customer_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    UNIQUE KEY unique_coupon_customer (coupon_id, customer_id)
);

-- Coupon product restrictions
CREATE TABLE coupon_products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    coupon_id INT NOT NULL,
    product_id INT NOT NULL,
    include_exclude ENUM('include', 'exclude') DEFAULT 'include',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY unique_coupon_product (coupon_id, product_id)
);

-- Coupon category restrictions
CREATE TABLE coupon_categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    coupon_id INT NOT NULL,
    category_id INT NOT NULL,
    include_exclude ENUM('include', 'exclude') DEFAULT 'include',
    include_subcategories BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    UNIQUE KEY unique_coupon_category (coupon_id, category_id)
);

-- Coupon usage tracking
CREATE TABLE coupon_usage (
    id INT PRIMARY KEY AUTO_INCREMENT,
    coupon_id INT NOT NULL,
    order_id INT NOT NULL,
    customer_id INT NOT NULL,
    discount_amount DECIMAL(10,2) NOT NULL,
    original_order_amount DECIMAL(10,2) NOT NULL,
    final_order_amount DECIMAL(10,2) NOT NULL,
    usage_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    INDEX idx_coupon_id (coupon_id),
    INDEX idx_customer_id (customer_id),
    INDEX idx_usage_date (usage_date)
);

-- Customer groups for group-based targeting
CREATE TABLE customer_groups (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    criteria JSON, -- Conditions for automatic group assignment
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Customer group memberships
CREATE TABLE customer_group_members (
    id INT PRIMARY KEY AUTO_INCREMENT,
    group_id INT NOT NULL,
    customer_id INT NOT NULL,
    assigned_automatically BOOLEAN DEFAULT FALSE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES customer_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    UNIQUE KEY unique_group_customer (group_id, customer_id)
);

-- Coupon group restrictions
CREATE TABLE coupon_customer_groups (
    id INT PRIMARY KEY AUTO_INCREMENT,
    coupon_id INT NOT NULL,
    group_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES customer_groups(id) ON DELETE CASCADE,
    UNIQUE KEY unique_coupon_group (coupon_id, group_id)
);

-- Flash sales / Time-based offers
CREATE TABLE flash_sales (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    discount_type ENUM('percentage', 'fixed_amount') NOT NULL,
    discount_value DECIMAL(10,2) NOT NULL,
    max_discount_amount DECIMAL(10,2) NULL,
    target_type ENUM('all_products', 'specific_products', 'specific_categories') DEFAULT 'all_products',
    usage_limit INT NULL,
    used_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    banner_text VARCHAR(500),
    banner_color VARCHAR(7) DEFAULT '#ff4444',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active_time (is_active, start_time, end_time)
);

-- Flash sale product targeting
CREATE TABLE flash_sale_products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    flash_sale_id INT NOT NULL,
    product_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (flash_sale_id) REFERENCES flash_sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY unique_sale_product (flash_sale_id, product_id)
);

-- Flash sale category targeting
CREATE TABLE flash_sale_categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    flash_sale_id INT NOT NULL,
    category_id INT NOT NULL,
    include_subcategories BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (flash_sale_id) REFERENCES flash_sales(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    UNIQUE KEY unique_sale_category (flash_sale_id, category_id)
);

-- Discount analytics (daily aggregated data)
CREATE TABLE discount_analytics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    date DATE NOT NULL,
    coupon_id INT,
    flash_sale_id INT,
    total_usage INT DEFAULT 0,
    total_discount_amount DECIMAL(10,2) DEFAULT 0,
    total_order_amount DECIMAL(10,2) DEFAULT 0,
    unique_customers INT DEFAULT 0,
    average_order_value DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE CASCADE,
    FOREIGN KEY (flash_sale_id) REFERENCES flash_sales(id) ON DELETE CASCADE,
    UNIQUE KEY unique_date_coupon (date, coupon_id),
    UNIQUE KEY unique_date_flash_sale (date, flash_sale_id),
    INDEX idx_date (date)
);

-- Bulk purchase discount rules
CREATE TABLE bulk_discount_rules (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rule_type ENUM('quantity_based', 'amount_based') NOT NULL,
    target_type ENUM('all_products', 'specific_products', 'specific_categories') DEFAULT 'all_products',
    tiers JSON NOT NULL, -- [{min_qty: 5, discount: 10}, {min_qty: 10, discount: 20}]
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Bulk discount product targeting
CREATE TABLE bulk_discount_products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    rule_id INT NOT NULL,
    product_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rule_id) REFERENCES bulk_discount_rules(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY unique_rule_product (rule_id, product_id)
);

-- Bulk discount category targeting
CREATE TABLE bulk_discount_categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    rule_id INT NOT NULL,
    category_id INT NOT NULL,
    include_subcategories BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rule_id) REFERENCES bulk_discount_rules(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    UNIQUE KEY unique_rule_category (rule_id, category_id)
);

-- First-time buyer promotions
CREATE TABLE first_buyer_promotions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    discount_type ENUM('percentage', 'fixed_amount', 'free_shipping') NOT NULL,
    discount_value DECIMAL(10,2) NOT NULL,
    minimum_amount DECIMAL(10,2) DEFAULT 0,
    max_discount_amount DECIMAL(10,2) NULL,
    valid_days_after_registration INT DEFAULT 30, -- Valid for X days after registration
    is_active BOOLEAN DEFAULT TRUE,
    usage_count INT DEFAULT 0,
    email_template TEXT, -- Welcome email template
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Insert some default customer groups
INSERT INTO customer_groups (name, description, criteria) VALUES
('VIP Customers', 'High-value customers with orders above ₹50,000', '{"min_total_spent": 50000}'),
('Regular Customers', 'Customers with 3+ orders', '{"min_order_count": 3}'),
('New Customers', 'Customers registered in last 30 days', '{"registered_within_days": 30}'),
('Inactive Customers', 'No orders in last 90 days', '{"no_orders_since_days": 90}');

-- Insert some sample bulk discount rules
INSERT INTO bulk_discount_rules (name, description, rule_type, tiers) VALUES
('Quantity Discount - Electronics', 'Volume discounts for electronics', 'quantity_based', 
 '[{"min_qty": 5, "discount": 5}, {"min_qty": 10, "discount": 10}, {"min_qty": 20, "discount": 15}]'),
('Amount-based Discount', 'Discounts based on order value', 'amount_based',
 '[{"min_amount": 1000, "discount": 5}, {"min_amount": 5000, "discount": 10}, {"min_amount": 10000, "discount": 15}]');

-- Insert default first-time buyer promotion
INSERT INTO first_buyer_promotions (name, description, discount_type, discount_value, minimum_amount, valid_days_after_registration) VALUES
('Welcome Discount', 'Welcome new customers with 10% off first order', 'percentage', 10.00, 500.00, 30);

-- Create indexes for better performance
CREATE INDEX idx_coupons_validity ON coupons(is_active, valid_from, valid_until);
CREATE INDEX idx_coupon_usage_date ON coupon_usage(usage_date);
CREATE INDEX idx_flash_sales_time ON flash_sales(start_time, end_time, is_active);
CREATE INDEX idx_customer_groups_active ON customer_groups(is_active);
CREATE INDEX idx_bulk_rules_active ON bulk_discount_rules(is_active);





-- Additional tables for Product Reviews System
-- Add to your existing database_scheme.sql

-- Enhanced product_reviews table (replace existing if needed)
DROP TABLE IF EXISTS product_reviews;
CREATE TABLE product_reviews (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    customer_id INT NOT NULL,
    order_id INT NULL, -- For verified purchase validation
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(255),
    review_text TEXT NOT NULL,
    review_images JSON, -- Array of image URLs/paths
    review_videos JSON, -- Array of video URLs/paths
    is_verified_purchase BOOLEAN DEFAULT FALSE,
    is_approved BOOLEAN DEFAULT FALSE,
    is_flagged BOOLEAN DEFAULT FALSE,
    helpfulness_score DECIMAL(5,2) DEFAULT 0.00,
    admin_response TEXT,
    approved_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    INDEX idx_product_id (product_id),
    INDEX idx_customer_id (customer_id),
    INDEX idx_rating (rating),
    INDEX idx_approved (is_approved),
    INDEX idx_created_at (created_at),
    INDEX idx_verified_purchase (is_verified_purchase)
);

-- Review helpfulness voting table
CREATE TABLE review_helpfulness (
    id INT PRIMARY KEY AUTO_INCREMENT,
    review_id INT NOT NULL,
    customer_id INT NOT NULL,
    is_helpful BOOLEAN NOT NULL, -- TRUE for helpful, FALSE for not helpful
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES product_reviews(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    UNIQUE KEY unique_customer_review_vote (review_id, customer_id),
    INDEX idx_review_id (review_id),
    INDEX idx_helpful (is_helpful)
);

-- Review reports table (for flagging inappropriate reviews)
CREATE TABLE review_reports (
    id INT PRIMARY KEY AUTO_INCREMENT,
    review_id INT NOT NULL,
    reported_by INT NOT NULL, -- Customer who reported
    reason ENUM('spam', 'fake', 'inappropriate', 'offensive', 'irrelevant', 'other') NOT NULL,
    description TEXT,
    status ENUM('pending', 'resolved', 'dismissed') DEFAULT 'pending',
    admin_action VARCHAR(100), -- Action taken by admin
    admin_note TEXT,
    resolved_by INT, -- Admin who resolved
    reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    FOREIGN KEY (review_id) REFERENCES product_reviews(id) ON DELETE CASCADE,
    FOREIGN KEY (reported_by) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_by) REFERENCES admins(id) ON DELETE SET NULL,
    INDEX idx_review_id (review_id),
    INDEX idx_status (status),
    INDEX idx_reported_at (reported_at)
);

-- Admin review actions log table
CREATE TABLE admin_review_actions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    review_id INT NOT NULL,
    admin_id INT NOT NULL,
    action ENUM('approved', 'rejected', 'flagged', 'responded', 'deleted') NOT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES product_reviews(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE CASCADE,
    INDEX idx_review_id (review_id),
    INDEX idx_admin_id (admin_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
);

-- Admin responses to reviews table
CREATE TABLE admin_review_responses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    review_id INT NOT NULL,
    admin_id INT NOT NULL,
    response_text TEXT NOT NULL,
    is_public BOOLEAN DEFAULT TRUE, -- Whether response is visible to customers
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES product_reviews(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE CASCADE,
    INDEX idx_review_id (review_id),
    INDEX idx_admin_id (admin_id),
    INDEX idx_created_at (created_at)
);

-- Review analytics table (daily aggregated data)
CREATE TABLE review_analytics_daily (
    id INT PRIMARY KEY AUTO_INCREMENT,
    analytics_date DATE NOT NULL,
    product_id INT,
    total_reviews INT DEFAULT 0,
    approved_reviews INT DEFAULT 0,
    average_rating DECIMAL(3,2) DEFAULT 0.00,
    verified_reviews INT DEFAULT 0,
    reviews_with_media INT DEFAULT 0,
    total_helpfulness_votes INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY unique_date_product (analytics_date, product_id),
    INDEX idx_date (analytics_date),
    INDEX idx_product_id (product_id)
);

-- Review quality scores table (for fake detection)
CREATE TABLE review_quality_scores (
    id INT PRIMARY KEY AUTO_INCREMENT,
    review_id INT NOT NULL,
    quality_score INT DEFAULT 0, -- 0-100 score
    fake_probability DECIMAL(5,4) DEFAULT 0.0000, -- 0.0000 to 1.0000
    suspicious_indicators JSON, -- Array of detected indicators
    sentiment_score DECIMAL(3,2) DEFAULT 0.00, -- -1.00 to 1.00
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES product_reviews(id) ON DELETE CASCADE,
    UNIQUE KEY unique_review_score (review_id),
    INDEX idx_quality_score (quality_score),
    INDEX idx_fake_probability (fake_probability)
);

-- Add columns to products table for review aggregation
ALTER TABLE products 
ADD COLUMN average_rating DECIMAL(3,2) DEFAULT 0.00 AFTER price,
ADD COLUMN review_count INT DEFAULT 0 AFTER average_rating,
ADD COLUMN last_reviewed_at TIMESTAMP NULL AFTER review_count;

-- Create indexes for better performance
CREATE INDEX idx_products_rating ON products(average_rating);
CREATE INDEX idx_products_review_count ON products(review_count);

-- Insert some sample review quality indicators for testing
INSERT INTO review_quality_scores (review_id, quality_score, fake_probability, suspicious_indicators, sentiment_score)
SELECT 
    id,
    FLOOR(RAND() * 100) + 1, -- Random quality score 1-100
    RAND() * 0.5, -- Random fake probability 0.0-0.5
    JSON_ARRAY('sample_indicator'), -- Sample indicators
    (RAND() * 2) - 1 -- Random sentiment -1.0 to 1.0
FROM product_reviews 
WHERE id IN (SELECT id FROM product_reviews LIMIT 10);

-- Create stored procedure to update product ratings
DELIMITER //
CREATE PROCEDURE UpdateProductRating(IN product_id_param INT)
BEGIN
    DECLARE avg_rating DECIMAL(3,2);
    DECLARE review_count_var INT;
    DECLARE last_review TIMESTAMP;
    
    -- Calculate average rating from approved reviews
    SELECT 
        COALESCE(AVG(rating), 0),
        COUNT(*),
        MAX(created_at)
    INTO avg_rating, review_count_var, last_review
    FROM product_reviews 
    WHERE product_id = product_id_param AND is_approved = 1;
    
    -- Update product table
    UPDATE products 
    SET 
        average_rating = avg_rating,
        review_count = review_count_var,
        last_reviewed_at = last_review
    WHERE id = product_id_param;
END //
DELIMITER ;

-- Create trigger to automatically update helpfulness score
DELIMITER //
CREATE TRIGGER update_helpfulness_score 
    AFTER INSERT ON review_helpfulness
    FOR EACH ROW
BEGIN
    DECLARE helpful_count INT;
    DECLARE total_count INT;
    DECLARE helpfulness DECIMAL(5,2);
    
    -- Count helpful and total votes
    SELECT 
        SUM(CASE WHEN is_helpful = 1 THEN 1 ELSE 0 END),
        COUNT(*)
    INTO helpful_count, total_count
    FROM review_helpfulness 
    WHERE review_id = NEW.review_id;
    
    -- Calculate helpfulness score (percentage)
    SET helpfulness = (helpful_count / total_count) * 100;
    
    -- Update review
    UPDATE product_reviews 
    SET helpfulness_score = helpfulness 
    WHERE id = NEW.review_id;
END //
DELIMITER ;

-- Sample data for testing (optional)
-- Insert sample reviews if products and customers exist
/*
INSERT INTO product_reviews (product_id, customer_id, rating, title, review_text, is_verified_purchase, is_approved) 
VALUES 
(1, 1, 5, 'Excellent Product!', 'This product exceeded my expectations. Great quality and fast delivery.', TRUE, TRUE),
(1, 2, 4, 'Good value for money', 'Nice product overall, though packaging could be better.', TRUE, TRUE),
(2, 1, 3, 'Average quality', 'The product is okay but nothing special. Expected better for the price.', TRUE, FALSE),
(2, 3, 5, 'Love it!', 'Amazing quality! Will definitely buy again. Highly recommended.', FALSE, FALSE),
(1, 3, 1, 'Poor quality', 'Product broke after one day. Very disappointed with the quality.', TRUE, TRUE);

-- Insert sample helpfulness votes
INSERT INTO review_helpfulness (review_id, customer_id, is_helpful) 
VALUES 
(1, 2, TRUE),
(1, 3, TRUE),
(2, 1, TRUE),
(2, 3, FALSE),
(5, 1, TRUE),
(5, 2, TRUE);

-- Insert sample review reports
INSERT INTO review_reports (review_id, reported_by, reason, description) 
VALUES 
(4, 1, 'fake', 'This review seems fake - generic language and unverified purchase'),
(4, 2, 'spam', 'Looks like a spam review with promotional content');
*/

-- Create views for common queries
CREATE VIEW approved_reviews_summary AS
SELECT 
    pr.product_id,
    p.name as product_name,
    COUNT(*) as total_approved_reviews,
    AVG(pr.rating) as average_rating,
    SUM(CASE WHEN pr.rating = 5 THEN 1 ELSE 0 END) as five_star_count,
    SUM(CASE WHEN pr.rating = 4 THEN 1 ELSE 0 END) as four_star_count,
    SUM(CASE WHEN pr.rating = 3 THEN 1 ELSE 0 END) as three_star_count,
    SUM(CASE WHEN pr.rating = 2 THEN 1 ELSE 0 END) as two_star_count,
    SUM(CASE WHEN pr.rating = 1 THEN 1 ELSE 0 END) as one_star_count,
    SUM(CASE WHEN pr.is_verified_purchase = 1 THEN 1 ELSE 0 END) as verified_review_count,
    MAX(pr.created_at) as last_review_date
FROM product_reviews pr
LEFT JOIN products p ON pr.product_id = p.id
WHERE pr.is_approved = 1
GROUP BY pr.product_id, p.name;

CREATE VIEW review_moderation_queue AS
SELECT 
    pr.id,
    pr.product_id,
    p.name as product_name,
    pr.customer_id,
    c.name as customer_name,
    pr.rating,
    pr.title,
    pr.review_text,
    pr.is_verified_purchase,
    pr.created_at,
    CASE 
        WHEN pr.is_flagged = 1 OR EXISTS(SELECT 1 FROM review_reports WHERE review_id = pr.id AND status = 'pending') THEN 'high'
        WHEN pr.rating <= 2 OR pr.review_images IS NOT NULL OR pr.review_videos IS NOT NULL THEN 'medium'
        ELSE 'low'
    END as priority,
    (SELECT COUNT(*) FROM review_reports WHERE review_id = pr.id AND status = 'pending') as pending_reports
FROM product_reviews pr
LEFT JOIN products p ON pr.product_id = p.id
LEFT JOIN customers c ON pr.customer_id = c.id
WHERE pr.is_approved = 0 AND pr.admin_response IS NULL
ORDER BY 
    CASE 
        WHEN pr.is_flagged = 1 THEN 1
        WHEN EXISTS(SELECT 1 FROM review_reports WHERE review_id = pr.id AND status = 'pending') THEN 2
        WHEN pr.rating <= 2 THEN 3
        ELSE 4
    END,
    pr.created_at ASC;

CREATE VIEW review_analytics_summary AS
SELECT 
    DATE(pr.created_at) as review_date,
    COUNT(*) as total_reviews,
    SUM(CASE WHEN pr.is_approved = 1 THEN 1 ELSE 0 END) as approved_reviews,
    SUM(CASE WHEN pr.is_verified_purchase = 1 THEN 1 ELSE 0 END) as verified_reviews,
    SUM(CASE WHEN pr.review_images IS NOT NULL OR pr.review_videos IS NOT NULL THEN 1 ELSE 0 END) as reviews_with_media,
    AVG(pr.rating) as average_rating,
    SUM(CASE WHEN pr.rating = 5 THEN 1 ELSE 0 END) as five_star_reviews,
    SUM(CASE WHEN pr.rating = 1 THEN 1 ELSE 0 END) as one_star_reviews,
    COUNT(DISTINCT pr.customer_id) as unique_reviewers,
    COUNT(DISTINCT pr.product_id) as products_reviewed
FROM product_reviews pr
WHERE pr.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(pr.created_at)
ORDER BY review_date DESC;

-- Create indexes for the views
CREATE INDEX idx_review_moderation_priority ON product_reviews(is_approved, admin_response, is_flagged, rating);
CREATE INDEX idx_review_date_approved ON product_reviews(created_at, is_approved);
CREATE INDEX idx_review_media ON product_reviews(review_images, review_videos);

-- Performance optimization indexes
CREATE INDEX idx_reviews_product_approved_rating ON product_reviews(product_id, is_approved, rating);
CREATE INDEX idx_reviews_customer_verified ON product_reviews(customer_id, is_verified_purchase);
CREATE INDEX idx_helpfulness_review_helpful ON review_helpfulness(review_id, is_helpful);
CREATE INDEX idx_reports_status_date ON review_reports(status, reported_at);
CREATE INDEX idx_admin_actions_date ON admin_review_actions(created_at, action);

-- Add foreign key constraints for better data integrity
ALTER TABLE review_helpfulness 
ADD CONSTRAINT fk_helpfulness_review 
FOREIGN KEY (review_id) REFERENCES product_reviews(id) ON DELETE CASCADE;

ALTER TABLE review_helpfulness 
ADD CONSTRAINT fk_helpfulness_customer 
FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE;

-- Create function to calculate review sentiment score
DELIMITER //
CREATE FUNCTION CalculateReviewSentiment(review_text TEXT) 
RETURNS DECIMAL(3,2)
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE sentiment_score DECIMAL(3,2) DEFAULT 0.00;
    DECLARE positive_count INT DEFAULT 0;
    DECLARE negative_count INT DEFAULT 0;
    DECLARE total_words INT;
    
    -- Simple sentiment analysis based on keyword counting
    SET review_text = LOWER(review_text);
    
    -- Count positive words
    SET positive_count = positive_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'good', ''))) / 4;
    SET positive_count = positive_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'great', ''))) / 5;
    SET positive_count = positive_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'excellent', ''))) / 9;
    SET positive_count = positive_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'amazing', ''))) / 7;
    SET positive_count = positive_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'perfect', ''))) / 7;
    SET positive_count = positive_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'love', ''))) / 4;
    SET positive_count = positive_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'awesome', ''))) / 7;
    
    -- Count negative words
    SET negative_count = negative_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'bad', ''))) / 3;
    SET negative_count = negative_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'terrible', ''))) / 8;
    SET negative_count = negative_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'awful', ''))) / 5;
    SET negative_count = negative_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'hate', ''))) / 4;
    SET negative_count = negative_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'horrible', ''))) / 8;
    SET negative_count = negative_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'worst', ''))) / 5;
    SET negative_count = negative_count + (LENGTH(review_text) - LENGTH(REPLACE(review_text, 'disappointing', ''))) / 13;
    
    -- Calculate sentiment score
    SET total_words = positive_count + negative_count;
    
    IF total_words > 0 THEN
        SET sentiment_score = (positive_count - negative_count) / total_words;
        
        -- Ensure score is between -1.00 and 1.00
        IF sentiment_score > 1.00 THEN SET sentiment_score = 1.00; END IF;
        IF sentiment_score < -1.00 THEN SET sentiment_score = -1.00; END IF;
    END IF;
    
    RETURN sentiment_score;
END //
DELIMITER ;

-- Create procedure for batch processing of review quality scores
DELIMITER //
CREATE PROCEDURE UpdateReviewQualityScores()
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE review_id_var INT;
    DECLARE review_text_var TEXT;
    DECLARE quality_score_var INT;
    DECLARE sentiment_score_var DECIMAL(3,2);
    
    DECLARE review_cursor CURSOR FOR 
        SELECT id, review_text 
        FROM product_reviews 
        WHERE id NOT IN (SELECT review_id FROM review_quality_scores);
    
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;
    
    OPEN review_cursor;
    
    review_loop: LOOP
        FETCH review_cursor INTO review_id_var, review_text_var;
        IF done THEN
            LEAVE review_loop;
        END IF;
        
        -- Calculate quality score (simplified)
        SET quality_score_var = CASE 
            WHEN LENGTH(review_text_var) >= 100 THEN 80
            WHEN LENGTH(review_text_var) >= 50 THEN 60
            WHEN LENGTH(review_text_var) >= 20 THEN 40
            ELSE 20
        END;
        
        -- Calculate sentiment score
        SET sentiment_score_var = CalculateReviewSentiment(review_text_var);
        
        -- Insert quality score record
        INSERT INTO review_quality_scores (review_id, quality_score, sentiment_score)
        VALUES (review_id_var, quality_score_var, sentiment_score_var)
        ON DUPLICATE KEY UPDATE 
            quality_score = quality_score_var,
            sentiment_score = sentiment_score_var,
            updated_at = NOW();
        
    END LOOP;
    
    CLOSE review_cursor;
END //
DELIMITER ;

-- Create event scheduler for daily analytics aggregation
CREATE EVENT IF NOT EXISTS daily_review_analytics
ON SCHEDULE EVERY 1 DAY
STARTS '2025-01-01 01:00:00'
DO
BEGIN
    -- Aggregate daily review analytics
    INSERT INTO review_analytics_daily (
        analytics_date, 
        product_id, 
        total_reviews, 
        approved_reviews, 
        average_rating, 
        verified_reviews, 
        reviews_with_media, 
        total_helpfulness_votes
    )
    SELECT 
        CURDATE() - INTERVAL 1 DAY,
        pr.product_id,
        COUNT(*),
        SUM(CASE WHEN pr.is_approved = 1 THEN 1 ELSE 0 END),
        AVG(CASE WHEN pr.is_approved = 1 THEN pr.rating ELSE NULL END),
        SUM(CASE WHEN pr.is_verified_purchase = 1 THEN 1 ELSE 0 END),
        SUM(CASE WHEN pr.review_images IS NOT NULL OR pr.review_videos IS NOT NULL THEN 1 ELSE 0 END),
        COALESCE((SELECT COUNT(*) FROM review_helpfulness rh WHERE rh.review_id IN 
            (SELECT id FROM product_reviews WHERE product_id = pr.product_id AND DATE(created_at) = CURDATE() - INTERVAL 1 DAY)), 0)
    FROM product_reviews pr
    WHERE DATE(pr.created_at) = CURDATE() - INTERVAL 1 DAY
    GROUP BY pr.product_id
    ON DUPLICATE KEY UPDATE
        total_reviews = VALUES(total_reviews),
        approved_reviews = VALUES(approved_reviews),
        average_rating = VALUES(average_rating),
        verified_reviews = VALUES(verified_reviews),
        reviews_with_media = VALUES(reviews_with_media),
        total_helpfulness_votes = VALUES(total_helpfulness_votes);
END;

-- Inventory Management Database Schema
-- Add these tables to your existing database_scheme.sql

-- Add inventory-specific columns to existing products table
ALTER TABLE products 
ADD COLUMN low_stock_threshold INT DEFAULT 10 AFTER stock_quantity,
ADD COLUMN last_restocked TIMESTAMP NULL AFTER low_stock_threshold;

-- Stock movements tracking table
CREATE TABLE stock_movements (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    movement_type ENUM('restock', 'sale', 'adjustment', 'transfer', 'return', 'damage') NOT NULL,
    quantity_change INT NOT NULL, -- Positive for additions, negative for reductions
    reference_type ENUM('order', 'purchase_order', 'manual_adjustment', 'transfer', 'csv_import', 'bulk_update') NOT NULL,
    reference_id INT NULL, -- ID of related order, PO, etc.
    supplier_id INT NULL,
    admin_id INT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
    FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE SET NULL,
    INDEX idx_product_id (product_id),
    INDEX idx_movement_type (movement_type),
    INDEX idx_created_at (created_at),
    INDEX idx_reference (reference_type, reference_id)
);

-- Suppliers table
CREATE TABLE suppliers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    address JSON, -- Store address as JSON object
    website VARCHAR(255),
    tax_id VARCHAR(50),
    payment_terms VARCHAR(255), -- e.g., "Net 30", "2/10 Net 30"
    currency VARCHAR(3) DEFAULT 'INR',
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name),
    INDEX idx_email (email),
    INDEX idx_active (is_active)
);

-- Purchase orders table
CREATE TABLE purchase_orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    supplier_id INT NOT NULL,
    status ENUM('draft', 'sent', 'confirmed', 'received', 'completed', 'cancelled') DEFAULT 'draft',
    total_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'INR',
    notes TEXT,
    expected_delivery_date DATE NULL,
    actual_delivery_date DATE NULL,
    created_by INT NOT NULL,
    sent_at TIMESTAMP NULL,
    confirmed_at TIMESTAMP NULL,
    received_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by) REFERENCES admins(id) ON DELETE RESTRICT,
    INDEX idx_order_number (order_number),
    INDEX idx_supplier_id (supplier_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- Purchase order items table
CREATE TABLE purchase_order_items (
    id INT PRIMARY KEY AUTO_INCREMENT,
    purchase_order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_cost DECIMAL(10,2) NOT NULL,
    total_cost DECIMAL(12,2) GENERATED ALWAYS AS (quantity * unit_cost) STORED,
    received_quantity INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    INDEX idx_purchase_order_id (purchase_order_id),
    INDEX idx_product_id (product_id)
);

-- Inventory adjustments table (for detailed tracking of manual adjustments)
CREATE TABLE inventory_adjustments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    adjustment_number VARCHAR(50) UNIQUE NOT NULL,
    reason_code ENUM('damaged', 'expired', 'lost', 'found', 'correction', 'shrinkage', 'other') NOT NULL,
    reason_description TEXT NOT NULL,
    status ENUM('draft', 'submitted', 'approved', 'rejected') DEFAULT 'draft',
    total_items INT DEFAULT 0,
    total_value_impact DECIMAL(12,2) DEFAULT 0,
    approved_by INT NULL,
    approved_at TIMESTAMP NULL,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES admins(id) ON DELETE RESTRICT,
    FOREIGN KEY (approved_by) REFERENCES admins(id) ON DELETE SET NULL,
    INDEX idx_adjustment_number (adjustment_number),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- Inventory adjustment items table
CREATE TABLE inventory_adjustment_items (
    id INT PRIMARY KEY AUTO_INCREMENT,
    adjustment_id INT NOT NULL,
    product_id INT NOT NULL,
    expected_quantity INT NOT NULL,
    actual_quantity INT NOT NULL,
    quantity_difference INT GENERATED ALWAYS AS (actual_quantity - expected_quantity) STORED,
    unit_cost DECIMAL(10,2) NOT NULL,
    value_impact DECIMAL(12,2) GENERATED ALWAYS AS ((actual_quantity - expected_quantity) * unit_cost) STORED,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (adjustment_id) REFERENCES inventory_adjustments(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    INDEX idx_adjustment_id (adjustment_id),
    INDEX idx_product_id (product_id)
);

-- Inventory valuation history table (for tracking cost changes)
CREATE TABLE inventory_valuations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    valuation_date DATE NOT NULL,
    quantity_on_hand INT NOT NULL,
    unit_cost DECIMAL(10,2) NOT NULL,
    total_value DECIMAL(12,2) GENERATED ALWAYS AS (quantity_on_hand * unit_cost) STORED,
    valuation_method ENUM('fifo', 'lifo', 'average', 'standard') DEFAULT 'average',
    calculated_by_system BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY unique_product_date (product_id, valuation_date),
    INDEX idx_product_id (product_id),
    INDEX idx_valuation_date (valuation_date)
);

-- Stock transfers table (for multi-location inventory)
CREATE TABLE stock_transfers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    transfer_number VARCHAR(50) UNIQUE NOT NULL,
    from_location VARCHAR(100) NOT NULL,
    to_location VARCHAR(100) NOT NULL,
    status ENUM('draft', 'sent', 'received', 'completed', 'cancelled') DEFAULT 'draft',
    total_items INT DEFAULT 0,
    notes TEXT,
    requested_by INT NOT NULL,
    sent_at TIMESTAMP NULL,
    received_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (requested_by) REFERENCES admins(id) ON DELETE RESTRICT,
    INDEX idx_transfer_number (transfer_number),
    INDEX idx_status (status),
    INDEX idx_from_location (from_location),
    INDEX idx_to_location (to_location)
);

-- Stock transfer items table
CREATE TABLE stock_transfer_items (
    id INT PRIMARY KEY AUTO_INCREMENT,
    transfer_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity_requested INT NOT NULL,
    quantity_sent INT DEFAULT 0,
    quantity_received INT DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transfer_id) REFERENCES stock_transfers(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    INDEX idx_transfer_id (transfer_id),
    INDEX idx_product_id (product_id)
);

-- Inventory alerts configuration table
CREATE TABLE inventory_alert_configs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    alert_type ENUM('low_stock', 'overstock', 'dead_stock', 'negative_stock') NOT NULL,
    threshold_value INT NOT NULL,
    alert_enabled BOOLEAN DEFAULT TRUE,
    email_recipients JSON, -- Array of email addresses
    last_alert_sent TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY unique_product_alert_type (product_id, alert_type),
    INDEX idx_product_id (product_id),
    INDEX idx_alert_type (alert_type),
    INDEX idx_enabled (alert_enabled)
);

-- Inventory cycles/counts table
CREATE TABLE inventory_cycles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    cycle_name VARCHAR(255) NOT NULL,
    cycle_type ENUM('full', 'partial', 'spot', 'abc_analysis') NOT NULL,
    status ENUM('planned', 'in_progress', 'completed', 'cancelled') DEFAULT 'planned',
    scheduled_date DATE NOT NULL,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    total_products INT DEFAULT 0,
    counted_products INT DEFAULT 0,
    variance_count INT DEFAULT 0,
    total_variance_value DECIMAL(12,2) DEFAULT 0,
    conducted_by INT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (conducted_by) REFERENCES admins(id) ON DELETE RESTRICT,
    INDEX idx_cycle_name (cycle_name),
    INDEX idx_status (status),
    INDEX idx_scheduled_date (scheduled_date)
);

-- Inventory cycle counts table
CREATE TABLE inventory_cycle_counts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    cycle_id INT NOT NULL,
    product_id INT NOT NULL,
    expected_quantity INT NOT NULL,
    counted_quantity INT NULL,
    variance_quantity INT GENERATED ALWAYS AS (counted_quantity - expected_quantity) STORED,
    unit_cost DECIMAL(10,2) NOT NULL,
    variance_value DECIMAL(12,2) GENERATED ALWAYS AS ((counted_quantity - expected_quantity) * unit_cost) STORED,
    count_status ENUM('pending', 'counted', 'verified', 'adjusted') DEFAULT 'pending',
    counted_by INT NULL,
    counted_at TIMESTAMP NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cycle_id) REFERENCES inventory_cycles(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    FOREIGN KEY (counted_by) REFERENCES admins(id) ON DELETE SET NULL,
    INDEX idx_cycle_id (cycle_id),
    INDEX idx_product_id (product_id),
    INDEX idx_count_status (count_status)
);

-- Inventory forecasting data table
CREATE TABLE inventory_forecasts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    forecast_date DATE NOT NULL,
    forecast_period_days INT NOT NULL,
    historical_sales_data JSON, -- Store sales history used for forecast
    predicted_demand INT NOT NULL,
    confidence_level DECIMAL(5,2) DEFAULT 0, -- 0-100%
    current_stock INT NOT NULL,
    recommended_reorder_quantity INT DEFAULT 0,
    recommended_reorder_date DATE NULL,
    forecast_method ENUM('moving_average', 'exponential_smoothing', 'linear_regression', 'seasonal') DEFAULT 'moving_average',
    seasonal_factors JSON NULL, -- For seasonal forecasting
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY unique_product_forecast_date (product_id, forecast_date),
    INDEX idx_product_id (product_id),
    INDEX idx_forecast_date (forecast_date),
    INDEX idx_reorder_date (recommended_reorder_date)
);

-- Inventory locations table (for multi-warehouse support)
CREATE TABLE inventory_locations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    location_code VARCHAR(50) UNIQUE NOT NULL,
    location_name VARCHAR(255) NOT NULL,
    location_type ENUM('warehouse', 'store', 'supplier', 'customer', 'transit') NOT NULL,
    address JSON,
    contact_person VARCHAR(255),
    phone VARCHAR(50),
    email VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_location_code (location_code),
    INDEX idx_location_type (location_type),
    INDEX idx_active (is_active)
);

-- Product location stock table
CREATE TABLE product_location_stock (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    location_id INT NOT NULL,
    quantity_on_hand INT DEFAULT 0,
    quantity_available INT DEFAULT 0, -- On hand minus reserved
    quantity_reserved INT DEFAULT 0,
    quantity_on_order INT DEFAULT 0,
    minimum_stock_level INT DEFAULT 0,
    maximum_stock_level INT DEFAULT 0,
    last_counted TIMESTAMP NULL,
    last_movement TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES inventory_locations(id) ON DELETE CASCADE,
    UNIQUE KEY unique_product_location (product_id, location_id),
    INDEX idx_product_id (product_id),
    INDEX idx_location_id (location_id),
    INDEX idx_quantity_available (quantity_available)
);

-- ABC analysis results table
CREATE TABLE abc_analysis_results (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    analysis_date DATE NOT NULL,
    annual_usage_value DECIMAL(12,2) NOT NULL,
    annual_usage_quantity INT NOT NULL,
    abc_class ENUM('A', 'B', 'C') NOT NULL,
    cumulative_percentage DECIMAL(5,2) NOT NULL,
    recommended_review_frequency_days INT NOT NULL,
    recommended_safety_stock_days INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY unique_product_analysis_date (product_id, analysis_date),
    INDEX idx_product_id (product_id),
    INDEX idx_analysis_date (analysis_date),
    INDEX idx_abc_class (abc_class)
);

-- Inventory reports table
CREATE TABLE inventory_reports (
    id INT PRIMARY KEY AUTO_INCREMENT,
    report_name VARCHAR(255) NOT NULL,
    report_type ENUM('stock_levels', 'movements', 'valuation', 'dead_stock', 'abc_analysis', 'forecasting', 'cycle_count') NOT NULL,
    parameters JSON, -- Store report filters and parameters
    file_path VARCHAR(500),
    file_format ENUM('pdf', 'excel', 'csv') NOT NULL,
    status ENUM('generating', 'completed', 'failed') DEFAULT 'generating',
    generated_by INT NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    download_count INT DEFAULT 0,
    expires_at TIMESTAMP NULL,
    FOREIGN KEY (generated_by) REFERENCES admins(id) ON DELETE RESTRICT,
    INDEX idx_report_type (report_type),
    INDEX idx_generated_by (generated_by),
    INDEX idx_generated_at (generated_at),
    INDEX idx_status (status)
);

-- Insert default inventory location
INSERT INTO inventory_locations (location_code, location_name, location_type, is_default) 
VALUES ('MAIN', 'Main Warehouse', 'warehouse', TRUE);

-- Insert default ABC analysis configuration
INSERT INTO site_config (config_key, value) VALUES 
('abc_analysis_config', '{"a_percentage": 80, "b_percentage": 15, "c_percentage": 5, "auto_run_monthly": true}'),
('inventory_settings', '{"default_low_stock_threshold": 10, "auto_reorder_enabled": false, "lead_time_days": 7}');

-- Create triggers for automatic stock movement recording

-- Trigger for order fulfillment
DELIMITER //
CREATE TRIGGER record_sale_movement 
    AFTER UPDATE ON orders
    FOR EACH ROW
BEGIN
    IF OLD.status != 'shipped' AND NEW.status = 'shipped' THEN
        INSERT INTO stock_movements (product_id, movement_type, quantity_change, reference_type, reference_id, notes)
        SELECT 
            oi.product_id,
            'sale',
            -oi.quantity,
            'order',
            NEW.id,
            CONCAT('Order ', NEW.order_number, ' shipped')
        FROM order_items oi
        WHERE oi.order_id = NEW.id;
    END IF;
END //
DELIMITER ;

-- Trigger for purchase order receiving
DELIMITER //
CREATE TRIGGER record_restock_movement 
    AFTER UPDATE ON purchase_orders
    FOR EACH ROW
BEGIN
    IF OLD.status != 'received' AND NEW.status = 'received' THEN
        INSERT INTO stock_movements (product_id, movement_type, quantity_change, reference_type, reference_id, supplier_id, notes)
        SELECT 
            poi.product_id,
            'restock',
            poi.received_quantity,
            'purchase_order',
            NEW.id,
            NEW.supplier_id,
            CONCAT('PO ', NEW.order_number, ' received')
        FROM purchase_order_items poi
        WHERE poi.purchase_order_id = NEW.id AND poi.received_quantity > 0;
    END IF;
END //
DELIMITER ;

-- Create stored procedures for inventory management

-- Procedure to update purchase order totals
DELIMITER //
CREATE PROCEDURE UpdatePurchaseOrderTotal(IN po_id INT)
BEGIN
    UPDATE purchase_orders 
    SET total_amount = (
        SELECT COALESCE(SUM(quantity * unit_cost), 0)
        FROM purchase_order_items 
        WHERE purchase_order_id = po_id
    )
    WHERE id = po_id;
END //
DELIMITER ;

-- Procedure for ABC analysis calculation
DELIMITER //
CREATE PROCEDURE CalculateABCAnalysis(IN analysis_date DATE)
BEGIN
    DECLARE total_value DECIMAL(20,2);
    DECLARE a_threshold DECIMAL(20,2);
    DECLARE b_threshold DECIMAL(20,2);
    
    -- Calculate total annual usage value
    SELECT SUM(annual_value) INTO total_value
    FROM (
        SELECT 
            p.id,
            SUM(oi.quantity * oi.price) as annual_value
        FROM products p
        LEFT JOIN order_items oi ON p.id = oi.product_id
        LEFT JOIN orders o ON oi.order_id = o.id
        WHERE o.created_at >= DATE_SUB(analysis_date, INTERVAL 1 YEAR)
              AND o.payment_status = 'paid'
        GROUP BY p.id
    ) annual_usage;
    
    SET a_threshold = total_value * 0.80;
    SET b_threshold = total_value * 0.95;
    
    -- Clear existing analysis for this date
    DELETE FROM abc_analysis_results WHERE analysis_date = analysis_date;
    
    -- Insert new ABC analysis results
    INSERT INTO abc_analysis_results (
        product_id, analysis_date, annual_usage_value, annual_usage_quantity,
        abc_class, cumulative_percentage, recommended_review_frequency_days,
        recommended_safety_stock_days
    )
    SELECT 
        product_id,
        analysis_date,
        annual_usage_value,
        annual_usage_quantity,
        CASE 
            WHEN running_total <= a_threshold THEN 'A'
            WHEN running_total <= b_threshold THEN 'B'
            ELSE 'C'
        END as abc_class,
        (running_total / total_value * 100) as cumulative_percentage,
        CASE 
            WHEN running_total <= a_threshold THEN 30  -- A items: monthly review
            WHEN running_total <= b_threshold THEN 90  -- B items: quarterly review
            ELSE 180  -- C items: semi-annual review
        END as recommended_review_frequency_days,
        CASE 
            WHEN running_total <= a_threshold THEN 7   -- A items: 1 week safety stock
            WHEN running_total <= b_threshold THEN 14  -- B items: 2 weeks safety stock
            ELSE 30   -- C items: 1 month safety stock
        END as recommended_safety_stock_days
    FROM (
        SELECT 
            p.id as product_id,
            COALESCE(SUM(oi.quantity * oi.price), 0) as annual_usage_value,
            COALESCE(SUM(oi.quantity), 0) as annual_usage_quantity,
            SUM(COALESCE(SUM(oi.quantity * oi.price), 0)) OVER (ORDER BY COALESCE(SUM(oi.quantity * oi.price), 0) DESC) as running_total
        FROM products p
        LEFT JOIN order_items oi ON p.id = oi.product_id
        LEFT JOIN orders o ON oi.order_id = o.id AND o.created_at >= DATE_SUB(analysis_date, INTERVAL 1 YEAR) AND o.payment_status = 'paid'
        WHERE p.status = 'active'
        GROUP BY p.id
        ORDER BY annual_usage_value DESC
    ) ranked_products;
    
END //
DELIMITER ;

-- Create views for common inventory queries

-- Stock levels summary view
CREATE VIEW inventory_stock_summary AS
SELECT 
    p.id,
    p.name,
    p.sku,
    p.stock_quantity,
    p.low_stock_threshold,
    p.price,
    c.name as category_name,
    (p.stock_quantity * p.price) as stock_value,
    CASE 
        WHEN p.stock_quantity = 0 THEN 'out_of_stock'
        WHEN p.stock_quantity <= COALESCE(p.low_stock_threshold, 10) THEN 'low_stock'
        ELSE 'in_stock'
    END as stock_status,
    p.last_restocked,
    DATEDIFF(NOW(), p.last_restocked) as days_since_restock
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
WHERE p.status = 'active';

-- Stock movements summary view
CREATE VIEW stock_movements_summary AS
SELECT 
    sm.id,
    sm.product_id,
    p.name as product_name,
    p.sku,
    sm.movement_type,
    sm.quantity_change,
    sm.reference_type,
    sm.reference_id,
    sm.notes,
    sm.created_at,
    s.name as supplier_name,
    a.name as admin_name
FROM stock_movements sm
LEFT JOIN products p ON sm.product_id = p.id
LEFT JOIN suppliers s ON sm.supplier_id = s.id
LEFT JOIN admins a ON sm.admin_id = a.id;

-- Low stock alerts view
CREATE VIEW low_stock_alerts AS
SELECT 
    p.id,
    p.name,
    p.sku,
    p.stock_quantity,
    p.low_stock_threshold,
    c.name as category_name,
    CASE 
        WHEN p.stock_quantity = 0 THEN 'critical'
        WHEN p.stock_quantity <= 5 THEN 'high'
        ELSE 'medium'
    END as urgency_level,
    COALESCE(sales.avg_daily_sales, 0) as avg_daily_sales,
    CASE 
        WHEN COALESCE(sales.avg_daily_sales, 0) > 0 
        THEN p.stock_quantity / sales.avg_daily_sales
        ELSE 999
    END as days_of_stock_remaining
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN (
    SELECT 
        oi.product_id,
        AVG(daily_sales.daily_quantity) as avg_daily_sales
    FROM (
        SELECT 
            oi.product_id,
            DATE(o.created_at) as sale_date,
            SUM(oi.quantity) as daily_quantity
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
              AND o.payment_status = 'paid'
        GROUP BY oi.product_id, DATE(o.created_at)
    ) daily_sales
    JOIN order_items oi ON daily_sales.product_id = oi.product_id
    GROUP BY oi.product_id
) sales ON p.id = sales.product_id
WHERE p.status = 'active' 
      AND p.stock_quantity <= COALESCE(p.low_stock_threshold, 10);

-- Create indexes for better performance
CREATE INDEX idx_products_stock_status ON products(stock_quantity, low_stock_threshold);
CREATE INDEX idx_products_last_restocked ON products(last_restocked);
CREATE INDEX idx_stock_movements_product_date ON stock_movements(product_id, created_at);
CREATE INDEX idx_stock_movements_type_date ON stock_movements(movement_type, created_at);
CREATE INDEX idx_purchase_orders_supplier_status ON purchase_orders(supplier_id, status);
CREATE INDEX idx_purchase_order_items_product ON purchase_order_items(product_id);
CREATE INDEX idx_inventory_cycles_date_status ON inventory_cycles(scheduled_date, status);

-- Create events for automated inventory tasks

-- Daily low stock alert check
CREATE EVENT IF NOT EXISTS daily_low_stock_check
ON SCHEDULE EVERY 1 DAY
STARTS '2025-01-01 08:00:00'
DO
BEGIN
    -- This would trigger email alerts for low stock items
    -- Implementation depends on your email system
    UPDATE inventory_alert_configs 
    SET last_alert_sent = NOW()
    WHERE alert_type = 'low_stock' 
          AND alert_enabled = TRUE
          AND product_id IN (
              SELECT id FROM products 
              WHERE stock_quantity <= COALESCE(low_stock_threshold, 10)
                    AND status = 'active'
          );
END;

-- Monthly ABC analysis
CREATE EVENT IF NOT EXISTS monthly_abc_analysis
ON SCHEDULE EVERY 1 MONTH
STARTS '2025-01-01 02:00:00'
DO
BEGIN
    CALL CalculateABCAnalysis(CURDATE());
END;








-- SEO Management Database Schema
-- Add these tables to your existing database_scheme.sql

-- SEO pages table for page-wise meta tag management
CREATE TABLE seo_pages (
    id INT PRIMARY KEY AUTO_INCREMENT,
    page_url VARCHAR(500) UNIQUE NOT NULL,
    page_title VARCHAR(255) NOT NULL,
    page_type ENUM('product', 'category', 'blog', 'custom', 'homepage') NOT NULL,
    meta_title VARCHAR(255),
    meta_description TEXT,
    meta_keywords TEXT,
    meta_tags JSON, -- Additional meta tags
    open_graph_tags JSON, -- Open Graph meta tags
    twitter_card_tags JSON, -- Twitter Card meta tags
    structured_data JSON, -- Schema.org structured data
    canonical_url VARCHAR(500),
    robots_directive VARCHAR(100) DEFAULT 'index,follow',
    focus_keyword VARCHAR(255),
    seo_score INT DEFAULT 0, -- 0-100 SEO score
    is_indexable BOOLEAN DEFAULT TRUE,
    last_audited TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_page_url (page_url),
    INDEX idx_page_type (page_type),
    INDEX idx_seo_score (seo_score),
    INDEX idx_last_audited (last_audited),
    INDEX idx_indexable (is_indexable)
);

-- SEO audits table for tracking audit history
CREATE TABLE seo_audits (
    id INT PRIMARY KEY AUTO_INCREMENT,
    page_id INT NOT NULL,
    seo_score INT NOT NULL,
    audit_results JSON, -- Detailed audit results including issues and suggestions
    audit_type ENUM('full', 'quick', 'technical', 'content') DEFAULT 'full',
    audit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (page_id) REFERENCES seo_pages(id) ON DELETE CASCADE,
    INDEX idx_page_id (page_id),
    INDEX idx_audit_date (audit_date),
    INDEX idx_seo_score (seo_score)
);

-- SEO keywords table for keyword tracking
CREATE TABLE seo_keywords (
    id INT PRIMARY KEY AUTO_INCREMENT,
    keyword VARCHAR(255) NOT NULL,
    target_url VARCHAR(500) NOT NULL,
    search_intent ENUM('informational', 'navigational', 'transactional', 'commercial') DEFAULT 'informational',
    priority INT DEFAULT 5, -- 1-10 priority scale
    notes TEXT,
    is_tracking_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_keyword (keyword),
    INDEX idx_target_url (target_url),
    INDEX idx_priority (priority),
    INDEX idx_tracking_enabled (is_tracking_enabled),
    UNIQUE KEY unique_keyword_url (keyword, target_url)
);

-- SEO keyword rankings table for tracking position changes
CREATE TABLE seo_keyword_rankings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    keyword_id INT NOT NULL,
    position INT NULL, -- NULL if not ranking in top 100
    search_volume INT DEFAULT 0,
    difficulty_score INT DEFAULT 0, -- 0-100 keyword difficulty
    cpc DECIMAL(10,2) DEFAULT 0.00, -- Cost per click
    search_engine ENUM('google', 'bing', 'yahoo') DEFAULT 'google',
    location VARCHAR(100) DEFAULT 'global',
    device ENUM('desktop', 'mobile', 'tablet') DEFAULT 'desktop',
    tracked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (keyword_id) REFERENCES seo_keywords(id) ON DELETE CASCADE,
    INDEX idx_keyword_id (keyword_id),
    INDEX idx_position (position),
    INDEX idx_tracked_date (tracked_date),
    INDEX idx_search_engine (search_engine)
);

-- Sitemap generations table for tracking sitemap creation
CREATE TABLE sitemap_generations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    urls_count INT DEFAULT 0,
    file_path VARCHAR(500),
    file_size INT DEFAULT 0, -- File size in bytes
    generation_status ENUM('generating', 'completed', 'failed') DEFAULT 'completed',
    error_message TEXT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_generated_at (generated_at),
    INDEX idx_status (generation_status)
);

-- SEO redirects table for managing 301/302 redirects
CREATE TABLE seo_redirects (
    id INT PRIMARY KEY AUTO_INCREMENT,
    source_url VARCHAR(500) NOT NULL,
    target_url VARCHAR(500) NOT NULL,
    redirect_type ENUM('301', '302', '307', '308') DEFAULT '301',
    is_active BOOLEAN DEFAULT TRUE,
    hit_count INT DEFAULT 0,
    notes TEXT,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES admins(id) ON DELETE RESTRICT,
    UNIQUE KEY unique_source_url (source_url),
    INDEX idx_source_url (source_url),
    INDEX idx_target_url (target_url),
    INDEX idx_active (is_active)
);

-- SEO issues table for tracking and managing SEO problems
CREATE TABLE seo_issues (
    id INT PRIMARY KEY AUTO_INCREMENT,
    page_id INT,
    issue_type ENUM('missing_meta_title', 'missing_meta_description', 'duplicate_content', 
                   'broken_link', 'missing_alt_text', 'slow_loading', 'mobile_unfriendly',
                   'missing_schema', 'incorrect_canonical', 'blocked_by_robots') NOT NULL,
    severity ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium',
    issue_description TEXT NOT NULL,
    suggested_fix TEXT,
    status ENUM('open', 'in_progress', 'resolved', 'ignored') DEFAULT 'open',
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    resolved_by INT NULL,
    FOREIGN KEY (page_id) REFERENCES seo_pages(id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_by) REFERENCES admins(id) ON DELETE SET NULL,
    INDEX idx_page_id (page_id),
    INDEX idx_issue_type (issue_type),
    INDEX idx_severity (severity),
    INDEX idx_status (status),
    INDEX idx_detected_at (detected_at)
);

-- SEO competitor analysis table
CREATE TABLE seo_competitors (
    id INT PRIMARY KEY AUTO_INCREMENT,
    competitor_name VARCHAR(255) NOT NULL,
    competitor_domain VARCHAR(255) NOT NULL UNIQUE,
    competitor_description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_domain (competitor_domain),
    INDEX idx_active (is_active)
);

-- SEO competitor rankings table
CREATE TABLE seo_competitor_rankings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    competitor_id INT NOT NULL,
    keyword_id INT NOT NULL,
    position INT NULL,
    tracked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (competitor_id) REFERENCES seo_competitors(id) ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES seo_keywords(id) ON DELETE CASCADE,
    INDEX idx_competitor_id (competitor_id),
    INDEX idx_keyword_id (keyword_id),
    INDEX idx_tracked_date (tracked_date),
    UNIQUE KEY unique_competitor_keyword_date (competitor_id, keyword_id, tracked_date)
);

-- SEO content analysis table
CREATE TABLE seo_content_analysis (
    id INT PRIMARY KEY AUTO_INCREMENT,
    page_id INT NOT NULL,
    content_length INT DEFAULT 0,
    word_count INT DEFAULT 0,
    heading_structure JSON, -- H1, H2, H3, etc. analysis
    keyword_density JSON, -- Keyword density analysis
    readability_score DECIMAL(5,2) DEFAULT 0.00,
    internal_links_count INT DEFAULT 0,
    external_links_count INT DEFAULT 0,
    images_count INT DEFAULT 0,
    images_without_alt INT DEFAULT 0,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (page_id) REFERENCES seo_pages(id) ON DELETE CASCADE,
    INDEX idx_page_id (page_id),
    INDEX idx_analyzed_at (analyzed_at),
    INDEX idx_word_count (word_count)
);

-- SEO backlinks table for tracking inbound links
CREATE TABLE seo_backlinks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    source_domain VARCHAR(255) NOT NULL,
    source_url VARCHAR(500) NOT NULL,
    target_url VARCHAR(500) NOT NULL,
    anchor_text VARCHAR(500),
    link_type ENUM('dofollow', 'nofollow', 'sponsored', 'ugc') DEFAULT 'dofollow',
    domain_authority INT DEFAULT 0,
    page_authority INT DEFAULT 0,
    spam_score INT DEFAULT 0,
    first_detected TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('active', 'lost', 'toxic', 'disavowed') DEFAULT 'active',
    INDEX idx_source_domain (source_domain),
    INDEX idx_target_url (target_url),
    INDEX idx_status (status),
    INDEX idx_first_detected (first_detected),
    UNIQUE KEY unique_source_target (source_url, target_url)
);

-- SEO reports table for scheduled reports
CREATE TABLE seo_reports (
    id INT PRIMARY KEY AUTO_INCREMENT,
    report_name VARCHAR(255) NOT NULL,
    report_type ENUM('audit', 'rankings', 'keywords', 'competitors', 'backlinks', 'comprehensive') NOT NULL,
    report_frequency ENUM('daily', 'weekly', 'monthly', 'quarterly') NOT NULL,
    recipients JSON, -- Email addresses for report delivery
    report_parameters JSON, -- Filters and settings for the report
    last_generated TIMESTAMP NULL,
    next_generation TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES admins(id) ON DELETE RESTRICT,
    INDEX idx_report_type (report_type),
    INDEX idx_next_generation (next_generation),
    INDEX idx_active (is_active)
);

-- Insert default SEO settings
INSERT INTO site_config (config_key, value) VALUES 
('global_seo_settings', '{"site_title": "", "site_description": "", "canonical_url": "", "robots_directives": {"index": true, "follow": true}}'),
('google_analytics_settings', '{"ga_tracking_id": "", "enhanced_ecommerce": false, "anonymize_ip": true}'),
('search_console_settings', '{"property_url": "", "verification_code": "", "auto_submit_sitemap": true}'),
('robots_txt_content', 'User-agent: *\nAllow: /\n\nDisallow: /admin/\nDisallow: /api/'),
('seo_automation_settings', '{"auto_generate_meta": true, "auto_audit_frequency": "weekly", "keyword_tracking_enabled": true}');

-- Create default SEO pages for important URLs
INSERT INTO seo_pages (page_url, page_title, page_type, meta_title, meta_description, is_indexable) VALUES
('/', 'Homepage', 'homepage', 'Welcome to Our Store', 'Discover amazing products at great prices', TRUE),
('/products', 'Products', 'custom', 'Our Products', 'Browse our complete product catalog', TRUE),
('/categories', 'Categories', 'custom', 'Product Categories', 'Shop by category to find what you need', TRUE),
('/blog', 'Blog', 'custom', 'Our Blog', 'Read our latest articles and insights', TRUE),
('/about', 'About Us', 'custom', 'About Our Company', 'Learn more about our story and mission', TRUE),
('/contact', 'Contact Us', 'custom', 'Contact Information', 'Get in touch with our team', TRUE);

-- Create triggers for automatic SEO page creation

-- Trigger for new products
DELIMITER //
CREATE TRIGGER create_seo_page_for_product 
    AFTER INSERT ON products
    FOR EACH ROW
BEGIN
    INSERT INTO seo_pages (page_url, page_title, page_type, meta_title, meta_description, focus_keyword, is_indexable)
    VALUES (
        CONCAT('/products/', NEW.id),
        NEW.name,
        'product',
        CONCAT(NEW.name, ' - Buy Online'),
        SUBSTRING(NEW.description, 1, 160),
        NEW.name,
        CASE WHEN NEW.status = 'active' THEN TRUE ELSE FALSE END
    );
END //
DELIMITER ;

-- Trigger for new categories
DELIMITER //
CREATE TRIGGER create_seo_page_for_category 
    AFTER INSERT ON categories
    FOR EACH ROW
BEGIN
    INSERT INTO seo_pages (page_url, page_title, page_type, meta_title, meta_description, focus_keyword, is_indexable)
    VALUES (
        CONCAT('/categories/', NEW.id),
        NEW.name,
        'category',
        CONCAT(NEW.name, ' Products - Shop Now'),
        COALESCE(NEW.description, CONCAT('Shop ', NEW.name, ' products at the best prices')),
        NEW.name,
        NEW.is_active
    );
END //
DELIMITER ;

-- Trigger for new blog posts
DELIMITER //
CREATE TRIGGER create_seo_page_for_blog_post 
    AFTER INSERT ON blog_posts
    FOR EACH ROW
BEGIN
    INSERT INTO seo_pages (page_url, page_title, page_type, meta_title, meta_description, focus_keyword, is_indexable)
    VALUES (
        CONCAT('/blog/', NEW.slug),
        NEW.title,
        'blog',
        NEW.title,
        COALESCE(NEW.excerpt, SUBSTRING(NEW.content, 1, 160)),
        NEW.title,
        CASE WHEN NEW.status = 'published' THEN TRUE ELSE FALSE END
    );
END //
DELIMITER ;

-- Update triggers for SEO pages when content changes

-- Update product SEO page when product changes
DELIMITER //
CREATE TRIGGER update_seo_page_for_product 
    AFTER UPDATE ON products
    FOR EACH ROW
BEGIN
    UPDATE seo_pages 
    SET 
        page_title = NEW.name,
        meta_title = CONCAT(NEW.name, ' - Buy Online'),
        meta_description = SUBSTRING(NEW.description, 1, 160),
        focus_keyword = NEW.name,
        is_indexable = CASE WHEN NEW.status = 'active' THEN TRUE ELSE FALSE END,
        updated_at = NOW()
    WHERE page_url = CONCAT('/products/', NEW.id);
END //
DELIMITER ;

-- Update category SEO page when category changes
DELIMITER //
CREATE TRIGGER update_seo_page_for_category 
    AFTER UPDATE ON categories
    FOR EACH ROW
BEGIN
    UPDATE seo_pages 
    SET 
        page_title = NEW.name,
        meta_title = CONCAT(NEW.name, ' Products - Shop Now'),
        meta_description = COALESCE(NEW.description, CONCAT('Shop ', NEW.name, ' products at the best prices')),
        focus_keyword = NEW.name,
        is_indexable = NEW.is_active,
        updated_at = NOW()
    WHERE page_url = CONCAT('/categories/', NEW.id);
END //
DELIMITER ;

-- Update blog post SEO page when blog post changes
DELIMITER //
CREATE TRIGGER update_seo_page_for_blog_post 
    AFTER UPDATE ON blog_posts
    FOR EACH ROW
BEGIN
    UPDATE seo_pages 
    SET 
        page_title = NEW.title,
        meta_title = NEW.title,
        meta_description = COALESCE(NEW.excerpt, SUBSTRING(NEW.content, 1, 160)),
        focus_keyword = NEW.title,
        is_indexable = CASE WHEN NEW.status = 'published' THEN TRUE ELSE FALSE END,
        updated_at = NOW()
    WHERE page_url = CONCAT('/blog/', NEW.slug);
END //
DELIMITER ;

-- Create stored procedures for SEO automation

-- Procedure to run SEO audit on all pages
DELIMITER //
CREATE PROCEDURE RunSEOAuditAll()
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE page_id INT;
    DECLARE audit_cursor CURSOR FOR 
        SELECT id FROM seo_pages WHERE is_indexable = TRUE;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;
    
    OPEN audit_cursor;
    
    audit_loop: LOOP
        FETCH audit_cursor INTO page_id;
        IF done THEN
            LEAVE audit_loop;
        END IF;
        
        -- This would call the Python audit function
        -- For now, just update the last_audited timestamp
        UPDATE seo_pages 
        SET last_audited = NOW() 
        WHERE id = page_id;
        
    END LOOP;
    
    CLOSE audit_cursor;
END //
DELIMITER ;

-- Procedure to update keyword rankings
DELIMITER //
CREATE PROCEDURE UpdateKeywordRankings()
BEGIN
    -- This would integrate with SEO APIs to get real rankings
    -- For now, just update the tracked_date
    UPDATE seo_keywords 
    SET updated_at = NOW() 
    WHERE is_tracking_enabled = TRUE;
END //
DELIMITER ;

-- Create views for SEO reporting

-- SEO health overview
CREATE VIEW seo_health_overview AS
SELECT 
    COUNT(*) as total_pages,
    AVG(seo_score) as avg_seo_score,
    SUM(CASE WHEN seo_score >= 80 THEN 1 ELSE 0 END) as excellent_pages,
    SUM(CASE WHEN seo_score >= 60 AND seo_score < 80 THEN 1 ELSE 0 END) as good_pages,
    SUM(CASE WHEN seo_score >= 40 AND seo_score < 60 THEN 1 ELSE 0 END) as average_pages,
    SUM(CASE WHEN seo_score < 40 THEN 1 ELSE 0 END) as poor_pages,
    COUNT(CASE WHEN last_audited IS NULL OR last_audited < DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) as pages_need_audit,
    COUNT(CASE WHEN is_indexable = 0 THEN 1 END) as non_indexable_pages
FROM seo_pages;

-- Keyword performance summary
CREATE VIEW keyword_performance_summary AS
SELECT 
    sk.id,
    sk.keyword,
    sk.target_url,
    sk.priority,
    skr.position as current_position,
    skr.search_volume,
    skr.tracked_date as last_tracked,
    LAG(skr.position) OVER (PARTITION BY sk.id ORDER BY skr.tracked_date DESC) as previous_position,
    CASE 
        WHEN skr.position IS NULL THEN 'not_ranking'
        WHEN skr.position <= 3 THEN 'excellent'
        WHEN skr.position <= 10 THEN 'good'
        WHEN skr.position <= 30 THEN 'average'
        ELSE 'poor'
    END as performance_grade
FROM seo_keywords sk
LEFT JOIN (
    SELECT DISTINCT keyword_id, position, search_volume, tracked_date,
           ROW_NUMBER() OVER (PARTITION BY keyword_id ORDER BY tracked_date DESC) as rn
    FROM seo_keyword_rankings
) skr ON sk.id = skr.keyword_id AND skr.rn = 1
WHERE sk.is_tracking_enabled = TRUE;

-- SEO issues summary
CREATE VIEW seo_issues_summary AS
SELECT 
    issue_type,
    severity,
    COUNT(*) as issue_count,
    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_issues,
    COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved_issues,
    AVG(DATEDIFF(COALESCE(resolved_at, NOW()), detected_at)) as avg_resolution_days
FROM seo_issues
GROUP BY issue_type, severity
ORDER BY 
    CASE severity 
        WHEN 'critical' THEN 1 
        WHEN 'high' THEN 2 
        WHEN 'medium' THEN 3 
        WHEN 'low' THEN 4 
    END,
    issue_count DESC;

-- Top performing content
CREATE VIEW top_performing_content AS
SELECT 
    sp.id,
    sp.page_url,
    sp.page_title,
    sp.page_type,
    sp.seo_score,
    COUNT(sk.id) as tracked_keywords,
    AVG(skr.position) as avg_keyword_position,
    COUNT(CASE WHEN skr.position <= 10 THEN 1 END) as top_10_keywords
FROM seo_pages sp
LEFT JOIN seo_keywords sk ON sp.page_url = sk.target_url
LEFT JOIN (
    SELECT DISTINCT keyword_id, position,
           ROW_NUMBER() OVER (PARTITION BY keyword_id ORDER BY tracked_date DESC) as rn
    FROM seo_keyword_rankings
) skr ON sk.id = skr.keyword_id AND skr.rn = 1
WHERE sp.is_indexable = TRUE
GROUP BY sp.id, sp.page_url, sp.page_title, sp.page_type, sp.seo_score
HAVING tracked_keywords > 0
ORDER BY sp.seo_score DESC, avg_keyword_position ASC;

-- Create indexes for better performance
CREATE INDEX idx_seo_pages_score_type ON seo_pages(seo_score, page_type);
CREATE INDEX idx_seo_audits_page_date ON seo_audits(page_id, audit_date);
CREATE INDEX idx_keyword_rankings_keyword_date ON seo_keyword_rankings(keyword_id, tracked_date);
CREATE INDEX idx_seo_issues_type_severity ON seo_issues(issue_type, severity, status);
CREATE INDEX idx_backlinks_domain_status ON seo_backlinks(source_domain, status);

-- Create events for automated SEO tasks

-- Daily SEO health check
CREATE EVENT IF NOT EXISTS daily_seo_health_check
ON SCHEDULE EVERY 1 DAY
STARTS '2025-01-01 02:00:00'
DO
BEGIN
    -- Identify pages that need auditing
    INSERT INTO seo_issues (page_id, issue_type, severity, issue_description)
    SELECT 
        id,
        'audit_needed',
        'low',
        'Page has not been audited in the last 30 days'
    FROM seo_pages 
    WHERE is_indexable = TRUE 
          AND (last_audited IS NULL OR last_audited < DATE_SUB(NOW(), INTERVAL 30 DAY))
          AND id NOT IN (
              SELECT page_id FROM seo_issues 
              WHERE issue_type = 'audit_needed' AND status = 'open'
          );
END;

-- Weekly keyword ranking update
CREATE EVENT IF NOT EXISTS weekly_keyword_update
ON SCHEDULE EVERY 1 WEEK
STARTS '2025-01-01 03:00:00'
DO
BEGIN
    CALL UpdateKeywordRankings();
END;

-- Monthly sitemap regeneration
CREATE EVENT IF NOT EXISTS monthly_sitemap_generation
ON SCHEDULE EVERY 1 MONTH
STARTS '2025-01-01 01:00:00'
DO
BEGIN
    -- This would trigger the sitemap generation endpoint
    UPDATE site_config 
    SET value = 'pending_regeneration'
    WHERE config_key = 'sitemap_status';
END;

-- Sample SEO keywords for testing
INSERT INTO seo_keywords (keyword, target_url, search_intent, priority, notes) VALUES
('ecommerce platform', '/', 'commercial', 10, 'Primary brand keyword'),
('online shopping', '/products', 'commercial', 9, 'High-value commercial keyword'),
('product categories', '/categories', 'informational', 7, 'Category page optimization'),
('shopping blog', '/blog', 'informational', 6, 'Content marketing keyword'),
('about us', '/about', 'navigational', 5, 'Brand awareness keyword');

-- Sample competitors for testing
INSERT INTO seo_competitors (competitor_name, competitor_domain, competitor_description) VALUES
('Amazon', 'amazon.com', 'Global e-commerce giant'),
('eBay', 'ebay.com', 'Online marketplace'),
('Shopify Stores', 'shopify.com', 'E-commerce platform competitor'),
('Local Competitor', 'localstore.com', 'Regional competitor in our market');

-- Insert sample structured data templates
INSERT INTO site_config (config_key, value) VALUES 
('schema_templates', '{
    "product": {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "",
        "description": "",
        "brand": {"@type": "Brand", "name": ""},
        "offers": {
            "@type": "Offer",
            "price": "",
            "priceCurrency": "INR",
            "availability": "https://schema.org/InStock"
        }
    },
    "organization": {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "",
        "url": "",
        "logo": "",
        "contactPoint": {
            "@type": "ContactPoint",
            "telephone": "",
            "contactType": "customer service"
        }
    }
}');

-- Performance optimization indexes
CREATE INDEX idx_seo_pages_composite ON seo_pages(page_type, is_indexable, seo_score);
CREATE INDEX idx_keyword_rankings_composite ON seo_keyword_rankings(keyword_id, tracked_date DESC, position);
CREATE INDEX idx_seo_issues_composite ON seo_issues(status, severity, detected_at);
CREATE INDEX idx_content_analysis_composite ON seo_content_analysis(page_id, analyzed_at DESC);