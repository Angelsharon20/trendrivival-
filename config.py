"""Central configuration. All values come from environment variables / the .env file."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
VALID_GRANULARITIES = ("day", "week", "month")
VALID_TOPIC_MODES = ("hashtag", "keyword", "auto")
DETECTION_PARAMS_FILE = BASE_DIR / "detection_params.json"


@dataclass
class Settings:
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    db_name: str = "trend_revival_db"
    dataset_path: str = ""
    dataset_name: str = ""
    dataset_source: str = ""
    dataset_license: str = ""
    col_id: str = ""
    col_text: str = "text"
    col_date: str = "created_at"
    col_hashtags: str = ""
    topic_mode: str = "auto"
    granularity: str = "week"
    batch_size: int = 5000


def load_settings() -> Settings:
    """Read settings from the environment (and .env). Called at run time, not import time."""
    load_dotenv(BASE_DIR / ".env")
    env = os.getenv
    settings = Settings(
        mongodb_uri=env("MONGODB_URI", "mongodb://127.0.0.1:27017"),
        db_name=env("MONGODB_DB", "trend_revival_db"),
        dataset_path=env("DATASET_PATH", ""),
        dataset_name=env("DATASET_NAME", ""),
        dataset_source=env("DATASET_SOURCE", ""),
        dataset_license=env("DATASET_LICENSE", ""),
        col_id=env("COL_ID", "").strip(),
        col_text=env("COL_TEXT", "text").strip(),
        col_date=env("COL_DATE", "created_at").strip(),
        col_hashtags=env("COL_HASHTAGS", "").strip(),
        topic_mode=env("TOPIC_MODE", "auto").strip().lower(),
        granularity=env("GRANULARITY", "week").strip().lower(),
        batch_size=int(env("BATCH_SIZE", "5000")),
    )
    if settings.granularity not in VALID_GRANULARITIES:
        raise ValueError(f"GRANULARITY must be one of {VALID_GRANULARITIES}, got '{settings.granularity}'")
    if settings.topic_mode not in VALID_TOPIC_MODES:
        raise ValueError(f"TOPIC_MODE must be one of {VALID_TOPIC_MODES}, got '{settings.topic_mode}'")
    return settings
