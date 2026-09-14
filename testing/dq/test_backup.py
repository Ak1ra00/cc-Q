# Export and import. An export is plain text on purpose; a bad merge on the way
# back in loses data silently, so merging gets the attention here.
import pytest


def test_encode_is_plain_readable_json(settings):
    from dq import backup
    import json
    text = backup.encode('vault', [{'id': 1, 'service': 'protonmail'}])
    got = json.loads(text)
    assert got['app'] == 'vault' and got['format'] == backup.MAGIC
    assert got['records'][0]['service'] == 'protonmail'


def test_round_trip(settings):
    from dq import backup
    recs = [{'id': 1, 'service': 'a'}, {'id': 2, 'service': 'b'}]
    assert backup.decode('vault', backup.encode('vault', recs)) == recs


def test_accepts_a_hand_edited_bare_list(settings):
    "editing an export on a laptop is a supported thing to do"
    from dq import backup
    assert backup.decode('vault', '[{"id": 1}]') == [{'id': 1}]


def test_refuses_another_apps_export(settings):
    from dq import backup
    blob = backup.encode('journal', [{'date': '2026-09-14'}])
    with pytest.raises(ValueError) as exc:
        backup.decode('vault', blob)
    assert 'journal' in str(exc.value)


def test_refuses_junk(settings):
    from dq import backup
    for bad in ['', 'not json', '{"app": "vault"}', '"a string"', '[1, 2, 3]']:
        with pytest.raises(ValueError):
            backup.decode('vault', bad)


def test_merge_adds_new(settings):
    from dq import backup
    existing = [{'id': 1, 'service': 'a'}]
    recs, added, updated = backup.merge(existing, [{'id': 2, 'service': 'b'}], 'id')
    assert (added, updated) == (1, 0)
    assert len(recs) == 2


def test_merge_updates_matching(settings):
    from dq import backup
    existing = [{'id': 1, 'service': 'a'}]
    recs, added, updated = backup.merge(existing, [{'id': 1, 'service': 'renamed'}], 'id')
    assert (added, updated) == (0, 1)
    assert recs[0]['service'] == 'renamed'


def test_merge_keeps_fields_the_import_does_not_mention(settings):
    "restoring an old export must not strip a field added since"
    from dq import backup
    existing = [{'id': 1, 'service': 'a', 'note': 'kept', 'source': 'stored'}]
    recs, _, _ = backup.merge(existing, [{'id': 1, 'service': 'a'}], 'id')
    assert recs[0]['note'] == 'kept' and recs[0]['source'] == 'stored'


def test_merge_does_not_delete(settings):
    "an import is a merge, never a replace: today's entries survive it"
    from dq import backup
    existing = [{'id': 1}, {'id': 2}, {'id': 3}]
    recs, _, _ = backup.merge(existing, [{'id': 1}], 'id')
    assert len(recs) == 3


def test_merge_on_a_different_key(settings):
    from dq import backup
    existing = [{'date': '2026-09-14', 'text': 'today'}]
    recs, added, updated = backup.merge(
        existing, [{'date': '2026-09-14', 'text': 'edited'},
                   {'date': '2026-09-13', 'text': 'yesterday'}], 'date')
    assert (added, updated) == (1, 1)
    assert recs[0]['text'] == 'edited'


def test_merge_handles_records_with_no_key(settings):
    from dq import backup
    recs, added, updated = backup.merge([], [{'no_id_here': True}], 'id')
    assert (added, updated) == (1, 0) and len(recs) == 1
