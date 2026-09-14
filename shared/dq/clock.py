# (c) 2026 cc-Q. Time, on a device that has none.
#
# The Q has no RTC, no backup cell and no 32.768 kHz crystal (SPEC.md, Findings),
# so wall-clock time is unknown at every boot. The owner sets it by scanning a QR,
# and we hold (unix_time, ticks_at_that_moment) in RAM only. utime.ticks_ms counts
# from boot, so the pair dies with the power and time is unset again next time.
#
# The last known time is persisted, but only ever as a LOWER BOUND: it says "not
# earlier than this", which is enough to spot a stale sync and never enough to
# present as the current time.
#
try:
    import utime
except ImportError:                     # CPython, for tests
    import time as _time, types
    utime = types.ModuleType('utime')
    utime.ticks_ms = lambda: int(_time.monotonic() * 1000)
    utime.ticks_diff = lambda a, b: a - b

SETTING_FLOOR = 'dq_tfloor'             # last known unix time, a lower bound
STALE_AFTER = 12 * 3600                 # a sync older than this is not trusted

_sync = None                            # (unix_seconds, ticks_ms) or None


def set_time(unix_seconds, _ticks=None):
    "owner scanned a time QR. Returns the time we adopted."
    unix_seconds = int(unix_seconds)
    if unix_seconds < 1_600_000_000:            # Sept 2020: older than the product
        raise ValueError('implausible time')

    global _sync
    _sync = (unix_seconds, utime.ticks_ms() if _ticks is None else _ticks)

    try:
        from glob import settings
        if unix_seconds > (settings.get(SETTING_FLOOR) or 0):
            settings.put(SETTING_FLOOR, unix_seconds)
            settings.save()
    except ImportError:
        pass
    return unix_seconds


def now(_ticks=None):
    "current unix time, or None if nobody has told us. None is normal."
    if _sync is None:
        return None
    base, at = _sync
    ticks = utime.ticks_ms() if _ticks is None else _ticks
    return base + (utime.ticks_diff(ticks, at) // 1000)


def is_set():
    return _sync is not None


def age(_ticks=None):
    "seconds since the clock was set, or None"
    if _sync is None:
        return None
    _, at = _sync
    ticks = utime.ticks_ms() if _ticks is None else _ticks
    return utime.ticks_diff(ticks, at) // 1000


def is_stale(_ticks=None):
    a = age(_ticks)
    return True if a is None else (a > STALE_AFTER)


def floor():
    "the lower bound: time is not earlier than this. Never a current time."
    try:
        from glob import settings
        return settings.get(SETTING_FLOOR) or None
    except ImportError:
        return None


def forget():
    global _sync
    _sync = None


def describe(_ticks=None):
    "what the codes header says, in the Q's 34 columns"
    a = age(_ticks)
    if a is None:
        return 'clock not set'
    if a < 90:
        return 'set just now'
    if a < 5400:
        return 'set %dm ago' % (a // 60)
    if a < 172800:
        return 'set %dh ago' % (a // 3600)
    return 'set %dd ago' % (a // 86400)
