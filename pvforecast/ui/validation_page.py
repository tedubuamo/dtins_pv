import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from pvforecast.data import split_data
from pvforecast.model import Config, train, unpack, pack, save_bundle
from pvforecast.ui.common import downloads
from pvforecast.ui.time_format import wib_time, parse_wib_input, display_frame, display_metadata, chart_times


def activate(bundle):
    st.session_state["bundle"] = bundle
    st.session_state.pop("forecast", None)


def render():
    st.title("Model Validation")
    st.caption("Seleksi: validation · Kalibrasi: calibration · Evaluasi akhir: independent test")
    with st.expander("Muat paket model", expanded="bundle" not in st.session_state):
        upload = st.file_uploader("Paket model kompatibel (.zip)", type="zip")
        if st.button("Muat model", disabled=upload is None):
            try:
                activate(unpack(upload.getvalue()))
                st.success("Model, scaler, dan checksum tervalidasi.")
            except Exception as exc:
                st.error(str(exc))
        local = sorted(Path("artifacts").glob("*.zip"))
        if local:
            chosen = st.selectbox("Model tersimpan lokal", local, format_func=lambda p: p.name)
            if st.button("Muat model lokal"):
                try:
                    activate(unpack(chosen.read_bytes()))
                except Exception as exc:
                    st.error(str(exc))
    dataset = st.session_state.get("dataset")
    with st.expander("Eksperimen dan pelatihan LSTM", expanded="bundle" not in st.session_state):
        st.write("Tentukan batas berdasarkan cakupan data. Tidak ada rasio split otomatis. Semua input dan target window berada sepenuhnya di satu partisi.")
        if dataset is None:
            st.info("Impor dataset terlebih dahulu untuk pelatihan.")
        else:
            st.caption(f"Cakupan: {wib_time(dataset.report['first_timestamp'])} → {wib_time(dataset.report['last_timestamp'])}")
            with st.form("training"):
                cuts = [st.text_input(label, placeholder="DD-MM-YYYY HH:mm WIB") for label in
                        ["Awal validation (akhir train)", "Awal calibration (akhir validation)", "Awal independent test (akhir calibration)"]]
                left, right = st.columns(2)
                lookbacks = left.multiselect("Kandidat look-back (sampel)", [6, 12, 24], default=[12], help="Hanya daya historis; timestamp bukan fitur.")
                hidden = right.multiselect("Kandidat hidden units", [32, 64, 128], default=[32])
                layers = left.selectbox("LSTM layers", [1, 2])
                dropout = right.slider("Dropout", 0., .2, .1, .05)
                lr = left.selectbox("Learning rate", [.001, .0005])
                batch = right.selectbox("Batch size", [16, 32, 64], index=1)
                epochs = left.number_input("Maximum epochs", 1, 1000, 100)
                patience = right.number_input("Early-stopping patience", 1, 100, 10)
                seed = left.number_input("Random seed", 0, 2**31-1, 42)
                approved = st.checkbox("Saya menetapkan batas partisi setelah audit data. Test digunakan hanya setelah seleksi model selesai.")
                submitted = st.form_submit_button("Latih, kalibrasi, dan evaluasi", type="primary")
            if submitted:
                try:
                    if not approved or not all(cuts) or not lookbacks or not hidden:
                        raise ValueError("Isi semua batas, kandidat, dan konfirmasi rancangan eksperimen.")
                    cuts = [parse_wib_input(value).isoformat() for value in cuts]
                    parts = split_data(dataset.clean, cuts)
                    st.dataframe(display_frame(pd.DataFrame([{"partition": n, "rows": len(p), "start": p.timestamp.min(), "end": p.timestamp.max()} for n, p in parts.items()])), hide_index=True)
                    candidates = [Config(lb, hu, layers, dropout, lr, batch, int(epochs), int(patience), int(seed)) for lb in lookbacks for hu in hidden]
                    status = st.empty()
                    with st.spinner("Pelatihan LSTM CPU sedang berjalan..."):
                        bundle = train(dataset.clean, cuts, candidates, dataset.report,
                                       lambda trial, total, epoch, loss: status.caption(f"Kandidat {trial}/{total} · epoch {epoch} · validation MSE {loss:.6f}"))
                        saved = save_bundle(bundle)
                        activate(bundle)
                    st.success(f"Eksperimen selesai; model terbaik berdasarkan validation disimpan di {saved}.")
                except Exception as exc:
                    st.error(str(exc))
    bundle = st.session_state.get("bundle")
    if bundle is None:
        st.info("Belum ada hasil evaluasi. Muat atau latih model untuk melihat metrik nyata.")
        return
    st.subheader("Independent test · hasil per horizon")
    st.caption(f"Model {bundle.metadata['model_version']} · {wib_time(bundle.metadata['trained_at'])}")
    st.dataframe(bundle.scores, hide_index=True, width="stretch")
    comparison = bundle.scores.melt(id_vars="minutes_ahead", value_vars=["lstm_mae_w", "persistence_mae_w", "lstm_rmse_w", "persistence_rmse_w"], var_name="metric", value_name="error_w")
    st.plotly_chart(px.bar(comparison, x="minutes_ahead", y="error_w", color="metric", barmode="group",
                           labels={"minutes_ahead": "Horizon (min)", "error_w": "Error (W)"}, color_discrete_sequence=["#1F6B3A", "#89938C", "#2878B8", "#D99022"]), width="stretch")
    st.caption("MAE/RMSE lebih kecil lebih baik. R² tidak terdefinisi pada target konstan. Tidak ada klaim LSTM selalu mengungguli persistence.")
    if bundle.quantiles is not None:
        chart = px.line(bundle.scores, x="minutes_ahead", y="picp", markers=True,
                        labels={"minutes_ahead": "Horizon (min)", "picp": "Empirical coverage (0–1)"})
        chart.add_hline(y=.95, line_dash="dash", annotation_text="Nominal 95%")
        st.plotly_chart(chart, width="stretch")
        st.plotly_chart(px.bar(bundle.scores, x="minutes_ahead", y="mean_interval_width_w",
                               labels={"minutes_ahead": "Horizon (min)", "mean_interval_width_w": "Mean interval width (W)"}), width="stretch")
        st.info("PI menggunakan split conformal per horizon. Ketergantungan temporal dan pergeseran distribusi dapat menurunkan coverage; nilai empiris test di atas harus dilaporkan bersama lebar interval.")
    else:
        st.warning("Kalibrasi tidak tersedia; PI tidak ditampilkan.")
    selected_h = st.selectbox("Horizon residual (min)", [5, 10, 15, 20, 25, 30])
    residuals = bundle.predictions.loc[bundle.predictions.minutes_ahead == selected_h].copy()
    residuals["residual_w"] = residuals.actual_w - residuals.power_w
    residuals["forecast_origin"] = chart_times(residuals.forecast_origin)
    st.plotly_chart(px.histogram(residuals, x="residual_w", nbins=40, labels={"residual_w": "Actual − forecast (W)"}), width="stretch")
    residual_chart = px.line(residuals, x="forecast_origin", y="residual_w", labels={"residual_w": "Residual (W)", "forecast_origin": "Tanggal dan waktu (WIB)"})
    residual_chart.update_xaxes(tickformat="%d-%m-%Y<br>%H:%M", hoverformat="%d-%m-%Y %H:%M WIB")
    st.plotly_chart(residual_chart, width="stretch")
    st.subheader("Riwayat pelatihan")
    st.plotly_chart(px.line(bundle.history, x="epoch", y=["train_mse_scaled", "validation_mse_scaled"], color="trial"), width="stretch")
    st.json(display_metadata(bundle.metadata))
    downloads(bundle.scores, "test_metrics", "Unduh metrik")
    downloads(bundle.predictions, "test_predictions", "Unduh prediksi test")
    downloads(bundle.history, "training_history", "Unduh riwayat")
    downloads(bundle.metadata, "experiment", "Unduh konfigurasi")
    report = {"metadata": bundle.metadata, "metrics": json.loads(bundle.scores.to_json(orient="records"))}
    downloads(report, "evaluation_report", "Unduh laporan evaluasi")
    st.download_button("Unduh paket model lengkap", pack(bundle), bundle.metadata["model_version"] + ".zip", "application/zip")
