from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime
from openviking_integration import OpenVikingIntegration

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
ov_integration = OpenVikingIntegration()

# Serialize todo object
def serialize_todo(todo):
    """序列化 todo 对象，将 datetime 转换为 ISO 8601 字符串"""
    if todo is None:
        return None

    todo_dict = dict(todo)
    # 将 datetime 对象转换为 ISO 8601 字符串
    if 'created_at' in todo_dict and isinstance(todo_dict['created_at'], datetime):
        todo_dict['created_at'] = todo_dict['created_at'].isoformat()

    return todo_dict

# Unified response format
def success_response(data=None, message='ok', code=200):
    """统一成功响应格式"""
    return jsonify({
        'code': code,
        'message': message,
        'data': data
    }), code

def error_response(message, code=400, data=None):
    """统一错误响应格式"""
    return jsonify({
        'code': code,
        'message': message,
        'data': data
    }), code


def _normalize_text(text):
    return (text or '').strip().lower()


def _parse_hybrid_rules(query):
    q = _normalize_text(query)
    ask_tasks = any(token in q for token in ['任务', '待办', 'todo'])
    has_today = any(token in q for token in ['今天', '今日', 'today'])
    has_unfinished = any(token in q for token in ['未完成', '没完成', 'unfinished'])

    stop_words = {
        '今天', '今日', 'today', '任务', '待办', 'todo', '是什么', '什么', '有哪些', '查询',
        '查', '查一下', '看看', '列出', '帮我', '我的', '请', '请问', '一下', '是', '吗', '?', '？'
    }
    raw_terms = [term for term in q.replace('？', ' ').replace('?', ' ').split() if term]
    keyword_terms = [term for term in raw_terms if term not in stop_words]
    if not keyword_terms and not ask_tasks:
        keyword_terms = [q] if q else []

    return {
        'query': q,
        'ask_tasks': ask_tasks,
        'today_only': has_today,
        'unfinished_only': has_today or has_unfinished,
        'keyword_terms': keyword_terms,
    }


def _rrf(rank, k=60):
    if rank is None or rank <= 0:
        return 0.0
    return 1.0 / (k + rank)


def _is_summary_memory(abstract):
    text = abstract or ''
    return ('任务集合' in text) or ('包含' in text and '项任务' in text)


def _keyword_recall_todos(conn, rules, fetch_limit=200):
    conditions = []
    params = []

    if rules['today_only']:
        conditions.append('created_at::date = CURRENT_DATE')
    if rules['unfinished_only']:
        conditions.append('completed = FALSE')

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ''
    sql = f'''
        SELECT id, title, description, completed, created_at
        FROM todos
        {where_sql}
        ORDER BY created_at DESC
        LIMIT %s
    '''
    params.append(fetch_limit)

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def _keyword_rank_todos(rows, rules):
    ranked = []
    query = rules['query']
    terms = rules['keyword_terms']

    for row in rows:
        title = _normalize_text(row.get('title'))
        description = _normalize_text(row.get('description'))
        keyword_score = 0.0

        if query and query in title:
            keyword_score += 1.0
        if query and query in description:
            keyword_score += 0.6

        for term in terms:
            if term in title:
                keyword_score += 0.4
            if term in description:
                keyword_score += 0.2

        # 任务问句可能没有有效关键词，此时保留候选以便结构化过滤生效。
        if rules['ask_tasks'] and not terms:
            keyword_score += 0.1

        if keyword_score > 0 or rules['ask_tasks']:
            ranked.append({
                'source': 'todo',
                'key': f"todo:{row.get('id')}",
                'id': row.get('id'),
                'title': row.get('title'),
                'description': row.get('description'),
                'completed': bool(row.get('completed')),
                'created_at': row.get('created_at').isoformat() if isinstance(row.get('created_at'), datetime) else row.get('created_at'),
                'abstract': row.get('title') or '',
                'keyword_raw_score': keyword_score,
            })

    ranked.sort(key=lambda item: (item['keyword_raw_score'], item.get('created_at') or ''), reverse=True)
    return ranked


