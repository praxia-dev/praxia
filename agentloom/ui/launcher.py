"""Entry point that the `agentloom-ui` console script binds to."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    app_path = Path(__file__).parent / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
