import pandas as pd
import pytest

from pvforecast.ui.time_format import wib_time, parse_wib_input, chart_times, display_frame, display_metadata


def test_wib_conversion_does_not_shift_local_time_twice():
    assert wib_time("2025-11-10T00:25:00Z") == "10-11-2025 07:25 WIB"
    assert wib_time("2025-11-10T07:25:00+07:00") == "10-11-2025 07:25 WIB"
    assert wib_time("2025-11-10 07:25") == "10-11-2025 07:25 WIB"
    assert wib_time("2025-11-09T18:25:00Z") == "10-11-2025 01:25 WIB"


def test_replay_input_is_day_first_and_localized():
    expected = pd.Timestamp("2025-04-03 07:25", tz="Asia/Jakarta")
    assert parse_wib_input("03-04-2025 07:25 WIB") == expected
    assert parse_wib_input("03-04-2025 07:25") == expected
    with pytest.raises(ValueError, match="DD-MM-YYYY"):
        parse_wib_input("31-02-2025 07:25 WIB")


def test_table_display_preserves_data_and_invalid_audit_values():
    source = pd.DataFrame({"timestamp": ["2025-11-10T00:25:00Z", "2025-11-10T07:25:00+07:00"],
                           "source_timestamp": ["2025/11/10 07:25", "invalid date"],
                           "power_w": [0, 10]})
    shown = display_frame(source)
    assert shown.timestamp.tolist() == ["10-11-2025 07:25 WIB"] * 2
    assert shown.source_timestamp.tolist() == ["10-11-2025 07:25 WIB", "invalid date"]
    assert source.timestamp.iloc[0] == "2025-11-10T00:25:00Z"
    assert shown.power_w.tolist() == [0, 10]


def test_chart_and_metadata_match_wib_clock():
    times = pd.Series(["2025-11-10T00:25:00Z"])
    assert chart_times(times).iloc[0] == pd.Timestamp("2025-11-10 07:25")
    original = {"trained_at": "2025-11-10T00:25:00Z", "nested": [{"start": "2025-11-10T07:25:00+07:00"}],
                "model_version": "lstm-20261115T115218576744Z"}
    shown = display_metadata(original)
    assert shown["trained_at"] == "10-11-2025 07:25 WIB"
    assert shown["nested"][0]["start"] == "10-11-2025 07:25 WIB"
    assert original["trained_at"].endswith("Z")
    assert shown["model_version"] == original["model_version"]
