import os
import secrets
from flask import Flask, request, jsonify ## + jsonly - render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# add for api
from flask_cors import CORS
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager
# .envファイルから環境変数を読み込み
load_dotenv()
app = Flask(__name__) # Flaskアプリケーションのインスタンスを作成

# --- CORS設定 ---
# これで、全てのオリジンからのリクエストを許可 (開発中は)
CORS(app) 

# SECRET_KEYの設定（セキュリティ重要）
def get_secret_key():
    """
    環境に応じて適切なSECRET_KEYを取得する
    """
    # 1. 環境変数から取得を試行
    secret_key = os.getenv('SECRET_KEY')
    
    if secret_key:
        return secret_key
    
    # 2. 本番環境の場合はエラーで停止
    if os.getenv('FLASK_ENV') == 'production':
        raise RuntimeError(
            "❌ PRODUCTION ERROR: SECRET_KEY must be set in production environment!\n"
            "Set SECRET_KEY environment variable before starting the application."
        )
    
    # 3. 開発環境の場合は警告して自動生成
    print("⚠️  WARNING: SECRET_KEY not found in environment variables!")
    print("⚠️  Using auto-generated SECRET_KEY for development only.")
    print("⚠️  For production, set SECRET_KEY environment variable.")
    print("⚠️  Generate secure key with: python -c 'import secrets; print(secrets.token_hex(32))'")
    
    return secrets.token_hex(32)

# 環境変数からデータベースのURLを読み込む。存在しない場合はデフォルト値としてSQLiteを指定。
# これにより、PostgreSQLをセットアップする前でも開発を続けられる。
db_uri = os.getenv('DATABASE_URL', 'sqlite:///default.db')
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SECRET_KEY'] = get_secret_key() 
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///default.db').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # SQLAlchemyのイベントシステムを無効にし、オーバーヘッドを削減

app.config["JWT_SECRET_KEY"] = app.config['SECRET_KEY'] # SECRET_KEYをJWTの署名鍵としても利用
jwt = JWTManager(app)

db = SQLAlchemy(app)

# Flask-Loginの初期化
# login_manager = LoginManager()
# login_manager.init_app(app)
# login_manager.login_view = 'login'
# login_manager.login_message = 'ログインが必要です。'

# ユーザーモデル
class User(db.Model):
    # ユーザーテーブルの定義 ormなので同名なクラスを作成
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    tasks = db.relationship('Task', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# To-Doタスクのデータベースモデル
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Task {self.id}: {self.content}>'

@app.route('/api/login', methods=['POST'])
def login():
    """ログインAPI。成功するとアクセストークンを返す"""
    data = request.get_json()

    if not data:
        return jsonify({"msg": "JSONデータが必要です"}), 400

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"msg": "ユーザー名とパスワードは必須です"}), 400

    user = User.query.filter_by(username=username).first()
        
    if user and user.check_password(password):
        # ユーザーIDを元にアクセストークンを生成
        access_token = create_access_token(identity=user.id)
        return jsonify(access_token=access_token)
    
    return jsonify({"msg": "ユーザー名またはパスワードが間違っています"}), 401

@app.route('/api/register', methods=['POST'])
def register():
    """ユーザー登録API"""
    data = request.get_json()

    if not data:
        return jsonify({"msg": "JSONデータが必要です"}), 400

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"msg": "ユーザー名とパスワードは必須です"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"msg": "このユーザー名は既に使用されています"}), 409        

    # 新しいユーザーを作成
    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"msg": "ユーザー登録が成功しました"}), 201

