"""Shared pytest configuration.

Adds a `--live` flag that opts tests marked `@pytest.mark.live` into running.
Default (no flag) skips them. Live tests hit real network + real Anthropic API.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--live", action="store_true", default=False,
        help="Run @pytest.mark.live tests (real network + API).",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: test requires live network + API key; opt in with --live",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="live test — use --live to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
