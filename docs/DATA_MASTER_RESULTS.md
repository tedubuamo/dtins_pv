# Hasil eksperimen Data Master — 15 November 2026

Model: `lstm-20261115T115218576744Z`, dilatih pada CPU menggunakan `Data Master.xlsx` dari workspace. Ini hasil eksperimen Historical Replay, bukan data live.

## Data dan pembagian

- SHA-256 sumber: `7476c6bc4122642c32afcf345efa08ba3c30c5527c4ba8bb00ad29b58ba9dec8`.
- Seluruh 30 sheet diperiksa berdasarkan timestamp aktual, bukan nama sheet. Desember 2025 hanya memiliki nilai daya kosong; Januari 2026 kosong.
- 52.592 baris sumber menjadi 51.226 baris bersih: 792 baris invalid, 572 duplikat identik, dan 2 baris duplikat konflik dikarantina/dihapus. Hitungan status ini eksklusif; jumlah issue di laporan kualitas dapat tumpang tindih.
- Cakupan bersih: 27 Agustus 2023 13:40 hingga 24 November 2025 14:30 WIB. Ada 11.780 segmen kontinu, terpanjang 154 baris. Tidak dilakukan interpolasi atau pengisian nol.

Pembagian berdasarkan baris bersih secara kronologis, tanpa shuffle. Batas merupakan awal partisi berikutnya (interval kanan terbuka).

| Partisi | Baris | Awal partisi | Window lookback 6 / 12 / 24 |
| --- | ---: | --- | --- |
| Train (70%) | 35.858 | 2023-08-27 13:40 WIB | 8.286 / 4.928 / 1.932 |
| Validation (10%) | 5.122 | 2025-02-05 14:05 WIB | 787 / 331 / 50 |
| Calibration (10%) | 5.123 | 2025-04-07 07:20 WIB | 382 / 160 / 42 |
| Test (10%) | 5.123 | 2025-07-18 17:20 WIB | 493 / 160 / 19 |

Input dan enam target tiap window berada seluruhnya di dalam satu partisi dan segmen 5 menit. Scaler hanya di-fit pada train.

## Seleksi model

Semua kandidat memakai hidden 32, satu layer, dropout 0,1, learning rate 0,001, batch 32, maksimum 100 epoch, patience 10, seed 42. Test tidak dipakai untuk seleksi atau kalibrasi.

| Lookback | Epoch terbaik | Epoch dijalankan | Validation MSE (skala normalisasi) |
| ---: | ---: | ---: | ---: |
| 6 | 61 | 71 | 0,01820320 |
| **12** | **96** | **100** | **0,01729911** |
| 24 | 6 | 16 | 0,02280157 |

Model terpilih memakai 12 pengamatan (60 menit riwayat) dan menghasilkan enam prediksi daya +5 sampai +30 menit. Kalibrasi memakai 160 window tersendiri dengan split conformal per horizon.

## Evaluasi independent test

Setiap horizon memakai 160 window test. Persistence dibandingkan pada origin dan target yang sama dengan LSTM terpilih.

| Horizon (menit) | MAE LSTM (W) | MAE persistence (W) | RMSE LSTM (W) | RMSE persistence (W) | R² LSTM | PICP | Lebar rata-rata PI (W) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 120,01 | 110,73 | 252,04 | 299,66 | 0,9165 | 94,375% | 825,68 |
| 10 | 165,65 | 163,36 | 296,51 | 357,09 | 0,8825 | 93,125% | 1.215,35 |
| 15 | 198,20 | 201,73 | 320,92 | 400,18 | 0,8624 | 93,125% | 1.323,94 |
| 20 | 236,51 | 235,24 | 356,55 | 432,08 | 0,8296 | 96,875% | 2.030,37 |
| 25 | 258,99 | 249,13 | 372,98 | 449,74 | 0,8133 | 100% | 2.643,87 |
| 30 | 281,44 | 260,47 | 387,33 | 437,48 | 0,7932 | 100% | 3.031,09 |

RMSE LSTM lebih rendah pada semua horizon; MAE lebih rendah hanya pada +15 menit. Coverage empiris pada +5/+10/+15 berada di bawah nominal 95%, sedangkan interval horizon panjang cukup lebar. Hasil ini tidak mendukung klaim keunggulan universal LSTM atau jaminan coverage 95%.

Window yang tersedia berbeda antar-lookback karena celah data; validation loss tiap kandidat menggunakan subset yang memenuhi lookback masing-masing. Test hanya mewakili segmen kontinu yang tersedia, dan window dapat saling overlap di dalam partisi. Tidak dilakukan uji signifikansi atau klaim generalisasi seluruh musim. Tidak ada tuning lanjutan berdasarkan hasil test ini.

## Artefak dan penggunaan

- Paket model: `artifacts/lstm-20261115T115218576744Z.zip`.
- Konfigurasi aktual, data bersih, kualitas, metrik, history, prediksi test, forecast, dan ringkasan: `data/experiments/data_master_70_10_10_10/`.
- Audit per baris dengan `source_sheet` dan `source_excel_row`: `data/processed/7476c6bc4122_2026-11-15T114659.317101_0000/`.
- Sumber asli tersalin tanpa perubahan ke `data/raw/`, dengan nama berdasarkan hash.

Paket memuat checkpoint, scaler, kuantil calibration, metadata, history, metrik, prediksi test, dan manifest checksum. Prediksi seluruh window test identik sebelum/sesudah pemuatan ulang paket. Satu forecast juga diverifikasi dan diekspor pada **10 November 2025 07:25 WIB**, yaitu origin terakhir dengan 12 input kontinu. Origin lebih awal daripada timestamp sumber terakhir karena segmen setelahnya terlalu pendek; bukan waktu saat ini. Estimasi energi 30 menit pada replay tersebut adalah 248,04 Wh. PI dipertahankan tanpa clipping.

Di dashboard, unggah `clean.csv` melalui Data Management (kolom `timestamp`, `power_w`, zona `Asia/Jakarta`), kemudian pilih paket melalui **Model Validation → Model tersimpan lokal → Muat model lokal**. Gunakan origin di atas untuk mengulang contoh forecast.

Untuk reproduksi, dari root proyek jalankan `python -m pvforecast.master_experiment --data "Data Master.xlsx"` dengan dependensi terpasang. Hasil masuk folder eksperimen baru; konfigurasi eksperimen ini ada di `experiment.json`. Versi pelatihan: Python 3.11.15, PyTorch 2.6.0+cu124 (CPU), NumPy 2.4.6, pandas 3.1.1.

Verifikasi otomatis: **25 passed** melalui `python -m pytest -q` dengan `.deps` di `PYTHONPATH`, termasuk tiga pengujian baru untuk workbook seluruh-sheet, penolakan kalibrasi terlalu pendek, serta pelatihan/ekspor end-to-end. Dataset fixture pengujian tetap sintetis; tabel evaluasi di atas berasal dari Data Master aktual.
