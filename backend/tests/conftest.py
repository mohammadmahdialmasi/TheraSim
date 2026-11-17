import pytest

from app.api.routes.auth import get_current_user
from app.main import app
from app.services.local_auth import AuthenticatedUser


@pytest.fixture(autouse=True)
def authenticate_existing_api_tests():
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id="local-reviewer",
        reviewer_name="Test Reviewer",
    )
    yield
    if previous is None:
        app.dependency_overrides.pop(get_current_user, None)
    else:
        app.dependency_overrides[get_current_user] = previous
