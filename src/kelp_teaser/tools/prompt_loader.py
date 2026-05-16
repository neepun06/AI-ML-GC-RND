"""Load Jinja2-templated Markdown prompts from the prompts/ directory."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from kelp_teaser.config import PROMPTS_DIR as _DEFAULT_PROMPTS_DIR

PROMPTS_DIR: Path = _DEFAULT_PROMPTS_DIR


class PromptNotFoundError(FileNotFoundError):
    pass


class Prompt:
    def __init__(self, name: str, template_text: str) -> None:
        self.name = name
        env = Environment(undefined=StrictUndefined, autoescape=False)
        self._template = env.from_string(template_text)

    def render(self, **kwargs: object) -> str:
        return self._template.render(**kwargs)


def load_prompt(name: str) -> Prompt:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise PromptNotFoundError(f"prompt not found: {path}")
    return Prompt(name=name, template_text=path.read_text(encoding="utf-8"))
