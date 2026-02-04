from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# 时区转换辅助函数
def convert_to_beijing_time(utc_time):
    """将 UTC 时间转换为北京时间"""
    if utc_time is None:
        return None

    # 如果是 naive datetime（没有时区信息），假设它是 UTC
    if utc_time.tzinfo is None:
        utc_time = pytz.utc.localize(utc_time)

    # 转换为北京时间
    beijing_tz = pytz.timezone('Asia/Shanghai')
    beijing_time = utc_time.astimezone(beijing_tz)

    # 返回格式化的字符串
    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')

def format_todo(todo):
    """格式化 todo 对象，将时间转换为北京时间"""
    todo_dict = dict(todo)
    if 'created_at' in todo_dict and todo_dict['created_at']:
        todo_dict['created_at'] = convert_to_beijing_time(todo_dict['created_at'])
    return todo_dict

# Unified response format
def success_response(data=None, message='ok', code=200):
    """统一成功响应格式"""
    return jsonify({
        'code': code,
        'message': message,
        'data': data
    }), code

def error_response(message, code=400, data=None):
    """统一错误响应格式"""
    return jsonify({
        'code': code,
        'message': message,
        'data': data
    }), code

# Database connection
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'todo_app'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', '123456')
    )
    return conn

# Create todos table if not exists
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            completed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()

@app.route('/api/todos', methods=['GET'])
def get_todos():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute('SELECT * FROM todos ORDER BY created_at DESC')
        todos = cur.fetchall()

        cur.close()
        conn.close()

        return success_response(data=[format_todo(todo) for todo in todos])
    except Exception as e:
        return error_response(message=f'获取待办事项列表失败: {str(e)}', code=500)

@app.route('/api/todos', methods=['POST'])
def create_todo():
    try:
        data = request.get_json()

        title = data.get('title')
        description = data.get('description', '')

        if not title:
            return error_response(message='标题不能为空', code=400)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            'INSERT INTO todos (title, description) VALUES (%s, %s) RETURNING *',
            (title, description)
        )
        new_todo = cur.fetchone()

        conn.commit()
        cur.close()
        conn.close()

        return success_response(data=format_todo(new_todo), message='创建待办事项成功', code=201)
    except Exception as e:
        return error_response(message=f'创建待办事项失败: {str(e)}', code=500)

@app.route('/api/todos/<int:id>', methods=['PUT'])
def update_todo(id):
    try:
        data = request.get_json()

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check if todo exists
        cur.execute('SELECT * FROM todos WHERE id = %s', (id,))
        todo = cur.fetchone()
        if not todo:
            cur.close()
            conn.close()
            return error_response(message='待办事项不存在', code=404)

        # Update the todo
        title = data.get('title', todo['title'])
        description = data.get('description', todo['description'])
        completed = data.get('completed', todo['completed'])

        cur.execute(
            '''UPDATE todos SET title=%s, description=%s, completed=%s
               WHERE id = %s RETURNING *''',
            (title, description, completed, id)
        )
        updated_todo = cur.fetchone()

        conn.commit()
        cur.close()
        conn.close()

        return success_response(data=format_todo(updated_todo), message='更新待办事项成功')
    except Exception as e:
        return error_response(message=f'更新待办事项失败: {str(e)}', code=500)

@app.route('/api/todos/<int:id>', methods=['DELETE'])
def delete_todo(id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check if todo exists
        cur.execute('SELECT * FROM todos WHERE id = %s', (id,))
        todo = cur.fetchone()
        if not todo:
            cur.close()
            conn.close()
            return error_response(message='待办事项不存在', code=404)

        cur.execute('DELETE FROM todos WHERE id = %s RETURNING *', (id,))
        deleted_todo = cur.fetchone()

        conn.commit()
        cur.close()
        conn.close()

        return success_response(data=format_todo(deleted_todo), message='删除待办事项成功')
    except Exception as e:
        return error_response(message=f'删除待办事项失败: {str(e)}', code=500)

@app.route('/', methods=['GET'])
def health_check():
    return success_response(data={'status': 'running'}, message='后端服务运行正常')

if __name__ == '__main__':
    init_db()  # Initialize database on startup
    port = int(os.getenv('PORT', '5001'))
    app.run(debug=True, host='0.0.0.0', port=port)
