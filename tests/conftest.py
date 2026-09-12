from pathlib import Path

import pytest

from reclaim.config import Settings
from reclaim.repo import Repo

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def repo(tmp_path) -> Repo:
    r = Repo(str(tmp_path / "reclaim.db"))
    r.init_schema()
    return r


@pytest.fixture
def fixtures_dir() -> Path:
    return REPO_ROOT / "fixtures"
