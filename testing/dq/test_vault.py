# Vault record logic. The id rules are the ones worth guarding: the owner writes
# those numbers on paper, and a derived password IS its id.
import pytest


def test_ids_start_at_one(settings):
    from dq.apps import vault
    assert vault.next_id([]) == 1


def test_ids_are_never_reused(settings):
    from dq.apps import vault
    recs = [vault.new_entry([], 'a', 'a@x'), ]
    recs.append(vault.new_entry(recs, 'b', 'b@x'))
    recs.append(vault.new_entry(recs, 'c', 'c@x'))
    assert [r['id'] for r in recs] == [1, 2, 3]

    del recs[1]                                     # delete the middle one
    recs.append(vault.new_entry(recs, 'd', 'd@x'))
    assert recs[-1]['id'] == 4, 'id 2 must never come back'


def test_search_matches_service_and_login(settings):
    from dq.apps import vault
    recs = [{'id': 1, 'service': 'protonmail', 'login': 'akira@proton.me'},
            {'id': 2, 'service': 'github', 'login': 'ak1ra00'},
            {'id': 3, 'service': 'Proton VPN', 'login': 'akira@proton.me'}]
    assert len(vault.search(recs, 'proton')) == 2    # service, case-insensitive
    assert len(vault.search(recs, 'PROTON.ME')) == 2  # and login
    assert len(vault.search(recs, 'GITHUB')) == 1
    assert len(vault.search(recs, '')) == 3
    assert vault.search(recs, 'nope') == []


def test_no_date_without_a_clock(settings):
    "the Q cannot know the date; a guessed one is worse than none"
    from dq.apps import vault
    rec = vault.new_entry([], 'protonmail', 'a@b')
    assert 'created' not in rec
    dated = vault.new_entry([], 'protonmail', 'a@b', created='2026-09-14')
    assert dated['created'] == '2026-09-14'


def test_export_carries_no_passwords(settings):
    "the wallet card is useless to anyone who picks it up"
    from dq.apps import vault
    recs = [{'id': 2, 'service': 'github', 'login': 'ak1ra00',
             'source': 'stored', 'secret': 'SEALEDSECRETDATA'},
            {'id': 1, 'service': 'protonmail', 'login': 'a@b', 'source': 'derived'}]
    lines = vault.export_lines(recs)
    assert lines[0] == 'service | login | id'
    assert lines[1].endswith('| 1') and lines[2].endswith('| 2')     # sorted by id
    assert 'SEALEDSECRETDATA' not in '\n'.join(lines)


def test_seal_and_open(settings):
    from dq.apps import vault
    key = b'\x11' * 32
    sealed = vault.seal_secret(key, 14, 'hunter2-but-longer')
    assert 'hunter2' not in sealed
    assert vault.open_secret(key, 14, sealed) == 'hunter2-but-longer'


def test_seal_is_bound_to_the_id(settings):
    "an entry's ciphertext must not open under another entry's id"
    from dq.apps import vault
    key = b'\x22' * 32
    sealed = vault.seal_secret(key, 14, 'secret-password')
    with pytest.raises(ValueError):
        vault.open_secret(key, 15, sealed)


def test_seal_is_bound_to_the_app_key(settings):
    from dq.apps import vault
    sealed = vault.seal_secret(b'\x22' * 32, 14, 'secret-password')
    with pytest.raises(ValueError):
        vault.open_secret(b'\x99' * 32, 14, sealed)


def test_tampered_seal_is_caught(settings):
    from dq.apps import vault
    from ubinascii import a2b_base64, b2a_base64
    key = b'\x44' * 32
    raw = bytearray(a2b_base64(vault.seal_secret(key, 5, 'secret-password')))
    raw[20] ^= 0x01
    with pytest.raises(ValueError):
        vault.open_secret(key, 5, b2a_base64(bytes(raw)).decode().strip())


def test_seal_nonce_differs(settings):
    from dq.apps import vault
    key = b'\x33' * 32
    assert vault.seal_secret(key, 1, 'same') != vault.seal_secret(key, 1, 'same')


def test_derived_entry_has_no_stored_secret(settings):
    from dq.apps import vault
    rec = vault.new_entry([], 'protonmail', 'a@b', source='derived')
    assert 'secret' not in rec and rec['source'] == 'derived'


def test_rejects_unknown_source(settings):
    from dq.apps import vault
    with pytest.raises(ValueError):
        vault.new_entry([], 'x', 'y', source='magic')
