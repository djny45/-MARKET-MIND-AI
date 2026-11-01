# Flowsurface Import Notes

- Upstream: https://github.com/flowsurface-rs/flowsurface
- Upstream commit: `50c06caac0cf7ce9c3bcaabcf99fbd4e4e0f6746`
- Imported snapshot path: `third_party/Flowsurface/`
- Imported tree entries: 350 (GitHub Actions import verified successful).
- Main application, data crate and bundled indicator sources: GPL-3.0-or-later.
- Indicator engine and CLI: Apache-2.0.
- Exchange adapter crate: MIT.
- The upstream root LICENSE and component-specific license files are retained.

## Import boundaries

This is a source archive, not an installation or integration into the MARKET-MIND-AI FastAPI/React application. It remains isolated under `third_party/`.

The source contains a standalone Rust desktop charting application and exchange data adapters. No Rust dependencies were installed, no binary was built or launched, and no exchange connections were configured by this import.

The upstream `.github/` directory was excluded. This also excludes upstream CI/release automation and its signing-key path; no signing key was copied.

## Intended use in this repository

Use as a reference for historical market-data visualization and market-microstructure research architecture. Any future extraction or reuse must preserve component-level license notices and provenance. Do not merge GPL application code into the existing application or distribute a combined/derivative product without first reviewing GPL-3.0-or-later obligations. This note is not legal advice.

The imported project includes exchange-stream functionality upstream. This import alone does not enable it in MARKET-MIND-AI. The existing MARKET-MIND-AI scope remains historical research and analytics, with no broker integration or order execution.
