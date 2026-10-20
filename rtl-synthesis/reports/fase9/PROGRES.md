# PROGRES Fase 9 — klasifier triase (`rtl/classifier.sv`)

Catatan bertahap selama pengerjaan. Bahasa Indonesia, istilah teknis Inggris. Semua perintah
dijalankan dari `rtl-synthesis/` dengan rute repo (`./run_lint.sh`, `./run_sim.sh`, debroot),
bukan `~/eda`.

## Langkah 0 — baca rencana dan kontrak

- `rtlplan2/final38.md:126` baris tabel Fase 9, blok lengkap di bagian 12 baris 2124-2139,
  keputusan D2/D2b/D7 di baris 2231, 2237, 2233 dan item ambang entropi di baris 2234.
- Kontrak: tabel sinyal 43 baris `rtl/afib_lite_pkg.sv` (grup `decide` baris 225-230, baris
  `i_ratio_thresh`/`i_entropy_thresh`/`i_arm_select` baris 242-244), `rtl/regs_axi.sv` (offset
  0x3C/0x40/0x44, nilai reset 33/63/5'h0F), `model/rantai-afib-lite/rantai.py:848-878`
  (`nilai_gerbang`: `p = (arr[:, 1] > t1) & (arr[:, 3] > t2)`).
- Data emas: `rtlplan2/fase5/04015.decisions.csv` (588), `...berpenanda.csv` (602),
  `04015.windows.csv` (602 x 210, kolom `label_class`), `04015.manifest.fase5.json`
  (`triage_gate`: predikat, 10813, 10322, dan seluruh angka lengan).
- Fixture dan vektor beku menyediakan kebenaran dasar per jendela: `jendela_fitur` +
  `jendela_kelas_benar` (588) dan `jendela_fitur_berpenanda` + `jendela_kelas_berpenanda` (602).

## Langkah 1 — vektor Fase 9 (`rtl/tb/vektor/fase9/`)

`rtl/tb/vektor/fase9/siapkan_vektor_fase9.py` membaca data emas dan menulis 14 berkas hex +
manifes. Penemuan yang dikunci di sana:

- Kode register dari manifes sama dengan pembulatan titik operasi ke format fitur:
  `rint(0.165 * 2^16) = 10813`, `rint(0.63 * 2^14) = 10322`.
- Pengodean kata fitur aman di batas: untuk aturan round, floor, dan truncate, jumlah jendela
  yang berpindah pihak = 0 pada kedua lengan, jadi perbandingan bilangan bulat mereproduksi
  predikat float beku di seluruh 588 dan 602 jendela.
- Sensus lengan berpenanda 602 (AFIB 95, N 507) fired 189 TP 95 FP 94 FN 0 TN 413 dan lengan
  mentah 588 (AFIB 95, N 493) fired 183 TP 95 FP 88 FN 0 TN 405 — sama dengan manifes.

Keluaran: `siapkan_vektor.out` (rc=0).

## Langkah 2 — badan `rtl/classifier.sv`

Dua pembanding terhadap dua register, kelas D2, keyakinan D2b, penjaga bit 15 medan entropi,
seleksi lengan `req = b0|b4` dan `b1|b4`. Porta dan parameter tidak diubah.

`./run_lint.sh ../rtl/classifier.sv classifier ../rtl/afib_lite_pkg.sv` → `lint clean`.
Empat peringatan Verilator (WIDTHEXPAND/WIDTHTRUNC/UNUSEDSIGNAL) diperbaiki dengan perluasan nol
eksplisit dan satu pragma `lint_off UNUSEDSIGNAL` yang berdokumentasi untuk `arm_q[3:2]`.

## Langkah 3 — `rtl/tb/tb_klasifier.sv`

Delapan bagian: reset/D2 (run 0), probe latensi terhadap `u_dut.LAT_CYCLES`, lengan berpenanda
(run 1), lengan mentah (run 2), sensitivitas register t=(0,0) (run 3), penjaga medan entropi
(run 4), satu lengan (run 5), properti keyakinan (run 6). Plusarg `+VECTOR`, `+RATIO_CODE`,
`+ENT_CODE` (jalur paritas), `+LIMIT`.

`./run_lint.sh ../rtl/tb/tb_klasifier.sv tb_klasifier ../rtl/classifier.sv ../rtl/afib_lite_pkg.sv`
→ `lint clean` (dengan `--timing`).

## Langkah 4 — simulasi

| berkas | perintah | hasil |
|---|---|---|
| `run1.out` | `./run_sim.sh ../rtl/tb/tb_klasifier.sv ../rtl/afib_lite_pkg.sv ../rtl/classifier.sv -- +VECTOR=../rtl/tb/vektor/fase9` | PASS, marked 0/602, raw 0/588 |
| `run2.out` | perintah yang sama, diulang | PASS, berkas bit-identik dengan run1 (`cmp` bersih) |
| `run3-plusarg.out` | perintah yang sama `+RATIO_CODE=10813 +ENT_CODE=10322` | PASS, marked 0/602, raw 0/588 |
| `run4-kendali-negatif.out` | perintah yang sama `+RATIO_CODE=0 +ENT_CODE=0` | GAGAL seperti diharapkan (probe langsung salah), membuktikan kolom paritas terikat pada kode yang disuntik |
| `run5-konfirmasi-akhir.out` | perintah paritas, diulang sesudah lint akhir | PASS, bit-identik dengan run1 (`cmp` bersih, sha256 sama) |

## Langkah 5 — uji mutasi RTL (bukti "ambang dari register")

Dua mutan disimpan di `reports/fase9/mutan/` dan dijalankan dengan testbench yang sama:

- `classifier_konstanta.sv` (ambang 10813/10322 sebagai konstanta): lengan paritas tetap 0
  beda — jadi lengan paritas sendirian **tidak** membuktikan register dibaca — sedangkan run 3
  gagal 405 dari 602 dan run 4 gagal 191 dari 602.
- `classifier_tanpa_penjaga.sv` (bit 15 medan entropi diabaikan): run 4 gagal 594 dari 602,
  sisanya lulus.

## Langkah 6 — lint rantai

`./run_lint.sh --chain` → 28 peringatan, seluruhnya dari `rr_series.sv` (24) dan `afib_lite_top.sv`
(4, instance `peak_detect`). Tidak ada satu pun dari `classifier.sv` atau `tb_klasifier.sv`;
kedua berkas Fase 9 bersih pada lint berkas tunggal.
