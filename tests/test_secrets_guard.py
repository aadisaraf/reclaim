import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*=\s*\S+"),
]


def test_env_is_gitignored():
    result = subprocess.run(
        ["git", "check-ignore", ".env"], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, ".env must be git-ignored"


def test_no_secret_values_under_fixtures_or_docs():
    for base in ["fixtures", "docs"]:
        for path in (ROOT / base).rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(errors="ignore")
            for pattern in SECRET_PATTERNS:
                assert not pattern.search(text), f"secret-shaped value in {path}"


def test_env_example_has_no_openai_key_value():
    text = (ROOT / ".env.example").read_text()
    for line in text.splitlines():
        if line.startswith("OPENAI_API_KEY="):
            assert line.strip() == "OPENAI_API_KEY=", ".env.example must not set a real key"
