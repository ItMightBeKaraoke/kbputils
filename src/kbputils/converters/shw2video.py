import dataclasses
import ffmpeg
import os
import types
import re
import enum
import tempfile
import subprocess
import pathlib
from .. import shw
from . import kbp2ass # TODO maybe some of the static helper methods need to move out of here
from .. import kbp
from .. import validators
from ..utils import Dimension
from ..utils import abspath
from .._ffmpegcolor import ffmpeg_color

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
    media_container: str | None = dataclasses.field(default=None, metadata={"doc": "Container file type to use for video output. If unspecified, will allow ffmpeg to infer from provided output filename"})
    video_codec: str = dataclasses.field(default="h264", metadata={"doc": "Codec to use for video output"})
    video_quality: int = dataclasses.field(default=23, metadata={"doc": "Video encoding quality, uses a CRF scale so lower values are higher quality. Recommended settings are 15-35, though it can vary between codecs. Set to 0 for lossless"})
    output_options: dict = dataclasses.field(default_factory=lambda: {"pix_fmt": "yuv420p"}, metadata={"doc": "Additional parameters to pass to ffmpeg"})

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
    def __init__(self, source: shw.SHWFile | kbp.KBPFile, dest: str, options: SHWConvertOptions | None = None, **kwargs):
        self.options = options or SHWConvertOptions()
        self.options.update(**kwargs)
        if isinstance(source, shw.SHWFile):
            self.shwfile = source
        else:
            self.kbpfile = source
        self.vidfile = os.path.abspath(dest)

    # Take a text string, requested font face, and an SHW style string and
    # return a dict of the text with caps applied if requested, and font face
    # with style transformations applied suitable for drawtext/fontconfig
    # Supported: bold, italic, allcaps
    # Not supported: strike-through, underline, jagged (not smooth)
    @staticmethod
    def style_text(text: str, font_face: str, style: str) -> dict[str, str]:
        if 'A' in style:
            text = text.upper()
        # This was a cute idea but ultimately fails because it only works on fonts that include these combining marks
        #combining_characters = {
        #        "S": "\u0336",
        #        "U": "\u0332"
        #    }
        #if to_combine := "".join(map(lambda x: combining_characters[x], combining_characters.keys() & set(style))):
        #    text = unicodedata.normalize("NFC", "".join(map(lambda x: x+to_combine, f" {text}"))+" ")
        font_transformations = {
                #TODO determine the preferred way to specify these.
                # Symbolic constants for bold and italic can apparently be
                # specified with or without their associated property, as well
                # as with "style". Not clear why the style option even exists if
                # it's not even needed - back compat?
                # https://freedesktop.org/software/fontconfig/fontconfig-user.html#AEN21
                #"B": "weight=bold",
                "B": "bold",
                #"I": "slant=italic",
                "I": "italic",
                # Doesn't seem to do anything, so removing for now
                #"J": "hintstyle=hintnone",
            }
        for x in font_transformations:
            if x in style:
                # ffmpeg-python already escapes the :, but apparently it needs to be double-escaped
                # It actually ends up triple-escaped this way somehow, but it still seems to work
                font_face += "\\:" + font_transformations[x]
        return {"text": text, "fontfile": font_face}

    def run(self):
        tmpdirs = []
        if hasattr(self, "kbpfile"):
            oldcwd = os.getcwd()
            if hasattr(self.kbpfile, "filename"):
                os.chdir(pathlib.Path(self.kbpfile.filename).parent)
            bgcolor = self.kbpfile.colors.as_rgb24()[0]
            # TODO kbp border
            size = Dimension(self.options.target_x, self.options.target_y)
            video = ffmpeg.input(f"color={bgcolor}:s={size}:r=60", f="lavfi")
            # else unlikely to find any of the shw files, but we'll try anyway...
            candidates = {}
            for idx, img in enumerate(self.kbpfile.images):
                cdg_file = abspath(img.filename)
                shw_file = cdg_file.parent.joinpath(cdg_file.stem + ".shw")
                if not shw_file.exists():
                    if not candidates:
                        for x in pathlib.Path.glob("**/*.shw", case_sensitive=False):
                            try:
                                s = shw.SHWFile(x)
                                candidates[pathlib.PureWindowsPath(s.cdg_filename).name] = x
                            except:
                                pass
                    if cdg_file.name in candidates:
                        shw_file = candidates[cdg_file.name]
                    else:
                        raise FileNotFoundError(shw_file)
                overlay, tmpdir = self._convert(shw.SHWFile(shw_file))
                tmpdirs.append(tmpdir)
                if img.start > 1:
                    overlay = ffmpeg_color(color="000000@0", r=60, s="1920x1080", d=img.start/100.0).filter_("format", "rgba").concat(overlay)
                if idx == len(self.kbpfile.images) - 1:
                    eof_action = "endall"
                elif img.leaveonscreen:
                    eof_action = "repeat"
                else:
                    eof_action = "pass"
                # Add a couple frames of background if the slide isn't supposed to be left on screen, so the last frame can still be repeated
                if idx == len(self.kbpfile.images) - 1 and not img.leaveonscreen:
                    overlay = overlay.concat(ffmpeg_color(color="000000@0", r=60, s="1920x1080", d="20ms").filter_("format", "rgba"))
                video = video.overlay(overlay, eof_action = eof_action)
            os.chdir(oldcwd)
        else:
            video, tmpdir = self._convert()
            tmpdirs.append(tmpdir)

        output_options = {}
        if self.options.video_quality == 0:
            if self.options.video_codec == "libvpx-vp9":
                output_options["lossless"]=1
            elif self.options.video_codec in ("libx265", "libsvtav1"):
                output_options[f"{self.options.video_codec[3:]}-params"]="lossless=1"
            elif self.options.video_codec != "png":
                output_options["crf"]=0
        else:
            output_options["crf"]=self.options.video_quality

        if self.options.video_codec == "libvpx-vp9":
            output_options["video_bitrate"] = 0 # Required for the format to use CRF only

        if self.options.video_codec in ("libvpx-vp9", "libaom-av1"):
            output_options["row-mt"] = 1 # Speeds up encode for most multicore systems

        if self.options.media_container:
            output_options["f"] = self.options.media_container

        output_options.update({
            "c:v": self.options.video_codec,
            **self.options.output_options
        })

        ffmpeg_options = ffmpeg.output(video, self.vidfile, **output_options).overwrite_output().get_args()
        cleanup_args(ffmpeg_options, "remove_me")
        print(f"cd {os.getcwd()}")
        print("ffmpeg" + " " + " ".join(x if re.fullmatch(r"[\w\-/:\.]+", x) else f'"{x}"' for x in ffmpeg_options))
        subprocess.run(["ffmpeg"] + ffmpeg_options)
        for tmpdir in tmpdirs:
            if tmpdir:
                tmpdir.cleanup()

    def _convert(self, shwfile: shw.SHWFile | None = None) -> tuple:
        if not shwfile:
            shwfile = self.shwfile
        oldcwd = os.getcwd()
        os.chdir(pathlib.Path(shwfile.filename).parent)
        video = None
        viewport_size = output_size = Dimension(self.options.target_x, self.options.target_y)
        if self.options.border:
            cdg_cursorheight = kbp2ass.AssConverter.rescale_scalar(12, *output_size)
            border_width = cdg_cursorheight if self.options.border == SHWBorderStyle.EQUAL else cdg_cursorheight // 2
            viewport_size = output_size - Dimension(2*border_width, 2*cdg_cursorheight)

        aspect_handling = {
                            shw.ResizeMethod.FIT: "decrease",
                            shw.ResizeMethod.CROP: "increase",
                            shw.ResizeMethod.STRETCH: "disable",
                          }
        alignment_handling = {
                               -1: "0",
                                0: "({}-{})/2",
                                1: "{}-{}"
                             }
        transitions = {
                        "Fade": ["fade", "fade"],
                        "Circle": ["circleopen", "circleclose"],
                        "Clock (Single)": ["radial", "radial"], # No counterclockwise option
                        "Diagonal (Bottom Left)": ["diagonaltr", "diagonalbl"],
                        "Diagonal (Top Left)": ["diagonalbr", "diagonaltl"],
                        "Left to Right": ["wiperight", "wipeleft"],
                        "Random Snow": ["dissolve", "dissolve"],
                        "Smooth Scroll (Horizontal)": ["slideleft", "slideright"],
                        "Smooth Scroll (Vertical)": ["slideup", "slidedown"],
                        "Scroll (Horizontal)": ["slideleft", "slideright"],
                        "Scroll (Vertical)": ["slideup", "slidedown"],
                        "Top to Bottom": ["wipedown", "wipeup"],
                      }

        transition_durations = {
                                 "Fade": None, # Use specified transition duration
                                 "Clear Screen": 0.1,
                                 "default": 2.0,
                               }

        offset = 0
        tmpdir = None
        for idx, slide in enumerate(shwfile.slides):
            transition_len = transition_durations.get(slide.transition_name, transition_durations["default"]) or slide.transition_duration/300

            if idx + 1 < len(shwfile.slides):
                nxt = shwfile.slides[idx+1]
                fadeout_len = transition_durations.get(nxt.transition_name, transition_durations["default"]) or nxt.transition_duration/300
            else:
                fadeout_len = 0.0

            full_duration = slide.view_duration/300 + transition_len + fadeout_len
            bg = ffmpeg.input(f"color={shw.shwcolor_to_hex(slide.palette[0])}:r=60:s={viewport_size}", f="lavfi", t=full_duration)
            if slide.image_filename:
                # TODO path management stuff?
                alignment = slide.crop_alignment if slide.resize_method == shw.ResizeMethod.CROP else slide.alignment
                overlay = ffmpeg.input(str(abspath(slide.image_filename)), framerate=60, loop=1, t=full_duration)
                overlay = overlay.filter_("scale", s=viewport_size, force_original_aspect_ratio=aspect_handling[slide.resize_method])
                bg = bg.overlay(
                                 overlay,
                                 x=alignment_handling[slide.alignment.x_value()].format("W", "w"),
                                 y=alignment_handling[slide.alignment.y_value()].format("H", "h"),
                                 eval='init',
                                 remove_me=filter_id()
                               )
            elif slide.text:
                if not tmpdir:
                    tmpdir = tempfile.TemporaryDirectory(delete=False)
                for l, line in enumerate(slide.text):
                    styled_text = SHWConverter.style_text(line.text, line.font_face, line.font_style)
                    tmpfile = os.path.join(tmpdir.name, f"slide{idx}_line{l}.txt")
                    with open(tmpfile, "w") as f:
                        f.write(styled_text["text"])
                    bg = bg.drawtext(
                                    textfile=tmpfile,
                                    fontfile=styled_text["fontfile"],
                                    expansion="none",
                                    fontcolor=shw.shwcolor_to_hex(line.color),
                                    fontsize=kbp2ass.AssConverter.rescale_scalar(line.font_size, *viewport_size, font=True, border=False),
                                    text_align="T+"+line.alignment,
                                    y_align="font",
                                    x=kbp2ass.AssConverter.rescale_scalar(line.across, *viewport_size, border=False),
                                    boxw=viewport_size.width,
                                    y=kbp2ass.AssConverter.rescale_scalar(line.down, *viewport_size, border=False),
                                   )
            if self.options.border:
                border = ffmpeg.input(f"color={shw.shwcolor_to_hex(slide.palette[slide.border_color])}:r=60:s={output_size}",
                                      f="lavfi",
                                      t=full_duration,
                                     )
                bg = border.overlay(bg, x=border_width, y=cdg_cursorheight, remove_me=filter_id())
            if video:
                video = ffmpeg.filter_([video, bg],
                                       "xfade",
                                       transition=transitions.get(slide.transition_name, ["fade", "fade"])[int(slide.transition_reversed)],
                                       duration=transition_len,
                                       offset=offset,
                                       remove_me=filter_id()
                                      )
            else:
                video = bg
            offset += full_duration - fadeout_len

        os.chdir(oldcwd)

        return (video, tmpdir)
