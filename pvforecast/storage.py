"""Local immutable source storage; filenames are derived from content hashes."""
import json
from pathlib import Path

from pvforecast.data import content_hash


def persist_dataset(content, filename, dataset, root="data"):
    root = Path(root)
    raw, processed = root / "raw", root / "processed"
    raw.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    digest = content_hash(content)
    source = raw / f"{digest}.{Path(filename).suffix.lstrip('.').lower()}"
    if not source.exists():
        source.write_bytes(content)
    # Multiple mappings/cleaning runs never overwrite an earlier audit.
    run = dataset.report["imported_at"].replace(":", "").replace("+", "_")
    folder = processed / f"{digest[:12]}_{run}"
    folder.mkdir(parents=True, exist_ok=False)
    dataset.clean.to_csv(folder / "clean.csv", index=False)
    dataset.audit.to_csv(folder / "audit.csv", index=False)
    (folder / "quality.json").write_text(json.dumps(dataset.report, indent=2), encoding="utf-8")
    return folder
