"""
Drop todos table
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def drop_table():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'todo_app'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '123456')
        )

        cur = conn.cursor()
        cur.execute('DROP TABLE IF EXISTS todos;')
        conn.commit()
        print("Table dropped successfully!")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")
        return False

    return True

if __name__ == "__main__":
    drop_table()
