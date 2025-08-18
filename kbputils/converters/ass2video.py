import dataclasses
import ffmpeg
import enum
import fractions
import os
import re
import subprocess
import types
from .._ffmpegcolor import ffmpeg_color
from .. import validators

@validators.validated_instantiation(replace="__init__")
@dataclasses.dataclass
class VideoOptions:
    preview: bool = dataclasses.field(default=False, metadata={"doc": "If set, do not run ffmpeg, only output the command that would be run"})
    audio_file: str | None = dataclasses.field(default=None, metadata={"doc": "Audio track to use with video"})
    aspect_ratio: fractions.Fraction = dataclasses.field(default=fractions.Fraction(300,216), metadata={"doc": "Aspect ratio of rendered subtitle. This will be letterboxed if not equal to the aspect ratio of the output video"})
    target_x: int = dataclasses.field(default=1500, metadata={"doc": "Output video width"})
    target_y: int = dataclasses.field(default=1080, metadata={"doc": "Output video height"})
    background_color: str = dataclasses.field(default="#000000", metadata={"doc": "Background color for the video, as 24-bit RGB hex value"})
    background_media: str | None = dataclasses.field(default=None, metadata={"doc": "Path to image or video to play in the background of the video"})
    loop_background_video: bool = dataclasses.field(default=False, metadata={"doc": "If using a background video, leaving this unset will play the background video exactly once, repeating the last frame if shorter than the audio, or continuing past the end of the audio if longer. If set, the background video will instead loop exactly as many times needed (including fractionally) to match the audio."})
    media_container: str | None = dataclasses.field(default=None, metadata={"doc": "Container file type to use for video output. If unspecified, will allow ffmpeg to infer from provided output filename"})
    video_codec: str = dataclasses.field(default="h264", metadata={"doc": "Codec to use for video output"})
    video_quality: int = dataclasses.field(default=23, metadata={"doc": "Video encoding quality, uses a CRF scale so lower values are higher quality. Recommended settings are 15-35, though it can vary between codecs. Set to 0 for lossless"})
    audio_codec: str = dataclasses.field(default="aac", metadata={"doc": "Codec to use for audio output"})
    audio_bitrate: int = dataclasses.field(default=256, metadata={"doc": "Bitrate for audio output, in kbps"})
    intro_media: str | None = dataclasses.field(default=None, metadata={"doc": "Image or video file to play at start of track, layered above the background, but below any subtitles"})
    outro_media: str | None = dataclasses.field(default=None, metadata={"doc": "Image or video file to play at end of track, layered above the background, but below any subtitles"})
    intro_length: int = dataclasses.field(default=0, metadata={"doc": "Time in milliseconds to play the intro if a file was specified"})
    outro_length: int = dataclasses.field(default=0, metadata={"doc": "Time in milliseconds to play the outro if a file was specified"})
    intro_fadeIn: int = dataclasses.field(default=0, metadata={"doc": "Time in milliseconds to fade in the intro"})
    outro_fadeIn: int = dataclasses.field(default=0, metadata={"doc": "Time in milliseconds to fade in the outro"})
    intro_fadeOut: int = dataclasses.field(default=0, metadata={"doc": "Time in milliseconds to fade out the intro"})
    outro_fadeOut: int = dataclasses.field(default=0, metadata={"doc": "Time in milliseconds to fade out the outro"})
    intro_concat: bool = dataclasses.field(default=False, metadata={"doc": "Play the intro before the audio/video starts instead of inserting at time 0"})
    outro_concat: bool = dataclasses.field(default=False, metadata={"doc": "Play the outro before the audio/video starts instead of inserting at time 0"})
    intro_fade_black: bool = dataclasses.field(default=False, metadata={"doc": "Fade in the video from a black screen instead of showing the background media immediately"})
    outro_fade_black: bool = dataclasses.field(default=False, metadata={"doc": "Fade the video out to a black screen instead of fading back to the background media"})
    output_options: dict = dataclasses.field(default_factory=lambda: {"pix_fmt": "yuv420p"}, metadata={"doc": "Additional parameters to pass to ffmpeg"})

    @validators.validated_types
    @staticmethod
    def __assert_valid(key: str, value):                                                                                                          
        return validators.validate_and_coerce_values(VideoOptions._fields, key, value)
    
    @validators.validated_structures(assert_function=__assert_valid)
    def update(self, **options):
        for opt in options:
            setattr(self, opt, options[opt])

VideoOptions._fields = types.MappingProxyType(dict((f.name,f) for f in dataclasses.fields(VideoOptions)))

