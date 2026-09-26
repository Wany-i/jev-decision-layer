"""Run the repository CLI from a linked Codex skill folder."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from decision import _main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(_main())
