"""Transparent, rule-based comeback detection on ONE topic's time series.

A series is a list of mention counts, one per period (day/week/month), oldest first,
with missing periods filled with 0.

ALGORITHM (scan left to right)
  1. PEAK      : the first period with count >= min_peak_count starts a peak. While no quiet
                 period has been established, a higher count replaces the peak.
  2. DECLINE   : a period is QUIET when count <= peak * (1 - min_decline_pct/100).
  3. QUIET RUN : consecutive quiet periods. A non-quiet period before the run reaches
                 min_quiet_periods cancels the run (the decline was not sustained).
  4. RESURGENCE: once the quiet run has >= min_quiet_periods, the first non-quiet period
                 starts a test. Look at the next `resurgence_window` periods (including it):
                    current_count = the highest count in that window
                    baseline      = average count over the quiet run
                    growth %      = (current - baseline) / baseline * 100
                 It is a resurgence only if growth >= min_growth_pct AND
                 current >= min_current_count AND window total >= min_posts_in_resurgence.
                 A small blip that fails the test does not erase the quiet run.
  5. REPEAT    : after a resurgence, the resurgence becomes the new peak, so multiple
                 comebacks can be found.

ZERO BASELINE RULE: if baseline is 0 we use baseline_floor (default 1 mention) as the divisor so
growth stays finite (no division by zero / infinity).

A topic that only ever grows never has a quiet period, so it can never be flagged.
The thresholds are practical defaults, NOT scientific constants: tune them on your real dataset.
Output wording: results are POTENTIAL comebacks (resurgence candidates), not proof of real-world revival.
"""
from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path

STATUS_COMEBACK = "potential_comeback"
STATUS_NONE = "no_comeback_detected"
STATUS_LOW_ACTIVITY = "insufficient_activity"
STATUS_LOW_HISTORY = "insufficient_history"


@dataclass
class DetectionParams:
    min_total_mentions: int = 100        # topic needs at least this many mentions overall
    min_peak_count: int = 30             # a peak period needs at least this many mentions
    min_decline_pct: float = 70.0        # quiet = at most (100 - this)% of the peak
    min_quiet_periods: int = 8           # how many consecutive quiet periods are required
    min_growth_pct: float = 200.0        # required growth above the quiet baseline
    min_current_count: int = 20          # required mentions in the resurgence period
    resurgence_window: int = 4           # periods examined for the resurgence
    min_posts_in_resurgence: int = 0     # optional: total mentions across the window
    baseline_floor: float = 1.0          # divisor used when the baseline is zero

    def validate(self) -> None:
        if not 0 < self.min_decline_pct <= 100:
            raise ValueError("min_decline_pct must be in (0, 100]")
        for name in ("min_quiet_periods", "resurgence_window", "min_peak_count"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")
        if self.baseline_floor <= 0:
            raise ValueError("baseline_floor must be positive")


def load_params(path=None, overrides: dict = None) -> DetectionParams:
    """Read thresholds from detection_params.json (if it exists), then apply overrides."""
    values = {}
    if path and Path(path).is_file():
        with open(path, "r", encoding="utf-8") as handle:
            values.update(json.load(handle))
    values.update(overrides or {})
    known = {f.name for f in fields(DetectionParams)}
    params = DetectionParams(**{k: v for k, v in values.items() if k in known})
    params.validate()
    return params


def decline_percentage(peak_count: float, low_count: float) -> float:
    """((peak - low) / peak) * 100, safe when the peak is zero."""
    if peak_count <= 0:
        return 0.0
    return (peak_count - low_count) / peak_count * 100.0


def growth_percentage(current_count: float, baseline_count: float, baseline_floor: float = 1.0) -> float:
    """((current - baseline) / baseline) * 100. A zero baseline uses baseline_floor instead."""
    effective = baseline_count if baseline_count > 0 else baseline_floor
    return (current_count - effective) / effective * 100.0


def _empty_result(topic, status, total):
    return {"topic": topic, "status": status, "total_mentions": total, "n_events": 0, "events": [],
            "peak_count": None, "peak_period": None, "decline_percentage": None, "quiet_periods": None,
            "quiet_start": None, "quiet_end": None, "baseline_count": None, "current_count": None,
            "resurgence_period": None, "growth_percentage": None}


def detect_comeback(counts: list, periods: list, params: DetectionParams, topic: str = "") -> dict:
    """Run the algorithm on one series and return a result dictionary."""
    params.validate()
    if len(counts) != len(periods):
        raise ValueError("counts and periods must have the same length")
    total = int(sum(counts))
    if total < params.min_total_mentions:
        return _empty_result(topic, STATUS_LOW_ACTIVITY, total)
    if len(counts) < params.min_quiet_periods + 3:  # peak + quiet run + resurgence need room
        return _empty_result(topic, STATUS_LOW_HISTORY, total)

    events = []
    peak_index, peak_value = None, 0
    quiet_values, quiet_first, quiet_last = [], None, None
    index, n = 0, len(counts)

    while index < n:
        value = counts[index]
        if peak_index is None:
            if value >= params.min_peak_count:
                peak_index, peak_value = index, value
            index += 1
            continue

        quiet_level = peak_value * (1 - params.min_decline_pct / 100.0)
        if value <= quiet_level:                                  # quiet period
            if not quiet_values:
                quiet_first = index
            quiet_values.append(value)
            quiet_last = index
            index += 1
            continue

        if len(quiet_values) < params.min_quiet_periods:          # decline was not sustained
            quiet_values, quiet_first, quiet_last = [], None, None
            if value > peak_value:
                peak_index, peak_value = index, value
            index += 1
            continue

        # A sustained quiet run exists and activity is back above the quiet level: test it.
        window = counts[index:index + params.resurgence_window]
        current = max(window)
        resurgence_index = index + window.index(current)
        baseline = sum(quiet_values) / len(quiet_values)
        growth = growth_percentage(current, baseline, params.baseline_floor)
        if (growth >= params.min_growth_pct and current >= params.min_current_count
                and sum(window) >= params.min_posts_in_resurgence):
            events.append({
                "peak_count": int(peak_value), "peak_period": periods[peak_index],
                "decline_percentage": decline_percentage(peak_value, min(quiet_values)),
                "quiet_periods": len(quiet_values), "quiet_start": periods[quiet_first],
                "quiet_end": periods[quiet_last], "baseline_count": baseline,
                "current_count": int(current), "resurgence_period": periods[resurgence_index],
                "growth_percentage": growth})
            peak_index, peak_value = resurgence_index, current   # allow later comebacks
            quiet_values, quiet_first, quiet_last = [], None, None
            index = resurgence_index + 1
        else:
            index += 1                                            # blip: keep the quiet run

    if not events:
        status = STATUS_NONE if peak_index is not None else STATUS_LOW_ACTIVITY
        return _empty_result(topic, status, total)
    result = _empty_result(topic, STATUS_COMEBACK, total)
    result.update(events[-1])            # headline metrics = the most recent resurgence
    result["n_events"] = len(events)
    result["events"] = events
    return result


def params_to_dict(params: DetectionParams) -> dict:
    return asdict(params)
