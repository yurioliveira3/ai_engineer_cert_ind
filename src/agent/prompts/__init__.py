"""Versioned prompt management: load, render, and hash prompts."""

import hashlib
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a prompt template from a .txt file in the prompts directory.

    Args:
        name: Prompt name without extension (e.g., 'system', 'analyze_metrics').

    Returns:
        The prompt template content as a string.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    prompt_path = PROMPTS_DIR / f"{name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def render_prompt(name: str, **kwargs) -> tuple[str, str]:
    """Load a prompt template, substitute placeholders, and return (rendered, sha256_hash).

    Args:
        name: Prompt name without extension.
        **kwargs: Key-value pairs to substitute in the template.
            Placeholders in the template use {key} format.

    Returns:
        Tuple of (rendered_prompt, sha256_hex_of_rendered_prompt).
    """
    template = load_prompt(name)
    rendered = template.format(**kwargs)
    sha256_hex = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    return rendered, sha256_hex
