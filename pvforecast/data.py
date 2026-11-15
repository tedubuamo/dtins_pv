"""Auditable ingestion, chronological partitions and gap-safe windows."""
from dataclasses import dataclass
import csv
from hashlib import sha256
from io import BytesIO
import logging

import numpy as np
import pandas as pd

LOG = logging.getLogger(__name__)
STEP = pd.Timedelta(minutes=5)
PARTITIONS = ("train", "validation", "calibration", "test")


def read_file(content: bytes, filename: str, sheet_name=0) -> pd.DataFrame:
    extension = filename.rsplit(".", 1)[-1].lower()
    try:
        if extension == "csv":
            dialect = csv.Sniffer().sniff(content[:16384].decode("utf-8-sig"), delimiters=",;\t|")
            frame = pd.read_csv(BytesIO(content), sep=dialect.delimiter, encoding="utf-8-sig")
        elif extension in ("xlsx", "xls"):
            frame = pd.read_excel(BytesIO(content), sheet_name=sheet_name)
        else:
            raise ValueError("Format harus CSV, XLSX, atau XLS.")
    except Exception as exc:
        raise ValueError(f"Tidak dapat membaca {filename}: {exc}") from exc
    if frame.empty or len(frame.columns) < 2:
        raise ValueError("File kosong atau tidak memiliki dua kolom yang dibutuhkan.")
    return frame


