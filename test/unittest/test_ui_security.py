import re

from arm.ui.security import load_or_create_flask_secret_key


def test_generated_secret_is_persisted_and_reused(tmp_path, monkeypatch):
    monkeypatch.delenv("ARM_FLASK_SECRET_KEY", raising=False)
    config_path = tmp_path / "arm.yaml"
    config_path.write_text('FLASK_SECRET_KEY: ""\nOTHER_SETTING: "value"\n', encoding="utf-8")
    config = {"FLASK_SECRET_KEY": ""}

    first = load_or_create_flask_secret_key(config, str(config_path))

    assert len(first) >= 40
    assert re.search(r"(?m)^FLASK_SECRET_KEY: \"[^\"]+\"$", config_path.read_text(encoding="utf-8"))
    assert "OTHER_SETTING: \"value\"" in config_path.read_text(encoding="utf-8")
    assert config["FLASK_SECRET_KEY"] == first

    second_config = {"FLASK_SECRET_KEY": first}
    assert load_or_create_flask_secret_key(second_config, str(config_path)) == first


def test_environment_secret_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("ARM_FLASK_SECRET_KEY", "environment-provided-secret")
    config_path = tmp_path / "arm.yaml"
    config_path.write_text('FLASK_SECRET_KEY: ""\n', encoding="utf-8")

    key = load_or_create_flask_secret_key({"FLASK_SECRET_KEY": ""}, str(config_path))

    assert key == "environment-provided-secret"
    assert config_path.read_text(encoding="utf-8") == 'FLASK_SECRET_KEY: ""\n'
