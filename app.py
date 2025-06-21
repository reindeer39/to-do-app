from flask import Flask, render_template, request, redirect, url_for

# Flaskアプリケーションのインスタンスを作成
app = Flask(__name__)

# To-Doタスクを保存するためのリスト（簡易的なデータベースの代わり）
# { 'content': 'タスクの内容', 'done': False } という辞書のリストになります
tasks = []

@app.route('/')
def index():
    """
    トップページ。タスク一覧を表示します。
    """
    # enumerateを使って、テンプレート側でインデックス番号を使えるようにします
    return render_template('index.html', tasks=enumerate(tasks))

@app.route('/add', methods=['POST'])
def add():
    """
    フォームから送信された新しいタスクを追加します。
    """
    task_content = request.form['task_content']
    if task_content: # 空のタスクは追加しない
        tasks.append({'content': task_content, 'done': False})
    return redirect(url_for('index'))

@app.route('/delete/<int:task_id>')
def delete(task_id):
    """
    指定されたIDのタスクを削除します。
    """
    if 0 <= task_id < len(tasks):
        tasks.pop(task_id)
    return redirect(url_for('index'))

@app.route('/toggle/<int:task_id>')
def toggle(task_id):
    """
    指定されたIDのタスクの完了/未完了を切り替えます。
    """
    if 0 <= task_id < len(tasks):
        tasks[task_id]['done'] = not tasks[task_id]['done']
    return redirect(url_for('index'))


if __name__ == '__main__':
    # 開発用サーバーを起動
    # host='0.0.0.0' にすると、同じネットワーク内の他のPCからもアクセスできます
    app.run(debug=True, host='0.0.0.0')
