import numpy as np
from climate_logic import (
    percentile_threshold, detect_heatwave_events, yearly_stats,
    linregress, mann_kendall, build_trend,
)


def test_percentile_and_detection():
    tmax = np.array([30.0] * 100 + [40.0] * 6)  # 6 hot days at end
    th = percentile_threshold(tmax, 95)
    assert 30 < th < 40
    dates = [f"2020-01-{(i % 28) + 1:02d}-{i}" for i in range(106)]
    # make unique sortable dates
    dates = [f"2020-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}" for i in range(106)]
    ev = detect_heatwave_events(dates, tmax, th, 3)
    assert len(ev) == 1 and ev[0]["duration_days"] == 6


def test_trend_direction():
    years = list(range(2000, 2020))
    vals = [float(i) for i in range(20)]  # strictly increasing
    t = build_trend(years, vals, "x")
    assert t["slope_per_year"] > 0 and t["direction"] == "increasing"


def test_mk_no_trend():
    tau, p, d = mann_kendall([5.0] * 10)
    assert d == "no trend"


def test_yearly_gaps_warn():
    import math
    tmax = np.array([30.0, np.nan] * 50)
    dates = [f"2020-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}" for i in range(100)]
    y, w = yearly_stats(dates, tmax, [])
    assert y and any("missing" in x for x in w)
