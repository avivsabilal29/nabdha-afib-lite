# PROGRES FASE 7 — t_rule.sv (aturan gelombang T)

Pemilik: `sa-1-d95120e9` (deleg_cb048085). Repo:
`/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite`.

Catatan: berkas ini append-only. Setiap langkah dicatat dengan perintah persis dan
keluaran mentah yang relevan.

## Linimasa

- [T0] Baca `rtlplan2/final38.md` baris 110-130, bagian 3.4 (baris 341-352), 4.10 (baris
  566-587), 5.4 (baris 710-723), 7.1 (baris 899-920), Fase 7 (baris 2086-2101). Baca
  `rtl/t_rule.sv` (104 baris, masih PLACEHOLDER), `rtl/tb/tb_integrator.sv` dan
  `rtl/tb/tb_puncak.sv` sebagai konvensi testbench, `rtl-synthesis/run_lint.sh` dan
  `run_sim.sh`, `rtl-synthesis/reports/KEPEMILIKAN-BERKAS.md`.
- [T0] sha256 `model/rantai-afib-lite/rantai.py` SEBELUM kerja =
  `90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5` (sama dengan nilai beku
  di KEPEMILIKAN-BERKAS.md). Model tidak disentuh, hanya diimpor baca-saja.
- [T0] Temuan angka `2.048 dari 16.777.216` DITEMUKAN, bukan dikarang:
  `model/rantai-afib-lite/uji_00_teorema.py:83` `KISI_T = 4096` dan `:767-777` (kisi
  `4096 x 4096 = 16.777.216` pasangan), hasilnya di
  `model/math-equation-afib/math-equation-explanation/06 - t-wave-discrimination.md:210-227`
  ("Uji kedua memakai kisi seluruh pasangan bilangan bulat dari 0 sampai 4.095 pada kedua
  sisi, yaitu 16.777.216 pasangan" ... "Yang menyimpang hanya bentuk geser ke bawah, tepat
  pada 2.048 pasangan, yaitu seluruh pasangan dengan s_prev ganjil dan 2 s = s_prev - 1").
  Fraksi 2048/16777216 = 1/8192 = 0,00012207, sama dengan kolom "Fraksi kisi" di tabel itu.
- [T0] Lint rantai BASAH sebelum perubahan apa pun: `./run_lint.sh --chain` sudah
  memunculkan **4 warning PINMISSING** dari `afib_lite_top.sv:398` (porta aditif
  `s_hp`, `s_besaran`, `d_dbg`, `d_dbg_valid` milik Fase 5 yang belum dirangkai di top),
  berakhir `%Error: Exiting due to 4 warning(s)`. Jadi "lint rantai bersih" bukan keadaan
  awal repo ini; gerbang lint saya adalah lint bersih berkas saya + bukti bahwa porta aditif
  yang saya tambah adalah satu-satunya sebab tambahan, plus lint bersih pada top salinan
  yang merangkai seluruh porta aditif. Semua mentahnya ada di direktori ini.
# PROGRES FASE 7 -- t_rule.sv (aturan gelombang T)

Pemilik: sa-1-d95120e9 (deleg_cb048085). Berkas ini append-only.

## 2026-10-21 catatan kerja (ringkas, bukti mentah di rtl-synthesis/reports/fase7/)

- Vektor Fase 7 diturunkan dari kolom Fase 0 BEKU + fixture Fase 5 BEKU oleh
  rtl/tb/vektor/fase7/siapkan_vektor_fase7.py (bukan simulasi model baru).
- rtl/t_rule.sv ditulis ulang menjadi blok kanonik mandiri; porta beku tidak berubah,
  antarmuka tambahan Fase 7 di-append ke daftar porta.
- rtl/tb/tb_gelombang_t.sv: empat fase (rekaman nyata 4777 puncak, garis sintetis 5453
  posisi, grid pasangan 16382 + 14 baris kasus tepi, penguji overrun).
- Lint bersih untuk t_rule.sv dan tb_gelombang_t.sv (bukti lint-*.out).
- Dua bug ditemukan lewat gerbang ini dan diperbaiki:
  (a) akumulator maksimum jendela mewarisi nilai puncak sebelumnya (smag_q tidak
      di-reset pada kata awal scan);
  (b) agen vektor memakai GarisTunda(64) untuk garis sintetis 60000 sampel, sehingga
      ring buffer mengembalikan ekor garis untuk setiap posisi awal.
- Kasus tepi yang ditambahkan setelah temuan: kem_qrs di luar lebar W_DER (tidak dapat
  diwakili porta 24 bit) diganti dua baris yang dapat diwakili: 8388607 lawan 16777215
  (tolak di puncak atas) dan -8388608 (saturasi kata laporan, 2*kem = 2**24 di atas
  kem_qrs maksimum porta).

## 2026-10-21 status gerbang: LULUS

- Jalan 1 `reports/fase7/jalan1-20261021T002209.out` dan jalan 2
  `reports/fase7/jalan2-20261021T002319.out`: `mismatches = 0 out of 26628`, `PASS`, `exit=0`,
  dan kedua berkas identik baris demi baris (di luar timestamp yang memang dicatat).
- Kontrol negatif `reports/fase7/negatif/kontrol-negatif-20261021T002417.out`: satu nilai
  emas dirusak di SALINAN (kem baris 100 +1) -> `mismatches = 1`, `FAIL`, `$fatal`, `exit=1`;
  semua klaim nol lain (in_band, t_rejected, rute float, grid, latensi) tetap nol.
- Lint: `t_rule` bersih, `tb_gelombang_t` bersih; lint rantai turun dari 34 warning (30 di
  antaranya dari placeholder t_rule.sv) menjadi 13, sisa 13 semuanya PINMISSING instansiasi di
  `afib_lite_top.sv` (9 port tambahan Fase 7 + 4 port tambahan Fase 5) -> pekerjaan Fase 10.
- Laporan lengkap: `rtl-synthesis/reports/LAPORAN-FASE7.md`.
- sha256 `model/rantai-afib-lite/rantai.py` sesudah kerja:
  `90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5` (tidak berubah).
