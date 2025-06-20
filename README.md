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

### Enhanced .lrc

    l = kbputils.LRC(filename)

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

### Enhanced .lrc to .kbp

    lrc_converter = kbputils.LRCConverter(l) # Several options are available to tweak processing
    kbp = lrc_converter.kbpFile()  # generate a KBPFile data structure
    with open("outputfile.kbp", "w", encoding='utf-8', newline='\r\n') as f:
        kbp.writeFile(f) # writeFile() can also just take a filename so you don't need to create a file handle like this

Utilities
---------

### KBP file validation and problem resolution

    k = kbputils.KBPFile(filename, tolerant_parsing=True)
    syntax_errors = k.onload_modifications # If you save out the file now, it will correct these immediately
    logic_errors = k.logicallyValidate() # These may have more than one possible resolutions
    action_choices = errors[0].propose_solutions(k) # Provide possible solutions for the first error
    action_choices[0].run(k) # Run the first solution - note that some actions require extra parameters, listed in a free_params attr

### File update operations

    # Long form - Subtract 5cs from the start and end wipe timings for all syllables on the first two pages
    action = kbputils.KBPAction(kbputils.KBPActionType.ChangeTiming, params={
        "target": kbputils.KBPTimingTarget.Wipe,
        "anchor": kbputils.KBPTimingAnchor.Both,
        "pages": slice(0,3),
        "value": -5
    })
    action.run(k)
    # Slightly shorter form of the same
    kbputils.KBPActionType.ChangeTiming(k, target=kbputils.KBPTimingTarget.Wipe, anchor=kbputils.KBPTimingAnchor.Both, pages=slice(0,3), value=-5)
    # Join the first 5 syllables on page 2, line 3 (zero-indexed)
    kbputils.KBPActionType.JoinSyllables(k, pages=2, line=3, syllables=slice(0,6))
    # Change the style of all lines on the first page to style 6
    kbputils.KBPActionType.ChangeLineStyle(k, pages=0, style=6)
    # Copy style 1 to style 7
    kbputils.KBPActionType.CopyStyle(k, source=1, destination=7)
    # Save out the modified file
    k.writeFile("new_file.kbp")

If the title, author, and comment options are not overridden when constructing the converter and are specified in the appropriate LRC tags, those are used in the .kbp.

Converter CLIs
--------------

### .kbp to .ass

    $ KBPUtils kbp2ass --help
    usage: KBPUtils kbp2ass [-h] [--border | --no-border | -b] [--float-font | --no-float-font | -f]
                            [--float-pos | --no-float-pos | -p] [--target-x TARGET_X] [--target-y TARGET_Y] [--fade-in FADE_IN]
                            [--fade-out FADE_OUT] [--transparency | --no-transparency | -t] [--offset OFFSET]
                            [--overflow {NO_WRAP,EVEN_SPLIT,TOP_SPLIT,BOTTOM_SPLIT}] [--allow-kt | --no-allow-kt | -k]
                            [--experimental-spacing | --no-experimental-spacing | -a]
                            [--tolerant-parsing | --no-tolerant-parsing | -r]
                            source_file [dest_file]

    Convert .kbp to .ass file

    positional arguments:
      source_file
      dest_file

    options:
      -h, --help            show this help message and exit
      --border, --no-border, -b
                            Add CDG-style borders to margins (default: True)
      --float-font, --no-float-font, -f
                            Use floating point in output font sizes (well-supported in renderers) (default: True)
      --float-pos, --no-float-pos, -p
                            Use floating point in \pos and margins (supported by recent libass) (default: False)
      --target-x, -x TARGET_X
                            Output width (default: 300)
      --target-y, -y TARGET_Y
                            Output height (default: 216)
      --fade-in, -i FADE_IN
                            Fade duration for line display (ms) (default: 300)
      --fade-out, -o FADE_OUT
                            Fade duration for line removal (ms) (default: 200)
      --transparency, --no-transparency, -t
                            Treat palette index 1 as transparent (default: True)
      --offset, -s OFFSET   How to handle KBS offset. False => disable offset (same as 0), True => pull from KBS config, int is
                            offset in ms (default: True)
      --overflow, -v {NO_WRAP,EVEN_SPLIT,TOP_SPLIT,BOTTOM_SPLIT}
                            How to handle lines wider than the screen (default: EVEN_SPLIT)
      --allow-kt, --no-allow-kt, -k
                            Use \kt if there are overlapping wipes on the same line (not supported by all ass implementations)
                            (default: False)
      --experimental-spacing, --no-experimental-spacing, -a
                            Calculate the "style 1" spacing instead of using Arial 12 bold default (only works for select fonts)
                            (default: False)
      --tolerant-parsing, --no-tolerant-parsing, -r
                            Automatically fix syntax errors in .kbp file if they have an unambiguous interpretation (default:
                            False)

