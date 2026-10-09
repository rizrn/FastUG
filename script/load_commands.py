from classes import *
import json
import re
import logging
from pathlib import Path

PARENT_DIR = Path(__file__).resolve().parent.parent
COMMAND_PATH = Path(__file__).resolve().parent / "Configs/custom.json"
COMMAND_PREFIX = "command"
FIELD_REGEX = Command.build_standard_regex("field", 1)
COMMAND_FILENAME = "commands.md"
SNIPPETS_PATH = PARENT_DIR / ".vscode/customcommand.code-snippets"

def create_snippet_format(fields):
    field_count = 1
    result = []
    for field in fields:
        field_string = "${" + str(field_count) + ":" + field + "}"
        result.append(field_string)
        field_count += 1


    return ":".join(result)

def remove_duplicate(list):
    res = []
    unique = set()

    for val in list:
        if val not in unique:
            res.append(val)
            unique.add(val)

    return res
def load_commands():

    with open(PARENT_DIR / COMMAND_FILENAME, "r", encoding="utf-8") as f:
        text = f.read()

    data = {}
    snippets = {}
    command_regex = CustomCommand.build_custom_regex(COMMAND_PREFIX, 2)
    command_match = re.findall(command_regex, text)
    for command in command_match:
        name, format = command
        fields_val = remove_duplicate(FIELD_REGEX.findall(format))

        def repl(match):
            return "{" + match.group(1) + "}"

        format = FIELD_REGEX.sub(repl, format)
        
        custom_command = CustomCommand(name, tuple(fields_val), format)

        snippets[name] = custom_command.create_snippet(create_snippet_format(fields_val))
        data[name] = custom_command.to_dict()

    with open(COMMAND_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    with open(SNIPPETS_PATH, "w", encoding="utf-8") as f:
        json.dump(snippets, f, indent=4)