class MediaType(enum.Enum):
    COLOR = enum.auto()
    IMAGE = enum.auto()
    VIDEO = enum.auto()

class Dimension(tuple):
    @validators.validated_types(coerce_types=False)
    def __new__(cls, x: str|int, y: str|int):
        return super().__new__(cls, (int(x), int(y)))

    def width(self) -> int:
        return self[0]

    def height(self) -> int:
        return self[1]

    def __repr__(self) -> str:
        return f"{self[0]}x{self[1]}"

class VideoConverter:
    @validators.validated_types
    def __init__(self, source: str, dest: str, options: VideoOptions | None = None, **kwargs):
        self.options = options or VideoOptions()
        self.options.update(**kwargs)
        self.assfile = os.path.abspath(source)
        self.vidfile = os.path.abspath(dest)
        for x in ['audio_file', 'intro_media', 'outro_media', 'background_media']:
            if (val := getattr(self.options, x)):
                setattr(self.options, x, os.path.abspath(val))

    def __getattr__(self, attr):
        return getattr(self.options, attr)

    # Return whether a file or ffmpeg.probe dict is a video or image
    @validators.validated_types(coerce_types=False)
    @staticmethod
    def get_visual_type(file: str | dict) -> MediaType:
        if not isinstance(file, dict):
            file = ffmpeg.probe(file)
        visual_stream = next(x for x in file['streams'] if x['codec_type'] == 'video')
        # Seems like there should be a better way to do this, but ffprobe seems to do weird things
        # like consider jpeg to be a one-frame mjpeg
        if visual_stream.get('duration_ts', 1) > 1:
            return MediaType.VIDEO
        else:
            return MediaType.IMAGE


    def run(self):
        # TODO: handle exception
        song_length_str = ffmpeg.probe(self.options.audio_file)['format']['duration']
        song_length_ms = int(float(song_length_str) * 1000)
        output_options = {}
        base_assfile = os.path.basename(self.assfile)

        if self.options.background_media:
            # TODO: handle exception
            bginfo = ffmpeg.probe(self.options.background_media)
            visual_stream = next(x for x in bginfo['streams'] if x['codec_type'] == 'video')
            # TODO: scale background media option?
            bg_size = Dimension(visual_stream["width"],visual_stream["height"])
            background_type = self.get_visual_type(bginfo)
            if background_type == MediaType.VIDEO:
                if self.options.loop_bg:
                    # Repeat background video until audio is complete
                    background_video = ffmpeg.input(self.options.background_media, stream_loop=-1, t=song_length_str).video
                else:
                    bgv_length_ms = int(float(bginfo['format']['duration'] * 1000))
                    background_video = ffmpeg.input(self.options.background_media).video
                    # If the background video is shorter than the audio (and possibly subtitle), repeat the last frame
                    if bgv_length_ms < song_length_ms:
                        background_video = background_video.filter_(
                                "tpad",
                                stop_mode="clone",
                                stop_duration=str(song_length_ms - bgv_length_ms)+"ms"
                            )
                    # Continue video until background video completes
                    else:
                        song_length_ms = bgv_length_ms
            else: # MediaType.IMAGE
                background_video = ffmpeg.input(self.options.background_media, loop=1, framerate=60, t=song_length_str)
        else:
            background_type = MediaType.COLOR
            bg_size = Dimension(self.options.target_x, self.options.target_y)
            background_video = ffmpeg.input(f"color=color={self.options.background_color.lstrip('#')}:r=60:s={bg_size}", f="lavfi", t=song_length_str)

        del song_length_str
        ### Note: past this point, song_length_ms represents the confirmed output file duration rather than just the audio length

        to_concat = [None, None]
        concat_length = 0
        for x in ("intro", "outro"):
            media = getattr(self.options, f"{x}_media")
            if media:
            # TODO: alpha, sound?
                opts = {}
                if self.get_visual_type(media) == MediaType.IMAGE:
                    opts["loop"]=1
                    opts["framerate"]=60
                length = getattr(self.options, f"{x}_length")
                # TODO skip scale if matching?
                # TODO set x/y if mismatched aspect ratio?
                overlay = ffmpeg.input(media, t=f"{length}ms", **opts).filter_("scale", s=str(bg_size))
                if x == "outro" and not self.options.outro_concat:
                    overlay = overlay.filter_("tpad", start_duration=f"{song_length_ms - length}ms", color="0x000000@0")
                for y in ("In", "Out"):
                    curfade = getattr(self.options, f"{x}_fade{y}")
                    if curfade:
                        fade_settings = {}
                        if not getattr(self.options, f"{x}_concat") and (not getattr(self.options, f"{x}_black") or (x, y) == ("intro", "Out") or (x, y) == ("outro", "In")):

                            fade_settings["alpha"] = 1
                        if x == "intro" or self.options.outro_concat: # TODO: check logic
                            if y == "In":
                                fade_settings["st"] = 0
                            else:
                                fade_settings["st"] = (length - getattr(self.options, f"{x}_fadeOut")) / 1000 # According to manpage this has to be in seconds
                        else:
                            if y == "Out":
                                fade_settings["st"] = (song_length_ms - getattr(self.options, f"{x}_fadeOut")) / 1000
                            else:
                                fade_settings["st"] = (song_length_ms - length) / 1000
                        overlay = overlay.filter_("fade", t=y.lower(), d=(curfade / 1000), **fade_settings)

                if getattr(self.options, f"{x}_concat"):
                    to_concat[0 if x == "intro" else 1] = overlay
                    concat_length += advanced[f"{x}_length"]
                else:
                    background_video = background_video.overlay(overlay, eof_action=("pass" if x == "intro" else "repeat"))

        audio_stream = ffmpeg.input(self.options.audio_file).audio

        bg_ratio = fractions.Fraction(*bg_size)
        ass_ratio = self.options.aspect_ratio

        if bg_ratio > ass_ratio:
            # letterbox sides
            ass_size = Dimension(round(bg_size.height() * ass_ratio), bg_size.height())
            ass_move = {"x": round((bg_size.width() - ass_size.width())/2)}
        elif bg_ratio < ass_ratio:
            # letterbox top/bottom
            ass_size = Dimension(bg_size.width(), round(bg_size.width() / ass_ratio))
            ass_move = {"y": round((bg_size.height() - ass_size.height())/2)}
        else:
            ass_size = bg_size
            # ass_move = ""
            ass_move = {}

        if ass_move:
            filtered_video = background_video.overlay(
                ffmpeg_color(color="000000@0", r=60, s=str(ass_size))
                    .filter_("format", "rgba")
                    .filter_("ass", base_assfile, alpha=1),
                eof_action="pass",
                **ass_move
            )
        else:
            filtered_video = background_video.filter_("ass", base_assfile)

        if to_concat[0]:
            filtered_video = to_concat[0].concat(filtered_video)
            audio_stream = ffmpeg.input("anullsrc", f="lavfi", t=f"{self.options.intro_length}ms").audio.concat(audio_stream, v=0, a=1)
        if to_concat[1]:
            filtered_video = filtered_video.concat(to_concat[1])
            audio_stream = audio_stream.concat(ffmpeg.input("anullsrc", f="lavfi", t=f"{self.options.outro_length}ms").audio, v=0, a=1)

        if self.options.audio_codec != 'flac':
            output_options['audio_bitrate'] = f"{self.options.audio_bitrate}k"

        # Lossless handling
        if self.options.video_quality == 0:
            if self.options.video_codec == "libvpx-vp9":
                output_options["lossless"]=1
            elif self.options.video_codec == "libx265":
                output_options["x265-params"]="lossless=1"
            else:
                output_options["crf"]=0
        else:
            output_options["crf"]=self.options.video_quality

        if self.options.video_codec == "libvpx-vp9":
            output_options["video_bitrate"] = 0 # Required for the format to use CRF only
            output_options["row-mt"] = 1 # Speeds up encode for most multicore systems

        if self.options.media_container:
            output_options["f"] = self.options.media_container

        output_options.update({
            "c:a": self.options.audio_codec,
            "c:v": self.options.video_codec,
            **self.options.output_options
        })

        ffmpeg_options = ffmpeg.output(filtered_video, audio_stream, self.vidfile, **output_options).overwrite_output().get_args()
        assdir = os.path.dirname(self.assfile)
        print(f'cd "{assdir}"')
        # Only quote empty or suitably complicated arguments in the command
        print("ffmpeg" + " " + " ".join(x if re.fullmatch(r"[\w\-/:\.]+", x) else f'"{x}"' for x in ffmpeg_options))
        #q = QProcess(program="ffmpeg", arguments=ffmpeg_options, workingDirectory=os.path.dirname(assfile))
        subprocess_opts = {"args": ["ffmpeg"] + ffmpeg_options, "cwd": assdir}
        if self.options.preview:
            return subprocess_opts
        else:
            subprocess.run(subprocess_opts.pop("args"), **subprocess_opts)
