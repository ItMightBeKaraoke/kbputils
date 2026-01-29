import dataclasses
import ffmpeg
import os
import types
import re
from .. import shw
from . import kbp2ass # TODO maybe some of the static helper methods need to move out of here
from .. import validators
from ..utils import Dimension

@validators.validated_instantiation(replace="__init__")
@dataclasses.dataclass
class SHWConvertOptions:
    target_x: int = dataclasses.field(default=1500, metadata={"doc": "Output video width"})
    target_y: int = dataclasses.field(default=1080, metadata={"doc": "Output video height"})
    border: bool = dataclasses.field(default=True, metadata={"doc": "Render CDG border"})

    @validators.validated_types
    @staticmethod
    def __assert_valid(key: str, value):
        return validators.validate_and_coerce_values(SHWConvertOptions._fields, key, value)

    @validators.validated_structures(assert_function=__assert_valid)
    def update(self, **options):
        for opt in options:
            setattr(self, opt, options[opt])

SHWConvertOptions._fields = types.MappingProxyType(dict((f.name, f) for f in dataclasses.fields(SHWConvertOptions)))

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
        output_size = Dimension(self.options.target_x, self.options.target_y)

        for slide in self.shwfile.slides:
            full_duration = (slide.view_duration + slide.transition_duration)/300
            bg = ffmpeg.input(f"color={shw.shwcolor_to_hex(slide.palette[0])}:r=60:s={output_size}", f="lavfi", t=full_duration)
            if slide.image_filename:
                # TODO path management stuff?
                # TODO fade out (needs next slide's fade in)
                # TODO some transition support other than fade
                # TODO position/scaling
                overlay = ffmpeg.input(slide.image_filename, framerate=60, loop=1, t=full_duration)
                overlay = overlay.filter_("scale", s=output_size, force_original_aspect_ratio="decrease")
                overlay = overlay.filter_("fade", t="in", d=slide.transition_duration/300, alpha=1)
                bg = bg.overlay(overlay)
            elif slide.text:
                for line in slide.text:
                    # TODO style, margin, border, etc
                    # TODO transition: draw on transparent background and apply fade?
                    bg = bg.filter_("drawtext", 
                                    text=line.text,
                                    fontcolor=shw.shwcolor_to_hex(line.color),
                                    font=line.font_face,
                                    fontsize=kbp2ass.AssConverter.rescale_scalar(line.font_size, *output_size, font=True),
                                    text_align="T+"+line.alignment,
                                    y_align="font",
                                    x=kbp2ass.AssConverter.rescale_scalar(line.across, *output_size),
                                    boxw=output_size.width(),
                                    y=kbp2ass.AssConverter.rescale_scalar(line.down, *output_size),
                                   )
            video = video.concat(bg) if video else bg
        ffmpeg_options = ffmpeg.output(video, self.vidfile).get_args()
        print(f"cd {os.getcwd()}")
        print("ffmpeg" + " " + " ".join(x if re.fullmatch(r"[\w\-/:\.]+", x) else f'"{x}"' for x in ffmpeg_options))
        os.chdir(oldcwd)
