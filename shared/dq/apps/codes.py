# (c) 2026 cc-Q. Sign-in codes, on a device with no clock.
#
# HOTP works with no clock at all and is the safe default. TOTP needs time, so it
# is enrolled by scanning otpauth:// QRs and resynced by scanning a QR holding the
# current unix time. When the clock is unset or stale, codes are shown greyed with
# an explicit warning rather than as numbers that might be wrong.
#
from dq.apps import DQApp, register_app
from dq import otp, clock

NAME = 'codes'
VISIBLE = 3                     # three codes on screen at once


# ------------------------------------------------------------- pure logic --

def rows(records, unix_time, limit=VISIBLE):
    """What the codes screen draws: (label, code_or_None, fraction_left).

    code is None when the record needs a clock and we have none -- the screen
    greys those rather than inventing digits.
    """
    out = []
    for rec in records[:limit]:
        try:
            code = otp.code_for(rec, unix_time)
        except Exception:
            code, frac = None, 0.0
        if code is None or rec.get('kind') == 'hotp' or unix_time is None:
            frac = 0.0
        else:
            period = int(rec.get('period', 30))
            frac = otp.seconds_left(unix_time, period) / float(period)
        out.append((otp.label(rec), _spaced(code), frac))
    return out


def _spaced(code):
    "418204 -> 418 204, easier to read off a screen and type"
    if not code:
        return None
    half = len(code) // 2
    return code if len(code) < 6 else '%s %s' % (code[:half], code[half:])


def needs_clock(records):
    return any(r.get('kind', 'totp') == 'totp' for r in records)


def bump_counter(records, rec):
    """HOTP counters must persist the moment a code is shown, not after it works.

    If the device loses power between showing and saving, the service has moved
    on and we have not -- so we write first and show second.
    """
    rec['counter'] = int(rec.get('counter', 0)) + 1
    return records


def parse_time_qr(text):
    """Accept what a resync QR plausibly holds: a bare unix time, or
    `time=...`/`t=...`, or an ISO-ish timestamp we can read digits out of."""
    text = (text or '').strip()
    if text.isdigit():
        return int(text)
    low = text.lower()
    for prefix in ('time=', 't=', 'unix=', 'cc-q:time='):
        if low.startswith(prefix):
            rest = text[len(prefix):].strip()
            if rest.isdigit():
                return int(rest)
    raise ValueError('not a time QR')


# -------------------------------------------------------------------- app --

@register_app
class Codes(DQApp):
    name = NAME
    title = 'codes'
    hotkey = 'c'

    def home_line(self):
        records, status = self.load_for_home()
        if status:
            return status
        if not records:
            return ('none enrolled', False)
        if needs_clock(records) and not clock.is_set():
            return ('%d, clock unset' % len(records), True)
        return ('%d enrolled' % len(records), False)

    async def start(self):
        "Opens on the codes themselves. Export and import are function keys."
        from dq import ui
        try:
            records = self.store().load()
        except Exception as exc:
            await ui.show_error('codes', exc)
            return
        await _screen(self, records)

    def enroll(self, records, uri):
        "returns the new record; raises ValueError on anything unparseable"
        rec = otp.parse_uri(uri)
        records.append(rec)
        return rec


async def _screen(app, records):
    from charcodes import KEY_F2, KEY_F3
    "the codes screen, including the greyed state when time is unknown"
    from glob import dis
    from dq import clock

    while True:
        now = clock.now()
        stale = clock.is_stale()
        usable = (now is not None) and not stale

        dis.clear()
        theme.header(dis, 'codes', clock.describe())
        if not records:
            theme.body(dis, 2, 'nothing enrolled yet', x=1, dark=True)
            theme.body(dis, 4, 'scan a QR to add one', x=1, dark=True)
        else:
            for n, (name, code, frac) in enumerate(rows(records, now if usable else None)):
                theme.body(dis, n * 2, name, x=1, dark=True)
                dis.text(-1, theme.BODY_TOP + (n * 2), code or '••• •••',
                         dark=not code)
                if code and frac:
                    dis.text(1, theme.BODY_TOP + (n * 2) + 1,
                             '█' * int(frac * 28), dark=True)
            if not usable and needs_clock(records):
                theme.body(dis, 6, 'Time is unknown after power off.', x=1)
                theme.body(dis, 7, 'Scan a time QR to fix.', x=1)
        theme.footer(dis, 'r resync  + enroll', 'F2 export  X back')
        dis.show()

        ch = await _key()
        if ch in BACK_KEYS:
            return
        if ch in ('r', KEY_QR, '+'):
            got = await ui.scan_text()
            if not got:
                continue
            try:
                if ch == '+' or got.startswith('otpauth://'):
                    app.enroll(records, got)
                else:
                    clock.set_time(parse_time_qr(got))
                app.store().save(records)
            except Exception as exc:
                await ui.show_error('codes', exc)
