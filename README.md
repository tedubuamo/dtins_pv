# DTINS | PV Forecasting

Aplikasi riset lokal untuk PLTS On-Grid 3,5 kWp DTINS, FV-ITS. Implementasi mengacu pada empat dokumen dalam `skills/`. **Historical Replay** menggunakan file historis; timestamp komputer tidak dipakai sebagai forecast origin. Input model hanya **Production Power (W)**.

## Menjalankan

Python 3.11 direkomendasikan. Jalankan dari root proyek dengan PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py
```

Buka alamat lokal yang dicetak Streamlit (umumnya `http://localhost:8501`). Instalasi pertama membutuhkan internet; impor, pelatihan, inferensi, dan ekspor berikutnya dapat berjalan offline. GPU tidak diperlukan; pelatihan menggunakan CPU. Dependensi model PyTorch dapat memerlukan unduhan besar.

Shortcut Windows: `powershell -ExecutionPolicy Bypass -File .\run.ps1`. Launcher memakai `.venv` jika tersedia, atau dependensi `.deps` lokal pada workspace pengembangan ini.

1. **Data Management**: unggah CSV/XLSX/XLS, pilih sheet/kolom, tentukan zona waktu dan format tanggal, lalu periksa audit dan siapkan dataset. Timestamp tanpa offset dilokalkan sesuai zona yang dipilih; timestamp ber-offset dikonversi ke zona tersebut. Serial tanggal Excel numerik perlu dikonversi menjadi tanggal terlebih dahulu. CSV numerik memakai titik desimal.
2. **Historical Monitoring**: pilih rentang tanggal, lihat statistik, kurva historis, dan inspeksi harian. Grafik diputus di celah waktu.
3. **Model Validation**: isi tiga batas waktu ber-offset yang menentukan awal validation, calibration, dan test. Pilih kandidat LSTM, kemudian latih. Alternatifnya, muat paket ZIP hasil pelatihan sebelumnya. ZIP lokal tetap dapat dimuat setelah sesi aplikasi ditutup.
4. **LSTM Forecasting**: tentukan timestamp replay dengan offset, jalankan prediksi, periksa enam horizon dan PI, lalu ekspor CSV/JSON.

Dataset dan model aktif disimpan dalam sesi browser. Sumber, audit, dan model tersimpan di disk. Tanpa konfigurasi default, sesi baru memerlukan impor dataset dan pemuatan model kembali. Mengganti dataset meminta konfirmasi dan menghapus hasil forecast sesi sebelumnya.

Jika `configs/dashboard.json` tersedia, sesi baru otomatis memuat pasangan dataset/model dari folder eksperimen yang ditunjuk oleh `experiment`. Konfigurasi saat ini menunjuk `deployment/default`, berisi hasil Data Master 70/10/10/10 yang ikut disertakan dalam repository untuk Streamlit Cloud. Dashboard memeriksa hash dataset dan kesesuaian sumber pelatihan sebelum mengaktifkan keduanya, serta menampilkan kegagalan pemuatan bila berkas belum tersedia. Pilihan dataset/model manual dalam sesi aktif tetap dipertahankan. Halaman forecast mengisi origin awal dengan pengamatan terakhir yang mempunyai input kontinu cukup untuk model aktif. Lihat [paket deployment](deployment/README.md) untuk berkas yang perlu ikut di-push.

Tanggal pada dashboard ditampilkan sebagai `DD-MM-YYYY HH:mm WIB`, misalnya `10-11-2025 07:25 WIB`. Isian waktu replay dan batas partisi pelatihan menggunakan format yang sama (akhiran `WIB` boleh dihilangkan). Grafik dan tooltip memakai jam Asia/Jakarta. Timestamp internal, paket model, dan ekspor CSV/JSON tetap memakai format ISO dengan zona waktu agar dapat diproses ulang secara tepat.

## Metodologi yang diterapkan

