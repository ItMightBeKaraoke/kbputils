kbputils
========

This is a module containing utilities to handle .kbp files created with Karaoke Builder Studio. It's still very early development, but if you want to try it out, see some notes below.

Current contents are:

Parsers
-------

### Karaoke Builder Studio (.kbp)

    k = kbputils.KBPFile(filename)

### Doblon (full timing lyrics export .txt)

    d = kbputils.DoblonTxt(filename)

Converters
----------

### .kbp to .ass

    ass_converter = kbputils.AssConverter(k) # Several options are available to tweak processing
    doc = converter.ass_document()  # generate an ass.Document from the ass module
    with open("outputfile.ass", "w", encoding='utf_8_sig') as f:
        doc.dump_file(f)

### Doblon .txt to .kbp

    doblon_converter = kbputils.DoblonTxtConverter(d) # Several options are available to tweak processing
    kbp = doblon_converter.kbpFile()  # generate a KBPFile data structure
    with open("outputfile.kbp", "w", encoding='utf-8', newline='\r\n') as f:
        kbp.writeFile(f) # writeFile() can also just take a filename so you don't need to create a file handle like this

Converter CLIs
--------------

### .kbp to .ass

    $ KBPUtils kbp2ass --help
    usage: KBPUtils kbp2ass [-h] [--border | --no-border | -b] [--float-font | --no-float-font | -f] [--float-pos | --no-float-pos | -p]
                        [--target-x TARGET_X] [--target-y TARGET_Y] [--fade-in FADE_IN] [--fade-out FADE_OUT]
                        [--transparency | --no-transparency | -t] [--offset OFFSET] [--overflow {NO_WRAP,EVEN_SPLIT,TOP_SPLIT,BOTTOM_SPLIT}]
                        [--allow-kt | --no-allow-kt | -k] [--experimental-spacing | --no-experimental-spacing | -a] [--version]
                        source_file [dest_file]

    Convert .kbp to .ass file

    positional arguments:
      source_file
      dest_file

    options:
      -h, --help            show this help message and exit
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
      --allow-kt, --no-allow-kt, -k
                            bool (default: False)
      --experimental-spacing, --no-experimental-spacing, -a
                            bool (default: False)
      --version, -V         show program's version number and exit

### Doblon .txt to .kbp

    $ KBPUtils doblontxt2kbp --help
    usage: KBPUtils doblontxt2kbp [-h] [--title TITLE] [--artist ARTIST] [--audio-file AUDIO_FILE] [--comments COMMENTS]
                                  [--max-lines-per-page MAX_LINES_PER_PAGE] [--min-gap-for-new-page MIN_GAP_FOR_NEW_PAGE]
                                  [--display-before-wipe DISPLAY_BEFORE_WIPE] [--remove-after-wipe REMOVE_AFTER_WIPE] [--version]
                                  source_file [dest_file]

    Convert Doblon full timing .txt file to .kbp

    positional arguments:
      source_file
      dest_file

    options:
      -h, --help            show this help message and exit
      --title TITLE, -t TITLE
                            str (default: )
      --artist ARTIST, -a ARTIST
                            str (default: )
      --audio-file AUDIO_FILE, -f AUDIO_FILE
                            str (default: )
      --comments COMMENTS, -c COMMENTS
                            str (default: Created with kbputils Converted from Doblon .txt file)
      --max-lines-per-page MAX_LINES_PER_PAGE, -p MAX_LINES_PER_PAGE
                            int (default: 6)
      --min-gap-for-new-page MIN_GAP_FOR_NEW_PAGE, -g MIN_GAP_FOR_NEW_PAGE
                            int (default: 1000)
      --display-before-wipe DISPLAY_BEFORE_WIPE, -w DISPLAY_BEFORE_WIPE
                            int (default: 1000)
      --remove-after-wipe REMOVE_AFTER_WIPE, -i REMOVE_AFTER_WIPE
                            int (default: 500)
      --version, -V         show program's version number and exit

