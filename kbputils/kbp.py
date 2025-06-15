import collections
import re
import string
import typing
import io
import warnings
import os.path
import enum
from . import validators

@enum.unique
class KBPErrorCode(enum.Enum):
    # KBPLine
    NegativeLineStart = enum.auto()
    NegativeLineEnd = enum.auto()
    LineStyleMissing = enum.auto()
    # KBPSyllable
    WipeStartBeforeLine = enum.auto()
    WipeEndAfterLine = enum.auto()
    ZeroWipeTiming = enum.auto()

@validators.validated_instantiation
class KBPErrorDetails(typing.NamedTuple):
    error: KBPErrorCode
    page: int
    line: int
    syllable: int | None = None
    value: int | None = None

class KBPFile:

    DIVIDER = "-----------------------------"
    HEADER_START = "\n".join((
        DIVIDER,
        "KARAOKE BUILDER STUDIO",
        "www.KaraokeBuilder.com",
        "",
        DIVIDER,
        "HEADERV2",
        "",
        "'--- Template Information ---",
        "\n"
    ))

    def __init__(self, kbpFile=None, **kwargs):
        self.pages = []
        self.images = []
        self.lyrics = [] # Unsynced lyrics
        if kbpFile is None:
            self.colors = KBPPalette("055","FFF","000","E70","940","CFF","033","0DD","077","FCF","303","F3F","818","000","FFF","000")
            self.styles = KBPStyleCollection({1: KBPStyle(style_no=1, name='Default', textcolor=1, outlinecolor=2, textwipecolor=3, outlinewipecolor=4, fontname='Arial', fontsize=12, fontstyle='B', charset=0, outlines=[2, 2, 2, 2], shadows=[0, 0], wipestyle=0, allcaps='L', fixed=False), 2: KBPStyle(style_no=2, name='Male', textcolor=5, outlinecolor=6, textwipecolor=7, outlinewipecolor=8, fontname='Arial', fontsize=12, fontstyle='B', charset=0, outlines=[2, 2, 2, 2], shadows=[0, 0], wipestyle=0, allcaps='L', fixed=False), 3: KBPStyle(style_no=3, name='Female', textcolor=9, outlinecolor=10, textwipecolor=11, outlinewipecolor=12, fontname='Arial', fontsize=12, fontstyle='B', charset=0, outlines=[2, 2, 2, 2], shadows=[0, 0], wipestyle=0, allcaps='L', fixed=False), 4: KBPStyle(style_no=4, name='Other', textcolor=4, outlinecolor=8, textwipecolor=12, outlinewipecolor=14, fontname='Arial', fontsize=12, fontstyle='B', charset=0, outlines=[2, 2, 2, 2], shadows=[0, 0], wipestyle=0, allcaps='L', fixed=False)})
            self.margins = {'left': 2, 'right': 2, 'top': 7, 'spacing': 12}
            self.other = {'bordercolor': 0, 'wipedetail': 2}
            return
        needsclosed = False
        if not isinstance(kbpFile, io.IOBase):
            self.filename = kbpFile
            kbpFile = open(kbpFile, "r", encoding="utf-8")
            needsclosed = True
        self.parse([x.rstrip("\r\n") for x in kbpFile.readlines()], **kwargs)
        if needsclosed:
            kbpFile.close()

    def parse(self, kbpLines, resolve_colors=False, resolve_wipe=True, template=None, tolerant_parsing=False):
        in_header = False
        top_section = True
        divider = False
        status = None
        x = 0
        while x < len(kbpLines):
            line = kbpLines[x]
            cursor = [0, slice(0,1)]
            try:
                if not line == KBPFile.DIVIDER and in_header:
                    cursor = [1, slice(0,2)]
                    if line.startswith("'Palette Colours"):
                        self.colors = KBPPalette.from_string(kbpLines[x+1])
                    elif line.startswith("  Style"):
                        data = kbpLines[x:kbpLines.index("  StyleEnd", x+1)]
                        cursor = [None, slice(0,len(data)+1)]
                        opts = {"palette": self.colors} if resolve_colors else {}
                        self.styles = KBPStyleCollection.from_textlines(data, **opts)
                    elif line.startswith("'Margins"):
                        self.parse_margins(kbpLines[x+1])
                    elif line.startswith("'Other"):
                        self.parse_other(kbpLines[x+1])
                    elif line == "'--- Track Information ---":
                        if template:
                            return
                        data = kbpLines[x+1:kbpLines.index(KBPFile.DIVIDER, x+1)]
                        cursor = [None, slice(0,len(data)+1)]
                        self.parse_trackinfo(data)
                        status = self.trackinfo["Status"]
                    elif line == '' or line.startswith("'"):
                        cursor = [0, slice(0,1)]
                    else:
                        cursor = [0, slice(0,1)]
                        raise ValueError("Unexpected header line")


                # Only accept lyrics instead of pages if unsynced
                elif divider and status == '0' and line == "LYRICSV2":
                    data = kbpLines[x+1:]
                    self.lyrics = data
                    cursor = [None, slice(0,len(data)+1)]

                # TODO: For things like this that send lines starting from x+1, receiving function shouldn't need to know to add 1 to line number
                elif divider and status == '1' and line == "PAGEV2":
                    data = kbpLines[x+1:kbpLines.index(KBPFile.DIVIDER, x+1)]
                    cursor = [None, slice(1,len(data)+1)]
                    opts = {"default_wipe": self.other['wipedetail']} if resolve_wipe else {}
                    self.pages.append(KBPPage.from_textlines(data, **opts, tolerant=tolerant_parsing))

                elif divider and line in ('PAGEV2', 'LYRICSV2'):
                    raise ValueError(f"Incorrect lyric sync state found, expected {"synced" if self.trackinfo["Status"] == '1' else "unsynced"}")

                elif divider and line == "IMAGE":
                    # TODO: Determine if it's ever possible to have multiple image lines in one section
                    cursor = [1, slice(0,2)]
                    data = kbpLines[x+1]
                    self.images.append(KBPImage.from_string(data))

                elif divider and line == "HEADERV2":
                    in_header = True
                    top_section = False

                elif line == KBPFile.DIVIDER:
                    in_header = False
                    divider = True

                # Allow anything before the HEADERv2 (the section that usually has the software name and website)
                # Other than that, every non-comment/empty line should be accounted for
                elif line  != "" and not line.startswith("'") and not top_section:
                    raise ValueError("Unknown section header")

                # Ignore empty/comment lines and still consider the previous line to be a divider
                if line != KBPFile.DIVIDER and line != "" and not line.startswith("'"):
                    divider = False
                 
                x += cursor[1].stop

            except Exception as e:
                error = "Failed to parse kbp file:\n"
                if hasattr(e, 'line'):
                    cursor[0] = e.line
                if hasattr(e, 'range'):
                    cursor[1] = slice(cursor[1].start + e.range.start, cursor[1].start + e.range.stop)
                    if cursor[0] is not None:
                        cursor[0] -= e.range.start
                if cursor[0] is not None and cursor[1].stop - cursor[1].start > 8:
                    curline = cursor[1].start + cursor[0]
                    cursor[1] = slice(max(curline-4,0), curline+4)
                    cursor[0] = curline - cursor[1].start
                for n, error_line in enumerate(kbpLines[x:][cursor[1]],start=cursor[1].start):
                    if cursor[0] is not None and n == cursor[0] + cursor[1].start:
                        error += f">>{n+x+1:6}: {error_line}\n"
                    else:
                        error += f"{n+x+1:8}: {error_line}\n"
                raise ValueError(error) from e

        missing = ', '.join(filter(lambda x: not hasattr(self, x), ('colors', 'styles', 'margins', 'other','pages')))
        if missing:
            raise ValueError(f"Invalid KBP file, missing sections: {missing}")

        if not hasattr(self, 'trackinfo') and template == False: # ignore when None
            raise ValueError("Invalid KBP file, missing track info. If this was intended to be used as a template, set template to True or None")

    

    def parse_margins(self, margin_line):
        self.margins = dict(zip(("left", "right", "top", "spacing"), (int(x) for x in margin_line.strip().split(","))))

    def parse_other(self, other_line):
        self.other = dict(zip(("bordercolor", "wipedetail"), (int(x) for x in other_line.strip().split(","))))

    # This is formatted in a way that it may allow freeform key/value pairs, so
    # leaving this as just a dict, but so far it always seems to contain exactly:
    # - Status
    # - Title
    # - Artist
    # - Audio
    # - BuildFile
    # - Intro
    # - Outro
    # - Comments
    def parse_trackinfo(self, trackinfo_lines):
        self.trackinfo = {}
        prev = None
        for line in trackinfo_lines:
            if line.startswith(" "):
                self.trackinfo[prev] += f"\n{line.lstrip()}"
            elif line != "" and not line.startswith("'"):
                fields = line.split(maxsplit=1)
                if len(fields) == 1:
                    fields.append("")
                self.trackinfo[fields[0]] = fields[1]
                prev = fields[0]

    

    # Convenience method to get all the lyric text without timing info,
    # potentially with syllable marks added. To get lyric text that could be used
    # to restart sync on a new project, use:
    # myKBPFile.text(include_empty=True, syllable_separator="/", space_is_separator=True)
    def text(self, page_separator="", include_empty=False, syllable_separator="", space_is_separator=False):
        result = []
        for page in self.pages:
            lines = []
            for line in page.lines:
                if include_empty or not line.isempty():
                    lines.append(line.text(syllable_separator=syllable_separator, space_is_separator=space_is_separator))
            result.append("\n".join(lines))
        return f"\n{page_separator}\n".join(result)

    def writeFile(self, kbpFile, allow_overwrite=False):
        if any(x.has_colors() for x in self.styles.values()):
            raise ValueError("Unable to write styles when they contain arbitrary colors. They must use palette indexes.")
        if not isinstance(kbpFile, io.IOBase):
            if not allow_overwrite and os.path.exists(kbpFile) and hasattr(self,'filename') and os.path.samefile(kbpFile, self.filename):
                raise ValueError("Refusing to write back to original filename. Set allow_overwrite if you need to do so.")
            kbpFile = open(kbpFile, "w", encoding="utf-8",newline="\r\n")
            needsclosed = True
        else:
            needsclosed = False
        kbpFile.write(KBPFile.HEADER_START)
        kbpFile.write(self.colors.toKBP())
        kbpFile.write(self.styles.toKBP())
        kbpFile.write("\n  ".join((
            "'Margins : L,R,T,Line Spacing",
            ",".join(str(x) for x in self.margins.values())
        )) + "\n\n")
        kbpFile.write("\n  ".join((
            "'Other: Border Colour,Detail Level",
            ",".join(str(x) for x in self.other.values())
        )) + "\n\n")

        if hasattr(self, 'trackinfo'):
            kbpFile.write("'--- Track Information ---\n\n")
            for x in self.trackinfo:
                if x == 'Comments':
                    kbpFile.write("\n")
                tmp = ('\n' + ' ' * 10).join(self.trackinfo[x].split('\n'))
                kbpFile.write(f"{x:<10}{tmp}\n")
            kbpFile.write("\n")
            #kbpFile.write("\n".join(f"""{'\n' if x == 'Comments' else ''}{x:<10}{
            #    ('\n' + ' ' * 10).join(self.trackinfo[x].split('\n'))
            #}""" for x in self.trackinfo) + "\n\n")
            if self.trackinfo['Status'] == '1':
                for page in self.pages:
                    kbpFile.write(page.toKBP())
                for image in self.images:
                    kbpFile.write(image.toKBP())
                kbpFile.write(KBPFile.DIVIDER + "\n\n")
            else:
                kbpFile.write(KBPFile.DIVIDER + "\n")
                kbpFile.write("LYRICSV2\n")
                for line in self.lyrics:
                    kbpFile.write(line + "\n")
        else:
            kbpFile.write(KBPFile.DIVIDER + "\n\n")

        if needsclosed:
            kbpFile.close()

    # There are several ways a syntactically valid KBP file may not work in practice. This will attempt to report on these logic errors
    def logicallyValidate(self) -> typing.List[KBPErrorDetails]:
        result = []
        # TODO: Count from 1 to match user expectation or handle that in output?
        for p, page in enumerate(self.pages):
            for l, line in enumerate(page.lines):
                result.extend(line.logicallyValidate(p, l, self.styles))
        return result


