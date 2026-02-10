# Todo App Backend

Backend API for the Todo application with PostgreSQL database.

## Features
- RESTful API endpoints for todo management
- CRUD operations for todos
- Data persistence with PostgreSQL
- PostgreSQL best practices implementation
- Automatic timezone handling with TIMESTAMPTZ
- Type-safe boolean fields
- Optimized indexes for common queries

## Prerequisites
- Python 3.8+
- PostgreSQL 12+

## Database Design

本项目采用 PostgreSQL 最佳实践设计数据库表结构：

### 表结构
```sql
CREATE TABLE todos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title TEXT NOT NULL CHECK (LENGTH(title) <= 255 AND LENGTH(title) > 0),
    description TEXT,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 索引
- `idx_todos_completed` - 优化按完成状态查询
- `idx_todos_created_at` - 优化按时间排序

### 关键特性
- ✅ 使用 `BIGINT GENERATED ALWAYS AS IDENTITY` 作为主键
- ✅ 使用 `TEXT` 类型替代 `VARCHAR(n)`
- ✅ 使用 `BOOLEAN` 类型表示完成状态
- ✅ 使用 `TIMESTAMPTZ` 自动处理时区
- ✅ 为常见查询路径创建索引

## Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/MaxPeng324/todo-backend.git
   cd todo-backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` file and set your database credentials:
   ```
   DB_HOST=localhost
   DB_NAME=todo_app
   DB_USER=your_username
   DB_PASSWORD=your_password
   ```

5. Initialize the database:

   **开发环境（删除所有数据）：**
   ```bash
   python rebuild_db.py
   ```

   **生产环境（保留现有数据）：**
   ```bash
   python migrate_db.py
   ```

   或者使用 init_db.py（首次安装）：
   ```bash
   python init_db.py
   ```

6. Run the application:
   ```bash
   python app.py
   ```

The backend will be running on `http://localhost:5001`

## API Endpoints

### 响应格式

所有 API 响应遵循统一格式：

```json
{
  "code": 200,
  "message": "ok",
  "data": { ... }
}
```

### 端点列表

#### GET /api/todos
获取所有待办事项（按创建时间降序）

**响应示例：**
```json
{
  "code": 200,
  "message": "ok",
  "data": [
    {
      "id": 1,
      "title": "测试任务",
      "description": "任务描述",
      "completed": false,
      "created_at": "2026-02-04T10:00:00+08:00"
    }
  ]
}
```

#### POST /api/todos
创建新的待办事项

**请求体：**
```json
{
  "title": "任务标题",
  "description": "任务描述（可选）"
}
```

**响应：** 返回创建的待办事项（201 Created）

#### PUT /api/todos/<id>
更新待办事项

**请求体：**
```json
{
  "title": "更新的标题",
  "description": "更新的描述",
  "completed": true
}
```

**注意：** `completed` 字段必须是布尔值（`true` 或 `false`）

#### DELETE /api/todos/<id>
删除待办事项

**响应：** 返回被删除的待办事项

#### GET /
健康检查

## 数据类型说明

### completed 字段
- **类型：** `BOOLEAN`
- **值：** `true`（已完成）或 `false`（未完成）
- **默认值：** `false`

### created_at 字段
- **类型：** `TIMESTAMPTZ`（带时区的时间戳）
- **格式：** ISO 8601 字符串（例如：`2026-02-04T10:00:00+08:00`）
- **自动生成：** 数据库自动生成，无需手动传入

## Environment Variables

- `DB_HOST`: Database host (default: localhost)
- `DB_NAME`: Database name (default: todo_app)
- `DB_USER`: Database user (default: postgres)
- `DB_PASSWORD`: Database password (default: password)
- `PORT`: Server port (default: 5001)

## Frontend Integration

前端需要适配以下数据格式变化：

1. **completed 字段**：从 `0/1` 改为 `true/false`
2. **created_at 字段**：从 Unix 时间戳改为 ISO 8601 字符串

示例前端代码：
```javascript
// 解析时间字符串
const createdDate = new Date(todo.created_at);

// 显示本地时间
const localTime = createdDate.toLocaleString();
```

## 数据库迁移

### 从旧版本迁移

如果您从旧版本（使用 INTEGER 和 BIGINT 时间戳）升级，请使用：

```bash
python migrate_db.py
```

此脚本会：
1. 创建新表结构
2. 迁移现有数据（INTEGER → BOOLEAN，Unix 时间戳 → TIMESTAMPTZ）
3. 创建索引
4. 保留旧表作为备份（`todos_old`）

### 重建数据库（开发环境）

如果不需要保留数据：

```bash
python rebuild_db.py
```

⚠️ **警告：** 此操作会删除所有现有数据！

## 性能优化

本项目实施了以下性能优化：

1. **索引优化**
   - `idx_todos_completed` - 加速按完成状态筛选
   - `idx_todos_created_at` - 加速按时间排序

2. **存储优化**
   - BOOLEAN 比 INTEGER 节省 75% 空间
   - TIMESTAMPTZ 提供自动时区转换

3. **查询优化**
   - 使用索引避免全表扫描
   - 降序索引优化 `ORDER BY created_at DESC`

## 文档

详细的设计文档请参考：
- [PostgreSQL 最佳实践重新设计](docs/plans/2026-02-04-postgresql-best-practices-redesign.md)
- [时间戳存储优化设计](docs/plans/2026-02-04-timestamp-storage-design.md)

## License

MIT
