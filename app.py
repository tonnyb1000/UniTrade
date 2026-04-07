from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, abort
)
import pymysql
import pymysql.cursors
import re
import os
import math
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from decimal import Decimal

import config

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['UPLOAD_FOLDER']      = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db():
    """Return a new PyMySQL DictCursor connection."""
    return pymysql.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        charset=config.DB_CHARSET,
        autocommit=False,
    )


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


def save_uploaded_image(file_field_name):
    """Save an uploaded image and return the relative URL, or None."""
    if file_field_name not in request.files:
        return None
    file = request.files[file_field_name]
    if file and file.filename != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return f"uploads/items/{filename}"
    return None


def create_notification(conn, user_id, message, link=None):
    """Insert a notification row (caller must commit the connection)."""
    with conn.cursor() as cur:
        cur.execute(
            'INSERT INTO notifications (user_id, message, link) VALUES (%s, %s, %s)',
            (user_id, message, link)
        )


def get_unread_notification_count(user_id):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*) AS cnt FROM notifications WHERE user_id=%s AND is_read=0',
                (user_id,)
            )
            return cur.fetchone()['cnt']
    except Exception:
        return 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def seller_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        if session.get('mode') != 'seller':
            flash('Switch to Seller mode first.', 'warning')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def buyer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        if session.get('mode') != 'buyer':
            flash('Switch to Buyer mode first.', 'warning')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Context processor – inject vars into every template
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    notif_count = 0
    if session.get('loggedin'):
        notif_count = get_unread_notification_count(session['user_id'])
    return dict(
        notif_count=notif_count,
        categories=config.CATEGORIES,
        conditions=config.CONDITIONS,
    )


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM items WHERE status='available'")
            item_count = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) AS cnt FROM users")
            user_count = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) AS cnt FROM transactions WHERE status='completed'")
            deal_count = cur.fetchone()['cnt']
    finally:
        conn.close()
    return render_template('index.html',
                           item_count=item_count,
                           user_count=user_count,
                           deal_count=deal_count)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username   = request.form['username'].strip()
        email      = request.form['email'].strip()
        password   = request.form['password']
        first_name = request.form['first_name'].strip()
        last_name  = request.form['last_name'].strip()
        university = request.form.get('university', '').strip()
        student_id = request.form.get('student_id', '').strip()
        phone      = request.form.get('phone', '').strip()

        if not all([username, email, password, first_name, last_name]):
            flash('Please fill in all required fields.', 'error')
            return render_template('register.html')

        if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Invalid email address.', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register.html')

        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT id FROM users WHERE username=%s OR email=%s',
                    (username, email)
                )
                if cur.fetchone():
                    flash('Username or email already taken.', 'error')
                    return render_template('register.html')

                cur.execute('''
                    INSERT INTO users
                        (username, email, password, first_name, last_name, university, student_id, phone)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (username, email, generate_password_hash(password),
                      first_name, last_name, university, student_id, phone))
                conn.commit()
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash('An error occurred during registration.', 'error')
            app.logger.error(f"Register error: {e}")
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM users WHERE username=%s', (username,))
                account = cur.fetchone()

            if account and check_password_hash(account['password'], password):
                session.clear()
                session['loggedin']   = True
                session['user_id']    = account['id']
                session['username']   = account['username']
                session['first_name'] = account['first_name']
                session['mode']       = 'buyer'
                session['cart']       = []
                flash(f"Welcome back, {account['first_name']}! 👋", 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Incorrect username or password.', 'error')
        finally:
            conn.close()

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    page      = max(1, request.args.get('page', 1, type=int))
    per_page  = config.ITEMS_PER_PAGE
    offset    = (page - 1) * per_page
    mode      = session.get('mode', 'buyer')

    conn = get_db()
    try:
        with conn.cursor() as cur:
            if mode == 'buyer':
                cur.execute('''
                    SELECT i.*, u.username AS seller_name, u.avg_rating AS seller_rating
                    FROM items i
                    JOIN users u ON i.seller_id = u.id
                    WHERE i.status = 'available' AND i.seller_id != %s
                    ORDER BY i.created_at DESC
                    LIMIT %s OFFSET %s
                ''', (session['user_id'], per_page, offset))
                available_items = cur.fetchall()

                cur.execute('''
                    SELECT COUNT(*) AS cnt FROM items
                    WHERE status='available' AND seller_id != %s
                ''', (session['user_id'],))
                total = cur.fetchone()['cnt']

                # Wishlist IDs for the current user
                cur.execute(
                    'SELECT item_id FROM wishlist WHERE user_id=%s',
                    (session['user_id'],)
                )
                wishlist_ids = {row['item_id'] for row in cur.fetchall()}

                total_pages = math.ceil(total / per_page)
                return render_template('dashboard.html',
                                       available_items=available_items,
                                       user_items=[],
                                       current_mode=mode,
                                       wishlist_ids=wishlist_ids,
                                       page=page,
                                       total_pages=total_pages)
            else:
                cur.execute('''
                    SELECT * FROM items
                    WHERE seller_id = %s
                    ORDER BY created_at DESC
                ''', (session['user_id'],))
                user_items = cur.fetchall()

                return render_template('dashboard.html',
                                       available_items=[],
                                       user_items=user_items,
                                       current_mode=mode,
                                       wishlist_ids=set(),
                                       page=1,
                                       total_pages=1)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Mode switching
# ---------------------------------------------------------------------------

@app.route('/switch_mode/<mode>')
@login_required
def switch_mode(mode):
    if mode in ('buyer', 'seller'):
        session['mode'] = mode
        session.modified = True
        flash(f'Switched to {mode.title()} mode.', 'success')
    return redirect(url_for('dashboard'))


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.route('/search')
@login_required
def search():
    q          = request.args.get('q', '').strip()
    category   = request.args.get('category', '')
    condition  = request.args.get('condition', '')
    min_price  = request.args.get('min_price', '', type=str)
    max_price  = request.args.get('max_price', '', type=str)
    sort       = request.args.get('sort', 'newest')
    page       = max(1, request.args.get('page', 1, type=int))
    per_page   = config.ITEMS_PER_PAGE
    offset     = (page - 1) * per_page

    where  = ["i.status = 'available'", "i.seller_id != %s"]
    params = [session['user_id']]

    if q:
        where.append('(i.title LIKE %s OR i.description LIKE %s)')
        like = f'%{q}%'
        params += [like, like]
    if category:
        where.append('i.category = %s')
        params.append(category)
    if condition:
        where.append('i.item_condition = %s')
        params.append(condition)
    if min_price:
        try:
            where.append('i.price >= %s')
            params.append(float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            where.append('i.price <= %s')
            params.append(float(max_price))
        except ValueError:
            pass

    order_map = {
        'newest':     'i.created_at DESC',
        'price_asc':  'i.price ASC',
        'price_desc': 'i.price DESC',
    }
    order_clause = order_map.get(sort, 'i.created_at DESC')
    where_clause = ' AND '.join(where)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Total count
            cur.execute(
                f'SELECT COUNT(*) AS cnt FROM items i WHERE {where_clause}',
                params
            )
            total = cur.fetchone()['cnt']

            # Paginated results
            cur.execute(f'''
                SELECT i.*, u.username AS seller_name, u.avg_rating AS seller_rating
                FROM items i
                JOIN users u ON i.seller_id = u.id
                WHERE {where_clause}
                ORDER BY {order_clause}
                LIMIT %s OFFSET %s
            ''', params + [per_page, offset])
            items = cur.fetchall()

            cur.execute('SELECT item_id FROM wishlist WHERE user_id=%s', (session['user_id'],))
            wishlist_ids = {row['item_id'] for row in cur.fetchall()}

        total_pages = math.ceil(total / per_page) if total else 1
        return render_template('search_results.html',
                               items=items,
                               q=q,
                               category=category,
                               condition=condition,
                               min_price=min_price,
                               max_price=max_price,
                               sort=sort,
                               page=page,
                               total_pages=total_pages,
                               total=total,
                               wishlist_ids=wishlist_ids)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Item CRUD
# ---------------------------------------------------------------------------

@app.route('/item/<int:item_id>')
@login_required
def item_detail(item_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT i.*, u.username AS seller_name, u.university,
                       u.phone, u.avg_rating AS seller_rating, u.id AS seller_user_id
                FROM items i
                JOIN users u ON i.seller_id = u.id
                WHERE i.id = %s
            ''', (item_id,))
            item = cur.fetchone()

            if not item:
                flash('Item not found.', 'error')
                return redirect(url_for('dashboard'))

            # Increment view count
            cur.execute('UPDATE items SET views = views + 1 WHERE id = %s', (item_id,))
            conn.commit()

            is_seller = (item['seller_id'] == session['user_id'])
            in_cart   = any(c['id'] == item_id for c in session.get('cart', []))

            cur.execute(
                'SELECT 1 FROM wishlist WHERE user_id=%s AND item_id=%s',
                (session['user_id'], item_id)
            )
            in_wishlist = cur.fetchone() is not None

            # Reviews for the seller
            cur.execute('''
                SELECT r.rating, r.comment, r.created_at,
                       u.username AS reviewer_name, u.first_name
                FROM reviews r
                JOIN users u ON r.reviewer_id = u.id
                WHERE r.reviewee_id = %s
                ORDER BY r.created_at DESC
                LIMIT 5
            ''', (item['seller_id'],))
            reviews = cur.fetchall()

            # Has buyer already reviewed seller for any completed transaction on this item?
            can_review = False
            if not is_seller:
                cur.execute('''
                    SELECT t.id FROM transactions t
                    LEFT JOIN reviews r ON r.transaction_id = t.id AND r.reviewer_id = %s
                    WHERE t.item_id = %s AND t.buyer_id = %s AND t.status = 'completed'
                      AND r.id IS NULL
                    LIMIT 1
                ''', (session['user_id'], item_id, session['user_id']))
                can_review = cur.fetchone() is not None

        return render_template('item_detail.html',
                               item=item,
                               is_seller=is_seller,
                               in_cart=in_cart,
                               in_wishlist=in_wishlist,
                               reviews=reviews,
                               can_review=can_review)
    finally:
        conn.close()


