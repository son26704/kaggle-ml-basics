from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "ppg_hr_micro_power_analysis.ipynb"


def lines(text: str) -> list[str]:
    text = dedent(text).strip("\n")
    return [f"{line}\n" for line in text.splitlines()]


def markdown_cell(text: str, cell_id: str) -> dict[str, object]:
    return {"cell_type": "markdown", "id": cell_id, "metadata": {}, "source": lines(text)}


def code_cell(text: str, cell_id: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "id": cell_id,
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": lines(text),
    }


def build_notebook() -> dict[str, object]:
    cells = [
        markdown_cell(
            """
            # PPG HR Micro Power Analysis

            Notebook này phân tích bộ log **V7 dual-MCU hardware sync** tại `log/pgg_hr_log_v7/`.

            Mục tiêu:
            - Đo **effective DAQ sampling interval** từ dữ liệu thật thay vì giả định theo cấu hình danh định
            - Ghép **target.csv** và **daq.csv** theo thứ tự burst để phân tích từng cửa sổ xử lý `HIGH`
            - Tích phân **total active energy** gồm cả **power tail**
            - Ước lượng riêng **TinyML invoke energy** bằng `invoke_time_us` từ target log
            - So sánh mức đóng góp năng lượng của **DSP/feature extraction** và **TinyML**
            """,
            "intro",
        ),
        code_cell(
            """
            import importlib
            import sys
            from pathlib import Path

            import matplotlib.pyplot as plt
            import pandas as pd

            PROJECT_ROOT = Path.cwd()
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))

            import ppg_hr_micro_analysis_lib as micro_lib
            micro_lib = importlib.reload(micro_lib)

            micro_lib.apply_publication_style()

            LOG_ROOT = PROJECT_ROOT / "log" / "pgg_hr_log_v7"
            OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "ppg_hr_micro_analysis_v7"
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            print("Project root:", PROJECT_ROOT)
            print("Log root:", LOG_ROOT)
            print("Output dir:", OUTPUT_DIR)
            """,
            "setup",
        ),
        code_cell(
            """
            analysis = micro_lib.analyze_dataset(LOG_ROOT)
            run_summary_df = analysis["run_summary"].copy()
            burst_df = analysis["burst_df"].copy()
            mode_summary_df = analysis["mode_summary"].copy()

            print(f"Loaded {len(run_summary_df)} runs.")
            display(run_summary_df.round(2))
            """,
            "load-data",
        ),
        code_cell(
            """
            display(mode_summary_df.round(2))

            slow_summary_df = mode_summary_df[mode_summary_df["slow_path_bursts"].fillna(0) > 0].copy()

            print("Key V7 findings")
            print(f"- Effective DAQ median interval: {mode_summary_df['dt_median_us'].mean():.1f} us")
            print(f"- Adaptive mean total active energy per burst: {slow_summary_df.loc[slow_summary_df['mode_name'] == 'adaptive', 'total_active_energy_uj_mean'].iloc[0]:.2f} uJ")
            print(f"- Fixed High mean total active energy per burst: {slow_summary_df.loc[slow_summary_df['mode_name'] == 'fixed_high', 'total_active_energy_uj_mean'].iloc[0]:.2f} uJ")
            print(f"- Adaptive weighted AI energy fraction: {slow_summary_df.loc[slow_summary_df['mode_name'] == 'adaptive', 'ai_energy_fraction_pct_weighted'].iloc[0]:.2f}%")
            print(f"- Fixed High weighted AI energy fraction: {slow_summary_df.loc[slow_summary_df['mode_name'] == 'fixed_high', 'ai_energy_fraction_pct_weighted'].iloc[0]:.2f}%")
            """,
            "summary",
        ),
        code_cell(
            """
            fig = micro_lib.plot_micro_energy_dashboard(mode_summary_df)
            fig.savefig(OUTPUT_DIR / "micro_energy_dashboard_v7.png", bbox_inches="tight")
            plt.show()
            """,
            "energy-dashboard",
        ),
        code_cell(
            """
            fig = micro_lib.plot_timing_resolution_dashboard(mode_summary_df)
            fig.savefig(OUTPUT_DIR / "micro_timing_resolution_v7.png", bbox_inches="tight")
            plt.show()
            """,
            "timing-dashboard",
        ),
        code_cell(
            """
            representative_burst = micro_lib.pick_representative_burst(
                burst_df,
                prefer_mode="fixed_high",
                require_infer_capture=True,
            )
            run_key = (representative_burst["mode_name"], representative_burst["run_name"])
            representative_run = analysis["runs"][run_key]

            print("Representative burst")
            display(representative_burst.to_frame().T.round(2))

            fig = micro_lib.plot_representative_burst(representative_burst, representative_run)
            fig.savefig(OUTPUT_DIR / "representative_burst_v7.png", bbox_inches="tight")
            plt.show()
            """,
            "representative-burst",
        ),
        code_cell(
            """
            burst_distribution_df = burst_df.copy()
            burst_distribution_df["mode_label"] = burst_distribution_df["mode_name"].map(micro_lib.MODE_LABELS)

            fig, ax = plt.subplots(figsize=(8.8, 4.8), constrained_layout=True)
            box_data = [
                burst_distribution_df.loc[burst_distribution_df["mode_name"] == mode, "total_active_energy_uj"].to_numpy()
                for mode in ["adaptive", "fixed_high"]
            ]
            ax.boxplot(
                box_data,
                labels=[micro_lib.MODE_LABELS["adaptive"], micro_lib.MODE_LABELS["fixed_high"]],
                patch_artist=True,
                boxprops={"facecolor": "#DBEAFE", "edgecolor": "#1D4ED8"},
                medianprops={"color": "#DC2626", "linewidth": 1.8},
            )
            ax.set_ylabel("Total active energy per burst (uJ)")
            ax.set_title("Burst Energy Distribution Across Slow-Path Modes")
            fig.savefig(OUTPUT_DIR / "burst_energy_distribution_v7.png", bbox_inches="tight")
            plt.show()
            """,
            "distribution",
        ),
        code_cell(
            """
            run_summary_df.to_csv(OUTPUT_DIR / "run_summary_v7.csv", index=False)
            burst_df.to_csv(OUTPUT_DIR / "burst_summary_v7.csv", index=False)
            mode_summary_df.to_csv(OUTPUT_DIR / "mode_summary_v7.csv", index=False)

            print("Saved CSV artifacts:")
            print("-", OUTPUT_DIR / "run_summary_v7.csv")
            print("-", OUTPUT_DIR / "burst_summary_v7.csv")
            print("-", OUTPUT_DIR / "mode_summary_v7.csv")
            """,
            "save-artifacts",
        ),
    ]

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    notebook = build_notebook()
    NOTEBOOK_PATH.write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
