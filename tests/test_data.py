from io import BytesIO
import numpy as np
import pandas as pd
import pytest

from pvforecast.data import prepare, read_file, Scale, windows, split_data, segment, parse_time


def frame(n=240):
    return pd.DataFrame({"timestamp": pd.date_range("2025-01-01", periods=n, freq="5min", tz="Asia/Jakarta"),
                         "power_w": np.arange(n, dtype=float)})


def test_cleaning_duplicate_conflicts_invalid_negative_and_zero():
    raw = pd.DataFrame({"time": ["2025-01-01 00:00", "2025-01-01 00:05", "2025-01-01 00:05",
                                      "2025-01-01 00:10", "2025-01-01 00:10", "bad", "2025-01-01 00:15",
                                      "2025-01-01 00:20", "2025-01-01 00:25", "2025-01-01 00:30"],
                        "power": [0, 2, 2, 3, 4, 5, "bad", -1, np.inf, 10]})
    result = prepare(raw, "time", "power", "Asia/Jakarta")
    assert result.clean.power_w.tolist() == [0, 2, 10]
    assert result.report["duplicate_rows"] == 4
    assert result.report["conflicting_timestamps"] == 1
    assert result.report["invalid_timestamps"] == 1
    assert result.report["invalid_power"] == 2
    assert result.report["negative_power"] == 1
    assert result.report["removed_rows"] == 7
    assert sum(result.report["status_counts"].values()) == len(raw)


def test_invalid_rows_are_quarantined_and_cannot_bridge_windows():
    raw = frame(35).drop(index=15)
    dataset = prepare(raw, "timestamp", "power_w", "Asia/Jakarta")
    assert dataset.report["missing_intervals"] == 1
    assert dataset.report["segments"] == 2
    x, y, origins = windows(dataset.clean, 6)
    for origin in origins:
        assert origin + pd.Timedelta(minutes=30) < frame(35).timestamp.iloc[15] or origin - pd.Timedelta(minutes=25) > frame(35).timestamp.iloc[15]


def test_irregular_cadence_and_order():
    raw = frame(3)
    raw.loc[2, "timestamp"] += pd.Timedelta(minutes=1)
    result = prepare(raw.iloc[::-1], "timestamp", "power_w", "Asia/Jakarta")
    assert result.clean.timestamp.is_monotonic_increasing
    assert result.report["irregular_intervals"] == 1
    assert result.report["segments"] == 2


def test_windows_alignment_and_partition_isolation():
    raw = frame()
    boundaries = [raw.timestamp.iloc[i] for i in (60, 120, 180)]
    parts = split_data(raw, boundaries)
    used = []
    for part in parts.values():
        x, y, origins = windows(part, 6)
        assert x.shape[1:] == (6, 1) and y.shape[1:] == (6,)
        assert y[0].tolist() == list(x[0, -1, 0] + np.arange(1, 7))
        assert origins[0] == part.timestamp.iloc[5]
        assert origins[-1] + pd.Timedelta(minutes=30) == part.timestamp.iloc[-1]
        used.append(set(part.timestamp))
    assert all(not a & b for i, a in enumerate(used) for b in used[i+1:])


def test_scaler_training_only_and_inverse():
    scale = Scale.fit([0, 10])
    assert scale.transform([20])[0] == 2  # not refit/clipped on later partitions
    np.testing.assert_allclose(scale.inverse(scale.transform([0, 5, 10])), [0, 5, 10])
    assert Scale.fit([0, 0]).span == 1


def test_timezone_and_dayfirst():
    assert parse_time("2025-01-01T00:00:00Z", "Asia/Jakarta").hour == 7
    assert parse_time("02/01/2025 12:00", "Asia/Jakarta", True).day == 2
    assert pd.isna(parse_time(45000, "Asia/Jakarta"))


def test_readers_and_errors():
    raw = frame(20)
    assert len(read_file(raw.to_csv(index=False).encode(), "sample.csv")) == 20
    buffer = BytesIO()
    raw.assign(timestamp=raw.timestamp.astype(str)).to_excel(buffer, index=False)
    excel = read_file(buffer.getvalue(), "sample.xlsx")
    assert len(prepare(excel, "timestamp", "power_w", "Asia/Jakarta").clean) == 20
    for content, name in [(b"", "empty.csv"), (b"x\n1\n", "one.csv"), (b"x", "bad.xlsx"), (b"x", "bad.txt")]:
        with pytest.raises(ValueError):
            read_file(content, name)
    with pytest.raises(ValueError):
        prepare(pd.DataFrame({"a": ["bad"], "b": ["bad"]}), "a", "b", "Asia/Jakarta")
    with pytest.raises(ValueError):
        split_data(raw, [raw.timestamp.iloc[4]] * 3)
    with pytest.raises(ValueError):
        windows(raw.head(5), 6)


def test_duplicate_with_invalid_value_quarantines_whole_timestamp():
    raw = frame(20)
    duplicate = raw.iloc[[5]].copy()
    duplicate["power_w"] = np.nan
    result = prepare(pd.concat([raw, duplicate]), "timestamp", "power_w", "Asia/Jakarta")
    assert raw.timestamp.iloc[5] not in set(result.clean.timestamp)
