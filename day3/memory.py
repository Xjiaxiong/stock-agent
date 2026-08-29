"""Day 3 Memory：基于 SQLite 的对话记忆与长期记忆持久化。

给 TS/JS 开发者的对照说明：
- 本文件的每个 def 都相当于一个带类型的函数：def f(x: str) -> dict 约等于
  function f(x: string): Record<string, any>
- sqlite3 是 Python 内置的数据库库（不需要 pip/npm 安装），我们直接写 SQL，
  相当于 Node 里用 better-sqlite3 而不上 ORM
- dict 就是对象（Record<string, any>）；list[dict] 就是 Array<Record<string, any>>

三张表（相当于三个数据模型）：
- conversations：会话，一个 conversation_id 对应一段连续对话
- messages：对话历史，短期记忆的来源，重启程序后从这张表恢复上下文
- memory：长期记忆，从对话中抽取的事实（如"用户正在研究贵州茅台"）
"""

# 标准库导入。Python 的 import 和 TS 类似：
#   import os                          -> import * as os from 'os'
#   from datetime import datetime      -> import { datetime } from 'datetime'
import os
import sqlite3
import uuid
from datetime import datetime

# 数据库文件路径：day3/agent.db（已加入 .gitignore，不会提交到 git）
# __file__ = 当前文件路径；abspath 转成绝对路径，避免在不同工作目录下跑时找不到文件
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.db")


def _now() -> str:
    # datetime.now() -> 当前本地时间；isoformat(timespec="seconds")
    # 转成 "2026-08-23T15:30:00" 这样的字符串，方便存数据库和比较
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    # 每次操作都新建一个数据库连接（Python 的 sqlite3 连接很轻量，不需要连接池）
    conn = sqlite3.connect(DB_PATH)
    # row_factory = sqlite3.Row 让查询结果能用列名取值：
    #   row["id"]（类似 JS 的对象属性访问），而不是只能 row[0] 按下标取
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表（幂等，重复调用安全）。"""
    # with 语句 = 上下文管理器，作用类似 try/finally：
    # 无论中间是否报错，退出 with 块时连接会自动提交并关闭
    with _connect() as conn:
        # executescript 一次执行多段 SQL
        # "IF NOT EXISTS" = 表已存在就跳过，所以 init_db() 可以反复调用（类似幂等的迁移脚本）
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory (
                conversation_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (conversation_id, key)
            );
            """
        )


def create_conversation(user_id: str = "default") -> str:
    # uuid4().hex[:12]：生成 12 位随机十六进制字符串当会话 ID
    # （类似 crypto.randomUUID().replace(/-/g, '').slice(0, 12)）
    conversation_id = uuid.uuid4().hex[:12]
    with _connect() as conn:
        # 参数化查询：SQL 里的 ? 是占位符，后面的元组 (…) 提供真实值。
        # 相当于 prepared statement，避免字符串拼接导致的 SQL 注入
        conn.execute(
            "INSERT INTO conversations (id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conversation_id, user_id, _now(), _now()),
        )
    return conversation_id


def list_conversations(user_id: str = "default") -> list[dict]:
    with _connect() as conn:
        # ORDER BY updated_at DESC：按最近更新时间倒序（最新会话排最前）
        # fetchall() 返回所有行；dict(r) 把 Row 转成普通 dict
        #   [dict(r) for r in rows] 相当于 rows.map(r => ({ ...r }))
        rows = conn.execute(
            "SELECT id, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def append_message(conversation_id: str, role: str, content: str) -> None:
    with _connect() as conn:
        # 同一个 with 块里的多条 SQL = 一个事务：要么全部成功，要么全部回滚
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, _now()),
        )
        # 顺手更新会话的 updated_at，让 list_conversations 的排序保持准确
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (_now(), conversation_id),
        )


def load_messages(conversation_id: str, limit: int = 30) -> list[dict]:
    """取最近的 N 条对话，按时间正序返回（短期记忆）。"""
    with _connect() as conn:
        # 先按 id 倒序取最新的 limit 条，再 reversed 翻回正序。
        # 这样返回的列表是"从旧到新"，可以直接按顺序拼进模型上下文
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def set_memory(conversation_id: str, key: str, value: str) -> None:
    """写入或更新一条长期记忆。"""
    with _connect() as conn:
        # ON CONFLICT(conversation_id, key) DO UPDATE = UPSERT：
        # 键存在则更新值，不存在则插入（类似数据库版的 set / upsert）
        conn.execute(
            """
            INSERT INTO memory (conversation_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(conversation_id, key)
            DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (conversation_id, key, value, _now()),
        )


def load_memory(conversation_id: str) -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT key, value FROM memory WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchall()
    # 字典推导式 {r["key"]: r["value"] for r in rows}
    # 相当于 Object.fromEntries(rows.map(r => [r.key, r.value]))
    return {r["key"]: r["value"] for r in rows}
