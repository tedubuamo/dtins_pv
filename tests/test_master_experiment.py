from io import BytesIO
import json

import pandas as pd
import pytest

from pvforecast.master_experiment import load_master, experiment_config, run_experiment
from pvforecast.model import Config


def workbook():
    frame = pd.DataFrame({"Updated Time": pd.date_range("2025-01-01", periods=600, freq="5min"),
                          "Production Power(W)": [float(i % 100) for i in range(600)]})
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.iloc[:300].to_excel(writer, sheet_name="Wrong month", index=False)
        pd.concat([frame.iloc[299:], pd.DataFrame({"Updated Time": [pd.Timestamp("2025-02-01")],
                                                 "Production Power(W)": [None]})]).to_excel(writer, sheet_name="Second", index=False)
        frame.iloc[:0].to_excel(writer, sheet_name="Empty", index=False)
    return output.getvalue()


def test_all_sheets_provenance_and_split():
    dataset = load_master(workbook(), "master.xlsx")
    assert len(dataset.clean) == 600
    assert dataset.report["status_counts"]["identical_duplicate_removed"] == 1
    assert dataset.audit.iloc[300].source_sheet == "Second"
    assert dataset.audit.iloc[300].source_excel_row == 2
    assert dataset.audit.iloc[-1].status == "invalid_power"
    config = experiment_config(dataset, [Config(lookback=24)])
    assert [part["rows"] for part in config["partitions"].values()] == [420, 60, 60, 60]
    assert config["boundaries"][0] == dataset.clean.timestamp.iloc[420].isoformat()
    assert config["partitions"]["calibration"]["windows"]["24"] == 31


def test_inadequate_calibration_is_rejected():
    dataset = load_master(workbook(), "master.xlsx")
    dataset.clean = dataset.clean.iloc[:300]
    with pytest.raises(ValueError, match="19 window"):
        experiment_config(dataset, [Config(lookback=24)])


def test_master_training_exports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "master.xlsx"
    source.write_bytes(workbook())
    output = tmp_path / "experiment"
    summary = run_experiment(source, output, [Config(lookback=6, epochs=1)])
    assert summary["roundtrip_verified"]
    assert len(summary["metrics"]) == 6
    assert len(json.loads((output / "forecast.json").read_text())["forecasts"]) == 6
    assert (tmp_path / summary["model"]).exists()
    audit = pd.read_csv(tmp_path / summary["audit"] / "audit.csv")
    assert {"source_sheet", "source_excel_row"} <= set(audit.columns)
