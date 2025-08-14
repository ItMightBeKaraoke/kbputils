import dataclasses
import types
import math
from .. import kbp
from .. import validators
from .. import doblontxt
from .. import lrc


@validators.validated_instantiation(replace="__init__")
@dataclasses.dataclass
class LyricsOptions:
    title: str = ''
    artist: str = ''
    audio_file: str = ''
    comments: str = 'Created with kbputils'
    max_lines_per_page: int = 6
    min_gap_for_new_page: int = 1000
    display_before_wipe: int = 1000
    remove_after_wipe: int = 500
    template_file: str = ''

    @validators.validated_types
    @staticmethod
    def __assert_valid(key: str, value):
        if key in LyricsOptions._fields:
            if not isinstance(value, (t := LyricsOptions._fields[key].type)):
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
LyricsOptions._fields = types.MappingProxyType(dict((f.name,f) for f in dataclasses.fields(LyricsOptions)))

# Create aliases in case anyone is relying on the old name
DoblonTxtOptions = LyricsOptions
LRCOptions = LyricsOptions

class LyricsConverter:
    def __init__(self):
        raise NotImplementedError("LyricsConverter type must be subclassed")

    @staticmethod
    def syl2kbp(syl: str) -> str:
        if syl.endswith("-"):
            syl = syl[:-1]
        return syl.replace("/", "{~}")

    def kbpFile(self):
        if hasattr(self, 'kbpfile'):
            return self.kbpfile
        self.kbpfile = self.template
        delattr(self, 'template')
        if not hasattr(self.kbpfile, 'trackinfo'):
            self.kbpfile.trackinfo = {'Status': '1', 'Title': self.options.title, 'Artist': self.options.artist, 'Audio': self.options.audio_file, 'BuildFile': '', 'Intro': '', 'Outro': '', 'Comments': self.options.comments}

        # Add empty line to ensure last page is processed
        self.srcFile.lines.append([])

        kbplines = []
        for line in self.srcFile.lines:
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
                style="A", # TODO: Figure out generic way to handle if a lyrics type has parts (midiCo LRC)
                start=round((line[0][0] - self.options.display_before_wipe)/10),
                end=round((line[-1][1] + self.options.remove_after_wipe)/10),
                right=0,
                down=0,
                rotation=0
            ) 
            kbpline = kbp.KBPLine(line_header, [kbp.KBPSyllable(self.syl2kbp(syl), round(start/10), round(end/10), 0) for start, end, syl in line])
            kbplines.append(kbpline)
        return self.kbpfile

class DoblonTxtConverter(LyricsConverter):
    @validators.validated_types
    def __init__(self, doblonTxtFile: doblontxt.DoblonTxt, options: DoblonTxtOptions | types.NoneType = None, **kwargs):
        self.srcFile = doblonTxtFile
        self.options = options or DoblonTxtOptions()
        self.options.update(**kwargs)
        self.template = kbp.KBPFile(self.options.template_file, template=True) if self.options.template_file else kbp.KBPFile()

class LRCConverter(LyricsConverter):
    @validators.validated_types
    def __init__(self, lrcFile: lrc.LRC, options: LRCOptions | types.NoneType = None, **kwargs):
        self.srcFile = lrcFile
        implicitopts = {'ti': 'title', 'ar': 'artist', '#': 'comments'}
        self.options = options or LRCOptions(**{implicitopts[x]: lrcFile.tags[x] for x in lrcFile.tags if x in implicitopts})
        self.options.update(**kwargs)
        self.template = kbp.KBPFile(self.options.template_file, template=True) if self.options.template_file else kbp.KBPFile()
