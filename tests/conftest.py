import numpy as np
import pandas as pd
import pytest

from pvforecast.data import prepare
from pvforecast.model import Config, train


@pytest.fixture(scope="session")
def experiment():
    # Synthetic fixture only. No claims about measured PV performance.
    raw = pd.DataFrame({"timestamp": pd.date_range("2025-01-01", periods=240, freq="5min", tz="Asia/Jakarta"),
                        "power_w": np.maximum(0, 200 + 100 * np.sin(np.arange(240)/12))})
    dataset = prepare(raw, "timestamp", "power_w", "Asia/Jakarta", source_file="synthetic_test_fixture.csv")
    cuts = [raw.timestamp.iloc[i].isoformat() for i in (60, 120, 180)]
    bundle = train(dataset.clean, cuts, [Config(lookback=6, epochs=2, patience=1)], dataset.report)
    return dataset, bundle
