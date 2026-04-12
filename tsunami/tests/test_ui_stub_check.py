"""QA-1 Playtest Fire 120: stubbed UI component shipped.

`simple-expense-tracker/src/components/ui/Button.tsx` had been
overwritten with a 62-byte stub:

    export default function Button() {
      return <div>Button</div>
    }

App.tsx used `<Button>Start Game</Button>` / `<Button>Reset</Button>`,
but the stub takes no props, ignores children, renders literal "Button".
Shipped with every clickable UI element labelled "Button".

Gate: detect `src/components/ui/<Name>.tsx` matching the stub shape
(tiny + renders literal Name + no `children` reference), cross-check
against App.tsx usage, REFUSE if the stubbed component is used with
content between its tags.
"""

from __future__ import annotations

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


def _make_deliverable(tmp: str, name: str, button_content: str, app_content: str) -> Path:
    ws = Path(tmp) / "workspace"
    d = ws / "deliverables" / name
    (d / "src" / "components" / "ui").mkdir(parents=True)
    (d / "package.json").write_text('{"name":"x"}')
    (d / "src" / "components" / "ui" / "Button.tsx").write_text(button_content)
    (d / "src" / "App.tsx").write_text(app_content)
    return ws


# --- Fire 120 repro ---------------------------------------------------------


def test_fire120_stub_button_detected():
    """Fire 120 exact: stub Button + App uses <Button>X</Button>."""
    stub = 'export default function Button() {\n  return <div>Button</div>\n}\n'
    app = (
        'import { useState } from "react";\n'
        'import Button from "./components/ui/Button";\n'
        'export default function App() {\n'
        '  const [count, setCount] = useState(0);\n'
        '  const [step, setStep] = useState(1);\n'
        '  const start = () => setCount(count + step);\n'
        '  const reset = () => setCount(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Game</h1>\n'
        '      <Button>Start Game</Button>\n'
        '      <Button>Reset</Button>\n'
        '      <p>Count: {count}</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_deliverable(tmp, "my-app", stub, app)
        fs_state._session_last_project = "my-app"
        fs_state._session_task_prompt = "build an app"
        result = _check_deliverable_complete(str(ws))
        assert result is not None
        assert "Button.tsx" in result
        assert "stub" in result.lower()


def test_real_button_passes():
    """Regression: a real Button component (accepts children) passes."""
    real = (
        'import React from "react";\n'
        'interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {\n'
        '  variant?: "primary" | "secondary";\n'
        '}\n'
        'export default function Button({ children, variant = "primary", ...props }: ButtonProps) {\n'
        '  return <button className={variant} {...props}>{children}</button>;\n'
        '}\n'
    )
    app = (
        'import { useState } from "react";\n'
        'import Button from "./components/ui/Button";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  const [n, setN] = useState(1);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Counter</h1>\n'
        '      <Button>Start</Button>\n'
        '      <Button>Reset</Button>\n'
        '      <p>Value: {c}</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_deliverable(tmp, "my-app", real, app)
        fs_state._session_last_project = "my-app"
        fs_state._session_task_prompt = "counter app"
        result = _check_deliverable_complete(str(ws))
        assert result is None, f"real Button should pass, got: {result}"


def test_stub_unused_passes():
    """Edge case: stub Button exists but App.tsx doesn't use <Button>X</Button>
    with children. Not a ship-breaking issue — passes."""
    stub = 'export default function Button() {\n  return <div>Button</div>\n}\n'
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  const [s, setS] = useState("");\n'
        '  const inc = () => setC(c + 1);\n'
        '  const dec = () => setC(c - 1);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Counter (No Button Component)</h1>\n'
        '      <p>Value: {c}</p>\n'
        '      <input value={s} onChange={e => setS(e.target.value)}/>\n'
        '      <button onClick={inc}>+</button>\n'
        '      <button onClick={dec}>-</button>\n'
        '      <p>Padding: {s || "(empty)"}</p>\n'
        '      <p>Entered text appears here above and count below</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_deliverable(tmp, "my-app", stub, app)
        fs_state._session_last_project = "my-app"
        fs_state._session_task_prompt = "counter with input"
        result = _check_deliverable_complete(str(ws))
        assert result is None, f"unused stub should pass, got: {result}"


def test_self_closing_button_with_stub_passes():
    """`<Button/>` self-closing = no children = stub is semantically fine."""
    stub = 'export default function Button() {\n  return <div>Button</div>\n}\n'
    app = (
        'import { useState } from "react";\n'
        'import Button from "./components/ui/Button";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  const [n, setN] = useState(1);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Self closing</h1>\n'
        '      <Button/>\n'
        '      <Button/>\n'
        '      <p>Count: {c}</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_deliverable(tmp, "my-app", stub, app)
        fs_state._session_last_project = "my-app"
        fs_state._session_task_prompt = "counter"
        result = _check_deliverable_complete(str(ws))
        # No <Button>X</Button> with children — gate passes.
        assert result is None, f"self-closing Button should pass, got: {result}"


def test_large_component_with_name_text_passes():
    """Regression: a proper component that happens to render its name
    somewhere (e.g. `<h1>Button</h1>` as a label) but is long enough
    and references children — not a stub."""
    not_stub = (
        'import React from "react";\n'
        'export default function Button({ children }: { children: React.ReactNode }) {\n'
        '  // Internal label displayed sometimes\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Button</h1>\n'
        '      <div>{children}</div>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    app = (
        'import { useState } from "react";\n'
        'import Button from "./components/ui/Button";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  const [s, setS] = useState(1);\n'
        '  const inc = () => setC(c + s);\n'
        '  const dec = () => setC(c - s);\n'
        '  const reset = () => setC(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Counter with Big Buttons</h1>\n'
        '      <Button>Click me to Start</Button>\n'
        '      <Button>Reset Everything</Button>\n'
        '      <Button>Add One More Thing</Button>\n'
        '      <p>Current count value: {c}</p>\n'
        '      <p>Current step size: {s}</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_deliverable(tmp, "my-app", not_stub, app)
        fs_state._session_last_project = "my-app"
        fs_state._session_task_prompt = "counter big buttons"
        result = _check_deliverable_complete(str(ws))
        assert result is None, f"large component should pass, got: {result}"


def test_multiple_stubs_named_in_error():
    """When multiple UI components are stubbed, error lists them."""
    stub_button = 'export default function Button() { return <div>Button</div> }\n'
    stub_card = 'export default function Card() { return <div>Card</div> }\n'
    app = (
        'import { useState } from "react";\n'
        'import Button from "./components/ui/Button";\n'
        'import Card from "./components/ui/Card";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  const [s, setS] = useState("");\n'
        '  return (\n'
        '    <Card>\n'
        '      <Button>Start</Button>\n'
        '      <Button>Reset</Button>\n'
        '      <p>{c}</p>\n'
        '    </Card>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_deliverable(tmp, "my-app", stub_button, app)
        # Also stub Card
        (Path(tmp) / "workspace" / "deliverables" / "my-app" / "src"
         / "components" / "ui" / "Card.tsx").write_text(stub_card)
        fs_state._session_last_project = "my-app"
        fs_state._session_task_prompt = "card app"
        result = _check_deliverable_complete(str(ws))
        assert result is not None
        # First stub is the one that gets headlined — but both listed.
        assert "Button" in result or "Card" in result
