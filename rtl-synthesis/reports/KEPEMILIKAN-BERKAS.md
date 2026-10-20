# PETA KEPEMILIKAN BERKAS — pekerjaan paralel di repo ini

Dibuat oleh agen induk pada 2026-10-20 ~23:40 WIB. Tujuan: mencegah dua penulis pada
berkas yang sama. **Satu berkas = satu penulis.** Sebelum menulis, cek daftar ini.

## Penulis yang aktif sekarang

| Pekerja | Tugas | Berkas yang boleh ditulis | Status |
|---|---|---|---|
| `sa-0-0cfa909a` (deleg_9c55248f) | **Fase 10** — integrasi `afib_lite_top.sv` | `rtl/afib_lite_top.sv`, `rtl/tb/tb_top.sv` (baru), `rtl-synthesis/reports/fase10/**`, `rtl-synthesis/reports/LAPORAN-FASE10.md`; pada Tahap 5 boleh menyunting `rtl/peak_detect.sv` (penyatuan `t_rule`) lalu **wajib** menjalankan ulang gerbang Fase 5 + 7 | berjalan; spec: `reports/fase10/SPEC-TERKUNCI-FASE10.md`; 13 pin yang harus disambung sudah terverifikasi induk |
| `sa-0-41f6e8a9` (deleg_4482560c) | **Fase 5** — `peak_detect.sv` + `tb_puncak.sv` | `rtl/peak_detect.sv`, `rtl/tb/tb_puncak.sv`, `rtl/tb/vektor/fase5/**`, `rtl-synthesis/reports/fase5/**`, `rtl-synthesis/reports/LAPORAN-FASE5.md` | **SELESAI — LULUS** (verifikasi induk 2026-10-21 00:20): puncak 4777/4777, ambang_state 9/9, qrs 2596/2596, lint 0, empat jalan penuh identik, kontrol negatif sah `rc=1` (kontrol pertama kosong, ditemukan induk, diperbaiki) |
| `sa-0-bd0ea5bd` (deleg_e3566308) | **Fase 8** — `features.sv` + TB | `rtl/features.sv`, `rtl/tb/tb_fitur.sv` (nama sesuai plan), `rtl/tb/vektor/fase8/**`, `rtl-synthesis/reports/fase8/**`, `rtl-synthesis/reports/LAPORAN-FASE8.md` | **SELESAI — LULUS**: `mismatches = 0 out of 1190`, lengan berpenanda 602/602 bit-exact, lengan mentah 0 baris di atas 1 LSB, dua jalan penuh identik (sha256 `31e64f4b…`), **enam** kontrol negatif `rc=1` (termasuk jebakan `X !== X`). Menemukan + memperbaiki tiga bug RTL nyata di `features.sv` |
| `sa-1-4db73b6b` (deleg_e3566308) | **Fase 9** — `classifier.sv` + `tb_klasifier` | `rtl/classifier.sv`, `rtl/tb/tb_klasifier.sv`, `rtl/tb/vektor/fase9/**`, `rtl-synthesis/reports/fase9/**`, `rtl-synthesis/reports/LAPORAN-FASE9.md` | **SELESAI — LULUS**: mentah 0/588, berpenanda 0/602 (TP 95 / FP 94 / FN 0 / TN 413, fired 189), tiga jalan identik, dua mutan RTL membuktikan jalur ambang-register bergigi. **Mengangkat temuan satuan ambang → K7 direvisi**, dan itu risiko nyata untuk demo |
| `sa-0-46efc14f` (deleg_cb048085) | **Fase 6** — `rr_series.sv` + TB | `rtl/rr_series.sv`, `rtl/tb/tb_rr.sv`, `rtl/tb/vektor/fase6/**`, `rtl-synthesis/reports/fase6/**`, `rtl-synthesis/reports/LAPORAN-FASE6.md` | **SELESAI — LULUS** (verifikasi induk): interval 0/2595, langkah 0/2586, census tanda 2186/397/9/3 = emas, antrean 8 sesudah langkah 24, dua jalan penuh identik, dua kontrol negatif `rc=1`. Catatan: TB memakai rujukan hierarkis + satu blok waiver lint (tugas Fase 10) |
| `sa-1-d95120e9` (deleg_cb048085) | **Fase 7** — `t_rule.sv` + `tb_gelombang_t` | `rtl/t_rule.sv`, `rtl/tb/tb_gelombang_t.sv`, `rtl/tb/vektor/fase7/**`, `rtl-synthesis/reports/fase7/**`, `rtl-synthesis/reports/LAPORAN-FASE7.md` | **SELESAI — LULUS**: `mismatches = 0 out of 26628`, bentuk silang = rute float 0 beda, selisih 2048/16777216 terdokumentasi + terukur di RTL, dua jalan identik, kontrol negatif `rc=1`. Menambah 9 porta (K6) |
| `sa-2-aa48f005` (deleg_cb048085) | **Fase 11** — `regs_axi.sv` + penggerak PS | `rtl/regs_axi.sv`, `rtl/tb/tb_regs_axi.sv`, penggerak PS pada jalur plan, `rtl/tb/vektor/fase11/**`, `rtl-synthesis/reports/fase11/**`, `rtl-synthesis/reports/LAPORAN-FASE11.md` | **SELESAI — LULUS**: 38 slot, 4056 kata 0 beda, 118 pemeriksaan, dua lengan cocok manifes (588 vs 602), dua kontrol negatif `rc=1` (TB + penggerak). Lihat K7/K8 |
| sesi lain (bukan agen ini) | mutation coverage Fase 2 | `rtl-synthesis/mcy/**` | berjalan (4× `vvp`) |

