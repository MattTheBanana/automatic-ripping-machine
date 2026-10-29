"""Tests for configurable MakeMKV and HandBrake track-language selection."""
import shlex

from arm.ripper.track_selection import (
    apply_handbrake_track_selection_args,
    build_makemkv_selection_rule,
    write_makemkv_selection_rule,
)


def test_default_selection_keeps_all_audio_and_subtitle_languages():
    assert build_makemkv_selection_rule() == "+sel:all"


def test_custom_audio_and_subtitle_language_lists_are_independent():
    assert build_makemkv_selection_rule("eng, spa,eng", "fra") == (
        "-sel:all,+sel:audio&(eng|spa),+sel:subtitle&(fra),=100:all,-10:favlang"
    )
    assert build_makemkv_selection_rule("all", "eng,spa") == (
        "-sel:all,+sel:audio,+sel:subtitle&(eng|spa),=100:all,-10:favlang"
    )


def test_invalid_language_values_fall_back_to_all():
    assert build_makemkv_selection_rule("es", "eng") == (
        "-sel:all,+sel:audio,+sel:subtitle&(eng),=100:all,-10:favlang"
    )


def test_settings_update_preserves_key_and_other_preferences(tmp_path):
    settings = tmp_path / "settings.conf"
    settings.write_text(
        'app_Key = "T-test-key"\n'
        'app_DefaultSelectionString = "old-rule"\n'
        'app_ExpertMode = dword:00000001\n'
        'app_DefaultSelectionString = "duplicate-rule"\n',
        encoding="utf-8",
    )

    write_makemkv_selection_rule("+sel:all", settings_file=settings)
    content = settings.read_text(encoding="utf-8")

    assert 'app_Key = "T-test-key"' in content
    assert "app_ExpertMode = dword:00000001" in content
    assert content.count("app_DefaultSelectionString") == 1
    assert 'app_DefaultSelectionString = "+sel:all"' in content


def test_handbrake_selection_overrides_scan_forced_only_defaults():
    result = apply_handbrake_track_selection_args(
        "--subtitle scan -F --subtitle-burned --audio-lang-list eng "
        "--all-audio --encoder x264 --quality 20",
        "eng,spa",
        "all",
    )
    args = shlex.split(result)

    assert "--subtitle" not in args
    assert "scan" not in args
    assert "-F" not in args
    assert "--subtitle-burned" not in args
    assert "--audio-lang-list" in args
    assert args[args.index("--audio-lang-list") + 1] == "eng,spa"
    assert "--all-audio" in args
    assert "--all-subtitles" in args
    assert "--encoder" in args
    assert "x264" in args


def test_handbrake_defaults_include_every_language():
    args = shlex.split(apply_handbrake_track_selection_args(
        "--subtitle scan -F --subtitle-burned --audio-lang-list eng --all-audio"
    ))
    assert "--all-audio" in args
    assert "--audio-lang-list" not in args
    assert "--all-subtitles" in args
    assert "--subtitle-lang-list" not in args
    assert "--subtitle" not in args
