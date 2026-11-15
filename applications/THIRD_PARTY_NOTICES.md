# Third-Party Notices — OpenLine Genie

Audit date: 2026-11-11. Scope: the launch candidate source tree only.
This source tree redistributes no third-party software. Dependencies below are
installed by the user at install time (see `requirements.txt`,
`pyproject.toml`); they are not bundled in this tree.

## Runtime dependencies

- **cryptography** (`cryptography>=41.0.0`, required): Ed25519 signing and
  verification. Dual-licensed under the Apache License 2.0 OR the BSD
  License, at the user's choice. Source:
  https://github.com/pyca/cryptography (LICENSE.APACHE / LICENSE.BSD in the
  installed distribution). Compatible with this project's Apache 2.0 release.
- **playwright** (`playwright>=1.40.0`, optional, browser tests only):
  Apache License 2.0. Source: https://github.com/microsoft/playwright

## Tooling

- Python standard library only beyond the above; no CPython redistribution
  in this tree.
- Node.js tests use the built-in `node --test` runner only. There is no
  `package.json` and no npm dependency in this tree.

## Fonts, imagery, vendored code

- None. No third-party fonts, images, icons, or vendored libraries are in
  this tree. No external CDN, font, or script references exist in the HTML,
  JavaScript, or template files (checked 2026-11-11).
- All PNG and MP4 files in the tree are OpenLine-generated screenshots,
  evidence captures, and demo artifacts.

## Branding

OpenLine branding and trademarks are governed separately and are not licensed
under the Apache License 2.0.
