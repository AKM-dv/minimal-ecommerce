# Advanced coupons features - append to main coupons.py or import these functions

# ======================= FLASH SALES MANAGEMENT =======================

@coupons_bp.route('/flash-sales', methods=['GET'])
@admin_required
def get_flash_sales():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')  # active, upcoming, expired, inactive
        
        offset = (page - 1) * per_page
        
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if status == 'active':
            where_conditions.append("fs.is_active = 1 AND fs.start_time <= NOW() AND fs.end_time > NOW()")
        elif status == 'upcoming':
            where_conditions.append("fs.is_active = 1 AND fs.start_time > NOW()")
        elif status == 'expired':
            where_conditions.append("fs.end_time <= NOW()")
        elif status == 'inactive':
            where_conditions.append("fs.is_active = 0")
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM flash_sales fs WHERE {where_clause}"
        total = Database.execute_query(count_query, params, fetch=True)[0]['total']
        
        # Get flash sales
        sales_query = f"""
        SELECT fs.*,
               CASE 
                   WHEN fs.end_time <= NOW() THEN 'expired'
                   WHEN fs.start_time > NOW() THEN 'upcoming'
                   WHEN fs.is_active = 0 THEN 'inactive'
                   ELSE 'active'
               END as computed_status
        FROM flash_sales fs
        WHERE {where_clause}
        ORDER BY fs.created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        flash_sales = Database.execute_query(sales_query, params, fetch=True)
        
        # Convert decimals and add computed fields
        for sale in flash_sales:
            sale['discount_value'] = float(sale['discount_value'])
            if sale['max_discount_amount']:
                sale['max_discount_amount'] = float(sale['max_discount_amount'])
        
        return jsonify(ResponseFormatter.paginated(flash_sales, total, page, per_page))
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/flash-sales', methods=['POST'])
@admin_required
def create_flash_sale():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['name', 'start_time', 'end_time', 'discount_type', 'discount_value']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Parse dates
        try:
            start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
        except:
            return error_response('Invalid date format', 400)
        
        if end_time <= start_time:
            return error_response('End time must be after start time', 400)
        
        # Create flash sale
        sale_query = """
        INSERT INTO flash_sales (name, description, start_time, end_time, discount_type,
                               discount_value, max_discount_amount, target_type, usage_limit,
                               is_active, banner_text, banner_color, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        sale_id = Database.execute_query(sale_query, (
            data['name'], data.get('description', ''), start_time, end_time,
            data['discount_type'], float(data['discount_value']),
            float(data['max_discount_amount']) if data.get('max_discount_amount') else None,
            data.get('target_type', 'all_products'), int(data['usage_limit']) if data.get('usage_limit') else None,
            bool(data.get('is_active', True)), data.get('banner_text', ''),
            data.get('banner_color', '#ff4444'), datetime.now()
        ))
        
        return success_response({
            'id': sale_id,
            'name': data['name']
        }, 'Flash sale created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BULK DISCOUNT RULES =======================

@coupons_bp.route('/bulk-discounts', methods=['GET'])
@admin_required
def get_bulk_discount_rules():
    try:
        rules = Database.execute_query(
            "SELECT * FROM bulk_discount_rules ORDER BY created_at DESC", fetch=True
        )
        
        # Parse JSON tiers
        for rule in rules:
            if rule.get('tiers'):
                try:
                    rule['tiers'] = json.loads(rule['tiers'])
                except:
                    rule['tiers'] = []
        
        return success_response(rules)
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/bulk-discounts', methods=['POST'])
@admin_required
def create_bulk_discount_rule():
    try:
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['name', 'rule_type', 'tiers']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        if data['rule_type'] not in ['quantity_based', 'amount_based']:
            return error_response('Invalid rule type', 400)
        
        # Create bulk discount rule
        rule_query = """
        INSERT INTO bulk_discount_rules (name, description, rule_type, target_type, tiers, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        rule_id = Database.execute_query(rule_query, (
            data['name'], data.get('description', ''), data['rule_type'],
            data.get('target_type', 'all_products'), json.dumps(data['tiers']),
            bool(data.get('is_active', True)), datetime.now()
        ))
        
        return success_response({
            'id': rule_id,
            'name': data['name']
        }, 'Bulk discount rule created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= CUSTOMER GROUPS =======================

@coupons_bp.route('/customer-groups', methods=['GET'])
@admin_required
def get_customer_groups():
    try:
        groups_query = """
        SELECT cg.*,
               (SELECT COUNT(*) FROM customer_group_members cgm WHERE cgm.group_id = cg.id) as member_count
        FROM customer_groups cg
        ORDER BY cg.created_at DESC
        """
        groups = Database.execute_query(groups_query, fetch=True)
        
        # Parse JSON criteria
        for group in groups:
            if group.get('criteria'):
                try:
                    group['criteria'] = json.loads(group['criteria'])
                except:
                    group['criteria'] = {}
        
        return success_response(groups)
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/customer-groups', methods=['POST'])
@admin_required
def create_customer_group():
    try:
        data = get_request_data()
        
        if not data.get('name'):
            return error_response('Group name is required', 400)
        
        # Create customer group
        group_query = """
        INSERT INTO customer_groups (name, description, criteria, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        group_id = Database.execute_query(group_query, (
            data['name'], data.get('description', ''),
            json.dumps(data.get('criteria', {})),
            bool(data.get('is_active', True)), datetime.now()
        ))
        
        return success_response({
            'id': group_id,
            'name': data['name']
        }, 'Customer group created successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= COUPON ANALYTICS =======================

@coupons_bp.route('/coupons/analytics/dashboard', methods=['GET'])
@admin_required
def coupon_analytics_dashboard():
    try:
        days = int(request.args.get('days', 30))
        
        # Overall coupon statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_coupons,
            SUM(CASE WHEN is_active = 1 AND (valid_until IS NULL OR valid_until > NOW()) AND valid_from <= NOW() THEN 1 ELSE 0 END) as active_coupons,
            SUM(CASE WHEN valid_until IS NOT NULL AND valid_until <= NOW() THEN 1 ELSE 0 END) as expired_coupons,
            SUM(used_count) as total_usage
        FROM coupons
        """
        stats = Database.execute_query(stats_query, fetch=True)[0]
        
        # Discount given statistics
        discount_stats_query = """
        SELECT 
            COUNT(*) as total_orders_with_coupons,
            SUM(discount_amount) as total_discount_given,
            AVG(discount_amount) as avg_discount_amount
        FROM coupon_usage
        WHERE usage_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        discount_stats = Database.execute_query(discount_stats_query, (days,), fetch=True)[0]
        
        # Convert decimals
        if discount_stats['total_discount_given']:
            discount_stats['total_discount_given'] = float(discount_stats['total_discount_given'])
        if discount_stats['avg_discount_amount']:
            discount_stats['avg_discount_amount'] = float(discount_stats['avg_discount_amount'])
        
        # Top performing coupons
        top_coupons_query = """
        SELECT c.id, c.code, c.name, c.type, 
               COUNT(cu.id) as usage_count,
               SUM(cu.discount_amount) as total_discount
        FROM coupons c
        LEFT JOIN coupon_usage cu ON c.id = cu.coupon_id AND cu.usage_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        WHERE c.is_active = 1
        GROUP BY c.id, c.code, c.name, c.type
        HAVING usage_count > 0
        ORDER BY usage_count DESC
        LIMIT 10
        """
        top_coupons = Database.execute_query(top_coupons_query, (days,), fetch=True)
        
        # Convert decimals in top coupons
        for coupon in top_coupons:
            if coupon['total_discount']:
                coupon['total_discount'] = float(coupon['total_discount'])
        
        # Daily usage trends
        trends_query = """
        SELECT DATE(usage_date) as date, 
               COUNT(*) as usage_count,
               SUM(discount_amount) as total_discount
        FROM coupon_usage
        WHERE usage_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY DATE(usage_date)
        ORDER BY date
        """
        usage_trends = Database.execute_query(trends_query, (days,), fetch=True)
        
        # Convert decimals in trends
        for trend in usage_trends:
            trend['total_discount'] = float(trend['total_discount'])
        
        return success_response({
            'days': days,
            'statistics': {**stats, **discount_stats},
            'top_coupons': top_coupons,
            'usage_trends': usage_trends
        })
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= BULK OPERATIONS =======================

@coupons_bp.route('/coupons/bulk-update', methods=['PUT'])
@admin_required
def bulk_update_coupons():
    try:
        data = get_request_data()
        coupon_ids = data.get('coupon_ids', [])
        updates = data.get('updates', {})
        
        if not coupon_ids:
            return error_response('Coupon IDs are required', 400)
        
        if not updates:
            return error_response('Update data is required', 400)
        
        # Build update query
        update_fields = []
        params = []
        
        allowed_bulk_fields = ['is_active', 'priority']
        
        for field in allowed_bulk_fields:
            if field in updates:
                update_fields.append(f"{field} = %s")
                if field == 'is_active':
                    params.append(bool(updates[field]))
                else:
                    params.append(updates[field])
        
        if not update_fields:
            return error_response('No valid fields to update', 400)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        
        # Create placeholders for coupon IDs
        id_placeholders = ','.join(['%s'] * len(coupon_ids))
        params.extend(coupon_ids)
        
        query = f"UPDATE coupons SET {', '.join(update_fields)} WHERE id IN ({id_placeholders})"
        Database.execute_query(query, params)
        
        return success_response(message=f'{len(coupon_ids)} coupons updated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

@coupons_bp.route('/coupons/bulk-generate', methods=['POST'])
@admin_required
def bulk_generate_coupons():
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['count', 'name_template', 'type', 'value']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        count = int(data['count'])
        if count < 1 or count > 100:
            return error_response('Count must be between 1 and 100', 400)
        
        current_admin = get_jwt_identity()
        created_coupons = []
        
        # Generate coupons
        for i in range(count):
            code = generate_coupon_code(
                length=int(data.get('code_length', 8)),
                prefix=data.get('code_prefix', ''),
                suffix=data.get('code_suffix', ''),
                code_type=data.get('code_type', 'random')
            )
            
            # Check for duplicate
            existing = Database.execute_query(
                "SELECT COUNT(*) as count FROM coupons WHERE code = %s",
                (code,), fetch=True
            )[0]['count']
            
            if existing > 0:
                continue  # Skip duplicate
            
            name = data['name_template'].replace('{counter}', str(i + 1))
            
            # Create coupon
            coupon_query = """
            INSERT INTO coupons (code, name, description, type, value, minimum_amount,
                               usage_limit_per_customer, valid_from, valid_until,
                               customer_eligibility, is_active, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            valid_from = datetime.now()
            valid_until = None
            if data.get('valid_days'):
                valid_until = valid_from + timedelta(days=int(data['valid_days']))
            
            coupon_id = Database.execute_query(coupon_query, (
                code, name, data.get('description', ''), data['type'],
                float(data['value']), float(data.get('minimum_amount', 0)),
                int(data.get('usage_limit_per_customer', 1)), valid_from, valid_until,
                data.get('customer_eligibility', 'all'), True,
                current_admin['id'], datetime.now()
            ))
            
            created_coupons.append({
                'id': coupon_id,
                'code': code,
                'name': name
            })
        
        return success_response({
            'created_count': len(created_coupons),
            'coupons': created_coupons
        }, f'{len(created_coupons)} coupons generated successfully')
        
    except Exception as e:
        return error_response(str(e), 500)

# ======================= PUBLIC HELPER FUNCTIONS =======================

def get_applicable_coupons_for_customer(customer_id):
    """Get all applicable coupons for a specific customer"""
    try:
        # Get active coupons
        coupons_query = """
        SELECT * FROM coupons 
        WHERE is_active = 1 
        AND valid_from <= NOW() 
        AND (valid_until IS NULL OR valid_until > NOW())
        ORDER BY priority DESC, created_at DESC
        """
        coupons = Database.execute_query(coupons_query, fetch=True)
        
        applicable_coupons = []
        
        for coupon in coupons:
            # Check customer eligibility
            if coupon['customer_eligibility'] == 'new_customers':
                order_count = Database.execute_query(
                    "SELECT COUNT(*) as count FROM orders WHERE customer_id = %s AND payment_status = 'paid'",
                    (customer_id,), fetch=True
                )[0]['count']
                if order_count > 0:
                    continue
            
            elif coupon['customer_eligibility'] == 'existing_customers':
                order_count = Database.execute_query(
                    "SELECT COUNT(*) as count FROM orders WHERE customer_id = %s AND payment_status = 'paid'",
                    (customer_id,), fetch=True
                )[0]['count']
                if order_count == 0:
                    continue
            
            elif coupon['customer_eligibility'] == 'specific_customers':
                allowed = Database.execute_query(
                    "SELECT COUNT(*) as count FROM coupon_customers WHERE coupon_id = %s AND customer_id = %s",
                    (coupon['id'], customer_id), fetch=True
                )[0]['count']
                if allowed == 0:
                    continue
            
            # Check usage limit per customer
            if coupon['usage_limit_per_customer']:
                customer_usage = Database.execute_query(
                    "SELECT COUNT(*) as count FROM coupon_usage WHERE coupon_id = %s AND customer_id = %s",
                    (coupon['id'], customer_id), fetch=True
                )[0]['count']
                
                if customer_usage >= coupon['usage_limit_per_customer']:
                    continue
            
            applicable_coupons.append(coupon)
        
        return applicable_coupons
        
    except Exception as e:
        return []

# ======================= COUPON STATS =======================

@coupons_bp.route('/coupons/stats', methods=['GET'])
@admin_required
def get_coupons_stats():
    try:
        stats_query = """
        SELECT 
            COUNT(*) as total_coupons,
            SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_coupons,
            SUM(CASE WHEN valid_until IS NOT NULL AND valid_until <= NOW() THEN 1 ELSE 0 END) as expired_coupons,
            SUM(CASE WHEN valid_from > NOW() THEN 1 ELSE 0 END) as upcoming_coupons,
            SUM(used_count) as total_usage
        FROM coupons
        """
        
        stats = Database.execute_query(stats_query, fetch=True)[0]
        
        # Get usage in last 30 days
        recent_usage_query = """
        SELECT COUNT(*) as recent_usage
        FROM coupon_usage
        WHERE usage_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        recent_usage = Database.execute_query(recent_usage_query, fetch=True)[0]['recent_usage']
        stats['recent_usage'] = recent_usage
        
        # Get most popular coupon type
        type_usage_query = """
        SELECT c.type, COUNT(cu.id) as usage_count
        FROM coupons c
        LEFT JOIN coupon_usage cu ON c.id = cu.coupon_id
        WHERE c.is_active = 1
        GROUP BY c.type
        ORDER BY usage_count DESC
        LIMIT 1
        """
        most_popular_type = Database.execute_query(type_usage_query, fetch=True)
        stats['most_popular_type'] = most_popular_type[0]['type'] if most_popular_type else None
        
        return success_response(stats)
        
    except Exception as e:
        return error_response(str(e), 500)