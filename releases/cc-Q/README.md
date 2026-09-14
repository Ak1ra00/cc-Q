# cc-Q binaries

Firmware images built from this repository, for the **Q1 only**, signed with the public
developer key (key 0). They are *unofficial firmware*: the Q1 shows a long warning on every
boot and the genuine light stays red until Coinkite-signed firmware is reinstalled. Read
the warnings in the [top-level README](../../README.md) first.

| File | Version | Source | Signing key |
|---|---|---|---|
| `2026-09-03T1540-v1.5.2Q-q1-devkey0-cc-Q.dfu` | 1.5.2Q | upstream `2026-09-03T1540-v1.5.2Q` (`84fd1a5f`), unmodified | dev key 0 |

Check the download before flashing:

```shell
sha256sum -c SHA256SUMS
```

`SHA256SUMS` is not signed. It pins the bytes to this repository; it says nothing about
provenance beyond that.

Official Coinkite binaries and their PGP signatures are at
[coldcard.com/downloads](https://coldcard.com/downloads) and in `../signatures.txt` — that
signature file covers upstream releases only, never anything in this directory.
