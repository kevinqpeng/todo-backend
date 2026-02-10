# PostgreSQL 最佳实践数据库重新设计

**日期**: 2026-02-04
**状态**: 提议中

## 概述

根据 PostgreSQL 最佳实践重新设计 Todo 应用的数据库表结构，提升性能、可维护性和数据完整性。

## 设计原则

遵循以下 PostgreSQL 核心规则：
1. 使用 `BIGINT GENERATED ALWAYS AS IDENTITY` 作为主键
2. 使用 `TEXT` 类型替代 `VARCHAR(n)`
3. 使用 `BOOLEAN` 类型表示真/假值
4. 使用 `TIMESTAMPTZ` 存储时间戳（带时区）
5. 为所有语义上必需的字段添加 `NOT NULL` 约束
6. 为常见查询路径创建索引

## 表结构设计

### 优化后的 todos 表

```sql
CREATE TABLE IF NOT EXISTS todos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title TEXT NOT NULL CHECK (LENGTH(title) <= 255 AND LENGTH(title) > 0),
    description TEXT,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 索引设计

```sql
-- 按完成状态查询的索引（例如：查询所有未完成的任务）
CREATE INDEX IF NOT EXISTS idx_todos_completed
ON todos (completed);

-- 按创建时间排序的索引（降序，最新的在前）
CREATE INDEX IF NOT EXISTS idx_todos_created_at
ON todos (created_at DESC);
```

## 关键改进说明

### 1. 主键类型：SERIAL → BIGINT GENERATED ALWAYS AS IDENTITY

**原因**：
- `SERIAL` 是旧式语法，实际上是 `INTEGER` + 序列的简写
- `BIGINT` 提供更大的范围（-9,223,372,036,854,775,808 到 9,223,372,036,854,775,807）
- `GENERATED ALWAYS AS IDENTITY` 是 SQL 标准语法，更安全（防止手动插入 ID）

**优势**：
- 避免 ID 耗尽问题（SERIAL 的 INTEGER 范围较小）
- 符合 SQL 标准
- 更好的语义表达

### 2. 字符串类型：VARCHAR(255) → TEXT + CHECK

**原因**：
- PostgreSQL 内部对 `VARCHAR(n)` 和 `TEXT` 的处理方式相同
- `TEXT` 更灵活，不会因为长度限制导致意外错误
- 使用 `CHECK` 约束可以在需要时限制长度，且更明确

**优势**：
- 性能相同，但更灵活
- 避免因长度限制导致的数据截断错误
- `CHECK` 约束提供更清晰的业务规则表达
- 可以轻松调整长度限制而无需修改列类型

### 3. 布尔类型：INTEGER (0/1) → BOOLEAN

**原因**：
- PostgreSQL 原生支持 `BOOLEAN` 类型
- 使用整数表示布尔值是反模式，违背了类型安全原则
- `BOOLEAN` 类型占用 1 字节，`INTEGER` 占用 4 字节

**优势**：
- 更小的存储空间（节省 75% 空间）
- 类型安全，防止无效值（如 2、3 等）
- 更清晰的语义表达
- 支持 `IS TRUE`、`IS FALSE`、`IS NULL` 等标准 SQL 语法
- 更好的查询优化器支持

**示例**：
```sql
-- 清晰的查询语法
SELECT * FROM todos WHERE completed IS TRUE;
SELECT * FROM todos WHERE NOT completed;

-- 而不是
SELECT * FROM todos WHERE completed = 1;
```

### 4. 时间戳类型：BIGINT (Unix 时间戳) → TIMESTAMPTZ

**原因**：
- `TIMESTAMPTZ` 是 PostgreSQL 推荐的时间存储类型
- 自动处理时区转换
- 支持丰富的时间函数和操作符
- 占用 8 字节，与 `BIGINT` 相同

**优势**：
- 自动时区处理，存储 UTC，查询时转换为客户端时区
- 支持时间范围查询、时间算术运算
- 可读性更好（数据库中直接显示为人类可读的时间）
- 支持索引优化的时间范围查询
- 避免手动时间戳转换的错误

**示例**：
```sql
-- 查询最近 7 天的任务
SELECT * FROM todos WHERE created_at > now() - INTERVAL '7 days';

