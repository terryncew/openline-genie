# Third-Party Notices — OpenLine Genie

Audit date: 2026-11-17. Scope: the release candidate source tree only.
This source tree redistributes no third-party software. Dependencies below are
installed by the user at install time (see `requirements.txt`,
`pyproject.toml`); they are not bundled in this tree.

## Runtime dependencies

- **cryptography** (`cryptography>=41.0.0`, required): Ed25519 signing and
  verification. Dual-licensed under the Apache License 2.0 OR the BSD
  License, at the user's choice. Source:
  https://github.com/pyca/cryptography (LICENSE.APACHE / LICENSE.BSD in the
  installed distribution). Compatible with this project's Apache 2.0 release.
- **numpy** (`numpy>=1.26.0`, required): numerical computation. BSD-3-Clause
  license. Source: https://github.com/numpy/numpy
- **onnxruntime** (`onnxruntime>=1.16.0`, required): ONNX model inference.
  MIT license. Source: https://github.com/microsoft/onnxruntime
- **Pillow** (`Pillow>=10.0.0`, required): image processing. Historical
  Permission Notice and Disclaimer (HPND) license. Source:
  https://github.com/python-pillow/Pillow
- **selenium** (`selenium>=4.8.0`, required): browser automation for the
  real-browser functional runner. Apache License 2.0. Source:
  https://github.com/SeleniumHQ/selenium

## Browser-test compatibility shim (in-tree, not a PyPI dependency)

- No PyPI `playwright` package is installed or used. The `playwright`
  package in this tree (`playwright/sync_api.py`) is an in-tree
  Selenium-backed compatibility shim that implements the subset of the
  `playwright.sync_api` interface the test and runner code imports, driving
  real headless Chromium through Selenium. It is OpenLine-written code, not
  redistributed Microsoft Playwright software.

## Tooling

- Python standard library only beyond the above; no CPython redistribution
  in this tree.
- Node.js tests use the built-in `node --test` runner only. There is no
  `package.json` and no npm dependency in this tree.

## Fonts, imagery, vendored code

- No third-party fonts, images, icons, or vendored libraries are bundled in
  this tree. All PNG and MP4 files in the tree are OpenLine-generated
  screenshots, evidence captures, and demo artifacts.
- External CDN references: the Robotics Studio and Ratchet Workbench pages
  served by `genie_server` (the root copies) load no external CDN, font, or
  script assets. The standalone Robotics Studio copy served by the robotics
  server (`openline_robotics_001/openline_robotics_studio.html`) loads
  Tailwind CSS (MIT), Chart.js (MIT), and Google Fonts (Inter and JetBrains
  Mono) from public CDNs and needs network access for full styling and
  charts. See `openline_robotics_001/THIRD_PARTY_NOTICES.md` for that
  sub-package's listing.

## Branding

OpenLine branding and trademarks are governed separately and are not licensed
under the Apache License 2.0.
