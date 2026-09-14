# (c) 2026 cc-Q. One encrypted file per app on microSD: dq-<app>.dat
#
#   magic "DQ01" | app name | schema version | nonce | AES-256-CTR ciphertext | HMAC-SHA256
#
# Encrypted under app_key(app_name). The HMAC covers everything before it and is
# verified before anything is decrypted, so a tampered file is rejected rather
# than parsed.
#
# Records are JSON objects and **unknown fields are read, held and written back
# unchanged**. That is what lets a later version add fields without this one
# destroying them, and it is tested.
#
import ngu, ujson

MAGIC = b'DQ01'
SCHEMA = 1
NONCE_LEN = 16
MAC_LEN = 32
MAX_NAME = 16


class StoreError(Exception):
    pass


class BadMAC(StoreError):
    "file is corrupt, truncated, tampered with, or from another device"
    pass


def encode(app_name, records, key, nonce=None, schema=SCHEMA):
    "records (list of dicts) -> one sealed blob. Pure: no files, no card."
    name = app_name.encode()
    if not 0 < len(name) <= MAX_NAME:
        raise ValueError('app name')

    if nonce is None:
        nonce = ngu.random.bytes(NONCE_LEN)
    assert len(nonce) == NONCE_LEN

    body = ujson.dumps(records).encode()
    ct = ngu.aes.CTR(key, nonce).cipher(body)

    head = MAGIC + bytes([len(name)]) + name + bytes([schema]) + nonce
    return head + ct + ngu.hmac.hmac_sha256(key, head + ct)


def decode(app_name, blob, key):
    "sealed blob -> records. Verifies the MAC before decrypting anything."
    name = app_name.encode()
    least = len(MAGIC) + 1 + len(name) + 1 + NONCE_LEN + MAC_LEN
    if len(blob) < least:
        raise StoreError('too short')
    if blob[:4] != MAGIC:
        raise StoreError('not a cc-Q file')

    n = blob[4]
    if n != len(name) or blob[5:5 + n] != name:
        raise StoreError('belongs to another app')

    schema = blob[5 + n]
    if schema > SCHEMA:
        # Written by a newer cc-Q. Refuse rather than round-trip it: we would
        # have to re-encrypt, and we cannot promise to preserve what we cannot read.
        raise StoreError('schema %d is newer than %d' % (schema, SCHEMA))

    body, mac = blob[:-MAC_LEN], blob[-MAC_LEN:]
    if not _eq(ngu.hmac.hmac_sha256(key, body), mac):
        raise BadMAC('HMAC mismatch')

    off = 6 + n
    nonce, ct = body[off:off + NONCE_LEN], body[off + NONCE_LEN:]
    if not ct:
        return []

    plain = ngu.aes.CTR(key, nonce).cipher(ct)
    records = ujson.loads(plain.decode())
    if not isinstance(records, list):
        raise StoreError('not a record list')
    return records


def _eq(a, b):
    "constant-time-ish compare; MicroPython has no hmac.compare_digest"
    if len(a) != len(b):
        return False
    diff = 0
    for x, y in zip(a, b):
        diff |= x ^ y
    return diff == 0


def mirror_enabled():
    "card B mirroring, on unless the owner turned it off"
    try:
        from glob import settings
        return bool(settings.get('dq_mirror', True))
    except ImportError:
        return True


class RecordStore:
    """An app's records on card A, mirrored to card B when one is present.

    Writes go to a temp file and are renamed into place, so a card pulled
    mid-write can never leave a truncated file as the only copy.
    """

    def __init__(self, app_name, key=None):
        self.app_name = app_name
        self._key = key

    def key(self):
        if self._key is None:
            from dq.keys import app_key
            self._key = app_key(self.app_name)
        return self._key

    def filename(self, card):
        return card.get_sd_root() + '/dq-%s.dat' % self.app_name

    def load(self):
        "records, or [] when there is no file yet. Raises BadMAC on a bad one."
        from files import CardSlot
        with CardSlot() as card:
            fn = self.filename(card)
            try:
                with open(fn, 'rb') as fd:
                    blob = fd.read()
            except OSError:
                return []
        return decode(self.app_name, blob, self.key())

    def save(self, records):
        "write card A, then mirror to B if it is there. Returns cards written."
        from files import CardSlot
        blob = encode(self.app_name, records, self.key())

        slots = [False]                     # A, or whichever single card is in
        if CardSlot.both_inserted() and mirror_enabled():
            slots.append(True)

        written = 0
        for slot_b in slots:
            try:
                with CardSlot(slot_b=slot_b) as card:
                    self._write_one(card, blob)
                written += 1
            except Exception:
                # a full or unwritable second card must not lose the first
                continue
        if not written:
            raise StoreError('nothing written: no card?')
        return written

    def _write_one(self, card, blob):
        import os
        final = self.filename(card)
        tmp = final + '.tmp'
        with open(tmp, 'wb') as fd:
            fd.write(blob)
        try:
            os.remove(final)
        except OSError:
            pass
        os.rename(tmp, final)
