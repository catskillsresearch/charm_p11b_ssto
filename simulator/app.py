"""Entry point: python -m simulator.app"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python -m simulator.app` from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from simulator.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("p11b-operator-twin")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