def _business_bonus(item, rules):
    bonus = 0.0
    query = rules['query']

    if item['source'] == 'todo':
        title = _normalize_text(item.get('title'))
        completed = bool(item.get('completed', False))
        if query and query in title:
            bonus += 0.08
        if rules['unfinished_only'] and not completed:
            bonus += 0.05
        if rules['unfinished_only'] and completed:
            bonus -= 0.10
    else:
        abstract = item.get('abstract', '')
        if _is_summary_memory(abstract):
            bonus -= 0.06
        if rules['unfinished_only'] and ('已完成' in abstract):
            bonus -= 0.05

    return bonus

# Database connection
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'todo_app'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', '123456')
    )
    return conn

# Create todos table if not exists
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # Create table with PostgreSQL best practices
    cur.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            title TEXT NOT NULL CHECK (LENGTH(title) <= 255 AND LENGTH(title) > 0),
            description TEXT,
            completed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    ''')

    # Create indexes for common query patterns
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_todos_completed
        ON todos (completed)
    ''')

    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_todos_created_at
        ON todos (created_at DESC)
    ''')

    conn.commit()
    cur.close()
    conn.close()

@app.route('/api/todos', methods=['GET'])
def get_todos():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute('SELECT * FROM todos ORDER BY created_at DESC')
        todos = cur.fetchall()

        cur.close()
        conn.close()

        return success_response(data=[serialize_todo(todo) for todo in todos])
    except Exception as e:
        return error_response(message=f'获取待办事项列表失败: {str(e)}', code=500)

@app.route('/api/todos', methods=['POST'])
def create_todo():
    try:
        data = request.get_json()

        title = data.get('title')
        description = data.get('description', '')

        if not title:
            return error_response(message='标题不能为空', code=400)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 数据库自动生成 created_at
        cur.execute(
            'INSERT INTO todos (title, description) VALUES (%s, %s) RETURNING *',
            (title, description)
        )
        new_todo = cur.fetchone()

        conn.commit()
        cur.close()
        conn.close()

        try:
            ov_integration.sync_todo_event("create", serialize_todo(new_todo))
        except Exception as sync_error:
            app.logger.warning(f"OpenViking 同步创建事件失败: {sync_error}")

        return success_response(data=serialize_todo(new_todo), message='创建待办事项成功', code=201)
    except Exception as e:
        return error_response(message=f'创建待办事项失败: {str(e)}', code=500)

@app.route('/api/todos/<int:id>', methods=['PUT'])
def update_todo(id):
    try:
        data = request.get_json()

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check if todo exists
        cur.execute('SELECT * FROM todos WHERE id = %s', (id,))
        todo = cur.fetchone()
        if not todo:
            cur.close()
            conn.close()
            return error_response(message='待办事项不存在', code=404)

        # Update the todo
        title = data.get('title', todo['title'])
        description = data.get('description', todo['description'])
        completed = data.get('completed', todo['completed'])

        # 验证 completed 字段必须是布尔值
        if not isinstance(completed, bool):
            cur.close()
            conn.close()
            return error_response(message='completed 字段必须是布尔值', code=400)

        cur.execute(
            '''UPDATE todos SET title=%s, description=%s, completed=%s
               WHERE id = %s RETURNING *''',
            (title, description, completed, id)
        )
        updated_todo = cur.fetchone()

        conn.commit()
        cur.close()
        conn.close()

        try:
            ov_integration.sync_todo_event("update", serialize_todo(updated_todo))
        except Exception as sync_error:
            app.logger.warning(f"OpenViking 同步更新事件失败: {sync_error}")

        return success_response(data=serialize_todo(updated_todo), message='更新待办事项成功')
    except Exception as e:
        return error_response(message=f'更新待办事项失败: {str(e)}', code=500)

@app.route('/api/todos/<int:id>', methods=['DELETE'])
def delete_todo(id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check if todo exists
        cur.execute('SELECT * FROM todos WHERE id = %s', (id,))
        todo = cur.fetchone()
        if not todo:
            cur.close()
            conn.close()
            return error_response(message='待办事项不存在', code=404)

        cur.execute('DELETE FROM todos WHERE id = %s RETURNING *', (id,))
        deleted_todo = cur.fetchone()

        conn.commit()
        cur.close()
        conn.close()

        try:
            ov_integration.sync_todo_event("delete", serialize_todo(deleted_todo))
        except Exception as sync_error:
            app.logger.warning(f"OpenViking 同步删除事件失败: {sync_error}")

        return success_response(data=serialize_todo(deleted_todo), message='删除待办事项成功')
    except Exception as e:
        return error_response(message=f'删除待办事项失败: {str(e)}', code=500)


@app.route('/api/todos/hybrid-search', methods=['POST'])
def hybrid_search_todos():
    """Todo 混合检索：关键词召回 + 语义召回 + RRF 融合 + 业务重排"""
    try:
        data = request.get_json(silent=True) or {}
        query = (data.get('query') or '').strip()
        limit = int(data.get('limit', 10))
        if not query:
            return error_response(message='query 不能为空', code=400)
        if limit <= 0:
            return error_response(message='limit 必须大于 0', code=400)
        limit = min(limit, 50)

        weight_keyword = float(data.get('weight_keyword', 0.7))
        weight_semantic = float(data.get('weight_semantic', 0.3))
        if weight_keyword < 0 or weight_semantic < 0:
            return error_response(message='weight_keyword 和 weight_semantic 不能为负数', code=400)
        total_weight = weight_keyword + weight_semantic
        if total_weight == 0:
            return error_response(message='weight_keyword 与 weight_semantic 不能同时为 0', code=400)

        # 归一化权重，避免调用方传入的比例不规范导致解释困难。
        weight_keyword = weight_keyword / total_weight
        weight_semantic = weight_semantic / total_weight

        rules = _parse_hybrid_rules(query)

        conn = get_db_connection()
        try:
            todo_rows = _keyword_recall_todos(conn=conn, rules=rules, fetch_limit=200)
        finally:
            conn.close()
        keyword_candidates = _keyword_rank_todos(todo_rows, rules)

        semantic_candidates = []
        semantic_error = None
        try:
            semantic_result = ov_integration.search(
                query=query,
                mode='search',
                target_uri='viking://user/memories/events',
                limit=30,
                score_threshold=None,
                filter_obj=None,
            )
            semantic_memories = (semantic_result.get('result') or {}).get('memories', []) or []
            for memory in semantic_memories:
                uri = memory.get('uri')
                if not uri:
                    continue
                semantic_candidates.append({
                    'source': 'memory',
                    'key': f'memory:{uri}',
                    'uri': uri,
                    'abstract': memory.get('abstract', ''),
                    'memory_score': memory.get('score', 0.0),
                })
        except Exception as e:
            semantic_error = str(e)

        rank_keyword = {}
        rank_semantic = {}
        candidates = {}

        for index, item in enumerate(keyword_candidates, start=1):
            rank_keyword[item['key']] = index
            candidates[item['key']] = item

        for index, item in enumerate(semantic_candidates, start=1):
            rank_semantic[item['key']] = index
            if item['key'] not in candidates:
                candidates[item['key']] = item

        merged = []
        for key, item in candidates.items():
            keyword_rank = rank_keyword.get(key)
            semantic_rank = rank_semantic.get(key)
            keyword_rrf = _rrf(keyword_rank)
            semantic_rrf = _rrf(semantic_rank)
            fused_score = (weight_keyword * keyword_rrf) + (weight_semantic * semantic_rrf)
            rule_bonus = _business_bonus(item, rules)
            final_score = fused_score + rule_bonus

            merged_item = dict(item)
            merged_item['score_breakdown'] = {
                'keyword_rank': keyword_rank,
                'semantic_rank': semantic_rank,
                'rrf_keyword': keyword_rrf,
                'rrf_semantic': semantic_rrf,
                'fused_score': fused_score,
                'rule_bonus': rule_bonus,
                'final_score': final_score,
            }
            merged.append(merged_item)

        merged.sort(key=lambda item: item['score_breakdown']['final_score'], reverse=True)
        final_results = merged[:limit]

        return success_response(
            data={
                'query': query,
                'rules': rules,
                'weights': {
                    'keyword': weight_keyword,
                    'semantic': weight_semantic,
                },
                'results': final_results,
                'counts': {
                    'todo_recall': len(todo_rows),
                    'keyword_ranked': len(keyword_candidates),
                    'semantic_ranked': len(semantic_candidates),
                    'merged': len(merged),
                    'returned': len(final_results),
                },
                'semantic_error': semantic_error,
            },
            message='混合检索成功'
        )
    except ValueError as e:
        return error_response(message=str(e), code=400)
    except Exception as e:
        return error_response(message=f'混合检索失败: {str(e)}', code=500)

@app.route('/api/openviking/health', methods=['GET'])
def openviking_health():
    """OpenViking 集成健康检查"""
    status = ov_integration.health()
    if status.get("healthy"):
        return success_response(data=status, message='OpenViking 状态正常')
    return error_response(message='OpenViking 未就绪', code=503, data=status)

@app.route('/api/openviking/memory/commit', methods=['POST'])
def openviking_memory_commit():
    """写入会话消息并提交，触发长期记忆抽取"""
    try:
        data = request.get_json(silent=True) or {}
        messages = data.get('messages')
        session_id = data.get('session_id')
        commit = bool(data.get('commit', True))

        if not isinstance(messages, list) or len(messages) == 0:
            return error_response(message='messages 必须是非空数组', code=400)

        result = ov_integration.add_messages_and_commit(
            messages=messages,
            session_id=session_id,
            commit=commit,
        )
        return success_response(data=result, message='OpenViking 记忆提交成功')
    except ValueError as e:
        return error_response(message=str(e), code=400)
    except RuntimeError as e:
        return error_response(message=f'OpenViking 暂不可用: {str(e)}', code=503)
    except Exception as e:
        return error_response(message=f'OpenViking 记忆提交失败: {str(e)}', code=500)

@app.route('/api/openviking/memory/search', methods=['POST'])
def openviking_memory_search():
    """检索 OpenViking 长期记忆"""
    try:
        data = request.get_json(silent=True) or {}
        query = (data.get('query') or '').strip()
        mode = (data.get('mode') or 'search').strip().lower()
        session_id = data.get('session_id')
        target_uri = (data.get('target_uri') or '').strip()
        limit = int(data.get('limit', 5))
        score_threshold = data.get('score_threshold')
        filter_obj = data.get('filter')

        if not query:
            return error_response(message='query 不能为空', code=400)
        if mode not in {'search', 'find'}:
            return error_response(message='mode 仅支持 search 或 find', code=400)
        if limit <= 0:
            return error_response(message='limit 必须大于 0', code=400)

        result = ov_integration.search(
            query=query,
            mode=mode,
            session_id=session_id,
            target_uri=target_uri,
            limit=limit,
            score_threshold=score_threshold,
            filter_obj=filter_obj,
        )
        return success_response(data=result, message='OpenViking 检索成功')
    except ValueError as e:
        return error_response(message=str(e), code=400)
    except RuntimeError as e:
        return error_response(message=f'OpenViking 暂不可用: {str(e)}', code=503)
    except Exception as e:
        return error_response(message=f'OpenViking 检索失败: {str(e)}', code=500)

@app.route('/api/openviking/resources', methods=['POST'])
def openviking_add_resource():
    """导入资源到 OpenViking（例如文档、代码目录）"""
    try:
        data = request.get_json(silent=True) or {}
        path = (data.get('path') or '').strip()
        target = data.get('target')
        reason = data.get('reason', '')
        instruction = data.get('instruction', '')
        wait = bool(data.get('wait', False))
        timeout = data.get('timeout')

        if not path:
            return error_response(message='path 不能为空', code=400)

        result = ov_integration.add_resource(
            path=path,
            target=target,
            reason=reason,
            instruction=instruction,
            wait=wait,
            timeout=timeout,
        )
        return success_response(data=result, message='OpenViking 资源导入成功')
    except ValueError as e:
        return error_response(message=str(e), code=400)
    except RuntimeError as e:
        return error_response(message=f'OpenViking 暂不可用: {str(e)}', code=503)
    except Exception as e:
        return error_response(message=f'OpenViking 资源导入失败: {str(e)}', code=500)

@app.route('/', methods=['GET'])
def health_check():
    return success_response(data={'status': 'running'}, message='后端服务运行正常')

if __name__ == '__main__':
    init_db()  # Initialize database on startup
    port = int(os.getenv('PORT', '5001'))
    app.run(debug=True, host='0.0.0.0', port=port)
