# Acceptance & traceability — DTINS PV Forecasting

Scope: offline-first Historical Replay research prototype, sesuai `skills/PRD.md`, `Architecture.md`, `Design_System.md`, dan `Agents.md`. Implementasi tersedia; penerimaan ilmiah pada dataset PLTS aktual memerlukan dataset dan rancangan eksperimen peneliti.

| Requirement | Implementasi | Bukti otomatis |
| --- | --- | --- |
| FR-01 Excel/CSV | `data.read_file`, upload Data Management termasuk sheet Excel | CSV/XLSX roundtrip; empty/malformed/unsupported files |
| FR-02 Column mapping | pemetaan timestamp/daya, timezone dan day-first pada UI/CLI | canonicalization dan parsing timezone |
| FR-03 Validation | audit per baris; invalid timestamp, nonfinite/nonnumeric, negatif, missing, irregular | fixture issues dengan hitungan eksplisit |
| FR-04 Time ordering | sort canonical timestamp sebelum segmentasi | reversed-input test |
| FR-05 Duplicates | keep first identical; quarantine semua conflicting timestamps | identical/conflicting/invalid-value duplicate tests |
| FR-06 Cadence | segmentasi tepat 5 menit, window tidak melewati gap | gap/irregular/window alignment tests |
| FR-07 True zero | nol tetap valid, tanpa imputation | cleaning retains 0 W |
| FR-08 Inference | PyTorch LSTM, input satu fitur, output enam neuron | shape tests, trained model roundtrip |
| FR-09 Energy | semua enam keluaran × 5/60 jam, Wh dan kWh | hand-computed energy cases dan forecast consistency |
| FR-10 PI | split conformal per horizon, quantile finite-sample, calibration terpisah | quantile/bounds/minimum samples/PICP tests |
| FR-11 Replay | source timestamp, forecast origin, replay age, stale blocking | replay timestamp, stale and insufficient sequence tests |
| FR-12 Metrics | MAE/RMSE/R² per horizon, independent test | hand-computed metrics, partition metadata |
| FR-13 Baseline | persistence memakai power terakhir setiap origin yang sama | per-origin baseline alignment assertions |
| FR-14 Export | clean/audit/quality, forecast, metrics, history, metadata/report, paket ZIP | CSV/JSON serialization, CLI audit/forecast, artifact roundtrip |
| FR-15 Metadata | version, training date, lookback, feature, cadence, scaler/calibration/config/software versions | compatibility/checksum and version mismatch rejection |
| FR-16 Automated sync | milestone Later, tidak disertakan sesuai PRD | tidak ada status Live atau akuisisi palsu |

## Pemeriksaan integritas

Scaler hanya menggunakan train. Setiap window input beserta target berada di satu partisi sehingga tidak ada pengamatan bersama antarpartisi. Pengujian mengubah seluruh calibration/test power, melatih ulang dengan seed yang sama, lalu memastikan checkpoint dan hasil seleksi validation tetap identik. Seleksi beberapa kandidat diuji terhadap nilai validation minimum. Calibration dan independent test memiliki cakupan terpisah; test hanya dievaluasi setelah seleksi dan calibration selesai.

Artifact loader menolak checksum rusak, komponen wajib hilang, kontrak feature/horizon/cadence tidak sesuai, atau versi model/scaler/calibration tidak cocok. Checkpoint dibaca dengan `weights_only=True`. ZIP tidak diekstrak ke path dari upload. Tanpa calibration, PI tetap null, bukan angka ilustrasi.

## UI dan desain

Empat halaman diuji dengan Streamlit AppTest pada kondisi kosong dan terisi. Interaksi forecast serta perubahan horizon diuji. Warna sesuai token hijau/blue dari Design System; actual solid blue, forecast dashed green, persistence dotted neutral, PI shaded dan numerik. Forecast-origin boundary ditampilkan. Empat kartu KPI mencantumkan satuan/konteks. Tabel mendampingi grafik, fokus keyboard tetap terlihat, dan kolom Streamlit menumpuk pada layar sempit. Tidak ada foto/dekorasi yang mengganggu pembacaan ilmiah.

## Verifikasi dan batas

Hasil verifikasi workspace terbaru: **25 passed** melalui `python -m pytest -q` dengan `.deps` di `PYTHONPATH`; tidak ada test yang di-skip pada eksekusi ini. Tiga pengujian tambahan memeriksa penggabungan seluruh sheet beserta asal baris, pembagian/kalibrasi, dan pelatihan/ekspor eksperimen Data Master. Pada verifikasi rilis sebelumnya, `python -m compileall -q app.py pvforecast tests` berhasil dan launcher `run.ps1` menjalankan server; `/` dan `/_stcore/health` merespons HTTP 200 (health content: `ok`). Lingkungan uji: Python 3.11.15, PyTorch 2.6.0+cu124 (training CPU), NumPy 2.4.6, pandas 3.1.1, Streamlit 1.67.0, Plotly 6.8.0, openpyxl 3.1.5. Reader XLS tersedia melalui xlrd 2.0.2; roundtrip file diuji untuk CSV dan XLSX.

Dataset pengujian otomatis adalah **sintetis**, hanya untuk memeriksa fungsi; metrik fixture bukan hasil penelitian PLTS. Eksperimen terpisah menggunakan `Data Master.xlsx` telah menghasilkan model lokal, audit dan evaluasi nyata; lihat [hasil Data Master](DATA_MASTER_RESULTS.md). Pemeriksaan HTTP local dan AppTest tidak menggantikan inspeksi visual browser pada seluruh ukuran layar. Model hasil eksperimen belum merupakan penerimaan ilmiah final.

Eksperimen Data Master menetapkan pemetaan kolom, zona Asia/Jakarta, rasio kronologis 70/10/10/10 sesuai pilihan pengguna, batas tanggal aktual, dan konfigurasi terpilih melalui validation. Konvensi integrasi sesuai definisi pengukuran sumber, kecukupan statistik calibration/test, serta interpretasi independensi/seasonality/coverage tetap perlu penilaian peneliti. Semuanya dapat diperiksa melalui konfigurasi, audit, dan laporan tanpa mengubah fitur univariate.
