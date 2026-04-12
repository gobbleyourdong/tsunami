"""QA-1 Playtest Fires 117 + 119: dashboard / analytics deliverables
shipped with ZERO chart primitives. The scaffold pulls in `recharts`
(dashboard / data-viz scaffolds), the project name screams chart intent
("analytics-dashboard-charts"), but App.tsx rendered either a
"Chart Placeholder" text stub or nothing at all.

Gate: if any known chart library is in package.json dependencies AND
App.tsx doesn't render any chart primitive or raw <canvas>/<svg>,
REFUSE. Chart-scaffold deliverables must actually render a chart.

Benign shapes that pass:
  - No chart lib in deps (vanilla React app) → gate doesn't fire.
  - Chart lib in deps + <LineChart>/<BarChart>/etc. primitive present.
  - Chart lib in deps + raw <svg> (D3-style custom viz).
  - Chart lib in deps + raw <canvas> (Chart.js manual binding).
"""

from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path

from tsunami.tools.message import _check_deliverable_complete
from tsunami.tools import filesystem as fs_state


@pytest.fixture(autouse=True)
def reset_state():
    fs_state._session_created_projects.clear()
    fs_state._session_last_project = None
    fs_state._last_written_deliverable = None
    fs_state._session_task_prompt = ""
    fs_state._active_project = None
    yield
    fs_state._session_created_projects.clear()
    fs_state._session_last_project = None
    fs_state._last_written_deliverable = None
    fs_state._session_task_prompt = ""
    fs_state._active_project = None


def _make(tmp: str, name: str, deps: dict, app_content: str) -> Path:
    ws = Path(tmp) / "workspace"
    d = ws / "deliverables" / name
    (d / "src").mkdir(parents=True)
    (d / "package.json").write_text(
        json.dumps({"name": "x", "dependencies": deps})
    )
    (d / "src" / "App.tsx").write_text(app_content)
    return ws


# --- Fire 117 / 119 repro ---------------------------------------------------


