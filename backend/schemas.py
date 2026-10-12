"""Pydantic request/response schemas with strict validation (security: safe user inputs)."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    # Optional custom lat-lon box; if given, analysis uses box centre (documented assumption)
    lat_min: Optional[float] = Field(default=None, ge=-90, le=90)
    lat_max: Optional[float] = Field(default=None, ge=-90, le=90)
    lon_min: Optional[float] = Field(default=None, ge=-180, le=180)
    lon_max: Optional[float] = Field(default=None, ge=-180, le=180)
    start_year: int = Field(default=1990, ge=1940, le=2025)
    end_year: int = Field(default=2020, ge=1940, le=2025)
    hazard_type: str = Field(default="heatwave")
    threshold_percentile: float = Field(default=95.0, ge=80, le=99.9)
    min_consecutive_days: int = Field(default=3, ge=2, le=10)
    label: Optional[str] = Field(default=None, max_length=120)

    @field_validator("end_year")
    @classmethod
    def _check_range(cls, v, info):
        start = info.data.get("start_year", 1990)
        if v < start:
            raise ValueError("end_year must be >= start_year")
        if v - start > 60:
            raise ValueError("max 60-year window (performance guard)")
        return v

    @field_validator("hazard_type")
    @classmethod
    def _check_hazard(cls, v):
        v = v.lower().strip()
        if v not in ("heatwave",):
            raise ValueError("Only 'heatwave' is supported in this version")
        return v

    @field_validator("label")
    @classmethod
    def _clean_label(cls, v):
        if v is None:
            return v
        # strip HTML / control chars (basic XSS guard)
        return "".join(c for c in v.strip() if c.isprintable())[:120]

    def effective_point(self) -> tuple[float, float]:
        if self.lat is not None and self.lon is not None:
            return float(self.lat), float(self.lon)
        if None not in (self.lat_min, self.lat_max, self.lon_min, self.lon_max):
            lo_la, hi_la = sorted([self.lat_min, self.lat_max])  # type: ignore
            lo_lo, hi_lo = sorted([self.lon_min, self.lon_max])  # type: ignore
            return (lo_la + hi_la) / 2.0, (lo_lo + hi_lo) / 2.0
        raise ValueError("Provide either (lat, lon) or a full lat-lon box")


class YearlyStat(BaseModel):
    year: int
    heatwave_events: int
    heatwave_days: int
    max_duration_days: int
    mean_tmax: Optional[float] = None
    mean_intensity_c: Optional[float] = None


class TrendResult(BaseModel):
    metric: str
    slope_per_year: float
    intercept: float
    pct_change: Optional[float] = None
    pct_change_note: str = ""
    mann_kendall_tau: float
    mann_kendall_p: float
    direction: str  # increasing | decreasing | no trend
    rolling_5y: List[dict] = []


class AnalyzeResponse(BaseModel):
    cache_key: str
    location: dict
    threshold_c: float
    baseline_note: str
    yearly: List[YearlyStat]
    trend_days: TrendResult
    trend_events: TrendResult
    summary: str
    warnings: List[str] = []
    meta: dict = {}