- Data diurutkan; nol asli dipertahankan. Tidak ada imputasi atau interpolasi. Timestamp invalid, daya nonnumerik/nonfinite/negatif dikarantina dan tetap tercatat di audit.
- Duplikat identik mempertahankan baris pertama. Seluruh baris pada timestamp dengan nilai bertentangan dikarantina, termasuk konflik nilai valid dengan nilai invalid. Angka pada laporan issue dapat saling tumpang tindih; `status_counts` merupakan klasifikasi eksklusif setiap baris.
- Window hanya dibuat pada segmen kontinu tepat 5 menit. Empat partisi berbatas tanggal tidak berbagi pengamatan, konteks, atau target. Karena seluruh window dibentuk di dalam partisinya, embargo tambahan tidak diperlukan untuk mencegah overlap antarpartisi.
- Batas partisi **tidak diasumsikan**. Peneliti menetapkannya setelah inspeksi data. Setiap partisi perlu minimal `lookback + 6` baris kontinu. Calibration perlu minimal 19 window, sehingga untuk satu segmen perlu `lookback + 24` baris. Ini batas matematis minimum, bukan rekomendasi kecukupan statistik.
- Min-max scaler di-fit hanya dari training; nilai di luar rentang training tidak di-clipping. Semua partisi dan inferensi memakai scaler yang sama.
- LSTM multi-output menerima `(batch, lookback, 1)` dan mengeluarkan `(batch, 6)`, untuk +5, +10, +15, +20, +25, +30 menit. Tidak ada fitur waktu atau cuaca. Kandidat dipilih hanya dari MSE validation pada skala normalisasi; early stopping menyimpan checkpoint validation terbaik. Mini-batch berurutan, tanpa shuffle. Seed dan versi pustaka tercatat.
- Split conformal per horizon menggunakan residual absolut calibration; kuantil adalah order statistic ke-`ceil((n+1) × 0.95)` (indeks satu). Jika rank melebihi jumlah residual, kalibrasi ditolak. PI = prediksi ± kuantil, tanpa clipping. Empirical PICP dan mean interval width dihitung pada independent test. Coverage 95% tidak dijamin pada data dependen waktu atau distribution shift.
- MAE, RMSE dan R² per horizon dilaporkan pada test, bersama persistence pada origin/target yang sama. R² untuk target konstan dilaporkan kosong. Tidak ada klaim LSTM selalu lebih baik. Mengulang tuning berdasarkan hasil test akan merusak independensinya; gunakan test baru untuk eksperimen lanjutan yang dipengaruhi hasil tersebut.
- Energi memakai aproksimasi persegi kanan: `Σ enam prediksi W × (5/60 jam)` menghasilkan Wh; dibagi 1000 untuk kWh. Daya akhir interval dianggap mewakili interval sebelumnya. Ini konvensi integrasi yang dinyatakan, bukan klaim bahwa sumber mengukur rata-rata interval. Prediksi negatif tetap ditampilkan dengan peringatan agar konsisten dengan evaluasi.
- Inferensi memakai segmen terakhir sebelum/tepat pada waktu replay. Jika berjarak ≥5 menit dari pengamatan terakhir atau input tidak cukup kontinu, forecast diblokir. Timestamp sumber terakhir dan timestamp input terakhir ditampilkan terpisah.

## Artefak dan struktur

```text
app.py                      shell dashboard
pvforecast/data.py          ingestion, audit, segmentation, split, scaling, windows
pvforecast/model.py         LSTM, training, selection, calibration, artifact ZIP
pvforecast/statistics.py    metrics, conformal, energy
pvforecast/forecast.py      historical replay and exports
pvforecast/storage.py       immutable raw source and audit persistence
pvforecast/ui/              four presentation modules
configs/                    reproducible experiment template
tests/                      unit, integration and dashboard checks
skills/                     original product/research/design specifications
data/raw/                   immutable uploaded content, named by SHA-256
data/processed/             cleaned data, row-level audit and quality report per import
data/exports/               CLI exports
artifacts/                  versioned model packages
```

Setiap ZIP berisi checkpoint weights-only PyTorch, konfigurasi/metadata, scaler, kuantil calibration, riwayat pelatihan, metrik, prediksi test, dan manifest SHA-256. Loader memeriksa checksum serta kontrak input/output, versi scaler, dan versi calibration. Kalibrasi opsional: jika paket tidak memiliki calibration, model dapat digunakan dengan PI kosong dan peringatan. Jangan menggabungkan komponen dari eksperimen berbeda. Checksum mendeteksi kerusakan atau ketidakcocokan, bukan tanda tangan autentikasi.

Folder kerja `data/`, `artifacts/`, dependensi lokal, dan kredensial diabaikan Git. Paket dataset/model Data Master yang dipilih sebagai default deployment disertakan terpisah di `deployment/default/`. Dokumen audit menyimpan nama sumber, hash, kolom, zona waktu, keputusan pembersihan, serta jumlah baris. File raw tidak ditimpa; processed membuat folder baru setiap impor. Metrik aktual eksperimen tersedia di `docs/DATA_MASTER_RESULTS.md`.

