import os
import sys


def _fetch_offset():
    if os.environ.get('APPDATA') and os.path.exists(p := os.path.join(os.environ['APPDATA'], 'Karaoke Builder', 'data_studio.ini')):
        try:
            with open(p, 'r') as f:
                for line in f:
                    field, val = line.split(maxsplit=1)
                    if field == "setoffset":
                        return int(val)
        except OSError:
            pass
    return 0

# Lazy-load the offset attribute so the file is only read if needed

def __getattr__(attr):
    if attr == "offset":
        setattr(sys.modules[__name__], attr, _fetch_offset())
        return getattr(sys.modules[__name__], attr)
    else:
        raise AttributeError(f"Module {__name__!r} has no attribute {attr!r}")