def parse_time(value, timezone: str, dayfirst: bool = False):
    try:
        if pd.isna(value) or isinstance(value, (int, float, np.number)):
            return pd.NaT  # Excel date serials require explicit upstream conversion.
        stamp = pd.Timestamp(pd.to_datetime(value, dayfirst=dayfirst))
        return stamp.tz_localize(timezone) if stamp.tzinfo is None else stamp.tz_convert(timezone)
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def segment(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_values("timestamp").reset_index(drop=True).copy()
    result["segment"] = result.timestamp.diff().ne(STEP).cumsum().astype(int)
    return result


@dataclass
class Dataset:
    clean: pd.DataFrame
    audit: pd.DataFrame
    report: dict


def prepare(frame, timestamp_column, power_column, timezone, *, dayfirst=False,
            source_file="", source_hash="") -> Dataset:
    if timestamp_column == power_column or not {timestamp_column, power_column} <= set(frame.columns):
        raise ValueError("Pilih dua kolom berbeda untuk timestamp dan daya.")
    # Validate timezone even if every timestamp in a malformed upload fails parsing.
    pd.Timestamp("2020-01-01").tz_localize(timezone)
    audit = pd.DataFrame({"source_row": np.arange(len(frame)) + 2,
                          "source_timestamp": frame[timestamp_column].astype(str),
                          "source_power": frame[power_column].astype(str)})
    audit["timestamp"] = pd.to_datetime(
        frame[timestamp_column].map(lambda v: parse_time(v, timezone, dayfirst)), utc=True
    ).dt.tz_convert(timezone).to_numpy()
    audit["power_w"] = pd.to_numeric(frame[power_column], errors="coerce").to_numpy()
    invalid_time = audit.timestamp.isna()
    invalid_power = ~np.isfinite(audit.power_w.to_numpy(dtype=float))
    negative = audit.power_w.lt(0)
    duplicate = audit.timestamp.notna() & audit.timestamp.duplicated(keep=False)
    conflicts = audit.loc[~invalid_time].groupby("timestamp").power_w.nunique(dropna=False)
    conflict_stamps = conflicts[conflicts > 1].index
    conflicting = audit.timestamp.isin(conflict_stamps)
    audit["status"] = "retained"
    audit.loc[invalid_time, "status"] = "invalid_timestamp"
    audit.loc[invalid_power & ~invalid_time, "status"] = "invalid_power"
    audit.loc[negative & ~invalid_time, "status"] = "negative_power_quarantined"
    audit.loc[conflicting, "status"] = "conflicting_duplicate_quarantined"
    eligible = audit.status.eq("retained")
    repeated = audit.loc[eligible, "timestamp"].duplicated(keep="first")
    audit.loc[repeated[repeated].index, "status"] = "identical_duplicate_removed"
    clean = segment(audit.loc[audit.status.eq("retained"), ["timestamp", "power_w"]])
    if clean.empty:
        raise ValueError("Tidak ada data valid. Periksa format timestamp, daya numerik, dan duplikat.")
    differences = clean.timestamp.diff().dropna()
    missing = sum(max(int(d / STEP) - 1, 0) for d in differences if d > STEP)
    report = {
        "source_file": source_file, "source_sha256": source_hash,
        "imported_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "mapping": {"timestamp": str(timestamp_column), "power_w": str(power_column)},
        "timezone": timezone, "dayfirst": dayfirst,
        "original_rows": len(frame), "clean_rows": len(clean),
        "removed_rows": len(frame) - len(clean), "invalid_timestamps": int(invalid_time.sum()),
        "invalid_power": int(invalid_power.sum()), "negative_power": int(negative.sum()),
        "duplicate_rows": int(duplicate.sum()), "conflicting_timestamps": len(conflict_stamps),
        "missing_intervals": missing, "irregular_intervals": int((differences != STEP).sum()),
        "segments": int(clean.segment.nunique()), "longest_segment": int(clean.groupby("segment").size().max()),
        "first_timestamp": clean.timestamp.iloc[0].isoformat(),
        "last_timestamp": clean.timestamp.iloc[-1].isoformat(),
        "cleaning_version": "1", "policy": "Keep first identical duplicate; quarantine ALL conflicting duplicates, invalid and negative records; no imputation.",
        "status_counts": {str(k): int(v) for k, v in audit.status.value_counts().items()},
    }
    LOG.info("Prepared dataset %s", report)
    return Dataset(clean, audit, report)


def content_hash(content: bytes) -> str:
    return sha256(content).hexdigest()


def dataset_hash(frame: pd.DataFrame) -> str:
    return sha256(frame[["timestamp", "power_w"]].to_csv(index=False).encode()).hexdigest()


def split_data(frame, boundaries):
    if len(boundaries) != 3:
        raise ValueError("Tentukan tiga batas waktu train/validation/calibration/test.")
    cuts = [pd.Timestamp(v) for v in boundaries]
    if any(c.tzinfo is None for c in cuts):
        raise ValueError("Batas waktu harus memiliki zona waktu.")
    if not frame.timestamp.min() < cuts[0] < cuts[1] < cuts[2] <= frame.timestamp.max():
        raise ValueError("Batas harus berurutan di dalam rentang data.")
    edges = [frame.timestamp.min(), *cuts, frame.timestamp.max() + STEP]
    # All context AND targets belong wholly to one partition. No shared observations.
    return {name: segment(frame.loc[(frame.timestamp >= a) & (frame.timestamp < b)])
            for name, a, b in zip(PARTITIONS, edges, edges[1:])}


@dataclass
class Scale:
    minimum: float
    span: float

    @classmethod
    def fit(cls, training_power):
        values = np.asarray(training_power, dtype=float)
        if not values.size or not np.isfinite(values).all():
            raise ValueError("Data scaler training tidak valid.")
        return cls(float(values.min()), float(np.ptp(values)) or 1.0)

    def transform(self, values):
        return (np.asarray(values, dtype=np.float32) - self.minimum) / self.span

    def inverse(self, values):
        return np.asarray(values) * self.span + self.minimum


def windows(frame, lookback):
    if lookback not in (6, 12, 24):
        raise ValueError("Look-back harus 6, 12, atau 24.")
    xs, ys, origins = [], [], []
    for _, group in segment(frame).groupby("segment"):
        values = group.power_w.to_numpy(dtype=np.float32)
        for end in range(lookback, len(group) - 5):
            xs.append(values[end-lookback:end, None])
            ys.append(values[end:end+6])
            origins.append(group.timestamp.iloc[end-1])
    if not xs:
        raise ValueError(f"Tidak ada window kontinu: perlu minimal {lookback + 6} baris per partisi.")
    return np.stack(xs), np.stack(ys), pd.DatetimeIndex(origins)
