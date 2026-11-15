"""Human-readable WIB dates, isolated from model and export timestamps."""
import re

import pandas as pd

ZONE = "Asia/Jakarta"
DATE_TIME = "%d-%m-%Y %H:%M"


def wib_time(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        return ""
    stamp = stamp.tz_localize(ZONE) if stamp.tzinfo is None else stamp.tz_convert(ZONE)
    return stamp.strftime(DATE_TIME) + " WIB"


def parse_wib_input(value):
    try:
        stamp = pd.to_datetime(value.strip().removesuffix("WIB").strip(), format=DATE_TIME)
        return stamp.tz_localize(ZONE)
    except (ValueError, TypeError) as exc:
        raise ValueError("Gunakan tanggal dan jam WIB: DD-MM-YYYY HH:mm, misalnya 10-11-2025 07:25 WIB.") from exc


def chart_times(values):
    # Plotly receives local clock values; the axis explicitly labels them WIB.
    return pd.to_datetime(values, utc=True).dt.tz_convert(ZONE).dt.tz_localize(None)


def display_frame(frame):
    result = frame.copy()
    for name in result.columns:
        if name not in {"timestamp", "source_timestamp", "Updated Time", "forecast_origin", "last_observation_timestamp",
                        "start", "end", "trained_at"}:
            continue
        text = result[name].astype(str)
        parsed = pd.to_datetime(text, format="mixed", utc=True, errors="coerce")
        aware = text.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True)
        local = parsed.dt.tz_convert(ZONE).dt.strftime(DATE_TIME)
        naive = parsed.dt.strftime(DATE_TIME)
        formatted = local.where(aware, naive) + " WIB"
        result[name] = formatted.where(parsed.notna(), text.where(result[name].notna(), ""))
    return result


def display_metadata(value):
    if isinstance(value, dict):
        return {key: display_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [display_metadata(item) for item in value]
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", value):
        try:
            return wib_time(value)
        except ValueError:
            pass
    return value
