import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO = Path(__file__).resolve().parents[1]


def test_dry_mode_prints_plan():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "run.py"),
         "--recipe", str(REPO / "recipes" / "live_test_recipe.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "32 LANGS" in out
    assert "Next:" in out


def test_download_rejects_non_http_schemes():
    from scripts.run import download

    with pytest.raises(ValueError, match="refusing to fetch scheme"):
        download("file:///etc/passwd", Path("/tmp/x.jpg"))


def test_download_rejects_oversized_response(tmp_path):
    from scripts.run import download

    fake = MagicMock()
    fake.headers = {"Content-Type": "image/jpeg"}
    big = b"\xff\xd8\xff" + b"x" * (1024 * 1024)

    def chunk_iter():
        for _ in range(30):
            yield big

    fake.__enter__ = lambda self: self
    fake.__exit__ = lambda self, *args: None
    fake.__iter__ = lambda self: chunk_iter()
    with patch("urllib.request.urlopen", return_value=fake):
        with pytest.raises(ValueError, match="exceeds"):
            download("http://example.com/huge.jpg", tmp_path / "x.jpg")
