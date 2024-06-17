import sys

# Probably not the final strategy, but start with some hardcoded spacing values
font_info = {
    'Arial': {'regular': [16, 17, 18, 19, 22, 23, 24, 26, 27], 'bold': [16, 18, 19, 19, 22, 24, 24, 27, 29]},
    'Tahoma': [16, 18, 19, 21, 23, 24],
    'Kozuka Gothic Pro H': [19, 22, 23, 24, 27, 29],
    'Helvetica LT std': [15, 18, 19, 20, 23, 24],
    'Open Sans Semibold': [19, 22, 23, 24, 27, 28],
    'Franklin Gothic Book': [17, 20, 21, 21, 24, 25],
    'Franklin Gothic Demi': [17, 20, 21, 21, 24, 25],
    'Franklin Gothic Medium': [17, 20, 21, 21, 24, 25],
    'MS Gothic': [13, 15, 16, 17, 19, 20, 21, 23, 24],
    'Gadugi': {'regular': [16, 18, 19, 20, 22, 24, 25], 'bold': [16, 18, 19, 20, 21, 24, 25]},
    'Verdana': [16, 18, 18, 20, 23, 25, 25]
}

# TODO: object with spacing property
#def spacing(font, size, bold=False):
def spacing(style):
    global __warned__
    font = style.fontname
    size = style.fontsize
    bold = 'B' in style.fontstyle
    spacing = None
    if font in font_info:
        if type(cur := font_info[font]) is dict:
            cur = cur['bold' if bold else 'regular']
        if 0 <= size - 10 < len(cur):
            spacing = cur[size - 10]
    if spacing is None:
        raise KeyError(f'Font "{font}", size {size}{" (bold)" if bold else ""} not known. Disable the experimental spacing feature to process the file.')
    return spacing
