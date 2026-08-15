import sys
from pathlib import Path
from unittest.mock import patch

from scripts.pipeline.typography import overlay_typography


@patch("subprocess.run")
def test_overlay_typography_invokes_overlay_text(mock_run, tmp_path):
    src = tmp_path / "raw.jpg"
    src.write_bytes(b"\xff\xd8\xff\xe0fake jpeg")
    dst = tmp_path / "final.png"

    overlay_typography(
        src, dst,
        lines=[("SYSTEM", "32 language runtimes online"),
               ("NEW", "Full-stack AI MLOps")],
    )

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == sys.executable
    assert any("overlay_text.py" in arg for arg in args)
    line_args = [
        arg for arg in args if arg.startswith("SYSTEM=") or arg.startswith("NEW=")
    ]
    assert len(line_args) == 2
    assert "SYSTEM=32 language runtimes online" in line_args
    assert "NEW=Full-stack AI MLOps" in line_args


@patch("subprocess.run")
def test_overlay_typography_optional_font(mock_run, tmp_path):
    src = tmp_path / "raw.jpg"
    src.write_bytes(b"\xff\xd8\xff\xe0fake jpeg")
    dst = tmp_path / "final.png"

    overlay_typography(
        src,
        dst,
        lines=[("X", "y")],
        font=Path("/System/Library/Fonts/Menlo.ttc"),
    )
    args = mock_run.call_args[0][0]
    assert "--font" in args
    assert "/System/Library/Fonts/Menlo.ttc" in args
