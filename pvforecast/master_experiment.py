"""Reproducible all-sheet Data Master training experiment."""
import argparse
from dataclasses import asdict
from io import BytesIO
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from pvforecast.data import content_hash, prepare, split_data, windows
from pvforecast.forecast import forecast, forecast_table
from pvforecast.model import Config, predict, save_bundle, train, unpack
from pvforecast.storage import persist_dataset

LOG = logging.getLogger(__name__)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def load_master(content, filename):
    frames, sources, sheets = [], [], []
    with pd.ExcelFile(BytesIO(content)) as workbook:
        for name in workbook.sheet_names:
            frame = pd.read_excel(workbook, sheet_name=name)
            required = {"Updated Time", "Production Power(W)"}
            if not required <= set(frame.columns):
                if frame.empty:
                    sheets.append({"sheet": name, "rows": 0, "status": "empty"})
                    continue
                raise ValueError(f"Sheet {name!r} tidak memiliki kolom timestamp/daya.")
            valid = pd.to_numeric(frame["Production Power(W)"], errors="coerce")
            sheets.append({"sheet": name, "rows": len(frame),
                           "finite_power_rows": int(np.isfinite(valid).sum()),
                           "status": "empty" if frame.empty else "audited"})
            if frame.empty:
                continue
            frames.append(frame[list(sorted(required))])
            sources.extend({"source_sheet": name, "source_excel_row": row + 2}
                           for row in range(len(frame)))
    if not frames:
        raise ValueError("Workbook tidak memiliki data.")
    dataset = prepare(pd.concat(frames, ignore_index=True), "Updated Time",
                      "Production Power(W)", "Asia/Jakarta", source_file=filename,
                      source_hash=content_hash(content))
    # prepare retains audit rows in their original concatenation order.
    provenance = pd.DataFrame(sources)
    dataset.audit[provenance.columns] = provenance
    dataset.report["sheets"] = sheets
    dataset.report["source_row_convention"] = "Use source_sheet and source_excel_row for workbook coordinates."
    return dataset


def experiment_config(dataset, candidates):
    frame = dataset.clean
    n = len(frame)
    indices = [n * fraction // 10 for fraction in (7, 8, 9)]
    boundaries = [frame.timestamp.iloc[index].isoformat() for index in indices]
    parts = split_data(frame, boundaries)
    counts = {}
    for name, part in parts.items():
        counts[name] = {"rows": len(part), "windows": {}}
        for config in candidates:
            config.validate()
            count = len(windows(part, config.lookback)[1])
            if name == "calibration" and count < 19:
                raise ValueError("Calibration memerlukan minimal 19 window per kandidat.")
            counts[name]["windows"][str(config.lookback)] = count
    return {"data": {"timestamp_column": "Updated Time", "power_column": "Production Power(W)",
                     "timezone": "Asia/Jakarta", "dayfirst": False,
                     "sheets": [item["sheet"] for item in dataset.report["sheets"]]},
            "source_sha256": dataset.report["source_sha256"],
            "split": {"ratios": [0.7, 0.1, 0.1, 0.1],
                      "rule": "chronological cleaned rows; cuts at floor(7N/10), floor(8N/10), floor(9N/10)"},
            "boundaries": boundaries, "partitions": counts,
            "candidates": [asdict(candidate) for candidate in candidates]}


def run_experiment(data, output, candidates=None):
    candidates = candidates or [Config(lookback=value) for value in (6, 12, 24)]
    content = data.read_bytes()
    dataset = load_master(content, data.name)
    config = experiment_config(dataset, candidates)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "experiment.json", config)
    dataset.report["experiment"] = config
    audit_folder = persist_dataset(content, data.name, dataset)
    dataset.clean.to_csv(output / "clean.csv", index=False)
    write_json(output / "quality.json", dataset.report)
    LOG.info("Partitions: %s", config["partitions"])
    bundle = train(dataset.clean, config["boundaries"], candidates, dataset.report,
                   lambda t, total, e, loss: LOG.info("Trial %s/%s epoch %s validation %.6f", t, total, e, loss))
    model_path = save_bundle(bundle)
    restored = unpack(model_path.read_bytes())
    lookback = bundle.metadata["config"]["lookback"]
    # Latest usable observation, even if the workbook ends with a short segment.
    eligible = dataset.clean.groupby("segment").filter(lambda group: len(group) >= lookback)
    origin = eligible.timestamp.iloc[-1]
    result = forecast(dataset, restored, origin)
    original_result = forecast(dataset, bundle, origin)
    if result["forecasts"] != original_result["forecasts"]:
        raise ValueError("Prediksi berubah setelah pemuatan ulang model.")
    parts = split_data(dataset.clean, config["boundaries"])
    x, _, _ = windows(parts["test"], lookback)
    np.testing.assert_array_equal(predict(bundle.model, bundle.scaler, x),
                                  predict(restored.model, restored.scaler, x))
    for name, table in (("metrics", bundle.scores), ("history", bundle.history),
                        ("test_predictions", bundle.predictions), ("forecast", forecast_table(result))):
        table.to_csv(output / f"{name}.csv", index=False)
    write_json(output / "forecast.json", result)
    summary = {"model": str(model_path), "audit": str(audit_folder),
               "selected_config": bundle.metadata["config"],
               "model_version": bundle.metadata["model_version"],
               "roundtrip_verified": True, "forecast_origin": origin.isoformat(),
               "metrics": json.loads(bundle.scores.to_json(orient="records"))}
    write_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("Data Master.xlsx"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    output = args.output or Path("data/experiments") / pd.Timestamp.now(tz="UTC").strftime("master_%Y%m%dT%H%M%S%fZ")
    summary = run_experiment(args.data, output)
    print(json.dumps({"output": str(output), **summary}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
