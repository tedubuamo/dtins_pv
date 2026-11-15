from pathlib import Path
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest
APP = Path(__file__).resolve().parents[1] / "app.py"


def test_empty_dashboard_pages(monkeypatch):
    monkeypatch.setattr("pvforecast.ui.startup.load_default_experiment", lambda root: None)
    app = AppTest.from_file(APP, default_timeout=30).run()
    for page in ("Data Management", "Historical Monitoring", "LSTM Forecasting", "Model Validation"):
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, [e.message for e in app.exception]
        assert not app.error


def test_populated_dashboard_and_forecast(experiment):
    dataset, bundle = experiment
    app = AppTest.from_file(APP, default_timeout=30)
    app.session_state["dataset"] = dataset
    app.session_state["bundle"] = bundle
    app.run()
    for page in ("Data Management", "Historical Monitoring", "Model Validation", "LSTM Forecasting"):
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, [e.message for e in app.exception]
        assert not app.error
    next(b for b in app.button if b.label == "Jalankan forecast").click().run()
    assert not app.exception, [e.message for e in app.exception]
    assert not app.error
    assert len(app.metric) == 4
    assert len(app.session_state["forecast"]["forecasts"]) == 6
    app.select_slider[0].set_value(5).run()
    assert not app.exception
    assert "+5 min" in app.metric[1].label


def test_default_experiment_is_active_on_first_visit(experiment, monkeypatch):
    monkeypatch.setattr("pvforecast.ui.startup.load_default_experiment", lambda root: experiment)
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert app.session_state["dataset"].report["source_file"] == "synthetic_test_fixture.csv"
    assert app.session_state["bundle"].metadata["model_version"] == experiment[1].metadata["model_version"]
    app.sidebar.radio[0].set_value("LSTM Forecasting").run()
    assert app.text_input[0].value.endswith(" WIB")
    assert "+07:00" not in app.text_input[0].value
    next(b for b in app.button if b.label == "Jalankan forecast").click().run()
    assert not app.exception
    assert not app.error
    assert len(app.session_state["forecast"]["forecasts"]) == 6


def test_startup_failure_and_existing_session(monkeypatch):
    from pvforecast.ui.startup import initialize_session
    def broken(root):
        raise ValueError("checksum mismatch")
    monkeypatch.setattr("pvforecast.ui.startup.load_default_experiment", broken)
    state = {}
    initialize_session(state, APP.parent)
    assert "checksum mismatch" in state["startup_error"]
    existing = {"dataset": "manual dataset", "bundle": "manual model"}
    initialize_session(existing, APP.parent)
    assert existing["dataset"] == "manual dataset"
    assert "startup_error" not in existing


def test_fragmented_history_keeps_gaps(experiment):
    from pvforecast.ui.common import historical_chart
    frame = experiment[0].clean.drop(index=12)
    chart = historical_chart(frame)
    assert len(chart.data) == 1
    assert chart.data[0].connectgaps is False
    assert sum(value is None for value in chart.data[0].x) == 1
    assert len(chart.data[0].x) == len(frame) + 1


def test_saved_startup_pair_and_mismatched_data(experiment, tmp_path):
    from dataclasses import replace
    import json
    from pvforecast.model import pack
    from pvforecast.ui.startup import load_default_experiment
    dataset, bundle = experiment
    for folder in ("configs", "run", "audit"):
        (tmp_path / folder).mkdir()
    (tmp_path / "configs/dashboard.json").write_text(json.dumps({"experiment": "run"}))
    (tmp_path / "run/summary.json").write_text(json.dumps({"model": "model.zip", "audit": "audit"}))
    compatible = replace(bundle, metadata={**bundle.metadata, "provenance": dataset.report})
    (tmp_path / "model.zip").write_bytes(pack(compatible))
    (tmp_path / "audit/quality.json").write_text(json.dumps(dataset.report))
    dataset.clean.to_csv(tmp_path / "audit/clean.csv", index=False)
    dataset.audit.to_csv(tmp_path / "audit/audit.csv", index=False)
    loaded, model = load_default_experiment(tmp_path)
    assert len(loaded.clean) == len(dataset.clean)
    assert model.metadata["model_version"] == bundle.metadata["model_version"]
    altered = dataset.clean.copy()
    altered.loc[0, "power_w"] += 1
    altered.to_csv(tmp_path / "audit/clean.csv", index=False)
    with pytest.raises(ValueError, match="tidak cocok"):
        load_default_experiment(tmp_path)


def test_cloud_default_without_local_artifact_folders(tmp_path):
    import shutil
    from pvforecast.ui.startup import load_default_experiment
    from pvforecast.forecast import forecast
    root = APP.parent
    shutil.copytree(root / "deployment", tmp_path / "deployment")
    (tmp_path / "configs").mkdir()
    shutil.copyfile(root / "configs/dashboard.json", tmp_path / "configs/dashboard.json")
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "artifacts").exists()
    dataset, bundle = load_default_experiment(tmp_path)
    assert dataset.report["source_file"] == "Data Master.xlsx"
    assert len(dataset.clean) == 51226
    assert len(dataset.audit) == 52592
    assert bundle.metadata["model_version"] == "lstm-20261115T115218576744Z"
    result = forecast(dataset, bundle, "2025-11-10T07:25:00+07:00")
    assert len(result["forecasts"]) == 6


def test_windows_summary_paths_are_portable():
    from pathlib import PurePosixPath
    from pvforecast.ui.startup import project_path
    assert project_path(PurePosixPath("/app"), "deployment\\default\\model.zip") == PurePosixPath("/app/deployment/default/model.zip")
