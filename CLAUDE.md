# CLAUDE.md

Standing instructions for this repo. Read this before any work, every session.

## What this is

`cc-Q` is a custom firmware for the Coldcard Q that removes the Bitcoin workflow
and replaces it with a daily-use personal terminal: a password vault, sign-in
codes, and an encrypted journal, all behind the device PIN.

Upstream base: https://github.com/Coldcard/firmware — Q1 target only.
Remote: https://github.com/Ak1ra00/cc-Q

## Attribution rules

These are absolute and apply to every commit, tag, PR, issue, and file.

- Never add `Co-Authored-By: Claude` or any co-author trailer.
- Never add `Generated with Claude Code`, `🤖`, or any similar marker to a
  commit message, PR body, changelog, README, or source comment.
- Never set git `author` or `committer`. Use whatever the local git config
  already has. Do not run `git config user.name` or `user.email`.
- No mention of Claude, Anthropic, or AI assistance anywhere in the repo.

Commit messages are plain and imperative: `add encrypted record store`,
`fix vault search on empty query`. Body only when the change needs explaining.

## Hard boundaries

- **Never touch the bootrom or bootloader.** `stm32/bootloader/` is off limits.
  It runs first, it is signed by Coinkite, and it cannot be replaced.
- **Never modify the PIN entry or login sequence.** A crash there bricks the
  device with no recovery path. If a change appears to require it, stop and ask.
- **Simulator first.** Nothing goes to hardware until it runs clean in
  `unix/simulator.py`. Hardware flashing is a manual step the owner performs,
  never something you instruct as routine.
- **Keep a recovery path.** The README must always tell the owner to keep an
  official Coinkite `.dfu` on a spare microSD.
- Upstream's license is source-available, not OSI open source. Keep their
  LICENSE file intact and unmodified.

## Architecture invariants

These exist so upstream can be merged later without a fight, and so new
features are cheap to add.

1. **All new code lives in `shared/dq/`.** One namespace, ours. Nothing else.
2. **Patches to upstream files are minimal and logged.** Every file outside
   `shared/dq/` that we touch gets an entry in `PATCHES.md` saying what changed
   and why. Aim for under ten such files total.
3. **Hide upstream features, do not delete them.** Bitcoin menus get removed
   from the menu tree, not ripped out of the source. Deletion makes every
   future upstream merge painful.
4. **Apps are plugins.** No app knows about any other app. The home screen
   reads a registry; it does not hardcode a list.
5. **Storage is schema-versioned and forward-compatible.** Unknown fields in a
   record are preserved on write, never dropped. A newer file opened by older
   firmware must not lose data.
6. **No network code, ever.** There is no network. Any dependency that implies
   one is a bug.

## Adding a feature

This is the recipe. It should stay this short. If adding a feature ever needs
more than these steps, the plugin layer has regressed and that is the bug to
fix first.

1. Create `shared/dq/apps/<name>.py` with a class subclassing `DQApp`.
2. Decorate it with `@register_app`.
3. Add the module to `manifest_q1.py`.
4. Add tests in `testing/dq/test_<name>.py`.

The app gets its storage, its encryption subkey, its theming, and its home
screen slot for free from the framework. It should not reach outside its own
namespace for any of them.

`FEATURES.md` is the running backlog. The owner appends ideas to it freely, in
any state of half-formedness. Read it at the start of a session. Never delete
or reword an entry that has not been built; move it to the Done section with
the commit hash when it ships.

## Seed policy

The firmware runs fully without a BIP39 seed. This is the default and the
supported path. A seed is optional and only unlocks one extra capability.
See `SPEC.md` for the two key modes. Never write code that assumes a seed
exists, and never prompt the owner to create one.

## Working style

- Small commits, each one leaving the simulator in a working state.
- Write the test before the feature where it is practical.
- When a decision has more than one reasonable answer, put it in `PATCHES.md`
  or a code comment rather than picking silently.
- If a task requires touching something in Hard boundaries, stop and ask.
