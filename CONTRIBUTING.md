# Contributing

Improvements to protocol correctness, simulator clarity, dashboard accessibility, and embedded explanations are welcome.

## Development

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The optional serial integration is installed with `.\.venv\Scripts\python.exe -m pip install -e ".[serial]"`.

## Change expectations

- Keep packet format changes synchronized between Python and firmware and add round-trip/corruption tests.
- Keep the dashboard bound to loopback by default.
- Label generated data as synthetic and state when hardware was not tested.
- Add tests for malformed data, error paths, and new CLI behavior.
- Do not commit credentials, captured private telemetry, build output, or serial logs.

Pull requests should explain the engineering decision, test commands/results, and any hardware assumptions.
