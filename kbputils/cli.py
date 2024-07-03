from . import kbp
from . import doblontxt
from . import converters
from . import __version__
import argparse
import dataclasses
import io
import sys
import collections

def convert_file():
    parser = argparse.ArgumentParser(prog='KBPUtils', description="Various utilities for .kbp files", argument_default=argparse.SUPPRESS)

    parser_data = {
        'kbp2ass': {
            'add_parser': {
                'description': 'Convert .kbp to .ass file',
                'argument_default': argparse.SUPPRESS
            },
            'input': kbp.KBPFile,
            'output': lambda source, args, dest: converters.AssConverter(source, **vars(args)).ass_document().dump_file(dest),
            'output_opts': {
                'encoding': 'utf_8_sig'
            },
            'options': converters.AssOptions
        },
        'doblontxt2kbp': {
            'add_parser': {
                'description': 'Convert Doblon full timing .txt file to .kbp',
                'argument_default': argparse.SUPPRESS
            },
            'input': doblontxt.DoblonTxt,
            'output': lambda source, args, dest: converters.DoblonTxtConverter(source, **vars(args)).kbpFile().writeFile(dest),
            'output_opts': {
                'encoding': 'utf-8',
                'newline': '\r\n'
            },
            'options': converters.DoblonTxtOptions
        }
    }

    subparsers = parser.add_subparsers(dest='subparser', required=True)

    for p in parser_data:
        cur = subparsers.add_parser(p, **parser_data[p]['add_parser'])

        for field in dataclasses.fields(parser_data[p]['options']):
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

            cur.add_argument(
                f"--{name}",
                gen_shortopt(p, name),
                dest = field.name,
                help = (field.type.__name__ if hasattr(field.type, '__name__') else repr(field.type)) + f" (default: {field.default})",
                action = argparse.BooleanOptionalAction if field.type == bool else 'store',
                **additional_params,
            )

        cur.add_argument("--version", "-V", action="version", version=__version__)
        cur.add_argument("source_file")
        cur.add_argument("dest_file", nargs='?')

    args = parser.parse_args()
    subparser = args.subparser
    del args.subparser
    source = parser_data[subparser]['input'](sys.stdin if args.source_file == "-" else args.source_file)
    del args.source_file
    dest = open(args.dest_file, 'w', **parser_data[subparser]['output_opts']) if hasattr(args, 'dest_file') else sys.stdout
    if hasattr(args, 'dest_file'):
        del args.dest_file
    parser_data[subparser]['output'](source, args, dest)

# Auto-generate short option based on field name
used_shortopts=collections.defaultdict(lambda: set("hV"))
def gen_shortopt(command, longopt):
    # Options with - likely have duplication, so use a letter from after the
    # last one
    if len(parts := longopt.split("-")) > 1:
        return gen_shortopt(command, parts[-1])
    for char in longopt:
        if char not in used_shortopts[command]:
            used_shortopts[command].add(char)
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
