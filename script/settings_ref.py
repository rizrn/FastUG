import json
import logging
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

SETTINGS_FILENAME = "settings.json"

DEFAULTS = {
    "configs_dir": "Configs",
    "icon_dir": "Icons/",
    "diagram_dir": "Diagrams/",

    "userguide_path": "userguide.md",
    "template_path": "template.md",
    "command_path": "commands.md",

    "compiled_suffix": "_res",
    "custom_snippets_path": ".vscode/customcommand.code-snippets",

    "image_extension": ".png",
    "json_indent": 4,
    "log_name": "script.log",
    "log_level": "INFO",
}


class SettingsError(Exception):
    pass


def _load():
    path = SCRIPT_DIR / SETTINGS_FILENAME
    if not path.exists():
        logging.info("No %s found; using built-in defaults.", path)
        return dict(DEFAULTS)

    with open(path, "r", encoding="utf-8") as f:
        try:
            overrides = json.load(f)
        except json.JSONDecodeError as exc:
            raise SettingsError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(overrides, dict):
        raise SettingsError(
            f"{path} must contain a JSON object, got {type(overrides).__name__}."
        )

    unknown = sorted(set(overrides) - set(DEFAULTS))
    if unknown:
        raise SettingsError(
            f"{path} has unrecognised key(s): {unknown}. "
            f"Supported keys: {sorted(DEFAULTS)}"
        )

    return {**DEFAULTS, **overrides}


_values = _load()


CONFIG_DIR = SCRIPT_DIR / _values["configs_dir"]
ICONS_DIR = ROOT / _values["icon_dir"]
DIAGRAMS_DIR = ROOT / _values["diagram_dir"]

USERGUIDE_FILENAME = _values["userguide_path"]
TEMPLATE_FILENAME = _values["template_path"]
COMMAND_FILENAME = _values["command_path"]

COMPILED_SUFFIX = _values["compiled_suffix"]
SNIPPETS_PATH = ROOT / _values["custom_snippets_path"]

IMAGE_EXTENSION = _values["image_extension"]
JSON_INDENT = _values["json_indent"]

LOG_PATH = SCRIPT_DIR / _values["log_name"]
LOG_LEVEL = _values["log_level"]


def result_filename(filename):
    path = Path(filename)
    return str(path.with_name(path.stem + COMPILED_SUFFIX + path.suffix))


def configure_logging():
    level = getattr(logging, str(LOG_LEVEL).upper(), logging.INFO)
    logging.basicConfig(level=level, filename=LOG_PATH, force=True)


def validate():
    for key, path in (
        ("configs_dir", CONFIG_DIR),
        ("icon_dir", ICONS_DIR),
        ("diagram_dir", DIAGRAMS_DIR),
    ):
        if not path.is_dir():
            raise SettingsError(
                f"settings.json {key!r} points at a missing directory: {path}"
            )

    for key, filename in (
        ("userguide_path", USERGUIDE_FILENAME),
        ("template_path", TEMPLATE_FILENAME),
        ("command_path", COMMAND_FILENAME),
    ):
        if not (ROOT / filename).is_file():
            raise SettingsError(
                f"settings.json {key!r} points at a missing file: {ROOT / filename}"
            )

    if not COMPILED_SUFFIX:
        raise SettingsError(
            "settings.json 'compiled_suffix' must not be empty - a generated "
            "file would otherwise overwrite the source it was generated from."
        )
