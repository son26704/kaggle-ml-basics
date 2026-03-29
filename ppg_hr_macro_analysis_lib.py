from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


TELEMETRY_COLUMNS = [
    "timestamp_ms",
    "state",
    "profile",
    "quality",
    "diff",
    "red",
    "ir",
    "bus_v",
    "current_ma",
    "power_mw",
]

TELEMETRY_RE = re.compile(
    r"^(?P<timestamp_ms>\d+),(?P<state>\d+),(?P<profile>\d+),(?P<quality>-?\d+),"
    r"(?P<diff>-?\d+(?:\.\d+)?),(?P<red>\d+),(?P<ir>\d+),"
    r"(?P<bus_v>-?\d+(?:\.\d+)?),(?P<current_ma>-?\d+(?:\.\d+)?),"
    r"(?P<power_mw>-?\d+(?:\.\d+)?)$"
)
LOG_LINE_RE = re.compile(r"^(?P<level>[IWE]) \((?P<timestamp_ms>\d+)\) PPG_TINYML: (?P<body>.+)$")
STATE_RE = re.compile(r"Scheduler state -> (?P<label>NORMAL|HIGH)\((?P<profile>\d+)sps\)")
HR_RE = re.compile(r"(?P<kind>DSP_HR|AI_ASSIST_HR)=(?P<hr>-?\d+(?:\.\d+)?)")
STATE_ID_RE = re.compile(r"state=(?P<state>\d+)")
PHASES = [
    ("Rest 1", 0.0, 60.0, "#E6EEF7"),
    ("Motion", 60.0, 120.0, "#FBE7D3"),
    ("Rest 2", 120.0, 180.0, "#E6EEF7"),
]
STATE_COLORS = {0: "#2E8B57", 1: "#E67E22"}
MODE_ORDER = ["adaptive", "fixed_high", "fixed_normal"]
MODE_LABELS = {
    "adaptive": "Adaptive",
    "fixed_high": "Fixed High",
    "fixed_normal": "Fixed Normal",
}


def apply_publication_style() -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 220,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#3C4043",
            "axes.labelcolor": "#202124",
            "axes.titleweight": "bold",
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "grid.color": "#DADCE0",
            "grid.alpha": 0.55,
            "font.size": 10.5,
            "legend.frameon": True,
            "legend.facecolor": "white",
            "legend.edgecolor": "#DADCE0",
            "lines.linewidth": 2.0,
        }
    )