# I didn't want to use a list because it can't have specific size, and liked
# all the data being tuple-compatible, but still wanted list-like access with [].
# There are modules that make something like a "frozen" list, but I didn't want
# to pull in any more extra modules, so you get this monstrosity, sorry world
@validators.validated_instantiation
class KBPPalette(collections.namedtuple("KBPPalette", tuple(range(16)), rename=True)):

    __annotations__ = dict((f"_{x}",str) for x in range(16))
    
    # namedtuple-generated classes don't have __init__ so must instead override __new__
    def __new__(cls, *colors):
        assert len(colors) == 16 and all(re.match(r"[0-9A-F]{3}$", x) for x in colors), "Palette must have 16 12-bit RGB values."
        return super().__new__(cls, *colors)

    # Hide the field names because they are just _0 to _15 and aren't going to be used directly
    def __repr__(self):
        return "KBPPalette(" + ", ".join(repr(x) for x in self) + ")"

    def __getitem__(self, x):
        if isinstance(x, int) and 0 <= x < 16:
            return getattr(self, f"_{x}")
        else:
            raise KeyError(x)

    # Set available colors to what is configured in the palette
    @staticmethod
    def from_string(palette_line):
        return KBPPalette(*palette_line.lstrip().split(","))

    def toKBP(self):
        return f"'Palette Colours (0-15)\n  {','.join(self)}\n\n"

    def as_rgb24(self):
        return ["".join(y * 2 for y in x) for x in self]

    def as_rgba32(self):
        return [x+"FF" for x in self.as_rgb24()]

