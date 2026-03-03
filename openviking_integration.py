import os
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional


OPENVIKING_CONFIG_ENV = "OPENVIKING_CONFIG_FILE"


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump())
    if hasattr(value, "dict"):
        return _to_jsonable(value.dict())
    if hasattr(value, "__dict__"):
        return _to_jsonable(vars(value))
    return str(value)


def _extract_session_id(payload: Dict[str, Any]) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    if "session_id" in payload and payload["session_id"]:
        return str(payload["session_id"])
    if "id" in payload and payload["id"]:
        return str(payload["id"])
    session = payload.get("session")
    if isinstance(session, dict):
        if session.get("session_id"):
            return str(session["session_id"])
        if session.get("id"):
            return str(session["id"])
    return None


class OpenVikingIntegration:
    def __init__(self) -> None:
        self._client = None
        self._init_error: Optional[str] = None
        self._lock = Lock()

    def _enabled(self) -> bool:
        return _parse_bool(os.getenv("OPENVIKING_ENABLED"), default=True)

    def _resolve_config_path(self) -> Optional[str]:
        explicit = os.getenv(OPENVIKING_CONFIG_ENV)
        if explicit:
            candidate = os.path.abspath(os.path.expanduser(explicit))
            if os.path.exists(candidate):
                return candidate
        default_path = os.path.expanduser("~/.openviking/ov.conf")
        if os.path.exists(default_path):
            return default_path
        return None

    def _ensure_client(self):
        if not self._enabled():
            raise RuntimeError("OpenViking 已被 OPENVIKING_ENABLED=false 禁用")
        if self._client is not None:
            return self._client

        with self._lock:
            if self._client is not None:
                return self._client

            try:
                from openviking import OpenViking
            except ImportError as exc:
                self._init_error = f"未安装 openviking 依赖: {exc}"
                raise RuntimeError(self._init_error) from exc

            config_path = self._resolve_config_path()
            if not config_path:
                self._init_error = (
                    "未找到 ov.conf，请设置 OPENVIKING_CONFIG_FILE "
                    "或创建 ~/.openviking/ov.conf"
                )
                raise RuntimeError(self._init_error)

            os.environ[OPENVIKING_CONFIG_ENV] = config_path

            path = os.getenv("OV_STORAGE_PATH", "").strip() or None
            try:
                client = OpenViking(path=path) if path else OpenViking()
                # OpenViking 当前版本存在单例初始化异常后残留状态的问题，
                # 这里主动检测底层 client，避免返回"半初始化对象"。
                if (
                    not hasattr(client, "_async_client")
                    or not hasattr(client._async_client, "_client")
                ):
                    self._reset_singleton_state()
                    raise RuntimeError(
                        "OpenViking 单例状态异常，请检查端口/配置后重试"
                    )
                client.initialize()
            except Exception as exc:
                self._reset_singleton_state()
                self._init_error = str(exc)
                raise RuntimeError(self._init_error) from exc

            self._client = client
            self._init_error = None
            return self._client

    @staticmethod
    def _reset_singleton_state() -> None:
        try:
            from openviking.async_client import AsyncOpenViking

            AsyncOpenViking._instance = None
        except Exception:
            pass

    def health(self) -> Dict[str, Any]:
        config_path = self._resolve_config_path()
        status: Dict[str, Any] = {
            "enabled": self._enabled(),
            "config_path": config_path,
            "ready": False,
            "healthy": False,
            "error": self._init_error,
        }
        if not status["enabled"]:
            status["ready"] = True
            status["healthy"] = True
            status["error"] = None
            return status

        try:
            client = self._ensure_client()
            status["ready"] = True
            status["healthy"] = bool(client.is_healthy())
            status["error"] = None
        except Exception as exc:
            status["error"] = str(exc)
        return status

    def create_session(self) -> Dict[str, Any]:
        client = self._ensure_client()
        result = client.create_session()
        return _to_jsonable(result)

    def add_messages_and_commit(
        self,
        messages: List[Dict[str, str]],
        session_id: Optional[str] = None,
        commit: bool = True,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        created_session = False
        session_result: Dict[str, Any] = {}

        if not session_id:
            session_result = _to_jsonable(client.create_session())
            session_id = _extract_session_id(session_result)
            created_session = True

        if not session_id:
            raise RuntimeError("无法从 OpenViking create_session 响应中解析 session_id")

        writes = []
        for item in messages:
            role = (item.get("role") or "").strip()
            content = (item.get("content") or "").strip()
            if not role or not content:
                raise ValueError("messages 中每一项都必须包含非空 role 和 content")
            writes.append(_to_jsonable(self._add_message(client, session_id, role, content)))

        commit_result = None
        if commit:
            commit_result = _to_jsonable(client.commit_session(session_id))

        return {
            "session_id": session_id,
            "created_session": created_session,
            "session": session_result if created_session else None,
            "writes": writes,
            "commit": commit_result,
        }

    def _add_message(self, client: Any, session_id: str, role: str, content: str) -> Dict[str, Any]:
        """兼容当前 OpenViking add_message 的参数传递问题。"""
        try:
            from openviking.message.part import TextPart
            from openviking_cli.utils import run_async

            session = client.session(session_id)
            run_async(session.load())
            session.add_message(role, [TextPart(text=content)])
            return {
                "session_id": session_id,
                "message_count": len(session.messages),
                "write_mode": "text_part",
            }
        except Exception:
            # 若 SDK 行为变化或环境缺少依赖，回退到官方 add_message 调用。
            return client.add_message(session_id, role, content)

    def search(
        self,
        query: str,
        mode: str = "search",
        session_id: Optional[str] = None,
        target_uri: str = "",
        limit: int = 5,
        score_threshold: Optional[float] = None,
        filter_obj: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        if mode == "find":
            result = client.find(
                query=query,
                target_uri=target_uri,
                limit=limit,
                score_threshold=score_threshold,
            )
        else:
            result = client.search(
                query=query,
                target_uri=target_uri,
                session_id=session_id,
                limit=limit,
                score_threshold=score_threshold,
                filter=filter_obj,
            )
        return {
            "mode": mode,
            "query": query,
            "result": _to_jsonable(result),
        }

    def add_resource(
        self,
        path: str,
        target: Optional[str] = None,
        reason: str = "",
        instruction: str = "",
        wait: bool = False,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        result = client.add_resource(
            path=path,
            target=target,
            reason=reason,
            instruction=instruction,
            wait=wait,
            timeout=timeout,
        )
        return _to_jsonable(result)

    def sync_todo_event(self, action: str, todo: Dict[str, Any]) -> Optional[str]:
        if not _parse_bool(os.getenv("OV_AUTO_SYNC_TODO"), default=True):
            return None

        role = os.getenv("OV_SYNC_ROLE", "user").strip() or "user"
        message = (
            f"[todo_{action}] "
            f"title={todo.get('title', '')}; "
            f"description={todo.get('description', '')}; "
            f"completed={todo.get('completed', '')}; "
            f"id={todo.get('id', '')}; "
            f"created_at={todo.get('created_at', '')}"
        )
        result = self.add_messages_and_commit(
            messages=[{"role": role, "content": message}],
            session_id=None,
            commit=True,
        )
        return result.get("session_id")
