# (c) 2026 cc-Q. The screens every app shares, drawn on the 34x10 grid.
#
# Apps describe what they want shown; none of them draws the chrome itself, so
# the theme stays in one place and a new app gets it for free.
#
from dq import theme
from charcodes import (KEY_ENTER, KEY_CANCEL, KEY_UP, KEY_DOWN, KEY_DELETE,
                       KEY_QR, KEY_NFC, KEY_HOME)

BACK_KEYS = (KEY_CANCEL, KEY_DELETE, KEY_HOME)


async def _key(allowed=None, timeout_ms=None):
    from ux import ux_wait_keydown
    return await ux_wait_keydown(allowed, timeout_ms=timeout_ms)


async def show_error(title, exc):
    from ux import ux_show_story
    from dq.store import BadMAC
    if isinstance(exc, BadMAC):
        msg = ("This card's %s file does not match this device.\n\n"
               "It was written by another Coldcard, or it has been altered. "
               "Nothing was changed." % title)
    else:
        msg = '%s\n\n%s' % (title, exc)
    await ux_show_story(msg, title=title)


async def pick_from_list(title, records, line, match, footer='OK open   X back'):
    """Type-to-filter list. Returns the chosen record, or None on back.

    `line(rec)` gives (left, right); `match(records, query)` does the filtering,
    so each app decides what "matching" means for its own records.
    """
    from glob import dis
    query = ''
    idx = 0
    while True:
        shown = match(records, query)
        idx = max(0, min(idx, len(shown) - 1))

        dis.clear()
        theme.header(dis, title)
        theme.body(dis, 0, 'find: %s' % query)
        if not shown:
            theme.body(dis, 2, 'nothing matches', x=2, dark=True)
        for n, rec in enumerate(shown[:5]):
            left, right = line(rec)
            row = theme.pad(('> ' if n == idx else '  ') + left, right)
            dis.text(0, theme.BODY_TOP + 2 + n, row, invert=(n == idx))
        theme.footer(dis, '%d of %d' % (len(shown), len(records)), footer)
        dis.show()

        ch = await _key()
        if ch in BACK_KEYS and not query:
            return None
        elif ch in BACK_KEYS:
            query = query[:-1]
        elif ch == KEY_ENTER and shown:
            return shown[idx]
        elif ch == KEY_UP:
            idx -= 1
        elif ch == KEY_DOWN:
            idx += 1
        elif ch and ' ' <= ch <= '~':
            query += ch
            idx = 0


async def show_secret(title, right, subtitle, secret, note='', hide_after=20):
    """A secret on screen, with a countdown that resets on any keypress.

    The countdown is the alert colour because it is the one thing here with a
    deadline. QR on demand rather than always: it is the fastest way to leak a
    password to a room.
    """
    from glob import dis
    import utime
    from ux import show_qr_code

    deadline = utime.ticks_add(utime.ticks_ms(), hide_after * 1000)
    while True:
        left = utime.ticks_diff(deadline, utime.ticks_ms()) // 1000
        if left <= 0:
            return

        dis.clear()
        theme.header(dis, title, right)
        theme.body(dis, 1, subtitle, x=1, dark=True)
        for n, chunk in enumerate(_wrap(secret, theme.CHARS_W - 2)[:2]):
            theme.body(dis, 3 + n, chunk, x=1)
        theme.body(dis, 6, 'hides in %ds' % left, x=1)
        if note:
            dis.text(-1, theme.BODY_TOP + 6, note, dark=True)
        theme.footer(dis, 'QR show   n NFC', 'X back')
        dis.show()

        ch = await _key(timeout_ms=250)
        if ch is None:
            continue                        # tick the countdown
        if ch in BACK_KEYS:
            return
        if ch == KEY_QR:
            await show_qr_code(secret, is_alnum=False)
        elif ch == KEY_NFC:
            from glob import NFC
            if NFC:
                await NFC.share_text(secret)
        deadline = utime.ticks_add(utime.ticks_ms(), hide_after * 1000)


async def edit_text(title, value, lines=5):
    "full-screen editor; returns the new text, or None if the owner backed out"
    from ux_q1 import ux_input_text
    return await ux_input_text(value, prompt=title, max_len=2000,
                               confirm_exit=True, scan_ok=False)


async def ask_date(guess, why):
    """Confirm the date. Never assumed, because the Q cannot know it.

    Returns YYYY-MM-DD, or None if they decline -- in which case the caller
    does not write anything.
    """
    from ux import ux_show_story
    from ux_q1 import ux_input_text
    from dq.session import _date_check

    ch = await ux_show_story(
        "What is today's date?\n\nBest guess is %s, from the %s.\n\n"
        "This device has no clock, so it cannot know. Press OK to accept, "
        "or 2 to type a different date." % (guess, why),
        title='date', escape='2')
    if ch == 'x':
        return None
    if ch != '2':
        return guess

    while True:
        got = await ux_input_text(guess, prompt='YYYY-MM-DD', max_len=10)
        if got is None:
            return None
        try:
            return _date_check(got.strip())
        except Exception:
            await ux_show_story('Want YYYY-MM-DD, like 2026-09-14.', title='date')


async def show_codes(app, records):
    "the codes screen, including the greyed state when time is unknown"
    from glob import dis
    from dq import clock
    from dq.apps.codes import rows, needs_clock, parse_time_qr

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
        theme.footer(dis, 'r resync', '+ enroll   X back')
        dis.show()

        ch = await _key()
        if ch in BACK_KEYS:
            return
        if ch in ('r', KEY_QR, '+'):
            got = await _scan()
            if not got:
                continue
            try:
                if ch == '+' or got.startswith('otpauth://'):
                    app.enroll(records, got)
                else:
                    clock.set_time(parse_time_qr(got))
                app.store().save(records)
            except Exception as exc:
                await show_error('codes', exc)


async def _scan():
    from ux_q1 import QRScannerInteraction
    return await QRScannerInteraction().scan_text('Scan a QR')


def _wrap(txt, width):
    return [txt[i:i + width] for i in range(0, len(txt), width)] or ['']
