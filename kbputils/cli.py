from . import kbp
from . import converters
from . import __version__
import argparse
import dataclasses
import io
import sys

def convert_file():
    parser = argparse.ArgumentParser(prog='KBPUtils', description="Convert .kbp to .ass file", argument_default=argparse.SUPPRESS)
    parser.add_argument("--version", "-V", action="version", version=__version__)
    for field in dataclasses.fields(converters.AssOptions):
        name = field.name.replace("_", "-")

        additional_params = {}
        if field.type == int | bool:
            additional_params["type"] = int_or_bool 
        elif hasattr(field.type, "__members__") and hasattr(field.type, "__getitem__"):
            # Handle enum types
            additional_params["type"] = field.type.__getitem__
            additional_params["choices"] = field.type.__members__.values()
        else:
            additional_params["type"] = field.type

        parser.add_argument(
            f"--{name}",
            gen_shortopt(name),
            dest = field.name,
            help = (field.type.__name__ if hasattr(field.type, '__name__') else repr(field.type)) + f" (default: {field.default})",
            action = argparse.BooleanOptionalAction if field.type == bool else 'store',
            **additional_params,
        )
    parser.add_argument("source_file")
    parser.add_argument("dest_file", nargs='?')
    args = parser.parse_args()
    source = args.source_file
    k = kbp.KBPFile(sys.stdin if source == "-" else source)
    dest = open(args.dest_file, 'w', encoding='utf_8_sig') if hasattr(args, 'dest_file') else io.StringIO()
    del args.source_file
    if hasattr(args, 'dest_file'):
        del args.dest_file
    converters.AssConverter(k, **vars(args)).ass_document().dump_file(dest)
    if type(dest) is io.StringIO:
        print(dest.getvalue())

# Auto-generate short option based on field name
used_shortopts=set("hV")
def gen_shortopt(longopt):
    # Options with - likely have duplication, so use a letter from after the
    # last one
    if len(parts := longopt.split("-")) > 1:
        return gen_shortopt(parts[-1])
    for char in longopt:
        if char not in used_shortopts:
            used_shortopts.add(char)
            return f"-{char}"

# Coerce a string value into a bool or int
# Accept true|false (case-insensitive), otherwise try int
def int_or_bool(strVal):
    if strVal.upper() == 'FALSE':
        return False
    elif strVal.upper() == 'TRUE':
        return True
    else:
        return int(strVal)

if __name__ == "__main__":
    convert_file()
