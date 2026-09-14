# (c) 2026 cc-Q. Getting data off the device, and back on.
#
# Framework, not an app: the vault, journal and codes all need this and none of
# them should own it.
#
# An export is PLAIN TEXT. That is the point -- it has to be readable on a
# machine that is not this one, years from now, without cc-Q. It is also the
# whole risk, so every path through here says so before writing anything.
#
import ujson

MAGIC = 'cc-Q export v1'


def encode(app_name, records):
    "records -> a plain JSON document, readable by anything"
    return ujson.dumps({'format': MAGIC, 'app': app_name, 'records': records})


def decode(app_name, text):
    """A JSON document -> records. Refuses another app's export.

    Accepts a bare list too: someone hand-editing an export on a laptop is a
    supported thing to do, and demanding the wrapper would punish them for it.
    """
    try:
        got = ujson.loads(text)
    except Exception:
        raise ValueError('not readable as JSON')

    if isinstance(got, list):
        records = got
    elif isinstance(got, dict):
        if got.get('app') and got['app'] != app_name:
            raise ValueError('that is a %s export, not %s' % (got['app'], app_name))
        records = got.get('records')
        if records is None:
            raise ValueError('no records in that file')
    else:
        raise ValueError('not a cc-Q export')

    if not isinstance(records, list):
        raise ValueError('records is not a list')
    for r in records:
        if not isinstance(r, dict):
            raise ValueError('a record is not an object')
    return records


def merge(existing, incoming, key):
    """Add incoming records, matching on `key`. Returns (records, added, updated).

    Fields the incoming record does not mention are kept, so restoring an old
    export cannot silently strip a field a later version added.
    """
    by_key = {}
    for r in existing:
        if r.get(key) is not None:
            by_key[r[key]] = r

    added = updated = 0
    for r in incoming:
        k = r.get(key)
        if k is not None and k in by_key:
            by_key[k].update(r)
            updated += 1
        else:
            existing.append(r)
            if k is not None:
                by_key[k] = r
            added += 1
    return existing, added, updated


def filename(app_name):
    return 'dq-%s-export.json' % app_name


WARNING = ('This writes your %s to the card as PLAIN TEXT.\n\n'
           'Anyone who picks up that card can read it. It is the only way to get '
           'your data onto another device, and it is the only way to lose it all '
           'at once.\n\nWrite it?')
