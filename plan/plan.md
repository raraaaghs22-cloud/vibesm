# Import Project "rara" dari GitHub

Mengimpor project dari repository private `raraaaghs22-cloud/rara` (branch `main`), memasang semua dependencies, lalu memastikan aplikasinya berjalan dan bisa dibuka di preview.
Fitur aplikasi tetap sama. Perubahan hanya dibuat sebatas yang diperlukan agar project berjalan di environment ini.

## Untuk siapa
Pemilik repository yang ingin project-nya bisa dijalankan dan dicoba di preview Emergent tanpa perlu setup manual.

## Fitur inti dan pengalaman
- Kode dari branch `main` diambil dengan GitHub Personal Access Token yang Anda berikan.
- Semua dependencies backend dan frontend dipasang.
- Jika struktur project berbeda dari environment ini (frontend React di port 3000, backend FastAPI di port 8001 dengan prefix `/api`, database MongoDB), konfigurasi disesuaikan supaya cocok: path, port, alamat API, dan koneksi database. Logika dan tampilan fitur tidak diubah.
- Nilai konfigurasi yang dibutuhkan project (misalnya API key pihak ketiga) didata. Jika ada yang belum tersedia, Anda akan dimintai nilainya.
- Aplikasi dicek sampai halaman utamanya terbuka di preview dan backend merespons.

## Alur pengguna
1. Anda memberikan GitHub Personal Access Token.
2. Project diimpor, dependencies dipasang, dan konfigurasi disesuaikan.
3. Jika ada key atau kredensial yang belum ada, Anda akan dimintai nilainya.
4. Anda membuka preview dan mencoba aplikasinya.

## UI/UX
Tampilan asli project dipertahankan. Desain tidak diubah.

## Tahapan implementasi
- **Fase 1 (MVP, dikerjakan sekarang):** Import repository, pasang dependencies, sesuaikan konfigurasi, lalu pastikan aplikasi berjalan di preview.
- **Fase 2:** Memperbaiki bug atau error yang ditemukan saat aplikasi dicoba.
- **Fase 3:** Menambah atau mengembangkan fitur sesuai permintaan Anda.

## Asumsi
- Yang diimpor adalah branch `main` saja. Isinya menggantikan template kosong yang ada sekarang.
- Token hanya dipakai untuk mengambil kode. Token tidak disimpan di dalam kode project.
- Jika project tidak memakai React, FastAPI, atau MongoDB, bagian tersebut disesuaikan seminimal mungkin agar bisa berjalan. Fitur tidak ditulis ulang.
- Tidak ada push balik ke GitHub kecuali Anda memintanya.
- Fitur yang bergantung pada layanan pihak ketiga baru bisa berfungsi setelah key-nya tersedia. Sampai saat itu, fitur tersebut ditandai belum aktif.
