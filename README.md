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

### .ass to video (requires ffmpeg dependency)

    video_converter = kbputils.VideoConverter(
        "source_file.ass",
        "dest_file.mp4",
        audio_file="something.flac") # Numerous additional options, see ass2video CLI docs below
    video_converter.run()

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

### .ass to video file (if ffmpeg dependency is installed)

    $ KBPUtils ass2video --help
    usage: KBPUtils ass2video [-h] [--preview | --no-preview | -p] [--audio-file AUDIO_FILE] [--aspect-ratio ASPECT_RATIO]
                              [--target-x TARGET_X] [--target-y TARGET_Y] [--background-color BACKGROUND_COLOR]
                              [--background-media BACKGROUND_MEDIA]
                              [--loop-background-video | --no-loop-background-video | -v] [--media-container MEDIA_CONTAINER]
                              [--video-codec VIDEO_CODEC] [--video-quality VIDEO_QUALITY] [--audio-codec AUDIO_CODEC]
                              [--audio-bitrate AUDIO_BITRATE] [--intro-media INTRO_MEDIA] [--outro-media OUTRO_MEDIA]
                              [--intro-length INTRO_LENGTH] [--outro-length OUTRO_LENGTH] [--intro-fadeIn INTRO_FADEIN]
                              [--outro-fadeIn OUTRO_FADEIN] [--intro-fadeOut INTRO_FADEOUT] [--outro-fadeOut OUTRO_FADEOUT]
                              [--intro-concat | --no-intro-concat | -t] [--outro-concat | --no-outro-concat | -C]
                              [--intro-fade-black | --no-intro-fade-black | -k]
                              [--outro-fade-black | --no-outro-fade-black | -B] [--intro-sound | --no-intro-sound | -s]
                              [--outro-sound | --no-outro-sound | -S] [--output-options OUTPUT_OPTIONS]
                              source_file [dest_file]
    
    Render .ass subtitle to a video
    
    positional arguments:
      source_file           input file
      dest_file             output file
    
    options:
      -h, --help            show this help message and exit
      --preview, --no-preview, -p
                            If set, do not run ffmpeg, only output the command that would be run (default: False)
      --audio-file, -f AUDIO_FILE
                            Audio track to use with video (default: None)
      --aspect-ratio, -r ASPECT_RATIO
                            Aspect ratio of rendered subtitle. This will be letterboxed if not equal to the aspect ratio of
                            the output video (default: 25:18)
      --target-x, -x TARGET_X
                            Output video width (default: 1500)
      --target-y, -y TARGET_Y
                            Output video height (default: 1080)
      --background-color, -c BACKGROUND_COLOR
                            Background color for the video, as 24-bit RGB hex value (default: #000000)
      --background-media, -m BACKGROUND_MEDIA
                            Path to image or video to play in the background of the video (default: None)
      --loop-background-video, --no-loop-background-video, -v
                            If using a background video, leaving this unset will play the background video exactly once,
                            repeating the last frame if shorter than the audio, or continuing past the end of the audio if
                            longer. If set, the background video will instead loop exactly as many times needed (including
                            fractionally) to match the audio. (default: False)
      --media-container, -o MEDIA_CONTAINER
                            Container file type to use for video output. If unspecified, will allow ffmpeg to infer from
                            provided output filename (default: None)
      --video-codec, -d VIDEO_CODEC
                            Codec to use for video output (default: h264)
      --video-quality, -q VIDEO_QUALITY
                            Video encoding quality, uses a CRF scale so lower values are higher quality. Recommended settings
                            are 15-35, though it can vary between codecs. Set to 0 for lossless (default: 23)
      --audio-codec, -e AUDIO_CODEC
                            Codec to use for audio output (default: aac)
      --audio-bitrate, -b AUDIO_BITRATE
                            Bitrate for audio output, in kbps (default: 256)
      --intro-media, -i INTRO_MEDIA
                            Image or video file to play at start of track, layered above the background, but below any
                            subtitles (default: None)
      --outro-media, -a OUTRO_MEDIA
                            Image or video file to play at end of track, layered above the background, but below any subtitles
                            (default: None)
      --intro-length, -l INTRO_LENGTH
                            Time in milliseconds to play the intro if a file was specified (default: 0)
      --outro-length, -n OUTRO_LENGTH
                            Time in milliseconds to play the outro if a file was specified (default: 0)
      --intro-fadeIn, -I INTRO_FADEIN
                            Time in milliseconds to fade in the intro (default: 0)
      --outro-fadeIn, -F OUTRO_FADEIN
                            Time in milliseconds to fade in the outro (default: 0)
      --intro-fadeOut, -O INTRO_FADEOUT
                            Time in milliseconds to fade out the intro (default: 0)
      --outro-fadeOut, -u OUTRO_FADEOUT
                            Time in milliseconds to fade out the outro (default: 0)
      --intro-concat, --no-intro-concat, -t
                            Play the intro before the audio/video starts instead of inserting at time 0 (default: False)
      --outro-concat, --no-outro-concat, -C
                            Play the outro before the audio/video starts instead of inserting at time 0 (default: False)
      --intro-fade-black, --no-intro-fade-black, -k
                            Fade in the video from a black screen instead of showing the background media immediately
                            (default: False)
      --outro-fade-black, --no-outro-fade-black, -B
                            Fade the video out to a black screen instead of fading back to the background media (default:
                            False)
      --intro-sound, --no-intro-sound, -s
                            Preserve audio in the intro (if video). Note that when using without the intro_concat option, this
                            will mix without normalization, and may cause clipping (default: False)
      --outro-sound, --no-outro-sound, -S
                            Preserve audio in the outro (if video). Note that when using without the outro_concat option, this
                            will mix without normalization, and may cause clipping (default: False)
      --output-options, -P OUTPUT_OPTIONS
                            Additional parameters to pass to ffmpeg (default: {"pix_fmt": "yuv420p"})

### Doblon .txt to .kbp

    $ KBPUtils doblontxt2kbp --help
    usage: KBPUtils doblontxt2kbp [-h] [--title TITLE] [--artist ARTIST] [--audio-file AUDIO_FILE] [--comments COMMENTS]
                                  [--max-lines-per-page MAX_LINES_PER_PAGE] [--min-gap-for-new-page MIN_GAP_FOR_NEW_PAGE]
                                  [--display-before-wipe DISPLAY_BEFORE_WIPE] [--remove-after-wipe REMOVE_AFTER_WIPE]
                                  [--template-file TEMPLATE_FILE]
                                  source_file [dest_file]

    Convert Doblon full timing .txt file to .kbp
    
    positional arguments:
      source_file           input file
      dest_file             output file
    
    options:
      -h, --help            show this help message and exit
      --title, -t TITLE     Title field to use in kbp file (default: )
      --artist, -a ARTIST   Artist field to use in kbp file (default: )
      --audio-file, -f AUDIO_FILE
                            Audio file associated with this subtitle (default: )
      --comments, -c COMMENTS
                            Comment field to use in kbp file (default: Created with kbputils)
      --max-lines-per-page, -p MAX_LINES_PER_PAGE
                            Maximum number of lines to leave per page after initial page splitting rules applied (default:
                            6)
      --min-gap-for-new-page, -g MIN_GAP_FOR_NEW_PAGE
                            Time in ms between the removal of a line and the display of the next before a page break is
                            added (default: 1000)
      --display-before-wipe, -w DISPLAY_BEFORE_WIPE
                            Amount of time in ms that a line is displayed before it starts wiping (default: 1000)
      --remove-after-wipe, -i REMOVE_AFTER_WIPE
                            Amount of time in ms that a line is removed after it finishes wiping (default: 500)
      --template-file, -l TEMPLATE_FILE
                            KBS template or project file (.kbt or .kbp) containing the styles and project settings to use
                            (default: None)

### Enhanced .lrc to .kbp

    $ KBPUtils lrc2kbp --help
    usage: KBPUtils lrc2kbp [-h] [--title TITLE] [--artist ARTIST] [--audio-file AUDIO_FILE] [--comments COMMENTS]
                            [--max-lines-per-page MAX_LINES_PER_PAGE] [--min-gap-for-new-page MIN_GAP_FOR_NEW_PAGE]
                            [--display-before-wipe DISPLAY_BEFORE_WIPE] [--remove-after-wipe REMOVE_AFTER_WIPE]
                            [--template-file TEMPLATE_FILE]
                            source_file [dest_file]
    
    Convert Enhanced or MidiCo .lrc to .kbp
    
    positional arguments:
      source_file           input file
      dest_file             output file
    
    options:
      -h, --help            show this help message and exit
      --title, -t TITLE     Title field to use in kbp file (default: )
      --artist, -a ARTIST   Artist field to use in kbp file (default: )
      --audio-file, -f AUDIO_FILE
                            Audio file associated with this subtitle (default: )
      --comments, -c COMMENTS
                            Comment field to use in kbp file (default: Created with kbputils)
      --max-lines-per-page, -p MAX_LINES_PER_PAGE
                            Maximum number of lines to leave per page after initial page splitting rules applied (default:
                            6)
      --min-gap-for-new-page, -g MIN_GAP_FOR_NEW_PAGE
                            Time in ms between the removal of a line and the display of the next before a page break is
                            added (default: 1000)
      --display-before-wipe, -w DISPLAY_BEFORE_WIPE
                            Amount of time in ms that a line is displayed before it starts wiping (default: 1000)
      --remove-after-wipe, -i REMOVE_AFTER_WIPE
                            Amount of time in ms that a line is removed after it finishes wiping (default: 500)
      --template-file, -l TEMPLATE_FILE
                            KBS template or project file (.kbt or .kbp) containing the styles and project settings to use
                            (default: None)

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

