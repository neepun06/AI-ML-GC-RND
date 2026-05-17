from pathlib import Path
from kelp_teaser import config


def test_repo_root_resolves_to_directory_containing_pyproject():
    assert (config.REPO_ROOT / "pyproject.toml").exists()


def test_default_paths_are_under_repo_root():
    assert config.PROMPTS_DIR == config.REPO_ROOT / "prompts"
    assert config.DATA_INPUTS_DIR == config.REPO_ROOT / "data" / "inputs"
    assert config.DATA_OUTPUTS_DIR == config.REPO_ROOT / "data" / "outputs"


def test_model_ids_are_defined():
    assert config.MODEL_FAST == "gemini-2.5-flash"
    # MODEL_SMART defaults to gemini-2.5-pro but can be overridden via the
    # KELP_MODEL_SMART env var (e.g. for free-tier smoke runs on Flash).
    assert config.MODEL_SMART in ("gemini-2.5-pro", "gemini-2.5-flash")


def test_cost_guardrails_are_sane():
    assert 0 < config.COST_SOFT_WARNING < config.COST_HARD_ABORT