@app.route('/add_item', methods=['GET', 'POST'])
@seller_required
def add_item():
    if request.method == 'POST':
        title          = request.form['title'].strip()
        description    = request.form.get('description', '').strip()
        category       = request.form['category']
        price          = request.form['price']
        item_condition = request.form['item_condition']

        if not title or not price:
            flash('Title and price are required.', 'error')
            return render_template('add_item.html')

        try:
            price = float(price)
            if price <= 0:
                raise ValueError
        except ValueError:
            flash('Price must be a positive number.', 'error')
            return render_template('add_item.html')

        image_url = save_uploaded_image('item_image') or 'uploads/items/placeholder.jpg'

        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO items
                        (title, description, category, price, item_condition, image_url, seller_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (title, description, category, price,
                      item_condition, image_url, session['user_id']))
                conn.commit()
            flash('Item listed successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            conn.rollback()
            flash('Error adding item.', 'error')
            app.logger.error(f"add_item error: {e}")
        finally:
            conn.close()

    return render_template('add_item.html')


@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
@seller_required
def edit_item(item_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT * FROM items WHERE id=%s AND seller_id=%s',
                (item_id, session['user_id'])
            )
            item = cur.fetchone()

        if not item:
            flash('Item not found or you do not own it.', 'error')
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            title          = request.form['title'].strip()
            description    = request.form.get('description', '').strip()
            category       = request.form['category']
            price          = request.form['price']
            item_condition = request.form['item_condition']

            try:
                price = float(price)
            except ValueError:
                flash('Invalid price.', 'error')
                return render_template('edit_item.html', item=item)

            image_url = save_uploaded_image('item_image') or item['image_url']

            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE items
                    SET title=%s, description=%s, category=%s, price=%s,
                        item_condition=%s, image_url=%s
                    WHERE id=%s AND seller_id=%s
                ''', (title, description, category, price,
                      item_condition, image_url, item_id, session['user_id']))
                conn.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('dashboard'))

        return render_template('edit_item.html', item=item)
    finally:
        conn.close()


@app.route('/delete_item/<int:item_id>', methods=['POST'])
@seller_required
def delete_item(item_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM items WHERE id=%s AND seller_id=%s AND status='available'",
                (item_id, session['user_id'])
            )
            if cur.fetchone():
                cur.execute('DELETE FROM items WHERE id=%s', (item_id,))
                conn.commit()
                flash('Item deleted.', 'success')
            else:
                flash('Cannot delete this item.', 'error')
    finally:
        conn.close()
    return redirect(url_for('dashboard'))


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

@app.route('/add_to_cart/<int:item_id>', methods=['POST'])
@buyer_required
def add_to_cart(item_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT i.*, u.username AS seller_name
                FROM items i
                JOIN users u ON i.seller_id = u.id
                WHERE i.id=%s AND i.status='available'
            ''', (item_id,))
            item = cur.fetchone()

        if item:
            cart = session.get('cart', [])
            if any(c['id'] == item_id for c in cart):
                flash('Item already in cart.', 'info')
            else:
                cart.append({
                    'id':          item['id'],
                    'title':       item['title'],
                    'price':       float(item['price']),
                    'seller_id':   item['seller_id'],
                    'seller_name': item['seller_name'],   # ← fixed: real name from DB
                    'image_url':   item.get('image_url') or 'uploads/items/placeholder.jpg',
                })
                session['cart'] = cart
                session.modified = True
                flash(f'"{item["title"]}" added to cart!', 'success')
        else:
            flash('Item is not available.', 'error')
    finally:
        conn.close()
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    session['cart'] = [c for c in session.get('cart', []) if c['id'] != item_id]
    session.modified = True
    flash('Item removed from cart.', 'success')
    return redirect(url_for('cart'))


