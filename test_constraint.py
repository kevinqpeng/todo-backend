"""
Test database CHECK constraint for completed field
"""
import psycopg2
import os
from dotenv import load_dotenv
import time

load_dotenv()

def test_constraint():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'todo_app'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '123456')
        )

        cur = conn.cursor()

        # Test 1: Insert with completed=0 (should succeed)
        print("Test 1: Insert with completed=0")
        cur.execute(
            'INSERT INTO todos (title, description, completed, created_at) VALUES (%s, %s, %s, %s) RETURNING id',
            ('Test 0', 'Description', 0, int(time.time()))
        )
        result = cur.fetchone()
        print(f"✓ Success: Inserted todo with id={result[0]}, completed=0")
        conn.commit()

        # Test 2: Insert with completed=1 (should succeed)
        print("\nTest 2: Insert with completed=1")
        cur.execute(
            'INSERT INTO todos (title, description, completed, created_at) VALUES (%s, %s, %s, %s) RETURNING id',
            ('Test 1', 'Description', 1, int(time.time()))
        )
        result = cur.fetchone()
        print(f"✓ Success: Inserted todo with id={result[0]}, completed=1")
        conn.commit()

        # Test 3: Insert with completed=2 (should fail)
        print("\nTest 3: Insert with completed=2 (should fail)")
        try:
            cur.execute(
                'INSERT INTO todos (title, description, completed, created_at) VALUES (%s, %s, %s, %s)',
                ('Test 2', 'Description', 2, int(time.time()))
            )
            conn.commit()
            print("✗ Failed: Should have raised an error!")
        except psycopg2.IntegrityError as e:
            conn.rollback()
            print(f"✓ Success: CHECK constraint prevented invalid value")
            print(f"  Error: {e}")

        # Test 4: Update to completed=2 (should fail)
        print("\nTest 4: Update to completed=2 (should fail)")
        try:
            cur.execute('UPDATE todos SET completed = 2 WHERE id = 1')
            conn.commit()
            print("✗ Failed: Should have raised an error!")
        except psycopg2.IntegrityError as e:
            conn.rollback()
            print(f"✓ Success: CHECK constraint prevented invalid value")
            print(f"  Error: {e}")

        cur.close()
        conn.close()

        print("\n✓ All tests passed!")

    except Exception as e:
        print(f"Error: {e}")
        return False

    return True

if __name__ == "__main__":
    test_constraint()
