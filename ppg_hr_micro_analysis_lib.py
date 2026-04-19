from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DAQ_COLUMNS = [
    "timestamp_us",
    "bus_v",
    "current_ma",
    "power_mw",
    "feature_pin_state",
    "infer_pin_state",
]

TARGET_TELEMETRY_COLUMNS = [
    "timestamp_ms",
    "state",
    "profile",
    "quality",
    "diff",
    "red",
    "ir",
]

MODE_NAME_FROM_ID = {
    0: "fixed_normal",
    1: "fixed_high",
    2: "adaptive",
}

MODE_LABELS = {
    "adaptive": "Adaptive",
    "fixed_high": "Fixed High",
    "fixed_normal": "Fixed Normal",
}

MODE_ORDER = ["adaptive", "fixed_high", "fixed_normal"]

TARGET_MODE_RE = re.compile(r"Starting PPG Scheduler \(mode=(?P<mode>\d+)\)")
TARGET_STATE_RE = re.compile(
    r"^I \((?P<timestamp_ms>\d+)\) PPG_TINYML: Scheduler state -> "
    r"(?P<state_label>HIGH|NORMAL)\((?P<profile_sps>\d+)sps\)$"
)
TARGET_INVOKE_RE = re.compile(
    r"^I \((?P<timestamp_ms>\d+)\) PPG_TINYML: TinyML Invoke time: (?P<invoke_time_us>\d+) us$"
)
TARGET_AI_RE = re.compile(
    r"^I \((?P<timestamp_ms>\d+)\) PPG_TINYML: AI_ASSIST_HR=(?P<ai_hr>-?\d+(?:\.\d+)?) "
    r"\| raw_ai=(?P<raw_ai>-?\d+(?:\.\d+)?) \| y_q=(?P<y_q>-?\d+) "
    r"\| dsp_peak=(?P<dsp_peak_ai_log>-?\d+(?:\.\d+)?) ac=(?P<ac_ai_log>-?\d+(?:\.\d+)?)$"
)
TARGET_DSP_HOLD_RE = re.compile(
    r"^W \((?P<timestamp_ms>\d+)\) PPG_TINYML: DSP_HOLD: state=(?P<state>\d+) "
    r"peak=(?P<peak_bpm>-?\d+(?:\.\d+)?) ac_hr=(?P<ac_hr>-?\d+(?:\.\d+)?) "
    r"ac=(?P<ac>-?\d+(?:\.\d+)?)$"
)
TARGET_DSP_HR_RE = re.compile(
    r"^I \((?P<timestamp_ms>\d+)\) PPG_TINYML: DSP_HR=(?P<dsp_hr>-?\d+(?:\.\d+)?) "
    r"\| state=(?P<state>\d+) \| ac=(?P<ac>-?\d+(?:\.\d+)?) "
    r"ac_hr=(?P<ac_hr>-?\d+(?:\.\d+)?) std_hp=(?P<std_hp>-?\d+(?:\.\d+)?) "
    r"ptp_hp=(?P<ptp_hp>-?\d+(?:\.\d+)?)$"
)
TARGET_LOW_QUALITY_RE = re.compile(
    r"^W \((?P<timestamp_ms>\d+)\) PPG_TINYML: Low quality window: state=(?P<state>\d+) "
    r"reason=(?P<reason>\d+) ac=(?P<ac>-?\d+(?:\.\d+)?) "
    r"peak_bpm=(?P<peak_bpm>-?\d+(?:\.\d+)?) ac_hr=(?P<ac_hr>-?\d+(?:\.\d+)?) "
    r"std_hp=(?P<std_hp>-?\d+(?:\.\d+)?) ptp_hp=(?P<ptp_hp>-?\d+(?:\.\d+)?)$"
)
TARGET_NO_CONTACT_RE = re.compile(
    r"^W \((?P<timestamp_ms>\d+)\) PPG_TINYML: NO_CONTACT: state=(?P<state>\d+) "
    r"ac=(?P<ac>-?\d+(?:\.\d+)?) peak_bpm=(?P<peak_bpm>-?\d+(?:\.\d+)?) "
    r"std_hp=(?P<std_hp>-?\d+(?:\.\d+)?) ptp_hp=(?P<ptp_hp>-?\d+(?:\.\d+)?)$"
)
TARGET_TELEMETRY_RE = re.compile(
    r"^(?P<timestamp_ms>\d+),(?P<state>\d+),(?P<profile>\d+),(?P<quality>-?\d+),"
    r"(?P<diff>-?\d+(?:\.\d+)?),(?P<red>\d+),(?P<ir>\d+)$"
)


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