-- 按日期分组统计
SELECT DATE(created_at), COUNT(*)
FROM todos
GROUP BY DATE(created_at);
```

### 5. NOT NULL 约束

**添加的约束**：
- `title NOT NULL` - 标题是必需的
- `completed NOT NULL` - 完成状态必须明确（默认 FALSE）
- `created_at NOT NULL` - 创建时间必须存在

**原因**：
- 防止数据不一致
- 明确表达业务规则
- 避免 NULL 值带来的三值逻辑复杂性
- 提升查询性能（优化器可以做更好的假设）

### 6. 索引策略

#### idx_todos_completed
```sql
CREATE INDEX idx_todos_completed ON todos (completed);
```

**用途**：
- 快速查询未完成的任务：`WHERE completed = FALSE`
- 快速查询已完成的任务：`WHERE completed = TRUE`
- 按完成状态分组统计

**性能影响**：
- 对于大表，可以将全表扫描优化为索引扫描
- 特别适合"查询所有未完成任务"这种常见场景

#### idx_todos_created_at
```sql
CREATE INDEX idx_todos_created_at ON todos (created_at DESC);
```

**用途**：
- 按创建时间排序（最新的在前）：`ORDER BY created_at DESC`
- 时间范围查询：`WHERE created_at > '2026-01-01'`
- 分页查询优化

**性能影响**：
- 避免排序操作（sort）
- 支持高效的时间范围扫描

## 数据迁移策略

### 方案 1：删除重建（开发环境）

```sql
DROP TABLE IF EXISTS todos CASCADE;
-- 然后运行新的 CREATE TABLE 语句
```

**适用场景**：开发环境，无需保留数据

### 方案 2：在线迁移（生产环境）

```sql
-- 1. 创建新表
CREATE TABLE todos_new (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title TEXT NOT NULL CHECK (LENGTH(title) <= 255 AND LENGTH(title) > 0),
    description TEXT,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. 迁移数据
INSERT INTO todos_new (title, description, completed, created_at)
SELECT
    title,
    description,
    CASE WHEN completed = 1 THEN TRUE ELSE FALSE END,  -- 将 INTEGER 转换为 BOOLEAN
    to_timestamp(created_at)  -- 将 Unix 时间戳转换为 TIMESTAMPTZ
FROM todos;

-- 3. 创建索引
CREATE INDEX idx_todos_completed ON todos_new (completed);
CREATE INDEX idx_todos_created_at ON todos_new (created_at DESC);

-- 4. 重命名表（在事务中执行）
BEGIN;
ALTER TABLE todos RENAME TO todos_old;
ALTER TABLE todos_new RENAME TO todos;
COMMIT;

-- 5. 验证后删除旧表
DROP TABLE todos_old;
```

**适用场景**：生产环境，需要保留数据

## API 响应格式变化

### 旧格式（Unix 时间戳）
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 1,
    "title": "测试任务",
    "description": "任务描述",
    "completed": 0,
    "created_at": 1738656000
  }
}
```

### 新格式（ISO 8601 时间字符串）
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 1,
    "title": "测试任务",
    "description": "任务描述",
    "completed": false,
    "created_at": "2026-02-04T10:00:00+08:00"
  }
}
```

## 后端代码调整

### 需要修改的文件
1. `init_db.py` - 更新表创建语句和索引 ✅
2. `app.py` - 修改所有相关接口

### 具体变更

#### 1. 移除时间戳转换代码
- 不再需要 `int(time.time())`
- 使用数据库的 `now()` 函数自动生成时间

#### 2. 修改 API 接口

**POST `/api/todos` - 创建 Todo**
```python
# 不再需要手动生成时间戳
cur.execute(
    "INSERT INTO todos (title, description) VALUES (%s, %s) RETURNING *",
    (title, description)
)
```

**PUT `/api/todos/<id>` - 更新 Todo**
```python
# completed 现在是布尔值
completed = data.get('completed')
if completed is not None and not isinstance(completed, bool):
    return error_response(message='completed 字段必须是布尔值', code=400)