def _coerce_numeric_frame(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def parse_log_file(path: Path) -> dict[str, object]:
    telemetry_rows: list[dict[str, object]] = []
    hr_rows: list[dict[str, object]] = []
    dropout_rows: list[dict[str, object]] = []
    transition_rows: list[dict[str, object]] = []

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue

            telemetry_match = TELEMETRY_RE.match(line)
            if telemetry_match:
                row = telemetry_match.groupdict()
                row["source"] = path.name
                telemetry_rows.append(row)
                continue

            log_match = LOG_LINE_RE.match(line)
            if not log_match:
                continue

            ts_ms = int(log_match.group("timestamp_ms"))
            body = log_match.group("body")
            state_id_match = STATE_ID_RE.search(body)
            state_id = int(state_id_match.group("state")) if state_id_match else None

            state_match = STATE_RE.search(body)
            if state_match:
                transition_rows.append(
                    {
                        "timestamp_ms": ts_ms,
                        "state": 0 if state_match.group("label") == "NORMAL" else 1,
                        "state_label": state_match.group("label"),
                        "profile_sps": int(state_match.group("profile")),
                        "source": path.name,
                    }
                )
                continue

            hr_match = HR_RE.search(body)
            if hr_match:
                hr_rows.append(
                    {
                        "timestamp_ms": ts_ms,
                        "hr_bpm": float(hr_match.group("hr")),
                        "hr_kind": hr_match.group("kind"),
                        "state": state_id,
                        "source": path.name,
                    }
                )
                continue

            if "Low quality window" in body:
                dropout_rows.append(
                    {
                        "timestamp_ms": ts_ms,
                        "dropout_kind": "low_quality",
                        "state": state_id,
                        "source": path.name,
                    }
                )
                continue

            if "NO_CONTACT" in body:
                dropout_rows.append(
                    {
                        "timestamp_ms": ts_ms,
                        "dropout_kind": "no_contact",
                        "state": state_id,
                        "source": path.name,
                    }
                )

    telemetry_df = pd.DataFrame(telemetry_rows, columns=TELEMETRY_COLUMNS + ["source"])
    if not telemetry_df.empty:
        telemetry_df = _coerce_numeric_frame(telemetry_df, TELEMETRY_COLUMNS)
        telemetry_df = telemetry_df.sort_values("timestamp_ms").reset_index(drop=True)
        telemetry_df["elapsed_s"] = telemetry_df["timestamp_ms"] / 1000.0

    hr_df = pd.DataFrame(hr_rows)
    if not hr_df.empty:
        hr_df = _coerce_numeric_frame(hr_df, ["timestamp_ms", "hr_bpm", "state"])
        hr_df = hr_df.sort_values(["timestamp_ms", "hr_kind"]).reset_index(drop=True)
        hr_df["elapsed_s"] = hr_df["timestamp_ms"] / 1000.0

    dropout_df = pd.DataFrame(dropout_rows)
    if not dropout_df.empty:
        dropout_df = _coerce_numeric_frame(dropout_df, ["timestamp_ms", "state"])
        dropout_df = dropout_df.sort_values("timestamp_ms").reset_index(drop=True)
        dropout_df["elapsed_s"] = dropout_df["timestamp_ms"] / 1000.0

    transition_df = pd.DataFrame(transition_rows)
    if not transition_df.empty:
        transition_df = _coerce_numeric_frame(transition_df, ["timestamp_ms", "state", "profile_sps"])
        transition_df = transition_df.sort_values("timestamp_ms").reset_index(drop=True)
        transition_df["elapsed_s"] = transition_df["timestamp_ms"] / 1000.0

    all_times = []
    for df in (telemetry_df, hr_df, dropout_df, transition_df):
        if not df.empty:
            all_times.extend(df["timestamp_ms"].tolist())
    end_ms = int(max(all_times)) if all_times else 0

    decision_df = build_decision_timeline(hr_df, dropout_df, end_ms=end_ms)
    run_summary = summarize_run(path, telemetry_df, decision_df, transition_df, end_ms)

    return {
        "telemetry": telemetry_df,
        "hr_events": hr_df,
        "dropouts": dropout_df,
        "transitions": transition_df,
        "decisions": decision_df,
        "summary": run_summary,
    }


def build_decision_timeline(hr_df: pd.DataFrame, dropout_df: pd.DataFrame, end_ms: int) -> pd.DataFrame:
    timestamps = sorted(set(hr_df.get("timestamp_ms", pd.Series(dtype=float)).tolist()) | set(dropout_df.get("timestamp_ms", pd.Series(dtype=float)).tolist()))
    decisions: list[dict[str, object]] = []

    for ts_ms in timestamps:
        hr_slice = hr_df[hr_df["timestamp_ms"] == ts_ms] if not hr_df.empty else pd.DataFrame()
        dropout_slice = dropout_df[dropout_df["timestamp_ms"] == ts_ms] if not dropout_df.empty else pd.DataFrame()

        has_ai = not hr_slice.empty and (hr_slice["hr_kind"] == "AI_ASSIST_HR").any()
        if has_ai:
            chosen = hr_slice[hr_slice["hr_kind"] == "AI_ASSIST_HR"].iloc[0]
        elif not hr_slice.empty:
            chosen = hr_slice.iloc[0]
        else:
            chosen = None

        valid = chosen is not None
        state_value = None
        if valid and not pd.isna(chosen["state"]):
            state_value = int(chosen["state"])
        elif not dropout_slice.empty and not pd.isna(dropout_slice.iloc[0]["state"]):
            state_value = int(dropout_slice.iloc[0]["state"])

        decisions.append(
            {
                "timestamp_ms": int(ts_ms),
                "elapsed_s": ts_ms / 1000.0,
                "valid_hr": bool(valid),
                "hr_bpm": float(chosen["hr_bpm"]) if valid else np.nan,
                "output_kind": chosen["hr_kind"] if valid else None,
                "dropout_kind": None if valid or dropout_slice.empty else dropout_slice.iloc[0]["dropout_kind"],
                "state": state_value,
            }
        )

    decision_df = pd.DataFrame(decisions)
    if decision_df.empty:
        return decision_df

    decision_df = decision_df.sort_values("timestamp_ms").reset_index(drop=True)
    next_ts = decision_df["timestamp_ms"].shift(-1).fillna(end_ms)
    decision_df["interval_ms"] = (next_ts - decision_df["timestamp_ms"]).clip(lower=0)
    decision_df["interval_s"] = decision_df["interval_ms"] / 1000.0
    return decision_df


def time_weighted_mean(df: pd.DataFrame, value_col: str, time_col: str, end_ms: int) -> float:
    if df.empty:
        return float("nan")
    ordered = df.sort_values(time_col).reset_index(drop=True)
    next_ts = ordered[time_col].shift(-1).fillna(end_ms)
    duration_ms = (next_ts - ordered[time_col]).clip(lower=0)
    if duration_ms.sum() <= 0:
        return float(ordered[value_col].mean())
    return float(np.average(ordered[value_col], weights=duration_ms))


def summarize_run(
    path: Path,
    telemetry_df: pd.DataFrame,
    decision_df: pd.DataFrame,
    transition_df: pd.DataFrame,
    end_ms: int,
) -> dict[str, object]:
    mode = path.parent.name
    power_mean_mw = time_weighted_mean(telemetry_df, "power_mw", "timestamp_ms", end_ms)

    coverage_start_ms = int(decision_df["timestamp_ms"].min()) if not decision_df.empty else 0
    coverage_total_s = float(decision_df["interval_s"].sum()) if not decision_df.empty else 0.0
    covered_s = float(decision_df.loc[decision_df["valid_hr"], "interval_s"].sum()) if not decision_df.empty else 0.0
    dropped_s = float(decision_df.loc[~decision_df["valid_hr"], "interval_s"].sum()) if not decision_df.empty else 0.0

    state_segments = build_state_segments(transition_df, end_ms)
    adaptive_state_0_s = float(state_segments.loc[state_segments["state"] == 0, "duration_s"].sum()) if not state_segments.empty else math.nan
    adaptive_state_1_s = float(state_segments.loc[state_segments["state"] == 1, "duration_s"].sum()) if not state_segments.empty else math.nan
    state_total_s = float(state_segments["duration_s"].sum()) if not state_segments.empty else math.nan

    return {
        "mode": mode,
        "file_name": path.name,
        "run_duration_s": end_ms / 1000.0,
        "telemetry_points": int(len(telemetry_df)),
        "decision_points": int(len(decision_df)),
        "avg_power_mw": power_mean_mw,
        "coverage_start_s": coverage_start_ms / 1000.0,
        "coverage_total_s": coverage_total_s,
        "covered_s": covered_s,
        "dropped_s": dropped_s,
        "coverage_pct": 100.0 * covered_s / coverage_total_s if coverage_total_s > 0 else np.nan,
        "state_0_s": adaptive_state_0_s,
        "state_1_s": adaptive_state_1_s,
        "state_total_s": state_total_s,
        "state_0_pct": 100.0 * adaptive_state_0_s / state_total_s if state_total_s and state_total_s > 0 else np.nan,
        "state_1_pct": 100.0 * adaptive_state_1_s / state_total_s if state_total_s and state_total_s > 0 else np.nan,
    }


def build_state_segments(transition_df: pd.DataFrame, end_ms: int) -> pd.DataFrame:
    if transition_df.empty:
        return pd.DataFrame(columns=["state", "start_s", "end_s", "duration_s"])

    ordered = transition_df.sort_values("timestamp_ms").reset_index(drop=True).copy()
    next_ts = ordered["timestamp_ms"].shift(-1).fillna(end_ms)
    ordered["start_s"] = ordered["timestamp_ms"] / 1000.0
    ordered["end_s"] = next_ts / 1000.0
    ordered["duration_s"] = (ordered["end_s"] - ordered["start_s"]).clip(lower=0)
    return ordered[["state", "state_label", "start_s", "end_s", "duration_s"]]


def split_interval_by_phase(start_s: float, end_s: float) -> list[dict[str, float | str]]:
    spans: list[dict[str, float | str]] = []
    for phase_name, phase_start, phase_end, _ in PHASES:
        left = max(start_s, phase_start)
        right = min(end_s, phase_end)
        if right > left:
            spans.append({"phase": phase_name, "duration_s": right - left})
    return spans


def summarize_phase_coverage(decision_df: pd.DataFrame) -> pd.DataFrame:
    if decision_df.empty:
        return pd.DataFrame(columns=["phase", "covered_s", "dropped_s", "total_s", "coverage_pct"])

    rows: list[dict[str, object]] = []
    for decision in decision_df.itertuples(index=False):
        end_s = float(decision.elapsed_s + decision.interval_s)
        for span in split_interval_by_phase(float(decision.elapsed_s), end_s):
            rows.append(
                {
                    "phase": span["phase"],
                    "covered_s": span["duration_s"] if decision.valid_hr else 0.0,
                    "dropped_s": 0.0 if decision.valid_hr else span["duration_s"],
                }
            )

    phase_df = pd.DataFrame(rows)
    if phase_df.empty:
        return pd.DataFrame(columns=["phase", "covered_s", "dropped_s", "total_s", "coverage_pct"])

    summary = phase_df.groupby("phase", as_index=False)[["covered_s", "dropped_s"]].sum()
    summary["total_s"] = summary["covered_s"] + summary["dropped_s"]
    summary["coverage_pct"] = 100.0 * summary["covered_s"] / summary["total_s"]
    return summary


def summarize_phase_power(telemetry_df: pd.DataFrame, end_ms: int) -> pd.DataFrame:
    if telemetry_df.empty:
        return pd.DataFrame(columns=["phase", "energy_mws", "duration_s", "avg_power_mw"])

    ordered = telemetry_df.sort_values("timestamp_ms").reset_index(drop=True).copy()
    next_ts = ordered["timestamp_ms"].shift(-1).fillna(end_ms)
    ordered["interval_end_ms"] = next_ts

    rows: list[dict[str, object]] = []
    for sample in ordered.itertuples(index=False):
        start_s = float(sample.timestamp_ms) / 1000.0
        end_s = float(sample.interval_end_ms) / 1000.0
        if end_s <= start_s:
            continue
        for span in split_interval_by_phase(start_s, end_s):
            duration_s = float(span["duration_s"])
            rows.append(
                {
                    "phase": span["phase"],
                    "energy_mws": float(sample.power_mw) * duration_s,
                    "duration_s": duration_s,
                }
            )

    phase_df = pd.DataFrame(rows)
    if phase_df.empty:
        return pd.DataFrame(columns=["phase", "energy_mws", "duration_s", "avg_power_mw"])

    summary = phase_df.groupby("phase", as_index=False)[["energy_mws", "duration_s"]].sum()
    summary["avg_power_mw"] = summary["energy_mws"] / summary["duration_s"]
    return summary


def load_all_runs(log_root: Path) -> dict[str, object]:
    runs: dict[tuple[str, str], dict[str, object]] = {}
    summary_rows: list[dict[str, object]] = []
    phase_rows: list[dict[str, object]] = []
    phase_power_rows: list[pd.DataFrame] = []

    for mode_dir in sorted(p for p in log_root.iterdir() if p.is_dir()):
        for path in sorted(mode_dir.glob("*.csv")):
            parsed = parse_log_file(path)
            runs[(mode_dir.name, path.name)] = parsed
            summary_rows.append(parsed["summary"])

            phase_summary = summarize_phase_coverage(parsed["decisions"])
            if not phase_summary.empty:
                phase_summary["mode"] = mode_dir.name
                phase_summary["file_name"] = path.name
                phase_rows.append(phase_summary)

            phase_power_summary = summarize_phase_power(parsed["telemetry"], end_ms=int(round(parsed["summary"]["run_duration_s"] * 1000.0)))
            if not phase_power_summary.empty:
                phase_power_summary["mode"] = mode_dir.name
                phase_power_summary["file_name"] = path.name
                phase_power_rows.append(phase_power_summary)

    run_summary_df = pd.DataFrame(summary_rows)
    phase_summary_df = pd.concat(phase_rows, ignore_index=True) if phase_rows else pd.DataFrame()
    phase_power_df = pd.concat(phase_power_rows, ignore_index=True) if phase_power_rows else pd.DataFrame()

    if run_summary_df.empty:
        mode_summary_df = pd.DataFrame()
    else:
        mode_rows = [_aggregate_mode_summary(group) for _, group in run_summary_df.groupby("mode", sort=False)]
        mode_summary_df = pd.DataFrame(mode_rows)
        mode_summary_df["mode"] = pd.Categorical(mode_summary_df["mode"], categories=MODE_ORDER, ordered=True)
        mode_summary_df = mode_summary_df.sort_values("mode").reset_index(drop=True)

    if not phase_summary_df.empty:
        phase_mode_summary_df = (
            phase_summary_df.groupby(["mode", "phase"], as_index=False)[["covered_s", "dropped_s", "total_s"]].sum()
        )
        phase_mode_summary_df["coverage_pct"] = 100.0 * phase_mode_summary_df["covered_s"] / phase_mode_summary_df["total_s"]
        phase_mode_summary_df["mode"] = pd.Categorical(phase_mode_summary_df["mode"], categories=MODE_ORDER, ordered=True)
        phase_mode_summary_df = phase_mode_summary_df.sort_values(["phase", "mode"]).reset_index(drop=True)
    else:
        phase_mode_summary_df = pd.DataFrame()

    if not phase_power_df.empty:
        phase_power_mode_summary_df = (
            phase_power_df.groupby(["mode", "phase"], as_index=False)[["energy_mws", "duration_s"]].sum()
        )
        phase_power_mode_summary_df["avg_power_mw"] = phase_power_mode_summary_df["energy_mws"] / phase_power_mode_summary_df["duration_s"]
        phase_power_mode_summary_df["mode"] = pd.Categorical(phase_power_mode_summary_df["mode"], categories=MODE_ORDER, ordered=True)
        phase_power_mode_summary_df = phase_power_mode_summary_df.sort_values(["phase", "mode"]).reset_index(drop=True)
    else:
        phase_power_mode_summary_df = pd.DataFrame()

    return {
        "runs": runs,
        "run_summary": run_summary_df,
        "mode_summary": mode_summary_df,
        "phase_summary": phase_summary_df,
        "phase_mode_summary": phase_mode_summary_df,
        "phase_power_summary": phase_power_df,
        "phase_power_mode_summary": phase_power_mode_summary_df,
    }


def _aggregate_mode_summary(group: pd.DataFrame) -> pd.Series:
    power_weights = group["run_duration_s"].fillna(0).clip(lower=0)
    coverage_weights = group["coverage_total_s"].fillna(0).clip(lower=0)
    state_weights = group["state_total_s"].fillna(0).clip(lower=0)

    avg_power_mw = np.average(group["avg_power_mw"], weights=power_weights) if power_weights.sum() > 0 else group["avg_power_mw"].mean()
    coverage_pct = 100.0 * group["covered_s"].sum() / group["coverage_total_s"].sum() if group["coverage_total_s"].sum() > 0 else np.nan
    state_0_pct = 100.0 * group["state_0_s"].sum() / group["state_total_s"].sum() if group["state_total_s"].sum() > 0 else np.nan
    state_1_pct = 100.0 * group["state_1_s"].sum() / group["state_total_s"].sum() if group["state_total_s"].sum() > 0 else np.nan

    return pd.Series(
        {
            "mode": group["mode"].iloc[0],
            "runs": int(len(group)),
            "avg_power_mw": avg_power_mw,
            "coverage_pct": coverage_pct,
            "coverage_total_s": float(group["coverage_total_s"].sum()),
            "covered_s": float(group["covered_s"].sum()),
            "dropped_s": float(group["dropped_s"].sum()),
            "state_0_pct": state_0_pct,
            "state_1_pct": state_1_pct,
        }
    )


def add_battery_metrics(mode_summary_df: pd.DataFrame, battery_mah: float = 150.0, battery_v: float = 3.7) -> pd.DataFrame:
    summary = mode_summary_df.copy()
    battery_mwh = battery_mah * battery_v
    summary["battery_mwh"] = battery_mwh
    summary["battery_life_h"] = battery_mwh / summary["avg_power_mw"]
    summary["battery_life_days"] = summary["battery_life_h"] / 24.0

    fixed_high_power = summary.loc[summary["mode"] == "fixed_high", "avg_power_mw"]
    fixed_high_life = summary.loc[summary["mode"] == "fixed_high", "battery_life_h"]
    if not fixed_high_power.empty:
        reference_power = float(fixed_high_power.iloc[0])
        summary["power_saving_vs_fixed_high_pct"] = 100.0 * (1.0 - summary["avg_power_mw"] / reference_power)
    else:
        summary["power_saving_vs_fixed_high_pct"] = np.nan
    if not fixed_high_life.empty:
        reference_life = float(fixed_high_life.iloc[0])
        summary["battery_extension_vs_fixed_high_pct"] = 100.0 * (summary["battery_life_h"] / reference_life - 1.0)
    else:
        summary["battery_extension_vs_fixed_high_pct"] = np.nan
    return summary


def pick_representative_run(run_summary_df: pd.DataFrame, mode: str) -> str | None:
    subset = run_summary_df[run_summary_df["mode"] == mode].copy()
    if subset.empty:
        return None
    target = subset["run_duration_s"].median()
    subset["distance"] = (subset["run_duration_s"] - target).abs()
    subset = subset.sort_values(["distance", "file_name"]).reset_index(drop=True)
    return str(subset.iloc[0]["file_name"])


def _shade_phases(ax: plt.Axes) -> None:
    for name, start_s, end_s, color in PHASES:
        ax.axvspan(start_s, end_s, color=color, alpha=0.55, lw=0)
    ymin, ymax = ax.get_ylim()
    if np.isfinite(ymin) and np.isfinite(ymax):
        y_text = ymax - 0.06 * (ymax - ymin if ymax > ymin else 1.0)
        for name, start_s, end_s, _ in PHASES:
            ax.text((start_s + end_s) / 2.0, y_text, name, ha="center", va="top", fontsize=9, color="#3C4043")


def plot_representative_run(parsed_run: dict[str, object], mode_label: str, title: str | None = None) -> plt.Figure:
    telemetry_df = parsed_run["telemetry"]
    decision_df = parsed_run["decisions"]
    transition_df = parsed_run["transitions"]
    summary = parsed_run["summary"]

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(12.5, 8.2),
        sharex=True,
        gridspec_kw={"height_ratios": [0.32, 1.15, 1.0]},
        constrained_layout=True,
    )
    ax_state, ax_hr, ax_power = axes

    state_segments = build_state_segments(transition_df, end_ms=int(round(summary["run_duration_s"] * 1000.0)))
    for segment in state_segments.itertuples(index=False):
        ax_state.axvspan(segment.start_s, segment.end_s, color=STATE_COLORS.get(int(segment.state), "#B0BEC5"), alpha=0.95, lw=0)
    ax_state.set_ylim(0, 1)
    ax_state.set_yticks([])
    ax_state.set_ylabel("State")
    ax_state.grid(False)

    if not decision_df.empty:
        valid_df = decision_df[decision_df["valid_hr"]].copy()
        dropout_df = decision_df[~decision_df["valid_hr"]].copy()
        if not valid_df.empty:
            ax_hr.plot(valid_df["elapsed_s"], valid_df["hr_bpm"], color="#1F5AA6", marker="o", markersize=3.8, label="Valid HR")
        if not dropout_df.empty:
            baseline = float(valid_df["hr_bpm"].min() - 6.0) if not valid_df.empty else 40.0
            ax_hr.scatter(dropout_df["elapsed_s"], np.full(len(dropout_df), baseline), color="#C62828", marker="x", s=38, label="Dropped window")
        ax_hr.set_ylabel("HR (bpm)")
        ax_hr.legend(loc="upper right")

    if not telemetry_df.empty:
        ax_power.plot(telemetry_df["elapsed_s"], telemetry_df["power_mw"], color="#37474F", marker="o", markersize=2.8)
        ax_power.fill_between(telemetry_df["elapsed_s"], telemetry_df["power_mw"], color="#90A4AE", alpha=0.18)
        ax_power.set_ylabel("Power (mW)")

    for axis in axes[1:]:
        _shade_phases(axis)
        axis.set_xlim(0, max(180.0, float(summary["run_duration_s"]) + 1.0))

    ax_power.set_xlabel("Elapsed time (s)")
    state_patches = [
        Patch(facecolor=STATE_COLORS[0], label="State 0 / NORMAL"),
        Patch(facecolor=STATE_COLORS[1], label="State 1 / HIGH"),
    ]
    ax_state.legend(handles=state_patches, loc="center right", ncol=2)
    ax_state.set_title(title or f"{mode_label}: representative run")
    return fig


