import ass
import dataclasses
import datetime
import enum
import types
import typing
import collections
import re
import math
from . import kbp
from . import validators
from . import kbs
from . import kbpfont
from . import doblontxt

class AssAlignment(enum.Enum):
    DEFAULT = 0
    BOTTOM_LEFT = 1
    BOTTOM_CENTER = 2
    BOTTOM_RIGHT = 3
    MIDDLE_LEFT = 4
    MIDDLE_CENTER = 5
    MIDDLE_RIGHT = 6
    TOP_LEFT = 7
    L = 7 # Alias
    TOP_CENTER = 8
    C = 8 # Alias
    TOP_RIGHT = 9
    R = 9 # Alias

@validators.validated_instantiation
class AssPosition(typing.NamedTuple):
    rotation: int
    alignment: AssAlignment
    x: int | float
    y: int | float

    def __str__(self):
        result = "{"
        if self.alignment != AssAlignment.DEFAULT:
            result += r"\an%d" % self.alignment.value
        if self.rotation:
            result += r"\frz%d" % self.rotation
        # Yes, %s, so it will stringify either an int or float and display properly
        result += r"\pos(%s,%s)}" % (self.x, self.y)
        return result

class AssOverflow(enum.Enum):
    NO_WRAP = 2
    EVEN_SPLIT = 0
    TOP_SPLIT = 1
    BOTTOM_SPLIT = 3

    def __str__(self):
        return self.name

@validators.validated_instantiation(replace="__init__")
@dataclasses.dataclass
class AssOptions:
    #position: bool
    #wipe: bool
    border: bool = True # Add CDG-style borders to margins
    #display: int
    #remove: int
    float_font: bool = True # Allow floating point in output font sizes (well-supported)
    float_pos: bool = False # Allow floating point in \pos and margins (supported by recent libass)
    target_x: int = 300 # Output resolution
    target_y: int = 216
    fade_in: int = 300 # Fade duration for line display/remove
    fade_out: int = 200
    transparency: bool = True
    offset: int | bool = True # False = disable offset (same as 0), True = pull from KBS config, int is offset in ms
    overflow: AssOverflow = AssOverflow.EVEN_SPLIT
    allow_kt: bool = False # Use \kt if there are overlapping wipes on the same line (not supported by all ass implementations)
    experimental_spacing: bool = False
    #overflow_spacing: float # TODO? spacing value in styles that will apply for overflow (default 0). Multiplied by font height or based on default style?

    @validators.validated_types
    @staticmethod
    def __assert_valid(key: str, value):
        if key in AssOptions._fields:
            if not isinstance(value, (t := AssOptions._fields[key].type)):
                if callable(t):
                    value = t(value)
                # Also try the first type in a union
                elif hasattr(t, '__args__') and callable(s := t.__args__[0]):
                    value = s(value)
            elif not isinstance(value, t):
                raise TypeError(f"Expected {opt} to be of type {t}. Found {type(options[opt])}.")
        else:
            raise TypeError(f"Unexpected field '{key}'. Possible fields are {self._fields.keys()}.")

        return value

    @validators.validated_structures(assert_function=__assert_valid)
    def update(self, **options):
        for opt in options:
            setattr(self, opt, options[opt])

# Not sure why dataclasses doesn't define something like this keyed by field name
AssOptions._fields = types.MappingProxyType(dict((f.name,f) for f in dataclasses.fields(AssOptions)))

