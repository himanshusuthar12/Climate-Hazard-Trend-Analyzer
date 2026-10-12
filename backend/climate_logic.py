"""Pure climate-logic: heatwave detection, yearly aggregation, trends.

Heatwave definition (default): 3+ consecutive days with daily Tmax above the
regional 95th percentile. Percentile is computed over the full requested period
(robust, simple, documented). Baseline alternative is noted in README.

No heavy deps: numpy only. Mann-Kendall implemented manually (two-sided,
normal approximation, tie correction).
"""

from __future__ import annotations

import math
from typing import List, Dict, Tuple
import numpy as np


def percentile_threshold(tmax: np.ndarray, pct: float = 95.0) -> float:
    clean = tmax[~np.isnan(tmax)]
    if clean.size == 0:
        raise ValueError("No valid temperature data")
    return float(np.percentile(clean, pct))


def detect_heatwave_events(
    dates: List[str], tmax: np.ndarray, threshold: float, min_days: int = 3
) -> List[dict]:
    """Return list of events {start, end, duration_days, peak_exceedance_c}."""
    events: List[dict] = []
    run_start: int | None = None
    for i in range(len(tmax)):
        hot = bool(not math.isnan(tmax[i]) and tmax[i] > threshold)
        if hot and run_start is None:
            run_start = i
        if (not hot or i == len(tmax) - 1) and run_start is not None:
            # close run (if last day is hot, include it)
            end = i if not hot else i
            if hot and i == len(tmax) - 1:
                end = i
            else:
                end = i - 1 if not hot else i
            duration = end - run_start + 1
            if duration >= min_days:
                peak = float(np.nanmax(tmax[run_start : end + 1] - threshold))
                events.append(
                    {
                        "start": dates[run_start],
                        "end": dates[end],
                        "duration_days": int(duration),
                        "peak_exceedance_c": round(peak, 2),
                    }
                )
            run_start = None
    return events


def yearly_stats(
    dates: List[str], tmax: np.ndarray, events: List[dict]
) -> Tuple[List[dict], List[str]]:
    """Aggregate per-year stats. Returns (yearly_list, warnings)."""
    warnings: List[str] = []
    if not dates:
        return [], ["empty dataset"]
    years = sorted({d[:4] for d in dates})
    # map date -> tmax
    day_map = dict(zip(dates, [float(v) if not math.isnan(v) else None for v in tmax]))
    # map year -> events
    yearly: List[dict] = []
    for y in years:
        y_days = [v for d, v in day_map.items() if d.startswith(y) and v is not None]
        y_events = [e for e in events if e["start"][:4] == y]
        hw_days = sum(e["duration_days"] for e in y_events)
        max_dur = max((e["duration_days"] for e in y_events), default=0)
        yearly.append(
            {
                "year": int(y),
                "heatwave_events": len(y_events),
                "heatwave_days": int(hw_days),
                "max_duration_days": int(max_dur),
                "mean_tmax": round(float(np.mean(y_days)), 2) if y_days else None,
                "mean_intensity_c": round(
                    float(np.mean([e["peak_exceedance_c"] for e in y_events])), 2
                )
                if y_events
                else None,
            }
        )
    # data-quality warnings
    total_days = len(dates)
    missing = int(np.isnan(tmax).sum())
    if total_days and missing / total_days > 0.05:
        warnings.append(
            f"{missing}/{total_days} days ({missing/total_days:.1%}) missing — gap-filled as NaN and excluded."
        )
    return yearly, warnings


def rolling_mean(values: List[float], window: int = 5) -> List[dict | None]:
    out: List[dict | None] = []
    arr = np.array(values, dtype=float)
    for i in range(len(arr)):
        lo = max(0, i - window + 1)
        seg = arr[lo : i + 1]
        out.append({"index": i, "value": round(float(np.nanmean(seg)), 3)})
    return out  # type: ignore


def linregress(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """OLS slope + intercept (no scipy dependency)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = ~np.isnan(y)
    x, y = x[mask], y[mask]
    if len(x) < 3:
        return 0.0, float(np.nanmean(y)) if len(y) else 0.0
    xm, ym = float(np.mean(x)), float(np.mean(y))
    denom = float(np.sum((x - xm) ** 2))
    slope = float(np.sum((x - xm) * (y - ym)) / denom) if denom else 0.0
    return slope, float(ym - slope * xm)


def mann_kendall(y: List[float]) -> tuple[float, float, str]:
    """Return (tau, p_value approx, direction). Normal approx with tie correction."""
    arr = np.array([v for v in y if v is not None and not (isinstance(v, float) and math.isnan(v))], dtype=float)
    n = len(arr)
    if n < 4:
        return 0.0, 1.0, "no trend"
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            s += int(np.sign(arr[j] - arr[i]))
    # tie correction
    _, counts = np.unique(arr, return_counts=True)
    tie = float(np.sum(counts * (counts - 1) * (2 * counts + 5)))
    var_s = (n * (n - 1) * (2 * n + 5) - tie) / 18.0
    if var_s <= 0:
        return 0.0, 1.0, "no trend"
    z = (s - 1) / math.sqrt(var_s) if s > 0 else ((s + 1) / math.sqrt(var_s) if s < 0 else 0.0)
    # two-sided p from normal CDF via erf
    p = float(2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))))
    tau = float(s / (n * (n - 1) / 2))
    direction = "increasing" if (p < 0.05 and s > 0) else ("decreasing" if (p < 0.05 and s < 0) else "no trend")
    return round(tau, 4), round(p, 4), direction


def pct_change_first_last(values: List[float], k: int = 5) -> tuple[float | None, str]:
    """% change: mean(last k years) vs mean(first k years). Returns (pct, note)."""
    arr = np.array(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 2 * k:
        k = max(1, len(arr) // 2)
    if len(arr) < 2:
        return None, "insufficient data"
    first = float(np.mean(arr[:k]))
    last = float(np.mean(arr[-k:]))
    if first == 0:
        # fall back to absolute change wording
        return (None, f"baseline mean is 0 (abs change {last:.2f}); % undefined")
    pct = (last - first) / abs(first) * 100.0
    return round(float(pct), 1), f"mean of last {k}y vs first {k}y"


def build_trend(years: List[int], values: List[float], metric: str) -> dict:
    x = np.array(years, dtype=float)
    slope, intercept = linregress(x, np.array(values, dtype=float))
    pct, note = pct_change_first_last(values)
    tau, p, direction = mann_kendall(values)
    roll = rolling_mean(values, 5)
    return {
        "metric": metric,
        "slope_per_year": round(float(slope), 4),
        "intercept": round(float(intercept), 3),
        "pct_change": pct,
        "pct_change_note": note,
        "mann_kendall_tau": tau,
        "mann_kendall_p": p,
        "direction": direction,
        "rolling_5y": roll,
    }


def summary_sentence(label: str, trend_days: dict, threshold: float) -> str:
    pct = trend_days.get("pct_change")
    direction = trend_days.get("direction", "no trend")
    slope = trend_days.get("slope_per_year", 0)
    if pct is None:
        change_txt = f"trend slope {slope:+.2f} heatwave-days/year ({direction}; Mann-Kendall p={trend_days.get('mann_kendall_p')})"
    else:
        verb = "increased" if pct > 0 else "decreased"
        change_txt = f"have {verb} by {abs(pct)}% ({direction}; {slope:+.2f} days/year, MK p={trend_days.get('mann_kendall_p')})"
    return (
        f"Heatwave days {change_txt} in {label} since the start of the record "
        f"(heatwave = 3+ days above {threshold:.1f}°C, the 95th percentile)."
    )
