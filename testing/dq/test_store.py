# The record store's container format. These are the tests that matter most:
# a bug here loses data that cannot be recovered from anywhere else.
import pytest


def test_roundtrip(settings):
    from dq import store
    key = b'\x11' * 32
    recs = [{'id': 1, 'service': 'protonmail'}, {'id': 2, 'service': 'github'}]
    blob = store.encode('vault', recs, key)
    assert store.decode('vault', blob, key) == recs


def test_header_is_what_spec_says(settings):
    from dq import store
    key = b'\x22' * 32
    blob = store.encode('vault', [], key, nonce=b'\xaa' * 16)
    assert blob[:4] == b'DQ01'
    assert blob[4] == 5 and blob[5:10] == b'vault'      # length-prefixed name
    assert blob[10] == store.SCHEMA
    assert blob[11:27] == b'\xaa' * 16                  # nonce
    assert len(blob[-32:]) == 32                        # mac


def test_empty_store(settings):
    from dq import store
    key = b'\x33' * 32
    assert store.decode('vault', store.encode('vault', [], key), key) == []


def test_unknown_fields_survive(settings):
    """A newer cc-Q adds a field; this one must write it back untouched.

    This is the forward-compatibility promise in CLAUDE.md, invariant 5.
    """
    from dq import store
    key = b'\x44' * 32
    original = [{'id': 7, 'service': 'fastmail',
                 'colour': 'green', 'nested': {'added': 'later'}}]
    recs = store.decode('vault', store.encode('vault', original, key), key)

    recs[0]['service'] = 'fastmail.com'         # the kind of edit this version makes
    back = store.decode('vault', store.encode('vault', recs, key), key)

    assert back[0]['service'] == 'fastmail.com'
    assert back[0]['colour'] == 'green'
    assert back[0]['nested'] == {'added': 'later'}


def test_tampering_is_caught(settings):
    from dq import store
    key = b'\x55' * 32
    blob = bytearray(store.encode('vault', [{'id': 1}], key))
    blob[-40] ^= 0x01                            # flip a ciphertext bit
    with pytest.raises(store.BadMAC):
        store.decode('vault', bytes(blob), key)


def test_truncated_file_is_caught(settings):
    from dq import store
    key = b'\x66' * 32
    blob = store.encode('vault', [{'id': 1}], key)
    with pytest.raises(store.StoreError):
        store.decode('vault', blob[:-1], key)


def test_wrong_key_is_caught(settings):
    from dq import store
    blob = store.encode('vault', [{'id': 1}], b'\x77' * 32)
    with pytest.raises(store.BadMAC):
        store.decode('vault', blob, b'\x88' * 32)


def test_another_apps_file_is_refused(settings):
    "journal's key must not open the vault's file, and vice versa"
    from dq import store
    key = b'\x99' * 32
    blob = store.encode('vault', [{'id': 1}], key)
    with pytest.raises(store.StoreError):
        store.decode('journal', blob, key)


def test_newer_schema_is_refused(settings):
    from dq import store
    key = b'\xaa' * 32
    blob = store.encode('vault', [{'id': 1}], key, schema=store.SCHEMA + 1)
    with pytest.raises(store.StoreError):
        store.decode('vault', blob, key)


def test_nonce_differs_every_write(settings):
    from dq import store
    key = b'\xbb' * 32
    recs = [{'id': 1}]
    a = store.encode('vault', recs, key)
    b = store.encode('vault', recs, key)
    assert a != b, 'same nonce twice would reuse the CTR keystream'
    assert a[11:27] != b[11:27]
