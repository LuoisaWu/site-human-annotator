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
import json

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

def parse_labels(value):
    if not value:
        return []
    if isinstance(value, str):
        v = value.strip()
        if v.startswith('[') and v.endswith(']'):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [x for x in parsed if isinstance(x, str) and x]
            except Exception:
                pass
        return [value]
    if isinstance(value, list):
        return [x for x in value if isinstance(x, str) and x]
    return []

def extract_other_text(labels):
    for k in labels or []:
        if isinstance(k, str) and k.startswith('Other:'):
            return k[len('Other:'):].strip()
    return ''

def format_labels(labels):
    parts = []
    for k in labels:
        if isinstance(k, str) and k.startswith('Other:'):
            cn = CATEGORIES.get('Other', 'Other')
            custom = k[len('Other:'):].strip()
            if custom:
                parts.append(f"Other({cn}): {custom}")
            else:
                parts.append(f"Other({cn})")
            continue
        cn = CATEGORIES.get(k, k)
        if cn == k:
            parts.append(k)
        else:
            parts.append(f"{k}({cn})")
    return "; ".join(parts)

@login_manager.user_loader
def load_user(user_id):
    if app.config.get('DB_DISABLED'):
        return None
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            if app.config.get('DB_DISABLED'):
                flash('数据库未配置，无法登录。请先在 Vercel 环境变量中设置 DATABASE_URL 并完成 Supabase 建表。', 'danger')
                return redirect(url_for('login'))
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
            if app.config.get('DB_DISABLED'):
                flash('数据库未配置，无法注册。请先在 Vercel 环境变量中设置 DATABASE_URL 并完成 Supabase 建表。', 'danger')
                return redirect(url_for('register'))
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
    try:
        page = request.args.get('page', 1, type=int)
        mode = request.args.get('mode', 'sequential')

        user_other_texts = {}
        user_annotations = {
            a.website_id: parse_labels(a.label)
            for a in Annotation.query.filter_by(user_id=current_user.id).all()
        }
        for website_id, labels in list(user_annotations.items()):
            other_text = extract_other_text(labels)
            if other_text:
                user_other_texts[website_id] = other_text
                base = [x for x in labels if not (isinstance(x, str) and x.startswith('Other:'))]
                base.append('Other')
                user_annotations[website_id] = list(dict.fromkeys([x for x in base if isinstance(x, str) and x]))

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
            user_annotations=user_annotations,
            user_other_texts=user_other_texts
        )
    except Exception as e:
        return render_template('db_error.html', error=str(e))