@app.route('/cart')
@login_required
def cart():
    cart_items  = session.get('cart', [])
    total_price = sum(c['price'] for c in cart_items)
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

@app.route('/checkout', methods=['GET', 'POST'])
@buyer_required
def checkout():
    cart_items = session.get('cart', [])
    if not cart_items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('cart'))

    if request.method == 'POST':
        meeting_location = request.form.get('meeting_location', '').strip()
        pickup_location  = request.form.get('pickup_location', '').strip()
        meeting_time_str = request.form.get('meeting_time', '')

        if not meeting_time_str:
            flash('Please select a meeting time.', 'error')
            total_price = sum(c['price'] for c in cart_items)
            return render_template('checkout.html',
                                   cart_items=cart_items, total_price=total_price)

        try:
            meeting_time = datetime.fromisoformat(meeting_time_str)
        except ValueError:
            flash('Invalid meeting time format.', 'error')
            total_price = sum(c['price'] for c in cart_items)
            return render_template('checkout.html',
                                   cart_items=cart_items, total_price=total_price)

        conn = get_db()
        try:
            placed = []
            with conn.cursor() as cur:
                for cart_item in cart_items:
                    cur.execute(
                        "SELECT * FROM items WHERE id=%s AND status='available'",
                        (cart_item['id'],)
                    )
                    db_item = cur.fetchone()
                    if db_item:
                        cur.execute('''
                            INSERT INTO transactions
                                (item_id, buyer_id, seller_id, price,
                                 meeting_location, pickup_location, meeting_time)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ''', (cart_item['id'], session['user_id'],
                              cart_item['seller_id'], cart_item['price'],
                              meeting_location, pickup_location, meeting_time))
                        cur.execute(
                            "UPDATE items SET status='pending' WHERE id=%s",
                            (cart_item['id'],)
                        )
                        placed.append(cart_item)
                        # Notify seller
                        create_notification(
                            conn, cart_item['seller_id'],
                            f"New order for '{cart_item['title']}' from {session['username']}!",
                            link=url_for('my_orders')
                        )
                    else:
                        flash(f'"{cart_item["title"]}" is no longer available.', 'warning')

            conn.commit()
            session['cart'] = []
            session.modified = True
            if placed:
                flash(f'Order placed for {len(placed)} item(s)! Seller(s) will be notified.', 'success')
            return redirect(url_for('my_orders'))

        except Exception as e:
            conn.rollback()
            flash('Checkout error. Please try again.', 'error')
            app.logger.error(f"Checkout error: {e}")
        finally:
            conn.close()

    total_price = sum(c['price'] for c in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total_price=total_price)


