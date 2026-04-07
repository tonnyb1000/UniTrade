# 🎓 UniTrade – University Campus Marketplace

A modern peer-to-peer trading platform for university students, rebuilt with improved functionality, security, and design.

## ✨ What's New in This Version

| Feature | v0.01 | v1.0 (This) |
|---------|-------|-------------|
| DB credentials | Hardcoded | `config.py` / env vars |
| Seller name in cart | Always "Unknown" | Fetched from DB ✅ |
| Cart/delete mutations | GET requests (insecure) | POST forms ✅ |
| Search & filter | None | Keyword + Category + Condition + Price ✅ |
| Wishlist | None | Full add/remove ✅ |
| Reviews & ratings | None | Post-transaction star ratings ✅ |
| Notifications | None | Real-time bell with count badge ✅ |
| User profile | None | Full profile + edit ✅ |
| Pagination | None | 12 items/page ✅ |
| Auth decorator | Repeated `if 'loggedin'` checks | `@login_required` ✅ |
| UI Theme | Bootstrap light | Dark mode, Inter font ✅ |
| DB schema | `image_url` missing from SQL | All columns present ✅ |

## 🚀 Quick Start

### 1. Set your database password

Edit `config.py` and set your MySQL password:
```python
DB_PASSWORD = 'your_password_here'
```

### 2. Set up the database

```sql
-- In MySQL / phpMyAdmin / CLI:
source E:/UniTrade/UniTrade/database_setup.sql
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create uploads directory

```bash
mkdir -p static/uploads/items
```

### 5. Run the app

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

## 📁 Project Structure

```
UniTrade/
├── app.py                   # Flask app – all routes
├── config.py                # Config (DB creds, upload settings)
├── requirements.txt
├── database_setup.sql       # 6-table schema
├── templates/
│   ├── base.html            # Dark theme base
│   ├── index.html           # Landing page
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html       # Buyer/seller dashboard
│   ├── item_detail.html     # Item page + reviews
│   ├── add_item.html
│   ├── edit_item.html
│   ├── cart.html
│   ├── checkout.html
│   ├── my_orders.html       # Buy/sell tabs + review form
│   ├── search_results.html  # Search + filters
│   ├── wishlist.html
│   ├── profile.html
│   ├── edit_profile.html
│   └── notifications.html
└── static/
    └── uploads/
        └── items/           # Uploaded item images
```

## 🗃️ Database Schema (6 Tables)

- **users** – username, email, password (hashed), university, rating
- **items** – title, description, category, price, condition, `image_url`, status, views
- **transactions** – buyer/seller/item FKs, meeting details, status (ENUM)
- **reviews** – one per transaction direction, 1-5 stars + comment
- **wishlist** – user × item pairs
- **notifications** – messages with read status

## 🔒 Security

- Werkzeug password hashing
- Parameterized SQL queries (no injection)
- `@login_required`, `@seller_required`, `@buyer_required` decorators
- POST-based state mutations (no GET-based deletes)
- Ownership checks on edit/delete/review actions

## 💱 Currency

All prices are in **UGX (Ugandan Shillings)**.
