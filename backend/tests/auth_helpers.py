from functools import lru_cache
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.security import passwords
from app.models.user import User

TEST_PASSWORD = "CRM test fixture password 2026"


def isolate_request_limits(testcase):
    """Keep real middleware enabled while directing its transactions to the fixture DB."""
    patcher = patch("app.services.request_limits.SessionLocal", sessionmaker(bind=testcase.engine))
    patcher.start()
    testcase.addCleanup(patcher.stop)


@lru_cache(maxsize=1)
def test_password_hash():
    return passwords.hash(TEST_PASSWORD)


def authorize(client, db):
    """Real test-only login; never bypass the production auth dependency."""
    user = db.scalar(select(User).where(User.email == "test.admin@example.test"))
    if user is None:
        user = User(email="test.admin@example.test", name="Test Admin", role="Admin", password_hash=test_password_hash())
        db.add(user)
        db.commit()
    client.headers["X-CRM-Request"] = "1"
    response = client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    if response.status_code != 200:
        raise AssertionError(f"Test-only login failed ({response.status_code})")
    client.headers["Authorization"] = "Bearer " + response.json()["accessToken"]
    return user
