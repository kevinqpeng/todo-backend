"""
数据库重建脚本：删除旧表并创建新表
⚠️ 警告：此脚本会删除所有现有数据！仅用于开发环境
"""
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def rebuild_db():
    """
    删除旧表并创建新表（不保留数据）
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

        print("开始重建数据库...")

        # 1. 删除旧表
        print("1. 删除旧表...")
        cur.execute('DROP TABLE IF EXISTS todos CASCADE')

        # 2. 创建新表
        print("2. 创建新表...")
        cur.execute('''
            CREATE TABLE todos (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                title TEXT NOT NULL CHECK (LENGTH(title) <= 255 AND LENGTH(title) > 0),
                description TEXT,
                completed BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        ''')

        # 3. 创建索引
        print("3. 创建索引...")
        cur.execute('''
            CREATE INDEX idx_todos_completed ON todos (completed)
        ''')

        cur.execute('''
            CREATE INDEX idx_todos_created_at ON todos (created_at DESC)
        ''')

        conn.commit()
        print("✅ 数据库重建成功！")

        cur.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"❌ 数据库错误: {e}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"❌ 重建失败: {e}")
        if conn:
            conn.rollback()
        return False

    return True

if __name__ == "__main__":
    print("=" * 60)
    print("PostgreSQL 数据库重建脚本")
    print("=" * 60)
    print("\n⚠️  警告：此脚本将删除所有现有数据！")
    print("仅用于开发环境，生产环境请使用 migrate_db.py\n")

    response = input("确认删除所有数据并重建表？(yes/no): ")
    if response.lower() == 'yes':
        rebuild_db()
    else:
        print("已取消重建")
