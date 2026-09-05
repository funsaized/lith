#!/usr/bin/env python3
"""Run independent branch-aware coverage gates for each system capability."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
THRESHOLD = 80.0
CAPABILITIES = {
    "recipe-generation": {
        "source": "lith.expand,lith.recipe,lith.render,lith.aspect,lith.layout,lith.styles,lith.paths,lith.cli.plate",
        "tests": [
            "tests/test_recipe_generation_integration.py",
            "tests/test_integration_recipes.py",
            "tests/test_lith_expand.py",
            "tests/test_lith_render.py",
            "tests/test_lith_compact.py",
            "tests/test_lith_cli_plate.py",
        ],
    },
    "provider-invocation": {
        "source": "lith.call,lith.cli.press",
        "tests": [
            "tests/test_lith_call.py",
            "tests/test_lith_cli_press.py",
            "tests/test_lith_creds.py",
            "tests/test_lith_http.py",
            "tests/test_lith_minimax.py",
            "tests/test_lith_openai.py",
            "tests/test_lith_xai.py",
        ],
    },
    "output-validation": {
        "source": "lith.imagebytes,lith.cli.print",
        "tests": [
            "tests/test_output_integration.py",
            "tests/test_lith_cli_print.py",
            "tests/test_lith_smoke_e2e.py",
            "tests/test_integration_recipes.py",
        ],
    },
}


def _coverage_percent(summary: dict[str, int]) -> float:
    possible = summary["num_statements"] + summary["num_branches"]
    covered = summary["covered_lines"] + summary["covered_branches"]
    return 100.0 if possible == 0 else covered * 100 / possible


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory(prefix="lith-capability-coverage-") as temporary:
        temp = Path(temporary)
        for name, capability in CAPABILITIES.items():
            data_file = temp / f".{name}.coverage"
            report_file = temp / f"{name}.json"
            environment = {**os.environ, "COVERAGE_FILE": str(data_file)}
            command = [
                sys.executable,
                "-m",
                "coverage",
                "run",
                "--branch",
                f"--source={capability['source']}",
                "-m",
                "pytest",
                "-q",
                *capability["tests"],
            ]
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            if result.returncode:
                print(result.stdout, end="")
                print(result.stderr, end="", file=sys.stderr)
                failures.append(f"{name}: tests failed")
                continue
            subprocess.run(
                [sys.executable, "-m", "coverage", "json", "-o", str(report_file)],
                cwd=ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(report_file.read_text())["totals"]
            percent = _coverage_percent(summary)
            status = "PASS" if percent >= THRESHOLD else "FAIL"
            print(
                f"{status} {name}: {percent:.1f}% branch-aware "
                f"({summary['covered_lines']}/{summary['num_statements']} lines, "
                f"{summary['covered_branches']}/{summary['num_branches']} branches)"
            )
            if percent < THRESHOLD:
                failures.append(f"{name}: {percent:.1f}% < {THRESHOLD:.1f}%")
    if failures:
        print("Capability coverage gate failed: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
