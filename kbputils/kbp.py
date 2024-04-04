import collections
import re

class KBPFile:

    DIVIDER = "-----------------------------"

    def __init__(self, kbpFile, options={}):
        self.options = options
        self.pages = []
        self.images = []
        self.styles = {} # using dict despite integer indexes to allow gaps
        with open(kbpFile, "r") as f:
            self.parse([x.rstrip() for x in f.readlines()])

    def parse(self, kbpLines, resolve_colors=True):
        in_header = False
        divider = False
        for x, line in enumerate(kbpLines):
            if in_header:
                if line.startswith("'Palette Colours"):
                    self.parse_colors(kbpLines[x+1])
                elif line.startswith("'Styles"):
                    data = kbpLines[x+1:kbpLines.index("  StyleEnd", x+1)]
                    self.parse_styles([x for x in data if not x.startswith("'")], resolve_colors=resolve_colors)
                elif line.startswith("'Margins"):
                    self.parse_margins(kbpLines[x+1])
                elif line.startswith("'Other"):
                    self.parse_other(kbpLines[x+1])
                elif line == "'--- Track Information ---":
                    data = kbpLines[x+1:kbpLines.index(KBPFile.DIVIDER, x+1)]
                    self.parse_trackinfo(data)

            elif divider and line == "PAGEV2":
                data = kbpLines[x+1:kbpLines.index(KBPFile.DIVIDER, x+1)]
                self.parse_page(data)

            elif divider and line == "IMAGE":
                # TODO: Determine if it's ever possible to have multiple image lines in one section
                data = kbpLines[x+1]
                self.parse_image(data)

            if divider and line == "HEADERV2":
                in_header = True

            if line == KBPFile.DIVIDER:
                in_header = False
                divider = True
            # Ignore empty/comment lines and still consider the previous line to be a divider
            elif line != "" and not line.startswith("'"):
                divider = False
    
    # Set available colors to what is configured in the palette
    def parse_colors(self, palette_line):
        self.colors = palette_line.lstrip().split(",")

    # Set available styles based on the configuration
    def parse_styles(self, style_lines, resolve_colors=False):
        fields = {}
        style_no = None
        for n, line in enumerate(style_lines):
            line = line.lstrip()
            if line == "" and style_no is not None:
                style_no = None
                fields = {}
            elif style_no is None and line.startswith("Style"):
                tmp = line.split(",")
                style_no = int(tmp[0][5:])
                tmp = [f"{tmp[0]}_{tmp[1]}", *(int(x) for x in tmp[2:])]
                fields.update(dict(zip(("name", "textcolor", "outlinecolor", "textwipecolor", "outlinewipecolor"),tmp)))
                tmp = style_lines[n+1].lstrip().split(",")
                tmp[1] = int(tmp[1])
                tmp[3] = int(tmp[3])
                fields.update(dict(zip(("fontname", "fontsize", "fontstyle", "charset"),tmp)))
                tmp = style_lines[n+2].lstrip().split(",")
                tmp[:-1] = [int(x) for x in tmp[:-1]]
                fields.update(dict(zip(("outlines", "shadows", "wipestyle", "allcaps"),(tmp[:4],tmp[4:6],tmp[6],tmp[7]))))
                result = KBPStyle(**fields)
                if resolve_colors:
                    result = result.resolved_colors(self.colors)
                self.styles[style_no] = result
            # else second/third line of styles already processed
    
    # Set margins based on the configuration
    def parse_margins(self, margin_line):
        self.margins = dict(zip(("left", "right", "top", "spacing"), (int(x) for x in margin_line.strip().split(","))))

    # Data currently not used
    def parse_other(self, other_line):
        self.other = dict(zip(("bordercolor", "wipedetail"), (int(x) for x in other_line.strip().split(","))))

    # Data currently not used
    def parse_trackinfo(self, trackinfo_lines):
        self.trackinfo = {}
        prev = None
        for line in trackinfo_lines:
            if line.startswith(" "):
                self.trackinfo[prev] += f"\n{line.lstrip()}"
            elif line != "" and not line.startswith("'"):
                fields = line.split(maxsplit=1)
                fields[0] = fields[0].lower()
                if len(fields) == 1:
                    fields.append("")
                self.trackinfo[fields[0]] = fields[1]
                prev = fields[0]

    # Add a page from the provided info
    def parse_page(self, page_lines):
        lines=[]
        syllables=[]
        header=None
        transitions=["", ""] # Default line by line
        for x in page_lines:
            if header is None and re.match(r"[LCR]/[a-zA-Z](/\d+){5}$", x):
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
            elif x != "":
                fields = x.split("/")
                fields[0] = re.sub(r"{-}", "/", fields[0]) # This field uses this as a surrogate for / since that denotes end of syllable
                fields[1] = fields[1].lstrip() # Only the second field should have extra spaces
                fields[1:] = [int(y) for y in fields[1:]]
                syllables.append(KBPSyllable(**dict(zip(("syllable", "start", "end", "wipe"), fields))))
        self.pages.append(KBPPage(*transitions, lines))
    
    # Data currently not used
    def parse_image(self, image_line):
        fields = image_line.split("/")
        for x in (0, 1, 3):
            fields[x] = int(fields[x])
        self.images.append(KBPImage(**dict(zip(("start", "end", "filename", "leaveonscreen"),fields))))

    def text(self, page_separator="", include_empty=False, syllable_separator="", space_is_separator=False):
        result = []
        for page in self.pages:
            lines = []
            for line in page:
                if include_empty or not line.isempty():
                    lines.append(line.text(syllable_separator=syllable_separator, space_is_separator=space_is_separator))
            result.append("\n".join(lines))
        return f"\n{page_separator}\n".join(result)

