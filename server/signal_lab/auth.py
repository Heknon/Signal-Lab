"""Authentication, accounts and per-user state (progress, drafts, run history).

Modes (``SIGNAL_LAB_AUTH``):

* ``open`` (default): no login. Everyone is the built-in ``local`` user,
  which suits a lab running on your own machine.
* ``accounts``: username/password accounts with session cookies, for a
  shared deployment. The first account (or ``SIGNAL_LAB_ADMIN_USERNAME``)
  becomes an admin; admins see everyone's progress and can create users.
"""

from __future__ import annotations

import contextvars
import logging
import re
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import Settings
from .db import BaseDB, User, verify_password

log = logging.getLogger("signal_lab.auth")

COOKIE = "sl_session"
current_user: contextvars.ContextVar[User | None] = contextvars.ContextVar("current_user", default=None)

# Reachable without a session.
PUBLIC_PREFIXES = ("/api/meta", "/api/me", "/api/auth/", "/api/health", "/tap/", "/healthz")
ADMIN_PREFIXES = ("/api/admin/",)
SCENARIO_WRITES = ("/api/scenario/",)
USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")


class Credentials(BaseModel):
    username: str
    password: str
    display_name: str | None = None


class NewUser(Credentials):
    role: str = "learner"


class UserPatch(BaseModel):
    role: str | None = None
    password: str | None = None


class ProgressUpdate(BaseModel):
    lessons: list[str]
    state: str | None  # "done" | "known" | None (clear)


class LastLesson(BaseModel):
    lesson: str


class Draft(BaseModel):
    code: str


def _validate(username: str, password: str) -> str:
    username = username.strip().lower()
    if not USERNAME.match(username):
        raise HTTPException(400, "Usernames are 2-32 characters: lowercase letters, digits, dots, dashes and underscores.")
    if len(password) < 8:
        raise HTTPException(400, "Passwords need at least 8 characters.")
    return username


