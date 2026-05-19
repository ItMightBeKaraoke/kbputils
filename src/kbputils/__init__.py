#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__version__ = '0.2.11'

__all__ = ['KBPFile', 'AssConverter', 'DoblonTxtConverter', 'LRCConverter', 'KBPAction', 'KBPActionType', 'KBPTimingTarget', 'KBPTimingAnchor', 'KBPActionParams']

from .kbp import *
from .doblontxt import *
from .lrc import *
from .converters import *

import ass
if not hasattr(ass.ScriptInfoSection, "add_comment"):
    raise NotImplementedError("This version of kbputils is not compatible with the standard 'ass' module. Please uninstall 'ass' and install 'ass_imbk'. If both are installed, uninstall both, then reinstall the latter.")

if ffmpeg_available:
    __all__.append('VideoConverter')
