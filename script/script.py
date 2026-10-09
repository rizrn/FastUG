from classes import *
import json
import logging
import settings
from load_commands import load_commands
from load_pictures import *
from load_template import *
import argparse

logger = logging.getLogger(__name__)

STEP_LABELS = {
    1: "Quick Start (Load Picture, Replace & Load Template, Replace & Load Commands, Replace Userguide)",
    2: "Load Picture JSON",
    3: "Replace & Load Template",
    4: "Replace & Load Commands",
    5: "Replace Userguide",
}


def main():
    settings.configure_logging()
    logger.info(
        "Settings: configs=%s icons=%s diagrams=%s userguide=%s template=%s commands=%s suffix=%s",
        settings.CONFIG_DIR, settings.ICONS_DIR, settings.DIAGRAMS_DIR,
        settings.USERGUIDE_FILENAME, settings.TEMPLATE_FILENAME,
        settings.COMMAND_FILENAME, settings.COMPILED_SUFFIX,
    )

    try:
        settings.validate()
    except settings.SettingsError as exc:
        print(f"[ERROR] {exc}")
        return

    args = init_parser().parse_args()

    option = args.option
    if option is None:
        option = prompt_for_option()
        if option is None:
            return

    run_option(option)


def prompt_for_option():
    lines = [f"{number}. {label}" for number, label in sorted(STEP_LABELS.items())]
    prompt = "Select an Option\n" + "\n".join(lines) + "\n"
    try:
        return int(input(prompt))
    except ValueError:
        print("Unknown")
        return None


def run_option(option):
    match option:
        case 1:
            load_pictures()
            generate_user_guide("template")
            load_template()
            load_commands()
            generate_user_guide("userguide")
        case 2:
            load_pictures()
        case 3:
            generate_user_guide("template")
            load_template()
        case 4:
            load_commands()
        case 5:
            generate_user_guide("userguide")
        case _:
            print("Unknown")
    return


def source_filename(file_type):
    sources = {
        "template": settings.TEMPLATE_FILENAME,
        "userguide": settings.USERGUIDE_FILENAME,
    }
    if file_type not in sources:
        raise ValueError(
            f"Unknown file type {file_type!r}; expected one of {sorted(sources)}"
        )
    return sources[file_type]


def generate_user_guide(file_type, filename=None):
    filename = filename or source_filename(file_type)
    print(f"[INFO] Expanding {filename} -> {settings.result_filename(filename)}")

    with open(settings.PARENT_PATH / filename, "r", encoding="utf-8") as f:
        text = f.read()

    custom_commands = init_custom_commands()

    for custom in custom_commands:
        text = replace_text(custom, text)
        custom.success_message()

    commands = init_commands()

    for command in commands:
        text = replace_text(command, text)
        command.success_message()

    with open(settings.PARENT_PATH / settings.result_filename(filename), "w", encoding="utf-8") as f:
        f.write(text)


def load_json(filename):
    with open(settings.CONFIG_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)

def init_custom_commands():
    definitions = load_json("custom.json")
    commands = []
    for name, definition in definitions.items():
        format, fields = definition["format"], definition["fields"]
        commands.append(CustomCommand(name, fields, format))

    return commands

def init_commands():
    definitions = load_json("commands.json")
    commands = []
    for name, definition in definitions.items():
        lookup = load_json(definition["lookup"])
        format, prefix, fields = definition["format"], definition["prefix"], definition["fields"]
        regex = Command.build_standard_regex(prefix, len(fields))
        commands.append(Command(name, regex, format, lookup, fields))

    return commands

def init_parser():
    steps = "\n".join(f"  {n}. {label}" for n, label in sorted(STEP_LABELS.items()))
    parser = argparse.ArgumentParser(
        prog="script",
        description="Automates userguide creation with snippets. "
                    "Reads every path and filename from script/settings.json.",
        epilog="steps:\n" + steps,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "option",
        nargs="?",
        type=int,
        choices=sorted(STEP_LABELS),
        help="Step to run. Omit to be prompted.",
    )

    return parser

def replace_text(command, text):
    return command.substitute(text)

if __name__ == "__main__":
    main()
