"""Guard: the shared ``cfg`` fixture must never read the developer's real config.

The whole suite claims to be hermetic (no network, no API keys, no
``~/.hermes/ytdigest/config.yaml``).  ``config.config_path()`` falls back to
``$HOME/.hermes/ytdigest/config.yaml`` whenever ``YTDIGEST_CONFIG`` points at a
file that does not exist, so a fixture that only sets the variable to a
non-existent path still leaks host state into every test.
"""

import os
from pathlib import Path

from ytdigest import config


def test_cfg_fixture_isolates_config_from_the_real_user_config(cfg, tmp_path):
    resolved = config.config_path()
    assert resolved, "the cfg fixture must pin a concrete config file"
    assert str(resolved).startswith(str(tmp_path)), f"leaked to {resolved}"
    user_config = config.HERMES_HOME / "ytdigest" / "config.yaml"
    assert resolved != user_config, f"leaked to {resolved}"


def test_cfg_fixture_pins_ytdigest_config_to_a_file_that_exists(cfg, tmp_path):
    env = os.environ["YTDIGEST_CONFIG"]
    assert env.startswith(str(tmp_path))
    assert Path(env).is_file(), "an existing file is what stops the fallback to $HOME"
    assert config.config_path() == Path(env)
