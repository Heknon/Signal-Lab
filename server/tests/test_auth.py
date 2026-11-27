import os

import pytest

DSN = os.getenv("TEST_DATABASE_URL")
BACKENDS = [{}] + ([{"SIGNAL_LAB_DATABASE_URL": DSN}] if DSN else [])


@pytest.fixture(params=BACKENDS, ids=lambda e: "postgres" if e else "memory")
def accounts(request, make_client):
    if request.param:
        import psycopg

        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    return make_client(SIGNAL_LAB_AUTH="accounts", **request.param)


def test_open_mode_needs_no_login(make_client):
    c = make_client()
    me = c.get("/api/me").json()
    assert me["auth"] == "open" and me["user"]["username"] == "local"
    assert c.get("/api/progress").status_code == 200


def test_accounts_flow(accounts):
    c = accounts
    assert c.get("/api/progress").status_code == 401
    assert c.get("/api/me").json()["signup"] is True

    r = c.post("/api/auth/signup", json={"username": "Ada", "password": "correct horse"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin"  # first user is admin
    assert c.get("/api/me").json()["user"]["username"] == "ada"

    c.put("/api/progress", json={"lessons": ["otel-core/first-span"], "state": "done"})
    c.put("/api/progress", json={"lessons": ["otel-core/first-span", "otel-core/nested-spans"], "state": "known"})
    p = c.get("/api/progress").json()
    assert list(p["completed"]) == ["otel-core/first-span"]  # known never downgrades done
    assert list(p["known"]) == ["otel-core/nested-spans"]

    c.put("/api/drafts/otel-core/first-span", json={"code": "print(1)"})
    assert c.get("/api/drafts/otel-core/first-span").json()["code"] == "print(1)"

    assert c.post("/api/admin/users", json={"username": "bob", "password": "hunter2hunter2"}).status_code == 200
    users = c.get("/api/admin/users").json()
    assert {u["username"] for u in users} == {"ada", "bob"}
    assert next(u for u in users if u["username"] == "ada")["done"] == 1

    c.post("/api/auth/logout")
    assert c.get("/api/progress").status_code == 401
    assert c.post("/api/auth/login", json={"username": "bob", "password": "nope-nope"}).status_code == 401
    assert c.post("/api/auth/login", json={"username": "bob", "password": "hunter2hunter2"}).status_code == 200
    assert c.get("/api/admin/users").status_code == 403
    assert c.get("/api/progress").json()["completed"] == {}  # bob's own progress


def test_signup_closed(make_client):
    c = make_client(SIGNAL_LAB_AUTH="accounts", SIGNAL_LAB_SIGNUP="closed", SIGNAL_LAB_ADMIN_USERNAME="root", SIGNAL_LAB_ADMIN_PASSWORD="rootrootroot")
    assert c.get("/api/me").json()["signup"] is False
    assert c.post("/api/auth/signup", json={"username": "eve", "password": "12345678"}).status_code == 403
    assert c.post("/api/auth/login", json={"username": "root", "password": "rootrootroot"}).json()["user"]["role"] == "admin"


def test_validation(accounts):
    assert accounts.post("/api/auth/signup", json={"username": "x", "password": "longenough"}).status_code == 400
    assert accounts.post("/api/auth/signup", json={"username": "okname", "password": "short"}).status_code == 400