@validators.validated_instantiation
class KBPStyle(typing.NamedTuple):
    style_no: int
    name: str
    textcolor: str | int
    outlinecolor: str | int
    textwipecolor: str | int
    outlinewipecolor: str | int
    fontname: str
    fontsize: int
    fontstyle: str
    charset: int
    outlines: typing.Iterable
    shadows: typing.Iterable
    wipestyle: int
    allcaps: str
    fixed: bool

    # TODO: maybe have validated_instantiation take an argument to have a value validator
    @staticmethod
    def from_untrusted(**kwargs):
        for x in ('textcolor', 'outlinecolor', 'textwipecolor', 'outlinewipecolor'):
            assert 0 <= kwargs[x] <= 15 if isinstance(kwargs[x], int) else re.match(r"[0-9A-F]{3}$",kwargs[x]), "Style color must be a palette index or RGB value"
        assert len(kwargs['outlines']) == 4 and all(isinstance(x, int) and x >= 0 for x in kwargs['outlines']), "Outlines must be 4 non-negative integers"
        assert len(kwargs['shadows']) == 2 and all(isinstance(x, int) and x >= 0 for x in kwargs['shadows']), "Shadows must be 2 non-negative integers"
        # TODO: Look into narrowing this. I recall there were some cases where it could be >5 though
        assert kwargs['wipestyle'] >= 0, "Wipe style must be a non-negative"
        assert kwargs['allcaps'] in "LU", "All caps must be enabled (U) or disabled (L)"
        assert all(x in "BIUS" for x in kwargs['fontstyle']), "Font style can only contain bold (B), italic (I), underline (U) or strike-through (S)"
        return KBPStyle(**kwargs)

    def has_colors(self):
        fields = ("textcolor", "outlinecolor", "textwipecolor", "outlinewipecolor")
        if all(isinstance(getattr(self,x), str) for x in fields):
            return True
        elif all(isinstance(getattr(self,x), int) for x in fields):
            return False
        else:
            raise TypeError("Mixed/unexpected types found in color parameters:\n\t" + 
                "\n\t".join([": ".join((x, str(getattr(self,x)))) for x in fields]))

    def resolve_colors(style, palette):
        if style.has_colors():
            warnings.warn(f"Colors were already resolved on style {name}. Palette may not be used as intended", RuntimeWarning)
            return style
        else:
            fields = ("textcolor", "outlinecolor", "textwipecolor", "outlinewipecolor")
            return style._replace(**dict((x, palette[getattr(style,x)]) for x in fields))

    # Create a "fixed" version of a style (no wiping)
    # Technically the wipe colors are still defined with their original values,
    # but they are not used, so it makes sense to redefine them to their
    # non-wiped values for compatibility with other formats
    def make_fixed(style):
        if style.fixed:
            return style
        else:
            return style._replace(
                name = style.name + "_fixed",
                style_no = -style.style_no,
                textwipecolor = style.textcolor,
                outlinewipecolor = style.outlinecolor,
                fixed = True)

    def toKBP(self):
        tmp = tuple(str(x) for x in self)
        return "\n    ".join((
            ",".join((f"  Style{(self.style_no - 1):02d}",) + tmp[1:6]),
            ",".join(tmp[6:10]),
            ",".join(tuple(str(x) for x in self.outlines) + tuple(str(x) for x in self.shadows) + tmp[12:14])
        )) + "\n\n"

