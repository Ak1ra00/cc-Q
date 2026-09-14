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
        try:
            records = self.store().load()
        except Exception:
            return ('unreadable', True)
        if not records:
            return ('none enrolled', False)
        if needs_clock(records) and not clock.is_set():
            return ('%d, clock unset' % len(records), True)
        return ('%d enrolled' % len(records), False)

    async def start(self):
        from dq.ui import show_codes, show_error
        try:
            records = self.store().load()
        except Exception as exc:
            await show_error('codes', exc)
            return
        await show_codes(self, records)

    def enroll(self, records, uri):
        "returns the new record; raises ValueError on anything unparseable"
        rec = otp.parse_uri(uri)
        records.append(rec)
        return rec
