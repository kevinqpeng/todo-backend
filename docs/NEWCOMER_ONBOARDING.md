# Todo Backend 新人上手指南

## 1. 先建立全局认知：这是一个什么项目？

这是一个 **Flask + PostgreSQL** 的后端服务，提供 Todo 的标准 CRUD API。

- 对外接口在 `app.py`
- 数据库结构和初始化逻辑在 `init_db.py`
- 迁移/重建策略分别由 `migrate_db.py`、`rebuild_db.py` 管理

建议新人先跑通「本地启动 + 调一次 API + 看一眼数据库表」这三步，再深入代码。

## 2. 代码库整体结构（按学习优先级）

### P0：先看这些（核心业务闭环）

1. `app.py`
   - Flask 应用入口
   - 统一响应格式：`success_response` / `error_response`
   - 路由：`GET/POST/PUT/DELETE /api/todos`
   - 数据序列化：`serialize_todo`（`datetime` → ISO 8601）

2. `init_db.py`
   - 数据库表结构定义
   - 索引创建（`idx_todos_completed`、`idx_todos_created_at`）

3. `README.md`
   - 运行方式、环境变量、API 示例、迁移说明

### P1：再看这些（运维与演进）

4. `migrate_db.py`
   - 生产迁移脚本（保留数据）
   - 老字段类型转换：`INTEGER -> BOOLEAN`、`Unix 时间戳 -> TIMESTAMPTZ`

5. `rebuild_db.py`
   - 开发环境一键重建（删除数据）

6. `deploy.sh`
   - 部署脚本（创建 venv、装依赖、初始化数据库、启动服务）

### P2：文档与设计背景（帮助理解为什么这么做）

7. `docs/Todo-Backend-架构分析.md`
8. `docs/MIGRATION_SUMMARY.md`
9. `docs/plans/*.md`

## 3. 你必须理解的几个关键设计

1. **统一响应格式**
   - 所有 API 都返回 `{ code, message, data }`
   - 这让前端处理成功/失败逻辑更一致

2. **数据库类型设计是重点**
   - `completed` 用 `BOOLEAN`
   - `created_at` 用 `TIMESTAMPTZ`
   - `title` 有长度与非空约束

3. **API 与数据库的职责分层**
   - API 层做参数检查与错误包装
   - 数据层靠 PostgreSQL 约束兜底

4. **迁移策略分环境**
   - 开发：`rebuild_db.py`（快，但会清数据）
   - 生产：`migrate_db.py`（保留数据）

## 4. 新人第一周建议学习路径

### Day 1：跑通系统

- 安装依赖
- 配置 `.env`
- 执行 `python init_db.py`
- 启动 `python app.py`
- 用 curl/Postman 调通 4 个核心接口

### Day 2：理解数据流

以 `POST /api/todos` 为主线阅读：

- 请求解析
- 参数校验
- SQL 执行与 `RETURNING *`
- `serialize_todo` 序列化
- 最终响应结构

### Day 3：理解更新与约束

重点看 `PUT /api/todos/<id>`：

- 先查存在性
- 使用旧值作为默认值
- 强制 `completed` 必须是布尔值

### Day 4：理解迁移脚本

阅读并演练：

- `rebuild_db.py`（本地）
- `migrate_db.py`（了解生产变更思路）

### Day 5：做一个小改动

建议改动：

- 为 `GET /api/todos` 加 `completed` 过滤参数
- 补充 README 示例
- 自测并提交 PR

## 5. 常见坑位提醒

1. `.env` 与代码默认值不一致导致连错库。
2. `migrate_db.py` 是交互式脚本，自动化流程中要特别处理。
3. `deploy.sh` 当前直接用 `python app.py`（开发服务器），生产建议换 Gunicorn。
4. `test_constraint.py` 仍按旧字段类型构造测试，不适用于当前 BOOLEAN/TIMESTAMPTZ 结构。

## 6. 后续进阶建议

1. **工程化**
   - 拆分 `app.py` 为蓝图/服务层/数据访问层
   - 引入连接池

2. **质量保障**
   - 增加 pytest（单元测试 + API 集成测试）
   - 补充 CI（lint + test）

3. **可观测性与生产可用性**
   - 结构化日志
   - 指标与健康检查增强
   - CORS 白名单、错误分级

4. **API 能力演进**
   - 分页、过滤、排序参数
   - OpenAPI/Swagger 文档
   - 认证与鉴权（如 JWT）

---

如果你是第一次接手这个项目：**先能跑，再读主流程，再做小改动**。这样学习效率最高，也最不容易迷路。