class KBPStyleParseError(ValueError):
    def __init__(self, *args, **kwargs):
        if 'line' in kwargs:
            self.line = kwargs.pop('line')
        if 'range' in kwargs:
            self.range = kwargs.pop('range')
        super().__init__(*args, **kwargs)

class KBPStyleCollection(dict):
    __slots__ = ()

    HEADER = "\n".join((
        "'Styles (00-19)",
        "'  Number,Name",
        "'  Colour: Text,Outline,Text Wipe,Outline Wipe",
        "'  Font  : Name,Size,Style,Charset",
        "'  Other : Outline*4,Shadow*2,Wiping,Uppercase",
        "\n"
    ))

    def __repr__(self):
        return "KBPStyleCollection(" + super().__repr__() + ")"

    # Alias style letters used in line headers to style numbers used in definition
    @staticmethod
    def alpha2key(alpha):
        if alpha in list(string.ascii_uppercase):
            return string.ascii_uppercase.index(alpha)+1
        elif alpha in list(string.ascii_lowercase):
            return -string.ascii_lowercase.index(alpha)-1

    def __missing__(self, key):
        if key in list(string.ascii_letters):
            return self[KBPStyleCollection.alpha2key(key)]

        # Auto-vivify fixed styles
        elif isinstance(key, int) and -key in self.keys():
            self[key] = self[-key].make_fixed()
            return self[key]

        # Undefined styles should return the default style
        # The caller can determine this happened if needed by
        # comparing style.style_no with the requested index
        # A converter can choose on its side whether it wants
        # the undefined style to be considered a new one or 
        # reuse the name of the default
        elif isinstance(key, int) and (1 <= abs(key) <= 26):
            return self[1] if key > 0 else self[-1]

        else:
            raise KeyError(key)

    # Hopefully the checks in the next several methods will be enough to keep bad data out...
    @validators.validated_types
    @staticmethod
    def __assert_valid_item(key: int, value: KBPStyle):
        if not (1 <= key <= 26 or -26 <= key <= -1):
            raise KeyError(f"Invalid index for item in KBPStyleCollection: {key}")

    # Using *args is the only way to get unnamed positional arguments.
    # Otherwise if the argument name happens to be a key in the kwargs, it causes
    # a duplicate argument. The decorator validates that it still only gets one
    # argument. As far as I know this is the only way to properly replicate the
    # signatures of the dict methods that can take an object *or* a mapping via
    # kwargs
    @validators.validated_structures(__assert_valid_item)
    @validators.one_arg
    def __init__(self, *args, **kwargs):
        arg = args[0] if args else []
        super().__init__(arg, **kwargs)
    
    def __setitem__(self, key, value):
        KBPStyleCollection.__assert_valid_item(key, value)
        super().__setitem__(key, value)
    
    @validators.validated_structures(__assert_valid_item)
    @validators.one_arg
    def update(self, *args, **kwargs):
        arg = args[0] if args else []
        super().update(arg, **kwargs)

    @validators.validated_structures(__assert_valid_item)
    def __ior__(self, arg):
        return super().__ior__(arg)

    def __or__(self, arg):
        # Data validated by __init__
        return KBPStyleCollection(super().__or__(arg))

    @staticmethod
    def fromkeys(keys, value=None):
        # Data validated by __init__
         return KBPStyleCollection(dict.fromkeys(keys, value))

    # Set available styles based on the configuration
    @staticmethod
    def from_textlines(style_lines, palette=None):
        styles = KBPStyleCollection()
        fields = {}
        style_no = None
        #for n, line in enumerate(style_lines):
        n=0
        while n < len(style_lines):
            line = style_lines[n]
            parsing_lines = True
            try:
                line = line.lstrip()
                if line == "" and style_no is not None:
                    style_no = None
                    fields = {}
                    n += 1
                elif style_no is None and line.startswith("Style"):
                    tmp = line.split(",")
                    style_no = int(tmp[0][5:]) + 1
                    fields['style_no'] = style_no
                    tmp = [tmp[1], *(int(x) for x in tmp[2:])]
                    fields.update(dict(zip(("name", "textcolor", "outlinecolor", "textwipecolor", "outlinewipecolor"),tmp)))
                    n += 1
                    tmp = style_lines[n].lstrip().split(",")
                    tmp[1] = int(tmp[1])
                    tmp[3] = int(tmp[3])
                    fields.update(dict(zip(("fontname", "fontsize", "fontstyle", "charset"),tmp)))
                    n += 1
                    tmp = style_lines[n].lstrip().split(",")
                    tmp[:-1] = [int(x) for x in tmp[:-1]]
                    fields.update(dict(zip(("outlines", "shadows", "wipestyle", "allcaps", "fixed"),(tmp[:4],tmp[4:6],tmp[6],tmp[7],False))))
                    parsing_lines = False
                    result = KBPStyle.from_untrusted(**fields)
                    parsing_lines = True
                    if palette:
                        result = result.resolve_colors(palette)
                    # Adding 1 to style for 2 reasons:
                    # - Style 0/A is shown in the KBS UI as 01
                    # - It allows indexing fixed styles as negative numbers
                    styles[style_no] = result
                    n += 1
                else:
                    raise ValueError("Unexpected line in style definitions")
            except Exception as e:
                if parsing_lines:
                    raise KBPStyleParseError(f"Unable to parse style {style_no}", line = n) from e
                else:
                    raise KBPStyleParseError(f"Unable to parse style {style_no}", range = slice(n-2,n+1)) from e
        return styles
    
    
    def key2alpha(key: int):
        if key < 0:
            return string.ascii_lowercase[-key-1]
        else:
            return string.ascii_uppercase[key-1]

    # This is almost definitely ill-advised, but this is like dict.keys() and
    # returns a view object for the alpha aliases of the keys. And of course it
    # can give you an iterator so you can do something like:
    # for x in kbpfile.styles.alpha_keys():
    #     ...
    def alpha_keys(self):
        class alphakey_view:
            def __init__(slf, obj):
                slf.__obj = obj

            def __len__(slf):
                return len(slf.__obj)

            def __reversed__(slf):
                return alphakey_view(reversed(slf.__obj))

            def __repr__(slf):
                return f"style_alphakey_view({', '.join(repr(KBPStyleCollection.key2alpha(x)) for x in slf.__obj)})"

            def __iter__(slf):
                class alphakey_iterator:
                    def __init__(sf, it):
                        sf.__iter = it
                    def __repr__(sf):
                        return f"<style_alphakey_iterator at {hex(id(sf))}>"
                    def __next__(sf):
                        return next(sf.__iter)
                return alphakey_iterator(KBPStyleCollection.key2alpha(x) for x in slf.__obj)

        return alphakey_view(self.keys())

    def alpha_iter(self):
        return iter(self.alpha_keys())

    def toKBP(self):
        return KBPStyleCollection.HEADER + "".join(x.toKBP() for x in self.values() if x.style_no > 0) + "  StyleEnd\n\n"
        

