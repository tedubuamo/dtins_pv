from dataclasses import replace
from io import BytesIO
import json
import zipfile

import numpy as np
import pandas as pd
import pytest
import torch

from pvforecast.data import prepare, Scale
from pvforecast.forecast import forecast, forecast_table
from pvforecast.model import Config, LSTM, train, pack, unpack, predict, save_bundle
from pvforecast.storage import persist_dataset


def test_lstm_shapes():
    model = LSTM(Config())
    assert model(torch.zeros((3, 12, 1))).shape == (3, 6)
    with pytest.raises(ValueError):
        model(torch.zeros((3, 12, 2)))


def test_end_to_end_training_roundtrip_and_export(experiment, tmp_path):
    dataset, bundle = experiment
    restored = unpack(pack(bundle))
    path = save_bundle(bundle, tmp_path)
    assert path.exists()
    replay = dataset.clean.timestamp.iloc[220]
    result = forecast(dataset, restored, replay)
    assert len(result["forecasts"]) == 6
    assert result["forecast_origin"] == replay.isoformat()
    assert result["energy_30m_wh"] == pytest.approx(sum(r["power_w"] for r in result["forecasts"]) / 12)
    result2 = forecast(dataset, bundle, replay)
    assert result["forecasts"] == result2["forecasts"]
    table = forecast_table(result)
    assert {"actual_w", "power_w", "forecast_origin", "timestamp", "model_version", "lower_95_w", "upper_95_w"} <= set(table.columns)
    assert len(pd.read_csv(BytesIO(table.to_csv(index=False).encode()))) == 6
    json.dumps(result, allow_nan=False)
    assert len(restored.scores) == 6
    assert restored.scores.partition.eq("test").all()
    assert bundle.metadata["partitions"]["calibration"]["end"] < bundle.metadata["partitions"]["test"]["start"]
    assert bundle.scaler.minimum == pytest.approx(dataset.clean.power_w.iloc[:60].min())
    pred = bundle.predictions
    for _, rows in pred.groupby("forecast_origin"):
        assert rows.persistence_w.nunique() == 1
        origin = pd.Timestamp(rows.forecast_origin.iloc[0])
        assert rows.persistence_w.iloc[0] == pytest.approx(dataset.clean.loc[dataset.clean.timestamp == origin, "power_w"].iloc[0])


def test_missing_calibration_stale_and_short_history(experiment):
    dataset, bundle = experiment
    no_pi = replace(bundle, quantiles=None)
    restored = unpack(pack(no_pi))
    result = forecast(dataset, restored, dataset.clean.timestamp.iloc[-1])
    assert all(r["lower_95_w"] is None for r in result["forecasts"])
    with pytest.raises(ValueError, match="stale"):
        forecast(dataset, bundle, dataset.clean.timestamp.iloc[-1] + pd.Timedelta(minutes=5))
    with pytest.raises(ValueError, match="kontinu"):
        forecast(dataset, bundle, dataset.clean.timestamp.iloc[1])
    with pytest.raises(ValueError, match="zona"):
        forecast(dataset, bundle, "2025-01-01")


def test_mismatched_artifact_rejected(experiment):
    _, bundle = experiment
    source = zipfile.ZipFile(BytesIO(pack(bundle)))
    target = BytesIO()
    with zipfile.ZipFile(target, "w") as output:
        for name in source.namelist():
            content = source.read(name)
            if name == "scaler.json":
                content = b'{"version": "wrong", "minimum": 0, "span": 1}'
            output.writestr(name, content)
    with pytest.raises(ValueError, match="Checksum"):
        unpack(target.getvalue())
    with pytest.raises(ValueError):
        unpack(b"not a zip")


def test_raw_immutable_and_audit_saved(experiment, tmp_path):
    dataset, _ = experiment
    content = b"immutable source"
    path = persist_dataset(content, "../../source.csv", dataset, tmp_path)
    assert (path / "audit.csv").exists()
    assert (path / "quality.json").exists()
    assert list((tmp_path / "raw").glob("*.csv"))[0].read_bytes() == content


def test_calibration_and_test_values_cannot_change_model_selection(experiment):
    dataset, trained = experiment
    altered = dataset.clean.copy()
    altered.loc[120:, "power_w"] += 1000
    cuts = [altered.timestamp.iloc[i] for i in (60, 120, 180)]
    other = train(altered, cuts, [Config(lookback=6, epochs=2, patience=1)])
    assert other.metadata["trials"] == trained.metadata["trials"]
    for key, value in trained.model.state_dict().items():
        assert torch.equal(value, other.model.state_dict()[key])


def test_multiple_candidates_selected_by_validation_only(experiment):
    dataset, _ = experiment
    cuts = [dataset.clean.timestamp.iloc[i] for i in (60, 120, 180)]
    result = train(dataset.clean, cuts, [Config(lookback=6, epochs=1), Config(lookback=12, epochs=1)])
    winning_trial = min(result.metadata["trials"], key=lambda item: item["validation_mse_scaled"])
    assert result.metadata["config"] == winning_trial["config"]


def test_cli_audit_and_forecast(experiment, tmp_path, monkeypatch):
    from pvforecast.__main__ import main
    dataset, bundle = experiment
    data = tmp_path / "fixture.csv"
    dataset.clean.to_csv(data, index=False)
    config = tmp_path / "experiment.json"
    config.write_text(json.dumps({"data": {"timestamp_column": "timestamp", "power_column": "power_w", "timezone": "Asia/Jakarta"}}))
    model = save_bundle(bundle, tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["pvforecast", "audit", "--data", str(data), "--config", str(config)])
    main()
    assert (tmp_path / "data/exports/quality.json").exists()
    monkeypatch.setattr("sys.argv", ["pvforecast", "forecast", "--data", str(data), "--config", str(config),
                                     "--model", str(model), "--origin", dataset.clean.timestamp.iloc[-1].isoformat()])
    main()
    result = json.loads((tmp_path / "data/exports/forecast.json").read_text())
    assert len(result["forecasts"]) == 6


def test_semantic_scaler_version_mismatch_rejected(experiment):
    from hashlib import sha256
    _, bundle = experiment
    with zipfile.ZipFile(BytesIO(pack(bundle))) as source:
        members = {name: source.read(name) for name in source.namelist() if name != "manifest.json"}
    scaler = json.loads(members["scaler.json"])
    scaler["version"] = "incompatible"
    members["scaler.json"] = json.dumps(scaler).encode()
    members["manifest.json"] = json.dumps({n: sha256(v).hexdigest() for n, v in members.items()}).encode()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as output:
        for name, value in members.items():
            output.writestr(name, value)
    with pytest.raises(ValueError, match="Versi scaler"):
        unpack(buffer.getvalue())