```

## 性能对比

| 指标 | 旧设计 | 新设计 | 改进 |
|------|--------|--------|------|
| 主键存储 | 4 字节 (INTEGER) | 8 字节 (BIGINT) | 更大范围 |
| 布尔字段存储 | 4 字节 (INTEGER) | 1 字节 (BOOLEAN) | 节省 75% |
| 时间戳存储 | 8 字节 (BIGINT) | 8 字节 (TIMESTAMPTZ) | 相同，但功能更强 |
| 索引数量 | 0 | 2 | 查询性能提升 |
| 类型安全 | 低 | 高 | 防止数据错误 |

## 优势总结

1. **类型安全**：使用正确的数据类型，防止无效数据
2. **性能优化**：添加索引，优化常见查询
3. **存储效率**：BOOLEAN 比 INTEGER 节省 75% 空间
4. **可维护性**：符合 PostgreSQL 最佳实践，代码更清晰
5. **功能丰富**：TIMESTAMPTZ 支持丰富的时间操作
6. **标准兼容**：使用 SQL 标准语法，更好的可移植性
7. **自动时区处理**：无需手动处理时区转换

## 验证方法

1. 创建一条 Todo，检查返回的 `created_at` 是否为 ISO 8601 格式
2. 验证 `completed` 字段为布尔值
3. 测试按完成状态查询的性能
4. 测试按时间排序的性能
5. 在数据库中直接查询，确认数据类型正确

## 建议

1. **立即采用**：这些改进没有明显的缺点，建议立即采用
2. **前端适配**：前端需要适配新的数据格式（布尔值和 ISO 时间字符串）
3. **监控性能**：部署后监控查询性能，验证索引效果
4. **考虑扩展**：未来可以考虑添加更多字段（如 `updated_at`、`priority` 等）

## 未来扩展建议

### 1. 添加更新时间字段
```sql
ALTER TABLE todos ADD COLUMN updated_at TIMESTAMPTZ;

-- 创建触发器自动更新
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_todos_updated_at
    BEFORE UPDATE ON todos
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### 2. 添加软删除支持
```sql
ALTER TABLE todos ADD COLUMN deleted_at TIMESTAMPTZ;
CREATE INDEX idx_todos_deleted_at ON todos (deleted_at) WHERE deleted_at IS NULL;
```

### 3. 添加优先级字段
```sql
ALTER TABLE todos ADD COLUMN priority TEXT DEFAULT 'MEDIUM'
    CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT'));
CREATE INDEX idx_todos_priority ON todos (priority);
```

### 4. 添加标签支持（使用数组）
```sql
ALTER TABLE todos ADD COLUMN tags TEXT[] DEFAULT '{}';
CREATE INDEX idx_todos_tags ON todos USING GIN (tags);

-- 查询包含特定标签的任务
SELECT * FROM todos WHERE tags @> ARRAY['urgent'];
```

### 5. 添加全文搜索
```sql
ALTER TABLE todos ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (
        to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(description, ''))
    ) STORED;

CREATE INDEX idx_todos_search ON todos USING GIN (search_vector);

-- 全文搜索
SELECT * FROM todos WHERE search_vector @@ to_tsquery('english', 'important & task');
```

## 参考资料

- [PostgreSQL 官方文档 - 数据类型](https://www.postgresql.org/docs/current/datatype.html)
- [PostgreSQL 官方文档 - 索引](https://www.postgresql.org/docs/current/indexes.html)
- [PostgreSQL 官方文档 - 约束](https://www.postgresql.org/docs/current/ddl-constraints.html)
