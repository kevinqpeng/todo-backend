"""
Database constraint test script for current BOOLEAN/TIMESTAMPTZ schema.
"""
import os
import uuid

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def _get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'todo_app'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', '123456')
    )


def test_constraint():
    conn = None
    cur = None
    case_id = f"constraint-{uuid.uuid4().hex[:8]}"

    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Test 1: Insert with completed=False should succeed.
        print("Test 1: Insert with completed=False")
        cur.execute(
            '''
            INSERT INTO todos (title, description, completed)
            VALUES (%s, %s, %s)
            RETURNING id, completed, created_at
            ''',
            (f'{case_id}-false', 'Description', False)
        )
        inserted_false = cur.fetchone()
        conn.commit()
        assert inserted_false[1] is False
        assert inserted_false[2] is not None
        print(f"✓ Success: Inserted id={inserted_false[0]} with completed=False")

        # Test 2: Insert with completed=True should succeed.
        print("\nTest 2: Insert with completed=True")
        cur.execute(
            '''
            INSERT INTO todos (title, description, completed)
            VALUES (%s, %s, %s)
            RETURNING id, completed, created_at
            ''',
            (f'{case_id}-true', 'Description', True)
        )
        inserted_true = cur.fetchone()
        conn.commit()
        assert inserted_true[1] is True
        assert inserted_true[2] is not None
        print(f"✓ Success: Inserted id={inserted_true[0]} with completed=True")

        # Test 3: Insert with completed=2 should fail.
        print("\nTest 3: Insert with completed=2 (should fail)")
        try:
            cur.execute(
                '''
                INSERT INTO todos (title, description, completed)
                VALUES (%s, %s, %s)
                ''',
                (f'{case_id}-invalid', 'Description', 2)
            )
            conn.commit()
            print("✗ Failed: Should have raised an error!")
            return False
        except psycopg2.Error as e:
            conn.rollback()
            print("✓ Success: Invalid BOOLEAN value was rejected")
            print(f"  Error: {e}")

        # Test 4: Ensure created_at is TIMESTAMPTZ by checking timezone metadata.
        print("\nTest 4: Validate created_at uses timestamp with time zone")
        cur.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name='todos' AND column_name='created_at'
            """
        )
        created_at_type = cur.fetchone()
        assert created_at_type and created_at_type[0] == 'timestamp with time zone'
        print("✓ Success: created_at type is TIMESTAMPTZ")

        # Cleanup test rows for this run.
        cur.execute("DELETE FROM todos WHERE title LIKE %s", (f'{case_id}-%',))
        conn.commit()

        print("\n✓ All tests passed!")
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error: {e}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    test_constraint()
