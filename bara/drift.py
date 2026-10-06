"""The telemetry drift of the sensor-fault scenario (s3m), written out so no simulator is needed.

A linear drift of a reading: from the onset to the end the offset grows from 0 to *magnitude*, and
each drifted value is rounded to 3 decimals, as in the released stores. With *end* given the window
is [onset, end). Without it the drift runs to the last reading inclusive, which reaches the full
magnitude; the deposited scenario was made this way, and its label records the last timestamp. For
a temperature at medium severity the magnitude is +1.0 C. Applied to Core_mid's reading in the
supplement's __act store, it reproduces the deposited s3m series on all 8,760 hours
(tests/test_public.py).
"""
from __future__ import annotations

from datetime import datetime


def _t(ts: str) -> datetime:
    return datetime.fromisoformat(ts[:19])


def drift(series: list[tuple[str, float]], onset: str, end: str | None = None,
          magnitude: float = 1.0) -> list[tuple[str, float]]:
    t0 = _t(onset)
    t1 = _t(end) if end else _t(series[-1][0])
    total_h = max((t1 - t0).total_seconds() / 3600.0, 1.0)
    out = []
    for ts, v in series:
        d = _t(ts)
        if t0 <= d and (d < t1 or end is None):
            out.append((ts, round(v + magnitude * (d - t0).total_seconds() / 3600.0 / total_h, 3)))
        else:
            out.append((ts, v))
    return out


def label(timeseries_id: str, onset: str, end: str, magnitude: float = 1.0, unit: str = "C") -> dict:
    return {"timeseries_id": timeseries_id, "fault_type": "drift", "onset": onset, "end": end,
            "magnitude": magnitude, "unit": unit, "params": {},
            "source": "EnergyPlus severity-schedule ramp convention; RP-1312 drift"}
