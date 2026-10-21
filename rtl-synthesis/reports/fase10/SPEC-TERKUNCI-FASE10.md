# SPEC TERKUNCI — FASE 10 (integrasi `afib_lite_top.sv`)

Satu sumber kebenaran untuk pekerja Fase 10. Disusun agen induk dari laporan final Fase 5, 6, 7, 9, 11
dan dari pembacaan langsung pohon repo (2026-10-21 ~00:30 WIB).

## 0. Keadaan awal yang sudah terbukti (jangan diulang, jangan dibongkar)

- `afib_lite_top.sv` **sudah meng-instansiasi kesebelas modul**: `acq_frontend` (351), `bandpass` (362),
  `derivative` (371), `square` (380), `integrator` (389), `peak_detect` (398), `t_rule` (410),
  `rr_series` (421), `features` (432), `classifier` (445), `regs_axi` (456). Jadi tugas Fase 10 adalah
  **penyambungan**, bukan pembuatan modul atau instansiasi baru.
- Gerbang yang sudah lulus per modul (semua diverifikasi agen induk, bukan klaim anak):

| Modul | Berkas | Gerbang |
|---|---|---|
| `peak_detect.sv` | 962 baris, 28 porta | puncak 4777/4777, `ambang_state` 9/9, qrs 2596/2596, lint 0 |
| `rr_series.sv` | 855 baris, 23 porta | interval 0/2595, langkah 0/2586, census `2186/397/9/3`, antrean 8 sesudah langkah 24 |
| `t_rule.sv` | 380 baris, 26 porta | `mismatches = 0 out of 26628`, silang = float 0 beda, latensi 30 |
| `classifier.sv` | 213 baris, 18 porta | mentah 0/588, berpenanda 0/602, TP 95 / FP 94 / FN 0 / TN 413, fired 189 |
| `regs_axi.sv` | 453 baris, 29 porta | 38 slot, 4056 kata 0 beda, 118 pemeriksaan, dua lengan cocok manifes |
| `features.sv` | (Fase 8, lihat laporannya) | — |

## 1. Gerbang Fase 10 (dari plan §Fase 10, ditambah yang wajib)

1. **`run_lint.sh --chain` HIJAU, nol peringatan.** Ini gerbang pertama, bukan kosmetik: 13 `PINMISSING`
   yang sekarang ada adalah tanda penyambungan belum selesai.
2. **Replay penuh 450.000 sampel**: larik tapis **0 beda dari sampel 0** sampai akhir (bukan hanya
   statistik agregat), dan seluruh keluaran hilir cocok dengan data emas.
3. **Dua mesin bit-identik**: Icarus (4-state) dan Verilator (2-state) menghasilkan checksum identik.
   Ini bukti determinisme termurah dan terkuat yang kita punya.
4. **Sintesis rute repo** (`run_synth.sh`, Yosys 0.33): laporkan angka FF/LUT/area nyata per modul.
   **Jangan pakai `~/eda/oss-cad-suite`** (yosys 0.70 macet di pass ABC) dan jangan membandingkan angka
   antar rute.
5. **Uji sambungan hulu-hilir** yang belum pernah ada: `peak_detect → rr_series → features → classifier`
   di dalam satu rantai nyata (Fase 6 sengaja digerakkan dari kolom emas tanpa meng-instansiasi
   `peak_detect.sv`, jadi kesetaraan bit-akurat belum pernah diuji pada rantai nyata).
6. **Kontrol negatif yang benar-benar gagal** (`$fatal`, `rc != 0`) untuk setiap berkas bukti utama.
   Kontrol yang lulus = kontrol kosong, bukan bukti.

## 2. Pekerjaan penyambungan (inti Fase 10)

### 2.1 Delta porta yang diketahui
- `peak_detect` (baris 398): 4 pin — `s_hp` (26 bit), `s_besaran` (24 bit), `d_dbg` (448 bit),
  `d_dbg_valid`.
- `t_rule` (baris 410): 9 pin — `i_peak_valid`, `i_delta`, `i_delta_valid`, `i_kem_qrs`,
  `i_kem_qrs_valid`, `o_peak_valid`, `o_peak_idx`, `o_dalam_pita`, `o_overrun`.

**Jangan bekerja dari daftar ini saja.** Jalankan `run_lint.sh --chain`, baca daftar `PINMISSING`
yang nyata (fitur dan klasifier juga bertambah porta selama Fase 8/9), lalu tutup **semuanya** sampai
hijau. Daftar di atas adalah titik awal, linter adalah sumber kebenarannya.

Sumber sinyal harus **nyata**: `s_hp` dan `s_besaran` berasal dari ring hp dan ring turunan yang
menurut plan hidup di jalur data. **Dilarang menyambung ke tie-off/sinyal kosong hanya supaya linter
diam** — itu hijau palsu dan justru merusak PoC.

