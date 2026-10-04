from __future__ import annotations

from taskworker import config
from taskworker.config import Settings


def test_default_gemini_model_uses_current_lightweight_model(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "load_dotenv", lambda: False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "worker.db"))
    settings = Settings.from_environment()
    assert settings.gemini_model == "gemini-3.5-flash-lite"