def read_text_auto(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8", errors="ignore")


def _coerce_numeric_frame(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def parse_target_log(path: Path) -> dict[str, object]:
    windows: list[dict[str, object]] = []
    telemetry_rows: list[dict[str, object]] = []
    state_rows: list[dict[str, object]] = []
    mode_id: int | None = None

    for raw_line in read_text_auto(path).splitlines():
        line = raw_line.strip()
        if not line:
            continue

        mode_match = TARGET_MODE_RE.search(line)
        if mode_match:
            mode_id = int(mode_match.group("mode"))

        telemetry_match = TARGET_TELEMETRY_RE.match(line)
        if telemetry_match:
            telemetry_rows.append(telemetry_match.groupdict())
            continue

        state_match = TARGET_STATE_RE.match(line)
        if state_match:
            row = state_match.groupdict()
            row["state"] = 1 if row["state_label"] == "HIGH" else 0
            state_rows.append(row)
            continue

        dsp_hold_match = TARGET_DSP_HOLD_RE.match(line)
        if dsp_hold_match:
            row = dsp_hold_match.groupdict()
            row["window_kind"] = "DSP_HOLD"
            windows.append(row)
            continue

        dsp_hr_match = TARGET_DSP_HR_RE.match(line)
        if dsp_hr_match:
            row = dsp_hr_match.groupdict()
            row["window_kind"] = "DSP_HR"
            windows.append(row)
            continue

        low_quality_match = TARGET_LOW_QUALITY_RE.match(line)
        if low_quality_match:
            row = low_quality_match.groupdict()
            row["window_kind"] = "LOW_QUALITY"
            windows.append(row)
            continue

        no_contact_match = TARGET_NO_CONTACT_RE.match(line)
        if no_contact_match:
            row = no_contact_match.groupdict()
            row["window_kind"] = "NO_CONTACT"
            windows.append(row)
            continue

        invoke_match = TARGET_INVOKE_RE.match(line)
        if invoke_match and windows:
            windows[-1].update(invoke_match.groupdict())
            continue

        ai_match = TARGET_AI_RE.match(line)
        if ai_match and windows:
            windows[-1].update(ai_match.groupdict())

    telemetry_df = pd.DataFrame(telemetry_rows, columns=TARGET_TELEMETRY_COLUMNS)
    telemetry_df = _coerce_numeric_frame(telemetry_df, TARGET_TELEMETRY_COLUMNS)
    if not telemetry_df.empty:
        telemetry_df = telemetry_df.sort_values("timestamp_ms").reset_index(drop=True)
        telemetry_df["elapsed_s"] = telemetry_df["timestamp_ms"] / 1000.0

    state_df = pd.DataFrame(state_rows)
    state_df = _coerce_numeric_frame(state_df, ["timestamp_ms", "profile_sps", "state"])
    if not state_df.empty:
        state_df = state_df.sort_values("timestamp_ms").reset_index(drop=True)
        state_df["elapsed_s"] = state_df["timestamp_ms"] / 1000.0

    windows_df = pd.DataFrame(windows)
    window_numeric_cols = [
        "timestamp_ms",
        "state",
        "peak_bpm",
        "ac_hr",
        "ac",
        "dsp_hr",
        "std_hp",
        "ptp_hp",
        "reason",
        "invoke_time_us",
        "ai_hr",
        "raw_ai",
        "y_q",
        "dsp_peak_ai_log",
        "ac_ai_log",
    ]
    windows_df = _coerce_numeric_frame(windows_df, window_numeric_cols)
    if not windows_df.empty:
        windows_df = windows_df.sort_values("timestamp_ms").reset_index(drop=True)
        windows_df["elapsed_s"] = windows_df["timestamp_ms"] / 1000.0
        windows_df["window_index"] = np.arange(len(windows_df))

    return {
        "mode_id": mode_id,
        "mode_name": MODE_NAME_FROM_ID.get(mode_id, "unknown"),
        "telemetry": telemetry_df,
        "state_transitions": state_df,
        "windows": windows_df,
    }


def parse_daq_log(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, names=DAQ_COLUMNS)
    df = _coerce_numeric_frame(df, DAQ_COLUMNS)
    df = df.dropna().reset_index(drop=True)
    df["feature_pin_state"] = df["feature_pin_state"].astype(int)
    df["infer_pin_state"] = df["infer_pin_state"].astype(int)
    df["active"] = ((df["feature_pin_state"] > 0) | (df["infer_pin_state"] > 0)).astype(int)

    if len(df) > 1:
        dt_us = df["timestamp_us"].diff().dropna()
        median_dt_us = float(dt_us.median())
    else:
        median_dt_us = 0.0

    next_timestamp = df["timestamp_us"].shift(-1)
    df["sample_interval_us"] = (next_timestamp - df["timestamp_us"]).fillna(median_dt_us)
    df["sample_interval_us"] = df["sample_interval_us"].clip(lower=0.0)
    return df


def merge_active_bursts(daq_df: pd.DataFrame, max_gap_rows: int = 3) -> list[dict[str, int]]:
    active_indices = daq_df.index[daq_df["active"] == 1].tolist()
    if not active_indices:
        return []

    bursts: list[dict[str, int]] = []
    start_idx = active_indices[0]
    prev_idx = active_indices[0]

    for idx in active_indices[1:]:
        if idx - prev_idx <= max_gap_rows:
            prev_idx = idx
            continue

        bursts.append({"seed_start_idx": start_idx, "seed_end_idx": prev_idx})
        start_idx = idx
        prev_idx = idx

    bursts.append({"seed_start_idx": start_idx, "seed_end_idx": prev_idx})
    return bursts


def compute_burst_metrics(
    daq_df: pd.DataFrame,
    seed_start_idx: int,
    seed_end_idx: int,
    baseline_window: int = 20,
    settle_count: int = 2,
    min_excess_power_mw: float = 8.0,
    sigma_multiplier: float = 3.0,
) -> dict[str, float | int]:
    baseline_slice = daq_df.loc[max(0, seed_start_idx - baseline_window) : seed_start_idx - 1]
    quiet_slice = baseline_slice[baseline_slice["active"] == 0]
    if quiet_slice.empty:
        global_quiet = daq_df[daq_df["active"] == 0]
        quiet_slice = global_quiet.iloc[: min(50, len(global_quiet))] if not global_quiet.empty else pd.DataFrame()

    if quiet_slice.empty:
        baseline_power_mw = float(daq_df["power_mw"].median())
        noise_mw = 0.0
    else:
        baseline_power_mw = float(quiet_slice["power_mw"].median())
        mad_mw = float((quiet_slice["power_mw"] - baseline_power_mw).abs().median())
        noise_mw = 1.4826 * mad_mw if len(quiet_slice) >= 3 else 0.0

    settle_threshold_mw = baseline_power_mw + max(min_excess_power_mw, sigma_multiplier * noise_mw)

    integration_start_idx = seed_start_idx
    while (
        integration_start_idx > 0
        and daq_df.loc[integration_start_idx - 1, "active"] == 0
        and daq_df.loc[integration_start_idx - 1, "power_mw"] > settle_threshold_mw
    ):
        integration_start_idx -= 1

    integration_end_idx = seed_end_idx
    quiet_streak = 0
    for idx in range(seed_end_idx + 1, len(daq_df)):
        is_active = bool(daq_df.loc[idx, "active"])
        is_above_threshold = float(daq_df.loc[idx, "power_mw"]) > settle_threshold_mw
        integration_end_idx = idx
        if is_active or is_above_threshold:
            quiet_streak = 0
            continue
        quiet_streak += 1
        if quiet_streak >= settle_count:
            break

    seed_segment = daq_df.loc[seed_start_idx:seed_end_idx].copy()
    integration_segment = daq_df.loc[integration_start_idx:integration_end_idx].copy()

    excess_power_mw = np.maximum(integration_segment["power_mw"].to_numpy() - baseline_power_mw, 0.0)
    interval_us = integration_segment["sample_interval_us"].to_numpy()
    total_active_energy_uj = float(np.sum(excess_power_mw * interval_us / 1000.0))

    feature_interval_us = seed_segment.loc[
        seed_segment["feature_pin_state"] > 0, "sample_interval_us"
    ].sum()
    infer_interval_us = seed_segment.loc[
        seed_segment["infer_pin_state"] > 0, "sample_interval_us"
    ].sum()
    seed_duration_us = float(seed_segment["sample_interval_us"].sum())
    integration_duration_us = float(integration_segment["sample_interval_us"].sum())

    return {
        "seed_start_idx": int(seed_start_idx),
        "seed_end_idx": int(seed_end_idx),
        "integration_start_idx": int(integration_start_idx),
        "integration_end_idx": int(integration_end_idx),
        "seed_start_us": int(daq_df.loc[seed_start_idx, "timestamp_us"]),
        "seed_end_us": int(daq_df.loc[seed_end_idx, "timestamp_us"]),
        "integration_start_us": int(daq_df.loc[integration_start_idx, "timestamp_us"]),
        "integration_end_us": int(daq_df.loc[integration_end_idx, "timestamp_us"]),
        "baseline_power_mw": baseline_power_mw,
        "settle_threshold_mw": float(settle_threshold_mw),
        "peak_power_mw": float(integration_segment["power_mw"].max()),
        "peak_excess_power_mw": float(excess_power_mw.max()) if len(excess_power_mw) else 0.0,
        "mean_excess_power_mw": float(excess_power_mw.mean()) if len(excess_power_mw) else 0.0,
        "total_active_energy_uj": total_active_energy_uj,
        "feature_pin_width_us": float(feature_interval_us),
        "infer_pin_width_us": float(infer_interval_us),
        "seed_duration_us": seed_duration_us,
        "integration_duration_us": integration_duration_us,
        "tail_duration_us": max(0.0, integration_duration_us - seed_duration_us),
        "feature_rows": int((seed_segment["feature_pin_state"] > 0).sum()),
        "infer_rows": int((seed_segment["infer_pin_state"] > 0).sum()),
        "power_tail_rows": int(len(integration_segment) - len(seed_segment)),
    }


def _first_valid(series: pd.Series) -> float:
    cleaned = pd.to_numeric(series, errors="coerce").dropna()
    if cleaned.empty:
        return float("nan")
    return float(cleaned.iloc[0])


def analyze_run(run_dir: Path, merge_gap_rows: int = 3) -> dict[str, object]:
    target_path = run_dir / "target.csv"
    daq_path = run_dir / "daq.csv"

    target = parse_target_log(target_path)
    daq_df = parse_daq_log(daq_path)
    burst_seeds = merge_active_bursts(daq_df, max_gap_rows=merge_gap_rows)

    mode_id = int(target["mode_id"]) if target["mode_id"] is not None else -1
    mode_name = str(target["mode_name"])
    windows_df = target["windows"].copy()

    if mode_name in {"adaptive", "fixed_high"}:
        matched_windows = windows_df[windows_df["state"] == 1].reset_index(drop=True)
    else:
        matched_windows = windows_df.iloc[0:0].copy()

    alignment_ok = len(matched_windows) == len(burst_seeds)

    burst_rows: list[dict[str, object]] = []
    for burst_index, seed in enumerate(burst_seeds):
        row: dict[str, object] = {
            "mode_id": mode_id,
            "mode_name": mode_name,
            "run_name": run_dir.name,
            "burst_index": burst_index,
        }
        row.update(
            compute_burst_metrics(
                daq_df,
                seed_start_idx=seed["seed_start_idx"],
                seed_end_idx=seed["seed_end_idx"],
            )
        )

        if burst_index < len(matched_windows):
            window = matched_windows.iloc[burst_index]
            row["target_window_timestamp_ms"] = _first_valid(pd.Series([window.get("timestamp_ms")]))
            row["window_kind"] = window.get("window_kind")
            row["window_state"] = _first_valid(pd.Series([window.get("state")]))
            row["invoke_time_us"] = _first_valid(pd.Series([window.get("invoke_time_us")]))
            row["ai_hr_bpm"] = _first_valid(pd.Series([window.get("ai_hr")]))
            row["raw_ai_bpm"] = _first_valid(pd.Series([window.get("raw_ai")]))
            row["dsp_hr_bpm"] = _first_valid(pd.Series([window.get("dsp_hr")]))
            row["peak_bpm_target"] = _first_valid(
                pd.Series([window.get("peak_bpm"), window.get("dsp_peak_ai_log")])
            )
            row["ac_target"] = _first_valid(pd.Series([window.get("ac"), window.get("ac_ai_log")]))
            row["std_hp_target"] = _first_valid(pd.Series([window.get("std_hp")]))
            row["ptp_hp_target"] = _first_valid(pd.Series([window.get("ptp_hp")]))
            row["quality_reason"] = _first_valid(pd.Series([window.get("reason")]))
        else:
            row["target_window_timestamp_ms"] = float("nan")
            row["window_kind"] = "UNMATCHED"
            row["window_state"] = float("nan")
            row["invoke_time_us"] = 0.0
            row["ai_hr_bpm"] = float("nan")
            row["raw_ai_bpm"] = float("nan")
            row["dsp_hr_bpm"] = float("nan")
            row["peak_bpm_target"] = float("nan")
            row["ac_target"] = float("nan")
            row["std_hp_target"] = float("nan")
            row["ptp_hp_target"] = float("nan")
            row["quality_reason"] = float("nan")

        invoke_time_us = 0.0 if pd.isna(row["invoke_time_us"]) else float(row["invoke_time_us"])
        ai_energy_est_uj = float(row["peak_excess_power_mw"]) * invoke_time_us / 1000.0
        row["ai_energy_est_uj"] = ai_energy_est_uj
        row["dsp_energy_est_uj"] = max(0.0, float(row["total_active_energy_uj"]) - ai_energy_est_uj)
        row["ai_energy_fraction_pct"] = (
            100.0 * ai_energy_est_uj / float(row["total_active_energy_uj"])
            if float(row["total_active_energy_uj"]) > 0.0
            else 0.0
        )
        row["infer_captured"] = bool(float(row["infer_pin_width_us"]) > 0.0)
        burst_rows.append(row)

    burst_df = pd.DataFrame(burst_rows)

    inactive_rows = daq_df[daq_df["active"] == 0]
    quiet_power_mw = float(inactive_rows["power_mw"].median()) if not inactive_rows.empty else float("nan")
    dt_us = daq_df["timestamp_us"].diff().dropna()

    run_summary = {
        "mode_id": mode_id,
        "mode_name": mode_name,
        "run_name": run_dir.name,
        "n_target_windows": int(len(windows_df)),
        "n_high_windows": int((windows_df["state"] == 1).sum()) if not windows_df.empty else 0,
        "n_bursts": int(len(burst_df)),
        "alignment_ok": bool(alignment_ok),
        "daq_avg_power_mw": float(daq_df["power_mw"].mean()),
        "daq_median_power_mw": float(daq_df["power_mw"].median()),
        "quiet_baseline_mw": quiet_power_mw,
        "dt_mean_us": float(dt_us.mean()) if not dt_us.empty else 0.0,
        "dt_median_us": float(dt_us.median()) if not dt_us.empty else 0.0,
        "dt_min_us": float(dt_us.min()) if not dt_us.empty else 0.0,
        "dt_max_us": float(dt_us.max()) if not dt_us.empty else 0.0,
        "infer_capture_rate_pct": float((burst_df["infer_captured"].mean() * 100.0) if not burst_df.empty else 0.0),
        "mean_total_active_energy_uj": float(burst_df["total_active_energy_uj"].mean()) if not burst_df.empty else float("nan"),
        "mean_ai_energy_est_uj": float(burst_df["ai_energy_est_uj"].mean()) if not burst_df.empty else float("nan"),
        "mean_ai_energy_fraction_pct": float(burst_df["ai_energy_fraction_pct"].mean()) if not burst_df.empty else float("nan"),
        "mean_tail_duration_us": float(burst_df["tail_duration_us"].mean()) if not burst_df.empty else float("nan"),
    }

    return {
        "mode_id": mode_id,
        "mode_name": mode_name,
        "run_name": run_dir.name,
        "target": target,
        "daq": daq_df,
        "burst_df": burst_df,
        "run_summary": run_summary,
    }


def analyze_dataset(log_root: Path, merge_gap_rows: int = 3) -> dict[str, object]:
    runs: dict[tuple[str, str], dict[str, object]] = {}
    run_summaries: list[dict[str, object]] = []
    burst_frames: list[pd.DataFrame] = []

    for mode_dir in sorted(path for path in log_root.iterdir() if path.is_dir()):
        for run_dir in sorted(path for path in mode_dir.iterdir() if path.is_dir()):
            run_result = analyze_run(run_dir, merge_gap_rows=merge_gap_rows)
            runs[(run_result["mode_name"], run_result["run_name"])] = run_result
            run_summaries.append(run_result["run_summary"])
            if not run_result["burst_df"].empty:
                burst_frames.append(run_result["burst_df"])

    run_summary_df = pd.DataFrame(run_summaries)
    burst_df = pd.concat(burst_frames, ignore_index=True) if burst_frames else pd.DataFrame()
    mode_summary_df = summarize_mode_results(run_summary_df, burst_df)

    return {
        "runs": runs,
        "run_summary": run_summary_df.sort_values(["mode_name", "run_name"]).reset_index(drop=True),
        "burst_df": burst_df.sort_values(["mode_name", "run_name", "burst_index"]).reset_index(drop=True),
        "mode_summary": mode_summary_df.sort_values("mode_sort").drop(columns=["mode_sort"]).reset_index(drop=True),
    }


def summarize_mode_results(run_summary_df: pd.DataFrame, burst_df: pd.DataFrame) -> pd.DataFrame:
    if run_summary_df.empty:
        return pd.DataFrame()

    base = (
        run_summary_df.groupby("mode_name", as_index=False)
        .agg(
            n_runs=("run_name", "count"),
            daq_avg_power_mw=("daq_avg_power_mw", "mean"),
            daq_median_power_mw=("daq_median_power_mw", "mean"),
            quiet_baseline_mw=("quiet_baseline_mw", "mean"),
            dt_mean_us=("dt_mean_us", "mean"),
            dt_median_us=("dt_median_us", "mean"),
            dt_min_us=("dt_min_us", "mean"),
            dt_max_us=("dt_max_us", "mean"),
            n_bursts=("n_bursts", "sum"),
            infer_capture_rate_pct=("infer_capture_rate_pct", "mean"),
        )
    )

    if burst_df.empty:
        base["mode_sort"] = base["mode_name"].map({name: i for i, name in enumerate(MODE_ORDER)})
        return base

    burst_summary = (
        burst_df.groupby("mode_name", as_index=False)
        .agg(
            slow_path_bursts=("burst_index", "count"),
            total_active_energy_uj_mean=("total_active_energy_uj", "mean"),
            total_active_energy_uj_median=("total_active_energy_uj", "median"),
            ai_energy_est_uj_mean=("ai_energy_est_uj", "mean"),
            ai_energy_est_uj_median=("ai_energy_est_uj", "median"),
            dsp_energy_est_uj_mean=("dsp_energy_est_uj", "mean"),
            dsp_energy_est_uj_median=("dsp_energy_est_uj", "median"),
            ai_energy_fraction_pct_mean=("ai_energy_fraction_pct", "mean"),
            baseline_power_mw_mean=("baseline_power_mw", "mean"),
            peak_excess_power_mw_mean=("peak_excess_power_mw", "mean"),
            invoke_time_us_mean=("invoke_time_us", "mean"),
            invoke_time_us_median=("invoke_time_us", "median"),
            feature_pin_width_us_mean=("feature_pin_width_us", "mean"),
            infer_pin_width_us_mean=("infer_pin_width_us", "mean"),
            seed_duration_us_mean=("seed_duration_us", "mean"),
            tail_duration_us_mean=("tail_duration_us", "mean"),
            integration_duration_us_mean=("integration_duration_us", "mean"),
            infer_capture_rate_burst_pct=("infer_captured", lambda x: 100.0 * float(pd.Series(x).mean())),
        )
    )

    energy_sums = (
        burst_df.groupby("mode_name", as_index=False)[["total_active_energy_uj", "ai_energy_est_uj", "dsp_energy_est_uj"]]
        .sum()
        .rename(
            columns={
                "total_active_energy_uj": "total_active_energy_uj_sum",
                "ai_energy_est_uj": "ai_energy_est_uj_sum",
                "dsp_energy_est_uj": "dsp_energy_est_uj_sum",
            }
        )
    )
    energy_sums["ai_energy_fraction_pct_weighted"] = (
        100.0 * energy_sums["ai_energy_est_uj_sum"] / energy_sums["total_active_energy_uj_sum"]
    )

    summary = base.merge(burst_summary, on="mode_name", how="left").merge(energy_sums, on="mode_name", how="left")
    summary["mode_sort"] = summary["mode_name"].map({name: i for i, name in enumerate(MODE_ORDER)})
    return summary


def pick_representative_burst(
    burst_df: pd.DataFrame,
    prefer_mode: str = "fixed_high",
    require_infer_capture: bool = True,
) -> pd.Series:
    candidates = burst_df.copy()
    if prefer_mode in candidates["mode_name"].unique():
        candidates = candidates[candidates["mode_name"] == prefer_mode].copy()
    if require_infer_capture and "infer_captured" in candidates.columns:
        infer_candidates = candidates[candidates["infer_captured"]].copy()
        if not infer_candidates.empty:
            candidates = infer_candidates
    median_energy = float(candidates["total_active_energy_uj"].median())
    idx = (candidates["total_active_energy_uj"] - median_energy).abs().idxmin()
    return candidates.loc[idx]


def plot_micro_energy_dashboard(mode_summary_df: pd.DataFrame) -> plt.Figure:
    summary = mode_summary_df.copy()
    slow = summary[summary["slow_path_bursts"].fillna(0) > 0].copy()

    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.8), constrained_layout=True)

    axes[0].bar(
        [MODE_LABELS[m] for m in summary["mode_name"]],
        summary["quiet_baseline_mw"],
        color=["#2E8B57", "#D97706", "#7A7A7A"],
    )
    axes[0].set_ylabel("Quiet baseline power (mW)")
    axes[0].set_title("Baseline Power by Mode")

    axes[1].bar(
        [MODE_LABELS[m] for m in slow["mode_name"]],
        slow["total_active_energy_uj_mean"],
        color=["#2E8B57" if m == "adaptive" else "#D97706" for m in slow["mode_name"]],
    )
    axes[1].set_ylabel("Total active energy / burst (µJ)")
    axes[1].set_title("Total Burst Energy")

    x = np.arange(len(slow))
    axes[2].bar(x, slow["dsp_energy_est_uj_mean"], label="DSP / Feature", color="#2563EB")
    axes[2].bar(
        x,
        slow["ai_energy_est_uj_mean"],
        bottom=slow["dsp_energy_est_uj_mean"],
        label="TinyML Invoke",
        color="#F59E0B",
    )
    axes[2].set_xticks(x)
    axes[2].set_xticklabels([MODE_LABELS[m] for m in slow["mode_name"]])
    axes[2].set_ylabel("Estimated energy / burst (µJ)")
    axes[2].set_title("DSP vs TinyML Energy Breakdown")
    axes[2].legend(loc="upper right")

    for ax in axes:
        ax.tick_params(axis="x", rotation=0)

    return fig


