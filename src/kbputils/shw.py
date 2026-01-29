import collections
import re
import typing
import io
import os.path
import dataclasses
import enum
import itertools

"""
=== SHW File layout ===

    == Headers ==

Header: "[Slideshow]"
Settings (one line, colon-separated):
    - Total number of slides (including the first one that must be empty)
    - slideshow length type (minimized=0, add_time=1, fixed_len=2)
    - duration (CDG ticks, 300 per second)
    - last CDG filename (full path or relative to SHW)
    - 10 empty entries?
Unknown (e.g. "40")

    == Each slide ==

Palette (16 lines): each color is a 24-bit decimal with every other nibble being used as a color channel to make a 12-bit color (i.e. hex value is BXGXRX where B, G, R represent the color channels and X are discarded)
Unknown X 7 (e.g. all "0")
Image filename (empty if slide 0 or text slide)
Transition Name
Transition direction ("0" for forward, "-1" for reversed)
Viewing duration (CDG ticks)
Unknown (e.g. "0")
Dithering (true="-1", false="0")
Resize method (fit=0, stretch=1, crop=2)
Alignment (top-left=1, top-right=3, bottom-right=9)
Border color (palette index 0-16)
Crop alignment
Transition duration (CDG ticks)
Text (one line, "{#}"-separated within an entry, "{@}" between entries):
    - Across
    - Down
    - Text
    - Color (see color description above) - note that if the color is not in the palette, it would normally be replaced with the closest available, or multiple close ones, applying dithering if that's enabled
    - Font face
    - Font size
    - Font style ("B"old, "I"talic, "U"nderline, "S"trikeout, "A"llcaps, "J"agged (not smooth)) - letters concatenated together
    - Encoding (E.g. 0 for Western)
    - Unknown X 8 (e.g. "0")
    - Alignment ("L"eft, "C"enter, "R"ight)
Unknown X 5 (e.g. "0")
"""

class DurationType(enum.Enum):
    MINIMIZED = 0 # Use the least possible amount of CDG instructions
    ADD_TIME = 1 # Add a duration at the end after minimizing instructions
    FIXED = 2 # Attempt to make the overall duration a specific value (implementation method unknown)

class ImageAlignment(enum.Enum):
    TOP_LEFT = 1
    TOP_CENTER = 2
    TOP_RIGHT = 3
    MIDDLE_LEFT = 4
    MIDDLE_CENTER = 5
    MIDDLE_RIGHT = 6
    BOTTOM_LEFT = 7
    BOTTOM_CENTER = 8
    BOTTOM_RIGHT = 9

# Helper to construct a dataclass when all its member types can be coerced from strings
def dataclass_init_from_strings(klass: type, values: typing.List[str]):
    return klass(*(x.type(y) for x,y in zip(dataclasses.fields(klass), values)))

@dataclasses.dataclass
class SlideshowSettings:
    # TODO incorporate number of slides value? Perhaps return it in from_string so it can be used in validation
    duration_type: DurationType
    duration: int # Used only with duration_types ADD_TIME and FIXED, CDG ticks
    cdg_filename: str
    # TODO figure out unknown fields

    @staticmethod
    def from_string(s: str) -> typing.Self:
        vals = s.split(":")
        return SlideshowSettings(DurationType(int(vals[1])), int(vals[2]), vals[3])

class ResizeMethod(enum.Enum):
    FIT = 0 # letterbox to aspect ratio then apply alignment
    STRETCH = 1 # expand to space, ignoring aspect ratio
    CROP = 2 # keep size and align to crop alignment, allowing parts to go offscreen

@dataclasses.dataclass
class SlideTextLine:
    across: int
    down: int
    text: str
    color: int
    font_face: str
    font_size: int
    font_style: str # May only contain the characters "BIUSAJ"
    encoding: int
    # TODO figure out unknown fields
    alignment: str # May only be "L", "C", or "R"

    @staticmethod
    def lines_from_string(s: str) -> typing.List[typing.Self]:
        result = []
        for x in s.split("{@}")[:-1]: # Ends with a separator, so exclude last
            fields = x.split("{#}")
            fields = fields[:8] + fields[-1:] # Ignore the unknown fields
            result.append(dataclass_init_from_strings(SlideTextLine, fields))
        return result

@dataclasses.dataclass
class Slide:
    palette: list[int]
    # TODO figure out unknown fields
    image_filename: str
    transition_name: str
    transition_reversed: bool
    view_duration: int # minimum time of the slide on screen excluding transitions
    # TODO figure out unknown field
    dither: bool
    resize_method: ResizeMethod
    alignment: ImageAlignment
    border_color: int
    crop_alignment: ImageAlignment
    transition_duration: int
    text: list[SlideTextLine]
    # TODO figure out unknown fields

    @staticmethod
    def from_strings(data: typing.List[str]) -> typing.Self:
        return Slide(
                palette = [int(x) for x in data[:16]],
                image_filename = data[23],
                transition_name = data[24],
                transition_reversed = data[25] != "0",
                view_duration = int(data[26]),
                dither = data[28] != "0",
                resize_method = ResizeMethod(int(data[29])),
                alignment = ImageAlignment(int(data[30])),
                border_color = int(data[31]), # Leaving index in case we need to check if it's index 0 (e.g. bg transparency)
                crop_alignment = ImageAlignment(int(data[32])),
                transition_duration = int(data[33]),
                text = SlideTextLine.lines_from_string(data[34]),
             )


class SHWFile:

    HEADER = '[Slideshow]'

    def __init__(self, file):
        self.slides = []
        self.filename = file
        f = open(file, "r", encoding="utf-8")
        line = (x.rstrip('\r\n') for x in f)
        if next(line) != SHWFile.HEADER:
            raise ValueError("File doesn't start with the [Slideshow] header")
        self.settings = SlideshowSettings.from_string(next(line))
        next(line) # ignore unknown
        for slide_data in itertools.batched(line, n=40):
            if len(slide_data) == 40:
                self.slides.append(Slide.from_strings(slide_data))
        f.close()


def shwcolor_to_hex(shwcolor: int, to24bit: bool = True):
    b = shwcolor >> 20
    g = (shwcolor >> 12) % 16
    r = (shwcolor >> 4) % 16
    n=1
    if to24bit:
        r *= 0x11
        g *= 0x11
        b *= 0x11
        n = 2
    return f"0x{r:0{n}x}{g:0{n}x}{b:0{n}x}"
