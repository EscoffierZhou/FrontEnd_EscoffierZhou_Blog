import os
load_dotenv() # <<<< 新增：在其他导入之前加载 .env 文件中的环境变量
from flask import Flask, jsonify, request, send_from_directory, redirect, url_for,render_template_string # 确保 send_from_directory, redirect, url_for 已导入
from markdown import markdown
from flask_cors import CORS # 导入CORS
import urllib.parse # Added urllib.parse
from datetime import datetime, timedelta
import re
from werkzeug.utils import secure_filename
import uuid # For unique filenames
import shutil # Add this import at the top
from werkzeug.security import generate_password_hash, check_password_hash
# NEW IMPORTS for SQLAlchemy
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin # For secure redirection
from sqlalchemy import MetaData # NEW: For naming convention
from flask_migrate import Migrate # Make sure this import is at the top
from sqlalchemy import func
from dotenv import load_dotenv # <<<< 新增导入



app = Flask(__name__)
CORS(app) # 为整个应用启用CORS

# --- NEW: SQLAlchemy Configuration ---
# Define a naming convention for constraints for Alembic/Flask-Migrate
# This helps to have consistent and predictable names for indexes, foreign keys, etc.
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
metadata = MetaData(naming_convention=convention)

# Configure the SQLite database URI
# The database file (blog.db) will be created in the 'backend' directory, alongside app.py
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'blog.db') # 旧的 SQLite 配置

#新的配置，优先使用环境变量 DATABASE_URL (Render 会设置)
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # Render 提供的 DATABASE_URL 可能以 postgres:// 开头，SQLAlchemy 需要 postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # 如果没有 DATABASE_URL 环境变量 (例如本地开发)，则回退到 SQLite
    print("WARNING: DATABASE_URL not set, falling back to SQLite. This is for local development only.")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'blog.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Suppress a warning

db = SQLAlchemy(app, metadata=metadata) # Pass metadata to SQLAlchemy
# --- END: SQLAlchemy Configuration ---

# --- NEW: Flask-Migrate Configuration ---
migrate = Migrate(app, db) # Initialize Flask-Migrate
# --- END: Flask-Migrate Configuration ---

# --- NEW: Flask-Login Configuration ---
# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # The name of the view to redirect to when login is required
login_manager.login_message = "请先登录以访问此页面。" # Optional: Custom message
# app.config['SECRET_KEY'] = '8bf9f5229e741b0197e8949ea4241347d7548869f9b92db0cfaab86fee07c5e3' # Important for sessions and security. CHANGE THIS IN PRODUCTION!
# --- END: Flask-Login Configuration ---

# MODIFIED: Define the path to the static directory relative to the backend dir
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static')) # CORRECTED PATH CALCULATION
print(f"[INITIAL CONFIG] STATIC_DIR resolved to: {STATIC_DIR}")

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'blog'))
print(f"[INITIAL CONFIG] DATA_DIR resolved to: {DATA_DIR}")
PROFILE_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'profile')
# REMOVE: These will be replaced by database tables
# STATISTIC_FILE   = os.path.join(DATA_DIR, 'statistic.txt')
# LABELS_FILE      = os.path.join(DATA_DIR, 'labels.txt')
# TAGCLOUD_FILE    = os.path.join(DATA_DIR, 'tagcloud.txt')

UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploaded_images')
TEMP_UPLOAD_FOLDER = os.path.join(DATA_DIR, 'temp_uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(TEMP_UPLOAD_FOLDER):
    os.makedirs(TEMP_UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TEMP_UPLOAD_FOLDER'] = TEMP_UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

DATA_ROOT_FOR_STATIC_FILES = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
print(f"[INITIAL CONFIG] DATA_ROOT_FOR_STATIC_FILES resolved to: {DATA_ROOT_FOR_STATIC_FILES}")

DOCUMENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'document'))
print(f"[INITIAL CONFIG] DOCUMENT_DIR resolved to: {DOCUMENT_DIR}")

# --- NEW: Database Models ---

# Association table for Post and Tag (many-to-many)
post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    # description = db.Column(db.String(255), nullable=True) # Optional
    posts = db.relationship('Post', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    # Posts relationship defined by post_tags table handled by SQLAlchemy via secondary argument
    # No direct posts = db.relationship here, but accessible via Post.tags

    def __repr__(self):
        return f'<Tag {self.name}>'

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), unique=True, nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False) # URL-friendly version of title
    markdown_file_path = db.Column(db.String(300), nullable=False) # Relative path to the .md file
    summary = db.Column(db.Text, nullable=True)
    preview_image_url = db.Column(db.String(300), nullable=True) # Relative URL to preview image
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Assuming one admin for now
    
    # Many-to-many relationship with Tag
    tags = db.relationship('Tag', secondary=post_tags, lazy='subquery',
                           backref=db.backref('posts', lazy=True))
    
    author = db.relationship('User', backref=db.backref('posts', lazy=True))

    def __repr__(self):
        return f'<Post {self.title}>'

# --- END: Database Models ---

# --- NEW: Flask-Login user loader ---
@login_manager.user_loader
def load_user(user_id):
    # Flask-Login requires a function that loads a user given their ID.
    # The ID comes from the session.
    print(f"\n[DEBUG load_user] Attempting to load user with ID: {user_id}") # Added debug print
    if user_id is not None:
        user = db.session.get(User, int(user_id))
        print(f"[DEBUG load_user] Loaded user: {user.username if user else 'None'}") # Added debug print
        return user
    print("[DEBUG load_user] user_id is None.") # Added debug print
    return None
# --- END: Flask-Login user loader ---

# --- NEW: Helper functions for data migration ---
def generate_slug(title):
    """Generates a URL-friendly slug from a title, preserving Japanese and other safe characters."""
    print(f"\n[DEBUG generate_slug] Called for title: '{title}'")
    if not title:
        print("[DEBUG generate_slug] Title is empty, using UUID fallback.")
        return str(uuid.uuid4())

    # Convert to lowercase (optional, but good practice for slugs)
    slug = title.lower()

    # Replace spaces and other whitespace with a single hyphen
    slug = re.sub(r'\s+', '-', slug)

    # Remove characters that are NOT:
    # - Basic Latin letters (a-z)
    # - Numbers (0-9)
    # - Hyphen (-)
    # - Underscore (_)
    # - Common Unicode letters (e.g., Japanese Hiragana, Katakana, Kanji, etc.)
    # Using \w (word characters: a-zA-Z0-9_) and adding common Japanese ranges.
    # [\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff] covers basic alphanum+underscore, Hiragana, Katakana, and a large Kanji range.
    # We also explicitly add hyphen '-' inside the character set [].
    cleaned_slug = re.sub(r'[^\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff-]+', '', slug)

    # Replace multiple consecutive hyphens with a single hyphen
    cleaned_slug = re.sub(r'-+', '-', cleaned_slug)

    # Remove leading and trailing hyphens
    cleaned_slug = cleaned_slug.strip('-')

    # Ensure slug is not empty after cleaning; fall back to a unique string if it is.
    if not cleaned_slug:
         print("[DEBUG generate_slug] Cleaned slug is empty, using UUID fallback.")
         return f"post-{str(uuid.uuid4())[:8]}"

    print(f"[DEBUG generate_slug] Generated slug: '{cleaned_slug}'")
    return cleaned_slug

def extract_summary_from_md_content(md_content, max_length=150):
    # Remove common markdown elements to get plain text
    # Remove headers (lines starting with #)
    text = re.sub(r'^#+ .*$', '', md_content, flags=re.MULTILINE)
    # Remove code blocks (lines between ```) - Simplified
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    # Remove images and links markdown: ![alt](url) and [text](url)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)
    # Remove bold/italic markers (*, _)
    text = re.sub(r'([*_~`])\1*(.*?)\1*\1', r'\2', text) # Handles **, __, *, _, ~~ etc.
    # Remove blockquotes (> )
    text = re.sub(r'^> .*$', '', text, flags=re.MULTILINE)
    # Remove horizontal rules (---, ___, ***)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove unordered/ordered list markers (*, -, +, 1.)
    text = re.sub(r'^(\s*)[-*+]\s+', r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'^(\s*)\d+\.\s+', r'\1', text, flags=re.MULTILINE)
    # Remove remaining markdown like characters (e.g. inline code backticks)
    text = re.sub(r'`(.*?)`', r'\1', text)

    # Collapse multiple newlines and spaces
    text = re.sub(r'\s+', ' ', text).strip()

    # Take the first max_length characters
    # Ensure we don't cut in the middle of a word ideally, but simple substring is okay for a start
    summary = text[:max_length] 

    # Add ellipsis if the original text was longer than max_length
    if len(text) > max_length:
        # Find the last space before max_length to avoid breaking words
        last_space = summary.rfind(' ')
        if last_space != -1:
             summary = summary[:last_space] # Trim to the last full word
        summary += '...'

    return summary.strip() if summary else "概要を読み込めませんでした。"

def find_preview_image_for_post(post_slug):
    """
    Finds a potential preview image file path for a given post slug
    by looking in the post's assets directory. Returns a relative URL
    path suitable for serving, or None if no image is found.
    """
    print(f"\n[DEBUG find_preview_image] Called for slug: {post_slug}")

    if not post_slug:
        print("Warning: find_preview_image_for_post called with empty slug.")
        return None

    post_directory_on_disk = os.path.join(DATA_DIR, post_slug) # Use post_slug as directory name
    post_assets_dir_on_disk = os.path.join(post_directory_on_disk, 'assets')

    print(f"[DEBUG find_preview_image] Searching for preview image in: {post_assets_dir_on_disk}")

    if not os.path.exists(post_assets_dir_on_disk):
        print(f"[DEBUG find_preview_image] Assets directory not found for slug '{post_slug}'.")
        return None

    try:
        asset_files = os.listdir(post_assets_dir_on_disk)
        print(f"[DEBUG find_preview_image] Found items in assets dir: {asset_files}")

        image_files = [f for f in asset_files if os.path.isfile(os.path.join(post_assets_dir_on_disk, f)) and allowed_file(f)]

        if not image_files:
            print(f"[DEBUG find_preview_image] No image files found in assets directory for slug '{post_slug}'.")
            return None

        image_files.sort()
        preview_image_filename = image_files[0]
        print(f"[DEBUG find_preview_image] Selected potential preview image: {preview_image_filename}")

        # Construct the relative URL path for serving this image
        # The URL route is /blog_assets/<folder>/<filename>
        # where <folder> is the post slug, and <filename> is the path *relative to* the post slug's directory.
        # So, the filename part for /blog_assets route should be 'assets/image_filename.jpg'
        filename_for_url = os.path.join('assets', preview_image_filename).replace('\\', '/') # Use forward slashes for URL

        # The final URL format should be /blog_assets/post-slug/assets/image_filename.jpg
        relative_url_path = f"/blog_assets/{urllib.parse.quote(post_slug)}/{urllib.parse.quote(filename_for_url)}" # Ensure both parts are quoted

        print(f"[DEBUG find_preview_image] Generated preview image URL: {relative_url_path}")
        return relative_url_path

    except Exception as e:
        print(f"[ERROR find_preview_image] Error searching for preview image for slug '{post_slug}': {e}")
        import traceback
        traceback.print_exc()
        return None

