import ass
import dataclasses
import datetime
import enum
import types
import collections
from . import kbp
from . import validators
from . import kbs

class AssAlignment(enum.Enum):
    BOTTOM_LEFT = 1
    BOTTOM_CENTER = 2
    BOTTOM_RIGHT = 3
    MIDDLE_LEFT = 4
    MIDDLE_CENTER = 5
    MIDDLE_RIGHT = 6
    TOP_LEFT = 7
    TOP_CENTER = 8
    TOP_RIGHT = 9

class AssAspectHandling(enum.Enum):
    UNDEFINED = enum.auto()
    LETTERBOX = enum.auto()
    EXPAND = enum.auto()

@validators.validated_instantiation(replace="__init__")
@dataclasses.dataclass
class AssOptions:
    #position: bool
    #wipe: bool
    #border: bool
    #display: int
    # remove: int
    target_x: int = 300
    target_y: int = 216
    aspect_handling: AssAspectHandling = AssAspectHandling.UNDEFINED # TODO handle scaling and aspect ratio stuff
    alignment: AssAlignment = AssAlignment.MIDDLE_CENTER
    fade_in: int = 300
    fade_out: int = 200
    transparency: bool = True
    offset: int | bool = True # False = disable offset (same as 0), True = pull from KBS config, int is offset in ms

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
        self.options = options or AssOptions()
        self.options.update(**kwargs)

    def __getattr__(self,attr):
        return getattr(self.options, attr)

    def get_pos(self, line: kbp.KBPLine, num: int):
        margins = self.kbpFile.margins
        y = margins["top"] + num * (self.kbpFile.margins["spacing"] + 19) + 12 # TODO border setting

        if line.align == self.style_alignments[line.style]:
            result = r"{"
        else:
            result = r"{\an%d" % AssConverter.kbp2assalign(line.align)

        if line.align == 'L':
            result += r"\pos(%d,%d)}" % (margins["left"] + 6, y) # TODO border setting
        elif line.align == 'C':
            result += r"\pos(%d,%d)}" % (150, y)
        else: #line.align == 'R' or the file is broken
            result += r"\pos(%d,%d)}" % (300 - margins["right"] - 6, y) # TODO border setting

        return result

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

    def fade(self):
        return r"{\fad(%d,%d)}" % (self.options.fade_in, self.options.fade_out)

    # Convert a line of syllables into the text of a dialogue event including wipe tags
    def kbp2asstext(self, line: kbp.KBPLine, num: int):
        result = self.get_pos(line, num) + self.fade()
        cur = line.start
        for (n, s) in enumerate(line.syllables):
            delay = s.start - cur
            dur = s.end - s.start

            if delay > 0:
                # Gap between current position and start of next syllable
                result += r"{\k%d}" % delay
            elif delay < 0:
                # Playing catchup - could potentially use \kt to reset time
                # here but it has limited support
                dur += delay

            # By default a syllable ends 1 centisecond before the next, so
            # special casing so we don't need a bunch of \k1 and the slight
            # errors don't catch up with us on a long line
            if len(line.syllables) > n+1 and line.syllables[n+1].start - s.end == 1:
                dur += 1

            wipe = "\kf" if s.wipe < 5 else "\k"

            result += r"{%s%d}%s" % (wipe, dur, s.syllable)
            cur = s.start + dur
        return result

    @staticmethod
    def ass_style_name(index: int, kbpName: str):
        return f"Style{abs(index):02}_{kbpName}"

    @staticmethod
    def kbp2asscolor(kbpcolor: int | str, palette: kbp.KBPPalette = None, transparency: bool = False):
        alpha = "&H00"
        if isinstance(kbpcolor, int):
            if transparency and kbpcolor == 0:
                alpha = "&HFF"
            # This will intentionally raise an exception if colors are unresolved and palette is not provided
            kbpcolor = palette[kbpcolor]
        return alpha + "".join(x+x for x in reversed(list(kbpcolor)))

    @validators.validated_types
    @staticmethod
    def kbp2assalign(align: str) -> int:
        if align == 'L':
            return AssAlignment.TOP_LEFT.value
        elif align == 'C':
            return AssAlignment.TOP_CENTER.value
        elif align == 'R':
            return AssAlignment.TOP_RIGHT.value
        else:
            raise TypeError("Alignment should be one of ('L', 'C', 'R')")

    def ass_document(self):
        result = ass.Document()
        result.info.update(
            Title="",
            ScriptType="v4.00+",
            WrapStyle=0,
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
                result.events.append(ass.Dialogue(
                    start=datetime.timedelta(milliseconds = line.start * 10 + self.options.offset),
                    end=datetime.timedelta(milliseconds = line.end * 10 + self.options.offset),
                    style=AssConverter.ass_style_name(kbp.KBPStyleCollection.alpha2key(line.style), styles[line.style].name),
                    effect="karaoke",
                    text=line.text() if styles[line.style].fixed else self.kbp2asstext(line, num),
                    ))
        for idx in styles:
            style = styles[idx]
            result.styles.append(ass.Style(
                name=AssConverter.ass_style_name(idx, style.name),
                fontname=style.fontname,
                fontsize=style.fontsize * 1.4,  # TODO do better
                secondary_color=AssConverter.kbp2asscolor(style.textcolor, palette=self.kbpFile.colors, transparency=self.options.transparency),
                primary_color=AssConverter.kbp2asscolor(style.textwipecolor, palette=self.kbpFile.colors, transparency=self.options.transparency),
                outline_color=AssConverter.kbp2asscolor(style.outlinecolor, palette=self.kbpFile.colors, transparency=self.options.transparency),
                # NOTE: no outline wipe in .ass
                back_color=AssConverter.kbp2asscolor(style.outlinewipecolor, palette=self.kbpFile.colors, transparency=self.options.transparency),
                bold = 'B' in style.fontstyle,
                italic = 'I' in style.fontstyle,
                underline = 'U' in style.fontstyle,
                strike_out = 'S' in style.fontstyle,
                outline = sum(style.outlines)/4,   # NOTE: only one outline, but it's a float, so maybe this will be helpful
                shadow = sum(style.shadows)/2,
                margin_l = 0,
                margin_r = 0,
                margin_v = 0,
                encoding = style.charset,
                alignment=AssConverter.kbp2assalign(self.style_alignments.get(kbp.KBPStyleCollection.key2alpha(idx), 'C')),
                ))
            
        return result

