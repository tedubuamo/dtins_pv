import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pvforecast.forecast import forecast, forecast_table
from pvforecast.ui.common import require_dataset, require_model, downloads, historical_chart
from pvforecast.ui.time_format import wib_time, parse_wib_input, chart_times, display_frame, display_metadata


def render():
    st.title("LSTM Forecasting")
    dataset = require_dataset()
    bundle = require_model()
    data = dataset.clean
    st.caption(f"Historical Replay · sumber terakhir {wib_time(data.timestamp.iloc[-1])}")
    eligible = data.loc[data.groupby("segment").cumcount().ge(bundle.metadata["config"]["lookback"] - 1), "timestamp"]
    default_origin = eligible.iloc[-1] if not eligible.empty else data.timestamp.iloc[-1]
    replay = st.text_input("Waktu replay (DD-MM-YYYY HH:mm WIB)", wib_time(default_origin),
                           help="Contoh: 10-11-2025 07:25 WIB. Jam menggunakan Waktu Indonesia Barat.")
    if st.button("Jalankan forecast", type="primary"):
        st.session_state.pop("forecast", None)
        try:
            st.session_state["forecast"] = forecast(dataset, bundle, parse_wib_input(replay))
        except Exception as exc:
            st.error(str(exc))
    result = st.session_state.get("forecast")
    if result is None:
        st.info("Pilih forecast origin lalu jalankan model. Tidak ada nilai prediksi sebelum inferensi.")
        return
    st.write(f"Waktu awal prediksi: {wib_time(result['forecast_origin'])} · model {result['model_version']}")
    for warning in result["warnings"]:
        st.warning(warning)
    horizon = st.select_slider("Horizon", options=[5, 10, 15, 20, 25, 30], value=30,
                               format_func=lambda h: f"+{h} min")
    row = next(r for r in result["forecasts"] if r["minutes_ahead"] == horizon)
    cols = st.columns(4)
    cols[0].metric("Actual Power", f"{result['actual_power_w']:,.1f} W")
    cols[1].metric(f"Forecast Power · +{horizon} min", f"{row['power_w']:,.1f} W")
    cols[2].metric("Forecast Energy · 30 min", f"{result['energy_30m_kwh']:.3f} kWh")
    pi = f"{row['lower_95_w']:,.0f} – {row['upper_95_w']:,.0f} W" if row["lower_95_w"] is not None else "Tidak tersedia"
    cols[3].metric("Prediction Interval 95%", pi)
    if bundle.quantiles is None:
        st.warning("Kalibrasi tidak tersedia. PI 95% belum dapat ditampilkan.")
    table = forecast_table(result)
    times = chart_times(table.timestamp)
    origin = pd.Timestamp(result["forecast_origin"])
    context = data.loc[(data.timestamp <= origin) & (data.timestamp >= origin - pd.Timedelta(hours=2))]
    chart = historical_chart(context)
    if bundle.quantiles is not None:
        chart.add_trace(go.Scatter(x=times, y=table.upper_95_w, mode="lines", line=dict(width=0), showlegend=False, name="Upper 95% (W)"))
        chart.add_trace(go.Scatter(x=times, y=table.lower_95_w, mode="lines", line=dict(width=0),
                                  fill="tonexty", fillcolor="rgba(61,149,96,0.18)", name="PI 95% (W)"))
    chart.add_trace(go.Scatter(x=times, y=table.power_w, name="Forecast (W)", mode="lines+markers", line=dict(color="#1F8A55", dash="dash")))
    if st.checkbox("Tampilkan persistence", value=True):
        chart.add_trace(go.Scatter(x=times, y=table.persistence_w, name="Persistence (W)", line=dict(color="#89938C", dash="dot")))
    if st.checkbox("Tampilkan actual setelah origin (jika tersedia)"):
        chart.add_trace(go.Scatter(x=times, y=table.actual_w, name="Actual setelah origin (W)", line=dict(color="#2878B8")))
    local_origin = origin.tz_convert("Asia/Jakarta").tz_localize(None).isoformat()
    chart.add_shape(type="line", x0=local_origin, x1=local_origin, y0=0, y1=1,
                    yref="paper", line=dict(color="#647067", dash="dot"))
    chart.add_annotation(x=local_origin, y=1, yref="paper", text="Awal prediksi (WIB)", showarrow=False)
    st.plotly_chart(chart, width="stretch")
    st.dataframe(display_frame(table), hide_index=True, width="stretch")
    st.caption("Energi 30 menit = Σ enam prediksi daya × 5/60 jam. Aproksimasi persegi kanan dari daya akhir interval; Wh / 1000 = kWh. Batas PI tidak di-clipping.")
    downloads(table, "forecast", "Unduh forecast")
    downloads(result, "forecast_result", "Unduh forecast")
    with st.expander("Metadata model dan kalibrasi"):
        st.json(display_metadata(bundle.metadata))
