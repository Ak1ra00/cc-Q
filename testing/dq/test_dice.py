# Committed dice. The whole value is that the commitment binds the result, so
# that is what gets tested hardest.
import pytest


def test_rolls_are_in_range(settings):
    from dq.apps import dice
    for _ in range(50):
        assert all(1 <= r <= 6 for r in dice.roll(6, 5))


def test_roll_count_and_bounds(settings):
    from dq.apps import dice
    assert len(dice.roll(20, 3)) == 3
    for bad in [(1, 1), (1001, 1), (6, 0), (6, 99)]:
        with pytest.raises(ValueError):
            dice.roll(*bad)


def test_rng_is_used_as_given(settings):
    from dq.apps import dice
    assert dice.roll(6, 3, rng=lambda n: 0) == [1, 1, 1]
    assert dice.roll(6, 2, rng=lambda n: n - 1) == [6, 6]


def test_commitment_verifies(settings):
    from dq.apps import dice
    rolls, nonce = [3, 5, 1], dice.new_nonce()
    code = dice.short(dice.commitment(6, rolls, nonce))
    assert dice.verify(6, rolls, nonce, code)


def test_commitment_binds_the_rolls(settings):
    "the point of the whole app: you cannot re-roll after showing the code"
    from dq.apps import dice
    nonce = dice.new_nonce()
    code = dice.short(dice.commitment(6, [3, 5, 1], nonce))
    assert not dice.verify(6, [3, 5, 2], nonce, code)
    assert not dice.verify(6, [1, 5, 3], nonce, code), 'order matters too'


def test_commitment_binds_the_die(settings):
    "a d6 result must not be passed off as a d20 roll"
    from dq.apps import dice
    nonce = dice.new_nonce()
    code = dice.short(dice.commitment(6, [3], nonce))
    assert not dice.verify(20, [3], nonce, code)


def test_commitment_binds_the_nonce(settings):
    from dq.apps import dice
    code = dice.short(dice.commitment(6, [3], dice.new_nonce()))
    assert not dice.verify(6, [3], dice.new_nonce(), code)


def test_nonce_is_fresh_every_time(settings):
    from dq.apps import dice
    assert len({bytes(dice.new_nonce()) for _ in range(20)}) == 20


def test_verify_accepts_what_a_person_wrote_down(settings):
    from dq.apps import dice
    rolls, nonce = [4], dice.new_nonce()
    code = dice.short(dice.commitment(6, rolls, nonce))
    assert '-' in code and len(code) == 19
    for variant in (code, code.upper(), code.replace('-', ''), ' %s ' % code):
        assert dice.verify(6, rolls, nonce, variant), variant


def test_verify_refuses_a_stub(settings):
    "a two-character 'commitment' would match almost anything"
    from dq.apps import dice
    nonce = dice.new_nonce()
    code = dice.short(dice.commitment(6, [4], nonce))
    assert not dice.verify(6, [4], nonce, code[:3])
    assert not dice.verify(6, [4], nonce, '')


def test_encode_is_canonical(settings):
    from dq.apps import dice
    assert dice.encode(6, [3, 5, 1]) == b'd6:3,5,1'
    assert dice.encode(6, [3, 5, 1]) != dice.encode(6, [3, 51])


def test_describe_fits_the_screen(settings):
    from dq.apps import dice
    assert dice.describe(6, [4]) == '4'
    assert dice.describe(6, [3, 5, 1]) == '3, 5, 1  total 9'
    assert len(dice.describe(6, [6] * 8)) <= 34
