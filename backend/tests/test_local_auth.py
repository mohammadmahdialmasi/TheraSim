import hashlib

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import get_current_user, router as auth_router
from app.main import app as main_app
from app.persistence.database import DatabaseManager
from app.services.local_auth import AuthenticatedUser, LocalAuthService


PASSWORD = "correct horse battery staple"


def create_auth_test_app(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "auth-data")
    manager.initialize()
    application = FastAPI()
    application.state.local_auth_service = LocalAuthService(manager)
    application.include_router(auth_router)

    protected_router = APIRouter(
        dependencies=[Depends(get_current_user)],
    )

    @protected_router.get("/sensitive")
    def sensitive_data(user: AuthenticatedUser = Depends(get_current_user)):
        return {
            "user_id": user.user_id,
            "reviewer_name": user.reviewer_name,
        }

    application.include_router(protected_router)
    return application, manager


def test_local_initialization_protects_routes_and_issues_revocable_sessions(
    tmp_path,
):
    application, manager = create_auth_test_app(tmp_path)
    client = TestClient(application)

    assert client.get("/api/v1/auth/status").json()["data"]["initialized"] is False
    assert client.get("/sensitive").status_code == 401

    initialized = client.post(
        "/api/v1/auth/initialize",
        json={"reviewer_name": "Primary Reviewer", "password": PASSWORD},
    )
    assert initialized.status_code == 201
    body = initialized.json()["data"]
    token = body["access_token"]
    assert body["user"] == {
        "user_id": "local-reviewer",
        "reviewer_name": "Primary Reviewer",
    }
    assert PASSWORD not in initialized.text

    with manager.connection("operational") as connection:
        user = connection.execute(
            "SELECT password_hash FROM local_auth_users"
        ).fetchone()
        stored_session = connection.execute(
            "SELECT token_sha256 FROM local_auth_sessions"
        ).fetchone()
    assert user["password_hash"].startswith("scrypt$")
    assert token not in user["password_hash"]
    assert stored_session["token_sha256"] != token

    assert client.post(
        "/api/v1/auth/initialize",
        json={"reviewer_name": "Second Reviewer", "password": PASSWORD},
    ).status_code == 409
    assert client.get("/sensitive").status_code == 401

    authorized = client.get(
        "/sensitive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert authorized.status_code == 200
    assert authorized.json()["reviewer_name"] == "Primary Reviewer"
    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]["user_id"] == "local-reviewer"

    assert client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 200
    assert client.get(
        "/sensitive",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 401


def test_local_login_rejects_bad_credentials_and_expires_sessions(tmp_path):
    application, manager = create_auth_test_app(tmp_path)
    client = TestClient(application)
    setup = client.post(
        "/api/v1/auth/initialize",
        json={"reviewer_name": "Reviewer", "password": PASSWORD},
    )
    assert setup.status_code == 201

    assert client.post(
        "/api/v1/auth/login",
        json={"password": "not the password"},
    ).status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"password": PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    assert client.get(
        "/sensitive",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 200

    with manager.transaction("operational") as connection:
        connection.execute(
            "UPDATE local_auth_sessions SET expires_at = ? "
            "WHERE token_sha256 = ?",
            (
                "2000-01-01T00:00:00Z",
                hashlib.sha256(token.encode("ascii")).hexdigest(),
            ),
        )
    assert client.get(
        "/sensitive",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 401


def test_local_login_throttles_and_expires_failed_attempts(tmp_path):
    application, manager = create_auth_test_app(tmp_path)
    client = TestClient(application)
    assert client.post(
        "/api/v1/auth/initialize",
        json={"reviewer_name": "Reviewer", "password": PASSWORD},
    ).status_code == 201

    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"password": "wrong password"},
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/v1/auth/login",
        json={"password": PASSWORD},
    )
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    assert limited.json()["detail"] == "login_rate_limited"

    with manager.connection("operational") as connection:
        attempts = connection.execute(
            "SELECT client_sha256 FROM local_auth_login_attempts"
        ).fetchall()
    assert len(attempts) == 5
    assert all(row["client_sha256"] != "testclient" for row in attempts)

    with manager.transaction("operational") as connection:
        connection.execute(
            "UPDATE local_auth_login_attempts "
            "SET attempted_at = '2000-01-01T00:00:00Z'"
        )
    recovered = client.post(
        "/api/v1/auth/login",
        json={"password": PASSWORD},
    )
    assert recovered.status_code == 200
    with manager.connection("operational") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM local_auth_login_attempts"
        ).fetchone()[0] == 0


def test_local_initialization_rejects_short_passwords(tmp_path):
    application, _ = create_auth_test_app(tmp_path)
    response = TestClient(application).post(
        "/api/v1/auth/initialize",
        json={"reviewer_name": "Reviewer", "password": "short"},
    )
    assert response.status_code == 422


def test_main_sensitive_routes_reject_missing_bearer_token():
    previous = main_app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(main_app)
    try:
        response = client.get("/api/v1/cases")
        health = client.get("/health")
    finally:
        client.close()
        if previous is not None:
            main_app.dependency_overrides[get_current_user] = previous

    assert response.status_code == 401
    assert health.status_code == 200