def plot_summary_dashboard(mode_summary_df: pd.DataFrame) -> plt.Figure:
    summary = mode_summary_df.copy()
    summary["mode_label"] = summary["mode"].map(MODE_LABELS)
    colors = ["#2A6F97", "#D97706", "#7A7A7A"]

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.5), constrained_layout=True)
    ax_power, ax_life, ax_cov, ax_occ = axes.ravel()

    ax_power.bar(summary["mode_label"], summary["avg_power_mw"], color=colors)
    ax_power.set_title("Average Power")
    ax_power.set_ylabel("mW")
    for idx, value in enumerate(summary["avg_power_mw"]):
        ax_power.text(idx, value, f"{value:.2f}", ha="center", va="bottom")

    ax_life.bar(summary["mode_label"], summary["battery_life_h"], color=colors)
    ax_life.set_title("Estimated Battery Life")
    ax_life.set_ylabel("hours")
    for idx, value in enumerate(summary["battery_life_h"]):
        ax_life.text(idx, value, f"{value:.1f} h", ha="center", va="bottom")

    ax_cov.bar(summary["mode_label"], summary["coverage_pct"], color=colors)
    ax_cov.set_title("HR Coverage")
    ax_cov.set_ylabel("% of analysis time")
    ax_cov.set_ylim(0, 105)
    for idx, value in enumerate(summary["coverage_pct"]):
        ax_cov.text(idx, value, f"{value:.1f}%", ha="center", va="bottom")

    adaptive = summary[summary["mode"] == "adaptive"]
    if not adaptive.empty and not adaptive["state_0_pct"].isna().all():
        state0 = float(adaptive.iloc[0]["state_0_pct"])
        state1 = float(adaptive.iloc[0]["state_1_pct"])
        ax_occ.bar(["State 0", "State 1"], [state0, state1], color=[STATE_COLORS[0], STATE_COLORS[1]])
        ax_occ.set_ylim(0, 100)
        ax_occ.set_title("Adaptive State Occupancy")
        ax_occ.set_ylabel("% of runtime")
        for idx, value in enumerate([state0, state1]):
            ax_occ.text(idx, value, f"{value:.1f}%", ha="center", va="bottom")
    else:
        ax_occ.axis("off")

    return fig


