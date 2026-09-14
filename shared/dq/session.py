# (c) 2026 cc-Q. What day is it?
#
# Nothing on this device knows. The owner is asked once per session -- on the
# first write that needs a date -- and the answer is held in RAM only, exactly
# like the clock, because it is just as unknowable after a power cycle.
#
_today = None


def today_or_none():
    "the confirmed date, or None if nobody has said yet"
    global _today
    if _today:
        return _today
    from dq import clock
    now = clock.now()
    if now is not None:
        _today = _date_from_unix(now)
    return _today


def set_today(date):
    global _today
    _date_check(date)
    _today = date
    return date


def forget():
    global _today
    _today = None


def suggest():
    """Best guess to put in front of the owner -- never used without confirming.

    Order: a set clock, then the persisted lower bound (which is only ever
    'not earlier than'), then the firmware build date as a last resort.
    """
    from dq import clock
    now = clock.now()
    if now is not None:
        return _date_from_unix(now), 'clock'
    floor = clock.floor()
    if floor:
        return _date_from_unix(floor), 'last known'
    return _build_date(), 'build date'


async def ask_today():
    "confirm the date with the owner, once per session. None if they back out."
    got = today_or_none()
    if got:
        return got
    from dq.ui import ask_date
    guess, why = suggest()
    picked = await ask_date(guess, why)
    return set_today(picked) if picked else None


def _date_check(date):
    from dq.dates import ordinal
    ordinal(date)                       # raises on anything malformed
    if len(date) != 10 or date[4] != '-' or date[7] != '-':
        raise ValueError('want YYYY-MM-DD')
    return date


def _date_from_unix(secs):
    from dq.dates import from_ordinal
    return from_ordinal(int(secs) // 86400)


def _build_date():
    try:
        import version
        return version.build_date
    except Exception:
        return '2026-01-01'
