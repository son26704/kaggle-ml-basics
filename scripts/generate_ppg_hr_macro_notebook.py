from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "ppg_hr_macro_analysis.ipynb"


def lines(text: str) -> list[str]:
    text = dedent(text).strip("\n")
    return [f"{line}\n" for line in text.splitlines()]


def markdown_cell(text: str) -> dict[str, object]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": lines(text),
    }


def code_cell(text: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": lines(text),
    }


def build_notebook() -> dict[str, object]:
    cells = [
        markdown_cell(
            """
            # PPG HR Macro-Level Analysis

            Notebook này phân tích log mixed-text từ ESP32 cho thesis:
            **Energy-Aware Adaptive TinyML Scheduling for Wearable Health Monitoring**.

            Mục tiêu chính:
            - So sánh **average power** giữa `adaptive`, `fixed_high`, `fixed_normal`
            - Tính **battery life** với pin `150 mAh, 3.7 V`
            - Đo **HR coverage**: thời gian có HR hợp lệ so với thời gian drop vì low quality / no contact
            - Đo **state occupancy** của chế độ `adaptive`
            - Vẽ **time-series publication-style** với phase shading và state shading

            Ghi chú phương pháp:
            - Coverage được tính trên **decision timeline** của scheduler, từ **decision window đầu tiên** đến cuối run
            - `Low quality` vẫn được xem là **covered** nếu cùng timestamp có `AI_ASSIST_HR` hoặc `DSP_HR`
            - `fixed_high` ưu tiên `AI_ASSIST_HR` làm output cuối cùng khi cùng lúc có cả `DSP_HR` và `AI_ASSIST_HR`
            """
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

            import ppg_hr_macro_analysis_lib as macro_lib
            macro_lib = importlib.reload(macro_lib)

            MODE_LABELS = macro_lib.MODE_LABELS
            add_battery_metrics = macro_lib.add_battery_metrics
            apply_publication_style = macro_lib.apply_publication_style
            format_summary_table = macro_lib.format_summary_table
            load_all_runs = macro_lib.load_all_runs
            pick_representative_run = macro_lib.pick_representative_run
            plot_phase_coverage = macro_lib.plot_phase_coverage
            plot_phase_power = macro_lib.plot_phase_power
            plot_representative_run = macro_lib.plot_representative_run
            plot_summary_dashboard = macro_lib.plot_summary_dashboard
            plot_tradeoff_scatter = macro_lib.plot_tradeoff_scatter

            apply_publication_style()

            LOG_ROOT = PROJECT_ROOT / "log" / "pgg_hr_log"
            OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "ppg_hr_macro_analysis"
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            BATTERY_MAH = 150.0
            BATTERY_V = 3.7

            print("Project root:", PROJECT_ROOT)
            print("Log root:", LOG_ROOT)
            print("Output dir:", OUTPUT_DIR)
            """
        ),
        code_cell(
            """
            analysis = load_all_runs(LOG_ROOT)
            run_summary_df = analysis["run_summary"].copy()
            mode_summary_df = add_battery_metrics(analysis["mode_summary"].copy(), BATTERY_MAH, BATTERY_V)
            phase_mode_summary_df = analysis["phase_mode_summary"].copy()
            phase_power_mode_summary_df = analysis["phase_power_mode_summary"].copy()

            print(f"Loaded {len(run_summary_df)} runs across {run_summary_df['mode'].nunique()} modes.")
            display(run_summary_df.sort_values(["mode", "file_name"]).reset_index(drop=True))
            """
        ),
        code_cell(
            """
            thesis_summary_df = format_summary_table(mode_summary_df)
            display(thesis_summary_df.round(2))

            adaptive_row = mode_summary_df.loc[mode_summary_df["mode"] == "adaptive"].iloc[0]
            fixed_high_row = mode_summary_df.loc[mode_summary_df["mode"] == "fixed_high"].iloc[0]
            fixed_normal_row = mode_summary_df.loc[mode_summary_df["mode"] == "fixed_normal"].iloc[0]

            print("Adaptive vs Fixed High")
            print(f"- Average power saving: {adaptive_row['power_saving_vs_fixed_high_pct']:.2f}%")
            print(f"- Battery life extension: {adaptive_row['battery_extension_vs_fixed_high_pct']:.2f}%")
            print(f"- Adaptive HR coverage: {adaptive_row['coverage_pct']:.2f}%")
            print(f"- Fixed High HR coverage: {fixed_high_row['coverage_pct']:.2f}%")
            print(f"- Fixed Normal HR coverage: {fixed_normal_row['coverage_pct']:.2f}%")
            print(f"- Adaptive occupancy: State 0 = {adaptive_row['state_0_pct']:.2f}%, State 1 = {adaptive_row['state_1_pct']:.2f}%")
            """
        ),
        code_cell(
            """
            summary_fig = plot_summary_dashboard(mode_summary_df)
            summary_fig.savefig(OUTPUT_DIR / "macro_summary_dashboard.png", bbox_inches="tight")
            plt.show()
            """
        ),
        markdown_cell(
            """
            ## Phase-Specific Power Analysis

            Mục tiêu của section này là kiểm tra trực tiếp giả thuyết hệ thống:
            - `adaptive` nên gần `fixed_normal` trong hai pha nghỉ
            - `adaptive` nên tăng lên gần `fixed_high` trong pha motion, vì scheduler wake TinyML và tăng sampling rate lên `100 Hz`
            """
        ),
        code_cell(
            """
            phase_power_pivot = (
                phase_power_mode_summary_df
                .pivot(index="mode", columns="phase", values="avg_power_mw")
                .rename(index=MODE_LABELS)
            )
            display(phase_power_pivot.round(2))
            """
        ),
        code_cell(
            """
            for phase_name in ["Rest 1", "Motion", "Rest 2"]:
                phase_slice = (
                    phase_power_mode_summary_df[phase_power_mode_summary_df["phase"] == phase_name]
                    .sort_values("mode")
                    .copy()
                )
                print(phase_name)
                for row in phase_slice.itertuples(index=False):
                    print(f"- {MODE_LABELS[row.mode]}: {row.avg_power_mw:.2f} mW")
                print()
            """
        ),
        code_cell(
            """
            phase_power_fig = plot_phase_power(phase_power_mode_summary_df)
            phase_power_fig.savefig(OUTPUT_DIR / "power_by_phase.png", bbox_inches="tight")
            plt.show()
            """
        ),
        code_cell(
            """
            display(phase_mode_summary_df.round(2))

            phase_fig = plot_phase_coverage(phase_mode_summary_df)
            phase_fig.savefig(OUTPUT_DIR / "coverage_by_phase.png", bbox_inches="tight")
            plt.show()
            """
        ),
        markdown_cell(
            """
            ## Trade-off Analysis

            Scatter plot này gom toàn bộ macro result vào một hình duy nhất:
            - Trục X: công suất trung bình, càng thấp càng tốt
            - Trục Y: HR coverage, càng cao càng tốt
            - `adaptive` nên nằm giữa hai baseline và đóng vai trò là điểm trade-off thực tế
            """
        ),
        code_cell(
            """
            tradeoff_fig = plot_tradeoff_scatter(mode_summary_df, phase_mode_summary_df)
            tradeoff_fig.savefig(OUTPUT_DIR / "power_vs_coverage_tradeoff.png", bbox_inches="tight")
            plt.show()
            """
        ),
        code_cell(
            """
            representative_files = {
                mode: pick_representative_run(run_summary_df, mode)
                for mode in ["adaptive", "fixed_high", "fixed_normal"]
            }
            representative_files
            """
        ),
        code_cell(
            """
            for mode, file_name in representative_files.items():
                parsed_run = analysis["runs"][(mode, file_name)]
                fig = plot_representative_run(
                    parsed_run,
                    mode_label=MODE_LABELS[mode],
                    title=f"{MODE_LABELS[mode]}: {file_name}",
                )
                fig.savefig(OUTPUT_DIR / f"{mode}_{Path(file_name).stem}_timeseries.png", bbox_inches="tight")
                plt.show()
            """
        ),
        markdown_cell(
            """
            ## Thesis Interpretation Checklist

            Khi viết chương kết quả, có thể dùng trực tiếp các insight sau:
            - `adaptive` so với `fixed_high`: giảm power trung bình bao nhiêu phần trăm, đổi lại coverage giữ được ở mức nào
            - `fixed_normal` thường sụt coverage rõ nhất ở pha `Motion`, cho thấy DSP-only không đủ robust
            - `adaptive` nếu coverage gần `fixed_high` nhưng power gần `fixed_normal` hơn, đó là bằng chứng chính cho scheduler
            - `state_0_pct` và `state_1_pct` là bằng chứng vi mô cho việc scheduler chỉ wake TinyML khi cần
            """
        ),
        markdown_cell(
            """
            ## Why The Coverage Gap Is Expected

            Khoảng cách coverage giữa `adaptive` và `fixed_high` trong notebook này **không nên được diễn giải là failure của scheduler**.

            Thay vào đó, nó phản ánh đúng trade-off đã được thiết kế trong firmware:

            1. **Intentional rigorous quality gating**

            Scheduler đang dùng quality gate khá chặt. Khi window bị nghi ngờ là không đủ tin cậy, firmware chọn **drop output** thay vì phát ra một HR có khả năng sai lớn. Vì vậy coverage giảm, nhưng đổi lại thesis có thể lập luận rằng hệ thống ưu tiên **trustworthiness** hơn là ép coverage bằng mọi giá.

            2. **Hardware switching cost**

            Khi hệ thống chuyển từ `50 Hz / DSP` sang `100 Hz / TinyML`, cảm biến và pipeline cần một khoảng ngắn để ổn định lại. Những window ngay sau transition thường bị ảnh hưởng bởi transient noise, FIFO disturbance, hoặc biên độ chưa ổn định. Đây là chi phí vật lý thực tế của adaptive scheduling trên embedded hardware, không phải artifact của phân tích offline.

            Kết luận: `adaptive` hy sinh một phần coverage để đạt hai mục tiêu hệ thống quan trọng hơn:
            - giảm công suất trung bình và kéo dài thời lượng pin
            - tránh phát HR không chắc chắn trong giai đoạn chuyển mode và motion artifact nặng
            """
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
    print(f"Wrote notebook: {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
