#!/usr/bin/env python3
#
# Render cc-Q screen mockups as PNGs, using the Q's own font data and panel
# geometry. Output is pixel-exact: same 9x22 cells, same 4-bit antialiased
# glyphs the firmware blits, same 34x10 grid.
#
# Usage:  python3 misc/dq-screens/render.py [outdir]
#
import sys, os, zlib, struct, types, collections

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.normpath(os.path.join(HERE, '..', '..'))

# --- load the device font (MicroPython source, so shim the imports) ---------
_m = types.ModuleType('ucollections'); _m.namedtuple = collections.namedtuple
sys.modules['ucollections'] = _m
_ns = {}
exec(open(os.path.join(TOP, 'shared', 'font_iosevka.py')).read().replace('const(', '('), _ns)
GLYPHS = _ns['FontIosevka']._data

# --- panel geometry, from shared/lcd_display.py ----------------------------
WIDTH, HEIGHT = 320, 240
CELL_W, CELL_H = 9, 22
CHARS_W, CHARS_H = 34, 10
LEFT_MARGIN, TOP_MARGIN = 7, 15

# --- cc-Q theme, from SPEC.md ----------------------------------------------
BG       = (0x03, 0x08, 0x05)
PHOSPHOR = (0x4d, 0xff, 0x9e)
DIM      = (0x35, 0xd4, 0x7f)
FAINT    = (0x1f, 0x8f, 0x5c)
ALERT    = (0xff, 0xb3, 0x47)
BAR_A    = 0.13     # header/footer tint
SEL_A    = 0.18     # selected row


