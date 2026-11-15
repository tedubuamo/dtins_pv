"""PyTorch LSTM with validation-only selection and portable artifact bundles."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import logging
from pathlib import Path
import platform
import random
import zipfile

import numpy as np
import pandas as pd
import torch
from torch import nn

from pvforecast.data import Scale, dataset_hash, split_data, windows
from pvforecast.statistics import calibrate, intervals, metrics, HORIZONS

LOG = logging.getLogger(__name__)


@dataclass
class Config:
    lookback: int = 12
    hidden: int = 32
    layers: int = 1
    dropout: float = 0.1
    learning_rate: float = .001
    batch_size: int = 32
    epochs: int = 100
    patience: int = 10
    seed: int = 42

    def validate(self):
        if self.lookback not in (6, 12, 24) or self.hidden not in (32, 64, 128):
            raise ValueError("Lookback/hidden di luar kandidat eksperimen.")
        if self.layers not in (1, 2) or not 0 <= self.dropout <= .2:
            raise ValueError("Layer/dropout tidak valid.")
        if self.learning_rate not in (.001, .0005) or self.batch_size not in (16, 32, 64):
            raise ValueError("Learning rate/batch size tidak valid.")
        if not 1 <= self.epochs <= 1000 or not 1 <= self.patience <= 100:
            raise ValueError("Epoch/patience tidak valid.")


class LSTM(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.lstm = nn.LSTM(1, config.hidden, config.layers, batch_first=True,
                            dropout=config.dropout if config.layers > 1 else 0)
        self.dropout = nn.Dropout(config.dropout)
        self.output = nn.Linear(config.hidden, 6)

    def forward(self, x):
        if x.ndim != 3 or x.shape[-1] != 1:
            raise ValueError("Input harus (batch, lookback, 1).")
        sequence, _ = self.lstm(x)
        return self.output(self.dropout(sequence[:, -1]))


@dataclass
class Bundle:
    model: LSTM
    scaler: Scale
    quantiles: np.ndarray | None
    metadata: dict
    history: pd.DataFrame
    scores: pd.DataFrame
    predictions: pd.DataFrame


def predict(model, scaler, x, batch_size=1024):
    model.eval()
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(x), batch_size):
            tensor = torch.from_numpy(scaler.transform(x[start:start+batch_size]))
            outputs.append(scaler.inverse(model(tensor).numpy()))
    result = np.concatenate(outputs)
    if result.shape != (len(x), 6) or not np.isfinite(result).all():
        raise ValueError("Output model tidak valid.")
    return result


def train(frame, boundaries, candidates, provenance=None, progress=None):
    if not candidates:
        raise ValueError("Pilih minimal satu kandidat.")
    for config in candidates:
        config.validate()
    parts = split_data(frame, boundaries)
    scaler = Scale.fit(parts["train"].power_w)
    # Check every candidate and partition before expensive training starts.
    for config in candidates:
        for name, part in parts.items():
            _, targets, _ = windows(part, config.lookback)
            if name == "calibration" and len(targets) < 19:
                raise ValueError("Kalibrasi 95% memerlukan minimal 19 window untuk setiap kandidat.")
    torch.set_num_threads(min(4, torch.get_num_threads()))
    torch.use_deterministic_algorithms(True)
    best_loss, selected, selected_state = float("inf"), None, None
    histories, trials = [], []
    for trial, config in enumerate(candidates):
        random.seed(config.seed)
        np.random.seed(config.seed)
        torch.manual_seed(config.seed)
        model = LSTM(config)
        optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
        criterion = nn.MSELoss()
        tx, ty, _ = windows(parts["train"], config.lookback)
        vx, vy, _ = windows(parts["validation"], config.lookback)
        tx, ty = torch.from_numpy(scaler.transform(tx)), torch.from_numpy(scaler.transform(ty))
        vx, vy = torch.from_numpy(scaler.transform(vx)), torch.from_numpy(scaler.transform(vy))
        trial_best, state, wait, best_epoch = float("inf"), None, 0, 0
        for epoch in range(config.epochs):
            model.train()
            total = 0.
            # No shuffling: deterministic chronological mini-batches.
            for start in range(0, len(tx), config.batch_size):
                optimizer.zero_grad()
                loss = criterion(model(tx[start:start+config.batch_size]), ty[start:start+config.batch_size])
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                total += loss.item() * len(tx[start:start+config.batch_size])
            model.eval()
            with torch.inference_mode():
                valid_total = 0.
                for start in range(0, len(vx), 1024):
                    valid_total += criterion(model(vx[start:start+1024]), vy[start:start+1024]).item() * len(vx[start:start+1024])
                valid_loss = valid_total / len(vx)
            if not np.isfinite(valid_loss):
                raise ValueError("Loss tidak finite. Periksa rentang data dan konfigurasi.")
            histories.append({"trial": trial + 1, "epoch": epoch + 1,
                              "train_mse_scaled": total / len(tx), "validation_mse_scaled": valid_loss})
            if progress:
                progress(trial + 1, len(candidates), epoch + 1, valid_loss)
            if valid_loss < trial_best:
                trial_best, best_epoch, wait = valid_loss, epoch + 1, 0
                state = {key: value.detach().clone() for key, value in model.state_dict().items()}
            else:
                wait += 1
            if wait >= config.patience:
                break
        trials.append({"config": asdict(config), "validation_mse_scaled": trial_best, "best_epoch": best_epoch})
        if trial_best < best_loss:
            best_loss, selected, selected_state = trial_best, config, state
    model = LSTM(selected)
    model.load_state_dict(selected_state)
    model.eval()
    cx, cy, corigins = windows(parts["calibration"], selected.lookback)
    cp = predict(model, scaler, cx)
    q = calibrate(cy, cp)  # Never uses independent test residuals.
    x, y, origins = windows(parts["test"], selected.lookback)
    predicted = predict(model, scaler, x)
    persistence = np.repeat(x[:, -1, 0, None], 6, axis=1)
    scores = metrics(y, predicted, persistence, q)
    lower, upper = intervals(predicted, q)
    version = "lstm-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    rows = []
    for index, origin in enumerate(origins):
        for h, minutes in enumerate(HORIZONS):
            rows.append({"forecast_origin": origin.isoformat(), "timestamp": (origin + pd.Timedelta(minutes=minutes)).isoformat(),
                         "minutes_ahead": minutes, "actual_w": float(y[index, h]),
                         "power_w": float(predicted[index, h]), "persistence_w": float(persistence[index, h]),
                         "lower_95_w": float(lower[index, h]), "upper_95_w": float(upper[index, h]),
                         "model_version": version, "partition": "test"})
    metadata = {"schema_version": 1, "model_version": version,
                "trained_at": datetime.now(timezone.utc).isoformat(), "config": asdict(selected),
                "trials": trials, "selection_metric": "validation_mse_scaled", "feature": "Production Power (W)",
                "sampling_minutes": 5, "outputs": 6, "horizons": list(HORIZONS),
                "dataset_sha256": dataset_hash(frame), "provenance": provenance or {},
                "partitions": {name: {"start": part.timestamp.min().isoformat(), "end": part.timestamp.max().isoformat(),
                                      "rows": len(part)} for name, part in parts.items()},
                "partition_rule": "[start, end); windows entirely inside each partition; no shared context or targets",
                "scaler": asdict(scaler), "scaler_version": version,
                "calibration": {"version": version, "partition": "calibration", "samples": len(cy),
                                "first_origin": corigins[0].isoformat(), "last_origin": corigins[-1].isoformat(),
                                "method": "split conformal, absolute residual per horizon, order statistic ceil((n+1)*0.95)",
                                "nominal": .95, "clipping": "none"},
                "energy_convention": "Right-rectangle approximation from interval-end power, six 5-minute intervals",
                "prediction_postprocessing": "none; negative predictions retained and flagged",
                "versions": {"python": platform.python_version(), "torch": torch.__version__,
                             "numpy": np.__version__, "pandas": pd.__version__}}
    LOG.info("Training complete: %s", version)
    return Bundle(model, scaler, q, metadata, pd.DataFrame(histories), scores, pd.DataFrame(rows))


def pack(bundle):
    weights = BytesIO()
    torch.save(bundle.model.state_dict(), weights)
    members = {
        "weights.pt": weights.getvalue(),
        "metadata.json": json.dumps(bundle.metadata, indent=2, allow_nan=False).encode(),
        "scaler.json": json.dumps({"version": bundle.metadata["model_version"], **asdict(bundle.scaler)}).encode(),
        "history.csv": bundle.history.to_csv(index=False).encode(),
        "metrics.csv": bundle.scores.to_csv(index=False).encode(),
        "test_predictions.csv": bundle.predictions.to_csv(index=False).encode(),
    }
    if bundle.quantiles is not None:
        members["calibration.json"] = json.dumps({"version": bundle.metadata["model_version"],
                                                  "quantiles_w": bundle.quantiles.tolist()}).encode()
    members["manifest.json"] = json.dumps({name: sha256(value).hexdigest() for name, value in members.items()}).encode()
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return output.getvalue()


def unpack(content):
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if len(set(archive.namelist())) != len(archive.namelist()):
                raise ValueError("Nama artifact duplikat dalam ZIP.")
            if sum(info.file_size for info in archive.infolist()) > 250_000_000:
                raise ValueError("Paket model terlalu besar.")
            manifest = json.loads(archive.read("manifest.json"))
            for name in ("weights.pt", "metadata.json", "scaler.json", "history.csv", "metrics.csv", "test_predictions.csv"):
                if name not in manifest:
                    raise ValueError(f"Artifact wajib hilang: {name}")
            for name, digest in manifest.items():
                if sha256(archive.read(name)).hexdigest() != digest:
                    raise ValueError(f"Checksum artifact tidak cocok: {name}")
            metadata = json.loads(archive.read("metadata.json"))
            version = metadata["model_version"]
            if (metadata["schema_version"] != 1 or metadata["feature"] != "Production Power (W)"
                    or metadata["sampling_minutes"] != 5 or metadata["outputs"] != 6
                    or metadata["horizons"] != list(HORIZONS)):
                raise ValueError("Kontrak model tidak kompatibel.")
            s = json.loads(archive.read("scaler.json"))
            if s.pop("version") != version or metadata["scaler_version"] != version or s != metadata["scaler"]:
                raise ValueError("Versi scaler tidak cocok dengan model.")
            scaler = Scale(**s)
            if not np.isfinite([scaler.minimum, scaler.span]).all() or scaler.span <= 0:
                raise ValueError("Parameter scaler tidak valid.")
            q = None
            if "calibration.json" in archive.namelist():
                if "calibration.json" not in manifest:
                    raise ValueError("Kalibrasi tanpa checksum.")
                c = json.loads(archive.read("calibration.json"))
                if c["version"] != version or metadata["calibration"]["version"] != version:
                    raise ValueError("Versi kalibrasi tidak cocok.")
                q = np.asarray(c["quantiles_w"], dtype=float)
                intervals(np.zeros(6), q)
            config = Config(**metadata["config"])
            config.validate()
            model = LSTM(config)
            model.load_state_dict(torch.load(BytesIO(archive.read("weights.pt")), map_location="cpu", weights_only=True))
            model.eval()
            return Bundle(model, scaler, q, metadata,
                          pd.read_csv(BytesIO(archive.read("history.csv"))),
                          pd.read_csv(BytesIO(archive.read("metrics.csv"))),
                          pd.read_csv(BytesIO(archive.read("test_predictions.csv"))))
    except Exception as exc:
        raise ValueError(f"Paket model tidak valid: {exc}") from exc


def save_bundle(bundle, directory="artifacts"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{bundle.metadata['model_version']}.zip"
    path.write_bytes(pack(bundle))
    return path
