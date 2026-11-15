"""Horizon metrics and finite-sample split conformal intervals."""
import math
import numpy as np
import pandas as pd

HORIZONS = (5, 10, 15, 20, 25, 30)


def paired(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if actual.ndim != 2 or actual.shape[1] != 6 or actual.shape != predicted.shape or not len(actual):
        raise ValueError("Actual dan prediksi harus memiliki bentuk (n, 6).")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Actual/prediksi harus finite.")
    return actual, predicted


def calibrate(actual, predicted, alpha=0.05):
    actual, predicted = paired(actual, predicted)
    if not 0 < alpha < 1:
        raise ValueError("Alpha harus di antara 0 dan 1.")
    rank = math.ceil((len(actual) + 1) * (1 - alpha))
    if rank > len(actual):
        raise ValueError("Kalibrasi 95% memerlukan minimal 19 window; tambah data kalibrasi.")
    return np.sort(np.abs(actual - predicted), axis=0)[rank - 1]


def intervals(predicted, quantiles):
    q = np.asarray(quantiles, dtype=float)
    if q.shape != (6,) or not np.isfinite(q).all() or np.any(q < 0):
        raise ValueError("Kuantil kalibrasi harus enam nilai finite nonnegatif.")
    return np.asarray(predicted) - q, np.asarray(predicted) + q


def metrics(actual, predicted, baseline, quantiles=None, partition="test"):
    actual, predicted = paired(actual, predicted)
    _, baseline = paired(actual, baseline)
    rows = []
    bounds = intervals(predicted, quantiles) if quantiles is not None else None
    for h, minutes in enumerate(HORIZONS):
        residual = actual[:, h] - predicted[:, h]
        base_error = actual[:, h] - baseline[:, h]
        denom = np.sum((actual[:, h] - actual[:, h].mean()) ** 2)
        rows.append({"minutes_ahead": minutes, "samples": len(actual), "partition": partition,
                     "lstm_mae_w": float(np.mean(np.abs(residual))),
                     "lstm_rmse_w": float(np.sqrt(np.mean(residual**2))),
                     "lstm_r2": float(1 - np.sum(residual**2)/denom) if denom > 0 else None,
                     "persistence_mae_w": float(np.mean(np.abs(base_error))),
                     "persistence_rmse_w": float(np.sqrt(np.mean(base_error**2))),
                     "pi_nominal": .95 if bounds is not None else None,
                     "picp": float(np.mean((actual[:, h] >= bounds[0][:, h]) &
                                            (actual[:, h] <= bounds[1][:, h]))) if bounds else None,
                     "mean_interval_width_w": float(np.mean(bounds[1][:, h]-bounds[0][:, h])) if bounds else None})
    return pd.DataFrame(rows)


def energy_wh(predictions):
    values = np.asarray(predictions, dtype=float)
    if values.shape != (6,) or not np.isfinite(values).all():
        raise ValueError("Energi membutuhkan enam prediksi daya finite.")
    # Right-rectangle approximation: interval-end forecasts represent each 5-minute interval.
    return float(values.sum() * 5 / 60)
