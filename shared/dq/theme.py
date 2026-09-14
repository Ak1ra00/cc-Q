# (c) 2026 cc-Q. Green phosphor treatment, applied globally rather than per screen.
#
# The Q blits every glyph through one of three 16-entry palettes that live in
# font_iosevka.TEXT_PALETTES. lcd_display imports that list by reference, so
# replacing its *contents* recolours every screen in the firmware -- upstream's
# menus included -- without patching a single upstream file.
#
try:
    from ustruct import pack
except ImportError:
    from struct import pack

# SPEC.md palette
BG       = (0x03, 0x08, 0x05)
PHOSPHOR = (0x4d, 0xff, 0x9e)   # primary text, active elements
DIM      = (0x35, 0xd4, 0x7f)   # body text
FAINT    = (0x1f, 0x8f, 0x5c)   # labels, secondary info
ALERT    = (0xff, 0xb3, 0x47)   # time pressure, attention, unsaved state

# the 16 antialiasing levels the font data is quantised to (misc/q1font/render.py)
SHADES = (0, 16, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 192, 223, 239, 255)

# palette slots, indexed by lcd_display's attribute flags
PAL_NORMAL, PAL_INVERT, PAL_DARK = 0, 1, 2


def rgb565(col, amt):
    # colour at intensity amt (0..255) as RGB565, same maths as the font generator
    amt /= 255.0
    r = int((col[0] / 255.0) * amt * 0x1f)
    g = int((col[1] / 255.0) * amt * 0x3f)
    b = int((col[2] / 255.0) * amt * 0x1f)
    return (r << 11) | (g << 5) | b


def make_palette(col, darken=1.0, invert=False):
    # 16 RGB565 entries, big-endian, ramping black -> col
    shades = [255 - s for s in SHADES] if invert else list(SHADES)
    return pack('>16H', *[rgb565(col, s * darken) for s in shades])


def palettes(col=PHOSPHOR):
    "the three palettes lcd_display expects, in its own order"
    return [make_palette(col),
            make_palette(col, invert=True),
            make_palette(col, darken=0.66)]


def apply(col=PHOSPHOR):
    # Recolour the whole UI. Mutates in place: lcd_display did
    # `from font_iosevka import TEXT_PALETTES`, so it holds this same list object.
    from font_iosevka import TEXT_PALETTES
    for i, p in enumerate(palettes(col)):
        TEXT_PALETTES[i] = p
    return TEXT_PALETTES


# ---------------------------------------------------------------- drawing --
#
# The panel is a 34x10 character grid (CHARS_W/CHARS_H in lcd_display), cells
# 9x22px. Header and footer take one row each, leaving eight for content.
#
CHARS_W, CHARS_H = 34, 10
BODY_TOP, BODY_ROWS = 1, 8


def fit(msg, width=CHARS_W):
    "truncate with an ellipsis rather than wrapping, per SPEC"
    if len(msg) <= width:
        return msg
    return msg[:width - 1] + '⋯'


def pad(left, right, width=CHARS_W):
    "left text, right text, one line, right-aligned against the last column"
    room = width - len(right) - 1
    if room < 1:
        return fit(right, width)
    return '%s %s' % (fit(left, room).ljust(room), right)


def header(dis, title, right=None):
    # reverse video: the cell buffer only offers black or full-phosphor
    # backgrounds, so a bar is inverted rather than the 13% tint in SPEC.md.
    dis.text(0, 0, pad(title, right or '').ljust(CHARS_W), invert=True)


def footer(dis, keys, right=None):
    dis.text(0, -1, pad(keys, right or '').ljust(CHARS_W), invert=True)


def body(dis, row, msg, x=0, dark=False):
    "draw inside the content area; row 0 is the first line under the header"
    if 0 <= row < BODY_ROWS:
        dis.text(x, BODY_TOP + row, fit(msg, CHARS_W - x), dark=dark)
