# Typing over USB. Refusing is better than sending a character the far machine
# will read as something else.
import pytest


def test_untypable_uses_the_keyboards_real_table(settings):
    """The emulated keyboard knows 42 characters, roughly the Base64 set.

    An unknown one is not dropped -- usb.py types "x" in its place -- so a
    password with a symbol in it would go out silently wrong. Hence the guard.
    """
    from dq import hid
    assert hid.untypable('hunter2') == []
    assert hid.untypable('abc+/-*') == []
    assert hid.untypable('P@ssw0rd!') == ['@', '!']
    assert hid.untypable('café') == ['é']
    assert hid.untypable('a—b—c') == ['—'], 'reported once, not per occurrence'


def test_plan_refuses_rather_than_mangling(settings):
    "a silently wrong character looks like a wrong password on the far machine"
    from dq import hid
    for bad in ('paßword', 'P@ssw0rd!', 'has #hash'):
        with pytest.raises(ValueError) as exc:
            hid.plan(bad)
        assert 'cannot type' in str(exc.value)


def test_plan_passes_good_text(settings):
    from dq import hid
    assert hid.plan('hunter2') == 'hunter2'
    assert hid.plan('hunter2', press_enter=True) == 'hunter2\r'


def test_enter_is_ours_to_decide(settings):
    """upstream's send_keystrokes appends a carriage return to everything it
    sends; we drive the keyboard directly so a snippet does not submit the form
    it lands in."""
    from dq import hid
    assert not hid.plan('some text').endswith('\r')
    assert hid.plan('some text', press_enter=True).count('\r') == 1


def test_new_snippet(settings):
    from dq.apps import keypad
    recs = []
    rec = keypad.new_snippet(recs, 'address', '10 Example St')
    assert rec['label'] == 'address' and rec['text'] == '10 Example St'
    assert 'enter' not in rec
    assert len(recs) == 1


def test_snippet_with_enter(settings):
    from dq.apps import keypad
    rec = keypad.new_snippet([], 'login', 'ak1ra00', press_enter=True)
    assert rec['enter'] is True


def test_snippet_validation(settings):
    from dq.apps import keypad
    for label, text in [('', 'x'), ('x', ''), ('x', 'café'), ('x', '!'), ('x', 'y' * 500)]:
        with pytest.raises(ValueError):
            keypad.new_snippet([], label, text)


def test_search(settings):
    from dq.apps import keypad
    recs = [{'label': 'home address', 'text': 'a'}, {'label': 'work email', 'text': 'b'}]
    assert len(keypad.search(recs, 'ADDRESS')) == 1
    assert len(keypad.search(recs, '')) == 2


def test_preview_never_shows_the_whole_thing(settings):
    from dq.apps import keypad
    rec = {'label': 'key', 'text': 'ABCD-EFGH-IJKL-MNOP-QRST'}
    p = keypad.preview(rec, 12)
    assert len(p) == 12 and p != rec['text']
    assert keypad.preview({'text': 'short'}, 12) == 'short'
