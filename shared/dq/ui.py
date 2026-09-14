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


async def scan_text(prompt='Scan a QR'):
    "read a QR; apps use this rather than touching the scanner themselves"
    from ux_q1 import QRScannerInteraction
    return await QRScannerInteraction().scan_text(prompt)


async def menu_choice(title, options):
    """A short list of actions. Returns the chosen tag, or None on back.

    options is [(label, tag), ...] -- apps name their own actions rather than
    the framework guessing them.
    """
    from glob import dis
    idx = 0
    while True:
        dis.clear()
        theme.header(dis, title)
        for n, (label, _) in enumerate(options[:6]):
            dis.text(1, theme.BODY_TOP + 1 + n, theme.fit(label, theme.CHARS_W - 2),
                     invert=(n == idx))
        theme.footer(dis, 'OK choose', 'X back')
        dis.show()

        ch = await _key()
        if ch in BACK_KEYS:
            return None
        if ch == KEY_ENTER:
            return options[idx][1]
        if ch == KEY_UP:
            idx = (idx - 1) % len(options)
        elif ch == KEY_DOWN:
            idx = (idx + 1) % len(options)


async def collect_lines(title, prompt, done_when=None, limit=None):
    """Gather one or more lines (recovery shares, mostly), by QR or typing.

    done_when(lines) is tried after each line; when it stops raising we have
    everything, so the owner is never asked to count their own shares.
    """
    from ux_q1 import ux_input_text
    from ux import ux_show_story
    got = []
    while True:
        label = prompt % (len(got) + 1) if '%' in prompt else prompt
        line = await ux_input_text('', prompt=label, max_len=120, scan_ok=True)
        if line is None:
            return got if got and limit else None
        line = line.strip()
        if not line:
            continue
        got.append(line)

        if limit and len(got) >= limit:
            return got
        if done_when:
            try:
                done_when(got)
                return got
            except Exception as exc:
                await ux_show_story('%s\n\nAdd another, or press X to stop.' % exc,
                                    title=title)


async def import_text(title):
    "text in, by QR or keyboard"
    from ux_q1 import ux_input_text
    return await ux_input_text('', prompt=title, max_len=2000, scan_ok=True)


async def offer_export(title, blob, filename=None, qr_ok=False):
    "show it, then let the owner put it on a card or a QR"
    from ux import ux_show_story
    from glob import dis
    ch = await ux_show_story('%s\n\nPress 1 to write it to a card%s.'
                             % (blob, ', 2 for a QR' if qr_ok else ''),
                             title=title, escape='12')
    if ch == '1' and filename:
        from files import CardSlot
        with CardSlot() as card:
            path = card.get_sd_root() + '/' + filename
            with open(path, 'wt') as fd:
                fd.write(blob)
        await ux_show_story('Wrote %s' % filename, title=title)
    elif ch == '2' and qr_ok:
        from ux import show_qr_code
        await show_qr_code(blob, is_alnum=False)


async def pick_file(title, suffix=None, max_size=16 * 1024 * 1024):
    "choose a file off the card; returns a full path or None"
    from actions import file_picker
    got = await file_picker(suffix=suffix, max_size=max_size,
                            none_msg='No files on the card to %s.' % title)
    if not got:
        return None
    # file_picker hands back a path, or (path, size) depending on the caller
    return got[0] if isinstance(got, (tuple, list)) else got


def _wrap(txt, width):
    return [txt[i:i + width] for i in range(0, len(txt), width)] or ['']
