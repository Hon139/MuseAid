"""Entry point for the music production app.

Locates the project root, loads the example sequence, and launches the GUI.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from .app import MainWindow
from .generate_samples import generate_all_samples


def find_project_root() -> Path:
    """Walk up from this file to find the directory containing pyproject.toml."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback: cwd or cwd/Composition_App when run from parent repo
    cwd = Path.cwd()
    if (cwd / "Composition_App" / "pyproject.toml").exists():
        return cwd / "Composition_App"
    return cwd

def main() -> None:
    """Launch the music app."""
    root = find_project_root()
    data_dir = root / "data"
    example_path = root / "examples" / "c_major_scale.json"

    # Auto-generate placeholder samples if the data directory is empty or missing
    if not data_dir.exists() or not any(data_dir.iterdir()):
        print("No samples found — generating placeholder sine waves...")
        generate_all_samples(data_dir)

    app = QApplication(sys.argv)
    app.setApplicationName("Music App")

    # Force light theme regardless of OS dark mode
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #ffffff;
            color: #222222;
        }
        QLabel {
            background-color: #ffffff;
            color: #333333;
        }
        QStatusBar {
            background-color: #f0f0f0;
            color: #333333;
        }
    """)

    window = MainWindow(data_dir=data_dir, example_path=example_path)

    # Ensure cleanup also runs when the app exits without a window close event
    # (e.g. process-level quit requests).
    app.aboutToQuit.connect(window._shutdown)


    #TODO CHANGE
    window.showFullScreen()
    #window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
