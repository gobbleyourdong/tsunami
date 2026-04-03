"""Tests for Chunk 8: New Components Batch 1.

Verifies:
- Components exist as files
- Exported from index.ts
- Basic structural checks (interface definitions, default exports)
"""

from pathlib import Path

UI_DIR = Path(__file__).parent.parent.parent / "scaffolds" / "react-app" / "src" / "components" / "ui"


class TestComponentFilesExist:
    """All batch 1 component files present."""

    def test_rich_text_editor(self):
        assert (UI_DIR / "RichTextEditor.tsx").exists()

    def test_file_manager(self):
        assert (UI_DIR / "FileManager.tsx").exists()

    def test_command_palette(self):
        assert (UI_DIR / "CommandPalette.tsx").exists()

    def test_calendar(self):
        assert (UI_DIR / "Calendar.tsx").exists()


class TestExports:
    """Components exported from index.ts."""

    def test_all_exported(self):
        index = (UI_DIR / "index.ts").read_text()
        for name in ["RichTextEditor", "FileManager", "CommandPalette", "Calendar"]:
            assert name in index, f"{name} not exported"


class TestRichTextEditor:
    """RichTextEditor structural checks."""

    def test_has_toolbar_buttons(self):
        content = (UI_DIR / "RichTextEditor.tsx").read_text()
        assert "TOOLBAR_BUTTONS" in content

    def test_has_content_editable(self):
        content = (UI_DIR / "RichTextEditor.tsx").read_text()
        assert "contentEditable" in content

    def test_has_interface(self):
        content = (UI_DIR / "RichTextEditor.tsx").read_text()
        assert "interface RichTextEditorProps" in content

    def test_default_export(self):
        content = (UI_DIR / "RichTextEditor.tsx").read_text()
        assert "export default function RichTextEditor" in content

    def test_has_formatting_commands(self):
        content = (UI_DIR / "RichTextEditor.tsx").read_text()
        for cmd in ["bold", "italic", "underline"]:
            assert cmd in content


class TestFileManager:
    """FileManager structural checks."""

    def test_has_file_tree(self):
        content = (UI_DIR / "FileManager.tsx").read_text()
        assert "FileTree" in content

    def test_has_drag_drop(self):
        content = (UI_DIR / "FileManager.tsx").read_text()
        assert "onDrop" in content or "onDragOver" in content

    def test_has_rename(self):
        content = (UI_DIR / "FileManager.tsx").read_text()
        assert "onRename" in content

    def test_has_delete(self):
        content = (UI_DIR / "FileManager.tsx").read_text()
        assert "onDelete" in content

    def test_has_file_node_interface(self):
        content = (UI_DIR / "FileManager.tsx").read_text()
        assert "interface FileNode" in content


class TestCommandPalette:
    """CommandPalette structural checks."""

    def test_has_fuzzy_match(self):
        content = (UI_DIR / "CommandPalette.tsx").read_text()
        assert "fuzzyMatch" in content

    def test_has_keyboard_nav(self):
        content = (UI_DIR / "CommandPalette.tsx").read_text()
        assert "ArrowDown" in content
        assert "ArrowUp" in content

    def test_has_cmd_k_trigger(self):
        content = (UI_DIR / "CommandPalette.tsx").read_text()
        assert "metaKey" in content or "ctrlKey" in content

    def test_has_command_interface(self):
        content = (UI_DIR / "CommandPalette.tsx").read_text()
        assert "interface Command" in content

    def test_has_categories(self):
        content = (UI_DIR / "CommandPalette.tsx").read_text()
        assert "category" in content


class TestCalendar:
    """Calendar structural checks."""

    def test_has_month_navigation(self):
        content = (UI_DIR / "Calendar.tsx").read_text()
        assert "MONTHS" in content

    def test_has_day_names(self):
        content = (UI_DIR / "Calendar.tsx").read_text()
        assert "DAYS" in content

    def test_has_events(self):
        content = (UI_DIR / "Calendar.tsx").read_text()
        assert "CalendarEvent" in content

    def test_has_range_support(self):
        content = (UI_DIR / "Calendar.tsx").read_text()
        assert "rangeStart" in content
        assert "rangeEnd" in content

    def test_has_today_highlight(self):
        content = (UI_DIR / "Calendar.tsx").read_text()
        assert "isToday" in content

    def test_default_export(self):
        content = (UI_DIR / "Calendar.tsx").read_text()
        assert "export default function Calendar" in content
