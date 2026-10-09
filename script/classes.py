import logging
import re


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, filename="script.log")

COMMAND_START = '\\\\"'
COMMAND_END = '"\\\\'

FIELD_PLACEHOLDER_RE = re.compile(r'^([ \t]*)\{([^{}]+)\}', re.MULTILINE)

ESCAPED_FIELD = r'\s*\$\(.*?\)\$\s*'
STANDARD_NON_LAST_FIELD = '(?:' + ESCAPED_FIELD + '|[^:]+)'


def unwrap_escaped_field(value):
    if value.startswith("$(") and value.endswith(")$"):
        return value[2:-2].strip()
    return value


def reindent_field_values(format_str, field_values):
    reindented = dict(field_values)
    for indent, name in FIELD_PLACEHOLDER_RE.findall(format_str):
        value = reindented.get(name)
        if isinstance(value, str) and "\n" in value and indent:
            reindented[name] = value.replace("\n", "\n" + indent)
    return reindented


def propagate_calling_indent(text, match, result):
    line_start = text.rfind("\n", 0, match.start()) + 1
    indent = text[line_start:match.start()]
    if "\n" in result and indent.strip() == "":
        result = result.replace("\n", "\n" + indent)
    return result


class Command:


    def __init__(self, name, regex, format, lookup, fields):
        self.name = name
        self.regex = regex
        self.format = format
        self.lookup = lookup
        self.fields = fields 
        self.success = 0
        self.error = 0

    def substitute(self, text):
        def repl(match):
            logger.info(f"Replacing text using command with regex: {self.regex.pattern}")
            groups = match.groups()
            groups = tuple(map(lambda x: x.strip(), groups))

            logger.info(f"Matched groups: {groups}")
            field_values = dict(zip(self.fields, groups))
            if groups[0] in self.lookup:
                self.success += 1
                value = self.lookup[groups[0]]
                if isinstance(value, (list, tuple)):
                    field_values.update(zip(self.fields, value))
                else:
                    field_values[self.fields[0]] = value
                field_values = reindent_field_values(self.format, field_values)
                result = self.format.format(*groups, **field_values)
            else:
                self.error += 1
                logger.error(f"File '{groups[0]}' not found in lookup for command '{self.name}'.")
                result = self.missing_file_error(groups[0])

            result = propagate_calling_indent(text, match, result)
            return result


        return self.regex.sub(repl, text)
        
    def match(self, func, text):
        return self.regex.sub(func, text)
    
    def success_message(self):
        if self.success > 0:
            print(f"[SUCCESS] Command '{self.name}' successfully replaced {self.success} instances in the user guide.")
        if self.error > 0:
            print(f"[WARN] Command '{self.name}' encountered {self.error} errors during replacement. Check script.log for details.")

    def missing_file_error(self, filename):
        return f"Error: File '{filename}' not found for command '{self.name}'."
    
    @staticmethod
    def build_standard_regex(prefix, num_fields, allow_escaped_fields=False):
        non_last_field = STANDARD_NON_LAST_FIELD if allow_escaped_fields else '[^:]+'
        groups = ['(' + non_last_field + ')'] * (num_fields - 1) + ['(.+?)']
        pattern = COMMAND_START + prefix + ":" + ":".join(groups) + COMMAND_END
        return re.compile(pattern, re.MULTILINE | re.DOTALL)

class CustomCommand:
    CUSTOM_COMMAND_START = '!"'
    CUSTOM_COMMAND_END = '"!'

    def __init__(self, name, fields, format):
        self.name = name
        self.fields = fields
        self.format = format
        self.success = 0
        self.regex = Command.build_standard_regex("custom:" + name, len(fields), allow_escaped_fields=True)
    
    def substitute(self, text):
        def repl(match):
            self.success += 1
            groups = match.groups()
            groups = tuple(map(lambda x: x.strip(), groups))
            groups = tuple(map(unwrap_escaped_field, groups))

            field_values = dict(zip(self.fields, groups))
            field_values = reindent_field_values(self.format, field_values)
            result = self.format.format(*groups, **field_values)
            result = propagate_calling_indent(text, match, result)
            return result
        return self.regex.sub(repl, text)

    def create_snippet(self, snippet_fields):
        dict = {}
        dict["scope"] = "markdown"
        dict["prefix"] = "custom:" + self.name
        dict["body"] = ("\\\"custom:" + self.name + ":" + snippet_fields + "\"\\")
        return dict

    @staticmethod
    def build_custom_regex(prefix, num_fields, command_start=CUSTOM_COMMAND_START, command_end=CUSTOM_COMMAND_END):
        groups = ['([^:]+)'] * (num_fields - 1) + ['(.+?)']
        pattern = command_start + prefix + ":" + ":".join(groups) + command_end
        return re.compile(pattern, re.MULTILINE | re.DOTALL)

    def to_dict(self):
        return {"name": self.name, "fields": list(self.fields), "format": self.format}

    def success_message(self):
        if self.success > 0:
            print(f"[SUCCESS] Command '{self.name}' successfully replaced {self.success} instances in the user guide.")
