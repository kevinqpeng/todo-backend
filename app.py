from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database connection
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'todo_app'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'password')
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
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute('SELECT * FROM todos ORDER BY created_at DESC')
    todos = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return jsonify([dict(todo) for todo in todos])

@app.route('/api/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    
    title = data.get('title')
    description = data.get('description', '')
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
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
    
    return jsonify(dict(new_todo)), 201

@app.route('/api/todos/<int:id>', methods=['PUT'])
def update_todo(id):
    data = request.get_json()
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check if todo exists
    cur.execute('SELECT * FROM todos WHERE id = %s', (id,))
    todo = cur.fetchone()
    if not todo:
        cur.close()
        conn.close()
        return jsonify({'error': 'Todo not found'}), 404
    
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
    
    return jsonify(dict(updated_todo))

@app.route('/api/todos/<int:id>', methods=['DELETE'])
def delete_todo(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check if todo exists
    cur.execute('SELECT * FROM todos WHERE id = %s', (id,))
    todo = cur.fetchone()
    if not todo:
        cur.close()
        conn.close()
        return jsonify({'error': 'Todo not found'}), 404
    
    cur.execute('DELETE FROM todos WHERE id = %s RETURNING *', (id,))
    deleted_todo = cur.fetchone()
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'message': 'Todo deleted successfully'})

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'Backend is running'})

if __name__ == '__main__':
    init_db()  # Initialize database on startup
    app.run(debug=True, host='0.0.0.0', port=5000)