def plot_timing_resolution_dashboard(mode_summary_df: pd.DataFrame) -> plt.Figure:
    summary = mode_summary_df.copy()
    slow = summary[summary["slow_path_bursts"].fillna(0) > 0].copy()

    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.8), constrained_layout=True)

    x = np.arange(len(slow))
    width = 0.36
    axes[0].bar(x - width / 2, slow["dt_median_us"], width=width, color="#64748B", label="DAQ median interval")
    axes[0].bar(x + width / 2, slow["invoke_time_us_mean"], width=width, color="#F59E0B", label="Invoke exact time")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([MODE_LABELS[m] for m in slow["mode_name"]])
    axes[0].set_ylabel("Time (µs)")
    axes[0].set_title("DAQ Resolution vs TinyML Invoke Time")
    axes[0].legend(loc="upper right")

    axes[1].bar(
        x,
        slow["infer_capture_rate_burst_pct"],
        color=["#2E8B57" if m == "adaptive" else "#D97706" for m in slow["mode_name"]],
    )
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([MODE_LABELS[m] for m in slow["mode_name"]])
    axes[1].set_ylabel("Bursts with infer pin captured (%)")
    axes[1].set_title("Observed Infer-Pin Capture Rate")
    axes[1].set_ylim(0, 100)

    return fig


