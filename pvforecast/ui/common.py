import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pvforecast.ui.time_format import chart_times


def downloads(data, name, label="Unduh"):
    if isinstance(data, pd.DataFrame):
        st.download_button(label + " CSV", data.to_csv(index=False).encode(), name + ".csv", "text/csv", key=name+"csv")
    else:
        st.download_button(label + " JSON", json.dumps(data, indent=2, allow_nan=False, default=str), name + ".json", "application/json", key=name+"json")


def require_dataset():
    dataset = st.session_state.get("dataset")
    if dataset is None:
        st.info("Impor Excel/CSV di Data Management untuk mulai. Diperlukan timestamp dan Production Power (W).")
        st.stop()
    return dataset


def require_model():
    bundle = st.session_state.get("bundle")
    if bundle is None:
        st.info("Model belum dimuat. Latih model atau muat paket ZIP di Model Validation.")
        st.stop()
    return bundle


def historical_chart(frame):
    # One trace with explicit gaps keeps large, fragmented workbooks responsive.
    ordered = frame.sort_values("timestamp")
    breaks = ordered.timestamp.diff().ne(pd.Timedelta(minutes=5)).to_numpy()
    local_times = chart_times(ordered.timestamp)
    x, y = [], []
    for index, (stamp, power, gap) in enumerate(zip(local_times, ordered.power_w, breaks)):
        if index and gap:
            x.append(None)
            y.append(None)
        x.append(stamp)
        y.append(power)
    chart = go.Figure()
    chart.add_trace(go.Scatter(x=x, y=y, mode="lines", connectgaps=False,
                              name="Actual (W)", line=dict(color="#2878B8", width=2)))
    chart.update_layout(xaxis_title="Tanggal dan waktu (WIB)", yaxis_title="Daya (W)",
                        xaxis=dict(tickformat="%d-%m-%Y<br>%H:%M", hoverformat="%d-%m-%Y %H:%M WIB"),
                        template="plotly_white", margin=dict(l=20, r=20, t=20, b=30), height=380)
    return chart
