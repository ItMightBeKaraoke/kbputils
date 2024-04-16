from . import kbp
from . import converters
import argparse
import dataclasses
import io

def convert_file():
    parser = argparse.ArgumentParser(prog='KBPUtils', description="Convert .kbp to .ass file", argument_default=argparse.SUPPRESS)
    for field in dataclasses.fields(converters.AssOptions):
        name = field.name.replace("_", "-")
        parser.add_argument(
            f"--{name}",
            gen_shortopt(name),
            dest = field.name,
            help = (field.type.__name__ if hasattr(field.type, '__name__') else repr(field.type)) + f" (default: {field.default})",
            type = int_or_bool if field.type == int | bool else field.type,
            action = argparse.BooleanOptionalAction if field.type == bool else 'store',
        )
    parser.add_argument("source_file")
    parser.add_argument("dest_file", nargs='?')
    args = parser.parse_args()
    source = args.source_file
    k = kbp.KBPFile(source)
    dest = open(args.dest_file, 'w', encoding='utf_8_sig') if hasattr(args, 'dest_file') else io.StringIO()
    del args.source_file
    if hasattr(args, 'dest_file'):
        del args.dest_file
    converters.AssConverter(k, **vars(args)).ass_document().dump_file(dest)
    if type(dest) is io.StringIO:
        print(dest.getvalue())

# Auto-generate short option based on field name
used_shortopts=set("h")
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