class AssConverter:
    
    @validators.validated_types
    def __init__(self, kbpFile: kbp.KBPFile, options: AssOptions = None, **kwargs):
        self.kbpFile = kbpFile
        # Allow for applying specific overrides to defaults in kwargs, or
        # providing a template for defaults then overriding items there
        self.options = options or AssOptions()
        self.options.update(**kwargs)

    # Delegate to options if not present in the object itself
    def __getattr__(self,attr):
        return getattr(self.options, attr)

    # Move coordinates based on scaling the canvas size
    # If the target aspect ratio is wider than 300:216, x coordinates are
    # scaled more than y and vice versa
    # For example:
    #  - target_x, target_y = 384, 216
    #    - this behaves like -W 384 in the javascript kbp2ass
    #    - Text would not be scaled by scale_font, but this adjusts x positions to expand to fit the space
    #    - y positions would stay the same
    #  - target_x, target_y = 600, 600
    #    - Text would be scaled 2x by scale_font (min(600/300, 600/216))
    #    - x coordinates would be adjusted for the scaling factor
    #    - y coordinates would be further adjusted to fit the space
    #
    # NOTE: Original plan was to provide a letterboxed version as well, but
    # unfortunately .ass cannot reliably do that, as the margins are only used
    # for soft word wrapping. To letterbox, scale to a resolution with aspect
    # ratio the same as CDG, then letterbox when rendering the video
    @validators.validated_types
    @staticmethod
    def rescale_coords(x: int, y: int, target_x: int, target_y: int, allow_float: bool = False, border: bool = True) -> tuple:
        cdg_res = (300, 216) if border else (288, 192)
        res = (x * target_x / cdg_res[0], y * target_y / cdg_res[1])
        if allow_float:
            # Still return ints if they happen to be just as accurate
            return tuple(i if (i := int(r)) == r else r for r in res)
        else:
            return tuple(round(coord) for coord in res)

    # Scale scalars like font, border, shadow
    # These are scaled by a factor of the minimum of the scaling factor of x
    # and y to avoid going off screen
    # If font is true, additional scaling factor of 1.4 is applied to account for line height vs cap height
    @validators.validated_types
    @staticmethod
    def rescale_scalar(size: float, target_x: int, target_y: int, allow_float: bool = True, border: bool = True, font: bool = False) -> int | float:
        cdg_res = (300, 216) if border else (288, 192)
        scale = min(target_x / cdg_res[0], target_y / cdg_res[1])
        res = size * scale * (1.4 if font else 1) # Find way to calculate line_height(fontsize) instead of using this constant
        return res if (allow_float and int(res) != res) else round(res)

    @validators.validated_types
    def get_pos(self, line: kbp.KBPLine, num: int) -> AssPosition:
        cdg_res_x = 300 if self.border else 288
        margins = self.kbpFile.margins
        result = {}
        y = margins["top"] + \
            line.down + \
            num * (self.kbpFile.margins["spacing"] + (kbpfont.spacing(self.kbpFile.styles[1]) if self.experimental_spacing else 19)) + \
            (12 if self.border else 0)

        result["alignment"] = AssAlignment.DEFAULT if line.align == self.style_alignments[line.style] else AssAlignment[line.align]

        if line.align == 'L':
            x = margins["left"] + line.right + (6 if self.border else 0)
        elif line.align == 'C':
            x = cdg_res_x / 2 + line.right
        else: #line.align == 'R' or the file is broken
            x = cdg_res_x - margins["right"] + line.right - (6 if self.border else 0)

        result["x"], result["y"] = AssConverter.rescale_coords(x, y, self.target_x, self.target_y, border=self.border, allow_float=self.float_pos)

        return AssPosition(**result, rotation=line.rotation)

    @validators.validated_types
    def get_line_margins(self, line: kbp.KBPLine, pos: AssPosition | types.NoneType = None, num: int = 1) -> tuple:
        if pos is None:
            pos = self.get_pos(line, num)

        page_margins = self.kbpFile.margins

        left = page_margins["left"] - (0 if line.align == 'L' or (line.align == 'C' and line.right > 0) else line.right)
        right = page_margins["right"] + (0 if line.align == 'R' or (line.align == 'C' and line.right < 0) else line.right)
        left, _ = AssConverter.rescale_coords(left, pos.y, self.target_x, self.target_y, border=self.border, allow_float=self.float_pos)
        right, _ = AssConverter.rescale_coords(right, pos.y, self.target_x, self.target_y, border=self.border, allow_float=self.float_pos)

        return (left, right)
    
    # Determine the most-used line alignment for each style to minimize \anX tags in result
    # (since alignment is not part of the KBP style, but is part of the ASS style)
    def _calc_style_alignments(self):
        # dict of alpha-keyed style to dict of alignment to frequency
        # E.g.
        # { 'A' : {'C': 5, 'L': 2}}
        # would indicate style A was centered 5 times and left-aligned twice
        freqs = collections.defaultdict(lambda: collections.defaultdict(lambda: 0))
        for page in self.kbpFile.pages:
            for line in page.lines:
                freqs[line.style][line.align] += 1
        self.style_alignments = {}
        for style in freqs:
            self.style_alignments[style] = max(freqs[style], key = freqs[style].get)

    @validators.validated_types
    def fade(self) -> str:
        return r"{\fad(%d,%d)}" % (self.options.fade_in, self.options.fade_out)

    # Convert a line of syllables into the text of a dialogue event including wipe tags
    @validators.validated_types
    def kbp2asstext(self, line: kbp.KBPLine, pos: AssPosition):
        result = str(pos) + self.fade()
        if self.kbpFile.styles[line.style].fixed:
            return result + line.text()
        cur = line.start
        for (n, s) in enumerate(line.syllables):
            delay = s.start - cur
            dur = s.end - s.start

            if delay > 0:
                # Gap between current position and start of next syllable
                result += r"{\k%d}" % delay
            elif delay < 0:
                # Playing catchup
                if self.allow_kt:
                    # Reset time so wipes can overlap (\kt takes a time in centiseconds from line start)
                    result += r"{\kt%d}" % (s.start - line.start)
                else:
                    # Shorten syllable to compensate for missing time (keep in mind delay is negative)
                    dur += delay

            # By default a syllable ends 1 centisecond before the next, so
            # special casing so we don't need a bunch of \k1 and the slight
            # errors don't catch up with us on a long line
            if len(line.syllables) > n+1 and line.syllables[n+1].start - s.end == 1:
                dur += 1

            # Using == False explicitly because it's technically a tri-state with None meaning undefined
            # Though that scenario shouldn't come up since we are allowing KBPFile to resolve wipedetail
            wipe = r"\k" if s.isprogressive() == False else r"\kf"

            result += r"{%s%d}%s" % (wipe, dur, s.syllable)
            cur = s.start + dur
        return result

    @validators.validated_types
    @staticmethod
    def ass_style_name(index: int, kbpName: str):
        return f"Style{abs(index):02}_{kbpName}"

    @validators.validated_types(coerce_types=False)
    @staticmethod
    def kbp2asscolor(kbpcolor: int | str, palette: kbp.KBPPalette | types.NoneType = None, transparency: bool = False):
        alpha = "&H00"
        if isinstance(kbpcolor, int):
            if transparency and kbpcolor == 0:
                alpha = "&HFF"
            # This will intentionally raise an exception if colors are unresolved and palette is not provided
            kbpcolor = palette[kbpcolor]
        return alpha + "".join(x+x for x in reversed(list(kbpcolor)))

    def ass_document(self):
        result = ass.Document()
        result.info.update(
            Title="",
            ScriptType="v4.00+",
            WrapStyle=self.overflow.value,
            ScaledBorderAndShadow="yes",
            Collisions="Normal",
            PlayResX=self.options.target_x,
            PlayResY=self.options.target_y,
            ) 

        if self.options.offset is False:
            self.options.offset = 0
        elif self.options.offset is True:
            self.options.offset = kbs.offset * 10
        # else already resolved to an int

        styles = self.kbpFile.styles
        self._calc_style_alignments()
        for page in self.kbpFile.pages:
            for num, line in enumerate(page.lines):
                if line.isempty():
                    continue
                pos = self.get_pos(line, num)
                line_margins = self.get_line_margins(line, pos)
                line_style = styles[line.style]
                result.events.append(ass.Dialogue(
                    start=datetime.timedelta(milliseconds = line.start * 10 + self.options.offset),
                    end=datetime.timedelta(milliseconds = line.end * 10 + self.options.offset),
                    style=AssConverter.ass_style_name(line_style.style_no, line_style.name), # Undefined styles get default style number
                    effect="karaoke",
                    text=self.kbp2asstext(line, pos),
                    margin_l=line_margins[0],
                    margin_r=line_margins[1],
                    ))
        for idx in styles:
            style = styles[idx]
            result.styles.append(ass.Style(
                name=AssConverter.ass_style_name(idx, style.name),
                fontname=style.fontname,
                fontsize=AssConverter.rescale_scalar(style.fontsize, self.target_x, self.target_y, font = True, border=self.border),
                secondary_color=AssConverter.kbp2asscolor(style.textcolor, palette=self.kbpFile.colors, transparency=self.options.transparency),
                primary_color=AssConverter.kbp2asscolor(style.textwipecolor, palette=self.kbpFile.colors, transparency=self.options.transparency),
                outline_color=AssConverter.kbp2asscolor(style.outlinecolor, palette=self.kbpFile.colors, transparency=self.options.transparency),
                # NOTE: no outline wipe in .ass
                back_color=AssConverter.kbp2asscolor(style.outlinewipecolor, palette=self.kbpFile.colors, transparency=self.options.transparency),
                bold = 'B' in style.fontstyle,
                italic = 'I' in style.fontstyle,
                underline = 'U' in style.fontstyle,
                strike_out = 'S' in style.fontstyle,
                outline = AssConverter.rescale_scalar(sum(style.outlines), self.target_x, self.target_y, border=self.border)/4, # NOTE: only one outline, but it's a float, so maybe averaging will be helpful
                shadow = AssConverter.rescale_scalar(sum(style.shadows), self.target_x, self.target_y, border=self.border)/2,
                margin_l = 0, # TODO: Decide if these should be set (and overridden on lines only when different)
                margin_r = 0, # TODO cont: Potentially could also be set by style like alignment based on most-used positions
                margin_v = 0,
                encoding = style.charset,
                alignment=AssAlignment[self.style_alignments.get(kbp.KBPStyleCollection.key2alpha(idx), 'C')].value,
                ))
            
        return result

