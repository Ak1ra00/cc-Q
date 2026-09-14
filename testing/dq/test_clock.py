# Time on a device with no clock. Every one of these encodes a rule from
# SPEC.md's M0 finding.
import pytest


def test_unset_at_boot(settings):
    from dq import clock
    clock.forget()
    assert clock.now() is None
    assert not clock.is_set()
    assert clock.is_stale(), 'unknown time is stale by definition'


def test_set_and_advance(settings):
    from dq import clock
    clock.forget()
    clock.set_time(1_700_000_000, _ticks=1000)
    assert clock.now(_ticks=1000) == 1_700_000_000
    assert clock.now(_ticks=61_000) == 1_700_000_060


def test_rejects_implausible_time(settings):
    from dq import clock
    with pytest.raises(ValueError):
        clock.set_time(42)


def test_floor_is_a_lower_bound_not_a_time(settings):
    from dq import clock
    clock.forget()
    clock.set_time(1_700_000_000, _ticks=0)
    clock.forget()                                  # power cycle

    assert clock.now() is None, 'a persisted floor must never become the time'
    assert clock.floor() == 1_700_000_000


def test_floor_only_moves_forward(settings):
    from dq import clock
    clock.set_time(1_700_000_000, _ticks=0)
    clock.set_time(1_600_000_001, _ticks=0)         # owner scanned an old QR
    assert clock.floor() == 1_700_000_000


def test_staleness(settings):
    from dq import clock
    clock.forget()
    clock.set_time(1_700_000_000, _ticks=0)
    assert not clock.is_stale(_ticks=3600 * 1000)
    assert clock.is_stale(_ticks=(clock.STALE_AFTER + 60) * 1000)


def test_describe_fits_the_header(settings):
    from dq import clock
    clock.forget()
    assert clock.describe() == 'clock not set'
    clock.set_time(1_700_000_000, _ticks=0)
    assert clock.describe(_ticks=0) == 'set just now'
    assert clock.describe(_ticks=600 * 1000) == 'set 10m ago'
    assert clock.describe(_ticks=7200 * 1000) == 'set 2h ago'
    assert clock.describe(_ticks=3 * 86400 * 1000) == 'set 3d ago'
    assert all(len(clock.describe(_ticks=t)) <= 13
               for t in (0, 600_000, 7_200_000, 300 * 86400 * 1000))
