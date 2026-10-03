from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    planner_provider: str
    groq_api_key: str | None
    groq_model: str
    gemini_api_key: str | None
    gemini_model: str
    demo_transient_failure: bool

    @classmethod
    def from_environment(cls) -> Settings:
        load_dotenv()
        return cls(
            database_path=Path(os.getenv("DATABASE_PATH", "data/taskworker.db")),
            planner_provider=os.getenv("PLANNER_PROVIDER", "auto").lower(),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            demo_transient_failure=os.getenv("DEMO_TRANSIENT_FAILURE", "true").lower()
            not in {"0", "false", "no"},
        )
