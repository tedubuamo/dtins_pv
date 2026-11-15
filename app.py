"""Run with: python -m streamlit run app.py"""
import logging
from pathlib import Path
import streamlit as st

from pvforecast.ui import data_page, history_page, forecast_page, validation_page
from pvforecast.ui.startup import initialize_session
from pvforecast.ui.time_format import wib_time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
st.set_page_config(page_title="DTINS | PV Forecasting", page_icon="☀", layout="wide")
initialize_session(st.session_state, Path(__file__).resolve().parent)
if st.session_state.get("startup_error"):
    st.warning(st.session_state["startup_error"])
st.markdown("""<style>
 .block-container {max-width:1440px;padding-top:2rem;}
 [data-testid="stMetric"] {background:#fff;border:1px solid #DDE5DE;border-radius:12px;padding:16px;font-variant-numeric:tabular-nums;}
 [data-testid="stSidebar"] {border-right:1px solid #DDE5DE;}
 :focus-visible {outline:3px solid #2878B8!important;outline-offset:3px;}
 h1,h2,h3 {color:#123B2A;}
 @media(max-width:640px){.block-container{padding:1rem;}[data-testid="stMetricValue"]{font-size:1.4rem;}}
 </style>""", unsafe_allow_html=True)
with st.sidebar:
    st.title("DTINS | PV Forecasting")
    st.caption("On-Grid PV 3.5 kWp · Research Prototype")
    st.success("Historical Replay")
    selected = st.radio("Navigasi", ["Data Management", "Historical Monitoring", "LSTM Forecasting", "Model Validation"])
    st.divider()
    dataset = st.session_state.get("dataset")
    if dataset:
        st.caption("Dataset aktif")
        st.write(dataset.report["source_file"])
    st.caption("Sumber terakhir")
    st.write(wib_time(dataset.report["last_timestamp"]) if dataset else "Dataset belum dimuat")
    bundle = st.session_state.get("bundle")
    st.caption("Model version")
    st.write(bundle.metadata["model_version"] if bundle else "Model not loaded")
    st.caption("Input tunggal: Production Power (W) · interval 5 menit · enam horizon")
{"Data Management": data_page.render, "Historical Monitoring": history_page.render,
 "LSTM Forecasting": forecast_page.render, "Model Validation": validation_page.render}[selected]()