@app.route('/buy_now/<int:item_id>', methods=['POST'])
@buyer_required
def buy_now(item_id):
    """Clears cart, adds single item, redirects to checkout."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT i.*, u.username AS seller_name
                FROM items i JOIN users u ON i.seller_id = u.id
                WHERE i.id=%s AND i.status='available'
            ''', (item_id,))
            item = cur.fetchone()
        if item:
            session['cart'] = [{
                'id':          item['id'],
                'title':       item['title'],
                'price':       float(item['price']),
                'seller_id':   item['seller_id'],
                'seller_name': item['seller_name'],
                'image_url':   item.get('image_url') or 'uploads/items/placeholder.jpg',
            }]
            session.modified = True
            return redirect(url_for('checkout'))
        else:
            flash('Item is not available.', 'error')
            return redirect(url_for('dashboard'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@app.route('/my_orders')
@login_required
def my_orders():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT t.*, i.title, i.image_url, i.category, i.item_condition,
                       u.username AS seller_name
                FROM transactions t
                JOIN items i ON t.item_id = i.id
                JOIN users u ON t.seller_id = u.id
                WHERE t.buyer_id = %s
                ORDER BY t.created_at DESC
            ''', (session['user_id'],))
            buyer_orders = cur.fetchall()

            cur.execute('''
                SELECT t.*, i.title, i.image_url, i.category, i.item_condition,
                       u.username AS buyer_name
                FROM transactions t
                JOIN items i ON t.item_id = i.id
                JOIN users u ON t.buyer_id = u.id
                WHERE t.seller_id = %s
                ORDER BY t.created_at DESC
            ''', (session['user_id'],))
            seller_orders = cur.fetchall()

        return render_template('my_orders.html',
                               buyer_orders=buyer_orders,
                               seller_orders=seller_orders)
    finally:
        conn.close()


@app.route('/update_order_status/<int:transaction_id>/<status>', methods=['POST'])
@login_required
def update_order_status(transaction_id, status):
    allowed = ('accepted', 'completed', 'cancelled')
    if status not in allowed:
        abort(400)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Sellers can accept / complete / cancel
            cur.execute(
                'SELECT * FROM transactions WHERE id=%s AND seller_id=%s',
                (transaction_id, session['user_id'])
            )
            txn = cur.fetchone()

            if not txn:
                # Buyers may only cancel pending orders
                if status != 'cancelled':
                    flash('Unauthorized.', 'error')
                    return redirect(url_for('my_orders'))
                cur.execute(
                    "SELECT * FROM transactions WHERE id=%s AND buyer_id=%s AND status='pending'",
                    (transaction_id, session['user_id'])
                )
                txn = cur.fetchone()
                if not txn:
                    flash('Cannot update this order.', 'error')
                    return redirect(url_for('my_orders'))

            cur.execute(
                'UPDATE transactions SET status=%s WHERE id=%s',
                (status, transaction_id)
            )

            if status == 'completed':
                cur.execute(
                    "UPDATE items SET status='sold' WHERE id=%s",
                    (txn['item_id'],)
                )
                # Update seller avg_rating
                notify_uid = txn['buyer_id']
                msg = f"Your order has been marked as completed. Please leave a review!"
            elif status == 'cancelled':
                cur.execute(
                    "UPDATE items SET status='available' WHERE id=%s",
                    (txn['item_id'],)
                )
                notify_uid = txn['buyer_id'] if txn['seller_id'] == session['user_id'] \
                    else txn['seller_id']
                msg = f"Order for '{txn['item_id']}' was cancelled."
            elif status == 'accepted':
                notify_uid = txn['buyer_id']
                msg = "Your order has been accepted by the seller!"

            create_notification(conn, notify_uid, msg, link=url_for('my_orders'))
            conn.commit()
            flash(f'Order {status}.', 'success')
    except Exception as e:
        conn.rollback()
        flash('Error updating order.', 'error')
        app.logger.error(f"update_order_status error: {e}")
    finally:
        conn.close()
    return redirect(url_for('my_orders'))


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------

@app.route('/wishlist')
@login_required
def wishlist():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT i.*, u.username AS seller_name, w.created_at AS wished_at
                FROM wishlist w
                JOIN items i ON w.item_id = i.id
                JOIN users u ON i.seller_id = u.id
                WHERE w.user_id = %s
                ORDER BY w.created_at DESC
            ''', (session['user_id'],))
            items = cur.fetchall()
        return render_template('wishlist.html', items=items)
    finally:
        conn.close()


@app.route('/wishlist/toggle/<int:item_id>', methods=['POST'])
@login_required
def wishlist_toggle(item_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id FROM wishlist WHERE user_id=%s AND item_id=%s',
                (session['user_id'], item_id)
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    'DELETE FROM wishlist WHERE user_id=%s AND item_id=%s',
                    (session['user_id'], item_id)
                )
                conn.commit()
                flash('Removed from wishlist.', 'success')
            else:
                cur.execute(
                    'INSERT INTO wishlist (user_id, item_id) VALUES (%s, %s)',
                    (session['user_id'], item_id)
                )
                conn.commit()
                flash('Added to wishlist! ❤️', 'success')
    finally:
        conn.close()
    return redirect(request.referrer or url_for('dashboard'))


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@app.route('/profile')
@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id=None):
    if user_id is None:
        user_id = session['user_id']

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE id=%s', (user_id,))
            user = cur.fetchone()
            if not user:
                flash('User not found.', 'error')
                return redirect(url_for('dashboard'))

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM items WHERE seller_id=%s AND status='available'",
                (user_id,)
            )
            active_listings = cur.fetchone()['cnt']

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM transactions WHERE seller_id=%s AND status='completed'",
                (user_id,)
            )
            total_sales = cur.fetchone()['cnt']

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM transactions WHERE buyer_id=%s",
                (user_id,)
            )
            total_purchases = cur.fetchone()['cnt']

            cur.execute('''
                SELECT r.rating, r.comment, r.created_at, u.username AS reviewer_name
                FROM reviews r
                JOIN users u ON r.reviewer_id = u.id
                WHERE r.reviewee_id = %s
                ORDER BY r.created_at DESC
                LIMIT 10
            ''', (user_id,))
            reviews = cur.fetchall()

            cur.execute(
                "SELECT * FROM items WHERE seller_id=%s AND status='available' ORDER BY created_at DESC LIMIT 6",
                (user_id,)
            )
            recent_items = cur.fetchall()

        is_own = (user_id == session['user_id'])
        return render_template('profile.html',
                               user=user,
                               is_own=is_own,
                               active_listings=active_listings,
                               total_sales=total_sales,
                               total_purchases=total_purchases,
                               reviews=reviews,
                               recent_items=recent_items)
    finally:
        conn.close()


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE id=%s', (session['user_id'],))
            user = cur.fetchone()

        if request.method == 'POST':
            first_name = request.form['first_name'].strip()
            last_name  = request.form['last_name'].strip()
            university = request.form.get('university', '').strip()
            student_id = request.form.get('student_id', '').strip()
            phone      = request.form.get('phone', '').strip()
            bio        = request.form.get('bio', '').strip()

            profile_pic = save_uploaded_image('profile_pic') or user.get('profile_pic')

            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE users
                    SET first_name=%s, last_name=%s, university=%s,
                        student_id=%s, phone=%s, bio=%s, profile_pic=%s
                    WHERE id=%s
                ''', (first_name, last_name, university,
                      student_id, phone, bio, profile_pic, session['user_id']))
                conn.commit()
            session['first_name'] = first_name
            flash('Profile updated!', 'success')
            return redirect(url_for('profile'))

        return render_template('edit_profile.html', user=user)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

@app.route('/review/<int:transaction_id>', methods=['POST'])
@login_required
def submit_review(transaction_id):
    rating  = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()

    if not rating or not (1 <= rating <= 5):
        flash('Please select a rating from 1-5.', 'error')
        return redirect(request.referrer or url_for('my_orders'))

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM transactions WHERE id=%s AND status='completed'",
                (transaction_id,)
            )
            txn = cur.fetchone()
            if not txn:
                flash('Transaction not found or not completed.', 'error')
                return redirect(url_for('my_orders'))

            # Determine who is being reviewed
            if txn['buyer_id'] == session['user_id']:
                reviewee_id = txn['seller_id']
            elif txn['seller_id'] == session['user_id']:
                reviewee_id = txn['buyer_id']
            else:
                flash('Unauthorized.', 'error')
                return redirect(url_for('my_orders'))

            # Prevent duplicate reviews
            cur.execute(
                'SELECT id FROM reviews WHERE transaction_id=%s AND reviewer_id=%s',
                (transaction_id, session['user_id'])
            )
            if cur.fetchone():
                flash('You have already reviewed this transaction.', 'info')
                return redirect(url_for('my_orders'))

            cur.execute('''
                INSERT INTO reviews (transaction_id, reviewer_id, reviewee_id, rating, comment)
                VALUES (%s, %s, %s, %s, %s)
            ''', (transaction_id, session['user_id'], reviewee_id, rating, comment))

            # Recalculate reviewee's average rating
            cur.execute(
                'SELECT AVG(rating) AS avg_r FROM reviews WHERE reviewee_id=%s',
                (reviewee_id,)
            )
            avg = cur.fetchone()['avg_r'] or 0
            cur.execute(
                'UPDATE users SET avg_rating=%s WHERE id=%s',
                (round(avg, 2), reviewee_id)
            )

            create_notification(conn, reviewee_id,
                                f"{session['username']} left you a {rating}⭐ review!",
                                link=url_for('profile', user_id=reviewee_id))
            conn.commit()
            flash('Review submitted! Thank you.', 'success')
    except Exception as e:
        conn.rollback()
        flash('Error submitting review.', 'error')
        app.logger.error(f"submit_review error: {e}")
    finally:
        conn.close()
    return redirect(url_for('my_orders'))


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@app.route('/notifications')
@login_required
def notifications():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT * FROM notifications
                WHERE user_id=%s
                ORDER BY created_at DESC
                LIMIT 50
            ''', (session['user_id'],))
            notifs = cur.fetchall()
            # Mark all as read
            cur.execute(
                'UPDATE notifications SET is_read=1 WHERE user_id=%s',
                (session['user_id'],)
            )
            conn.commit()
        return render_template('notifications.html', notifications=notifs)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API – Dashboard stats
# ---------------------------------------------------------------------------

@app.route('/api/stats')
@login_required
def api_stats():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM items WHERE seller_id=%s AND status='available'",
                (session['user_id'],)
            )
            active = cur.fetchone()['cnt']

            cur.execute(
                "SELECT COALESCE(SUM(price),0) AS total FROM transactions WHERE seller_id=%s AND status='completed'",
                (session['user_id'],)
            )
            earnings = float(cur.fetchone()['total'])

            cur.execute(
                'SELECT COUNT(*) AS cnt FROM transactions WHERE buyer_id=%s',
                (session['user_id'],)
            )
            purchases = cur.fetchone()['cnt']

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM transactions WHERE (buyer_id=%s OR seller_id=%s) AND status='pending'",
                (session['user_id'], session['user_id'])
            )
            pending = cur.fetchone()['cnt']

        return jsonify(active_listings=active, total_earnings=earnings,
                       purchases_made=purchases, pending_transactions=pending)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True)
