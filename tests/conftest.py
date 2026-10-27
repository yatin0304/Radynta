import re
import time

import pytest
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash

from radynta import create_app
from radynta import db as dbmod
from radynta.config import Settings
from radynta.security import limiter


@pytest.fixture
def app(tmp_path):
    limiter.reset()
    settings = Settings(env="test", secret_key="t" * 40, database_path=tmp_path / "test.db",
                        site_url="https://radynta.com", canonical_host="radynta.com",
                        redirect_hosts=["radynta.in", "www.radynta.in", "www.radynta.com"],
                        contact_email="hello@radynta.com", audit_request_delay=0)
    app = create_app(settings)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def conn(app):
    c = dbmod.connect(app.config["SETTINGS"].database_path)
    yield c
    c.close()


def csrf_from(html: str) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "csrf token not found in page"
    return m.group(1)


def old_timer(app, seconds_ago=10):
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="form-timer").dumps({"t": time.time() - seconds_ago})


@pytest.fixture
def logged_in(client, conn):
    dbmod.insert(conn, "users", {"email": "qa@radynta.com", "password_hash": generate_password_hash("correct horse battery")})
    conn.commit()
    page = client.get("/monitor/login").get_data(as_text=True)
    r = client.post("/monitor/login", data={"email": "qa@radynta.com", "password": "correct horse battery", "csrf_token": csrf_from(page)})
    assert r.status_code == 302
    return client
