"""Persistence: users, sessions, progress, editor drafts and run history.

Two implementations with the same interface:

* ``PostgresDB``: for hosted / team deployments (``SIGNAL_LAB_DATABASE_URL``)
* ``MemoryDB``: zero-dependency fallback for local single-user use

Live telemetry is deliberately *not* stored here: it is short-lived and
large, and lives in ``store.Store``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

SESSION_TTL_S = 30 * 24 * 3600


# ------------------------------------------------------------------ passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(digest)))
        return hmac.compare_digest(calc.hex(), digest)
    except (ValueError, TypeError):
        return False


@dataclass
class User:
    id: str
    username: str
    display_name: str
    role: str  # "admin" | "learner"
    created: float
    password_hash: str = ""

    def public(self) -> dict:
        return {"id": self.id, "username": self.username, "display_name": self.display_name, "role": self.role}


SCHEMA = [
    # v1
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'learner',
        password_hash TEXT NOT NULL DEFAULT '',
        created DOUBLE PRECISION NOT NULL,
        last_seen DOUBLE PRECISION
    );
    CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created DOUBLE PRECISION NOT NULL,
        expires DOUBLE PRECISION NOT NULL
    );
    CREATE TABLE IF NOT EXISTS progress (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        lesson TEXT NOT NULL,
        state TEXT NOT NULL,
        at DOUBLE PRECISION NOT NULL,
        PRIMARY KEY (user_id, lesson)
    );
    CREATE TABLE IF NOT EXISTS last_lesson (
        user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        lesson TEXT NOT NULL,
        at DOUBLE PRECISION NOT NULL
    );
    CREATE TABLE IF NOT EXISTS drafts (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        lesson TEXT NOT NULL,
        code TEXT NOT NULL,
        updated DOUBLE PRECISION NOT NULL,
        PRIMARY KEY (user_id, lesson)
    );
    CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
        lesson TEXT NOT NULL,
        code TEXT NOT NULL,
        status TEXT NOT NULL,
        exit_code INTEGER,
        duration_ms DOUBLE PRECISION,
        checks JSONB NOT NULL DEFAULT '[]',
        counts JSONB NOT NULL DEFAULT '{}',
        created DOUBLE PRECISION NOT NULL
    );
    CREATE INDEX IF NOT EXISTS runs_user_lesson ON runs (user_id, lesson, created DESC);
    """,
]


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class BaseDB:
    """Interface shared by both stores."""

    kind = "base"

    async def start(self) -> None: ...
    async def close(self) -> None: ...

    # users
    async def count_users(self) -> int: raise NotImplementedError
    async def create_user(self, username: str, display_name: str, password: str, role: str) -> User: raise NotImplementedError
    async def get_user(self, user_id: str) -> User | None: raise NotImplementedError
    async def get_user_by_username(self, username: str) -> User | None: raise NotImplementedError
    async def set_password(self, user_id: str, password: str) -> None: raise NotImplementedError
    async def set_role(self, user_id: str, role: str) -> None: raise NotImplementedError
    async def delete_user(self, user_id: str) -> None: raise NotImplementedError
    async def list_users(self) -> list[dict]: raise NotImplementedError
    async def touch(self, user_id: str) -> None: ...

    # sessions
    async def create_session(self, user_id: str) -> str: raise NotImplementedError
    async def session_user(self, token: str) -> User | None: raise NotImplementedError
    async def delete_session(self, token: str) -> None: raise NotImplementedError

    # progress
    async def progress(self, user_id: str) -> dict: raise NotImplementedError
    async def set_progress(self, user_id: str, lessons: list[str], state: str | None) -> None: raise NotImplementedError
    async def set_last(self, user_id: str, lesson: str) -> None: raise NotImplementedError

    # drafts
    async def get_draft(self, user_id: str, lesson: str) -> str | None: raise NotImplementedError
    async def put_draft(self, user_id: str, lesson: str, code: str | None) -> None: raise NotImplementedError

    # runs
    async def save_run(self, user_id: str | None, run: dict) -> None: raise NotImplementedError
    async def list_runs(self, user_id: str, lesson: str | None = None, limit: int = 20) -> list[dict]: raise NotImplementedError


