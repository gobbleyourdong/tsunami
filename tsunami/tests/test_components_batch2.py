"""Tests for Chunk 9: New Components Batch 2.

Verifies:
- Components exist as files
- Exported from index.ts
- Structural checks (interfaces, default exports, key features)
"""

from pathlib import Path

UI_DIR = Path(__file__).parent.parent.parent / "scaffolds" / "react-app" / "src" / "components" / "ui"


class TestComponentFilesExist:
    """All batch 2 component files present."""

    def test_map_view(self):
        assert (UI_DIR / "MapView.tsx").exists()

    def test_notification_center(self):
        assert (UI_DIR / "NotificationCenter.tsx").exists()

    def test_audio_player(self):
        assert (UI_DIR / "AudioPlayer.tsx").exists()

    def test_video_player(self):
        assert (UI_DIR / "VideoPlayer.tsx").exists()


class TestExports:
    """Components exported from index.ts."""

    def test_all_exported(self):
        index = (UI_DIR / "index.ts").read_text()
        for name in ["MapView", "NotificationCenter", "AudioPlayer", "VideoPlayer"]:
            assert name in index, f"{name} not exported"


class TestMapView:
    """MapView structural checks."""

    def test_has_marker_interface(self):
        content = (UI_DIR / "MapView.tsx").read_text()
        assert "interface Marker" in content

    def test_has_leaflet_import(self):
        content = (UI_DIR / "MapView.tsx").read_text()
        assert "leaflet" in content

    def test_has_tile_layer(self):
        content = (UI_DIR / "MapView.tsx").read_text()
        assert "tileLayer" in content or "TileLayer" in content

    def test_has_popup_support(self):
        content = (UI_DIR / "MapView.tsx").read_text()
        assert "popup" in content.lower()

    def test_has_fallback_error(self):
        content = (UI_DIR / "MapView.tsx").read_text()
        assert "not installed" in content.lower() or "error" in content.lower()

    def test_default_export(self):
        content = (UI_DIR / "MapView.tsx").read_text()
        assert "export default function MapView" in content


class TestNotificationCenter:
    """NotificationCenter structural checks."""

    def test_has_notification_interface(self):
        content = (UI_DIR / "NotificationCenter.tsx").read_text()
        assert "interface Notification" in content

    def test_has_toast_component(self):
        content = (UI_DIR / "NotificationCenter.tsx").read_text()
        assert "Toast" in content

    def test_has_notification_types(self):
        content = (UI_DIR / "NotificationCenter.tsx").read_text()
        for t in ["info", "success", "warning", "error"]:
            assert t in content

    def test_has_action_button(self):
        content = (UI_DIR / "NotificationCenter.tsx").read_text()
        assert "action" in content

    def test_has_position_options(self):
        content = (UI_DIR / "NotificationCenter.tsx").read_text()
        assert "top-right" in content
        assert "bottom-left" in content

    def test_has_auto_dismiss(self):
        content = (UI_DIR / "NotificationCenter.tsx").read_text()
        assert "duration" in content

    def test_default_export(self):
        content = (UI_DIR / "NotificationCenter.tsx").read_text()
        assert "export default function NotificationCenter" in content


class TestAudioPlayer:
    """AudioPlayer structural checks."""

    def test_has_track_interface(self):
        content = (UI_DIR / "AudioPlayer.tsx").read_text()
        assert "interface Track" in content

    def test_has_audio_element(self):
        content = (UI_DIR / "AudioPlayer.tsx").read_text()
        assert "<audio" in content

    def test_has_play_pause(self):
        content = (UI_DIR / "AudioPlayer.tsx").read_text()
        assert "togglePlay" in content

    def test_has_progress_bar(self):
        content = (UI_DIR / "AudioPlayer.tsx").read_text()
        assert "progress" in content.lower()

    def test_has_volume_control(self):
        content = (UI_DIR / "AudioPlayer.tsx").read_text()
        assert "volume" in content.lower()

    def test_has_playlist(self):
        content = (UI_DIR / "AudioPlayer.tsx").read_text()
        assert "tracks" in content
        assert "currentTrack" in content

    def test_has_time_display(self):
        content = (UI_DIR / "AudioPlayer.tsx").read_text()
        assert "formatTime" in content

    def test_default_export(self):
        content = (UI_DIR / "AudioPlayer.tsx").read_text()
        assert "export default function AudioPlayer" in content


class TestVideoPlayer:
    """VideoPlayer structural checks."""

    def test_has_video_element(self):
        content = (UI_DIR / "VideoPlayer.tsx").read_text()
        assert "<video" in content

    def test_has_controls(self):
        content = (UI_DIR / "VideoPlayer.tsx").read_text()
        assert "togglePlay" in content

    def test_has_picture_in_picture(self):
        content = (UI_DIR / "VideoPlayer.tsx").read_text()
        assert "pictureInPicture" in content.lower() or "PiP" in content

    def test_has_fullscreen(self):
        content = (UI_DIR / "VideoPlayer.tsx").read_text()
        assert "fullscreen" in content.lower()

    def test_has_subtitles_support(self):
        content = (UI_DIR / "VideoPlayer.tsx").read_text()
        assert "subtitles" in content

    def test_has_progress_seek(self):
        content = (UI_DIR / "VideoPlayer.tsx").read_text()
        assert "seek" in content

    def test_has_volume_and_mute(self):
        content = (UI_DIR / "VideoPlayer.tsx").read_text()
        assert "volume" in content
        assert "muted" in content

    def test_default_export(self):
        content = (UI_DIR / "VideoPlayer.tsx").read_text()
        assert "export default function VideoPlayer" in content


class TestComponentCount:
    """Total component library count."""

    def test_total_ui_components(self):
        """Should now have 28+ UI components (24 original + 4 batch1 + 4 batch2)."""
        tsx_files = list(UI_DIR.glob("*.tsx"))
        assert len(tsx_files) >= 29  # 25 original + 4 + 4 = 33
