kbputils
========

This is a module containing utilities to handle .kbp files created with Karaoke Builder Studio. It's still very early development, but if you want to try it out, see some notes below.

Current contents are:

kbputils module to parse a file into a data structure:

    k = kbputils.KBPFile(filename)

converters module which currently contains a basic converter to the .ass format:

    converter = kbputils.converters.AssConverter(k) # A few options are available, but not many yet
    doc = converter.ass_document()  # generate an ass.Document from the ass module
    with open("outputfile.ass", "w", encoding='utf_8_sig') as f:
        doc.dump_file(f)

There's also a CLI for it (command and syntax subject to change):

    $ KBPUtils --help
    usage: KBPUtils [-h] [--border | --no-border] [--float-font | --no-float-font] [--float-pos | --no-float-pos] [--target-x TARGET_X]
                    [--target-y TARGET_Y] [--fade-in FADE_IN] [--fade-out FADE_OUT] [--transparency | --no-transparency] [--offset OFFSET]
                    source_file [dest_file]
    
    Convert .kbp to .ass file
    
    positional arguments:
      source_file
      dest_file
    
    options:
      -h, --help            show this help message and exit
      --border, --no-border
                            bool (default: True)
      --float-font, --no-float-font
                            bool (default: True)
      --float-pos, --no-float-pos
                            bool (default: False)
      --target-x TARGET_X   int (default: 300)
      --target-y TARGET_Y   int (default: 216)
      --fade-in FADE_IN     int (default: 300)
      --fade-out FADE_OUT   int (default: 200)
      --transparency, --no-transparency
                            bool (default: True)
      --offset OFFSET       int | bool (default: True)
    