## Tidak boleh disentuh siapa pun tanpa keputusan Aviv

- `model/**` — beku. `model/rantai-afib-lite/rantai.py` sha256
  `90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5`; `adapter.py`
  `f644493255ee1218d8ca49c37aae3858253a8ca2ddd0aa7371bc2fde24ccdba1`.
- `rtl/afib_lite_pkg.sv` — paket beku (Fase 1). Fase 5 memakai `localparam` di dalam modul
  agar tidak bergantung pada tambahan siapa pun.
- `rtl/afib_lite_top.sv` — integrasi; milik Fase 10.
- `rtl-synthesis/run_lint.sh`, `run_sim.sh`, `run_synth.sh` — peralatan bersama.
- `rtl/TASK_BRIEF.md`, `rtlplan/**`, `rtlplan2/**` — rujukan; baca-saja.
- Tidak ada `git add` / `commit` / `checkout` / `stash` tanpa persetujuan Aviv.

## Berkas bersama yang harus dibaca-saja oleh semua

- Data emas Fase 0: `rtlplan2/fase0/` (450.000 kata).
- Data rujukan Fase 5: `rtlplan2/fase5/04015.*.csv` + `04015.manifest.fase5.json`.
- Vektor milik Aviv: `rtl/tb/vektor/fase5-verifikasi-aviv/` (jangan diubah).
- Alat: rute repo `rtl-synthesis/debroot/` (Yosys 0.33, Icarus 12.0, Verilator 5.020).
  **Jangan** `~/eda/oss-cad-suite` — yosys 0.70 macet di pass ABC di mesin ini, dan angka
  sel/area antar rute tidak boleh dibandingkan.

## Catatan tabrakan yang sudah terjadi (jangan terulang)

Pada 22:32–23:21, `rtl/peak_detect.sv` ditulis dua pihak: pekerjaan sesi sebelumnya (yang
kemudian Aviv commit sebagai `93fedc6`) dan delegasi Fase 5 sekarang. Tidak ada yang hilang —
versi commit utuh di HEAD, versi 22:32 tersimpan di
`rtl-synthesis/reports/fase5/peak_detect.sv.sesi-lain-9c680d12.bak`. Pelajarannya: kunci
kepemilikan berkas **sebelum** meluncurkan pekerja, bukan sesudah.