class KBPLineHeader(collections.namedtuple("KBPLineHeader", ("align", "style", "start", "end", "right", "down", "rotation"))):
    __slots__ = ()

    def isfixed(self):
        return self.style.islower()

class KBPSyllable(collections.namedtuple("KBPSyllable", ("syllable", "start", "end", "wipe"))):
    __slots__ = ()

    def isempty(self):
        return self.syllable == ""

class KBPLine(collections.namedtuple("KBPPage", ("header", "syllables"))):
    __slots__ = ()

    # There's only one header, so may as well pass anything unresolved down to it
    def __getattr__(self, attr):
        return getattr(self.header, attr)

    def text(self, syllable_separator="", space_is_separator=False):
        if space_is_separator and syllable_separator != "":
            result = ""
            for syl in self.syllables:
                syltext = syl.syllable
                syltext = re.sub(r"( +)(?=[^ ])", lambda m: "_" * len(m.group(1)), syltext)
                result += syltext
                if not syltext.endswith(" "):
                    result += syllable_separator
            return result[:-len(syllable_separator)]
        else:
            return syllable_separator.join(x.syllable for x in self.syllables)

    def isempty(self):
        return not self.syllables or (len(self.syllables) == 1 and self.syllables[0].isempty())

class KBPStyle(collections.namedtuple("KBPStyle", ("name", "textcolor", "outlinecolor", "textwipecolor", "outlinewipecolor", "fontname", "fontsize", "fontstyle", "charset", "outlines", "shadows", "wipestyle", "allcaps"))):
    __slots__ = ()

    def resolved_colors(self, palette):
        result = self._asdict()
        for x in ("textcolor", "outlinecolor", "textwipecolor", "outlinewipecolor"):
            result[x] = palette[result[x]]
        return KBPStyle(**result)

    def has_colors(self):
        fields = ("textcolor", "outlinecolor", "textwipecolor", "outlinewipecolor")
        if all(type(getattr(self,x)) is str for x in fields):
            return True
        elif all(type(getattr(self,x)) is int for x in fields):
            return False
        else:
            raise TypeError("Mixed/unexpected types found in color parameters:\n\t" + 
                "\n\t".join([": ".join((x, str(getattr(self,x)))) for x in fields]))

class KBPPage(collections.namedtuple("KBPPage", ("remove", "display", "lines"))):
    __slots__ = ()

    def get_start(self):
        return min(line.start for line in self.lines if not line.isempty())

    def get_end(self):
        return max(line.end for line in self.lines)

class KBPImage(collections.namedtuple("KBPImage", ("start", "end", "filename", "leaveonscreen"))):
    __slots__ = ()