@validators.validated_instantiation
class KBPLineHeader(typing.NamedTuple):
    align: str
    style: str
    start: int
    end: int
    right: int
    down: int
    rotation: int

    def isfixed(self):
        return self.style.islower()

    def toKBP(self):
        return "/".join(str(x) for x in self)

@validators.validated_instantiation
class KBPSyllable(typing.NamedTuple):
    syllable: str
    start: int
    end: int
    wipe: int

    def isempty(self):
        return self.syllable == ""

    def isprogressive(self):
        # Zero means unresolved default wipe, so result is undefined. Otherwise
        # everything less than 5 is progressive with varying level of wipe detail
        return None if self.wipe == 0 else (self.wipe < 5)

    def toKBP(self):
        return f"{self.syllable + '/':<15}" + "/".join(str(x) for x in self[1:])

class KBPLine(typing.NamedTuple):
    header: KBPLineHeader
    syllables: list

    # There's only one header, so may as well pass anything unresolved down to it
    def __getattr__(self, attr):
        return getattr(self.header, attr)

    # These will just return "can't set" errors since it's immutable, but that
    # makes more sense than "has no attribute"
    def __setattr__(self, attr, val):
        return setattr(self.header, attr, val)

    def text(self, syllable_separator="", space_is_separator=False):

        # Special case for empty lines because when importing lyrics into KBS,
        # a syllable separator by itself is used to denote an empty line (as
        # opposed to a page break)
        if self.isempty():
            return syllable_separator

        # When space is considered a separator, underscore is used to represent
        # a non-splitting space
        elif space_is_separator and syllable_separator != "":
            result = ""
            for syl in self.syllables:
                syltext = syl.syllable
                syltext = re.sub(r"( +)(?=[^ ])", lambda m: "_" * len(m.group(1)), syltext)
                result += syltext
                if not syltext.endswith(" "):
                    result += syllable_separator
            return result[:-len(syllable_separator)]

        # Basic case - output syllables split only by the separator character(s)
        else:
            return syllable_separator.join(x.syllable for x in self.syllables)

    def isempty(self):
        return not self.syllables or (len(self.syllables) == 1 and self.syllables[0].isempty())

    def toKBP(self):
        return "\n".join((self.header.toKBP(), *(x.toKBP() for x in self.syllables))) + "\n"

    def logicallyValidate(self, page_no: int, line_no: int, styles: KBPStyleCollection) -> typing.List[KBPErrorDetails]:
        result = []
        if self.start < 0:
            result.append(KBPErrorDetails(
                error=KBPErrorCode.NegativeLineStart,
                page=page_no,
                line=line_no,
                value=self.start
            ))
        if self.end < 0:
            result.append(KBPErrorDetails(
                error=KBPErrorCode.NegativeLineEnd,
                page=page_no,
                line=line_no,
                value=self.end
            ))
        # If the style does not exist in the style collection, it will default but also switch to the default's style_no
        if (style_no := KBPStyleCollection.alpha2key(self.style)) != styles[self.style].style_no:
            result.append(KBPErrorDetails(
                error=KBPErrorCode.LineStyleMissing,
                page=page_no,
                line=line_no,
                value=abs(style_no)
            ))
        for s, syl in enumerate(self.syllables):
            if syl.start < self.start:
                result.append(KBPErrorDetails(
                    error=KBPErrorCode.WipeStartBeforeLine,
                    page=page_no,
                    line=line_no,
                    syllable=s,
                    value=syl.start - self.start
                ))
            if syl.end > self.end:
                result.append(KBPErrorDetails(
                    error=KBPErrorCode.WipeEndAfterLine,
                    page=page_no,
                    line=line_no,
                    syllable=s,
                    value=syl.end - self.end
                ))
        return result

