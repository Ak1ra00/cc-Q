# Key modes. Seedless is the default; a seed only ever adds the derived option.
import pytest


def test_device_key_created_once(settings):
    from dq import keys
    first = keys.device_key()
    assert len(first) == 32
    assert keys.device_key() == first, 'must not roll on every call'
    assert settings.saves == 1


def test_device_key_survives_the_settings_blob(settings):
    "settings are JSON, so the key has to be stored as text"
    from dq import keys
    key = keys.device_key()
    settings.save()                     # forces a JSON round-trip in the fake
    assert keys.device_key() == key


def test_first_run_detection(settings):
    from dq import keys
    assert keys.is_first_run()
    keys.device_key()
    assert not keys.is_first_run()


def test_app_keys_differ(settings):
    from dq import keys
    v, j, c = (keys.app_key(n) for n in ('vault', 'journal', 'codes'))
    assert len({v, j, c}) == 3, 'one app must not be able to read another'
    assert all(len(k) == 32 for k in (v, j, c))


def test_app_key_is_stable(settings):
    from dq import keys
    assert keys.app_key('vault') == keys.app_key('vault')


def test_app_key_follows_device_key(settings):
    from dq import keys
    before = keys.app_key('vault')
    settings.remove_key(keys.SETTINGS_KEY)
    assert keys.app_key('vault') != before


def test_hkdf_matches_rfc5869_shape(settings):
    "not an RFC vector (different salt), but the expand loop must be right"
    from dq import keys
    out = keys.hkdf_sha256(b'\x0b' * 22, info=b'vault', length=64)
    assert len(out) == 64
    assert out[:32] == keys.hkdf_sha256(b'\x0b' * 22, info=b'vault', length=32)


def test_corrupt_device_key_refuses(settings):
    "better to fail loudly than to mint a new key and orphan every file"
    from dq import keys
    settings.put(keys.SETTINGS_KEY, 'aabb')
    with pytest.raises(ValueError):
        keys.device_key()


def test_derive_password_needs_a_seed(settings, no_seed):
    from dq import keys
    with pytest.raises(ValueError):
        keys.derive_password(0)
