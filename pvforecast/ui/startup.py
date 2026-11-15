"""Restore the explicitly configured local experiment for a new session."""
import json
from pathlib import Path

import pandas as pd

from pvforecast.data import Dataset, dataset_hash
from pvforecast.model import unpack


def load_default_experiment(root):
    profile = root / "configs/dashboard.json"
    if not profile.exists():
        return None
    config = json.loads(profile.read_text(encoding="utf-8"))
    experiment = root / config["experiment"]
    summary = json.loads((experiment / "summary.json").read_text(encoding="utf-8"))
    bundle = unpack((root / summary["model"]).read_bytes())
    audit_folder = root / summary["audit"]
    report = json.loads((audit_folder / "quality.json").read_text(encoding="utf-8"))
    clean = pd.read_csv(audit_folder / "clean.csv", float_precision="round_trip")
    clean["timestamp"] = pd.to_datetime(clean.timestamp, utc=True).dt.tz_convert(report["timezone"])
    audit = pd.read_csv(audit_folder / "audit.csv", float_precision="round_trip")
    audit["timestamp"] = pd.to_datetime(audit.timestamp, utc=True).dt.tz_convert(report["timezone"])
    if (dataset_hash(clean) != bundle.metadata["dataset_sha256"]
            or report["source_sha256"] != bundle.metadata["provenance"]["source_sha256"]):
        raise ValueError("Dataset default tidak cocok dengan sumber pelatihan model.")
    return Dataset(clean, audit, report), bundle


def initialize_session(state, root):
    if state.get("startup_checked"):
        return
    state["startup_checked"] = True
    if "dataset" in state or "bundle" in state:
        return
    try:
        loaded = load_default_experiment(root)
        if loaded is not None:
            state["dataset"], state["bundle"] = loaded
    except (OSError, ValueError, KeyError) as exc:
        state["startup_error"] = f"Dataset/model default gagal dimuat: {exc}"
