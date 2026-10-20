# Math Equation AFIB

Kumpulan turunan rumus untuk logika Pan-Tompkins yang dipakai di rancangan AFIB-LITE. Semua persamaan ditulis dalam LaTeX supaya bisa dirender Obsidian, dan semua angka di dalamnya dihitung pada rekaman AFDB `04015`, bukan dikutip.

Tujuh dokumen tersedia, dan urutannya mengikuti alur sinyal.

| Dokumen | Isi |
|---|---|
| [[00 - low-pass-filter-equation|low-pass-filter-equation]] | Persamaan (3) halaman 232, tapis low-pass rekursif, lengkap dengan tiga contoh soal, respons frekuensi, dan catatan fixed-point |
| [[01 - high-pass-filter-equation|high-pass-filter-equation]] | Persamaan (6) halaman 232, tapis high-pass rekursif, lengkap dengan dua tabel hitung tangan, penurunan fungsi alih, dan temuan tentang klaim cutoff 5 Hz |
| [[02 - five-point-derivative-equation|five-point-derivative-equation]] | Persamaan (9) halaman 233, turunan lima titik, penguatan DC nol eksak, puncak di $f_s/6$, tunda grup dua sampel, dan enam belas bagian penurunan |
| [[03 - squaring-and-moving-window-integrator-equation|squaring-and-moving-window-integrator-equation]] | Persamaan (10) dan (11) halaman 233, pengkuadratan dan integrasi jendela bergerak 150 milidetik, deret nol di kelipatan $f_s/N$, temuan bahwa pengkuadratan pada sinyal nyata hanya menambah 14,16 dB, dan keputusan yang dikunci 18 Oktober 2026 |
| [[04 - adaptive-threshold-equations|adaptive-threshold-equations]] | Persamaan (12) sampai (23) halaman 233 dan 234, dua pasang bobot, dua set ambang di dua domain, pemotongan separuh saat irama tidak teratur, dan bukti bebas pengali yang kelima-limanya benar |
| [[05 - rr-interval-averaging-equations|rr-interval-averaging-equations]] | Persamaan (24) sampai (29) halaman 234, dua rata-rata interval RR, tiga batas beserta uji aproksimasi pangkat dua, prosedur search back, penanda irama teratur, dan aturan penyemaian ulang P4-5 |
| [[06 - t-wave-discrimination|t-wave-discrimination]] | Halaman 234, aturan diskriminasi gelombang T, gerbang refraktori 200 milidetik dan jendela uji 360 milidetik sesudah QRS, uji kemiringan separuh dari keluaran turunan lima titik, kasus sebelum dan sesudah pada EKG buatan bergelombang T menonjol, dan batas keberlakuan 0,90 milivolt |
| [[hasil-rantai-end-to-end]] | Hasil langkah S8, yaitu notebook rantai end to end, tiga tingkat validasi, titik operasi terkunci, temuan langkah S7, dan batas yang belum tertutup |
| [[pan-tompkins-index]] | Peta induk, yaitu rumus mana di dokumen mana, dijalankan di notebook mana, dan angka apa yang terkunci untuknya, beserta anggaran latensi jalur dan daftar batas yang harus disebut apa adanya |

Notebook pendamping untuk ketujuh dokumen ada di repo `nabdha-afib-lite/model/math-equation-afib/`:

| Notebook | Sel | Kode | Gambar | Keluaran |
|---|---|---|---|---|
| `00 - low-pass-filter-equation.ipynb` | 29 | 15 | 4 | dijalankan utuh, bebas keluaran error |
| `01 - high-pass-filter-equation.ipynb` | 32 | 15 | 3 | dijalankan utuh, bebas keluaran error |
| `02 - five-point-derivative-equation.ipynb` | 26 | 12 | 2 | dijalankan utuh, bebas keluaran error |
| `03 - squaring-and-moving-window-integrator-equation.ipynb` | 32 | 20 | 7 | dijalankan utuh, bebas keluaran error |
| `04 - adaptive-threshold-equations.ipynb` | 31 | 17 | 5 | dijalankan utuh, bebas keluaran error |
| `05 - rr-interval-averaging-equations.ipynb` | 44 | 23 | 6 | dijalankan utuh, bebas keluaran error |
| `06 - t-wave-discrimination.ipynb` | 33 | 18 | 5 | dijalankan utuh, bebas keluaran error |
| `07 - end-to-end-chain.ipynb` | 20 | 10 | 7 | dijalankan utuh, nol keluaran error, nol sel kosong, `execution_count` 1 sampai 10 |

Setiap sel kode di ketujuh notebook dibuka komentar `# Tujuan:` dalam bahasa Indonesia, dan setiap `execution_count` berurutan 1 sampai N tanpa celah, tanpa duplikat, dan tanpa nilai kosong. Konvensi fixed-point yang dipakai ketujuhnya adalah yang terkunci di [[afib-lite/afib-rtl/34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown]], bagian 3.7, dengan anggaran latensi dan luas di bagian 3.8.

Notebook kedelapan, `07 - end-to-end-chain.ipynb`, adalah notebook rantai end to end fase 6 dan berbeda aturan bahasanya: seluruh isinya berbahasa Inggris, tanpa em dash dan tanpa en dash, karena berkas di dalam repo memakai bahasa Inggris. Notebook itu memanggil setiap gerbang beku, mencetak baris yang dicetak gerbangnya sendiri, lalu mencetak nilai hasil uraiannya di sel yang sama. Hasil lengkapnya ada di [[hasil-rantai-end-to-end]].