## CLI dan reproduksi

Salin `configs/experiment.example.json` menjadi konfigurasi eksperimen sendiri. Sesuaikan pemetaan/zona waktu dan isi `boundaries` dengan tiga ISO timestamp ber-offset di dalam cakupan data. Nilai kosong pada template sengaja mencegah pembagian tanpa inspeksi.

```powershell
.\.venv\Scripts\python -m pvforecast audit --data data_anda.xlsx --config configs/experiment.json
.\.venv\Scripts\python -m pvforecast train --data data_anda.xlsx --config configs/experiment.json
.\.venv\Scripts\python -m pvforecast forecast --data data_anda.xlsx --config configs/experiment.json --model artifacts/NAMA_MODEL.zip --origin "TIMESTAMP_REPLAY_DENGAN_OFFSET"
.\.venv\Scripts\python -m pytest -q
```

Simpan konfigurasi aktual, paket model, audit, dan versi dependensi tiap eksperimen. Perangkat keras atau versi pustaka berbeda dapat mengubah hasil numerik walaupun seed tetap. Fixture sintetis dalam pengujian dipakai hanya untuk memeriksa fungsi; tidak digunakan sebagai bukti hasil riset PLTS.

## Eksperimen Data Master (seluruh sheet)

Untuk `Data Master.xlsx`, jalankan skrip khusus berikut dari root proyek (gunakan `PYTHONPATH=.deps` bila dependensi dipasang di `.deps`):

```powershell
python -m pvforecast.master_experiment --data "Data Master.xlsx"
```

Skrip menggabungkan seluruh sheet menurut timestamp `Updated Time`, memakai `Production Power(W)` dengan zona `Asia/Jakarta`, dan mengaudit baris invalid serta duplikat lintas sheet. Audit menyertakan `source_sheet` dan `source_excel_row`; nama bulan pada sheet tidak menentukan tanggal data. Sheet kosong dicatat, sedangkan sheet berisi data tanpa kolom wajib menghentikan eksperimen.

Pembagian khusus eksperimen ini telah ditetapkan menjadi 70/10/10/10 berdasarkan baris bersih yang terurut, dengan batas pada indeks `floor(7N/10)`, `floor(8N/10)`, dan `floor(9N/10)`. Semua window tetap berada dalam partisi dan segmen kontinu masing-masing. Kandidat memakai lookback 6/12/24, hidden 32, satu layer, dropout 0,1, learning rate 0,001, batch 32, maksimum 100 epoch, patience 10, dan seed 42. Kekurangan window menghentikan eksperimen tanpa mengubah pembagian.

Folder baru `data/experiments/master_<timestamp>/` menyimpan `experiment.json` (konfigurasi aktual, batas, jumlah window), `quality.json`, `clean.csv`, `metrics.csv`, `history.csv`, `test_predictions.csv`, `forecast.csv/json`, serta `summary.json` yang menunjuk paket model dan audit. Opsi `--output <folder-baru>` menetapkan folder hasil sendiri; folder yang sudah ada tidak ditimpa. Konfigurasi ini mendokumentasikan skrip seluruh-sheet dan berbeda dari konfigurasi CLI satu-sheet `pvforecast`.

Paket model disimpan di `artifacts/` dan dapat dimuat melalui **Model Validation → Model tersimpan lokal → Muat model lokal**. Dataset bersih hasil penggabungan dapat diunggah sebagai CSV di **Data Management**, dengan kolom `timestamp` dan `power_w`. Skrip memverifikasi kesamaan prediksi sebelum/sesudah pemuatan ulang, lalu mengekspor forecast pada pengamatan terakhir yang memiliki input kontinu cukup; waktu ini bisa lebih awal dari timestamp terakhir sumber.

## Batas rilis

Integrasi SOLARMAN, akuisisi otomatis, kontrol inverter, dan weather features berada di luar rilis pertama sesuai PRD. Dashboard Historical Replay menyediakan paket default portabel untuk deployment Streamlit Cloud. Dataset Data Master, batas partisi, konfigurasi terpilih, dan metrik eksperimen telah dicatat; interpretasi ilmiah dan kesesuaian konvensi integrasi dengan sumber tetap perlu penilaian peneliti. Lihat `docs/ACCEPTANCE.md` untuk pemetaan persyaratan dan status verifikasi.
