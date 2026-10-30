# Visual workflow guide

The React Flow canvas is a directed graph editor. Each node represents a data source, validation step, deterministic analytical calculation, or research output.

## Built-in executable nodes

| Node | Input | Output |
|---|---|---|
| Market Data Input | Numeric chronological observations | Normalized values |
| Data Quality | Values | Values plus quality report |
| SMA | Values | Moving-average series |
| EMA | Values | Exponential-average series |
| RSI | Values | RSI series |
| MACD | Values | MACD, signal and histogram |
| Bollinger Bands | Values | Middle, upper and lower bands |
| Returns | Values | Period returns and summary |
| Realized Volatility | Values | Per-observation volatility |
| Research Summary | Values | Descriptive endpoints and sample count |

## Build a workflow

1. Add a source node and analytical nodes from the sidebar.
2. Connect the right-side output handle to the next node's left-side input handle.
3. Branch a source into multiple analytics when independent calculations are needed.
4. Enter comma-separated chronological observations in the sample data field.
5. Run the workflow and inspect the structured results.

The current UI sends the sample close series to the backend. It is not a real-time quote feed. A node is executable only if it has a backend handler registered in the workflow engine. Worker catalogue entries that are not mapped to executable node types remain profiles, not functioning agents.

## Graph semantics and limitations

The backend executes nodes in topological order and rejects cycles, missing edge endpoints, unsupported node types, non-numeric values and non-finite values. Current edge payload semantics pass the upstream node result to the downstream node; typed multi-output port routing and configurable edge selectors are future work.

The numerical examples are educational research calculations. They are not trade instructions. The platform has no broker or order-routing integration.
