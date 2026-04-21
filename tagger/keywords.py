"""
Loader for the subfield taxonomy in tags.yaml.

Keyword-matching logic has been removed — the LLM now does all tagging from
listing content. This module is a thin YAML loader consumed by llm/prompts.py.
"""

import os
import yaml


TAGS_PATH = os.path.join(os.path.dirname(__file__), "tags.yaml")


def load_tags() -> dict[str, list[str]]:
    """Return the taxonomy as {slug: [keyword, ...]} from tags.yaml."""
    with open(TAGS_PATH) as f:
        return yaml.safe_load(f)