@app.route('/api/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    current_user_id = get_jwt_identity()
    tasks=Task.query.filter_by(user_id=current_user_id).all()
    ## convert tasks to dict
    tasks_list=[
        {"id":task.id, "content":task.content, "done":task.done}
        for task in tasks
    ]
    return jsonify(tasks_list)

@app.route('/api/tasks', methods=['POST'])
@jwt_required()
def add_task():
    """新しいタスクを追加"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    task_content = data.get('content')

    if not task_content:
        return jsonify({"msg": "タスク内容がありません"}), 400

    new_task = Task(content=task_content, user_id=current_user_id)
    db.session.add(new_task)
    db.session.commit()

    return jsonify({"id": new_task.id, "content": new_task.content, "done": new_task.done}), 201

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    """タスクを削除"""
    current_user_id = get_jwt_identity()
    task = Task.query.filter_by(id=task_id, user_id=current_user_id).first()

    if task is None:
        return jsonify({"msg": "タスクが見つからないか、権限がありません"}), 404
    
    db.session.delete(task)
    db.session.commit()
    return jsonify({"msg": "タスクが削除されました"})

@app.route('/api/tasks/<int:task_id>/toggle', methods=['PUT'])
@jwt_required()
def toggle_task(task_id):
    """タスクの完了/未完了を切り替え"""
    current_user_id = get_jwt_identity()
    task = Task.query.filter_by(id=task_id, user_id=current_user_id).first()

    if task is None:
        return jsonify({"msg": "タスクが見つからないか、権限がありません"}), 404

    task.done = not task.done
    db.session.commit()
    return jsonify({"id": task.id, "content": task.content, "done": task.done})

# @app.route('/debug')
# def debug():
#     """
#     ORM の動作を確認するためのデバッグページ
#     """
#     debug_info = []
    
#     # User クラスの属性を確認
#     debug_info.append("=== User クラスの属性 ===")
#     user_attrs = [attr for attr in dir(User) if not attr.startswith('_')]
#     for attr in sorted(user_attrs):
#         debug_info.append(f"User.{attr}")
    
#     # query 属性の詳細
#     debug_info.append("\n=== query 属性の詳細 ===")
#     debug_info.append(f"User.query のタイプ: {type(User.query)}")
#     debug_info.append(f"User.query: {User.query}")
    
#     # 実際のクエリ例
#     debug_info.append("\n=== 実際のクエリ例 ===")
#     users = User.query.all()
#     for user in users:
#         debug_info.append(f"ユーザー: {user.username} (ID: {user.id})")
    
#     return "<pre>" + "\n".join(debug_info) + "</pre>"

# @app.route('/session-debug')
# @login_required
# def session_debug():
#     """
#     セッションの内容を確認するためのデバッグページ
#     """
#     import json
#     from flask import session
    
#     debug_info = []
    
#     debug_info.append("=== セッション情報 ===")
#     debug_info.append(f"現在のユーザーID: {current_user.id}")
#     debug_info.append(f"現在のユーザー名: {current_user.username}")
#     debug_info.append(f"認証状態: {current_user.is_authenticated}")
    
#     debug_info.append("\n=== セッションクッキーの内容 ===")
#     for key, value in session.items():
#         debug_info.append(f"{key}: {value}")
    
#     debug_info.append("\n=== SECRET_KEY情報 ===")
#     debug_info.append(f"SECRET_KEY の長さ: {len(app.config['SECRET_KEY'])} 文字")
#     debug_info.append(f"SECRET_KEY の最初の10文字: {app.config['SECRET_KEY'][:10]}...")
    
#     debug_info.append("\n=== セッションの仕組み ===")
#     debug_info.append("1. ログイン時: Flask-LoginがユーザーIDをセッションに保存")
#     debug_info.append("2. 暗号化: SECRET_KEYでセッションデータを署名・暗号化")
#     debug_info.append("3. クッキー: 暗号化されたデータをブラウザのクッキーに保存")
#     debug_info.append("4. リクエスト時: クッキーを復号化してユーザーを特定")
    
#     return "<pre>" + "\n".join(debug_info) + "</pre>"

# @app.route('/crypto-debug')
# @login_required 
# def crypto_debug():
#     """
#     暗号化・復号化のプロセスを詳しく確認
#     """
#     from flask import session, request
#     from itsdangerous import URLSafeTimedSerializer
    
#     debug_info = []
    
#     debug_info.append("=== 暗号化・復号化の詳細 ===")
    
#     # 1. 現在のセッションデータ（復号化済み）
#     debug_info.append("\n1. セッションデータ（復号化済み）:")
#     for key, value in session.items():
#         debug_info.append(f"   {key}: {value}")
    
#     # 2. ブラウザから送られてきた暗号化されたクッキー
#     session_cookie = request.cookies.get('session')
#     debug_info.append(f"\n2. 暗号化されたセッションクッキー:")
#     debug_info.append(f"   {session_cookie[:50]}..." if session_cookie else "   なし")
    
#     # 3. SECRET_KEYを使った署名の仕組み
#     debug_info.append(f"\n3. SECRET_KEYによる署名:")
#     debug_info.append(f"   SECRET_KEY: {app.config['SECRET_KEY'][:20]}...")
    
#     # 4. Flaskが使用している署名ライブラリの詳細
#     try:
#         serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
#         debug_info.append(f"\n4. 署名ライブラリ:")
#         debug_info.append(f"   使用ライブラリ: itsdangerous.URLSafeTimedSerializer")
#         debug_info.append(f"   アルゴリズム: HMAC-SHA1 (デフォルト)")
#     except Exception as e:
#         debug_info.append(f"   エラー: {e}")
    
#     # 5. 暗号化・復号化フロー
#     debug_info.append(f"\n5. 暗号化・復号化フロー:")
#     debug_info.append("   ログイン時:")
#     debug_info.append("   ① ユーザーID等をセッションデータに保存")
#     debug_info.append("   ② SECRET_KEYで署名・暗号化")
#     debug_info.append("   ③ 暗号化されたクッキーをブラウザに送信")
#     debug_info.append("")
#     debug_info.append("   リクエスト時:")
#     debug_info.append("   ① ブラウザから暗号化クッキーを受信")
#     debug_info.append("   ② SECRET_KEYで署名検証・復号化")
#     debug_info.append("   ③ セッションデータを復元")
#     debug_info.append("   ④ current_userとして利用可能")
    
#     # 6. セキュリティのポイント
#     debug_info.append(f"\n6. セキュリティのポイント:")
#     debug_info.append("   ✓ SECRET_KEYを知らないと復号化できない")
#     debug_info.append("   ✓ 改ざんされた場合は署名検証でエラー")
#     debug_info.append("   ✓ ブラウザには暗号化された状態で保存")
#     debug_info.append("   ✓ サーバー側でのみ復号化される")
    
#     return "<pre>" + "\n".join(debug_info) + "</pre>"

if __name__ == '__main__':
    # アプリケーションコンテキスト内でデータベーステーブルを作成
    with app.app_context():
        db.create_all()
        
        # 開発用の初期ユーザーを作成（存在しない場合のみ）
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("開発用ユーザーが作成されました:")
            print("ユーザー名: admin")
            print("パスワード: admin123")
        
        if not User.query.filter_by(username='test').first():
            test_user = User(username='test')
            test_user.set_password('test123')
            db.session.add(test_user)
            db.session.commit()
            print("テスト用ユーザーが作成されました:")
            print("ユーザー名: test")
            print("パスワード: test123")
    
    # 開発用サーバーを起動
    # host='0.0.0.0' にすると、同じネットワーク内の他のPCからもアクセスできます
    app.run(debug=True, host='0.0.0.0', port=5001)
