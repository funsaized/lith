"""Install a built wheel into a fresh venv and smoke its CLIs outside the checkout."""

import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import venv
import zlib


def main() -> None:
    wheel = Path(sys.argv[1]).resolve()
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise SystemExit("usage: python tests/check_wheel.py path/to/lith.whl")
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "PYTHONHOME"}}
    with tempfile.TemporaryDirectory(prefix="lith-wheel-") as temporary:
        root = Path(temporary)
        venv.EnvBuilder(with_pip=True, symlinks=os.name != "nt").create(root / "venv")
        binaries = root / "venv" / ("Scripts" if os.name == "nt" else "bin")
        python = binaries / ("python.exe" if os.name == "nt" else "python")

        def run(*args):
            return subprocess.run(args, cwd=root, env=environment, check=True,
                                  capture_output=True, text=True).stdout

        run(str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel))
        installed = run(str(python), "-c", "import lith; print(lith.__file__)").strip()
        assert Path(installed).is_relative_to(root / "venv"), installed
        for cli in ("lith-plate", "lith-press", "lith-print"):
            assert "usage:" in run(str(binaries / cli), "--help")
        recipe = dict(name="wheel-smoke", style="B", model="grok-imagine-image-2.0", n=1,
                      brief=dict(topic="Wheel resources", headline="PACKAGED", icon="gear", aspect="1:1"))
        path = root / "recipe.json"
        path.write_text(json.dumps(recipe))
        envelope = json.loads(run(str(binaries / "lith-plate"), "--recipe", str(path), "--press", "--emit-json"))
        assert "PACKAGED" in envelope["prompt"]
        assert "PACKAGED" in run(str(binaries / "lith-press"), "--recipe", str(path), "--dry-run")

        def chunk(kind, payload):
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

        data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress((b"\x00" + b"\x00\xff\x00" * 16) * 16)) + chunk(b"IEND", b""))
        (root / "source.png").write_bytes(data)
        run(str(binaries / "lith-print"), "--recipe", str(path), "--image-file", str(root / "source.png"),
            "--output-dir", str(root / "published"), "--strict")
        assert (root / "published/B_brutalist_packaged.png").read_bytes() == data
        recipe["model"] = "image-01"
        recipe["brief"]["prompt_mode"] = "compact"
        path.write_text(json.dumps(recipe))
        preview = json.loads(run(str(binaries / "lith-press"), "--recipe", str(path), "--dry-run"))
        assert len(preview["body"]["prompt"]) <= 1500
        assert preview["body"]["prompt_optimizer"] is False
    print("PASS installed-wheel import, packaged templates, three CLIs, strict publication and compact preview")


if __name__ == "__main__":
    main()
