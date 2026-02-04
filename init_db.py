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
        
        # Create todos table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS todos (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                completed INTEGER DEFAULT 0 CHECK (completed IN (0, 1)),
                created_at BIGINT NOT NULL
            )
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