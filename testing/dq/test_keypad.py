# Typing over USB. Refusing is better than sending a character the far machine
# will read as something else.
import pytest


def test_untypable_finds_the_bad_ones(settings):
    from dq import hid
    assert hid.untypable('normal-Password_123!') == []
    assert hid.untypable('café') == ['é']
    assert hid.untypable('a—b—c') == ['—'], 'reported once, not per occurrence'


def test_plan_refuses_rather_than_mangling(settings):
    "a silently wrong character looks like a wrong password on the far machine"
    from dq import hid
    with pytest.raises(ValueError) as exc:
        hid.plan('paßword')
    assert 'cannot type' in str(exc.value)


def test_plan_passes_good_text(settings):
    from dq import hid
    assert hid.plan('hunter2') == 'hunter2'
    assert hid.plan('hunter2', press_enter=True) == 'hunter2\r'


def test_symbols_are_typable(settings):
    from dq import hid
    assert hid.plan('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~') is not None


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
    for label, text in [('', 'x'), ('x', ''), ('x', 'café'), ('x', 'y' * 500)]:
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
