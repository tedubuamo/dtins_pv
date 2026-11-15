"""Historical replay inference and provenance-rich exports."""
import numpy as np
import pandas as pd

from pvforecast.data import dataset_hash, segment, STEP
from pvforecast.model import predict
from pvforecast.statistics import energy_wh, intervals, HORIZONS


def forecast(dataset, bundle, replay_timestamp):
    frame = dataset.clean
    replay = pd.Timestamp(replay_timestamp)
    if replay.tzinfo is None:
        raise ValueError("Replay timestamp harus memiliki zona waktu.")
    history = segment(frame.loc[frame.timestamp <= replay])
    if history.empty:
        raise ValueError("Tidak ada pengamatan sebelum waktu replay.")
    origin = history.timestamp.iloc[-1]
    if replay - origin >= STEP:
        raise ValueError("Sumber stale terhadap waktu replay. Pilih timestamp pengamatan valid yang tersedia.")
    latest = history.loc[history.segment == history.segment.iloc[-1]]
    lookback = bundle.metadata["config"]["lookback"]
    if len(latest) < lookback:
        raise ValueError(f"Perlu {lookback} pengamatan kontinu; hanya ada {len(latest)} sebelum replay.")
    x = latest.power_w.iloc[-lookback:].to_numpy(dtype=np.float32)[None, :, None]
    predicted = predict(bundle.model, bundle.scaler, x)[0]
    bounds = intervals(predicted, bundle.quantiles) if bundle.quantiles is not None else None
    rows = []
    for index, minutes in enumerate(HORIZONS):
        target = origin + pd.Timedelta(minutes=minutes)
        actual = frame.loc[frame.timestamp == target, "power_w"]
        rows.append({"minutes_ahead": minutes, "timestamp": target.isoformat(),
                     "power_w": float(predicted[index]),
                     "actual_w": float(actual.iloc[0]) if len(actual) else None,
                     "persistence_w": float(x[0, -1, 0]),
                     "lower_95_w": float(bounds[0][index]) if bounds else None,
                     "upper_95_w": float(bounds[1][index]) if bounds else None})
    energy = energy_wh(predicted)
    return {"mode": "historical_replay", "source_file": dataset.report["source_file"],
            "source_sha256": dataset.report["source_sha256"], "forecast_origin": origin.isoformat(),
            "dataset_sha256": dataset_hash(frame), "model_config": bundle.metadata["config"],
            "replay_timestamp": replay.isoformat(), "source_age_at_replay_seconds": (replay-origin).total_seconds(),
            "last_observation_timestamp": origin.isoformat(),
            "last_source_timestamp": frame.timestamp.iloc[-1].isoformat(),
            "model_version": bundle.metadata["model_version"], "feature": "Production Power (W)",
            "sampling_minutes": 5, "actual_power_w": float(x[0, -1, 0]),
            "forecasts": rows, "energy_30m_wh": energy, "energy_30m_kwh": energy / 1000,
            "energy_convention": bundle.metadata["energy_convention"],
            "warnings": ["Prediksi negatif tersedia; hasil tanpa clipping untuk menjaga konsistensi evaluasi."] if (predicted < 0).any() else []}


def forecast_table(result):
    frame = pd.DataFrame(result["forecasts"])
    for key in ("forecast_origin", "last_observation_timestamp", "model_version", "mode", "source_file", "source_sha256",
                "energy_30m_wh", "energy_30m_kwh"):
        frame[key] = result[key]
    return frame