class KBPPageParseError(ValueError):
    def __init__(self, *args, **kwargs):
        if 'line' in kwargs:
            self.line = kwargs.pop('line')
        super().__init__(*args, **kwargs)

@validators.validated_instantiation
class KBPPage(typing.NamedTuple):
    remove: str
    display: str
    lines: list

    @staticmethod
    def from_textlines(page_lines, default_wipe = None, tolerant = False):
        lines=[]
        syllables=[]
        header = None
        transitions=["", ""] # Default line by line
        if tolerant:
            partial_syllable = []
        for n, x in enumerate(page_lines):
            try:
                if header is None and re.match(r"[LCR]/[a-zA-Z](/-?\d+){5}$", x): # Only last 3 fields can logically be negative, but KBS allows all
                    fields = x.split("/")
                    fields[2:] = [int(y) for y in fields[2:]]
                    header = KBPLineHeader(**dict(zip(("align", "style", "start", "end", "right", "down", "rotation"), fields)))
                elif x == "" and header is not None:
                    # Handle previous line
                    lines.append(KBPLine(header=header, syllables=syllables))
                    syllables = []
                    header = None
                elif header is None and x.startswith("FX/"):
                    transitions = x.split('/')[1:]
                elif header is not None and x != "":
                    fields = x.split("/")

                    # Sometimes kbp files are corrupt in such a way that a syllable line split into two
                    # This combines them back together into a valid line
                    # E.g.
                    #    Foo/     123/456/0
                    # Could have become
                    #    Foo
                    #    /     123/456/0
                    # Note that the second of these would be a syntactically-valid empty syllable on its own,
                    # but since it follows an incomplete line, it is combined into it, and the empty field is removed
                    if tolerant:
                        partial_syllable.extend(fields if fields[0] or not partial_syllable else fields[1:])
                        if len(partial_syllable) < 4:
                            continue
                        else:
                            fields, partial_syllable = partial_syllable, []

                    suggestion = " Try the tolerant_parsing option?" if page_lines[n+1].startswith("/") else ""
                    assert len(fields) == 4, f"Syllable line should have 4 fields (syllable, start, end, wipe).{suggestion}"

                    fields[0] = re.sub(r"{-}", "/", fields[0]) # This field uses this as a surrogate for / since that denotes end of syllable
                    fields[1] = fields[1].lstrip() # Only the second field should have extra spaces
                    fields[1:] = [int(y) for y in fields[1:]]
                    if default_wipe and fields[3] == 0:
                        fields[3] = default_wipe
                    syllables.append(KBPSyllable(**dict(zip(("syllable", "start", "end", "wipe"), fields))))
                else:
                    raise ValueError(f"Unexpected line{" (expected header here)" if header is None else ""}")
            except Exception as e:
                raise KBPPageParseError("Failed to parse page", line = n) from e
        return KBPPage(*transitions, lines)

    def get_start(self):
        return min(line.start for line in self.lines if not line.isempty())

    def get_end(self):
        return max(line.end for line in self.lines)

    def toKBP(self):
        transition = (f"FX/{self.remove}/{self.display}\n",) if (self.remove or self.display) else ()
        return "\n".join((KBPFile.DIVIDER, "PAGEV2", *transition, *(x.toKBP() for x in self.lines))) + "\n"

# Perhaps this could be better named as slideshow, but calling it IMAGE as that's what the header is called in the .kbp
@validators.validated_instantiation
class KBPImage(typing.NamedTuple):
    start: int
    end: int
    filename: str
    leaveonscreen: int

    @staticmethod
    def from_string(image_line):
        fields = image_line.split("/")
        for x in (0, 1, 3):
            fields[x] = int(fields[x])
        return KBPImage(**dict(zip(("start", "end", "filename", "leaveonscreen"),fields)))

    def toKBP(self):
        return "\n".join((KBPFile.DIVIDER, "IMAGE", "/".join(str(x) for x in self))) + "\n\n"
