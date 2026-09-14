# The file log. It is the bytes being witnessed, not the filename.
import pytest
import hashlib

DIGEST_A = hashlib.sha256(b'contract v1').hexdigest()
DIGEST_B = hashlib.sha256(b'contract v2').hexdigest()


def test_hash_chunks_matches_one_shot(settings):
    from dq.apps import witness
    data = b'a' * 3000
    chunks = [data[i:i + 1024] for i in range(0, len(data), 1024)]
    assert witness.hexed(witness.hash_chunks(chunks)) == hashlib.sha256(data).hexdigest()


def test_hash_chunks_empty(settings):
    from dq.apps import witness
    assert witness.hexed(witness.hash_chunks([])) == hashlib.sha256(b'').hexdigest()


def test_note_file(settings):
    from dq.apps import witness
    recs = []
    rec = witness.note_file(recs, 'contract.pdf', DIGEST_A, 1234, '2026-09-14')
    assert rec['sha256'] == DIGEST_A and rec['size'] == 1234
    assert rec['names'] == ['contract.pdf'] and rec['seen'] == '2026-09-14'


def test_same_bytes_twice_is_one_entry(settings):
    from dq.apps import witness
    recs = []
    witness.note_file(recs, 'contract.pdf', DIGEST_A, 1234, '2026-09-14')
    witness.note_file(recs, 'contract-copy.pdf', DIGEST_A, 1234, '2026-09-20')
    assert len(recs) == 1
    assert recs[0]['names'] == ['contract.pdf', 'contract-copy.pdf']
    assert recs[0]['seen'] == '2026-09-14', 'first sighting is the one that counts'


def test_no_date_when_the_owner_never_said(settings):
    from dq.apps import witness
    recs = []
    rec = witness.note_file(recs, 'x.pdf', DIGEST_A, 1, None)
    assert 'seen' not in rec


def test_check_match_and_unknown(settings):
    from dq.apps import witness
    recs = []
    witness.note_file(recs, 'contract.pdf', DIGEST_A, 1234, '2026-09-14')
    assert witness.check_file(recs, DIGEST_A)[0] == 'match'
    assert witness.check_file(recs, DIGEST_B) == ('unknown', None)


def test_changed_file_is_detected(settings):
    "the whole point: same name, different bytes"
    from dq.apps import witness
    recs = []
    witness.note_file(recs, 'contract.pdf', DIGEST_A, 1234, '2026-09-14')
    older = witness.check_name(recs, 'contract.pdf', DIGEST_B)
    assert older and older['sha256'] == DIGEST_A


def test_unchanged_file_is_not_flagged(settings):
    from dq.apps import witness
    recs = []
    witness.note_file(recs, 'contract.pdf', DIGEST_A, 1234, '2026-09-14')
    assert witness.check_name(recs, 'contract.pdf', DIGEST_A) is None


def test_short_digest_fits_the_screen(settings):
    from dq.apps import witness
    s = witness.short(DIGEST_A)
    assert len(s) <= 17 and s.startswith(DIGEST_A[:8])


def test_unknown_fields_survive(settings):
    from dq.apps import witness
    recs = [{'sha256': DIGEST_A, 'size': 1, 'names': ['a.pdf'], 'tag': 'legal'}]
    witness.note_file(recs, 'b.pdf', DIGEST_A, 1, '2026-09-14')
    assert recs[0]['tag'] == 'legal'
