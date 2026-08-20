"""Main entry point for the Fidget desktop music studio.

The same executable serves two roles. Launched normally it opens the desktop
window; launched with ``--serve`` it runs the FastAPI controller instead. A
frozen build cannot spawn ``python -m fidget.backend.server`` for the
controller -- it has no interpreter to call -- so the window re-launches this
executable in controller mode, preserving the two-process design.
"""

import multiprocessing
import sys


def main() -> None:
    if "--serve" in sys.argv:
        sys.argv.remove("--serve")
        from backend.server import main as serve

        serve()
        return

    from backend.desktop import run_desktop

    run_desktop()


if __name__ == "__main__":
    # Required before any child process is created in a frozen build; without
    # it a spawned child re-runs this module from the top.
    multiprocessing.freeze_support()
    main()
