"""
Database initialization script for Todo App backend
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def init_db():
    """
    Initialize the database and create todos table if not exists
    """
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'todo_app'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '123456')
        )
        
        cur = conn.cursor()
        
        # Create todos table with PostgreSQL best practices
        cur.execute('''
            CREATE TABLE IF NOT EXISTS todos (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                title TEXT NOT NULL CHECK (LENGTH(title) <= 255 AND LENGTH(title) > 0),
                description TEXT,
                completed BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        ''')

        # Create indexes for common query patterns
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_todos_completed
            ON todos (completed)
        ''')

        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_todos_created_at
            ON todos (created_at DESC)
        ''')
        
        conn.commit()
        print("Database initialized successfully!")
        
        cur.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False
        
    return True

if __name__ == "__main__":
    init_db()