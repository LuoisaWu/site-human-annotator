import sys
import os
from urllib.parse import urlparse, quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import csv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql.expression import func
from sqlalchemy.pool import NullPool
from sqlalchemy import text
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import traceback

load_dotenv()

from models import db, User, Website, Annotation

base_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, 
            template_folder=os.path.join(base_dir, 'templates'),
            static_folder=os.path.join(base_dir, 'static'))

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_here')

db_url = os.environ.get("DATABASE_URL")
db_disabled = False
if not db_url:
    db_disabled = True
    db_url = "sqlite:///:memory:"
app.config['DB_DISABLED'] = db_disabled

# URL-encode password 中的特殊字符（如 &, *, % 等）
parsed = urlparse(db_url)
if parsed.password:
    encoded_password = quote(parsed.password, safe='')
    userinfo = f"{parsed.username}:{encoded_password}" if parsed.username else f":{encoded_password}"
    netloc = f"{userinfo}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    parsed = parsed._replace(netloc=netloc)
    db_url = parsed.geturl()

# 强制转换连接字符串前缀以适配 psycopg3
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif db_url.startswith('postgresql://') and not db_url.startswith('postgresql+psycopg://'):
    db_url = db_url.replace('postgresql://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if not db_disabled and db_url.startswith("postgresql+psycopg://"):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "poolclass": NullPool,
        "connect_args": {
            "sslmode": "require",
        }
    }

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.unauthorized_handler
def unauthorized():
    if request.is_json:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    return redirect(url_for('login'))

@app.route('/healthz')
def healthz():
    if app.config.get('DB_DISABLED'):
        return jsonify({'ok': False, 'error': 'DATABASE_URL is not set'}), 500
    try:
        db.session.execute(text("select 1"))
        return jsonify({'ok': True}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/config')
def config():
    return jsonify({'db_disabled': bool(app.config.get('DB_DISABLED'))}), 200

@app.route('/whoami')
def whoami():
    if current_user.is_authenticated:
        return jsonify({'authenticated': True, 'user_id': current_user.id, 'username': current_user.username}), 200
    return jsonify({'authenticated': False}), 200

CATEGORIES = {
    "Ecommerce": "电商",
    "News": "新闻",
    "Corporate": "企业官网",
    "Education": "教育",
    "Forum": "论坛",
    "SocialMedia": "社交媒体",
    "CDN": "CDN",
    "CloudService": "云服务",
    "Technology": "科技",
    "AITool": "AI工具",
    "Government": "政府",
    "Entertainment": "娱乐",
    "Finance": "金融",
    "Adult": "成人",
    "Gambling": "博彩",
    "SearchEngine": "搜索引擎",
    "Blog": "博客",
    "DeveloperPlatform": "开发者平台",
    "Hosting": "托管服务",
    "Other": "其他",
    "Unsure": "不确定"
}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')

            user = User.query.filter_by(username=username).first()

            if user and check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash('用户名或密码错误。', 'danger')

        except Exception as e:
            error_msg = f"登录失败: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)

            flash(f'登录遇到问题，请联系开发者: {str(e)}', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')

            user = User.query.filter_by(username=username).first()

            if user:
                flash('用户名已存在。', 'danger')
                return redirect(url_for('register'))

            is_first_user = User.query.count() == 0
            is_admin = is_first_user or username.lower() == 'admin'

            new_user = User(
                username=username,
                password=generate_password_hash(password, method='pbkdf2:sha256'),
                is_admin=is_admin
            )

            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)

            return redirect(url_for('index'))

        except Exception as e:
            db.session.rollback()

            error_msg = f"注册失败: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)

            flash(f'注册遇到问题，请截图给开发者: {str(e)}', 'danger')

            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    mode = request.args.get('mode', 'sequential')

    user_annotations = {
        a.website_id: a.label
        for a in Annotation.query.filter_by(user_id=current_user.id).all()
    }

    if mode == 'random':
        websites = Website.query.order_by(func.random()).limit(20).all()
        pagination = None
    else:
        pagination = Website.query.paginate(
            page=page,
            per_page=20,
            error_out=False
        )

        websites = pagination.items

    return render_template(
        'index.html',
        websites=websites,
        categories=CATEGORIES,
        pagination=pagination,
        mode=mode,
        user_annotations=user_annotations
    )

@app.route('/annotate', methods=['POST'])
@login_required
def annotate():
    try:
        data = request.get_json(silent=True) or {}

        website_id = data.get('website_id')
        label = data.get('label')

        if website_id is None or not label:
            return jsonify({
                'status': 'error',
                'message': 'Invalid data'
            }), 400

        try:
            website_id = int(website_id)
        except Exception:
            return jsonify({
                'status': 'error',
                'message': 'Invalid website_id'
            }), 400

        if label not in CATEGORIES:
            return jsonify({
                'status': 'error',
                'message': 'Invalid label'
            }), 400

        annotation = Annotation.query.filter_by(
            website_id=website_id,
            user_id=current_user.id
        ).first()

        if annotation:
            annotation.label = label
            annotation.timestamp = datetime.utcnow()
        else:
            annotation = Annotation(
                website_id=website_id,
                user_id=current_user.id,
                label=label
            )

            db.session.add(annotation)

        db.session.commit()

        return jsonify({
            'status': 'success'
        })

    except Exception as e:
        db.session.rollback()

        error_msg = f"标注保存失败: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)

        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
