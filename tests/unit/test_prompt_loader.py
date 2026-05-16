import pytest

from kelp_teaser.tools.prompt_loader import Prompt, load_prompt, PromptNotFoundError


def test_load_known_prompt_returns_prompt_instance():
    p = load_prompt("sector_classifier")
    assert isinstance(p, Prompt)


def test_load_unknown_prompt_raises():
    with pytest.raises(PromptNotFoundError):
        load_prompt("does_not_exist")


def test_prompt_render_substitutes_variables(tmp_path, monkeypatch):
    prompt_file = tmp_path / "demo.md"
    prompt_file.write_text("Hello {{ name }}, sector is {{ sector }}.")
    monkeypatch.setattr("kelp_teaser.tools.prompt_loader.PROMPTS_DIR", tmp_path)
    p = load_prompt("demo")
    out = p.render(name="Halo", sector="Pharma")
    assert out == "Hello Halo, sector is Pharma."


def test_prompt_render_raises_on_missing_variable(tmp_path, monkeypatch):
    prompt_file = tmp_path / "demo.md"
    prompt_file.write_text("Hello {{ name }}")
    monkeypatch.setattr("kelp_teaser.tools.prompt_loader.PROMPTS_DIR", tmp_path)
    p = load_prompt("demo")
    with pytest.raises(Exception):  # jinja2.UndefinedError
        p.render()
