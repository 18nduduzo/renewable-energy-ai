"""Conversation storage for the chat tab.

Two backends with the same interface:
  - MemoryStore: lives in the visitor's Streamlit session (private, lost on tab close).
  - SqliteStore: saved in a local file (survives restarts on your own computer/server).

Every operation is scoped by `owner`, so once you add real logins you can pass
each user's id and they will only ever see their own chats.

WARNING: on free hosts (Streamlit Community Cloud, Hugging Face) the disk is
temporary and not private per visitor. Use SqliteStore only when running locally,
or after you have added user login. Otherwise visitors would share chats.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager


class MemoryStore:
    def __init__(self, data: dict | None = None):
        # `data` is a dict kept in st.session_state so it survives reruns
        self.data = data if data is not None else {}
        self.data.setdefault("chats", {})

    def list_chats(self, owner: str, limit: int = 50) -> list[dict]:
        rows = [
            {"id": c["id"], "title": c["title"], "updated": c["updated"]}
            for c in self.data["chats"].values()
            if c["owner"] == owner
        ]
        return sorted(rows, key=lambda r: r["updated"], reverse=True)[:limit]

    def create_chat(self, owner: str, title: str = "New chat") -> str:
        cid = uuid.uuid4().hex
        now = time.time()
        self.data["chats"][cid] = {
            "id": cid, "owner": owner, "title": title, "created": now, "updated": now, "messages": [],
        }
        return cid

    def _chat(self, chat_id: str, owner: str):
        c = self.data["chats"].get(chat_id)
        return c if c and c["owner"] == owner else None

    def get_messages(self, chat_id: str, owner: str) -> list[dict]:
        c = self._chat(chat_id, owner)
        return [dict(m) for m in c["messages"]] if c else []

    def add_message(self, chat_id: str, owner: str, role: str, content: str, meta: str = "") -> None:
        c = self._chat(chat_id, owner)
        if c:
            c["messages"].append({"role": role, "content": content, "meta": meta})
            c["updated"] = time.time()

    def pop_last_message(self, chat_id: str, owner: str) -> None:
        c = self._chat(chat_id, owner)
        if c and c["messages"]:
            c["messages"].pop()

    def set_title(self, chat_id: str, owner: str, title: str) -> None:
        c = self._chat(chat_id, owner)
        if c:
            c["title"] = title

    def delete_chat(self, chat_id: str, owner: str) -> None:
        if self._chat(chat_id, owner):
            del self.data["chats"][chat_id]


class SqliteStore:
    def __init__(self, path: str = "chats.db"):
        self.path = path
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS chats ("
                "id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL, "
                "created REAL NOT NULL, updated REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, "
                "role TEXT NOT NULL, content TEXT NOT NULL, meta TEXT NOT NULL DEFAULT '', "
                "created REAL NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_chats_owner ON chats(owner, updated)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_msgs_chat ON messages(chat_id, id)")

    @contextmanager
    def _db(self):
        # New connection per call: safe with Streamlit's threads.
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _owns(self, db, chat_id: str, owner: str) -> bool:
        row = db.execute("SELECT 1 FROM chats WHERE id=? AND owner=?", (chat_id, owner)).fetchone()
        return row is not None

    def list_chats(self, owner: str, limit: int = 50) -> list[dict]:
        with self._db() as db:
            rows = db.execute(
                "SELECT id, title, updated FROM chats WHERE owner=? ORDER BY updated DESC LIMIT ?",
                (owner, limit),
            ).fetchall()
        return [{"id": r[0], "title": r[1], "updated": r[2]} for r in rows]

    def create_chat(self, owner: str, title: str = "New chat") -> str:
        cid = uuid.uuid4().hex
        now = time.time()
        with self._db() as db:
            db.execute("INSERT INTO chats VALUES (?,?,?,?,?)", (cid, owner, title, now, now))
        return cid

    def get_messages(self, chat_id: str, owner: str) -> list[dict]:
        with self._db() as db:
            if not self._owns(db, chat_id, owner):
                return []
            rows = db.execute(
                "SELECT role, content, meta FROM messages WHERE chat_id=? ORDER BY id", (chat_id,)
            ).fetchall()
        return [{"role": r[0], "content": r[1], "meta": r[2]} for r in rows]

    def add_message(self, chat_id: str, owner: str, role: str, content: str, meta: str = "") -> None:
        now = time.time()
        with self._db() as db:
            if not self._owns(db, chat_id, owner):
                return
            db.execute(
                "INSERT INTO messages (chat_id, role, content, meta, created) VALUES (?,?,?,?,?)",
                (chat_id, role, content, meta, now),
            )
            db.execute("UPDATE chats SET updated=? WHERE id=?", (now, chat_id))

    def pop_last_message(self, chat_id: str, owner: str) -> None:
        with self._db() as db:
            if not self._owns(db, chat_id, owner):
                return
            db.execute(
                "DELETE FROM messages WHERE id = (SELECT MAX(id) FROM messages WHERE chat_id=?)",
                (chat_id,),
            )

    def set_title(self, chat_id: str, owner: str, title: str) -> None:
        with self._db() as db:
            db.execute("UPDATE chats SET title=? WHERE id=? AND owner=?", (title, chat_id, owner))

    def delete_chat(self, chat_id: str, owner: str) -> None:
        with self._db() as db:
            if not self._owns(db, chat_id, owner):
                return
            db.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
            db.execute("DELETE FROM chats WHERE id=?", (chat_id,))
