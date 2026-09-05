import base64
import io
import json
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from lith.call.creds import Credential
import run_provider_matrix as matrix
from test_lith_cli_print import png


MANIFEST = Path(__file__).with_name("provider-matrix.json")


@pytest.fixture
def no_auth(monkeypatch):
    auth = Mock(side_effect=AssertionError("must not resolve credentials"))
    monkeypatch.setattr(matrix, "resolve_credential", auth)
    monkeypatch.setattr(matrix.urllib.request, "urlopen", Mock(side_effect=AssertionError("must stay offline")))
    return auth


def test_offline_default_previews_effective_requests_without_writes(tmp_path, monkeypatch, capsys, no_auth):
    monkeypatch.chdir(tmp_path)
    assert matrix.main([str(MANIFEST)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["requested_candidates"] == 4
    assert result["maximum_with_retries"] == 8
    assert len(result["cases"]) == 4
    assert result["cases"][0]["request"]["body"]["model"] == "grok-imagine-image-quality"
    assert not list(tmp_path.iterdir())
    no_auth.assert_not_called()


@pytest.mark.parametrize("options", [[], ["--max-candidates", "0"], ["--max-candidates", "4"]])
def test_live_requires_budget_including_retries(options, tmp_path, no_auth):
    out = tmp_path / "evidence"
    with pytest.raises(SystemExit) as error:
        matrix.main([str(MANIFEST), "--live", "--out", str(out), *options])
    assert error.value.code == 2
    assert not out.exists()
    no_auth.assert_not_called()


@pytest.mark.parametrize("mutation", ["duplicate", "path", "option", "count", "model"])
def test_malformed_matrix_fails_before_auth(mutation, tmp_path, no_auth):
    case = dict(name="case", recipe=str(MANIFEST.parent.parent / "recipes/live_test_recipe.json"))
    cases = [case]
    if mutation == "duplicate":
        cases.append(case.copy())
    elif mutation == "path":
        case["name"] = "../escape"
    elif mutation == "option":
        case["options"] = {"qualty": "low"}
    elif mutation == "count":
        case["options"] = {"n": True}
    else:
        case["options"] = {"model": "unknown"}
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(cases))
    with pytest.raises(SystemExit):
        matrix.main([str(path), "--live", "--max-candidates", "100"])
    no_auth.assert_not_called()


def test_selection_and_existing_output_protection(tmp_path, no_auth):
    assert len(matrix.plan(MANIFEST, ["openai-landscape"])) == 1
    with pytest.raises(ValueError, match="unknown selected"):
        matrix.plan(MANIFEST, ["typo"])
    with pytest.raises(SystemExit):
        matrix.main([str(MANIFEST), "--case", "xai-portrait", "--live", "--max-candidates", "2", "--out", str(tmp_path)])
    no_auth.assert_not_called()


@pytest.mark.parametrize("reported_model", [None, "actual-served-model"])
def test_live_records_real_retry_model_provenance_and_separate_visual_status(tmp_path, monkeypatch, reported_model):
    secret = "never-log-this-key"
    monkeypatch.setattr(matrix, "resolve_credential", lambda *a, **k: Credential("xai", secret, 1, "test", "api_key"))
    payload = {"data": [{"b64_json": base64.b64encode(png(16, 24)).decode()}], "usage": {"cost_in_usd_ticks": 42}}
    if reported_model:
        payload["model"] = reported_model
    response = io.BytesIO(json.dumps(payload).encode())
    response.status = 200
    open_mock = Mock(side_effect=[HTTPError("https://api.x.ai", 429, "retry", {}, io.BytesIO(b"{}")), response])
    monkeypatch.setattr(matrix.urllib.request, "urlopen", open_mock)
    monkeypatch.setattr("lith.call.http.time.sleep", lambda _: None)
    out = tmp_path / "evidence"
    assert matrix.main([str(MANIFEST), "--case", "xai-portrait", "--live", "--max-candidates", "2", "--out", str(out)]) == 0
    result = json.loads((out / "results.json").read_text())[0]
    assert result["http_post_attempts"] == 2
    assert result["http_retries"] == 1
    assert result["returned_n"] == result["requested_n"] == 1
    assert result["model_in_raw_payload"] == reported_model
    assert result["model_reported_by_adapter"] == (reported_model or result["requested_model"])
    assert result["usage"] == {"cost_in_usd_ticks": 42}
    image = result["images"][0]
    assert image["dimensions"] == [16, 24]
    assert image["strict_exit"] == 0
    assert image["visual_review"] == {"status": "not_reviewed", "findings": []}
    for artifact in out.rglob("*.json"):
        assert secret not in artifact.read_text()
        assert payload["data"][0]["b64_json"] not in artifact.read_text()


def test_failures_are_retained_without_secret_messages_and_remaining_cases_run(tmp_path, monkeypatch):
    auth = Mock(side_effect=ValueError("secret-token-in-provider-error"))
    monkeypatch.setattr(matrix, "resolve_credential", auth)
    out = tmp_path / "evidence"
    assert matrix.main([str(MANIFEST), "--live", "--max-candidates", "8", "--out", str(out)]) == 1
    results = json.loads((out / "results.json").read_text())
    assert len(results) == auth.call_count == 4
    assert all(r["error_type"] == "ValueError" and not r["structural_pass"] for r in results)
    assert "secret-token" not in (out / "results.json").read_text()


@pytest.mark.parametrize("count,height", [(0, 24), (2, 24), (1, 16)])
def test_count_and_frame_failures_cannot_pass_or_trigger_replacements(tmp_path, monkeypatch, count, height):
    from lith.call import CallResult, Candidate

    monkeypatch.setattr(matrix, "resolve_credential", lambda *a, **k: object())
    candidates = [Candidate(i, png(16, height), "image/png", (16, height)) for i in range(count)]
    generate = Mock(return_value=CallResult(candidates, None, None, None, {}, None, {}))
    monkeypatch.setattr(matrix, "generate", generate)
    out = tmp_path / "evidence"
    assert matrix.main([str(MANIFEST), "--case", "xai-portrait", "--live", "--max-candidates", "2", "--out", str(out)]) == 1
    generate.assert_called_once()
    result = json.loads((out / "results.json").read_text())[0]
    assert result["returned_n"] == count
    assert not result["structural_pass"]
    if height == 16:
        assert result["images"][0]["strict_exit"] == 1
    assert all(image["visual_review"]["status"] == "not_reviewed" for image in result["images"])