def test_recharts_without_chart_refused():
    """Fire 119 pattern: dashboard scaffold + recharts dep + no <LineChart>."""
    app = (
        'import React from "react";\n'
        'export default function App() {\n'
        '  const [count, setCount] = React.useState(0);\n'
        '  const [data, setData] = React.useState([]);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Analytics Dashboard</h1>\n'
        '      <nav><a>Overview</a><a>Reports</a><a>Settings</a></nav>\n'
        '      <p>Total visits: {count}</p>\n'
        '      <p>Data points loaded: {data.length}</p>\n'
        '      <button onClick={() => setCount(count+1)}>Increment</button>\n'
        '      <p>Click tracker for the analytics dashboard session</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "analytics", {"react": "19", "recharts": "2.15"}, app)
        fs_state._session_last_project = "analytics"
        fs_state._session_task_prompt = "analytics dashboard"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "chart primitive" in r
        assert "recharts" in r


def test_recharts_with_linechart_passes():
    app = (
        'import React from "react";\n'
        'import { LineChart, Line, XAxis, YAxis, ResponsiveContainer } from "recharts";\n'
        'export default function App() {\n'
        '  const [data, setData] = React.useState([{x:1,y:5},{x:2,y:8},{x:3,y:3}]);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Analytics Dashboard</h1>\n'
        '      <ResponsiveContainer width="100%" height={300}>\n'
        '        <LineChart data={data}>\n'
        '          <Line dataKey="y" stroke="#8884d8"/>\n'
        '          <XAxis dataKey="x"/>\n'
        '          <YAxis/>\n'
        '        </LineChart>\n'
        '      </ResponsiveContainer>\n'
        '      <p>Data length: {data.length}</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "good", {"react": "19", "recharts": "2.15"}, app)
        fs_state._session_last_project = "good"
        fs_state._session_task_prompt = "analytics dashboard"
        assert _check_deliverable_complete(str(ws)) is None


def test_d3_with_raw_svg_passes():
    app = (
        'import * as d3 from "d3";\n'
        'import { useRef, useEffect } from "react";\n'
        'export default function App() {\n'
        '  const ref = useRef(null);\n'
        '  useEffect(() => { d3.select(ref.current).append("circle").attr("r", 10); }, []);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>D3 Data Viz</h1>\n'
        '      <svg ref={ref} width={600} height={400}>\n'
        '        <g transform="translate(40,40)">\n'
        '          <rect width={200} height={150} fill="steelblue"/>\n'
        '        </g>\n'
        '      </svg>\n'
        '      <p>A custom D3 visualization rendered above.</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "dv", {"react": "19", "d3": "7.9"}, app)
        fs_state._session_last_project = "dv"
        fs_state._session_task_prompt = "d3 visualization"
        assert _check_deliverable_complete(str(ws)) is None


def test_chartjs_with_canvas_passes():
    app = (
        'import { Chart } from "chart.js";\n'
        'import { useRef } from "react";\n'
        'export default function App() {\n'
        '  const ref = useRef(null);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Chart.js Dashboard</h1>\n'
        '      <canvas ref={ref} width={600} height={400}/>\n'
        '      <p>Chart will render into the canvas above.</p>\n'
        '      <p>Interactive data display for session metrics.</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "cj", {"react": "19", "chart.js": "4.4"}, app)
        fs_state._session_last_project = "cj"
        fs_state._session_task_prompt = "dashboard"
        assert _check_deliverable_complete(str(ws)) is None


def test_vanilla_react_no_chart_lib_passes():
    """Regression: no chart lib in deps → gate doesn't fire even without charts."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  const [s, setS] = useState("");\n'
        '  const inc = () => setC(c + 1);\n'
        '  const dec = () => setC(c - 1);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Counter</h1>\n'
        '      <p>Value: {c}</p>\n'
        '      <button onClick={inc}>+</button>\n'
        '      <button onClick={dec}>-</button>\n'
        '      <input value={s} onChange={e => setS(e.target.value)}/>\n'
        '      <p>Text: {s}</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "counter", {"react": "19"}, app)
        fs_state._session_last_project = "counter"
        fs_state._session_task_prompt = "counter app"
        assert _check_deliverable_complete(str(ws)) is None


def test_victory_with_victorychart_passes():
    app = (
        'import { VictoryChart, VictoryLine } from "victory";\n'
        'export default function App() {\n'
        '  const data = [{x:1,y:2},{x:2,y:3},{x:3,y:5}];\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Victory Metrics</h1>\n'
        '      <VictoryChart>\n'
        '        <VictoryLine data={data}/>\n'
        '      </VictoryChart>\n'
        '      <p>Victory visualization with sample data</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "vic", {"react": "19", "victory": "37"}, app)
        fs_state._session_last_project = "vic"
        fs_state._session_task_prompt = "metrics chart"
        assert _check_deliverable_complete(str(ws)) is None


def test_plotly_without_chart_refused():
    """Plotly in deps, no <Plot> / <canvas> / <svg> → refuse."""
    app = (
        'import React from "react";\n'
        'export default function App() {\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Plotly Dashboard</h1>\n'
        '      <p>Interactive plot configuration UI placeholder panel here.</p>\n'
        '      <p>Bring your own data and the plot renders inline below.</p>\n'
        '      <p>More content to keep this over the 300-byte minimum.</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "pl", {"react": "19", "plotly.js": "2.30"}, app)
        fs_state._session_last_project = "pl"
        fs_state._session_task_prompt = "plotly dashboard"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "chart primitive" in r
        assert "plotly.js" in r


def test_recharts_devdependency_also_triggers():
    """Both dependencies and devDependencies count as "in deps"."""
    app = (
        'import React, { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  const [f, setF] = useState("all");\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Dashboard</h1>\n'
        '      <p>Total records: {c}</p>\n'
        '      <p>Current filter: {f}</p>\n'
        '      <button onClick={() => setC(c+1)}>Increment</button>\n'
        '      <button onClick={() => setF("new")}>Filter new</button>\n'
        '      <button onClick={() => setF("all")}>All</button>\n'
        '      <p>Content padding to keep this over the 300-byte minimum size.</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    import json as _json
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "workspace"
        d = ws / "deliverables" / "dev-dep"
        (d / "src").mkdir(parents=True)
        (d / "package.json").write_text(_json.dumps({
            "name": "x",
            "dependencies": {"react": "19"},
            "devDependencies": {"recharts": "2.15"},
        }))
        (d / "src" / "App.tsx").write_text(app)
        fs_state._session_last_project = "dev-dep"
        fs_state._session_task_prompt = "dashboard"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "chart primitive" in r
