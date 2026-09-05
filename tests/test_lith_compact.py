"""Explicit compact MiniMax rendering and pre-spend boundaries."""
import copy
import json
import sys
from pathlib import Path

import pytest

from lith import load_recipe, recipe_from_brief, render_prompt, validate_brief
from lith.call import ImageRequest
from lith.call.minimax import PROMPT_MAX_CHARS, build_request
from lith.cli import press
from lith.render import format_spec


def brief(**overrides):
    return {
        'topic': 'Cold pickles', 'headline': 'DILL PICKLES', 'icon': 'jar',
        'prompt_mode': 'compact', 'aspect': '1:1', **overrides,
    }


def render(data=None, *, style='B', model='image-01'):
    return render_prompt(recipe_from_brief(data or brief(), style=style, model=model, n=1))


def test_sparse_and_three_panel_copy_survive_render_and_provider_translation():
    for sections in ([], [
        {'heading': f'{n} - COLD CRUNCH', 'lines': ['Fresh dill stays bright', 'Keep every jar cold']}
        for n in range(1, 4)
    ]):
        data = brief(title='PICKLE TIME', subtitle='COLD AND CRISP', footer='KEEP IT COLD', sections=sections)
        before = copy.deepcopy(data)
        result = render(data)
        prompt = result['prompt']
        assert 'experimental' in result['copy_note']
        assert format_spec(data) in prompt
        assert 'TITLE: PICKLE TIME' in prompt
        assert ('Stack 3 full-width panels vertically' in prompt) == bool(sections)
        assert len(prompt) <= PROMPT_MAX_CHARS
        request = build_request(ImageRequest(prompt=prompt, model='image-01', aspect='1:1'))
        assert request['prompt'] == prompt
        assert request['prompt_optimizer'] is False
        assert data == before


def test_exact_length_boundary_rejects_overflow_without_shortening_copy():
    data = brief(headline='X')
    overhead = len(render(data)['prompt']) - 1
    data['headline'] = 'X' * (PROMPT_MAX_CHARS - overhead)
    assert len(render(data)['prompt']) == PROMPT_MAX_CHARS
    data['headline'] += 'X'
    with pytest.raises(ValueError, match='1501 characters; cap is 1500'):
        render(data)
    assert len(data['headline']) == PROMPT_MAX_CHARS - overhead + 1


@pytest.mark.parametrize('style', list('ACDEFG'))
def test_unsupported_families_fail_explicitly(style):
    with pytest.raises(ValueError, match='only by family B'):
        render(style=style)


@pytest.mark.parametrize('model', ['gpt-image-2', 'grok-imagine-image-quality'])
def test_compact_is_not_silently_applied_to_other_providers(model):
    with pytest.raises(ValueError, match="requires MiniMax"):
        render(model=model)


@pytest.mark.parametrize('overrides, message', [
    ({'diagram':'Draw a jar'}, 'diagram'),
    ({'diagram_position':'above'}, 'diagram_position'),
    ({'base_color':'red'}, 'base_color'),
    ({'accent':['cyan']}, 'accent'),
    ({'volume':'2'}, 'volume'),
    ({'extra_copy':'keep me'}, 'extra_copy'),
    ({'layout':'two-column'}, "only layout 'stack'"),
    ({'sections':[{'heading':'H'}] * 4}, 'at most 3'),
    ({'sections':[{'heading':'H','lines':['one','two','three']}]}, 'at most 2'),
    ({'sections':[{'heading':'H','caption':'do not drop me'}]}, 'only heading and lines'),
])
def test_unsupported_content_is_rejected_not_discarded(overrides, message):
    with pytest.raises(ValueError, match=message):
        render(brief(**overrides))


@pytest.mark.parametrize('mode', [None, [], {}, 'tiny'])
def test_invalid_prompt_mode_is_a_recipe_error(mode):
    with pytest.raises(ValueError, match='brief.prompt_mode'):
        validate_brief(brief(prompt_mode=mode))


def test_explicit_standard_mode_preserves_existing_prompts():
    for path in (Path(__file__).parents[1] / 'recipes/integration').glob('*.json'):
        recipe = load_recipe(path)
        before = render_prompt(recipe)
        recipe.brief['prompt_mode'] = 'standard'
        assert render_prompt(recipe) == before


def test_compact_validation_happens_before_credential_lookup(tmp_path, monkeypatch):
    path = tmp_path / 'recipe.json'
    path.write_text(json.dumps({'style':'B','model':'image-01','n':1,'brief':brief(headline='X'*1500)}))
    def forbidden(*args, **kwargs):
        raise AssertionError('credentials or provider reached before validation')
    monkeypatch.setattr(press, 'resolve_credential', forbidden)
    monkeypatch.setattr(press, 'generate', forbidden)
    monkeypatch.setattr(sys, 'argv', ['lith-press','--recipe',str(path)])
    with pytest.raises(ValueError, match='cap is 1500'):
        press.main()


def test_compact_cli_preview_is_offline_and_uses_the_same_render(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'recipe.json'
    data = brief(layout='stack', sections=[{'heading':'CRUNCH','lines':['Serve cold']}])
    path.write_text(json.dumps({'style':'B','model':'image-01','n':1,'brief':data}))
    monkeypatch.setattr(sys, 'argv', ['lith-press','--recipe',str(path),'--dry-run'])
    assert press.main() == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview['provider'] == 'minimax'
    assert preview['body']['prompt'] == render(data)['prompt']
    assert preview['body']['prompt_optimizer'] is False



def test_compact_always_routes_direct_even_when_hermes_model_matches(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('FAL_IMAGE_MODEL', 'image-01')
    path = tmp_path / 'recipe.json'
    path.write_text(json.dumps({'style':'B','model':'image-01','n':1,'brief':brief()}))
    monkeypatch.setattr(sys, 'argv', ['lith-press','--recipe',str(path),'--check','--emit-json'])
    assert press.main() == 0
    decision = json.loads(capsys.readouterr().out)
    assert decision['route'] == 'lith-press'
    assert 'disable prompt optimization' in decision['reason']


@pytest.mark.parametrize('name', ['sparse', 'three-sections'])
def test_shipped_compact_examples_render_within_budget(name):
    path = Path(__file__).parents[1] / 'recipes/minimax' / f'{name}.json'
    recipe = load_recipe(path)
    rendered = render_prompt(recipe)
    assert 0 < len(rendered['prompt']) <= PROMPT_MAX_CHARS
    assert format_spec(recipe.brief) in rendered['prompt']
