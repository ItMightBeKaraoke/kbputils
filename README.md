kbputils
========

This is a module containing utilities to handle .kbp files created with Karaoke Builder Studio. It's still very early development, but if you want to try it out, see some notes below.

Current contents are:

kbputils module to parse a file into a data structure:

    k = kbputils.KBPFile(filename)

converters module which currently contains a converter to the .ass format:

    converter = kbputils.converters.AssConverter(k) # Several options are available to tweak processing
    doc = converter.ass_document()  # generate an ass.Document from the ass module
    with open("outputfile.ass", "w", encoding='utf_8_sig') as f:
        doc.dump_file(f)

There's also a CLI for it (command and syntax subject to change):

    $ KBPUtils --help
    usage: KBPUtils [-h] [--version] [--border | --no-border | -b] [--float-font | --no-float-font | -f] [--float-pos | --no-float-pos | -p]
                [--target-x TARGET_X] [--target-y TARGET_Y] [--fade-in FADE_IN] [--fade-out FADE_OUT] [--transparency | --no-transparency | -t]
                [--offset OFFSET] [--overflow {NO_WRAP,EVEN_SPLIT,TOP_SPLIT,BOTTOM_SPLIT}]
                source_file [dest_file]

    Convert .kbp to .ass file

    positional arguments:
      source_file
      dest_file

    options:
      -h, --help            show this help message and exit
      --version, -V         show program's version number and exit
      --border, --no-border, -b
                            bool (default: True)
      --float-font, --no-float-font, -f
                            bool (default: True)
      --float-pos, --no-float-pos, -p
                            bool (default: False)
      --target-x TARGET_X, -x TARGET_X
                            int (default: 300)
      --target-y TARGET_Y, -y TARGET_Y
                            int (default: 216)
      --fade-in FADE_IN, -i FADE_IN
                            int (default: 300)
      --fade-out FADE_OUT, -o FADE_OUT
                            int (default: 200)
      --transparency, --no-transparency, -t
                            bool (default: True)
      --offset OFFSET, -s OFFSET
                            int | bool (default: True)
      --overflow {NO_WRAP,EVEN_SPLIT,TOP_SPLIT,BOTTOM_SPLIT}, -v {NO_WRAP,EVEN_SPLIT,TOP_SPLIT,BOTTOM_SPLIT}
                            AssOverflow (default: EVEN_SPLIT)