@validators.validated_instantiation(replace="__init__")
@dataclasses.dataclass
class DoblonTxtOptions:
    title: str = ''
    artist: str = ''
    audio_file: str = ''
    comments: str = 'Created with kbputils\nConverted from Doblon .txt file'
    max_lines_per_page: int = 6
    min_gap_for_new_page: int = 1000
    display_before_wipe: int = 1000
    remove_after_wipe: int = 500
    template_file: str = ''

    @validators.validated_types
    @staticmethod
    def __assert_valid(key: str, value):
        if key in DoblonTxtOptions._fields:
            if not isinstance(value, (t := DoblonTxtOptions._fields[key].type)):
                if callable(t):
                    value = t(value)
                # Also try the first type in a union
                elif hasattr(t, '__args__') and callable(s := t.__args__[0]):
                    value = s(value)
            elif not isinstance(value, t):
                raise TypeError(f"Expected {opt} to be of type {t}. Found {type(options[opt])}.")
        else:
            raise TypeError(f"Unexpected field '{key}'. Possible fields are {self._fields.keys()}.")

        return value

    @validators.validated_structures(assert_function=__assert_valid)
    def update(self, **options):
        for opt in options:
            setattr(self, opt, options[opt])
DoblonTxtOptions._fields = types.MappingProxyType(dict((f.name,f) for f in dataclasses.fields(DoblonTxtOptions)))

