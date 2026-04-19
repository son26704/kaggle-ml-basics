import subprocess
import sys
import traceback
from pathlib import Path

import nbformat


NOTEBOOK_PATH = Path("ppg_dalia.ipynb")
SKIP_CELLS = {
    1,  # pip install packages
    4,  # kaggle download
    12,  # baseline RF with n_jobs
    14,  # CV RF with n_jobs
    15,  # scheduling RF with n_jobs
    16,  # difficulty RF with n_jobs
    17,  # model zoo with RF
    18,  # plots that depend on skipped baseline vars
}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    from IPython.display import display

    nb = nbformat.read(NOTEBOOK_PATH.open("r", encoding="utf-8"), as_version=4)

    env = {
        "__name__": "__main__",
        "__file__": str(NOTEBOOK_PATH.resolve()),
        "display": display,
        "subprocess": subprocess,
        "sys": sys,
    }

    preamble = "import sys\nimport subprocess\nprint('Notebook sequential executor started')"
    exec(compile(preamble, f"{NOTEBOOK_PATH}::preamble", "exec"), env)

    for idx, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        if idx in SKIP_CELLS:
            print(f"--- Skipping cell {idx} ---")
            continue

        print(f"=== Executing cell {idx} ===")
        try:
            exec(compile(cell.source, f"{NOTEBOOK_PATH}::cell_{idx}", "exec"), env)
        except Exception:
            print(f"Execution failed at cell {idx}")
            traceback.print_exc()
            raise

    print("Notebook sequential execution completed.")


if __name__ == "__main__":
    main()
