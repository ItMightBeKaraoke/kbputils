from .kbp2ass import *
from .lyrics2kbp import *

try:
    import ffmpeg
    del ffmpeg
    ffmpeg_available = True
except:
    ffmpeg_available = False
if ffmpeg_available:
    from .ass2video import *
