# Splitting the device key. If this is wrong, someone's vault is gone forever,
# so it gets the most paranoid tests in the tree.
import pytest

SECRET = bytes(range(32))


def test_split_and_combine(settings):
    from dq.apps import recovery
    shares = recovery.split(SECRET, 3)
    assert len(shares) == 3
    assert recovery.combine(shares) == SECRET


def test_order_does_not_matter(settings):
    from dq.apps import recovery
    shares = recovery.split(SECRET, 4)
    assert recovery.combine(list(reversed(shares))) == SECRET
    assert recovery.combine([shares[2], shares[0], shares[3], shares[1]]) == SECRET


def test_one_share_reveals_nothing(settings):
    "the property that makes it safe to store them in different places"
    from dq.apps import recovery
    for share in recovery.split(SECRET, 3):
        _, _, part, _ = recovery.decode(share)
        assert part != SECRET
        assert SECRET.hex()[:16] not in share


def test_missing_a_share_fails_loudly(settings):
    "n-of-n: it must say which share is missing, not return junk"
    from dq.apps import recovery
    shares = recovery.split(SECRET, 3)
    with pytest.raises(ValueError) as exc:
        recovery.combine(shares[:2])
    assert 'missing 3' in str(exc.value)


def test_duplicate_share_is_rejected(settings):
    "XOR of a share with itself is zero: this would silently corrupt"
    from dq.apps import recovery
    shares = recovery.split(SECRET, 3)
    with pytest.raises(ValueError):
        recovery.combine([shares[0], shares[0], shares[1]])


def test_damaged_share_is_caught(settings):
    from dq.apps import recovery
    shares = recovery.split(SECRET, 2)
    idx, total, part, check = recovery.decode(shares[0])
    broken = bytearray(part)
    broken[5] ^= 0x01
    shares[0] = recovery.encode(idx, total, bytes(broken), check)
    with pytest.raises(ValueError) as exc:
        recovery.combine(shares)
    assert 'damaged' in str(exc.value)


def test_shares_from_different_splits_do_not_mix(settings):
    from dq.apps import recovery
    a = recovery.split(SECRET, 2)
    b = recovery.split(bytes(32), 2)
    with pytest.raises(ValueError):
        recovery.combine([a[0], b[1]])


def test_encode_round_trip(settings):
    from dq.apps import recovery
    share = recovery.split(SECRET, 2)[0]
    idx, total, part, check = recovery.decode(share)
    assert (idx, total) == (1, 2)
    assert recovery.encode(idx, total, part, check) == share


def test_share_is_readable_and_typable(settings):
    "someone has to copy this onto paper and type it back in"
    from dq.apps import recovery
    share = recovery.split(SECRET, 2)[0]
    assert share.startswith('ccq1 1/2 ')
    body = share.replace('ccq1 1/2 ', '')
    assert all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567 ' for c in body)


def test_rejects_junk(settings):
    from dq.apps import recovery
    for bad in ['', 'hello', 'ccq9 1/2 AAAA BBBB', 'ccq1 0/2 AAAA BBBB',
                'ccq1 3/2 AAAA BBBB', 'ccq1 1/2 TOOSHORT AAAA']:
        with pytest.raises(ValueError):
            recovery.decode(bad)


def test_split_bounds(settings):
    from dq.apps import recovery
    with pytest.raises(ValueError):
        recovery.split(SECRET, 1)
    with pytest.raises(ValueError):
        recovery.split(SECRET, 9)
    with pytest.raises(ValueError):
        recovery.split(b'short', 2)


def test_xor_is_exact(settings):
    "with known randomness, the shares are exactly what XOR says they are"
    from dq.apps import recovery
    r = bytes([0xff] * 32)
    shares = recovery.split(SECRET, 2, _randoms=[r])
    _, _, first, _ = recovery.decode(shares[0])
    _, _, second, _ = recovery.decode(shares[1])
    assert first == r
    assert second == bytes(a ^ b for a, b in zip(SECRET, r))