def plot_phase_coverage(phase_mode_summary_df: pd.DataFrame) -> plt.Figure:
    phase_order = [phase[0] for phase in PHASES]
    df = phase_mode_summary_df.copy()
    df["phase"] = pd.Categorical(df["phase"], categories=phase_order, ordered=True)
    df["mode"] = pd.Categorical(df["mode"], categories=MODE_ORDER, ordered=True)
    df = df.sort_values(["phase", "mode"]).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(11.2, 5.6), constrained_layout=True)
    x = np.arange(len(phase_order))
    width = 0.23
    colors = {"adaptive": "#2A6F97", "fixed_high": "#D97706", "fixed_normal": "#7A7A7A"}

    for offset, mode in zip([-width, 0.0, width], MODE_ORDER):
        subset = df[df["mode"] == mode].set_index("phase").reindex(phase_order)
        ax.bar(x + offset, subset["coverage_pct"], width=width, label=MODE_LABELS[mode], color=colors[mode])

    ax.set_xticks(x)
    ax.set_xticklabels(phase_order)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Coverage (%)")
    ax.set_title("HR Coverage by Protocol Phase")
    ax.legend(loc="upper right")
    return fig


def plot_phase_power(phase_power_mode_summary_df: pd.DataFrame) -> plt.Figure:
    phase_order = [phase[0] for phase in PHASES]
    df = phase_power_mode_summary_df.copy()
    df["phase"] = pd.Categorical(df["phase"], categories=phase_order, ordered=True)
    df["mode"] = pd.Categorical(df["mode"], categories=MODE_ORDER, ordered=True)
    df = df.sort_values(["phase", "mode"]).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(11.2, 5.6), constrained_layout=True)
    x = np.arange(len(phase_order))
    width = 0.23
    colors = {"adaptive": "#2A6F97", "fixed_high": "#D97706", "fixed_normal": "#7A7A7A"}

    for offset, mode in zip([-width, 0.0, width], MODE_ORDER):
        subset = df[df["mode"] == mode].set_index("phase").reindex(phase_order)
        ax.bar(x + offset, subset["avg_power_mw"], width=width, label=MODE_LABELS[mode], color=colors[mode])

    ax.set_xticks(x)
    ax.set_xticklabels(phase_order)
    ax.set_ylabel("Average power (mW)")
    ax.set_title("Phase-Specific Power Analysis")
    ax.legend(loc="upper left")
    return fig


