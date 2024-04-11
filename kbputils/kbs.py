import os

# Metaclass to allow e.g. KBSSettings.offset instead of needing
# KBSSettings().offset for the first invocation

class ClassGetattr(type):
    def __getattr__(cls, attr):
        return cls.__getattr__(attr)

# Sort of a hacky singleton-like thing
# It only reads the KBS config file if one of the settings is requested from
# it, and fills in all settings.

class KBSSettings(metaclass=ClassGetattr):
    SETTING_NAMES = { 
        "offset": "setoffset",
        "removaltype": "setremovalfx",
    }

    _settings=None

    @staticmethod
    def _fetch_settings():
        settings = {
            "setoffset": 0,      # Offset to shift entire tracks
            "setremovalfx": 3,   # Default removal style (3 is line by line)
        }
        if os.environ.get('APPDATA') and os.path.exists(p := os.path.join(os.environ['APPDATA'], 'Karaoke Builder', 'data_studio.ini')):
            try:
                with open(p, 'r') as f:
                    for line in f:
                        field, val = line.split(maxsplit=1)
                        if field in settings:
                            settings[field] = int(val)
            except OSError:
                pass
        return settings

    @classmethod
    def __getattr__(cls, attr):
        if not cls._settings:
            cls._settings = cls._fetch_settings()
            for x in cls.SETTING_NAMES:
                setattr(cls, x, cls._settings[cls.SETTING_NAMES[x]])
        return getattr(cls, attr)
