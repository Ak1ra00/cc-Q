# Signing text with a key that has nothing to do with Bitcoin.
import pytest

BLOCK = '''----- cc-Q signed -----
hello there
----- signature -----
%s
key ABCD-EFGH
----- end -----'''


def _fake_sig():
    from ubinascii import b2a_base64
    return b2a_base64(bytes(range(65))).decode().strip()


def test_digest_is_domain_separated(settings):
    "a cc-Q signature must never be valid as some other protocol's signature"
    from dq.apps import sign
    import hashlib
    body = b'hello there'
    plain = hashlib.sha256(hashlib.sha256(body).digest()).digest()
    assert sign.digest('hello there') != plain
    assert len(sign.digest('hello there')) == 32


def test_digest_is_stable(settings):
    from dq.apps import sign
    assert sign.digest('x') == sign.digest('x')
    assert sign.digest('x') != sign.digest('y')


def test_identities_differ_by_index(settings):
    from dq.apps import sign
    key = b'\x11' * 32
    assert sign.identity_key(key, 0) != sign.identity_key(key, 1)
    assert sign.identity_key(key, 0) == sign.identity_key(key, 0)
    assert len(sign.identity_key(key, 0)) == 32


def test_identity_follows_the_app_key(settings):
    from dq.apps import sign
    assert sign.identity_key(b'\x11' * 32) != sign.identity_key(b'\x22' * 32)


def test_fingerprint_is_short_and_comparable(settings):
    from dq.apps import sign
    fp = sign.fingerprint(b'\x02' + b'\x33' * 32)
    assert len(fp) == 9 and fp[4] == '-'
    assert fp == sign.fingerprint(b'\x02' + b'\x33' * 32)
    assert fp != sign.fingerprint(b'\x02' + b'\x44' * 32)


def test_armor_round_trip(settings):
    from dq.apps import sign
    from ubinascii import a2b_base64
    sig = bytes(range(65))
    blob = sign.armor('hello there', sig, 'ABCD-EFGH')
    text, got_sig, fp = sign.parse_armor(blob)
    assert text == 'hello there'
    assert got_sig == sig
    assert fp == 'ABCD-EFGH'


def test_armor_keeps_multiline_text(settings):
    from dq.apps import sign
    body = 'line one\nline two\n\nline four'
    text, _, _ = sign.parse_armor(sign.armor(body, bytes(range(65)), 'AAAA-BBBB'))
    assert text == body


def test_parse_rejects_junk(settings):
    from dq.apps import sign
    for bad in ['', 'hello', '----- cc-Q signed -----\nx\n']:
        with pytest.raises(ValueError):
            sign.parse_armor(bad)


def test_parse_rejects_wrong_length_signature(settings):
    from dq.apps import sign
    from ubinascii import b2a_base64
    short = b2a_base64(bytes(10)).decode().strip()
    with pytest.raises(ValueError):
        sign.parse_armor(BLOCK % short)
