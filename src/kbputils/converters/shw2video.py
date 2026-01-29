import dataclasses
import ffmpeg
import os
import types
import re
import enum
from .. import shw
from . import kbp2ass # TODO maybe some of the static helper methods need to move out of here
from .. import validators
from ..utils import Dimension

class SHWBorderStyle(enum.Enum):
    NONE = enum.auto()
    CDG = enum.auto()
    EQUAL = enum.auto()

    def __str__(self):
        return self.name

    def __bool__(self):
        return self != SHWBorderStyle.NONE

@validators.validated_instantiation(replace="__init__")
@dataclasses.dataclass
class SHWConvertOptions:
    target_x: int = dataclasses.field(default=1500, metadata={"doc": "Output video width"})
    target_y: int = dataclasses.field(default=1080, metadata={"doc": "Output video height"})
    border: SHWBorderStyle = dataclasses.field(default=SHWBorderStyle.CDG, metadata={"doc": "Type of border to apply to the video"})

    @validators.validated_types
    @staticmethod
    def __assert_valid(key: str, value):
        return validators.validate_and_coerce_values(SHWConvertOptions._fields, key, value)

    @validators.validated_structures(assert_function=__assert_valid)
    def update(self, **options):
        for opt in options:
            setattr(self, opt, options[opt])

SHWConvertOptions._fields = types.MappingProxyType(dict((f.name, f) for f in dataclasses.fields(SHWConvertOptions)))

#workaround for ffmpeg-python deduplicating identical filters
cur_filter_id=0
def filter_id():
    global cur_filter_id
    cur_filter_id += 1
    return cur_filter_id

def cleanup_args(args, name):
    location = args.index("-filter_complex") + 1
    args[location] = re.sub(r"[=:]" + re.escape(name) + r"=\d+", "", args[location])

class SHWConverter:
    @validators.validated_types
    def __init__(self, source: shw.SHWFile, dest: str, options: SHWConvertOptions | None = None, **kwargs):
        self.options = options or SHWConvertOptions()
        self.options.update(**kwargs)
        self.shwfile = source
        self.vidfile = os.path.abspath(dest)

    def run(self):
        oldcwd = os.getcwd()
        os.chdir(os.path.dirname(self.shwfile.filename))
        video = None
        viewport_size = output_size = Dimension(self.options.target_x, self.options.target_y)
        if self.options.border:
            cdg_cursorheight = kbp2ass.AssConverter.rescale_scalar(12, *output_size)
            border_width = cdg_cursorheight if self.options.border == SHWBorderStyle.EQUAL else cdg_cursorheight // 2
            viewport_size = output_size - Dimension(2*border_width, 2*cdg_cursorheight)

        for slide in self.shwfile.slides:
            full_duration = (slide.view_duration + slide.transition_duration)/300
            bg = ffmpeg.input(f"color={shw.shwcolor_to_hex(slide.palette[0])}:r=60:s={viewport_size}", f="lavfi", t=full_duration)
            if slide.image_filename:
                # TODO path management stuff?
                # TODO fade out (needs next slide's fade in)
                # TODO some transition support other than fade
                # TODO position/scaling
                overlay = ffmpeg.input(slide.image_filename, framerate=60, loop=1, t=full_duration)
                overlay = overlay.filter_("scale", s=viewport_size, force_original_aspect_ratio="decrease")
                overlay = overlay.filter_("fade", t="in", d=slide.transition_duration/300, alpha=1)
                bg = bg.overlay(overlay, x="(W-w)/2", y="(H-h)/2", remove_me=filter_id())
            elif slide.text:
                for line in slide.text:
                    # TODO style, margin, border, etc
                    # TODO transition: draw on transparent background and apply fade?
                    bg = bg.drawtext(
                                    text=line.text,
                                    expansion="none",
                                    fontcolor=shw.shwcolor_to_hex(line.color),
                                    font=line.font_face,
                                    fontsize=kbp2ass.AssConverter.rescale_scalar(line.font_size, *viewport_size, font=True),
                                    text_align="T+"+line.alignment,
                                    y_align="font",
                                    x=kbp2ass.AssConverter.rescale_scalar(line.across, *viewport_size),
                                    boxw=viewport_size.width,
                                    y=kbp2ass.AssConverter.rescale_scalar(line.down, *viewport_size),
                                   )
            if self.options.border:
                border = ffmpeg.input(f"color={shw.shwcolor_to_hex(slide.palette[slide.border_color])}:r=60:s={output_size}",
                                      f="lavfi",
                                      t=full_duration
                                     )
                bg = border.overlay(bg, x=border_width, y=cdg_cursorheight, remove_me=filter_id())
            video = video.concat(bg) if video else bg
        ffmpeg_options = ffmpeg.output(video, self.vidfile).get_args()
        cleanup_args(ffmpeg_options, "remove_me")
        print(f"cd {os.getcwd()}")
        print("ffmpeg" + " " + " ".join(x if re.fullmatch(r"[\w\-/:\.]+", x) else f'"{x}"' for x in ffmpeg_options))
        os.chdir(oldcwd)
