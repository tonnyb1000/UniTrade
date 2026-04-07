import os

# Flask configuration
SECRET_KEY = os.environ.get('SECRET_KEY', 'unitrade-secret-key-2026-change-in-production')

# Database configuration – update these values or set environment variables
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')   # ← Set your MySQL password here
DB_NAME = os.environ.get('DB_NAME', 'unitrade_db')
DB_CHARSET = 'utf8mb4'

# File upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'items')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

# Pagination
ITEMS_PER_PAGE = 12

# Categories
CATEGORIES = [
    'Textbooks',
    'Electronics',
    'Furniture',
    'Clothing',
    'Sports & Fitness',
    'Stationery',
    'Others',
]

# Item conditions
CONDITIONS = [
    ('new', 'New'),
    ('like_new', 'Like New'),
    ('good', 'Good'),
    ('fair', 'Fair'),
]
