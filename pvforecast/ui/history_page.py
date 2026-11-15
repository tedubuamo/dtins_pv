import streamlit as st

from pvforecast.ui.common import require_dataset, historical_chart, downloads
from pvforecast.ui.time_format import display_frame, wib_time


def render():
    st.title("Historical Monitoring")
    st.caption("Historical data · Catatan sumber, bukan akuisisi waktu nyata.")
    dataset = require_dataset()
    data = dataset.clean.copy()
    data["timestamp"] = data.timestamp.dt.tz_convert("Asia/Jakarta")
    st.write(f"Pengamatan sumber terakhir: {wib_time(data.timestamp.iloc[-1])}")
    dates = st.date_input("Rentang tanggal", (data.timestamp.min().date(), data.timestamp.max().date()),
                          min_value=data.timestamp.min().date(), max_value=data.timestamp.max().date(), format="DD-MM-YYYY")
    if len(dates) != 2:
        st.info("Pilih tanggal awal dan akhir.")
        return
    selected = data.loc[(data.timestamp.dt.date >= dates[0]) & (data.timestamp.dt.date <= dates[1])]
    if selected.empty:
        st.warning("Tidak ada pengamatan valid pada rentang ini.")
        return
    for col, label, value in zip(st.columns(4), ["Maksimum", "Rata-rata", "Median", "Catatan valid"],
                                 [f"{selected.power_w.max():,.1f} W", f"{selected.power_w.mean():,.1f} W",
                                  f"{selected.power_w.median():,.1f} W", f"{len(selected):,}"]):
        col.metric(label, value)
    st.plotly_chart(historical_chart(selected), width="stretch")
    st.caption("Garis terputus pada celah waktu; tidak ada interpolasi pengamatan.")
    day = st.selectbox("Inspeksi harian", sorted(selected.timestamp.dt.date.unique()), format_func=lambda d: d.strftime("%d-%m-%Y"))
    daily = selected.loc[selected.timestamp.dt.date == day]
    st.plotly_chart(historical_chart(daily), width="stretch", key="daily")
    st.dataframe(display_frame(daily), hide_index=True, width="stretch")
    downloads(selected, "historical_selection", "Unduh rentang terpilih")
