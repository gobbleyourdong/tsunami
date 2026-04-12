"""QA-1 Playtest Fire 118: static JSX-import consistency check.

Deliverable shipped with `<Badge key={tip}>` in JSX body but no Badge
import. React throws at mount → blank page. tsc would have caught it
but that deliverable's package.json had `"build": "vite build"` (no
tsc prefix). This static check covers the scaffold-drift case where
typecheck is missing.
"""

from __future__ import annotations

from tsunami.jsx_import_check import find_undefined_jsx_components


def test_fire118_badge_missing_import_flagged():
    """Fire 118 exact shape: Card/Input/Button/Alert imported; Badge used."""
    content = (
        'import { useState } from "react";\n'
        'import { Card, Input, Button, Alert } from "./components/ui";\n'
        'export default function App() {\n'
        '  const [bill, setBill] = useState(0);\n'
        '  const tips = [10, 15, 20];\n'
        '  return (\n'
        '    <Card>\n'
        '      <Input value={bill} />\n'
        '      {tips.map(tip => <Badge key={tip}>{tip}%</Badge>)}\n'
        '      <Button>Calculate</Button>\n'
        '    </Card>\n'
        '  );\n'
        '}\n'
    )
    missing = find_undefined_jsx_components(content)
    assert missing == ["Badge"]


def test_all_imports_present_returns_empty():
    content = (
        'import { Card, Button } from "./components/ui";\n'
        'export default function App() {\n'
        '  return <Card><Button>Click</Button></Card>;\n'
        '}\n'
    )
    assert find_undefined_jsx_components(content) == []


def test_local_function_component_recognized():
    content = (
        'function MyButton({ children }) { return <button>{children}</button>; }\n'
        'export default function App() { return <MyButton>Click</MyButton>; }\n'
    )
    assert find_undefined_jsx_components(content) == []


def test_local_const_component_recognized():
    content = (
        'const Header = () => <h1>Title</h1>;\n'
        'export default function App() { return <Header/>; }\n'
    )
    assert find_undefined_jsx_components(content) == []


def test_class_component_recognized():
    content = (
        'class Counter extends React.Component { render() { return <div/>; } }\n'
        'export default function App() { return <Counter/>; }\n'
    )
    assert find_undefined_jsx_components(content) == []


def test_namespace_import_recognized():
    content = (
        'import * as UI from "./ui";\n'
        'export default function App() { return <UI.Button/>; }\n'
    )
    # `UI.Button` — we check the namespace root (`UI`) which IS imported.
    assert find_undefined_jsx_components(content) == []


def test_default_plus_named_import():
    content = (
        'import React, { Fragment } from "react";\n'
        'import DefaultBtn, { IconBtn } from "./btn";\n'
        'export default function App() {\n'
        '  return <><DefaultBtn/><IconBtn/></>;\n'
        '}\n'
    )
    assert find_undefined_jsx_components(content) == []


def test_as_alias_import():
    content = (
        'import { Foo as Bar } from "x";\n'
        'export default function App() { return <Bar/>; }\n'
    )
    assert find_undefined_jsx_components(content) == []


def test_react_intrinsic_fragment_passes():
    """`<Fragment>` is a React built-in; doesn't need explicit import."""
    content = (
        'import React from "react";\n'
        'export default function App() {\n'
        '  return <Fragment><div/></Fragment>;\n'
        '}\n'
    )
    assert find_undefined_jsx_components(content) == []


def test_multiple_undefined_components_all_flagged():
    content = (
        'export default function App() {\n'
        '  return <><Foo/><Bar/><Baz/></>;\n'
        '}\n'
    )
    missing = find_undefined_jsx_components(content)
    assert set(missing) == {"Foo", "Bar", "Baz"}


def test_html_tags_ignored():
    """Lowercase tags are HTML intrinsics — don't get checked."""
    content = (
        'export default function App() {\n'
        '  return <div><span><button>Hi</button></span></div>;\n'
        '}\n'
    )
    assert find_undefined_jsx_components(content) == []


def test_member_access_only_checks_root():
    """<Foo.Bar/> — only `Foo` needs to be in scope (Bar is a property)."""
    content = (
        'import { Foo } from "x";\n'
        'export default function App() { return <Foo.Bar/>; }\n'
    )
    assert find_undefined_jsx_components(content) == []


def test_empty_file_returns_empty():
    assert find_undefined_jsx_components("") == []


def test_no_jsx_returns_empty():
    content = 'export const add = (a, b) => a + b;\nexport default add;'
    assert find_undefined_jsx_components(content) == []


def test_closing_tag_not_double_counted():
    """<Foo>...</Foo> — opening and closing tags both match the pattern
    but we're just checking the set of names; deduping happens naturally."""
    content = (
        'import { Foo } from "x";\n'
        'export default function App() { return <Foo>content</Foo>; }\n'
    )
    assert find_undefined_jsx_components(content) == []


def test_typed_useState_component_recognized():
    """Regression: `const [x, setX] = useState<number>(0)` destructuring — the
    binding names aren't component definitions but shouldn't be mis-parsed
    as missing either."""
    content = (
        'import { useState } from "react";\n'
        'import { Card } from "./components/ui";\n'
        'export default function App() {\n'
        '  const [count, setCount] = useState<number>(0);\n'
        '  return <Card>{count}</Card>;\n'
        '}\n'
    )
    assert find_undefined_jsx_components(content) == []
