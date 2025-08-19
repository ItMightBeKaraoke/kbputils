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

__all__ = ['Ratio', 'VideoOptions', 'MediaType', 'Dimension', 'VideoConverter']

class Ratio(fractions.Fraction):
    def __new__(cls, *args, **kwargs):
        if isinstance(args[0], str) and ':' in args[0]:
            args = (args[0].replace(':', '/'), *args[1:])
        return super().__new__(cls, *args, **kwargs)
    def __str__(self):
        return super().__str__().replace('/', ':')
    def __format__(self, spec):
        return super().__format__(spec).replace('/', ':')

@validators.validated_instantiation(replace="__init__")
@dataclasses.dataclass
class VideoOptions:
    preview: bool = dataclasses.field(default=False, metadata={"doc": "If set, do not run ffmpeg, only output the command that would be run"})
    audio_file: str | None = dataclasses.field(default=None, metadata={"doc": "Audio track to use with video", "existing_file": True})
    aspect_ratio: Ratio = dataclasses.field(default=Ratio(300,216), metadata={"doc": "Aspect ratio of rendered subtitle. This will be letterboxed if not equal to the aspect ratio of the output video"})
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
    intro_sound: bool = dataclasses.field(default=False, metadata={"doc": "Preserve audio in the intro (if video). Note that when using without the intro_concat option, this will mix without normalization, and may cause clipping"})
    outro_sound: bool = dataclasses.field(default=False, metadata={"doc": "Preserve audio in the outro (if video). Note that when using without the outro_concat option, this will mix without normalization, and may cause clipping"})
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

class MediaType(enum.Flag):
    COLOR = enum.auto()
    IMAGE = enum.auto()
    VIDEO = enum.auto()
    AUDIO = enum.auto()

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

    # Return what kind of streams are contained in the file or existing ffprobe dict
    @staticmethod
    @validators.validated_types(coerce_types=False)
    def get_stream_types(file: str | dict) -> MediaType:
        result = MediaType(0)
        if not isinstance(file, dict):
            file = ffmpeg.probe(file)
        if any(x['codec_type']=='audio' for x in file['streams']):
            result |= MediaType.AUDIO 
        if any(x['codec_type']=='video' for x in file['streams']):
            # Is it really video or an image? Let's see...
            # Yes, this is ridiculous, but
            # 1) It's nearly impossible to determine this from ffprobe output and requires
            #    looking at multiple fields which can vary between formats
            # 2) I don't *really* care if it's an image or video, just whether I need these
            #    two options, so may as well test them
            testcmd = ffmpeg.output(
                    ffmpeg.input(file['format']['filename'], framerate=60, loop=1, t=0.01),
                    '-', f='null', loglevel='quiet'
                    ).get_args()
            if subprocess.run(['ffmpeg'] + testcmd).returncode == 0:
                result |= MediaType.IMAGE
            else:
                result |= MediaType.VIDEO
        return result

    def run(self):
        # TODO: handle exception
        if self.options.audio_file:
            song_length_str = ffmpeg.probe(self.options.audio_file)['format']['duration']
        else:
            # If there's no audio file provided, just take the largest timestamp from the subtitle and add a few seconds
            # Yes the 3 seconds is hardcoded, but who's making a karaoke video without the audio anyway?!
            import ass
            with open(self.assfile) as f:
                song_length_str = str(max(x.end for x in ass.parse_file(f).events).total_seconds() + 3)
            print("No audio file provided, estimating length from .ass file")
        song_length_ms = int(float(song_length_str) * 1000)
        output_options = {}
        base_assfile = os.path.basename(self.assfile)

        if self.options.background_media:
            # TODO: handle exception
            bginfo = ffmpeg.probe(self.options.background_media)
            visual_stream = next(x for x in bginfo['streams'] if x['codec_type'] == 'video')
            # TODO: scale background media option?
            bg_size = Dimension(visual_stream["width"],visual_stream["height"])
            background_type = self.get_stream_types(bginfo)
            if MediaType.VIDEO in background_type:
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

        audio_stream = ffmpeg.input(self.options.audio_file).audio if self.options.audio_file else None

        to_concat = [None, None]
        concat_length = 0
        for x in ("intro", "outro"):
            media = getattr(self.options, f"{x}_media")
            if media:
            # TODO: alpha, sound?
                opts = {}
                if MediaType.IMAGE in (media_type := self.get_stream_types(media)):
                    opts["loop"]=1
                    opts["framerate"]=60
                if MediaType.AUDIO not in media_type:
                    setattr(self.options, f"{x}_sound", False)
                length = getattr(self.options, f"{x}_length")
                # TODO skip scale if matching?
                # TODO set x/y if mismatched aspect ratio?
                overlay = ffmpeg.input(media, t=f"{length}ms", **opts).filter_("scale", s=str(bg_size))
                if x == "outro" and not self.options.outro_concat:
                    # Not sure why the tpad filter (commented below) doesn't work - it seem to pad the wrong duration
                    #overlay = overlay.filter_("tpad", start_duration=f"{song_length_ms - length}ms", color="0x000000@0")
                    padding = ffmpeg_color(color="000000@0", r=60, s=str(bg_size), d=f"{song_length_ms - length}ms")
                    overlay = padding.concat(overlay)
                for y in ("In", "Out"):
                    curfade = getattr(self.options, f"{x}_fade{y}")
                    if curfade:
                        fade_settings = {}
                        if not getattr(self.options, f"{x}_concat") and (not getattr(self.options, f"{x}_fade_black") or (x, y) == ("intro", "Out") or (x, y) == ("outro", "In")):

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
                    concat_length += length
                else:
                    background_video = background_video.overlay(overlay, eof_action=("pass" if x == "intro" else "repeat"))
                    if getattr(self.options, f"{x}_sound"):
                        to_mix = ffmpeg.input(media, t=f"{length}ms").audio
                        if x == "outro":
                            to_mix = ffmpeg.input("anullsrc", f="lavfi", t=f"{song_length_ms - length}ms").concat(to_mix, v=0, a=1)

                        audio_stream = audio_stream and ffmpeg.filter_([audio_stream, to_mix], "amix", normalize=0)

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
            prepend_audio = ffmpeg.input(self.options.intro_media, t=f"{self.options.intro_length}ms").audio if self.options.intro_sound else ffmpeg.input("anullsrc", f="lavfi", t=f"{self.options.intro_length}ms").audio
            audio_stream = audio_stream and prepend_audio.concat(audio_stream, v=0, a=1)
        if to_concat[1]:
            filtered_video = filtered_video.concat(to_concat[1])
            append_audio = ffmpeg.input(self.options.outro_media, t=f"{self.options.outro_length}ms").audio if self.options.outro_sound else ffmpeg.input("anullsrc", f="lavfi", t=f"{self.options.outro_length}ms").audio
            audio_stream = audio_stream and audio_stream.concat(append_audio, v=0, a=1)

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

        ffmpeg_options = ffmpeg.output(filtered_video, *([audio_stream] if audio_stream else []), self.vidfile, **output_options).overwrite_output().get_args()
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
