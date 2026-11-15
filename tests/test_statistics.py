import numpy as np
import pytest

from pvforecast.statistics import calibrate, intervals, metrics, energy_wh


def test_metrics_hand_computed_and_constant_r2():
    actual = np.repeat(np.array([[1.], [3.]]), 6, axis=1)
    predicted = np.repeat(np.array([[2.], [2.]]), 6, axis=1)
    result = metrics(actual, predicted, actual, np.ones(6))
    assert result.lstm_mae_w.tolist() == [1] * 6
    assert result.lstm_rmse_w.tolist() == [1] * 6
    assert result.lstm_r2.tolist() == [0] * 6
    assert result.persistence_mae_w.tolist() == [0] * 6
    assert result.picp.tolist() == [1] * 6
    assert result.mean_interval_width_w.tolist() == [2] * 6
    assert metrics(actual * 0, predicted, actual).lstm_r2.isna().all()


def test_finite_sample_quantile_not_interpolated():
    actual = np.arange(1, 21, dtype=float)[:, None] * np.arange(1, 7)[None, :]
    q = calibrate(actual, np.zeros_like(actual))
    np.testing.assert_equal(q, 20 * np.arange(1, 7))
    lower, upper = intervals(np.ones(6), q)
    assert lower[0] == -19 and upper[0] == 21  # no silent clipping
    with pytest.raises(ValueError, match="19"):
        calibrate(actual[:18], actual[:18])
    for invalid in ([1], [-1]*6, [np.inf]*6):
        with pytest.raises(ValueError):
            intervals(np.ones(6), invalid)


def test_energy_uses_all_six_outputs_and_units():
    assert energy_wh([1000] * 6) == 500
    assert energy_wh([0, 120, 240, 360, 480, 600]) == 150
    with pytest.raises(ValueError):
        energy_wh([1, 2, 3])
    with pytest.raises(ValueError):
        metrics(np.zeros((2, 6)), np.zeros((1, 6)), np.zeros((2, 6)))