class Panel:
    def __init__(self):
        self.px = [[BG] * WIDTH for _ in range(HEIGHT)]

    def rect(self, x, y, w, h, col, alpha=1.0):
        for yy in range(max(0, y), min(HEIGHT, y + h)):
            row = self.px[yy]
            for xx in range(max(0, x), min(WIDTH, x + w)):
                row[xx] = blend(row[xx], col, alpha)

    def bar(self, r, alpha=BAR_A, col=PHOSPHOR):
        "full-width tinted row (header / footer)"
        self.rect(0, TOP_MARGIN + r * CELL_H, WIDTH, CELL_H, col, alpha)

    def sel(self, r, alpha=SEL_A, col=PHOSPHOR):
        "selected row highlight, content width only"
        self.rect(LEFT_MARGIN, TOP_MARGIN + r * CELL_H, CHARS_W * CELL_W, CELL_H, col, alpha)

    def text(self, r, c, s, col=DIM):
        "draw at cell (col c, row r); returns the next free column"
        x = LEFT_MARGIN + c * CELL_W
        y = TOP_MARGIN + r * CELL_H
        for ch in s:
            bits = GLYPHS.get(ch)
            if bits is None:
                raise SystemExit("glyph not on device: %r (%s)" % (ch, hex(ord(ch))))
            w = len(bits) * 2 // CELL_H
            self.blit(x, y, w, bits, col)
            x += w
            c += w // CELL_W
        return c

    def right(self, r, s, col=DIM):
        "right-align s against the last content column"
        w = sum(len(GLYPHS[ch]) * 2 // CELL_H // CELL_W for ch in s)
        return self.text(r, CHARS_W - w, s, col)

    def blit(self, x0, y0, w, bits, col):
        for i in range(w * CELL_H):
            b = bits[i >> 1]
            v = (b >> 4) if (i & 1) == 0 else (b & 0x0f)
            if not v:
                continue
            x, y = x0 + (i % w), y0 + (i // w)
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                self.px[y][x] = blend(self.px[y][x], col, v / 15.0)

    def png(self, path, scale=2):
        raw = bytearray()
        for row in self.px:
            for _ in range(scale):
                raw.append(0)
                for p in row:
                    raw.extend(bytes(p) * scale)
        w, h = WIDTH * scale, HEIGHT * scale

        def chunk(tag, data):
            c = struct.pack('>I', len(data)) + tag + data
            return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

        out = (b'\x89PNG\r\n\x1a\n'
               + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
               + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
               + chunk(b'IEND', b''))
        open(path, 'wb').write(out)
        return path


def blend(under, col, a):
    if a >= 1.0:
        return col
    return tuple(int(round(u + (c - u) * a)) for u, c in zip(under, col))


def meter(frac, width=26):
    "countdown / progress bar out of block glyphs the device actually has"
    n = int(round(frac * width))
    return '█' * n + '░' * (width - n)


# ---------------------------------------------------------------- screens --

def s_warning():
    "upstream's unofficial-firmware screen: not ours, not themed"
    p = Panel()
    p.text(1, 2, '! ! !  UNOFFICIAL FIRMWARE', ALERT)
    p.text(3, 2, 'This firmware is not from', (0xc8, 0xc8, 0xc8))
    p.text(4, 2, 'Coinkite. It could steal your', (0xc8, 0xc8, 0xc8))
    p.text(5, 2, 'funds. Genuine light is RED.', (0xc8, 0xc8, 0xc8))
    p.text(7, 2, 'Hold down for 5 seconds', (0x80, 0x80, 0x80))
    p.text(8, 2, meter(0.45, 26), (0xc8, 0xc8, 0xc8))
    return p


def s_home():
    p = Panel()
    p.bar(0); p.bar(9)
    p.text(0, 0, 'cc-Q', PHOSPHOR); p.right(0, '87%', FAINT)
    p.text(2, 2, 'SUN 14 SEP 2026', PHOSPHOR)
    p.text(4, 2, 'v  vault', PHOSPHOR);   p.right(4, '42 entries', FAINT)
    p.text(5, 2, 'c  codes', PHOSPHOR);   p.right(5, '3 enrolled', FAINT)
    p.text(6, 2, 'j  journal', PHOSPHOR); p.right(6, 'not written', ALERT)
    p.text(8, 2, 'card A ok  •  B mirrored', FAINT)
    p.text(9, 0, 'v vault   c codes   j journal', DIM)
    return p


def s_vault_find():
    p = Panel()
    p.bar(0); p.bar(9)
    p.text(0, 0, 'vault', PHOSPHOR); p.right(0, 'find', FAINT)
    c = p.text(2, 2, 'find: ', FAINT); c = p.text(2, c, 'proton', PHOSPHOR)
    p.rect(LEFT_MARGIN + c * CELL_W, TOP_MARGIN + 2 * CELL_H + 3, CELL_W, CELL_H - 6, PHOSPHOR)
    p.sel(4)
    p.text(4, 1, '▶ protonmail', PHOSPHOR); p.right(4, '14', PHOSPHOR)
    p.text(5, 3, 'proton vpn', DIM);             p.right(5, '27', FAINT)
    p.text(6, 3, 'protonmail work', DIM);        p.right(6, '31', FAINT)
    p.text(9, 0, '3 of 42', FAINT); p.right(9, 'OK open   X back', FAINT)
    return p


def s_vault_detail():
    p = Panel()
    p.bar(0); p.bar(9)
    p.text(0, 0, 'protonmail', PHOSPHOR); p.right(0, '#14', FAINT)
    p.text(2, 2, 'akira@protonmail.com', DIM)
    p.text(4, 2, '4Kj9-wQ2m-7Fv3', PHOSPHOR)
    p.text(5, 2, '-bL8xR', PHOSPHOR)
    p.text(7, 2, 'hides in 12s', ALERT); p.right(7, 'stored', FAINT)
    p.text(9, 0, 'n NFC push', FAINT); p.right(9, 'X back', FAINT)
    qr(p, 232, 92, 3)
    return p


def s_journal():
    p = Panel()
    p.bar(0); p.bar(9)
    p.text(0, 0, 'journal  14 sep', PHOSPHOR); p.right(0, '◉', ALERT)
    for i, line in enumerate([
            'Ran the M0 build twice today.',
            'The toolchain reproduces byte',
            'for byte now, so every later',
            'build has something honest to',
            'be diffed against.']):
        c = p.text(2 + i, 0, line, DIM)
    p.rect(LEFT_MARGIN + c * CELL_W, TOP_MARGIN + 6 * CELL_H + 3, CELL_W, CELL_H - 6, PHOSPHOR)
    p.text(8, 0, '78 words', FAINT); p.right(8, 'unsaved', ALERT)
    p.text(9, 0, '^S save', FAINT); p.right(9, '^W week   X back', FAINT)
    return p


def s_week():
    p = Panel()
    p.bar(0); p.bar(9)
    p.text(0, 0, 'journal  week', PHOSPHOR); p.right(0, '21 days', FAINT)
    bars = [(30, 'f'), (58, 'f'), (22, 'f'), (66, 'f'), (0, 'o'), (0, 'o'), (40, 't')]
    base_y, x = 150, 26
    for h, kind in bars:
        if kind == 'o':
            p.rect(x, base_y - 8, 22, 8, FAINT, 1.0)
            p.rect(x + 1, base_y - 7, 20, 6, BG, 1.0)
        else:
            p.rect(x, base_y - h, 22, h, PHOSPHOR if kind == 't' else DIM)
        x += 36
    p.text(7, 1, 'm    t    w    t    f    s', FAINT)
    p.text(7, 32, 's', PHOSPHOR)
    p.text(8, 1, 'longest run 4 days', FAINT)
    p.text(9, 0, 'X back', FAINT)
    return p


def s_codes():
    p = Panel()
    p.bar(0); p.bar(9)
    p.text(0, 0, 'codes', PHOSPHOR); p.right(0, 'set 2h ago', FAINT)
    rows = [('protonmail', '418 204', 0.70), ('github', '902 771', 0.23),
            ('fastmail', '330 145', 0.88)]
    for i, (name, code, frac) in enumerate(rows):
        r = 2 + i * 2
        p.text(r, 1, name, FAINT); p.right(r, code, PHOSPHOR)
        # countdown: a thin filled bar, drawn with fill_rect rather than blocks
        bx, by, bw = LEFT_MARGIN + CELL_W, TOP_MARGIN + (r + 1) * CELL_H + 8, 31 * CELL_W
        p.rect(bx, by, bw, 5, PHOSPHOR, 0.18)
        p.rect(bx, by, int(bw * frac), 5, DIM if frac > 0.3 else ALERT)
    p.text(9, 0, 'r resync', FAINT); p.right(9, '+ enroll   X back', FAINT)
    return p


def s_codes_stale():
    p = Panel()
    p.bar(0); p.bar(9)
    p.text(0, 0, 'codes', PHOSPHOR); p.right(0, 'clock not set', ALERT)
    p.text(2, 1, 'protonmail', FAINT); p.right(2, '••• •••', FAINT)
    p.text(4, 1, 'github', FAINT);     p.right(4, '••• •••', FAINT)
    p.text(6, 1, 'Time is unknown after power', ALERT)
    p.text(7, 1, 'off. Scan a time QR to fix.', ALERT)
    p.text(9, 0, 'r resync', PHOSPHOR); p.right(9, 'h HOTP   X back', FAINT)
    return p


def s_first_run():
    p = Panel()
    p.bar(0); p.bar(9)
    p.text(0, 0, 'first run', PHOSPHOR)
    p.text(2, 1, 'A device key was made from', DIM)
    p.text(3, 1, 'the hardware TRNG. It lives', DIM)
    p.text(4, 1, 'behind your PIN.', DIM)
    p.text(6, 1, 'If this Q is wiped, vault,', ALERT)
    p.text(7, 1, 'journal and codes go too,', ALERT)
    p.text(8, 1, 'unless you exported them.', ALERT)
    p.text(9, 0, 'OK understood', PHOSPHOR)
    return p


def qr(p, x0, y0, s):
    "stand-in QR field: real finder squares, deterministic fill. Not scannable."
    N, seed = 21, 7
    def nxt():
        nonlocal seed
        seed = (seed * 1103515245 + 12345) & 0x7fffffff
        return (seed >> 16) & 1
    def finder(fx, fy, i, j):
        dx, dy = i - fx, j - fy
        if dx < 0 or dy < 0 or dx > 6 or dy > 6:
            return None
        return 0 if max(abs(dx - 3), abs(dy - 3)) == 1 else 1
    for j in range(N):
        for i in range(N):
            v = finder(0, 0, i, j)
            if v is None: v = finder(N - 7, 0, i, j)
            if v is None: v = finder(0, N - 7, i, j)
            if v is None: v = nxt()
            if v:
                p.rect(x0 + i * s, y0 + j * s, s, s, PHOSPHOR)


SCREENS = [
    ('warning',     s_warning),
    ('boot-home',   s_home),
    ('vault-find',  s_vault_find),
    ('vault-entry', s_vault_detail),
    ('journal',     s_journal),
    ('journal-week', s_week),
    ('codes',       s_codes),
    ('codes-noclock', s_codes_stale),
    ('first-run',   s_first_run),
]

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TOP, 'docs', 'img')
    os.makedirs(out, exist_ok=True)
    for name, fn in SCREENS:
        path = fn().png(os.path.join(out, 'screen-%s.png' % name))
        print('%-34s %6d bytes' % (os.path.relpath(path, TOP), os.path.getsize(path)))
