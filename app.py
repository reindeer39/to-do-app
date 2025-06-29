import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

# Flaskアプリケーションのインスタンスを作成
app = Flask(__name__)

# 環境変数からデータベースのURLを読み込む。存在しない場合はデフォルト値としてSQLiteを指定。
# これにより、PostgreSQLをセットアップする前でも開発を続けられる。
db_uri = os.getenv('DATABASE_URL', 'sqlite:///default.db')
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # SQLAlchemyのイベントシステムを無効にし、オーバーヘッドを削減

db = SQLAlchemy(app)

# To-Doタスクのデータベースモデル
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Task {self.id}: {self.content}>'

@app.route('/')
def index():
    """
    トップページ。タスク一覧を表示します。
    """
    # データベースからタスクを取得
    tasks = Task.query.all()
    # タスクのリストをそのまま渡します
    return render_template('index.html', tasks=tasks)

@app.route('/add', methods=['POST'])
def add():
    """
    フォームから送信された新しいタスクを追加します。
    """
    task_content = request.form['task_content']
    if task_content: # 空のタスクは追加しない
        new_task = Task(content=task_content)
        db.session.add(new_task)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:task_id>')
def delete(task_id):
    """
    指定されたIDのタスクを削除します。
    """
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/toggle/<int:task_id>')
def toggle(task_id):
    """
    指定されたIDのタスクの完了/未完了を切り替えます。
    """
    task = Task.query.get_or_404(task_id)
    task.done = not task.done
    db.session.commit()
    return redirect(url_for('index'))


if __name__ == '__main__':
    # アプリケーションコンテキスト内でデータベーステーブルを作成
    with app.app_context():
        db.create_all()
    
    # 開発用サーバーを起動
    # host='0.0.0.0' にすると、同じネットワーク内の他のPCからもアクセスできます
    app.run(debug=True, host='0.0.0.0')
