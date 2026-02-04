# 时间戳存储和完成字段优化设计方案

**日期**: 2026-02-04
**状态**: 已批准

## 概述

将 Todo 应用的时间存储方式从数据库 TIMESTAMP 类型改为 Unix 时间戳（整数），并将完成字段从 BOOLEAN 改为 INTEGER（0/1），由前端负责时间格式转换。

## 目标

1. 统一后端和数据库使用 Unix 时间戳存储时间
2. 简化后端逻辑，移除时区转换代码
3. 将完成字段改为整数类型，使用 0（未完成）和 1（完成）表示
4. 前端负责将时间戳转换为用户本地时间

## 数据库结构变更

### 当前表结构

```sql
CREATE TABLE todos (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### 新表结构

```sql
CREATE TABLE todos (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    completed INTEGER DEFAULT 0,
    created_at BIGINT NOT NULL
)
```

### 关键变更

1. `completed` 字段：从 `BOOLEAN` 改为 `INTEGER`
   - 0 表示未完成（默认值）
   - 1 表示完成
   - 只允许这两个值

2. `created_at` 字段：从 `TIMESTAMP` 改为 `BIGINT`
   - 存储 Unix 时间戳（秒级）
   - 由应用层生成，不使用数据库默认值

## 后端代码调整

### 需要修改的文件

1. `init_db.py` - 更新表创建语句
2. `app.py` - 修改所有相关接口和辅助函数

### 具体变更

#### 1. 移除时区转换相关代码

- 删除 `pytz` 导入
- 删除 `convert_to_beijing_time()` 函数
- 删除 `format_todo()` 函数

#### 2. 添加时间戳生成

- 导入 `time` 模块
- 使用 `int(time.time())` 生成当前 Unix 时间戳

#### 3. 修改 API 接口

**POST `/api/todos` - 创建 Todo**
- 生成当前时间戳
- 在 INSERT 语句中显式传入 `created_at` 值
- 直接返回原始数据，不做格式化

**GET `/api/todos` - 查询 Todo 列表**
- 直接返回原始数据，不做格式化

**PUT `/api/todos/<id>` - 更新 Todo**
- 添加 `completed` 字段验证，确保值只能是 0 或 1
- 直接返回原始数据，不做格式化

**DELETE `/api/todos/<id>` - 删除 Todo**
- 直接返回原始数据，不做格式化

#### 4. 数据验证

在更新 `completed` 字段时，添加验证逻辑：

```python
if completed not in [0, 1]:
    return error_response(message='completed 字段只能是 0 或 1', code=400)
```

## API 响应格式

### 示例响应

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

## 实施步骤

1. 修改 `init_db.py` 中的 `CREATE TABLE` 语句
2. 修改 `app.py` 中的 `init_db()` 函数
3. 移除时区转换相关代码
4. 添加时间戳生成逻辑
5. 修改所有 API 接口
6. 添加 `completed` 字段验证
7. 删除现有 `todos` 表
8. 重启应用，自动创建新表结构

## 验证方法

1. 创建一条 Todo，检查返回的 `created_at` 是否为 Unix 时间戳整数
2. 查询 Todo 列表，确认时间戳格式正确
3. 更新 `completed` 字段为 1，验证成功
4. 尝试更新 `completed` 为 2，验证返回 400 错误
5. 在数据库中直接查询，确认存储的是整数类型

## 迁移策略

采用直接修改表结构的方式，删除现有 `todos` 表并重新创建。此方式适用于开发环境，不保留现有数据。

## 影响范围

- 后端：需要修改数据库初始化和所有 API 接口
- 前端：需要修改时间显示逻辑，将时间戳转换为本地时间
- 数据库：需要删除并重建 `todos` 表

## 优势

1. 存储空间更小
2. 跨平台兼容性更好
3. 前端处理更灵活，可以根据用户时区显示
4. 后端逻辑更简单，无需处理时区转换
5. 完成字段使用整数，语义清晰且易于扩展