def plot_tradeoff_scatter(mode_summary_df: pd.DataFrame, phase_mode_summary_df: pd.DataFrame) -> plt.Figure:
    summary = mode_summary_df.copy().sort_values("mode").reset_index(drop=True)
    style_map = {
        "adaptive": {"color": "#2A6F97", "marker": "o", "size": 240},
        "fixed_high": {"color": "#D97706", "marker": "s", "size": 230},
        "fixed_normal": {"color": "#7A7A7A", "marker": "^", "size": 230},
    }

    fig, ax = plt.subplots(figsize=(10.8, 6.6), constrained_layout=True)

    for row in summary.itertuples(index=False):
        style = style_map[row.mode]
        ax.scatter(
            row.avg_power_mw,
            row.coverage_pct,
            s=style["size"],
            c=style["color"],
            marker=style["marker"],
            edgecolors="white",
            linewidths=1.6,
            zorder=3,
            label=MODE_LABELS[row.mode],
        )
        ax.annotate(
            f"{MODE_LABELS[row.mode]}\n({row.avg_power_mw:.2f} mW, {row.coverage_pct:.1f}%)",
            xy=(row.avg_power_mw, row.coverage_pct),
            xytext=(10, 12),
            textcoords="offset points",
            fontsize=9.5,
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#DADCE0", "alpha": 0.96},
        )

    adaptive = summary[summary["mode"] == "adaptive"].iloc[0]
    fixed_high = summary[summary["mode"] == "fixed_high"].iloc[0]
    fixed_normal = summary[summary["mode"] == "fixed_normal"].iloc[0]
    motion = phase_mode_summary_df.pivot(index="mode", columns="phase", values="coverage_pct")

    coverage_gap_pp = fixed_high["coverage_pct"] - adaptive["coverage_pct"]
    battery_extension_pct = adaptive["battery_extension_vs_fixed_high_pct"]
    motion_ratio = adaptive["coverage_pct"] / fixed_normal["coverage_pct"] if fixed_normal["coverage_pct"] > 0 else np.nan
    if "Motion" in motion.columns and "adaptive" in motion.index and "fixed_normal" in motion.index and motion.loc["fixed_normal", "Motion"] > 0:
        motion_ratio = motion.loc["adaptive", "Motion"] / motion.loc["fixed_normal", "Motion"]

    ax.plot(
        [fixed_normal["avg_power_mw"], adaptive["avg_power_mw"], fixed_high["avg_power_mw"]],
        [fixed_normal["coverage_pct"], adaptive["coverage_pct"], fixed_high["coverage_pct"]],
        color="#1F2937",
        linestyle="--",
        linewidth=1.3,
        alpha=0.65,
        zorder=2,
    )
    ax.text(
        adaptive["avg_power_mw"] + 0.18,
        adaptive["coverage_pct"] - 8.5,
        "Pareto trade-off region",
        fontsize=9.5,
        color="#1F2937",
        weight="bold",
    )

    insight_text = (
        f"Adaptive trades {coverage_gap_pp:.1f} coverage points for a "
        f"{battery_extension_pct:.1f}% battery-life gain vs Fixed High.\n"
        f"In motion, Adaptive keeps {motion_ratio:.1f}x the coverage of Fixed Normal."
    )
    ax.text(
        0.03,
        0.04,
        insight_text,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.4", "fc": "#F8FAFC", "ec": "#CBD5E1", "alpha": 0.98},
    )

    ax.set_title("Trade-off Analysis: Power vs HR Coverage")
    ax.set_xlabel("Average power consumption (mW)")
    ax.set_ylabel("Overall HR coverage (%)")
    ax.grid(True, alpha=0.5)
    ax.legend(loc="lower right")
    return fig


def format_summary_table(mode_summary_df: pd.DataFrame) -> pd.DataFrame:
    ordered = mode_summary_df.copy()
    ordered["Mode"] = ordered["mode"].map(MODE_LABELS)
    cols = [
        "Mode",
        "runs",
        "avg_power_mw",
        "power_saving_vs_fixed_high_pct",
        "battery_life_h",
        "battery_extension_vs_fixed_high_pct",
        "coverage_pct",
    ]
    if "state_0_pct" in ordered.columns:
        cols.extend(["state_0_pct", "state_1_pct"])
    return ordered[cols].rename(
        columns={
            "runs": "Runs",
            "avg_power_mw": "Avg Power (mW)",
            "power_saving_vs_fixed_high_pct": "Power Saving vs Fixed High (%)",
            "battery_life_h": "Battery Life (h)",
            "battery_extension_vs_fixed_high_pct": "Battery Extension vs Fixed High (%)",
            "coverage_pct": "HR Coverage (%)",
            "state_0_pct": "Adaptive State 0 (%)",
            "state_1_pct": "Adaptive State 1 (%)",
        }
    )
