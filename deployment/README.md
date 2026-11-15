# Dataset dan model default untuk deployment

Folder `default/` berisi hasil Data Master yang diperlukan saat dashboard pertama dibuka. Berkas ini sengaja disertakan dalam Git agar tersedia di Streamlit Cloud, terpisah dari folder kerja lokal `data/` dan `artifacts/` yang diabaikan Git.

- `model.zip`: paket model `lstm-20261115T115218576744Z`, scaler, calibration, dan hasil evaluasi.
- `clean.csv`: 51.226 pengamatan bersih dengan timestamp berzona.
- `audit.csv`: audit 52.592 baris sumber, termasuk sheet dan nomor baris Excel.
- `quality.json`: sumber, hash, laporan kualitas, dan konfigurasi eksperimen.
- `experiment.json`: konfigurasi aktual pembagian 70/10/10/10.
- `summary.json`: referensi model dan audit dengan path relatif terhadap root repository.

Konfigurasi `configs/dashboard.json` menunjuk `deployment/default`. Startup memeriksa manifest paket model, hash dataset, dan kesesuaian hash sumber sebelum memuat pasangan dataset/model. Data menggunakan jam WIB di tampilan; timestamp internal tetap berzona. Tidak ada pelatihan ulang saat startup.

Sertakan folder `deployment/`, `configs/dashboard.json`, dan perubahan kode startup saat commit/push ke branch yang digunakan Streamlit Cloud. Entry point tetap `app.py`. Deployment tidak memerlukan workbook Excel asli atau folder hasil eksperimen lokal. Setelah versi baru terpasang, refresh aplikasi untuk membuat sesi baru; jika sesi lama masih tampil, reboot aplikasi dari pengelolaan Streamlit.

Untuk mengganti model default di kemudian hari, ganti paket model beserta dataset/audit/laporan yang cocok dan perbarui `summary.json` sebagai satu pasangan. Lihat `docs/DATA_MASTER_RESULTS.md` untuk metrik dan batas interpretasinya.