### 2.2 Penyatuan satu sumber aturan gelombang T
`t_rule.sv` sekarang blok kanonik. `peak_detect.sv` masih memuat salinan aturan yang sama di baris
124-125, 216, 446 (`BATAS_PITA_SAMPEL 360`, `SETENGAH_JENDELA 18`, `N_PITA`, komentar bentuk silang).
Hapus salinan itu dan pakai `t_rule.sv` langsung, **tanpa mengubah `t_rule.sv` lagi**. Sesudah
penyatuan, kedua gerbang (Fase 5 dan Fase 7) harus dijalankan ulang dan tetap lulus — penyatuan yang
menurunkan angka = penyatuan yang salah.

### 2.3 Konvensi yang tidak boleh "diperbaiki" saat integrasi
- **`m_ev_idx` = indeks yang direkam model** (K2). Enam baris penelusuran balik memakai posisi yang
  lebih awal (`sp`), bukan `pos` puncak. Ini sengaja; jangan diseragamkan.
- **Satuan ambang mengikuti paket beku** (K7): 33 (1/200) dan 63 (1/100). Dokumen 36 menyebut
  10.813 Q16 / 10.322 Q14 untuk titik operasi yang sama — jangan ubah paket.
- **`kelas_e`**: 0 belum diputuskan, 1 normal, 2 perlu tinjau; reset 0 (keputusan D2 Fase 9).
- Bidang entri penampan kandidat **114 bit**, bukan 112 (K3) — `pk_f` mencapai 18.865.152 > 2²⁴.

### 2.4 Keterbatasan yang harus didokumentasikan, bukan ditutupi (K8)
Porta beku `regs_axi.sv` hanya membawa `i_status` dan `i_irq`, sehingga 12 slot RO membaca nilai
resetnya, `DEBUG_VAL` (0x94) membaca nol, `FIFO_OVF_COUNT` tetap nol, dan FIFO masukan kedalaman 64
belum ada. **Wajib ditulis di laporan akhir sebagai keterbatasan yang disengaja.**

> **MENUNGGU KEPUTUSAN AVIV — jangan dikerjakan tanpa izin eksplisit:** menyambungkan tujuh slot RO
> yang akan terlihat di demo (`BEAT_COUNT`, `RR_LAST`, `RR_MARK_LAST`, `SAMPLE_IDX`, `WINDOW_COUNT`,
> `CLASS_OUT`, `CONFIDENCE`) dari jalur data, supaya penggerak PS membaca angka hidup alih-alih nilai
> reset. Ini perubahan antarmuka; induk sudah menanyakannya ke Aviv.

## 3. Aturan kerja (dari pelajaran gelombang sebelumnya — ada karena pernah gagal)

- **Satu berkas = satu penulis.** Fase 10 hanya boleh menulis `rtl/afib_lite_top.sv` dan
  `rtl-synthesis/reports/fase10/**` + `LAPORAN-FASE10.md`. Bila modul fase lain perlu diubah, itu
  keputusan induk — laporkan, jangan langsung sunting.
- **Baca-saja, jangan disentuh:** `model/**` (beku), `rtl/afib_lite_pkg.sv` (beku), `rtlplan2/**`,
  `rtl/tb/vektor/fase5-verifikasi-aviv/**`, `rtl-synthesis/mcy/**` (milik sesi lain).
- **Tanpa `git add`/`commit`/`checkout`/`stash`.**
- **Jalankan tool, jangan `ls`.** "Berkas ada" bukan bukti; "tool mengeluarkan angka" bukti.
- **Log ber-timestamp terpisah** untuk setiap jalan; dua jalan penuh untuk klaim determinisme.
- **`$fatal` pada setiap jalur gagal** sehingga `rc != 0` benar-benar membedakan lulus dari gagal.
- **Jalan pendek harus mencetak `SKIP` eksplisit** untuk gerbang yang dilewatinya — jangan pernah
  melonggarkan gerbang secara diam-diam (ini persis kesalahan yang membuat kontrol negatif Fase 5
  kosong: larik yang dirusak justru yang dilewati jalan pendek).
- **Oracle wajib memakai `$isunknown`**: bila direktori vektor hilang atau pendek, `$readmemh`
  meninggalkan `X`, dan `X !== X` tidak terhitung beda → lulus palsu. Fase 6 sudah membuktikan ini.
- **Tulis laporan sambil jalan** ke `reports/fase10/PROGRES.md`; proses yang terpotong hanya
  menyisakan berkas.
- **Tanpa klaim lulus untuk gerbang yang merah.** Tulis status sebenarnya + penyebab + langkah
  berikutnya. Laporan yang jujur tentang gerbang merah jauh lebih berguna daripada laporan hijau palsu.

## 4. Perintah rujukan

```bash
cd rtl-synthesis
./run_lint.sh --chain                                  # gerbang 1
./run_sim.sh <tb> ../rtl/afib_lite_pkg.sv <modul...> -- +VECTOR=... +EXPECT=...   # Icarus
./run_synth.sh                                         # rute repo (Yosys 0.33)
cat ../rtl-synthesis/reports/KEPUTUSAN-INTEGRASI.md    # keputusan K1-K8 yang mengikat
```

Data emas: `rtlplan2/fase0/` (450.000 kata), `rtlplan2/fase5/04015.*.csv` +
`04015.manifest.fase5.json`. Vektor per fase sudah ada di `rtl/tb/vektor/fase{5,6,7,8,9,11}/`.