# ------------------------------------------------------------------ memory
@dataclass
class MemoryDB(BaseDB):
    kind: str = "memory"
    users: dict[str, User] = field(default_factory=dict)
    sessions: dict[str, tuple[str, float]] = field(default_factory=dict)
    prog: dict[str, dict[str, tuple[str, float]]] = field(default_factory=dict)
    last: dict[str, str] = field(default_factory=dict)
    drafts: dict[tuple[str, str], str] = field(default_factory=dict)
    runs: list[tuple[str | None, dict]] = field(default_factory=list)
    seen: dict[str, float] = field(default_factory=dict)

    async def count_users(self) -> int:
        return len(self.users)

    async def create_user(self, username: str, display_name: str, password: str, role: str) -> User:
        if any(u.username == username for u in self.users.values()):
            raise ValueError("username taken")
        u = User(uuid.uuid4().hex, username, display_name, role, time.time(), hash_password(password) if password else "")
        self.users[u.id] = u
        return u

    async def get_user(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    async def get_user_by_username(self, username: str) -> User | None:
        return next((u for u in self.users.values() if u.username == username), None)

    async def set_password(self, user_id: str, password: str) -> None:
        self.users[user_id].password_hash = hash_password(password)

    async def set_role(self, user_id: str, role: str) -> None:
        self.users[user_id].role = role

    async def delete_user(self, user_id: str) -> None:
        self.users.pop(user_id, None)
        self.sessions = {k: v for k, v in self.sessions.items() if v[0] != user_id}

    async def touch(self, user_id: str) -> None:
        self.seen[user_id] = time.time()

    async def list_users(self) -> list[dict]:
        out = []
        for u in self.users.values():
            p = self.prog.get(u.id, {})
            out.append(u.public() | {
                "created": u.created, "last_seen": self.seen.get(u.id),
                "done": sum(1 for s, _ in p.values() if s == "done"), "known": sum(1 for s, _ in p.values() if s == "known"),
                "runs": sum(1 for uid, _ in self.runs if uid == u.id), "last_lesson": self.last.get(u.id),
            })
        return out

    async def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[_token_hash(token)] = (user_id, time.time() + SESSION_TTL_S)
        return token

    async def session_user(self, token: str) -> User | None:
        hit = self.sessions.get(_token_hash(token))
        if not hit or hit[1] < time.time():
            return None
        return self.users.get(hit[0])

    async def delete_session(self, token: str) -> None:
        self.sessions.pop(_token_hash(token), None)

    async def progress(self, user_id: str) -> dict:
        p = self.prog.get(user_id, {})
        return {
            "completed": {k: at for k, (s, at) in p.items() if s == "done"},
            "known": {k: at for k, (s, at) in p.items() if s == "known"},
            "last": self.last.get(user_id),
        }

    async def set_progress(self, user_id: str, lessons: list[str], state: str | None) -> None:
        p = self.prog.setdefault(user_id, {})
        for lesson in lessons:
            if state is None:
                p.pop(lesson, None)
            elif not (state == "known" and p.get(lesson, ("",))[0] == "done"):
                p[lesson] = (state, time.time() * 1000)

    async def set_last(self, user_id: str, lesson: str) -> None:
        self.last[user_id] = lesson

    async def get_draft(self, user_id: str, lesson: str) -> str | None:
        return self.drafts.get((user_id, lesson))

    async def put_draft(self, user_id: str, lesson: str, code: str | None) -> None:
        if code is None:
            self.drafts.pop((user_id, lesson), None)
        else:
            self.drafts[(user_id, lesson)] = code

    async def save_run(self, user_id: str | None, run: dict) -> None:
        self.runs = [r for r in self.runs if r[1]["id"] != run["id"]][-2000:] + [(user_id, run)]

    async def list_runs(self, user_id: str, lesson: str | None = None, limit: int = 20) -> list[dict]:
        rows = [r for uid, r in self.runs if uid == user_id and (lesson is None or r["lesson"] == lesson)]
        return list(reversed(rows))[:limit]


# ------------------------------------------------------------------ postgres
class PostgresDB(BaseDB):
    kind = "postgres"

    def __init__(self, dsn: str):
        from psycopg_pool import AsyncConnectionPool

        self.pool = AsyncConnectionPool(dsn, min_size=1, max_size=10, open=False, kwargs={"autocommit": True})

    async def start(self) -> None:
        await self.pool.open(wait=True, timeout=30)
        async with self.pool.connection() as conn:
            await conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            cur = await conn.execute("SELECT max(version) FROM schema_version")
            row = await cur.fetchone()
            current = row[0] or 0
            for version, sql in enumerate(SCHEMA, start=1):
                if version > current:
                    async with conn.transaction():
                        await conn.execute(sql)
                        await conn.execute("INSERT INTO schema_version (version) VALUES (%s)", (version,))

    async def close(self) -> None:
        await self.pool.close()

    async def _one(self, sql: str, args: tuple = ()) -> Any:
        async with self.pool.connection() as conn:
            cur = await conn.execute(sql, args)
            return await cur.fetchone()

    async def _all(self, sql: str, args: tuple = ()) -> list:
        async with self.pool.connection() as conn:
            cur = await conn.execute(sql, args)
            return await cur.fetchall()

    async def _exec(self, sql: str, args: tuple = ()) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(sql, args)

    @staticmethod
    def _user(row) -> User | None:
        return User(id=row[0], username=row[1], display_name=row[2], role=row[3], password_hash=row[4], created=row[5]) if row else None

    _USER_COLS = "id, username, display_name, role, password_hash, created"

    async def count_users(self) -> int:
        return (await self._one("SELECT count(*) FROM users"))[0]

    async def create_user(self, username: str, display_name: str, password: str, role: str) -> User:
        from psycopg.errors import UniqueViolation

        u = User(uuid.uuid4().hex, username, display_name, role, time.time(), hash_password(password) if password else "")
        try:
            await self._exec(f"INSERT INTO users ({self._USER_COLS}) VALUES (%s, %s, %s, %s, %s, %s)", (u.id, u.username, u.display_name, u.role, u.password_hash, u.created))
        except UniqueViolation:
            raise ValueError("username taken")
        return u

    async def get_user(self, user_id: str) -> User | None:
        return self._user(await self._one(f"SELECT {self._USER_COLS} FROM users WHERE id = %s", (user_id,)))

    async def get_user_by_username(self, username: str) -> User | None:
        return self._user(await self._one(f"SELECT {self._USER_COLS} FROM users WHERE username = %s", (username,)))

    async def set_password(self, user_id: str, password: str) -> None:
        await self._exec("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(password), user_id))

    async def set_role(self, user_id: str, role: str) -> None:
        await self._exec("UPDATE users SET role = %s WHERE id = %s", (role, user_id))

    async def delete_user(self, user_id: str) -> None:
        await self._exec("DELETE FROM users WHERE id = %s", (user_id,))

    async def touch(self, user_id: str) -> None:
        await self._exec("UPDATE users SET last_seen = %s WHERE id = %s", (time.time(), user_id))

    async def list_users(self) -> list[dict]:
        rows = await self._all(
            """
            SELECT u.id, u.username, u.display_name, u.role, u.created, u.last_seen,
                   count(*) FILTER (WHERE p.state = 'done') AS done,
                   count(*) FILTER (WHERE p.state = 'known') AS known,
                   (SELECT count(*) FROM runs r WHERE r.user_id = u.id) AS runs,
                   (SELECT lesson FROM last_lesson l WHERE l.user_id = u.id) AS last_lesson
            FROM users u LEFT JOIN progress p ON p.user_id = u.id
            GROUP BY u.id ORDER BY u.created
            """
        )
        return [
            {"id": r[0], "username": r[1], "display_name": r[2], "role": r[3], "created": r[4], "last_seen": r[5], "done": r[6], "known": r[7], "runs": r[8], "last_lesson": r[9]}
            for r in rows
        ]

    async def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        await self._exec("INSERT INTO sessions (token_hash, user_id, created, expires) VALUES (%s, %s, %s, %s)", (_token_hash(token), user_id, now, now + SESSION_TTL_S))
        await self._exec("DELETE FROM sessions WHERE expires < %s", (now,))
        return token

    async def session_user(self, token: str) -> User | None:
        row = await self._one(
            f"SELECT {', '.join('u.' + c.strip() for c in self._USER_COLS.split(','))} FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = %s AND s.expires > %s",
            (_token_hash(token), time.time()),
        )
        return self._user(row)

    async def delete_session(self, token: str) -> None:
        await self._exec("DELETE FROM sessions WHERE token_hash = %s", (_token_hash(token),))

    async def progress(self, user_id: str) -> dict:
        rows = await self._all("SELECT lesson, state, at FROM progress WHERE user_id = %s", (user_id,))
        last = await self._one("SELECT lesson FROM last_lesson WHERE user_id = %s", (user_id,))
        return {
            "completed": {l: at for l, s, at in rows if s == "done"},
            "known": {l: at for l, s, at in rows if s == "known"},
            "last": last[0] if last else None,
        }

    async def set_progress(self, user_id: str, lessons: list[str], state: str | None) -> None:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                for lesson in lessons:
                    if state is None:
                        await conn.execute("DELETE FROM progress WHERE user_id = %s AND lesson = %s", (user_id, lesson))
                    elif state == "known":  # never downgrade a completed lesson
                        await conn.execute(
                            "INSERT INTO progress (user_id, lesson, state, at) VALUES (%s, %s, 'known', %s) ON CONFLICT (user_id, lesson) DO NOTHING",
                            (user_id, lesson, time.time() * 1000),
                        )
                    else:
                        await conn.execute(
                            "INSERT INTO progress (user_id, lesson, state, at) VALUES (%s, %s, %s, %s) ON CONFLICT (user_id, lesson) DO UPDATE SET state = EXCLUDED.state, at = EXCLUDED.at",
                            (user_id, lesson, state, time.time() * 1000),
                        )

    async def set_last(self, user_id: str, lesson: str) -> None:
        await self._exec(
            "INSERT INTO last_lesson (user_id, lesson, at) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET lesson = EXCLUDED.lesson, at = EXCLUDED.at",
            (user_id, lesson, time.time()),
        )

    async def get_draft(self, user_id: str, lesson: str) -> str | None:
        row = await self._one("SELECT code FROM drafts WHERE user_id = %s AND lesson = %s", (user_id, lesson))
        return row[0] if row else None

    async def put_draft(self, user_id: str, lesson: str, code: str | None) -> None:
        if code is None:
            await self._exec("DELETE FROM drafts WHERE user_id = %s AND lesson = %s", (user_id, lesson))
        else:
            await self._exec(
                "INSERT INTO drafts (user_id, lesson, code, updated) VALUES (%s, %s, %s, %s) ON CONFLICT (user_id, lesson) DO UPDATE SET code = EXCLUDED.code, updated = EXCLUDED.updated",
                (user_id, lesson, code, time.time()),
            )

    async def save_run(self, user_id: str | None, run: dict) -> None:
        await self._exec(
            """
            INSERT INTO runs (id, user_id, lesson, code, status, exit_code, duration_ms, checks, counts, created)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, exit_code = EXCLUDED.exit_code,
                duration_ms = EXCLUDED.duration_ms, checks = EXCLUDED.checks, counts = EXCLUDED.counts
            """,
            (run["id"], user_id, run["lesson"], run["code"], run["status"], run.get("exit_code"), run.get("duration_ms"), json.dumps(run.get("checks", [])), json.dumps(run.get("counts", {})), run["created"]),
        )

    async def list_runs(self, user_id: str, lesson: str | None = None, limit: int = 20) -> list[dict]:
        rows = await self._all(
            "SELECT id, lesson, status, exit_code, duration_ms, checks, counts, created FROM runs WHERE user_id = %s AND (%s::text IS NULL OR lesson = %s) ORDER BY created DESC LIMIT %s",
            (user_id, lesson, lesson, limit),
        )
        return [{"id": r[0], "lesson": r[1], "status": r[2], "exit_code": r[3], "duration_ms": r[4], "checks": r[5], "counts": r[6], "created": r[7]} for r in rows]


def create_db(dsn: str | None) -> BaseDB:
    return PostgresDB(dsn) if dsn else MemoryDB()