class DoblonTxtConverter:
    @validators.validated_types
    def __init__(self, doblonTxtFile: doblontxt.DoblonTxt, options: DoblonTxtOptions | types.NoneType = None, **kwargs):
        self.doblontxt = doblonTxtFile
        self.options = options or DoblonTxtOptions()
        self.options.update(**kwargs)
        self.template = kbp.KBPFile(self.options.template_file, template=True) if self.options.template_file else kbp.KBPFile()

    @staticmethod
    def syl2kbp(syl: str) -> str:
        if syl.endswith("-"):
            syl = syl[:-1]
        return re.sub("/", "{-}", syl)

    def kbpFile(self):
        if hasattr(self, 'kbpfile'):
            return self.kbpfile
        self.kbpfile = self.template
        delattr(self, 'template')
        if not hasattr(self.kbpfile, 'trackinfo'):
            self.kbpfile.trackinfo = {'Status': '1', 'Title': self.options.title, 'Artist': self.options.artist, 'Audio': self.options.audio_file, 'BuildFile': '', 'Intro': '', 'Outro': '', 'Comments': self.options.comments}

        # Add empty line to ensure last page is processed
        self.doblontxt.lines.append([])

        kbplines = []
        for line in self.doblontxt.lines:
            if not line or (kbplines and line[0][1] - self.options.display_before_wipe - kbplines[-1].end*10 > self.options.min_gap_for_new_page):
                if kbplines:
                    num_pages = math.ceil(len(kbplines) / self.options.max_lines_per_page)
                    per_page = len(kbplines) // num_pages
                    additional = len(kbplines) % num_pages
                    cur = 0
                    for group in range(num_pages):
                        nxt = cur + per_page + int(additional > 0)
                        additional -= 1
                        page = kbp.KBPPage("", "", kbplines[cur:nxt])
                        self.kbpfile.pages.append(page)
                        cur = nxt
                    kbplines = []
                if not line:
                    continue
            line_header = kbp.KBPLineHeader(
                align="C",
                style="A",
                start=round((line[0][0] - self.options.display_before_wipe)/10),
                end=round((line[-1][1] + self.options.remove_after_wipe)/10),
                right=0,
                down=0,
                rotation=0
            ) 
            kbpline = kbp.KBPLine(line_header, [kbp.KBPSyllable(self.syl2kbp(syl), round(start/10), round(end/10), 0) for start, end, syl in line])
            kbplines.append(kbpline)
        return self.kbpfile
