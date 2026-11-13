import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db, queries  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    import app as app_module

    db.init_db()
    db.seed_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _demo_id():
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT id FROM users WHERE email = 'demo@spendly.com'"
        ).fetchone()["id"]
    finally:
        conn.close()


def _login(client):
    return client.post(
        "/login", data={"email": "demo@spendly.com", "password": "demo123"}
    )


def test_get_user_by_id(client):
    u = queries.get_user_by_id(_demo_id())
    assert u["name"] == "Demo User"
    assert u["email"] == "demo@spendly.com"
    assert u["member_since"]
    assert queries.get_user_by_id(99999) is None


def test_summary_stats(client):
    s = queries.get_summary_stats(_demo_id())
    assert s["total_spent"] == 400.24
    assert s["transaction_count"] == 8
    assert s["top_category"] == "Bills"


def test_summary_stats_empty(client):
    uid = db.create_user("New", "new@x.com", "pw")
    assert queries.get_summary_stats(uid) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_recent_transactions(client):
    rows = queries.get_recent_transactions(_demo_id())
    assert len(rows) == 8
    assert [r["date"] for r in rows] == sorted((r["date"] for r in rows), reverse=True)
    assert set(rows[0]) == {"date", "description", "category", "amount"}
    uid = db.create_user("New", "new@x.com", "pw")
    assert queries.get_recent_transactions(uid) == []


def test_category_breakdown(client):
    cats = queries.get_category_breakdown(_demo_id())
    assert len(cats) == 7
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    assert all(isinstance(c["pct"], int) for c in cats)
    assert sum(c["pct"] for c in cats) == 100
    uid = db.create_user("New", "new@x.com", "pw")
    assert queries.get_category_breakdown(uid) == []


def test_profile_requires_login(client):
    r = client.get("/profile")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_profile_demo_user(client):
    _login(client)
    r = client.get("/profile")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "₹400.24" in html
    assert "Bills" in html
    assert "password_hash" not in html


def test_profile_new_user_empty(client):
    db.create_user("New Person", "new@x.com", "pw")
    client.post("/login", data={"email": "new@x.com", "password": "pw"})
    r = client.get("/profile")
    assert r.status_code == 200
    assert "₹0.00" in r.get_data(as_text=True)
