"""Secure, persistent Flask session-key handling for the ARM web UI."""

import logging
import os
import re
import secrets
import tempfile


LOGGER = logging.getLogger(__name__)


def load_or_create_flask_secret_key(config, config_path):
    """Load an explicit or persisted key, generating a strong key when missing.

    ARM_FLASK_SECRET_KEY can be set in the process environment to keep the key
    outside the YAML config. Otherwise, a generated key is written into the
    configured arm.yaml file so normal container restarts preserve sessions.
    """
    env_key = os.environ.get("ARM_FLASK_SECRET_KEY", "").strip()
    if env_key:
        return env_key

    current_key = str(config.get("FLASK_SECRET_KEY") or "").strip()
    if current_key:
        return current_key

    generated_key = secrets.token_urlsafe(48)
    temp_path = None
    try:
        with open(config_path, "r", encoding="utf-8") as settings_file:
            source = settings_file.read()

        setting_line = re.compile(r"(?m)^FLASK_SECRET_KEY\s*:\s*.*$")
        replacement = 'FLASK_SECRET_KEY: "' + generated_key + '"'
        updated, count = setting_line.subn(replacement, source, count=1)
        if count == 0:
            updated = source.rstrip() + "\n" + replacement + "\n"

        directory = os.path.dirname(os.path.abspath(config_path))
        descriptor, temp_path = tempfile.mkstemp(prefix=".arm-config-", dir=directory)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as settings_file:
            settings_file.write(updated)
        os.replace(temp_path, config_path)
        temp_path = None
        config['FLASK_SECRET_KEY'] = generated_key
    except OSError as error:
        LOGGER.warning("Could not persist the Flask session key. Set ARM_FLASK_SECRET_KEY for a stable key: %s", error)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    return generated_key