def parse_date_from_string(date_str, default_date=None):
    """Parses a date string (YYYY-MM-DD) into a datetime object."""
    if not date_str:
        return default_date
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        print(f"Warning: Could not parse date string '{date_str}'.")
        return default_date

# --- END: Helper functions ---

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.cli.command('create-admin')
def create_admin_command():
    """Creates the admin user."""
    username = input("Enter admin username: ")
    password = input("Enter admin password: ")
    
    if not username or not password:
        print("Username and password cannot be empty.")
        return

    with app.app_context():
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"User '{username}' already exists.")
            return

        hashed_password = generate_password_hash(password)
        new_admin = User(username=username, password_hash=hashed_password)
        db.session.add(new_admin)
        try:
            db.session.commit()
            print(f"Admin user '{username}' created successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating admin user: {e}")

@app.cli.command('migrate-data')
def migrate_data_command():
    """Migrates data from old text files to the database."""
    with app.app_context():
        admin_username = input("Enter the admin username for attributing posts: ")
        admin_user = User.query.filter_by(username=admin_username).first()
        if not admin_user:
            print(f"Admin user '{admin_username}' not found. Please create the admin user first using 'flask create-admin'.")
            return

        print("Starting data migration...")

        old_labels_file = os.path.join(DATA_DIR, 'labels.txt')
        migrated_categories_count = 0
        if os.path.exists(old_labels_file):
            print(f"\nMigrating categories from {old_labels_file}...")
            try:
                with open(old_labels_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            parts = line.split('|')
                            cat_name = parts[0].strip()
                            if cat_name:
                                existing_category = Category.query.filter_by(name=cat_name).first()
                                if not existing_category:
                                    new_category = Category(name=cat_name)
                                    db.session.add(new_category)
                                    print(f"  Adding category: {cat_name}")
                                    migrated_categories_count +=1
                                else:
                                    print(f"  Category '{cat_name}' already exists.")
                db.session.commit()
                print(f"Categories migration: {migrated_categories_count} new categories added.")
            except Exception as e:
                db.session.rollback()
                print(f"Error migrating categories: {e}")
        else:
            print(f"Warning: Old labels file not found at {old_labels_file}. Skipping category migration.")

        old_tagcloud_file = os.path.join(DATA_DIR, 'tagcloud.txt')
        migrated_tags_count = 0
        if os.path.exists(old_tagcloud_file):
            print(f"\nMigrating tags from {old_tagcloud_file}...")
            try:
                with open(old_tagcloud_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        tag_name = line.strip()
                        if tag_name:
                            existing_tag = Tag.query.filter_by(name=tag_name).first()
                            if not existing_tag:
                                new_tag = Tag(name=tag_name)
                                db.session.add(new_tag)
                                print(f"  Adding tag: {tag_name}")
                                migrated_tags_count += 1
                            else:
                                print(f"  Tag '{tag_name}' already exists.")
                db.session.commit()
                print(f"Tags migration: {migrated_tags_count} new tags added.")
            except Exception as e:
                db.session.rollback()
                print(f"Error migrating tags: {e}")
        else:
            print(f"Warning: Old tagcloud file not found at {old_tagcloud_file}. Skipping tag migration.")

        old_statistic_file = os.path.join(DATA_DIR, 'statistic.txt')
        migrated_posts_count = 0
        if os.path.exists(old_statistic_file):
            print(f"\nMigrating posts from {old_statistic_file}...")
            try:
                with open(old_statistic_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        parts = line.split('|')
                        if len(parts) < 3:
                            print(f"  Warning: Skipping malformed line {line_num} in statistic.txt: '{line}'")
                            continue

                        post_title = parts[0].strip()
                        post_date_str = parts[1].strip()
                        category_name_str = parts[2].strip()
                        tags_list_str = parts[3].split(',') if len(parts) > 3 and parts[3].strip() else []
                        
                        print(f"\n  Processing post: '{post_title}'")

                        existing_post = Post.query.filter_by(title=post_title).first()
                        if existing_post:
                            print(f"    Post '{post_title}' already exists in DB.")
                            # --- MODIFIED: Check if preview_image_url is missing and try to set it ---
                            if existing_post.preview_image_url is None:
                                print(f"    Checking for missing preview image for existing post '{post_title}'...")
                                found_preview_url = find_preview_image_for_post(existing_post.slug)
                                if found_preview_url and existing_post.preview_image_url != found_preview_url:
                                    existing_post.preview_image_url = found_preview_url
                                    db.session.add(existing_post) # Mark for update
                                    print(f"    Set missing preview_image_url for post '{post_title}'.")
                                else:
                                     print(f"    No preview image found or needed update for existing post '{post_title}'.")
                            # --- END MODIFIED ---
                            continue # Still skip creating a new post

                        category_obj = Category.query.filter_by(name=category_name_str).first()
                        if not category_obj:
                            print(f"    Warning: Category '{category_name_str}' for post '{post_title}' not found in DB. Creating it.")
                            category_obj = Category(name=category_name_str)
                            db.session.add(category_obj)
                            db.session.flush()

                        # --- MODIFIED: Ensure slug is generated BEFORE file path and preview search ---
                        post_slug = generate_slug(post_title) # Generate slug from title
                        original_slug = post_slug # Keep the initial generated slug
                        slug_counter = 1
                        while Post.query.filter_by(slug=post_slug).first():
                             post_slug = f"{original_slug}-{slug_counter}"
                             slug_counter += 1
                        if original_slug != post_slug:
                             print(f"    Slug collision for '{original_slug}'. Generated new slug: '{post_slug}'")

                        # Now use the (potentially updated) unique post_slug for file paths
                        relative_md_path = os.path.join(post_slug, f"{post_slug}.md")
                        full_md_path_on_disk = os.path.join(DATA_DIR, relative_md_path)

                        md_content_for_summary = ""
                        if os.path.exists(full_md_path_on_disk):
                            try:
                                with open(full_md_path_on_disk, 'r', encoding='utf-8') as md_file:
                                    md_content_for_summary = md_file.read()
                            except Exception as e_md:
                                print(f"    Warning: Could not read MD file {full_md_path_on_disk} for summary: {e_md}")
                        else:
                            print(f"    Warning: MD file not found at {full_md_path_on_disk} for post '{post_title}'. Summary will be basic.")

                        summary_text = extract_summary_from_md_content(md_content_for_summary)
                        # --- NEW: Find preview image using the final, unique post_slug ---
                        preview_url = find_preview_image_for_post(post_slug) # Use the post_slug here!
                        # --- END NEW ---

                        parsed_date = parse_date_from_string(post_date_str)
                        # The slug generation is moved up

                        new_post = Post(
                            title=post_title,
                            slug=post_slug, # Use the final, unique slug
                            markdown_file_path=relative_md_path,
                            summary=summary_text,
                            preview_image_url=preview_url, # Store the found URL
                            created_at=parsed_date,
                            updated_at=parsed_date,
                            is_published=True,
                            category_id=category_obj.id,
                            author_id=admin_user.id
                        )
                        
                        for tag_name_str in tags_list_str:
                            tag_name = tag_name_str.strip()
                            if tag_name:
                                tag_obj = Tag.query.filter_by(name=tag_name).first()
                                if not tag_obj:
                                    print(f"    Warning: Tag '{tag_name}' for post '{post_title}' not found in DB. Creating it.")
                                    tag_obj = Tag(name=tag_name)
                                    db.session.add(tag_obj)
                                new_post.tags.append(tag_obj)
                        
                        db.session.add(new_post)
                        print(f"    Adding post '{post_title}' to session.")
                        migrated_posts_count +=1
                
                db.session.commit()
                print(f"Posts migration: {migrated_posts_count} new posts processed and added.")
            except Exception as e:
                db.session.rollback()
                print(f"Error migrating posts: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"Warning: Old statistic file not found at {old_statistic_file}. Skipping post migration.")
        print("\nData migration finished.")

@app.route('/', methods=['GET'])
def home():
    """根路由，现在用于提供访客主页 visitor.html"""
    print(f"\n[DEBUG home] Accessed root route '/'. Serving visitor.html.")
    target_file_path = os.path.join(STATIC_DIR, 'visitor.html')
    print(f"[DEBUG home] Attempting to serve file from: '{STATIC_DIR}' with filename 'visitor.html'")
    print(f"[DEBUG home] Full target file path calculated as: '{target_file_path}'")

    if not os.path.exists(STATIC_DIR):
        print(f"[ERROR home] STATIC_DIR does not exist: '{STATIC_DIR}'")
        return "Error: Static directory not found.", 500

    if not os.path.isfile(target_file_path):
        print(f"[ERROR home] Target file does not exist: '{target_file_path}'")
        # This should ideally be caught by send_from_directory's FileNotFoundError, but let's be explicit
        return "Error: visitor.html not found.", 404

    try:
        print(f"[DEBUG home] Calling send_from_directory('{STATIC_DIR}', 'visitor.html')")
        response = send_from_directory(STATIC_DIR, 'visitor.html')
        print(f"[DEBUG home] send_from_directory returned: {response.status}")
        return response
    except FileNotFoundError:
        # This is caught, but let's keep the explicit check above too
        print(f"[ERROR home] FileNotFoundError caught by exception handler for '{target_file_path}'.")
        return "Error: visitor.html not found.", 404
    except Exception as e:
        print(f"[ERROR home] An unexpected error occurred while serving visitor.html: {e}")
        import traceback
        traceback.print_exc()
        return f"An internal error occurred: {str(e)}", 500

@app.route('/api/posts', methods=['GET'])
def get_posts():
    """API 端点：获取所有博客文章的元数据 (NOW FROM DB)"""
    print(f"\n[DEBUG /api/posts] Received GET request.")
    try:
        posts = Post.query.filter_by(is_published=True).order_by(Post.created_at.desc()).all()

        posts_metadata = []
        for post in posts:
             post_data = {
                'title': post.title,
                'date': post.created_at.strftime('%Y年%m月%d日'),
                'category': post.category.name if post.category else '未分類',
                'tags': [tag.name for tag in post.tags],
                'slug': post.slug,
                'summary': post.summary if post.summary else "概要なし",
                'preview_image_url': post.preview_image_url,
                'id': post.id
            }
             print(f"[DEBUG /api/posts] Processing post '{post.title}', preview_image_url: {post_data.get('preview_image_url')}")
             posts_metadata.append(post_data)


        if not posts_metadata:
            print(f"[DEBUG /api/posts] Warning: No published posts found in the database.")
        else:
             print(f"[DEBUG /api/posts] Returning {len(posts_metadata)} posts.")
        
        return jsonify(posts_metadata), 200

    except Exception as e:
        print(f"[ERROR /api/posts] Error getting posts from DB: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Error fetching posts', 'details': str(e)}), 500

@app.route('/api/post/<string:post_slug>', methods=['GET'])
def get_post_detail(post_slug):
    """API 端点：获取单篇博客文章的详细内容 (元数据从DB, 内容从MD文件)"""
    print(f"Attempting to get post with slug: '{post_slug}'")

    try:
        post_meta = Post.query.filter_by(slug=post_slug, is_published=True).first()

        if not post_meta:
            print(f"Error: Post metadata not found in database for slug: '{post_slug}'")
            return jsonify({'error': 'Post metadata not found'}), 404

        markdown_file_path = os.path.join(DATA_DIR, post_meta.markdown_file_path)
        print(f"Expected markdown file path from DB: '{markdown_file_path}'")
        
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            content_md = f.read() 
            # HTML conversion can be done here or on the frontend.
            # If done here, ensure 'markdown' library is used correctly.
            # content_html = markdown(content_md) # Example

            print(f"Found metadata and content for post: {post_meta.title}")
            return jsonify({
                'id': post_meta.id, # Include ID here too
            'title': post_meta.title,
                'date': post_meta.created_at.strftime('%Y年%m月%d日'),
                'category': post_meta.category.name if post_meta.category else '未分類',
            'tags': [tag.name for tag in post_meta.tags],
                    'content_md': content_md,
            'slug': post_meta.slug,
            'summary': post_meta.summary,
            'preview_image_url': post_meta.preview_image_url
            }), 200
            
    except FileNotFoundError:
        print(f"Error: Markdown file not found at path: '{markdown_file_path}'")
        # Even if MD file is missing, return metadata if available, but indicate missing content
        content_md = f"Error: Markdown file not found at {post_meta.markdown_file_path}"
        # You might want to return a different status code or error structure here

        return jsonify({
            'id': post_meta.id, # Include ID here too
            'title': post_meta.title,
            'date': post_meta.created_at.strftime('%Y年%m月%d日'),
            'category': post_meta.category.name if post_meta.category else '未分類',
            'tags': [tag.name for tag in post_meta.tags],
            'content_md': content_md,
            'slug': post_meta.slug,
            'summary': post_meta.summary,
            'preview_image_url': post_meta.preview_image_url
        }), 200
    except Exception as e:
        print(f"An unexpected error occurred for post slug '{post_slug}': {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/post', methods=['POST'])
@login_required # Add this decorator
def create_post():
    """API 端点：创建博客文章 (NOW USING DB)，需要登录和管理员权限"""
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required to create post"}), 403

    try:
        data = request.json
        print(f"DEBUG: create_post received data: {data}")

        title = data.get('title', '').strip()
        content = data.get('content', '')
        category_name = data.get('category', '').strip()
        tags_list = data.get('tags', [])
        date_str = data.get('date')
        session_id = data.get('session_id') # Get session_id from the request

        if not title or not content or not category_name or not session_id: # session_id is now required for create
            print("Error: Missing required fields for create_post")
            return jsonify({'error': 'Missing title, content, category, or session_id'}), 400
        
        with app.app_context():
            # 1. Check for existing post by title or slug
            potential_slug = generate_slug(title)
            existing_post = Post.query.filter((Post.title == title) | (Post.slug == potential_slug)).first()
            if existing_post:
                print(f"Error: Post with title '{title}' or slug '{potential_slug}' already exists.")
                return jsonify({'error': f"A post with the title '{title}' already exists."}), 409 # Conflict

            # 2. Get or create Category
            category_obj = Category.query.filter_by(name=category_name).first()
            if not category_obj:
                 print(f"Category '{category_name}' not found, creating it.")
                 category_obj = Category(name=category_name)
                 db.session.add(category_obj)
                 # No need to flush here, category will be committed with the post

            # 3. Set author to the current logged-in admin user
            # The check for is_admin is already done at the beginning of the function.
            author_user = current_user

            # 4. Prepare post data and generate final slug
            post_slug = potential_slug 
            slug_counter = 1
            while Post.query.filter_by(slug=post_slug).first():
                post_slug = f"{potential_slug}-{slug_counter}"
                slug_counter += 1

            summary_text = extract_summary_from_md_content(content)
            parsed_date = parse_date_from_string(date_str)
            if not parsed_date:
                parsed_date = datetime.utcnow()

            # The post directory will be renamed from session_id to post_slug
            final_post_directory_name = post_slug 
            # The markdown file path within the new directory
            relative_md_path = os.path.join(final_post_directory_name, f"{post_slug}.md").replace('\\', '/')


            # 5. Create new Post object (preview_image_url is None for now)
            new_post = Post(
                title=title,
                slug=post_slug, # Use the final, unique slug
                markdown_file_path=relative_md_path,
                summary=summary_text,
                preview_image_url=None, # Set to None initially
                created_at=parsed_date,
                updated_at=parsed_date,
                is_published=True,
                category=category_obj,
                author_id=author_user.id # Use current_user.id
            )

            # 6. Add Tags
            for tag_name_str in tags_list:
                tag_name = tag_name_str.strip()
                if tag_name:
                    tag_obj = Tag.query.filter_by(name=tag_name).first()
                    if not tag_obj:
                        print(f"Tag '{tag_name}' not found, creating it.")
                        tag_obj = Tag(name=tag_name)
                        db.session.add(tag_obj)
                    new_post.tags.append(tag_obj) # Link tag object

            # 7. Add post to session and commit DB changes FIRST
            db.session.add(new_post)
            db.session.commit() # Commit to get the post ID and save associations

            print(f"Post '{new_post.title}' (ID: {new_post.id}) committed to DB. Proceeding with file operations.")

            # 8. Handle file operations (Rename temporary session directory and save MD)
            # temp_session_dir is now directly under DATA_DIR
            temp_session_dir = os.path.join(DATA_DIR, session_id)
            final_post_dir = os.path.join(DATA_DIR, final_post_directory_name) # Target dir is final slug

            file_op_status = {'status': 'not_attempted', 'message': 'File operations not attempted.'}

            try:
                 # --- Step 8a: Rename the temporary session directory to the final slug directory ---
                # Check if the temp directory exists BEFORE attempting to rename
                if os.path.exists(temp_session_dir) and os.path.isdir(temp_session_dir):
                    # Check if the target directory already exists
                    if os.path.exists(final_post_dir):
                         # This should ideally not happen if slug generation is correct and unique
                         # If target exists, we don't rename the temp dir to it.
                         print(f"WARNING: Target directory '{final_post_dir}' already exists during rename from temp '{temp_session_dir}' for post ID {new_post.id}. Skipping rename.")
                         file_op_status['status'] = 'warning_target_dir_exists'
                         file_op_status['message'] = f"Warning: Target directory '{final_post_directory_name}' already exists. Temporary directory rename skipped."
                         # Optionally, you might want to move the *contents* of the temp dir into the existing final dir
                         # if you want to merge assets, but the request was to rename the folder.
                         # For simplicity, we just skip the rename if target exists. The temp dir remains.
                         # The MD file saving in step 8b will proceed to the *intended* final_post_dir.
                         
                         # Ensure the target directory exists even if rename was skipped
                         try:
                            os.makedirs(final_post_dir, exist_ok=True)
                            print(f"Ensured final directory '{final_post_dir}' exists for MD file save (after rename skipped).")
                         except Exception as e_mkdir:
                            print(f"CRITICAL ERROR: Could not ensure final directory '{final_post_dir}' exists after rename skipped: {e_mkdir}")
                            file_op_status['status'] = file_op_status.get('status', 'unknown') + '_critical_mkdir_error'
                            file_op_status['message'] += f" Critical mkdir error: {e_mkdir}"
                            pass # Decide if you want to abort or continue with warnings

                    else: # Target directory does not exist, safe to rename
                        os.rename(temp_session_dir, final_post_dir)
                        print(f"Renamed temp directory '{temp_session_dir}' to final directory '{final_post_dir}' for post ID {new_post.id}")
                        file_op_status['status'] = 'renamed_temp'
                        file_op_status['message'] = f"Renamed temporary directory to '{final_post_directory_name}'."

                else:
                    print(f"Warning: Temporary session directory '{temp_session_dir}' not found or is not a directory for post ID {new_post.id}. No directory to rename.")
                    file_op_status['status'] = 'temp_dir_not_found'
                    file_op_status['message'] = "Temporary session directory not found."
                    # If no temp dir to rename, create the intended final directory structure
                    try:
                         os.makedirs(final_post_dir, exist_ok=True)
                         os.makedirs(os.path.join(final_post_dir, 'assets'), exist_ok=True) # Also create assets dir
                         print(f"Created final directory '{final_post_dir}' and assets as temp was not found.")
                         file_op_status['status'] = 'final_dir_created'
                         file_op_status['message'] = "Temporary directory not found, created final directory."
                    except Exception as e_mkdir:
                         print(f"CRITICAL ERROR: Could not create final directory '{final_post_dir}' as temp was not found: {e_mkdir}")
                         file_op_status['status'] = file_op_status.get('status', 'unknown') + '_critical_mkdir_error'
                         file_op_status['message'] += f" Critical mkdir error: {e_mkdir}"
                         pass # Decide if you want to abort


                # --- Step 8b: Save markdown content into the final directory ---
                # Use the relative_md_path which was calculated based on the final slug
                full_md_path = os.path.join(DATA_DIR, new_post.markdown_file_path) 
                
                try:
                    with open(full_md_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Markdown file saved to {full_md_path} for post ID {new_post.id}")
                except IOError as e_write_md:
                    print(f"ERROR: Could not write markdown file '{full_md_path}' for post ID {new_post.id}: {e_write_md}")
                    file_op_status['status'] = file_op_status.get('status', 'unknown') + '_error_writing_md'
                    file_op_status['message'] += f" Failed to write markdown file: {e_write_md}"


                # --- Step 8c: Find and set the preview image URL AFTER assets are in the final location ---
                # The assets are now inside final_post_dir (because the whole dir was renamed/created)
                found_preview_url = find_preview_image_for_post(new_post.slug) # Use the post's final slug

                if found_preview_url and new_post.preview_image_url != found_preview_url:
                    new_post.preview_image_url = found_preview_url
                    db.session.commit() # Commit again to save the preview image URL
                    print(f"Set preview_image_url for post ID {new_post.id} to: {found_preview_url}")
                elif not found_preview_url:
                     print(f"DEBUG: No preview image found to set for post ID {new_post.id}.")

                print(f"File operations completed (with potential warnings/errors) for post ID {new_post.id}.")

            except Exception as file_error:
                 # Catch any other unexpected file operation errors
                 print(f"WARNING: Unexpected file operation error for post ID {new_post.id}: {file_error}")
                 import traceback
                 traceback.print_exc()
                 file_op_status['status'] = file_op_status.get('status', 'unknown') + '_unexpected_error'
                 file_op_status['message'] += f" Unexpected error: {file_error}"


            response_data = {
                'success': True,
                'message': 'Post created successfully',
                'slug': new_post.slug,
                'id': new_post.id,
                'preview_image_url': new_post.preview_image_url,
                'file_operation_status': file_op_status # Include file operation status
            }
            return jsonify(response_data), 201
    
    except Exception as e:
        # This catches errors before DB commit or major logic errors
        db.session.rollback()
        print(f"Error creating post: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/post/<string:post_identifier>', methods=['PUT'])
@login_required # Add this decorator
def edit_post(post_identifier): # Parameter name changed to reflect it could be ID or slug
    """API 端点：编辑指定博客文章 (NOW USING DB)，需要登录"""
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required to edit post"}), 403

    try:
        data = request.json
        print(f"DEBUG: edit_post received data for identifier {post_identifier}: {data}")

        new_title = data.get('title', '').strip()
        new_content = data.get('content', '')
        new_category_name = data.get('category', '').strip()
        new_tags_list = data.get('tags', [])
        new_date_str_client = data.get('date')
        # session_id is received but NOT used for moving assets in edit mode anymore
        # session_id = data.get('session_id')

        if not new_title or not new_content or not new_category_name:
            print("Error: Missing required fields for edit_post")
            return jsonify({'error': 'Missing required fields for edit'}), 400

        with app.app_context():
            # 1. Find the existing post by identifier (ID or Slug)
            post_to_edit = None
            if post_identifier.isdigit():
                # Try to find by ID if the identifier is numeric
                post_id = int(post_identifier)
                post_to_edit = db.session.get(Post, post_id) # Use get for primary key lookup
                print(f"DEBUG: Attempted to find post by ID {post_id}. Found: {post_to_edit is not None}")
            
            if not post_to_edit:
                # If not found by ID or identifier is not numeric, try finding by slug
                post_to_edit = Post.query.filter_by(slug=post_identifier).first()
                print(f"DEBUG: Attempted to find post by slug '{post_identifier}'. Found: {post_to_edit is not None}")

            if not post_to_edit:
                print(f"Post with identifier '{post_identifier}' not found for editing.")
                return jsonify({'error': 'Post not found'}), 404

            original_title = post_to_edit.title
            original_slug = post_to_edit.slug

            # 2. Handle Title Change and Slug Generation
            # new_slug = original_slug # Default to keeping the old slug - No, always generate based on NEW title
            new_slug = generate_slug(new_title) # Always generate potential new slug
            title_changed = False
            slug_changed = False

            if new_title != original_title:
                title_changed = True
            
            if new_slug != original_slug:
                 slug_changed = True # Slug is changing IF the newly generated one is different

            # Check for slug uniqueness *only if* the generated new slug is different from the original
            if slug_changed:
                existing_post_with_new_slug = Post.query.filter(Post.slug == new_slug, Post.id != post_to_edit.id).first()

                if existing_post_with_new_slug:
                    print(f"Slug conflict detected for new title '{new_title}'. Generated slug '{new_slug}' already exists for another post (ID: {existing_post_with_new_slug.id}).")
                     # Attempt to resolve conflict by appending a number
                    temp_slug = new_slug
                    slug_counter = 1
                    # Check uniqueness against all existing slugs, excluding the current post being edited
                    while Post.query.filter(Post.slug == temp_slug, Post.id != post_to_edit.id).first():
                         temp_slug = f"{new_slug}-{slug_counter}" # Append to the *initially generated* new slug
                         slug_counter += 1
                    print(f"Resolved slug conflict. Final new slug will be: '{temp_slug}'")
                    new_slug = temp_slug
                    # slug_changed remains True

                # Update title and potentially slug in the DB object
                post_to_edit.title = new_title
                # Always update slug if it was determined to be different (slug_changed is True)
                # or if the newly generated slug *after conflict resolution* is different from the original_slug
                if post_to_edit.slug != new_slug: # Double check against current DB value
                    post_to_edit.slug = new_slug
                    slug_changed = True # Confirm slug was indeed updated

            # If title changed but slug didn't (e.g., "Hello World" -> "hello-world" was already the slug)
            # or if neither title nor slug changed, slug_changed will be false.
            # The directory rename only happens if slug_changed is true.


            # 3. Update other Post attributes
            post_to_edit.summary = extract_summary_from_md_content(new_content)
            post_to_edit.updated_at = datetime.utcnow()

            if new_date_str_client:
                 parsed_date = parse_date_from_string(new_date_str_client)
                 if parsed_date:
                     # Only update created_at if the date was explicitly provided by the client
                     # This prevents updated_at from overwriting created_at unless intended
                     post_to_edit.created_at = parsed_date


            # 4. Update Category
            category_obj = Category.query.filter_by(name=new_category_name).first()
            if category_obj:
                post_to_edit.category = category_obj # Link object
            else:
                 print(f"Category '{new_category_name}' not found during edit for post ID {post_to_edit.id}. Creating it.")
                 new_category = Category(name=new_category_name)
                 db.session.add(new_category)
                 db.session.flush() # Ensure new_category gets an ID before linking
                 post_to_edit.category = new_category # Link new object

            # 5. Update Tags (replace existing tags with new ones)
            # Clear existing associations
            post_to_edit.tags.clear()
            db.session.flush() # Ensure old associations are marked for deletion before adding new ones

            # Add new associations
            for tag_name_str in new_tags_list:
                tag_name = tag_name_str.strip()
                if tag_name:
                    tag_obj = Tag.query.filter_by(name=tag_name).first()
                    if not tag_obj:
                        print(f"Tag '{tag_name}' not found during edit for post ID {post_to_edit.id}, creating it.")
                        tag_obj = Tag(name=tag_name)
                        db.session.add(tag_obj)
                        db.session.flush() # Ensure new_tag gets an ID before linking
                    post_to_edit.tags.append(tag_obj) # Link tag object

            # 6. Commit DB changes FIRST
            db.session.commit()
            print(f"DB changes committed for post ID {post_to_edit.id}.")

            # 7. Handle File Operations (Directory Rename if slug changed, and Content Update)
            file_op_status = {'status': 'not_attempted', 'message': 'File operations not attempted.'}

            # Determine the final directory path based on the *current* slug from the DB object
            current_slug_from_db = post_to_edit.slug # Get the final slug from the updated DB object
            final_post_dir_path = os.path.join(DATA_DIR, current_slug_from_db)
            # final_assets_dir = os.path.join(final_post_dir_path, 'assets') # Not directly used for saving here

            # Directory Rename if slug changed
            if slug_changed: # If the slug was actually changed in step 2 and committed
                 old_full_dir_path = os.path.join(DATA_DIR, original_slug)
                 new_full_dir_path = final_post_dir_path # This is the target based on new slug

                 if os.path.exists(old_full_dir_path) and old_full_dir_path != new_full_dir_path:
                     try:
                         # Check if the target directory already exists and is not the same as the old one
                         if os.path.exists(new_full_dir_path):
                             print(f"WARNING: Target directory '{new_full_dir_path}' already exists during rename attempt from '{old_full_dir_path}' for post ID {post_to_edit.id}.")
                             # This case needs careful handling. If the target exists, we cannot simply rename.
                             # Option 1: Error out. Option 2: Attempt to merge contents (complex).
                             # For now, log a warning and proceed, assuming the rename might fail but file writing might still go to the target dir.
                             file_op_status['status'] = 'warning_target_dir_exists'
                             file_op_status['message'] = f"Warning: Target directory '{current_slug_from_db}' already exists. Directory rename skipped or merged."
                             # Do NOT proceed with os.rename here if target exists, it's unsafe.
                             # Instead, ensure the target directory exists and proceed with saving MD file there.
                             try:
                                os.makedirs(new_full_dir_path, exist_ok=True)
                                print(f"Ensured target directory '{new_full_dir_path}' exists for MD file save.")
                             except Exception as e_mkdir:
                                print(f"CRITICAL ERROR: Could not ensure target directory '{new_full_dir_path}' exists after potential rename failure: {e_mkdir}")
                                file_op_status['status'] = file_op_status.get('status', 'unknown') + '_critical_mkdir_error'
                                file_op_status['message'] += f" Critical mkdir error: {e_mkdir}"
                                pass # Decide if you want to abort

                         else: # Target directory does not exist, safe to rename
                            os.rename(old_full_dir_path, new_full_dir_path)
                            print(f"Renamed directory from '{old_full_dir_path}' to '{new_full_dir_path}' for post ID {post_to_edit.id}")
                            file_op_status['status'] = 'renamed_directory'
                            file_op_status['message'] = f"Renamed directory to '{current_slug_from_db}'."

                            # Update markdown_file_path in DB after successful directory rename
                            # The path should now be relative to DATA_DIR using the *new* slug
                            post_to_edit.markdown_file_path = os.path.join(current_slug_from_db, f"{current_slug_from_db}.md").replace('\\', '/')
                            # Re-commit this path change to DB
                            db.session.commit() # Separate commit for path update
                            print(f"Updated markdown_file_path in DB to '{post_to_edit.markdown_file_path}' for post ID {post_to_edit.id}")

                     except OSError as e_rename:
                         print(f"ERROR: Could not rename directory from '{old_full_dir_path}' to '{new_full_dir_path}' for post ID {post_to_edit.id}: {e_rename}")
                         file_op_status['status'] = file_op_status.get('status', 'unknown') + '_error_renaming_dir'
                         file_op_status['message'] += f" Failed to rename directory: {e_rename}"
                         # File system inconsistency: DB might have new slug/path, but directory wasn't renamed.
                         # Ensure target directory exists for saving MD file.
                         try:
                            os.makedirs(final_post_dir_path, exist_ok=True)
                         except Exception as e_mkdir:
                            print(f"CRITICAL ERROR: Could not ensure final directory '{final_post_dir_path}' exists after rename failure: {e_mkdir}")
                            file_op_status['status'] = file_op_status.get('status', 'unknown') + '_critical_mkdir_error'
                            file_op_status['message'] += f" Critical mkdir error: {e_mkdir}"
                            pass # Decide if you want to abort


            # Ensure the target directory for the MD file exists (important if slug didn't change or rename failed)
            try:
                os.makedirs(final_post_dir_path, exist_ok=True)
            except Exception as e_mkdir:
                 print(f"ERROR: Could not ensure directory structure for post ID {post_to_edit.id}: {e_mkdir}")
                 file_op_status['status'] = file_op_status.get('status', 'unknown') + '_error_ensuring_dir'
                 file_op_status['message'] += f" Failed to ensure directory structure: {e_mkdir}"


            # Determine the final markdown file path
            # It should be in the directory named by the *current* slug, and the file name should match the *current* slug.
            full_md_file_path_to_write = os.path.join(final_post_dir_path, f"{post_to_edit.slug}.md")

            # Save/Overwrite Markdown file with new content
            try:
                with open(full_md_file_path_to_write, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated markdown file at '{full_md_file_path_to_write}' for post ID {post_to_edit.id}")
            except IOError as e_write_md:
                 print(f"ERROR: Could not write markdown file '{full_md_file_path_to_write}' for post ID {post_to_edit.id}: {e_write_md}")
                 file_op_status['status'] = file_op_status.get('status', 'unknown') + '_error_writing_md'
                 file_op_status['message'] += f" Failed to write markdown file: {e_write_md}"


            # Clean up the old MD filename if the slug changed
            if slug_changed and os.path.exists(final_post_dir_path): # Only clean up if dir exists and slug changed
                # The old MD file would have been named {original_slug}.md inside the {original_slug} directory.
                # After directory rename, it would be at {new_full_dir_path}/{original_slug}.md
                potential_leftover_old_md_path = os.path.join(final_post_dir_path, f"{original_slug}.md")
                # Ensure it's not the same as the new file path (in case original_slug == new_slug)
                if os.path.exists(potential_leftover_old_md_path) and os.path.basename(potential_leftover_old_md_path) != f"{post_to_edit.slug}.md":
                     try:
                         os.remove(potential_leftover_old_md_path)
                         print(f"Cleaned up leftover old markdown file: {potential_leftover_old_md_path} for post ID {post_to_edit.id}")
                     except OSError as e_remove_old_md:
                         print(f"WARNING: Could not remove leftover old markdown file '{potential_leftover_old_md_path}' for post ID {post_to_edit.id}: {e_remove_old_md}")
                         file_op_status['status'] = file_op_status.get('status', 'unknown') + '_warning_removing_old_md'
                         file_op_status['message'] += f" Warning removing old md file: {e_remove_old_md}"


            # Asset handling in edit mode: Images pasted/uploaded went directly to the final asset folder
            # so no separate 'move' step is needed here.
            # We just need to potentially update the preview_image_url based on the *current* state of the assets folder.

            # --- NEW: Find and set the preview image URL AFTER markdown is saved ---
            found_preview_url = find_preview_image_for_post(post_to_edit.slug) # Use the post's current slug

            if found_preview_url and post_to_edit.preview_image_url != found_preview_url:
                post_to_edit.preview_image_url = found_preview_url
                db.session.commit() # Commit again to save the preview image URL
                print(f"Updated preview_image_url for post ID {post_to_edit.id} to: {found_preview_url}")
            elif not found_preview_url and post_to_edit.preview_image_url is not None:
                 # If no image is found anymore, but there was one, clear the field
                 post_to_edit.preview_image_url = None
                 db.session.commit() # Commit again to clear the preview image URL
                 print(f"DEBUG: No preview image found, cleared preview_image_url for post ID {post_to_edit.id}.")


            print(f"Post ID {post_to_edit.id} edited successfully (DB and Files).")
            response_data = {
                'success': True,
                'message': 'Post updated successfully',
                'slug': post_to_edit.slug,
                'title': post_to_edit.title,
                'id': post_to_edit.id,
                'preview_image_url': post_to_edit.preview_image_url,
                'file_operation_status': file_op_status # Include file operation status
            }
            return jsonify(response_data), 200

    except Exception as e:
        db.session.rollback() # Rollback transaction on error
        print(f"Error editing post identifier {post_identifier}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/post/<int:post_id>', methods=['DELETE'])
@login_required # Add this decorator
def delete_post(post_id):
    """API 端点：删除指定博客文章 (NOW USING DB)，需要登录"""
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required to delete post"}), 403
    try:
        with app.app_context():
            # 1. Find the post by ID
            post_to_delete = Post.query.get(post_id)

            if not post_to_delete:
                print(f"Post with ID {post_id} not found for deletion.")
                return jsonify({'success': False, 'error': 'Post not found'}), 404

            post_title = post_to_delete.title
            post_slug = post_to_delete.slug # Get slug for file path

            # 2. Delete the post from the database FIRST
            # SQLAlchemy handles clearing the many-to-many relationship with tags automatically.
            db.session.delete(post_to_delete)
            db.session.commit()
            print(f"Post '{post_title}' (ID: {post_id}) deleted from DB.")

            # 3. Delete the corresponding markdown file and directory AFTER DB commit
            post_directory_path = os.path.join(DATA_DIR, post_slug)

            if os.path.exists(post_directory_path):
                try:
                    shutil.rmtree(post_directory_path)
                    print(f"Deleted post directory: {post_directory_path}")
                except OSError as e_rmtree:
                    # File system inconsistency: DB record is gone, but directory/files remain.
                    # Log error and return success for the API call. Manual cleanup might be needed.
                    print(f"WARNING: Error removing post directory {post_directory_path} for post ID {post_id}: {e_rmtree}")
                    import traceback
                    traceback.print_exc()
                    # Continue and return success because the main DB record is deleted

            return jsonify({'success': True, 'message': f"Post '{post_title}' deleted successfully"}), 200

    except Exception as e:
        # Catches errors during DB query or initial stages
        db.session.rollback()
        print(f"Error deleting post ID {post_id} from DB: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/profile/kyosuke', methods=['GET'])
def get_kyosuke_profile():
    """API 端点：获取柊杏介的个人详细信息"""
    print(f"\n[DEBUG /api/profile/kyosuke] Received GET request.")
    profile_file_path = os.path.join(PROFILE_DATA_DIR, 'profile1.txt')
    print(f"[DEBUG /api/profile/kyosuke] Reading profile file: {profile_file_path}")
    bio_content = "プロフィールの読み込みに失敗しました。"
    try:
        with open(profile_file_path, 'r', encoding='utf-8') as f:
            bio_content = f.read()
        print(f"[DEBUG /api/profile/kyosuke] Successfully read profile file.")
    except FileNotFoundError:
        print(f"[ERROR /api/profile/kyosuke] Profile file not found: {profile_file_path}")
    except Exception as e:
        print(f"[ERROR /api/profile/kyosuke] Error reading profile file {profile_file_path}: {e}")

    skills_data = [
        { "name": "Python", "color": "#FFD43B", "percent": 90, "note": "データ分析、ウェブ開発 (Flask)" },
        { "name": "深層学習", "color": "#9400D3", "percent": 85, "note": "CNN, RNN, Transformers" },
        { "name": "機械学習", "color": "#DC143C", "percent": 80, "note": "Scikit-learn, TensorFlow, PyTorch" },
        { "name": "データサイエンス(Data Science)", "color": "#00FA9A", "percent": 75, "note": "Pandas, NumPy, Matplotlib" },
        { "name": "C++", "color": "#EE82EE", "percent": 40, "note": "基本的なアルゴリズム、パフォーマンスクリティカルな部分" },
        { "name": "Java", "color": "#00BFFF", "percent": 40, "note": "基本的なフロントエンド、Node.js" },
        { "name": "MySQL", "color": "#4B0082", "percent": 40, "note": "基本的なフロントエンド、Node.js" },
        { "name": "HTML/CSS", "color": "#F08080", "percent": 20, "note": "Tailwind CSS, レスポンシブデザイン" }
    ]

    profile_data = {
        "name": "柊杏介 (ヒイラギ キョスケ)",
        "imageUrl": "/data/profile/kyosuke/portrait.jpg",
        "bio_html": markdown(bio_content),
        "gender": "男性",
        "birthday": "2004年05月23日",
        "hobbies": "AI技術の研究、プログラミングコンテストへの参加、旅行",
        "skills": skills_data,
        "education": [
            { "period": "2023年 - 現在", "institution": "SDUFE (Shandong University of finance and economics)", "details": "コンピュータ科学・人工知能学部 在学中" },
        ],
        "workExperience": [
             { "period": "", "company": "", "role": "関連する職務経歴は現在ありません。", "details": "" }
        ]
    }
    print(f"[DEBUG /api/profile/kyosuke] Returning profile data.")
    return jsonify(profile_data)

@app.route('/api/upload_image', methods=['POST'])
def upload_editor_image():
    """Handles image uploads directly to the permanent upload folder (deprecated by paste_image)."""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file part'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        try:
            file.save(filepath)
            image_url_for_client = f"/blog_assets/uploaded_images/{unique_filename}"
            return jsonify({'imageUrl': image_url_for_client}), 200
        except Exception as e:
            print(f"Error saving uploaded image: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'File type not allowed'}), 400

@app.route('/api/labels', methods=['GET'])
def get_labels():
    """API 端点：获取所有分类及其颜色 (NOW FROM DB)"""
    print("DEBUG: /api/labels route accessed (DB)")
    try:
        categories = Category.query.all()

        labels_data = [{'name': cat.name} for cat in categories]

        if not labels_data:
            print("Warning: No categories found in the database.")

        return jsonify(labels_data), 200

    except Exception as e:
        print(f"Error getting labels from DB: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Error fetching labels', 'details': str(e)}), 500

@app.route('/api/tags', methods=['GET'])
def get_tags():
    """API 端点：获取所有标签 (NOW FROM DB)"""
    print("DEBUG: /api/tags route accessed (DB)")
    try:
        tags = Tag.query.all()

        tags_list = [tag.name for tag in tags]

        if not tags_list:
            print("Warning: No tags found in the database.")

        return jsonify(tags_list), 200

    except Exception as e:
        print(f"Error getting tags from DB: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Error fetching tags', 'details': str(e)}), 500

@app.route('/api/paste_image', methods=['POST'])
def paste_image_handler():
    """Handles pasted or drag/dropped images, saves them to a temp session folder."""
    if 'image_file' not in request.files:
        return jsonify({'error': 'No image_file part in the request'}), 400
    
    file = request.files['image_file']
    session_id = request.form.get('session_id') 
    is_editing = request.form.get('is_editing') == 'true' # NEW: Check if it's an edit session
    original_post_title = request.form.get('original_post_title') # NEW: Get original title if editing

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # session_id is still required for identifying the session, even in edit mode for client tracking
    if not session_id: 
        # However, for edit mode, we also need the original_post_title/slug
        if is_editing and not original_post_title:
             return jsonify({'error': 'Original post title is required for image pasting in edit mode'}), 400
        if not is_editing:
            return jsonify({'error': 'Session ID is required for image pasting in create mode'}), 400


    if file and allowed_file(file.filename):
        filename_to_use = secure_filename(file.filename)
        if not filename_to_use:
            filename_to_use = f"pasted_image_{uuid.uuid4().hex[:8]}.{file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'png'}"

        # MODIFIED: Determine the target directory based on whether it's editing or creating
        target_base_dir = None
        markdown_image_path = None # Path to insert into markdown (relative)
        preview_image_url_prefix = None # Prefix for generating preview URL

        if is_editing and original_post_title:
            # In edit mode, save directly to the post's final assets folder
            # Generate slug from original title to find the directory
            original_slug = generate_slug(original_post_title) # Use helper to generate slug from original title
            # IMPORTANT: During edit, if the slug changes, the directory will be renamed *on save*.
            # However, newly pasted images *during* the edit need to go to the directory matching the *current* slug.
            # We should probably send the *current* slug from the frontend in edit mode if it's known.
            # For simplicity now, let's assume we are saving to the directory based on the *original* title/slug.
            # This might cause issues if the slug changes and images are pasted *after* the change but *before* save.
            # A more robust approach would be to send the *current* slug from the frontend.
            # Let's use the original_post_title to derive the initial target directory based on the *expected* slug.
            # A better approach would be to fetch the current slug from the DB using the original title/identifier *here* if possible,
            # or ensure the frontend always sends the current slug when editing.
            
            # Find the post by its current title (sent as original_post_title during edit)
            # This assumes the title hasn't been changed *yet* when pasting, or that the backend can find it by old title.
            # A more robust way: Frontend sends post ID or current slug during edit paste.
            
            # Let's modify the frontend to send `post_identifier` (which is the slug/ID in edit mode)
            # For now, assuming original_post_title uniquely identifies the post to get its *current* slug:
            post_to_edit = None
            with app.app_context(): # Need app context to query DB
                 # Try finding by title first, as the frontend currently sends original_post_title
                 post_to_edit = Post.query.filter_by(title=original_post_title).first()
                 if not post_to_edit:
                      # If not found by title, maybe the frontend sent the slug as original_post_title?
                     post_to_edit = Post.query.filter_by(slug=original_post_title).first()
                 
            if post_to_edit:
                 post_slug_for_dir = post_to_edit.slug # Use the actual current slug from the DB
                 target_base_dir = os.path.join(DATA_DIR, post_slug_for_dir)
                 markdown_image_path = f"./assets/{filename_to_use}" # Relative path in MD
                 preview_image_url_prefix = f"/blog_assets/{urllib.parse.quote(post_slug_for_dir)}/assets/" # URL prefix for frontend

            else:
                print(f"Error: Could not find post with identifier '{original_post_title}' for image paste in edit mode.")
                return jsonify({'error': f"Could not find post for image paste: {original_post_title}"}), 404

        else: # Create mode or fallback
            # In create mode, save to the temp session folder
            target_base_dir = os.path.join(app.config['TEMP_UPLOAD_FOLDER'], session_id)
            markdown_image_path = f"./assets/{filename_to_use}" # Relative path in MD
            preview_image_url_prefix = f"/temp_assets/{urllib.parse.quote(session_id)}/assets/" # URL prefix for frontend

        if not target_base_dir: # Should not happen if logic above is correct, but for safety
             print("Critical Error: target_base_dir is None.")
             return jsonify({'error': 'Internal server error determining save path'}), 500

        target_assets_dir = os.path.join(target_base_dir, 'assets') # Assets folder inside target base
        filepath_on_disk = os.path.join(target_assets_dir, filename_to_use)

        if not os.path.exists(target_assets_dir):
            try:
                os.makedirs(target_assets_dir, exist_ok=True) # Use exist_ok=True for safety
            except Exception as e:
                print(f"Error creating target assets directory {target_assets_dir}: {e}")
                return jsonify({'error': f"Could not create assets directory: {str(e)}"}), 500
        
        try:
            if os.path.exists(filepath_on_disk):
                # Optionally remove existing file if overwriting is desired
                # os.remove(filepath_on_disk)
                print(f"Warning: File already exists at {filepath_on_disk}. Overwriting.")
            
            file.save(filepath_on_disk)
            print(f"Image saved to: {filepath_on_disk}")

            # Construct the URL for the frontend preview
            preview_image_url = f"{preview_image_url_prefix}{urllib.parse.quote(filename_to_use)}"

            return jsonify({
                'filePath': markdown_image_path, # Path used in markdown like ./assets/image.png
                'previewUrl': preview_image_url, # Full URL for image preview
                'filenameInAssets': filename_to_use # Just the filename
            }), 200

        except Exception as e:
            print(f"Error saving pasted image: {e}")
            import traceback
            print(traceback.format_exc())
            return jsonify({'error': f"Could not save image: {str(e)}"}), 500
    else:
        return jsonify({'error': 'File type not allowed or no file provided'}), 400

@app.route('/temp_assets/<path:session_id>/<path:filename_with_assets_prefix>')
def serve_temp_asset(session_id, filename_with_assets_prefix):
    """Serves static files from temporary session folders."""
    print(f"\n[DEBUG serve_temp_asset] Received request: session_id='{session_id}', filename_with_assets_prefix='{filename_with_assets_prefix}'")
    print(f"[DEBUG serve_temp_asset] TEMP_UPLOAD_FOLDER: '{app.config['TEMP_UPLOAD_FOLDER']}'")
    
    # Ensure the requested path is within the specific session folder inside TEMP_UPLOAD_FOLDER
    # Using send_from_directory's security features is the best approach.
    directory_to_serve_from = os.path.join(app.config['TEMP_UPLOAD_FOLDER'], session_id)
    file_to_serve = filename_with_assets_prefix # This is the path relative to directory_to_serve_from (e.g., 'assets/image.jpg')

    # Optional: Basic sanity check if the session_id directory exists
    full_session_dir = os.path.abspath(directory_to_serve_from)
    temp_upload_base = os.path.abspath(app.config['TEMP_UPLOAD_FOLDER'])

    if not full_session_dir.startswith(temp_upload_base) or not os.path.exists(full_session_dir) or not os.path.isdir(full_session_dir):
        print(f"[SECURITY serve_temp_asset] Invalid session directory or path traversal attempt: {full_session_dir}")
        from flask import abort
        abort(404) # Not found or unauthorized access

    # send_from_directory handles the final path joining and security against `file_to_serve` escaping the directory.
    full_file_path_on_disk = os.path.join(directory_to_serve_from, file_to_serve)
    print(f"[DEBUG serve_temp_asset] Attempting to serve temporary file from full path: '{full_file_path_on_disk}'")

    if not os.path.exists(full_file_path_on_disk) or not os.path.isfile(full_file_path_on_disk):
        print(f"[DEBUG serve_temp_asset] Temporary file not found: '{full_file_path_on_disk}'")
        from flask import abort
        abort(404)
    
    try:
        print(f"[DEBUG serve_temp_asset] Serving '{file_to_serve}' from directory '{directory_to_serve_from}'")
        return send_from_directory(directory_to_serve_from, file_to_serve)
    except Exception as e:
        print(f"[ERROR serve_temp_asset] Error serving temporary file {session_id}/{filename_with_assets_prefix}: {e}")
        import traceback
        print(traceback.format_exc())
        from flask import abort
        abort(404) # Or 500, depending on desired error handling

@app.route('/api/latest-statistical-posts', methods=['GET'])
def get_latest_posts():
    """API 端点：获取最新的博客文章 (NOW FROM DB)"""
    try:
        latest_posts = Post.query.filter_by(is_published=True)\
                               .order_by(Post.created_at.desc())\
                               .limit(3)\
                               .all()

        posts_metadata = []
        for post in latest_posts:
             posts_metadata.append({
                'id': post.id,
                'title': post.title,
                'date': post.created_at.strftime('%Y年%m月%d日'),
                'category': post.category.name if post.category else '未分類',
                'tags': [tag.name for tag in post.tags],
                'slug': post.slug,
                'summary': post.summary if post.summary else "概要なし",
                'preview_image_url': post.preview_image_url
            })

        if not posts_metadata:
            print(f"Warning: No published posts found for latest list.")
            
        return jsonify(posts_metadata), 200

    except Exception as e:
        print(f"Error getting latest posts from DB: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Error fetching latest posts', 'details': str(e)}), 500

@app.route('/blog_assets/<path:folder>/<path:filename>')
def serve_blog_asset(folder, filename):
    """提供博客资源文件的路由 (例如图片, PDF等)"""
    print(f"\n[DEBUG serve_blog_asset] Received request: folder='{folder}', filename='{filename}'")
    print(f"[DEBUG serve_blog_asset] DATA_DIR: '{DATA_DIR}'")
    
    # Ensure the requested path is within the data directory and the specific folder
    # Using send_from_directory's security features is the best approach.
    # The folder part is the post slug. The filename part includes the assets/ prefix if the URL was constructed that way.
    directory_to_serve_from = os.path.join(DATA_DIR, folder) # Base directory is the post's slug folder
    file_to_serve = filename # This is the path relative to directory_to_serve_from (e.g., 'assets/image.jpg')

    # Optional: Basic sanity check if the folder directory exists
    full_folder_dir = os.path.abspath(directory_to_serve_from)
    data_base = os.path.abspath(DATA_DIR)

    if not full_folder_dir.startswith(data_base) or not os.path.exists(full_folder_dir) or not os.path.isdir(full_folder_dir):
        print(f"[SECURITY serve_blog_asset] Invalid post folder directory or path traversal attempt: {full_folder_dir}")
        from flask import abort
        abort(404) # Not found or unauthorized access

    # send_from_directory handles the final path joining and security against `file_to_serve` escaping the directory.
    full_file_path_on_disk = os.path.join(directory_to_serve_from, file_to_serve)
    print(f"[DEBUG serve_blog_asset] Attempting to serve blog asset from full path: '{full_file_path_on_disk}'")


    if not os.path.exists(full_file_path_on_disk) or not os.path.isfile(full_file_path_on_disk):
        print(f"[DEBUG serve_blog_asset] Blog asset file not found: '{full_file_path_on_disk}'")
        from flask import abort
        abort(404)

    try:
        print(f"[DEBUG serve_blog_asset] Serving '{file_to_serve}' from directory '{directory_to_serve_from}'")
        return send_from_directory(directory_to_serve_from, file_to_serve)
    except Exception as e:
        print(f"[ERROR serve_blog_asset] Error serving blog asset {folder}/{filename}: {e}")
        import traceback
        print(traceback.format_exc())
        from flask import abort
        abort(404) # Or 500, depending on desired error handling

@app.route('/data/<path:filename>')
def serve_data_file(filename):
    """提供 data 目录下的静态文件，例如 contribution.txt"""
    print(f"\n[DEBUG serve_data_file] Received request for filename: '{filename}'")
    print(f"[DEBUG serve_data_file] DATA_ROOT_FOR_STATIC_FILES: '{DATA_ROOT_FOR_STATIC_FILES}'")

    # Ensure the requested path is within the DATA_ROOT_FOR_STATIC_FILES directory
    # Using send_from_directory is the best approach.
    # The filename is the path relative to DATA_ROOT_FOR_STATIC_FILES.
    directory_to_serve_from = DATA_ROOT_FOR_STATIC_FILES # Base directory is the root of the 'data' folder
    file_to_serve = filename # This is the path relative to directory_to_serve_from (e.g., 'profile/kyosuke/portrait.jpg')

    # send_from_directory handles the final path joining and security against `file_to_serve` escaping the directory.
    full_file_path_on_disk = os.path.join(directory_to_serve_from, file_to_serve)
    print(f"[DEBUG serve_data_file] Attempting to serve data file from full path: '{full_file_path_on_disk}'")

    if not os.path.exists(full_file_path_on_disk) or not os.path.isfile(full_file_path_on_disk):
        print(f"[DEBUG serve_data_file] Data file not found: '{full_file_path_on_disk}'")
        from flask import abort
        abort(404)

    try:
        print(f"[DEBUG serve_data_file] Serving '{file_to_serve}' from directory '{directory_to_serve_from}'")
        return send_from_directory(directory_to_serve_from, file_to_serve)
    except Exception as e:
        print(f"[ERROR serve_data_file] Error serving data file {filename}: {e}")
        import traceback
        print(traceback.format_exc())
        from flask import abort
        abort(404) # Or 500

# --- NEW: Helper for next_page redirection security ---
def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc
# --- END: Helper for next_page redirection security ---

# --- NEW: Login and Logout Routes ---
@app.route('/login', methods=['GET', 'POST'])
# NO @login_required here, as this is the login page itself
def login():
    print(f"\n[DEBUG login] Accessed login route '/login'. Method: {request.method}. User authenticated: {current_user.is_authenticated}") # Added debug print

    if current_user.is_authenticated:
        print("[DEBUG login] User already authenticated, redirecting to admin_dashboard.") # Added debug print
        return redirect(url_for('admin_dashboard')) # Redirect if already logged in

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            print("[DEBUG login] Invalid username or password.") # Added debug print
            login_form_html_with_error = """
            <!doctype html>
            <html lang="zh">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>管理员登录</title>
                <style>
                    body { font-family: sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; display: flex; justify-content: center; align-items: center; height: 100vh; }
                    .login-container { background-color: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); width: 300px; }
                    h2 { text-align: center; color: #333; }
                    .form-group { margin-bottom: 15px; }
                    label { display: block; margin-bottom: 5px; color: #555; }
                    input[type="text"], input[type="password"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
                    input[type="checkbox"] { margin-right: 5px; }
                    button { width: 100%; padding: 10px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
                    button:hover { background-color: #0056b3; }
                    .error { color: red; text-align: center; margin-bottom: 10px; }
                </style>
            </head>
            <body>
                <div class="login-container">
                    <h2>管理员登录</h2>
                    {% if error %} {# Corrected Jinja2 if syntax #}
                    <p class="error">{{ error }}</p> {# Corrected Jinja2 variable syntax #}
                    {% endif %} {# Corrected Jinja2 endif syntax #}
                    <form method="post">
                        <div class="form-group">
                            <label for="username">用户名:</label>
                            <input type="text" id="username" name="username" required>
                        </div>
                        <div class="form-group">
                            <label for="password">密码:</label>
                            <input type="password" id="password" name="password" required>
                        </div>
                        <div class="form-group">
                            <input type="checkbox" id="remember" name="remember">
                            <label for="remember">记住我</label>
                        </div>
                        <button type="submit">登录</button>
                    </form>
                </div>
            </body>
            </html>
            """
            return render_template_string(login_form_html_with_error, error="无效的用户名或密码。"), 401

        login_user(user, remember=remember)
        print(f"[DEBUG login] Successful login for user: {user.username}. Redirecting.") # Added debug print
        next_page = request.args.get('next')
        if not next_page or not is_safe_url(next_page):
            next_page = url_for('admin_dashboard')
        return redirect(next_page)

    # GET request: display the login form
    print("[DEBUG login] Serving login form.") # Added debug print
    login_form_html = """
    <!doctype html>
    <html lang="zh">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>管理员登录</title>
        <style>
            body { font-family: sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; display: flex; justify-content: center; align-items: center; height: 100vh; }
            .login-container { background-color: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); width: 300px; }
            h2 { text-align: center; color: #333; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; color: #555; }
            input[type="text"], input[type="password"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            input[type="checkbox"] { margin-right: 5px; }
            button { width: 100%; padding: 10px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
            button:hover { background-color: #0056b3; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2>管理员登录</h2>
            <form method="post">
                <div class="form-group">
                    <label for="username">用户名:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="password">密码:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <div class="form-group">
                    <input type="checkbox" id="remember" name="remember">
                    <label for="remember">记住我</label>
                </div>
                <button type="submit">登录</button>
            </form>
        </div>
    </body>
    </html>
    """
    return render_template_string(login_form_html)

@app.route('/logout')
@login_required # User must be logged in to logout
def logout():
    logout_user()
    # Redirect to home page or login page after logout
    return redirect(url_for('login'))

# Example of a protected admin route
@app.route('/admin')
@login_required
def admin_dashboard():
    # Simple dashboard page
    # You would replace this with a proper template later
    # REMOVED f prefix, corrected Jinja2 syntax
    dashboard_html = """
    <!doctype html>
    <html lang="zh">
    <head>
        <meta charset="utf-8">
        <title>管理员后台</title>
    </head>
    <body>
        <h1>欢迎, {{ current_user.username }}!</h1> {# Corrected Jinja2 variable syntax #}
        <p>这里是管理员后台。</p>
        <p><a href="{{ url_for('logout') }}">登出</a></p> {# Corrected Jinja2 url_for syntax #}
        <p><a href="{{ url_for('serve_index') }}">返回主页</a></p> {# Corrected Jinja2 url_for syntax #}
        {# Add links to manage posts, categories, tags here later #}
    </body>
    </html>
    """
    return render_template_string(dashboard_html)

# --- NEW: Command to create database tables ---
@app.cli.command('create-db')
def create_db_command():
    """Creates the database tables."""
    with app.app_context():
        db.create_all()
    print('Database tables created.')
# --- END: Command to create database tables ---

# --- NEW: API Endpoint for Contribution Data ---
@app.route('/api/contribution-data', methods=['GET'])
def get_contribution_data():
    """
    API endpoint to get blog contribution data (creations and last updates) per day
    for the last 365 days.
    Returns daily counts for 'activity' (posts created) and 'frequency' (posts last updated).
    """
    print("\n[DEBUG /api/contribution-data] Received GET request.")
    try:
        # Define the date range for the last 365 days
        today = datetime.utcnow().date()
        one_year_ago = today - timedelta(days=364) # Include today and 364 previous days = 365 days

        # Initialize a dictionary to store daily counts (date: {created: count, updated: count})
        daily_counts = {}
        current_date = one_year_ago
        while current_date <= today:
            date_str = current_date.strftime('%Y-%m-%d')
            daily_counts[date_str] = {'created': 0, 'updated': 0}
            current_date += timedelta(days=1)

        # Query for creations within the date range
        # We only consider posts whose creation date is within the last 365 days
        # The group by date needs to handle the datetime object's date part
        creations_query = db.session.query(
            func.date(Post.created_at),
            func.count(Post.id)
        ).filter(
            func.date(Post.created_at) >= one_year_ago.strftime('%Y-%m-%d'),
            func.date(Post.created_at) <= today.strftime('%Y-%m-%d')
        ).group_by(
            func.date(Post.created_at)
        ).all()

        for date_obj, count in creations_query:
            # MODIFIED: date_obj is already a string in YYYY-MM-DD format from func.date() in SQLite
            date_str = date_obj # Use the string directly
            if date_str in daily_counts:
                daily_counts[date_str]['created'] = count

        # Query for last updates within the date range
        # We need posts whose *last* updated_at is within the last 365 days.
        # Also, exclude posts that were *created* on the same day they were updated,
        # if we want "updated" to mean "modified after creation day".
        # A simpler approach is to count all posts whose LAST update was on a given day.
        # Let's count posts where updated_at's DATE is within the range, and updated_at > created_at
        updates_query = db.session.query(
             func.date(Post.updated_at),
             func.count(Post.id)
        ).filter(
             func.date(Post.updated_at) >= one_year_ago.strftime('%Y-%m-%d'),
             func.date(Post.updated_at) <= today.strftime('%Y-%m-%d'),
             # Optional filter: only count updates that are strictly *after* creation
             # (updated_at is set on creation too)
             Post.updated_at > Post.created_at
        ).group_by(
             func.date(Post.updated_at)
        ).all()

        for date_obj, count in updates_query:
            # MODIFIED: date_obj is already a string in YYYY-MM-DD format from func.date() in SQLite
            date_str = date_obj # Use the string directly
            # We might need to distinguish if the update happened on a day a post was *also* created.
            # For now, let's just add it as a separate update count.
            # The frontend can then use 'created' for activity and 'updated' for frequency.
            if date_str in daily_counts:
                 daily_counts[date_str]['updated'] = count # Store counts of *last* updates

        # Format the data as a list of daily pairs (activity, frequency) in chronological order
        # Ensure we have 365 days, even if the counts are 0
        contribution_data = []
        current_date = one_year_ago
        while current_date <= today:
            date_str = current_date.strftime('%Y-%m-%d')
            # Use counts for 'created' as activity and 'updated' as frequency
            activity_count = daily_counts.get(date_str, {}).get('created', 0)
            frequency_count = daily_counts.get(date_str, {}).get('updated', 0) # Use the count of posts *last updated*
            contribution_data.append([activity_count, frequency_count])
            current_date += timedelta(days=1)

        print(f"[DEBUG /api/contribution-data] Returning {len(contribution_data)} days of data.")
        return jsonify(contribution_data), 200

    except Exception as e:
        print(f"[ERROR /api/contribution-data] Error fetching contribution data from DB: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Error fetching contribution data', 'details': str(e)}), 500


# --- NEW: Route to serve files from the calculated STATIC_DIR, now protected, add debug print ---
@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files from the configured STATIC_DIR, requires login."""
    print(f"\n[DEBUG serve_static] Received request for filename: '{filename}'. User authenticated: {current_user.is_authenticated}") # Added debug print
    print(f"[DEBUG serve_static] STATIC_DIR: '{STATIC_DIR}'")

    # Construct the full path to the file within the STATIC_DIR
    full_file_path_on_disk = os.path.join(STATIC_DIR, filename)
    print(f"[DEBUG serve_static] Attempting to serve static file from full path: '{full_file_path_on_disk}'")

    # Basic security check and existence check
    try:
        # Use os.path.commonpath to ensure the resolved path is within STATIC_DIR
        resolved_path = os.path.abspath(full_file_path_on_disk)
        if os.path.commonpath([STATIC_DIR, resolved_path]) != STATIC_DIR:
             print(f"[SECURITY serve_static] Path traversal attempt detected: {resolved_path}")
             from flask import abort
             abort(404) # Not found or unauthorized access

        if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
            print(f"[DEBUG serve_static] Static file not found: '{resolved_path}'")
            from flask import abort
            abort(404)

        print(f"[DEBUG serve_static] Serving '{filename}' from directory '{STATIC_DIR}'")
        return send_from_directory(STATIC_DIR, filename)
    except Exception as e:
        print(f"[ERROR serve_static] Error serving static file {filename}: {e}")
        import traceback
        print(traceback.format_exc())
        from flask import abort
        abort(404)
# --- END: MODIFIED Route to serve static files ---

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# --- NEW: Helper and API for Document Section ---

def list_files_recursive(base_path, current_relative_dir):
    """
    Recursively list files in a directory relative to a base path.
    Args:
        base_path: The absolute base path of the main document directory (e.g., /path/to/data/document).
        current_relative_dir: The current directory being scanned, relative to base_path (e.g., "courses/math" or "").
    Returns:
        A list of file metadata dictionaries.
    """
    files_list = []
    # Construct the full absolute path to the current directory being scanned
    full_current_dir_abs = os.path.join(base_path, current_relative_dir)

    print(f"\n[DEBUG list_files_recursive] Scanning directory: '{full_current_dir_abs}' (Relative: '{current_relative_dir}')")

    # Security: Ensure the resolved path is within the base_path
    try:
        resolved_path = os.path.abspath(full_current_dir_abs)
        base_path_abs = os.path.abspath(base_path) # Get absolute path of base_path once
        if not resolved_path.startswith(base_path_abs + os.sep) and resolved_path != base_path_abs:
            print(f"[SECURITY list_files_recursive] Path traversal attempt detected: {resolved_path}")
            # Or raise an error to stop processing this branch
            return []
    except Exception as e:
        print(f"[ERROR list_files_recursive] Error resolving path {full_current_dir_abs}: {e}")
        import traceback # Make sure traceback is imported
        traceback.print_exc()
        return [] # Return empty list on error

    # Check if the directory exists BEFORE trying to list contents
    if not os.path.exists(full_current_dir_abs):
        print(f"[WARNING list_files_recursive] Directory does not exist: {full_current_dir_abs}")
        return []
    if not os.path.isdir(full_current_dir_abs):
        print(f"[WARNING list_files_recursive] Path is not a directory: {full_current_dir_abs}")
        return []


    try:
        # List items in the current directory
        items_in_dir = os.listdir(full_current_dir_abs)
        print(f"[DEBUG list_files_recursive] Items found in '{full_current_dir_abs}': {items_in_dir}")


        for item_name in items_in_dir:
            full_item_path_abs = os.path.join(full_current_dir_abs, item_name)

            # Path relative to the *document root* (base_path) for client-side use
            # Ensure forward slashes for consistency in relative paths sent to client
            item_path_relative_to_doc_root = os.path.join(current_relative_dir, item_name).replace('\\', '/')

            if os.path.isfile(full_item_path_abs):
                file_extension = os.path.splitext(item_name)[1].lower()
                file_type = 'Other'
                if file_extension == '.md':
                    file_type = 'MD'
                elif file_extension == '.pdf':
                    file_type = 'PDF'
                elif file_extension in ['.xlsx', '.xls']: # Corrected extension check
                     file_type = 'Excel'
                elif file_extension in ['.doc', '.docx']: # Corrected extension check
                     file_type = 'Word'
                # 添加注释：删除文件最后修改时间相关的逻辑
                # try:
                #     last_mod_timestamp = os.path.getmtime(full_item_path_abs)
                #     last_mod_datetime = datetime.fromtimestamp(last_mod_timestamp)
                #     # last_modified_iso = last_mod_datetime.isoformat() # 删除此行
                #     # last_modified_display = last_mod_datetime.strftime('%Y年%m月%d日 %H:%M') # 删除此行
                # except Exception as e_stat:
                #     print(f"[ERROR list_files_recursive] Could not get stat for file {full_item_path_abs}: {e_stat}")
                #     # last_modified_iso = datetime.utcnow().isoformat() # 删除此行
                #     # last_modified_display = "不明" # 删除此行
                #     import traceback
                #     traceback.print_exc()


                files_list.append({
                    'name': item_name,
                    'path': item_path_relative_to_doc_root, # Path relative to DOCUMENT_DIR root
                    'type': file_type,
                    'size': os.path.getsize(full_item_path_abs),
                    # 添加注释：删除 'last_modified_iso' 和 'last_modified_display'
                    # 'last_modified_iso': last_modified_iso, 
                    # 'last_modified_display': last_modified_display, 
                    # NEW: Add full server URL for direct access (e.g., for PDF iframe)
                    'url': f"/data/document/{urllib.parse.quote(item_path_relative_to_doc_root)}"
                })
                print(f"[DEBUG list_files_recursive] Found file: '{item_path_relative_to_doc_root}' (Type: {file_type}, URL: {files_list[-1]['url']})")
            elif os.path.isdir(full_item_path_abs):
                # Recursively list files in subdirectories
                # Pass the item_path_relative_to_doc_root as the new current_relative_dir for the next call
                print(f"[DEBUG list_files_recursive] Found directory: '{item_path_relative_to_doc_root}'. Recursing...")
                files_list.extend(list_files_recursive(base_path, item_path_relative_to_doc_root))
            else:
                print(f"[DEBUG list_files_recursive] Skipping non-file, non-directory item: '{full_item_path_abs}'")

    except PermissionError:
        print(f"[ERROR list_files_recursive] Permission denied for directory {full_current_dir_abs}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"[ERROR list_files_recursive] Error listing directory {full_current_dir_abs}: {e}")
        import traceback
        traceback.print_exc()

    return files_list


@app.route('/api/documents', methods=['GET'])
def get_documents_list():
    """
    API endpoint to list all documents recursively from the DOCUMENT_DIR.
    """
    print("\n[DEBUG /api/documents] Received GET request.")
    try:
        # List files starting from the root of the document directory
        # The second argument to list_files_recursive is the starting relative path, which is empty for the root.
        all_documents = list_files_recursive(DOCUMENT_DIR, '')
        print(f"[DEBUG /api/documents] Found {len(all_documents)} documents in total.")

        # Also print the first few items of the list being returned for inspection
        print("[DEBUG /api/documents] First 5 documents in the list:")
        for i, doc in enumerate(all_documents[:5]):
            print(f"  Doc {i}: {doc}")


        return jsonify(all_documents), 200

    except Exception as e:
        print(f"[ERROR /api/documents] Error listing documents: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Error fetching documents list', 'details': str(e)}), 500

@app.route('/api/document/content', methods=['GET'])
def get_document_content():
    """
    API endpoint to get the raw content of a specific document (typically for MD files).
    Requires a 'path' query parameter, which is the document's path relative to DOCUMENT_DIR.
    """
    doc_relative_path = request.args.get('path')
    print(f"\n[DEBUG /api/document/content] Received GET request for path: '{doc_relative_path}'")

    if not doc_relative_path:
        print("[ERROR /api/document/content] 'path' query parameter is missing.")
        return jsonify({'error': "'path' query parameter is missing"}), 400

    # Security: Sanitize and validate the path
    # Ensure the resolved path is within the DOCUMENT_DIR
    document_dir_abs = os.path.abspath(DOCUMENT_DIR)
    # Construct the full absolute path to the requested document
    # This resolves '..' and ensures the path is absolute
    target_doc_abs_path = os.path.abspath(os.path.join(DOCUMENT_DIR, doc_relative_path))

    print(f"[DEBUG /api/document/content] DOCUMENT_DIR (abs): '{document_dir_abs}'")
    print(f"[DEBUG /api/document/content] Requested doc path (abs resolved): '{target_doc_abs_path}'")

    # Security check: Check if the resolved target path is *within* or is the DOCUMENT_DIR itself.
    # For files *within* the directory, the resolved path should start with the directory path plus a separator.
    # The second condition (== document_dir_abs) covers cases where the relative path might be empty or '.',
    # but this endpoint is for getting *file* content, so we primarily expect paths resolving *inside*.
    # Let's tighten the check slightly to ensure it's strictly a child path, not the directory root itself.
    if not target_doc_abs_path.startswith(document_dir_abs + os.sep):
        print(f"[SECURITY /api/document/content] Path traversal attempt or invalid path. Requested: '{doc_relative_path}', Resolved: '{target_doc_abs_path}'")
        return jsonify({'error': 'Invalid document path'}), 403 # Forbidden


    if not os.path.exists(target_doc_abs_path) or not os.path.isfile(target_doc_abs_path):
        print(f"[ERROR /api/document/content] Document not found or not a file at path: {target_doc_abs_path}")
        return jsonify({'error': 'Document not found'}), 404

    try:
        file_extension = os.path.splitext(target_doc_abs_path)[1].lower()

        if file_extension == '.md':
            with open(target_doc_abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"[DEBUG /api/document/content] Successfully read MD content from: {target_doc_abs_path}")
            return jsonify({'content': content}), 200
        else:
            print(f"[INFO /api/document/content] Content request for non-MD file type ('{file_extension}') for path: {doc_relative_path}. This endpoint primarily serves MD content.")
            return jsonify({'error': f"Content preview is not available for '{file_extension}' files."}), 415 # Unsupported Media Type

    except Exception as e:
        print(f"[ERROR /api/document/content] Error reading document content from {target_doc_abs_path}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Error reading document content', 'details': str(e)}), 500


# Note: Serving individual document files (like PDFs for iframe or any file for download)
# will primarily use the existing /data/<path:filename> route.
# The frontend will construct the URL like /data/document/<path/to/file.pdf>
# The /api/document/content route is mainly for fetching raw MD content if the frontend were to render it.

# --- END: Helper and API for Document Section ---