@app.route('/annotate', methods=['POST'])
@login_required
def annotate():
    try:
        data = request.get_json(silent=True) or {}

        website_id = data.get('website_id')
        labels = data.get('labels', None)
        label = data.get('label', None)
        other_text = data.get('other_text', '')

        if website_id is None:
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

        if labels is None:
            labels = [label] if label else []

        if not isinstance(labels, list):
            return jsonify({
                'status': 'error',
                'message': 'Invalid labels'
            }), 400

        labels = [x for x in labels if isinstance(x, str) and x]
        labels = list(dict.fromkeys(labels))

        if 'Other' in labels:
            t = (other_text or '').strip()
            if not t:
                return jsonify({'status': 'error', 'message': 'Other label required'}), 400
            labels = [x for x in labels if x != 'Other']
            labels.append(f"Other:{t}")

        invalid = [
            x for x in labels
            if (x not in CATEGORIES) and not (isinstance(x, str) and x.startswith('Other:') and x[len('Other:'):].strip())
        ]
        if invalid:
            return jsonify({
                'status': 'error',
                'message': 'Invalid label'
            }), 400

        annotation = Annotation.query.filter_by(
            website_id=website_id,
            user_id=current_user.id
        ).first()

        if not labels:
            if annotation:
                db.session.delete(annotation)
                db.session.commit()
            return jsonify({'status': 'success'})

        serialized = json.dumps(labels, ensure_ascii=False)

        if annotation:
            annotation.label = serialized
            annotation.timestamp = datetime.utcnow()
        else:
            annotation = Annotation(
                website_id=website_id,
                user_id=current_user.id,
                label=serialized
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

@app.route('/export')
@login_required
def export_csv():
    if app.config.get('DB_DISABLED'):
        return jsonify({'status': 'error', 'message': 'DATABASE_URL is not set'}), 500

    query = db.session.query(
        User.username.label('annotator'),
        Website.domain,
        Website.title,
        Website.icp,
        Website.server,
        Annotation.label,
        Annotation.timestamp
    ).join(Website, Annotation.website_id == Website.id) \
     .join(User, Annotation.user_id == User.id).all()

    def generate():
        yield 'Annotator,Domain,Title,ICP,Server,Label,Timestamp\n'
        for row in query:
            title = f'"{row.title}"' if row.title else ''
            domain = row.domain or ''
            icp = row.icp or ''
            server = row.server or ''
            label = ";".join(parse_labels(row.label))
            timestamp = row.timestamp.strftime('%Y-%m-%d %H:%M:%S') if row.timestamp else ''
            yield f'{row.annotator},{domain},{title},{icp},{server},{label},{timestamp}\n'

    return Response(
        generate(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=annotations.csv'}
    )

@app.route('/dashboard')
@login_required
def dashboard():
    if app.config.get('DB_DISABLED'):
        return render_template('db_error.html', error='DATABASE_URL is not set')

    total_annotations = Annotation.query.count()
    total_users = User.query.count()
    total_websites = Website.query.count()

    user_stats = db.session.query(
        User.username,
        func.count(Annotation.id).label('count')
    ).outerjoin(Annotation).group_by(User.id).all()

    recent_annotations_raw = db.session.query(
        User.username,
        Website.domain,
        Annotation.label,
        Annotation.timestamp
    ).join(User, Annotation.user_id == User.id) \
     .join(Website, Annotation.website_id == Website.id) \
     .order_by(Annotation.timestamp.desc()).limit(50).all()

    recent_annotations = [
        {
            'username': r.username,
            'domain': r.domain,
            'labels': parse_labels(r.label),
            'label_display': format_labels(parse_labels(r.label)),
            'timestamp': r.timestamp
        }
        for r in recent_annotations_raw
    ]

    return render_template(
        'dashboard.html',
        total_annotations=total_annotations,
        total_users=total_users,
        total_websites=total_websites,
        user_stats=user_stats,
        recent_annotations=recent_annotations,
        categories=CATEGORIES
    )

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if app.config.get('DB_DISABLED'):
        return render_template('db_error.html', error='DATABASE_URL is not set')

    if not getattr(current_user, 'is_admin', False):
        flash('您没有管理员权限。', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        file = request.files.get('csv_file')
        clear_existing = request.form.get('clear_existing') == 'yes'

        if not file or not file.filename.endswith('.csv'):
            flash('请上传有效的CSV文件 (.csv)。', 'danger')
            return redirect(url_for('admin'))

        try:
            df = pd.read_csv(file)
            columns = df.columns.tolist()

            def get_col(candidates):
                for c in candidates:
                    if c in columns:
                        return c
                return None

            domain_col = get_col(['Domain', 'domain', 'url', 'URL'])
            title_col = get_col(['Title', 'title'])
            icp_col = get_col(['ICP', 'icp'])
            server_col = get_col(['Server', 'server'])
            screenshot_col = get_col(['Screenshot_Path', 'screenshot_path', 'screenshot', 'Screenshot'])

            if not domain_col:
                flash('CSV文件缺少 Domain / URL 列，导入失败。', 'danger')
                return redirect(url_for('admin'))

            if clear_existing:
                Annotation.query.delete()
                Website.query.delete()
                db.session.commit()

            websites_to_add = []
            for _, row in df.iterrows():
                domain = str(row[domain_col]) if pd.notna(row[domain_col]) else ''
                if not domain:
                    continue

                title = str(row[title_col]) if title_col and pd.notna(row[title_col]) else ''
                icp = str(row[icp_col]) if icp_col and pd.notna(row[icp_col]) else ''
                server = str(row[server_col]) if server_col and pd.notna(row[server_col]) else ''
                screenshot_path = str(row[screenshot_col]) if screenshot_col and pd.notna(row[screenshot_col]) else ''

                websites_to_add.append(Website(
                    domain=domain,
                    title=title,
                    icp=icp,
                    server=server,
                    screenshot_path=screenshot_path
                ))

            db.session.add_all(websites_to_add)
            db.session.commit()
            flash(f'成功导入 {len(websites_to_add)} 个待标注网站！', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'导入时发生错误: {str(e)}', 'danger')

        return redirect(url_for('admin'))

    return render_template('admin.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
