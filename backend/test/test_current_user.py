"""Profil du compte courant, horodatage réel et migration additive."""
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from test.baseTest import BaseTest


class TestCurrentUser(BaseTest):
    def test_current_user_requires_authentication(self):
        assert self.client.get("/api/user/me").status_code == 401
        self.auth()
        response = self.client.get("/api/user/me")
        assert response.status_code == 200
        user = response.json()["data"]
        assert user["username"] == self.test_user.username
        assert user["last_login_at"].endswith("Z")
        datetime.fromisoformat(user["last_login_at"].replace("Z", "+00:00"))
        assert "password" not in user and "token" not in user

    def test_failed_login_does_not_update_timestamp(self):
        self.auth()
        before = self.client.get("/api/user/me").json()["data"]["last_login_at"]
        result = self.client.post("/api/auth/login", json={"username": self.test_user.username, "password": "incorrect"})
        assert result.status_code == 401
        assert self.client.get("/api/user/me").json()["data"]["last_login_at"] == before

    def test_update_own_phone_and_clear(self):
        self.auth()
        other = self.createTestUser()
        response = self.client.patch("/api/user/me", json={"telephone": "+22670000000"})
        assert response.status_code == 200
        assert response.json()["data"]["telephone"] == "+22670000000"
        self.db.refresh(other)
        assert other.telephone != "+22670000000"
        assert self.client.patch("/api/user/me", json={"username": other.username}).status_code == 400
        assert self.client.patch("/api/user/me", json={"telephone": None}).json()["data"]["telephone"] is None


def test_last_login_migration_preserves_existing_users(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as c:
        c.execute(sa.text("CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(255))"))
        c.execute(sa.text("INSERT INTO user (id,username) VALUES (1,'existing')"))
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = c
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        assert c.execute(sa.text("SELECT username,last_login_at FROM user")).one() == ("existing", None)
    engine.dispose()
