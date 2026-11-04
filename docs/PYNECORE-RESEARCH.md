# PyneCore research integration

MARKET-MIND-AI can use [PyneCore](https://github.com/PyneSys/pynecore) as an **optional, local indicator cross-check runtime**. PyneCore provides Pine Script-compatible bar-by-bar semantics and a Python API for running indicator scripts over OHLCV data. This integration is for reproducible historical/descriptive research only.

## What was added

- `backend/requirements-pynecore.txt`: optional install file; the main API requirements stay lightweight.
- `backend/pynecore_scripts/indicator_crosscheck.py`: fixed indicator-only example computing SMA(20), RSI(14), and ATR(14).
- This document: setup, data preparation, and boundaries.

## Install

From the repository root:

```bash
python -m pip install -r backend/requirements-pynecore.txt
```

This installs PyneCore's CLI extras. The core PyneCore runtime itself has no mandatory third-party dependencies; optional CLI features include timezone support. See the [official installation guide](https://pynecore.org/docs/getting-started/installation/).

## Run a cross-check on historical OHLCV

1. Prepare a chronological CSV containing timestamp, open, high, low, close, and volume.
2. Keep the source, retrieval time, symbol, interval, and timezone in your research notes. PyneCore expects OHLCV timestamps in **Unix milliseconds** when constructing data programmatically.
3. Use PyneCore's data converter/CLI to convert the CSV and run the included script. Check the official [CLI run guide](https://pynecore.org/docs/cli/run/) for current CLI syntax and expected data layout. Example shape:

```bash
cd backend
pyne data convert path/to/your_ohlcv.csv
pyne run pynecore_scripts/indicator_crosscheck.py path/to/converted_data.ohlcv
```

The CLI command and generated data filename can vary with PyneCore version and input naming; follow the CLI's help output if your version differs. Do not place API keys in this repository. Pine Script `.pine` compilation through PyneComp is a separate service and may require a PyneSys API key; this example is already Pyne/Python code and does not require Pine conversion.

## How MARKET-MIND-AI should use the output

- Compare PyneCore indicator values with `backend/app/indicators.py` on the same bars.
- Record discrepancies, warm-up behavior, missing-value (`na`) handling, and timestamp alignment.
- Keep comparisons chronological and use only information available at each bar.
- Treat mismatches as a data/implementation review task—not as a signal to buy or sell.
- Keep synthetic fixture data clearly labeled; do not present it as market evidence.

## Scope and safety boundaries

This is an **offline indicator research add-on**. It does not add broker connections, live mode, order routing, autonomous trading, or real-money execution. The included script is indicator-only; it deliberately does not call PyneCore strategy order functions. Historical indicator agreement does not prove predictive ability or future performance.

PyneCore is a separate project under the Apache-2.0 license. This repository adds an optional dependency and a small original example; it does not vendor or copy PyneCore source. PyneCore is independent of TradingView and is not endorsed by TradingView. See the [PyneCore repository](https://github.com/PyneSys/pynecore) and its license for full terms.
