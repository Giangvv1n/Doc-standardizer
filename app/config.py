from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a float.") from exc


@dataclass(slots=True)
class Settings:
    input_dir: Path
    output_dir: Path
    log_dir: Path
    cache_dir: Path
    report_dir: Path

    template_path: Path
    section_schema_path: Path
    section_synonyms_path: Path

    embedding_model: str

    auto_accept_threshold: float
    review_threshold: float

    use_llm_fallback: bool
    openai_api_key: str | None

    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            input_dir=Path(_get_env("INPUT_DIR", "data/input")),
            output_dir=Path(_get_env("OUTPUT_DIR", "data/output")),
            log_dir=Path(_get_env("LOG_DIR", "data/logs")),
            cache_dir=Path(_get_env("CACHE_DIR", "data/cache")),
            report_dir=Path(_get_env("REPORT_DIR", "data/reports")),
            template_path=Path(_get_env("TEMPLATE_PATH", "templates/standard_template.docx")),
            section_schema_path=Path(_get_env("SECTION_SCHEMA_PATH", "templates/section_schema.json")),
            section_synonyms_path=Path(_get_env("SECTION_SYNONYMS_PATH", "templates/section_synonyms.yaml")),
            embedding_model=_get_env(
                "EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ),
            auto_accept_threshold=_get_float("AUTO_ACCEPT_THRESHOLD", 0.85),
            review_threshold=_get_float("REVIEW_THRESHOLD", 0.70),
            use_llm_fallback=_get_bool("USE_LLM_FALLBACK", False),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            log_level=_get_env("LOG_LEVEL", "INFO").upper(),
        )
        settings.validate()
        settings.ensure_directories()
        return settings

    def validate(self) -> None:
        if not 0.0 <= self.review_threshold <= 1.0:
            raise ValueError("REVIEW_THRESHOLD must be between 0 and 1.")

        if not 0.0 <= self.auto_accept_threshold <= 1.0:
            raise ValueError("AUTO_ACCEPT_THRESHOLD must be between 0 and 1.")

        if self.review_threshold > self.auto_accept_threshold:
            raise ValueError(
                "REVIEW_THRESHOLD must be less than or equal to AUTO_ACCEPT_THRESHOLD."
            )

    def ensure_directories(self) -> None:
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)


settings = Settings.from_env()