def plot_representative_burst(
    burst_row: pd.Series,
    run_result: dict[str, object],
    pad_rows: int = 8,
) -> plt.Figure:
    daq_df = run_result["daq"]
    start_idx = max(0, int(burst_row["integration_start_idx"]) - pad_rows)
    end_idx = min(len(daq_df) - 1, int(burst_row["integration_end_idx"]) + pad_rows)
    segment = daq_df.loc[start_idx:end_idx].copy()
    segment["t_ms"] = (segment["timestamp_us"] - float(burst_row["integration_start_us"])) / 1000.0

    fig, (ax_power, ax_pin) = plt.subplots(
        2,
        1,
        figsize=(11.4, 5.8),
        sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.0]},
        constrained_layout=True,
    )

    ax_power.plot(segment["t_ms"], segment["power_mw"], color="#1D4ED8", label="Measured power")
    ax_power.axhline(float(burst_row["baseline_power_mw"]), color="#64748B", linestyle="--", label="Baseline")
    ax_power.axhline(float(burst_row["settle_threshold_mw"]), color="#94A3B8", linestyle=":", label="Settle threshold")
    ax_power.axvspan(
        0.0,
        float(burst_row["integration_duration_us"]) / 1000.0,
        color="#DBEAFE",
        alpha=0.35,
        label="Integrated active energy",
    )
    ax_power.set_ylabel("Power (mW)")
    ax_power.set_title(
        f"Representative Burst: {MODE_LABELS.get(str(burst_row['mode_name']), burst_row['mode_name'])} / "
        f"{burst_row['run_name']}"
    )
    ax_power.legend(loc="upper right")

    feature_level = np.where(segment["feature_pin_state"] > 0, 1.0, 0.0)
    infer_level = np.where(segment["infer_pin_state"] > 0, 0.45, 0.0)
    ax_pin.step(segment["t_ms"], feature_level, where="post", color="#059669", label="Feature pin")
    ax_pin.step(segment["t_ms"], infer_level, where="post", color="#F59E0B", label="Infer pin")
    ax_pin.set_ylabel("Pin")
    ax_pin.set_xlabel("Time relative to integration start (ms)")
    ax_pin.set_ylim(-0.1, 1.2)
    ax_pin.set_yticks([0.0, 0.45, 1.0])
    ax_pin.set_yticklabels(["0", "Infer", "Feature"])
    ax_pin.legend(loc="upper right")

    return fig
