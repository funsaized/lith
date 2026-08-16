import json

import pytest

from lith.call.creds import (
    CredentialFileError,
    MissingCredential,
    find_repo_root,
    resolve_credential,
)


def _repo(tmp_path):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    recipe = root / "recipes" / "integration" / "row.json"
    recipe.parent.mkdir(parents=True)
    recipe.write_text("{}")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    return root, recipe, elsewhere, home


def _write_auth(home, entries):
    hermes = home / ".hermes"
    hermes.mkdir(exist_ok=True)
    (hermes / "auth.json").write_text(json.dumps({"credential_pool": entries}))


def test_tier_1_shell_wins(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    credential = resolve_credential(
        "xai",
        recipe_path=recipe,
        cwd=elsewhere,
        environ={"XAI_API_KEY": "shell-secret"},
        home=home,
    )
    assert credential.secret == "shell-secret"
    assert (credential.tier, credential.source, credential.auth_type) == (
        1, "shell environment", "api_key",
    )


def test_tier_2_repo_env_wins_and_is_anchored_to_recipe(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    (root / ".env").write_text("XAI_API_KEY=repo-secret\n")
    credential = resolve_credential(
        "xai", recipe_path=recipe, cwd=elsewhere, environ={}, home=home
    )
    assert credential.secret == "repo-secret"
    assert credential.tier == 2
    assert credential.source == str(root / ".env")


def test_tier_3_hermes_env_wins(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    (home / ".hermes").mkdir()
    (home / ".hermes" / ".env").write_text("MINIMAX_API_KEY=hermes-secret\n")
    credential = resolve_credential(
        "minimax", recipe_path=recipe, cwd=elsewhere, environ={}, home=home
    )
    assert credential.secret == "hermes-secret"
    assert (credential.tier, credential.source) == (3, "~/.hermes/.env")


def test_tier_4_oauth_pool_wins(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    _write_auth(home, {
        "other-oauth": [{
            "provider": "other",
            "auth_type": "oauth",
            "access_token": "wrong-provider",
            "base_url": "https://api.x.ai/v1",
        }],
        "xai-oauth": [
            {
                "auth_type": "oauth",
                "base_url": "https://api.x.ai/v1",
            },
            {
                "auth_type": "oauth",
                "access_token": "oauth-secret",
                "refresh_token": "must-not-be-used",
                "base_url": "https://api.x.ai/v1",
            },
        ],
    })
    credential = resolve_credential(
        "xai", recipe_path=recipe, cwd=elsewhere, environ={}, home=home
    )
    assert credential.secret == "oauth-secret"
    assert credential.tier == 4
    assert credential.source == "~/.hermes/auth.json:xai-oauth"
    assert credential.is_oauth


def test_shell_beats_repo_env(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    (root / ".env").write_text("XAI_API_KEY=repo-secret\n")
    credential = resolve_credential(
        "xai",
        recipe_path=recipe,
        cwd=elsewhere,
        environ={"XAI_API_KEY": "shell-secret"},
        home=home,
    )
    assert credential.secret == "shell-secret"
    assert credential.tier == 1


def test_api_key_pool_entry_is_fingerprint_only_and_skipped(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    _write_auth(home, {
        "minimax": {
            "provider": "minimax",
            "auth_type": "api_key",
            "secret_fingerprint": "abc123",
            "source": "env:MINIMAX_API_KEY",
            "base_url": "https://api.minimax.io/v1",
        }
    })
    with pytest.raises(MissingCredential, match="MINIMAX_API_KEY"):
        resolve_credential(
            "minimax", recipe_path=recipe, cwd=elsewhere, environ={}, home=home
        )


def test_wrong_base_url_rejects_real_openai_codex_shape(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    _write_auth(home, {
        "openai-codex": [{
            "provider": "openai-codex",
            "auth_type": "oauth",
            "access_token": "codex-token",
            "refresh_token": "refresh-token",
            "base_url": "https://chatgpt.com/backend-api/codex",
        }]
    })
    with pytest.raises(MissingCredential, match="OPENAI_API_KEY"):
        resolve_credential(
            "openai", recipe_path=recipe, cwd=elsewhere, environ={}, home=home
        )


def test_missing_error_names_variable_and_all_four_tiers(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    with pytest.raises(MissingCredential) as caught:
        resolve_credential(
            "openai", recipe_path=recipe, cwd=elsewhere, environ={}, home=home
        )
    message = str(caught.value)
    assert "OPENAI_API_KEY" in message
    assert "tier 1 shell environment" in message
    assert f"tier 2 {root / '.env'}" in message
    assert "tier 3 ~/.hermes/.env" in message
    assert "tier 4 ~/.hermes/auth.json" in message


def test_strict_variable_names_ignore_aliases(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    with pytest.raises(MissingCredential):
        resolve_credential(
            "xai",
            recipe_path=recipe,
            cwd=elsewhere,
            environ={"GROK_API_KEY": "wrong-alias"},
            home=home,
        )


def test_openai_optional_headers_come_from_winning_tier(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    (root / ".env").write_text(
        "OPENAI_API_KEY='repo-secret'\n"
        "OPENAI_ORG_ID=org-example\n"
        "OPENAI_PROJECT_ID=project-example\n"
    )
    credential = resolve_credential(
        "openai", recipe_path=recipe, cwd=elsewhere, environ={}, home=home
    )
    assert credential.organization_id == "org-example"
    assert credential.project_id == "project-example"


def test_repo_discovery_supports_relative_recipes_and_cwd(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    assert find_repo_root("recipes/integration/row.json", cwd=root) == root
    assert find_repo_root(cwd=recipe.parent) == root
    assert find_repo_root(cwd=elsewhere) is None


def test_dotenv_accepts_comments_exports_and_ignores_malformed_lines(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    (root / ".env").write_text(
        "# local credentials\n"
        "not-an-assignment\n"
        "export XAI_API_KEY=repo-secret\n"
    )
    credential = resolve_credential(
        "xai", recipe_path=recipe, cwd=elsewhere, environ={}, home=home
    )
    assert credential.secret == "repo-secret"


def test_unterminated_dotenv_quote_is_rejected(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    (root / ".env").write_text("XAI_API_KEY='unterminated\n")
    with pytest.raises(CredentialFileError, match="unterminated quoted value"):
        resolve_credential(
            "xai", recipe_path=recipe, cwd=elsewhere, environ={}, home=home
        )


def test_unknown_provider_is_rejected_before_any_search(tmp_path):
    with pytest.raises(ValueError, match="unknown provider"):
        resolve_credential("fal", environ={}, home=tmp_path)


def test_secret_is_absent_from_repr_and_fingerprint_is_stable(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    credential = resolve_credential(
        "xai",
        recipe_path=recipe,
        cwd=elsewhere,
        environ={"XAI_API_KEY": "do-not-print-this"},
        home=home,
    )
    assert "do-not-print-this" not in repr(credential)
    assert credential.fingerprint == credential.fingerprint
    assert len(credential.fingerprint) == 8


def test_malformed_auth_json_names_file_without_reading_real_home(tmp_path):
    root, recipe, elsewhere, home = _repo(tmp_path)
    (home / ".hermes").mkdir()
    (home / ".hermes" / "auth.json").write_text("not-json")
    with pytest.raises(CredentialFileError, match="auth.json"):
        resolve_credential(
            "xai", recipe_path=recipe, cwd=elsewhere, environ={}, home=home
        )