def install(app: FastAPI, settings: Settings, db: BaseDB) -> None:
    seen: dict[str, float] = {}
    local: dict[str, User | None] = {"user": None}

    async def bootstrap() -> None:
        await db.start()
        if settings.auth == "open":
            user = await db.get_user_by_username("local")
            local["user"] = user or await db.create_user("local", "You", "", "admin")
        if settings.admin_username and settings.admin_password:
            existing = await db.get_user_by_username(settings.admin_username)
            if not existing:
                await db.create_user(settings.admin_username, settings.admin_username, settings.admin_password, "admin")
                log.info("created admin account %s", settings.admin_username)
            elif existing.role != "admin":
                await db.set_role(existing.id, "admin")
        log.info("auth mode %s, %s storage", settings.auth, db.kind)

    app.on_event("startup")(bootstrap)
    app.on_event("shutdown")(db.close)

    async def resolve(request: Request) -> User | None:
        if settings.auth == "open":
            return local["user"]
        token = request.cookies.get(COOKIE)
        return await db.session_user(token) if token else None

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        user = await resolve(request)
        if user is None and not path.startswith(PUBLIC_PREFIXES):
            return JSONResponse({"detail": "Sign in to continue."}, status_code=401)
        if path.startswith(ADMIN_PREFIXES) and (user is None or user.role != "admin"):
            return JSONResponse({"detail": "Admins only."}, status_code=403)
        if (
            path.startswith(SCENARIO_WRITES)
            and request.method != "GET"
            and settings.scenario_control == "admins"
            and (user is None or user.role != "admin")
        ):
            return JSONResponse({"detail": "Only admins can change the shared scenario on this deployment."}, status_code=403)
        request.state.user = user
        token = current_user.set(user)
        try:
            if user and time.time() - seen.get(user.id, 0) > 60:
                seen[user.id] = time.time()
                await db.touch(user.id)
            return await call_next(request)
        finally:
            current_user.reset(token)

    def set_cookie(response: Response, token: str) -> None:
        response.set_cookie(COOKIE, token, max_age=30 * 24 * 3600, httponly=True, samesite="lax", secure=settings.cookie_secure, path="/")

    # ------------------------------------------------------------ session
    @app.get("/api/me")
    async def me(request: Request) -> dict:
        user = await resolve(request)
        signup = settings.auth == "accounts" and (settings.signup == "open" or await db.count_users() == 0)
        return {"auth": settings.auth, "user": user.public() if user else None, "signup": signup, "storage": db.kind, "scenario_control": settings.scenario_control}

    @app.post("/api/auth/signup")
    async def signup(body: Credentials, response: Response) -> dict:
        if settings.auth != "accounts":
            raise HTTPException(400, "This lab doesn't use accounts.")
        first = await db.count_users() == 0
        if settings.signup != "open" and not first:
            raise HTTPException(403, "Sign-up is closed. Ask an admin for an account.")
        username = _validate(body.username, body.password)
        try:
            user = await db.create_user(username, (body.display_name or username).strip()[:64], body.password, "admin" if first else "learner")
        except ValueError:
            raise HTTPException(409, "That username is taken.")
        set_cookie(response, await db.create_session(user.id))
        return {"user": user.public()}

    @app.post("/api/auth/login")
    async def login(body: Credentials, response: Response) -> dict:
        if settings.auth != "accounts":
            raise HTTPException(400, "This lab doesn't use accounts.")
        user = await db.get_user_by_username(body.username.strip().lower())
        if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "Wrong username or password.")
        set_cookie(response, await db.create_session(user.id))
        return {"user": user.public()}

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response) -> dict:
        token = request.cookies.get(COOKIE)
        if token:
            await db.delete_session(token)
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    # ------------------------------------------------------------ progress & drafts
    @app.get("/api/progress")
    async def get_progress(request: Request) -> dict:
        return await db.progress(request.state.user.id)

    @app.put("/api/progress")
    async def put_progress(body: ProgressUpdate, request: Request) -> dict:
        if body.state not in ("done", "known", None):
            raise HTTPException(400, "state must be done, known or null")
        await db.set_progress(request.state.user.id, body.lessons[:200], body.state)
        return await db.progress(request.state.user.id)

    @app.put("/api/progress/last")
    async def put_last(body: LastLesson, request: Request) -> dict:
        await db.set_last(request.state.user.id, body.lesson)
        return {"ok": True}

    @app.get("/api/drafts/{pack}/{slug}")
    async def get_draft(pack: str, slug: str, request: Request) -> dict:
        return {"code": await db.get_draft(request.state.user.id, f"{pack}/{slug}")}

    @app.put("/api/drafts/{pack}/{slug}")
    async def put_draft(pack: str, slug: str, body: Draft, request: Request) -> dict:
        if len(body.code) > 100_000:
            raise HTTPException(413, "Draft too large")
        await db.put_draft(request.state.user.id, f"{pack}/{slug}", body.code)
        return {"ok": True}

    @app.delete("/api/drafts/{pack}/{slug}")
    async def delete_draft(pack: str, slug: str, request: Request) -> dict:
        await db.put_draft(request.state.user.id, f"{pack}/{slug}", None)
        return {"ok": True}

    @app.get("/api/history")
    async def history(request: Request, lesson: str | None = None) -> list[dict]:
        return await db.list_runs(request.state.user.id, lesson, 30)

    # ------------------------------------------------------------ admin
    @app.get("/api/admin/users")
    async def admin_users() -> list[dict]:
        return await db.list_users()

    @app.post("/api/admin/users")
    async def admin_create(body: NewUser) -> dict:
        username = _validate(body.username, body.password)
        if body.role not in ("admin", "learner"):
            raise HTTPException(400, "role must be admin or learner")
        try:
            user = await db.create_user(username, (body.display_name or username)[:64], body.password, body.role)
        except ValueError:
            raise HTTPException(409, "That username is taken.")
        return user.public()

    @app.patch("/api/admin/users/{user_id}")
    async def admin_patch(user_id: str, body: UserPatch, request: Request) -> dict:
        user = await db.get_user(user_id)
        if not user:
            raise HTTPException(404, "No such user")
        if body.role:
            if body.role not in ("admin", "learner"):
                raise HTTPException(400, "role must be admin or learner")
            if user.id == request.state.user.id and body.role != "admin":
                raise HTTPException(400, "You can't remove your own admin role.")
            await db.set_role(user_id, body.role)
        if body.password:
            if len(body.password) < 8:
                raise HTTPException(400, "Passwords need at least 8 characters.")
            await db.set_password(user_id, body.password)
        return {"ok": True}

    @app.delete("/api/admin/users/{user_id}")
    async def admin_delete(user_id: str, request: Request) -> dict:
        if user_id == request.state.user.id:
            raise HTTPException(400, "You can't delete yourself.")
        await db.delete_user(user_id)
        return {"ok": True}
