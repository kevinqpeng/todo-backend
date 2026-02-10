"""
数据库迁移脚本：从旧表结构迁移到新表结构
用于生产环境保留数据的迁移
"""
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def migrate_db():
    """
    迁移数据库表结构
    - 将 INTEGER (0/1) 转换为 BOOLEAN
    - 将 BIGINT (Unix 时间戳) 转换为 TIMESTAMPTZ
    - 更新主键类型和索引
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

        print("开始迁移数据库...")

        # 1. 创建新表
        print("1. 创建新表 todos_new...")
        cur.execute('''
            CREATE TABLE todos_new (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                title TEXT NOT NULL CHECK (LENGTH(title) <= 255 AND LENGTH(title) > 0),
                description TEXT,
                completed BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        ''')

        # 2. 迁移数据
        print("2. 迁移数据...")
        cur.execute('''
            INSERT INTO todos_new (title, description, completed, created_at)
            SELECT
                title,
                description,
                CASE WHEN completed = 1 THEN TRUE ELSE FALSE END,  -- 将 INTEGER 转换为 BOOLEAN
                to_timestamp(created_at)  -- 将 Unix 时间戳转换为 TIMESTAMPTZ
            FROM todos
        ''')

        # 3. 创建索引
        print("3. 创建索引...")
        cur.execute('''
            CREATE INDEX idx_todos_completed ON todos_new (completed)
        ''')

        cur.execute('''
            CREATE INDEX idx_todos_created_at ON todos_new (created_at DESC)
        ''')

        # 4. 重命名表（在事务中执行）
        print("4. 重命名表...")
        cur.execute('ALTER TABLE todos RENAME TO todos_old')
        cur.execute('ALTER TABLE todos_new RENAME TO todos')

        conn.commit()
        print("✅ 数据库迁移成功！")

        # 5. 显示迁移统计
        cur.execute('SELECT COUNT(*) FROM todos')
        count = cur.fetchone()[0]
        print(f"✅ 已迁移 {count} 条记录")

        print("\n⚠️  旧表 'todos_old' 已保留，验证无误后可手动删除：")
        print("   DROP TABLE todos_old;")

        cur.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"❌ 数据库错误: {e}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        if conn:
            conn.rollback()
        return False

    return True

if __name__ == "__main__":
    print("=" * 60)
    print("PostgreSQL 数据库迁移脚本")
    print("=" * 60)
    print("\n⚠️  警告：此脚本将修改数据库表结构")
    print("建议先备份数据库！\n")

    response = input("确认继续迁移？(yes/no): ")
    if response.lower() == 'yes':
        migrate_db()
    else:
        print("已取消迁移")

