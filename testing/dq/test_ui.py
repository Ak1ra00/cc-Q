# The list window. Every app that shows a list runs through this, and getting it
# wrong hides the selection rather than crashing, which is worse.
import pytest

ROWS = 5


def test_short_list_never_scrolls(settings):
    from dq.theme import window
    for i in range(3):
        assert window(i, 0, 3, ROWS) == (i, 0)


def test_selection_stays_visible_going_down(settings):
    "the bug: idx ran past the window and the highlight disappeared"
    from dq.theme import window
    idx, top = 0, 0
    for target in range(42):
        idx, top = window(target, top, 42, ROWS)
        assert top <= idx < top + ROWS, (idx, top)


def test_selection_stays_visible_going_up(settings):
    from dq.theme import window
    idx, top = window(41, 0, 42, ROWS)
    for target in range(41, -1, -1):
        idx, top = window(target, top, 42, ROWS)
        assert top <= idx < top + ROWS, (idx, top)


def test_window_does_not_run_off_the_end(settings):
    from dq.theme import window
    idx, top = window(41, 0, 42, ROWS)
    assert top == 42 - ROWS
    assert top + ROWS <= 42


def test_window_clamps_a_stale_selection(settings):
    "typing a filter shrinks the list under a selection that was valid"
    from dq.theme import window
    idx, top = window(30, 28, 3, ROWS)
    assert idx == 2 and top == 0


def test_empty_list(settings):
    from dq.theme import window
    idx, top = window(0, 0, 0, ROWS)
    assert (idx, top) == (0, 0)


def test_exactly_one_screenful(settings):
    from dq.theme import window
    for i in range(ROWS):
        assert window(i, 0, ROWS, ROWS) == (i, 0)


def test_paging_is_stable(settings):
    "moving back and forth over a boundary must not oscillate the window"
    from dq.theme import window
    idx, top = window(5, 0, 20, ROWS)
    assert top == 1
    idx, top = window(4, top, 20, ROWS)
    assert top == 1, 'stepping back inside the window should not move it'
    idx, top = window(0, top, 20, ROWS)
    assert top == 0
