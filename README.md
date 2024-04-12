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

