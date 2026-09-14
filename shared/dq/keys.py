# (c) 2026 cc-Q. Two key modes. Seedless is the default and everything works in it.
#
# Seedless: a 32-byte device key from the hardware TRNG, kept in the settings blob,
# which is already AES-encrypted under a key tied to the PIN and the secure element.
# Every app gets its own subkey off that, so one app's file cannot decrypt another's.
#
# Seed present: the vault may additionally offer BIP-85 derived passwords. That is
# the only thing a seed changes. Nothing else consults it, and nothing ever asks the
# owner to create one.
#
import ngu

SETTINGS_KEY = 'dq_dk'          # device key, hex, inside the encrypted settings blob
HKDF_SALT = b'cc-Q/dq/v1'
KEY_LEN = 32


def has_seed():
    """Is a BIP39 master secret loaded right now?

    A temporary seed counts: derived passwords follow whatever wallet is active,
    the same way the rest of the firmware treats a temporary seed.
    """
    try:
        from pincodes import pa
        return not pa.is_secret_blank()
    except ImportError:
        return False


def hkdf_sha256(ikm, info=b'', salt=HKDF_SALT, length=KEY_LEN):
    "RFC 5869, the two lines of it we need"
    prk = ngu.hmac.hmac_sha256(salt, ikm)
    out = b''
    block = b''
    counter = 1
    while len(out) < length:
        block = ngu.hmac.hmac_sha256(prk, block + info + bytes([counter]))
        out += block
        counter += 1
    return out[:length]


def device_key():
    "32 bytes, created from the TRNG on first run and kept from then on"
    from glob import settings
    from ubinascii import hexlify as b2a_hex, unhexlify as a2b_hex

    got = settings.get(SETTINGS_KEY)
    if got:
        key = a2b_hex(got)
        if len(key) == KEY_LEN:
            return key
        # A wrong-length key is corruption, not a migration: refuse rather than
        # silently make a new one, which would orphan every existing file.
        raise ValueError('device key is %d bytes' % len(key))

    key = ngu.random.bytes(KEY_LEN)
    settings.put(SETTINGS_KEY, b2a_hex(key).decode())
    settings.save()
    return key


def is_first_run():
    from glob import settings
    return not settings.get(SETTINGS_KEY)


def app_key(app_name):
    "per-app subkey; an app can only ever read its own file"
    if not app_name:
        raise ValueError('app_name')
    return hkdf_sha256(device_key(), info=app_name.encode())


def derive_password(index):
    """BIP-85 password for (seed, index). Raises if no seed is loaded.

    Never called unless the owner picked derived mode for that entry, and the
    option is simply absent from the UI when there is no seed.
    """
    if not has_seed():
        raise ValueError('no seed loaded')
    from drv_entro import bip85_derive, bip85_pwd
    secret, _, mode, _ = bip85_derive(7, index)
    assert mode == 'pw'
    return bip85_pwd(secret)
