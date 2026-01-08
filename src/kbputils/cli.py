from . import kbp
from . import doblontxt
from . import lrc
from . import converters
from . import misc
from . import __version__
import argparse
import dataclasses
import io
import os
import sys
import collections
import string
import json

# Shows a usage message for the main command and all subcommands.
# Requires an attribute added_subparsers since ArgumentParser normally
# doesn't provide an API for retrieving them and would require something
# unreliable like this:
# added_subparsers = parser._subparsers._name_parser_map.values()
class _UsageAllAction(argparse.Action):
    def __init__(self,
         option_strings,
         dest=argparse.SUPPRESS,
         default=argparse.SUPPRESS,
         help=None):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        print(parser.format_usage())
        for p in parser.added_subparsers:
            print(p.format_usage())
        parser.exit()

@dataclasses.dataclass
class KBPInputOptions:
    tolerant_parsing: bool = dataclasses.field(default=False, metadata={'doc': "Automatically fix syntax errors in .kbp file if they have an unambiguous interpretation"})


def convert_file():
    parser = argparse.ArgumentParser(
            prog='KBPUtils',
            description="Various utilities for .kbp files",
            epilog=f"Each utility has its own help, e.g. KBPUtils kbp2ass --help",
            argument_default=argparse.SUPPRESS,
        )

    parser_data = {
        'kbp2ass': {
            'add_parser': {
                'description': 'Convert .kbp to .ass file',
                'argument_default': argparse.SUPPRESS
            },
            'input': kbp.KBPFile,
            'input_options': KBPInputOptions,
            'output': lambda source, args, dest: converters.AssConverter(source, **vars(args)).ass_document().dump_file(dest),
            'output_opts': {
                'encoding': 'utf_8_sig'
            },
            'options': converters.AssOptions
        },
        **({'ass2video': {
            'add_parser': {
                'description': 'Render .ass subtitle to a video',
                'argument_default': argparse.SUPPRESS
            },
            'input': None,
            'output': lambda source, args, dest: converters.VideoConverter(source, dest, **vars(args)).run(),
            'output_opts': None,
            'options': converters.VideoOptions
        }} if converters.ffmpeg_available else {}),
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
        },
        'lrc2kbp': {
            'add_parser': {
                'description': 'Convert Enhanced or MidiCo .lrc to .kbp',
                'argument_default': argparse.SUPPRESS
            },
            'input': lrc.LRC,
            'output': lambda source, args, dest: converters.LRCConverter(source, **vars(args)).kbpFile().writeFile(dest),
            'output_opts': {
                'encoding': 'utf-8',
                'newline': '\r\n'
            },
            'options': converters.LRCOptions
        },
        'kbpcheck': {
            'add_parser': {
                'description': 'Discover logic errors in kbp files',
                'argument_default': argparse.SUPPRESS
            },
            'input': kbp.KBPFile,
            'input_options': KBPInputOptions,
            'output': misc.kbpcheck,
            'output_opts': None, # needs the filename instead of handle so it can write selectively in interactive mode
            'options': misc.KBPCheckOptions
        },
    }

    parser.add_argument("--version", "-V", action="version", version=__version__)

    subparsers = parser.add_subparsers(dest='subparser', required=True)

    # See _UsageAllAction
    parser.added_subparsers = []
    parser.register('action', 'usage_all', _UsageAllAction)
    parser.add_argument("--usage-all", action='usage_all', help = "show usage for all subcommands and exit")

    for p in parser_data:
        cur = subparsers.add_parser(p, **parser_data[p]['add_parser'])
        parser.added_subparsers.append(cur)

        for field in (
                dataclasses.fields(parser_data[p]['options']) if 'options' in parser_data[p] else ()
            ) + (
                dataclasses.fields(parser_data[p]['input_options']) if 'input_options' in parser_data[p] else ()
            ):
            name = field.name.replace("_", "-")

            additional_params = {}
            if field.metadata.get('existing_file'):
                additional_params["type"] = existing_file
            elif field.metadata.get('new_file'):
                additional_params["type"] = new_file
            elif field.type == int | bool:
                additional_params["type"] = int_or_bool 
            elif field.type == str | None:
                # TODO: more general
                additional_params["type"] = str
            elif field.type == dict:
                additional_params["type"] = json_dict
            elif hasattr(field.type, "__members__") and hasattr(field.type, "__getitem__"):
                # Handle enum types
                additional_params["type"] = field.type.__getitem__
                additional_params["choices"] = field.type.__members__.values()
            # Apparently in Python 3.14+, BooleanOptionalAction no longer supports a type parameter
            elif field.type != bool:
                additional_params["type"] = field.type

            help_text = ''
            if 'doc' in field.metadata:
                help_text += field.metadata['doc']
            elif hasattr(field.type, '__name__'):
                help_text += field.type.__name__
            else:
                help_text += repr(field.type)
            help_text += f" (default: {json.dumps(field.default_factory()) if isinstance(field.default, dataclasses._MISSING_TYPE) else field.default})"
            cur.add_argument(
                f"--{name}",
                gen_shortopt(p, name),
                dest = field.name,
                #help = (field.type.__name__ if hasattr(field.type, '__name__') else repr(field.type)) + f" (default: {field.default})",
                help = help_text,
                action = argparse.BooleanOptionalAction if field.type == bool else 'store',
                **additional_params,
            )

        # Ideally these could use argparse.FileType but it doesn't support the newline options
        cur.add_argument("source_file", type=existing_file, help='input file')
        cur.add_argument("dest_file", nargs='?', type=new_file, help='output file')

    args = parser.parse_args()

    subparser = args.subparser
    input_options = {}
    if 'input_options' in parser_data[subparser]:
        for field in dataclasses.fields(parser_data[subparser]['input_options']):
            if not hasattr(args, field.name):
                continue
            input_options[field.name] = getattr(args, field.name)
            delattr(args, field.name)
    del args.subparser
    if parser_data[subparser]['input']:
        source = parser_data[subparser]['input'](sys.stdin if args.source_file == "-" else args.source_file, **input_options)
    else:
        # If source handler not specified, provide the raw filename to the converter (it must also natively support "-" for stdin)
        source = args.source_file
    del args.source_file
    if parser_data[subparser]['output_opts'] is None:
        dest = args.dest_file if hasattr(args, 'dest_file') else None
    else:
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
    for char in longopt + longopt.upper() + string.ascii_uppercase:
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

def json_dict(strVal):
    res = json.loads(strVal)
    if not isinstance(res, dict):
        raise ValueError("Expected argument to be json serialization of dict")
    return res

def existing_file(strVal):
    if not os.path.isfile(strVal):
        raise ValueError("Expected argument to be existing file")
    return strVal

def new_file(strVal):
    if not os.path.isdir(os.path.dirname(strVal) or '.'):
        raise ValueError("Expected argument to be a valid place to write")
    return strVal

if __name__ == "__main__":
    convert_file()
