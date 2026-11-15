from io import BytesIO
import pandas as pd
import streamlit as st

from pvforecast.data import read_file, prepare, content_hash
from pvforecast.storage import persist_dataset
from pvforecast.ui.common import downloads, historical_chart
from pvforecast.ui.time_format import display_frame, display_metadata, wib_time


def render():
    st.title("Data Management")
    st.write("Impor dan audit data inverter. Catatan yang hilang tidak diubah menjadi 0 W.")
    upload = st.file_uploader("Data historis · CSV / Excel", type=["csv", "xlsx", "xls"])
    if upload is not None:
        try:
            content = upload.getvalue()
            sheet = 0
            if upload.name.lower().endswith((".xls", ".xlsx")):
                sheets = pd.ExcelFile(BytesIO(content)).sheet_names
                sheet = st.selectbox("Sheet Excel", sheets)
            raw = read_file(content, upload.name, sheet)
            st.caption(f"Preview sumber: {len(raw):,} baris · {len(raw.columns)} kolom")
            st.dataframe(display_frame(raw.head(20)), hide_index=True, width="stretch")
            with st.form("mapping"):
                cols = list(raw.columns)
                left, right = st.columns(2)
                time_col = left.selectbox("Kolom timestamp", cols)
                power_col = right.selectbox("Kolom daya (W)", cols, index=min(1, len(cols)-1))
                zone = st.text_input("Zona waktu untuk timestamp tanpa offset", "Asia/Jakarta")
                dayfirst = st.checkbox("Format tanggal mendahulukan hari (DD/MM/YYYY)")
                st.caption("Kebijakan: simpan duplikat identik pertama; karantina seluruh timestamp duplikat yang bertentangan, nilai invalid, dan daya negatif. Tanpa interpolasi.")
                accepted = st.checkbox("Saya telah memeriksa zona waktu, format tanggal, dan kebijakan pembersihan.")
                replace = st.checkbox("Ganti dataset aktif dan hapus forecast sesi sebelumnya") if "dataset" in st.session_state else True
                submitted = st.form_submit_button("Prepare dataset", type="primary")
            if submitted:
                if not accepted or not replace:
                    st.error("Konfirmasi konfigurasi dan penggantian dataset sebelum melanjutkan.")
                else:
                    with st.spinner("Memvalidasi dan menyimpan audit..."):
                        dataset = prepare(raw, time_col, power_col, zone, dayfirst=dayfirst,
                                          source_file=upload.name, source_hash=content_hash(content))
                        dataset.report["sheet"] = sheet
                        folder = persist_dataset(content, upload.name, dataset)
                        st.session_state["dataset"] = dataset
                        st.session_state.pop("forecast", None)
                    st.success(f"Dataset disiapkan. Audit tersimpan di {folder}.")
        except Exception as exc:
            st.error(str(exc))
    dataset = st.session_state.get("dataset")
    if dataset is None:
        st.info("Belum ada dataset. File sumber tidak akan ditimpa; hasil pembersihan disimpan terpisah.")
        return
    report = dataset.report
    st.subheader("Kualitas data")
    for col, label, value in zip(st.columns(4), ["Baris sumber", "Baris valid", "Segmen kontinu", "Interval hilang"],
                                 [report["original_rows"], report["clean_rows"], report["segments"], report["missing_intervals"]]):
        col.metric(label, f"{value:,}")
    st.caption(f"{report['source_file']} · {wib_time(report['first_timestamp'])} → {wib_time(report['last_timestamp'])} · interval 5 menit")
    lookback = st.session_state.get("bundle").metadata["config"]["lookback"] if st.session_state.get("bundle") else 24
    if report["longest_segment"] < lookback:
        st.error(f"Blocked: segmen terpanjang {report['longest_segment']} baris; perlu {lookback} untuk input model.")
    elif report["removed_rows"] or report["irregular_intervals"]:
        st.warning("Warning: dataset memiliki catatan karantina atau celah waktu. Periksa audit sebelum analisis.")
    else:
        st.success("Ready: tersedia input kontinu. Forecast tetap memerlukan model yang kompatibel.")
    st.json(display_metadata(report))
    st.plotly_chart(historical_chart(dataset.clean), width="stretch")
    st.dataframe(display_frame(dataset.audit), hide_index=True, width="stretch")
    downloads(dataset.clean, "cleaned_data", "Unduh data bersih")
    downloads(dataset.audit, "data_audit", "Unduh audit")
    downloads(report, "data_quality", "Unduh kualitas")
