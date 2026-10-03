from __future__ import annotations

from pathlib import Path

import pytest

from taskworker.api import create_app
from taskworker.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "taskworker.db",
        planner_provider="offline",
        groq_api_key=None,
        groq_model="test-groq",
        gemini_api_key=None,
        gemini_model="test-gemini",
        demo_transient_failure=True,
    )


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)
