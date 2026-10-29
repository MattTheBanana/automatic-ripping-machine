"""Shared MakeMKV and HandBrake audio/subtitle language selection.

RIP_AUDIO_LANGUAGES and RIP_SUBTITLE_LANGUAGES accept "all" or a comma-separated
list of ISO 639-2 three-letter language codes (for example "eng,spa").
"""
import logging
import os
import re
import shlex
import stat
import tempfile


MAKEMKV_SETTINGS_FILE = "/home/arm/.MakeMKV/settings.conf"
_LANGUAGE_CODE_RE = re.compile(r"[a-z]{3}", re.ASCII)
_MAKEMKV_SELECTION_KEY_RE = re.compile(r"^\s*app_DefaultSelectionString\s*=")

_HANDBRAKE_VALUE_OPTIONS = {
    "--audio-lang-list",
    "--subtitle-lang-list",
    "--audio",
    "-a",
    "--subtitle",
    "-s",
}
_HANDBRAKE_FLAG_OPTIONS = {
    "--all-audio",
    "--first-audio",
    "--all-subtitles",
    "--first-subtitle",
}
_HANDBRAKE_OPTIONAL_VALUE_OPTIONS = {
    "-F",
    "--subtitle-forced",
    "--subtitle-burned",
}


def normalize_track_languages(value, setting_name):
    """Return a list of valid language codes, or None to mean all languages."""
    raw_value = str(value if value is not None else "all").strip().lower()
    if raw_value in ("", "all", "any"):
        return None

    languages = [token.strip() for token in raw_value.split(",")]
    if not languages or any(
        token in ("all", "any") or not _LANGUAGE_CODE_RE.fullmatch(token)
        for token in languages
    ):
        logging.warning(
            "Invalid %s value; use 'all' or comma-separated ISO 639-2 codes. "
            "Falling back to all languages.",
            setting_name,
        )
        return None

    return list(dict.fromkeys(languages))


def build_makemkv_selection_rule(audio_languages="all", subtitle_languages="all"):
    """Build the MakeMKV default-selection rule for audio and subtitle tracks."""
    audio = normalize_track_languages(audio_languages, "RIP_AUDIO_LANGUAGES")
    subtitles = normalize_track_languages(subtitle_languages, "RIP_SUBTITLE_LANGUAGES")

    if audio is None and subtitles is None:
        # MakeMKV documents this as selecting all audio and subtitle tracks.
        return "+sel:all"

    rule_parts = ["-sel:all"]
    if audio is None:
        rule_parts.append("+sel:audio")
    else:
        rule_parts.append("+sel:audio&(" + "|".join(audio) + ")")

    if subtitles is None:
        rule_parts.append("+sel:subtitle")
    else:
        rule_parts.append("+sel:subtitle&(" + "|".join(subtitles) + ")")

    # Retain MakeMKV's normal title-priority behavior after selecting stream types.
    rule_parts.extend(["=100:all", "-10:favlang"])
    return ",".join(rule_parts)


def write_makemkv_selection_rule(rule, settings_file=MAKEMKV_SETTINGS_FILE):
    """Update only app_DefaultSelectionString, retaining other MakeMKV preferences."""
    settings_file = os.fspath(settings_file)
    settings_dir = os.path.dirname(settings_file) or "."
    os.makedirs(settings_dir, exist_ok=True)

    try:
        existing_stat = os.stat(settings_file)
        with open(settings_file, "r", encoding="utf-8") as existing_file:
            original_lines = existing_file.read().splitlines()
    except FileNotFoundError:
        existing_stat = None
        original_lines = []

    rule_line = 'app_DefaultSelectionString = "' + rule + '"'
    output_lines = []
    inserted = False
    for line in original_lines:
        if _MAKEMKV_SELECTION_KEY_RE.match(line):
            if not inserted:
                output_lines.append(rule_line)
                inserted = True
            continue
        output_lines.append(line)
    if not inserted:
        output_lines.append(rule_line)

    content = "\n".join(output_lines).rstrip("\n") + "\n"
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".settings.conf.", dir=settings_dir
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(content)

        if existing_stat is None:
            os.chmod(temporary_path, 0o600)
        else:
            os.chmod(temporary_path, stat.S_IMODE(existing_stat.st_mode))
            # The service may run as root; preserve the owner of an existing key file.
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                os.chown(temporary_path, existing_stat.st_uid, existing_stat.st_gid)

        os.replace(temporary_path, settings_file)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def configure_makemkv_track_selection(
    audio_languages, subtitle_languages, settings_file=MAKEMKV_SETTINGS_FILE
):
    """Persist ARM's configured MakeMKV audio/subtitle selection rule."""
    rule = build_makemkv_selection_rule(audio_languages, subtitle_languages)
    write_makemkv_selection_rule(rule, settings_file=settings_file)
    logging.info(
        "Applied ARM audio/dub and subtitle language preferences to MakeMKV."
    )
    return rule


def _remove_handbrake_track_selection_args(arguments):
    """Remove existing language/selection flags so ARM's language settings win."""
    tokens = shlex.split(arguments or "")
    filtered = []
    index = 0

    while index < len(tokens):
        token = tokens[index]
        option = token.split("=", 1)[0] if token.startswith("-") else token

        if option in _HANDBRAKE_VALUE_OPTIONS:
            if "=" not in token:
                index += 1
                if index < len(tokens) and not tokens[index].startswith("-"):
                    index += 1
            else:
                index += 1
        elif option in _HANDBRAKE_FLAG_OPTIONS:
            index += 1
        elif option in _HANDBRAKE_OPTIONAL_VALUE_OPTIONS:
            index += 1
            if index < len(tokens) and not tokens[index].startswith("-"):
                index += 1
        else:
            filtered.append(token)
            index += 1

    return filtered


def build_handbrake_track_selection_args(audio_languages="all", subtitle_languages="all"):
    """Return HandBrake arguments that preserve all matching audio and subtitle tracks."""
    audio = normalize_track_languages(audio_languages, "RIP_AUDIO_LANGUAGES")
    subtitles = normalize_track_languages(subtitle_languages, "RIP_SUBTITLE_LANGUAGES")
    args = []

    if audio is not None:
        args.extend(["--audio-lang-list", ",".join(audio)])
    args.append("--all-audio")

    if subtitles is not None:
        args.extend(["--subtitle-lang-list", ",".join(subtitles)])
    args.append("--all-subtitles")
    return args


def apply_handbrake_track_selection_args(
    arguments, audio_languages="all", subtitle_languages="all"
):
    """Override existing HandBrake track-selection flags with ARM language settings."""
    retained_args = _remove_handbrake_track_selection_args(arguments)
    selection_args = build_handbrake_track_selection_args(
        audio_languages, subtitle_languages
    )
    return shlex.join(retained_args + selection_args)