### Doblon .txt to .kbp

    $ KBPUtils doblontxt2kbp --help
    usage: KBPUtils doblontxt2kbp [-h] [--title TITLE] [--artist ARTIST] [--audio-file AUDIO_FILE] [--comments COMMENTS]
                              [--max-lines-per-page MAX_LINES_PER_PAGE] [--min-gap-for-new-page MIN_GAP_FOR_NEW_PAGE]
                              [--display-before-wipe DISPLAY_BEFORE_WIPE] [--remove-after-wipe REMOVE_AFTER_WIPE]
                              [--template-file TEMPLATE_FILE]
                              source_file [dest_file]

    Convert Doblon full timing .txt file to .kbp

    positional arguments:
      source_file
      dest_file

    options:
      -h, --help            show this help message and exit
      --title, -t TITLE     str (default: )
      --artist, -a ARTIST   str (default: )
      --audio-file, -f AUDIO_FILE
                            str (default: )
      --comments, -c COMMENTS
                            str (default: Created with kbputils Converted from Doblon .txt file)
      --max-lines-per-page, -p MAX_LINES_PER_PAGE
                            int (default: 6)
      --min-gap-for-new-page, -g MIN_GAP_FOR_NEW_PAGE
                            int (default: 1000)
      --display-before-wipe, -w DISPLAY_BEFORE_WIPE
                            int (default: 1000)
      --remove-after-wipe, -i REMOVE_AFTER_WIPE
                            int (default: 500)
      --template-file, -l TEMPLATE_FILE
                            str (default: )


### Enhanced .lrc to .kbp

    $ KBPUtils lrc2kbp --help
    usage: KBPUtils lrc2kbp [-h] [--title TITLE] [--artist ARTIST] [--audio-file AUDIO_FILE] [--comments COMMENTS]
                            [--max-lines-per-page MAX_LINES_PER_PAGE] [--min-gap-for-new-page MIN_GAP_FOR_NEW_PAGE]
                            [--display-before-wipe DISPLAY_BEFORE_WIPE] [--remove-after-wipe REMOVE_AFTER_WIPE]
                            [--template-file TEMPLATE_FILE]
                            source_file [dest_file]

    Convert Enhanced .lrc to .kbp

    positional arguments:
      source_file
      dest_file

    options:
      -h, --help            show this help message and exit
      --title, -t TITLE     str (default: )
      --artist, -a ARTIST   str (default: )
      --audio-file, -f AUDIO_FILE
                            str (default: )
      --comments, -c COMMENTS
                            str (default: Created with kbputils Converted from Enhanced LRC file)
      --max-lines-per-page, -p MAX_LINES_PER_PAGE
                            int (default: 6)
      --min-gap-for-new-page, -g MIN_GAP_FOR_NEW_PAGE
                            int (default: 1000)
      --display-before-wipe, -w DISPLAY_BEFORE_WIPE
                            int (default: 1000)
      --remove-after-wipe, -i REMOVE_AFTER_WIPE
                            int (default: 500)
      --template-file, -l TEMPLATE_FILE
                            str (default: )

Utility CLIs
-------------

### Check/resolve kbp file issues

    $ KBPUtils kbpcheck --help
    usage: KBPUtils kbpcheck [-h] [--suggestions | --no-suggestions | -s] [--interactive | --no-interactive | -i]
                             [--overwrite | --no-overwrite | -o] [--tolerant-parsing | --no-tolerant-parsing | -p]
                             source_file [dest_file]
    
    Discover logic errors in kbp files
    
    positional arguments:
      source_file
      dest_file
    
    options:
      -h, --help            show this help message and exit
      --suggestions, --no-suggestions, -s
                            Provide suggestions for fixing problems (default: False)
      --interactive, --no-interactive, -i
                            Start an interactive session to fix problems (default: False)
      --overwrite, --no-overwrite, -o
                            Allow in-place overwriting of file in interactive mode. Not recommended! (default: False)
      --tolerant-parsing, --no-tolerant-parsing, -p
                            Automatically fix syntax errors in .kbp file if they have an unambiguous interpretation (default:
                            False)

