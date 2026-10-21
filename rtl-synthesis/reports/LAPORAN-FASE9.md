# LAPORAN FASE 9 — Klasifier triase `rtl/classifier.sv`

Plan: `rtlplan2/final38.md` baris 126 (tabel) dan bagian 12 baris 2124-2139 (blok Fase 9).
Gerbang verbatim tabel: **"`tb_klasifier` 0 dari 588 keputusan; ambang dibaca dari register,
bukan konstanta; D2 sudah diputuskan"**.
Semua perintah dijalankan dari `rtl-synthesis/` memakai rute repo (`./run_lint.sh`, `./run_sim.sh`,
`debroot`), bukan `~/eda`.

## 1. Hasil gerbang

| Gerbang Fase 9 | Status | Angka nyata |
|---|---|---|
| `tb_klasifier` 0 dari 588 keputusan (lengan mentah) | **LULUS** | `tb_klasifier: [raw] mismatches = 0 out of 588` |
| lengan berpenanda 602 jendela konsisten dengan manifes | **LULUS** | `[marked] mismatches = 0 out of 602`; sensus TP 95 FP 94 FN 0 TN 413, fired 189 (manifes: 95/94/0, 189) |
| ambang dibaca dari register, bukan konstanta | **LULUS** | tiga jalur bukti di bagian 4 |
| kode ambang register 10813 Q16 dan 10322 Q14 | **LULUS** | vektor 16/17 dari `04015.fase9.counts.hex`; keduanya sama dengan pembulatan 0,165 dan 0,63 ke format fitur |
| lint bersih | **LULUS** | `lint clean: top=classifier sources=2`; `lint clean: top=tb_klasifier sources=3` |
| deterministik (dua jalan identik) | **LULUS** | `cmp run1.out run2.out` bersih, sha256 keduanya sama |
| D2 sudah diputuskan | **LULUS** | kelas ikut `afib_lite_pkg::kelas_e` (0 belum diputuskan, 1 normal, 2 perlu tinjau), reset 0; run 0 menguji reset dan tahap mati |

Keluaran yang bisa diperiksa: `rtl/classifier.sv`, `rtl/tb/tb_klasifier.sv`,
`rtl/tb/vektor/fase9/**`, `rtl-synthesis/reports/fase9/**`.

## 2. Perintah persis dan keluaran mentah

### 2.1 lint

```
$ ./run_lint.sh ../rtl/classifier.sv classifier ../rtl/afib_lite_pkg.sv
run_lint.sh: top=classifier sources=2 timing=0
  ../rtl/afib_lite_pkg.sv
  ../rtl/classifier.sv
lint clean: top=classifier sources=2 (/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite/rtl-synthesis/debroot/usr/bin/verilator_bin)

$ ./run_lint.sh ../rtl/tb/tb_klasifier.sv tb_klasifier ../rtl/classifier.sv ../rtl/afib_lite_pkg.sv
run_lint.sh: top=tb_klasifier sources=3 timing=1
lint clean: top=tb_klasifier sources=3 (.../debroot/usr/bin/verilator_bin)
```

### 2.2 simulasi, jalur paritas (`run1.out`)

```
$ ./run_sim.sh ../rtl/tb/tb_klasifier.sv ../rtl/afib_lite_pkg.sv ../rtl/classifier.sv -- \
      +VECTOR=../rtl/tb/vektor/fase9
== tb_klasifier, Fase 9, record 04015, vectors ../rtl/tb/vektor/fase9 ==
INFO tb_klasifier: vector words above their width: 0
INFO tb_klasifier: counts vector marked 602 raw 588, afib 95 and normal 507
INFO tb_klasifier: raw afib 95 normal 493, single arm windows 602, mutasi fired 594
INFO tb_klasifier: parity ratio code 10813
INFO tb_klasifier: parity entropy code 10322
INFO tb_klasifier: marked arm 0xf, raw arm 0x7, single arm 0x2
OK   tb_klasifier: reset and disabled stage read undecided, no decision (D2)
INFO tb_klasifier: measured latency = 1 cycles, DUT parameter = 1
OK   tb_klasifier: latency and first decision of the marked arm
INFO tb_klasifier: marked arm fired 189, TP=95 FP=94 FN=0 TN=413
OK   tb_klasifier: marked arm census equals the Fase 5 manifest
tb_klasifier: [marked] words compared: 602
tb_klasifier: [marked] mismatches = 0 out of 602
tb_klasifier: [marked] window index mismatches = 0
tb_klasifier: [marked] m_dvalid missing = 0, extra decisions = 0
tb_klasifier: [marked] introspection tap mismatches = 0
tb_klasifier: [marked] confidence out of range = 0
OK   tb_klasifier: window counter cleared
INFO tb_klasifier: raw arm fired 183, TP=95 FP=88 FN=0 TN=405
OK   tb_klasifier: raw arm census equals the Fase 5 manifest
tb_klasifier: [raw] words compared: 588
tb_klasifier: [raw] mismatches = 0 out of 588
tb_klasifier: [raw] window index mismatches = 0
tb_klasifier: [raw] m_dvalid missing = 0, extra decisions = 0
tb_klasifier: [mutasi] thresholds 0 and 0, arm 0xf
tb_klasifier: [mutasi] words compared: 602
tb_klasifier: [mutasi] mismatches = 0 out of 602
tb_klasifier: [guard] entropy field 32768, arm 0x2
tb_klasifier: [guard] words compared: 602
tb_klasifier: [guard] mismatches = 0 out of 602
tb_klasifier: [tunggal] arm 0x2, entropy arm alone
tb_klasifier: [tunggal] words compared: 602
tb_klasifier: [tunggal] mismatches = 0 out of 602
INFO tb_klasifier: tunggal fired 191
INFO tb_klasifier: conf on both thresholds = 0
INFO tb_klasifier: conf far above both thresholds = 1000
tb_klasifier: [conf] outside range = 0, nonzero on the threshold = 0
tb_klasifier: [conf] not monotone = 0, not saturating = 0, fired on the threshold = 0
tb_klasifier: [conf] words compared: 5, missing decisions = 0
tb_klasifier: gate totals, marked 0 raw 0 mutasi 0 guard 0 tunggal 0 conf 0
tb_klasifier: PASS
$ echo $?   -> 0
```

### 2.3 jalur paritas dengan ambang disuntik lewat plusarg (`run3-plusarg.out`)

```
$ ./run_sim.sh ../rtl/tb/tb_klasifier.sv ../rtl/afib_lite_pkg.sv ../rtl/classifier.sv -- \
      +VECTOR=../rtl/tb/vektor/fase9 +RATIO_CODE=10813 +ENT_CODE=10322
INFO tb_klasifier: +RATIO_CODE, parity ratio threshold injected from the command line
INFO tb_klasifier: +ENT_CODE, parity entropy threshold injected from the command line
OK   tb_klasifier: marked arm census equals the Fase 5 manifest
tb_klasifier: [marked] mismatches = 0 out of 602
OK   tb_klasifier: raw arm census equals the Fase 5 manifest
tb_klasifier: [raw] mismatches = 0 out of 588
tb_klasifier: PASS
```

### 2.4 determinisme (`run1.out` vs `run2.out` vs `run5-konfirmasi-akhir.out`)

```
$ ./run_sim.sh ... -- +VECTOR=../rtl/tb/vektor/fase9 > reports/fase9/run2.out 2>&1
$ cmp reports/fase9/run1.out reports/fase9/run2.out   -> tidak ada keluaran, selisih 0 byte
$ ./run_sim.sh ... -- +VECTOR=../rtl/tb/vektor/fase9 > reports/fase9/run5-konfirmasi-akhir.out 2>&1
$ cmp reports/fase9/run1.out reports/fase9/run5-konfirmasi-akhir.out  -> tidak ada keluaran
$ sha256sum reports/fase9/run1.out reports/fase9/run2.out reports/fase9/run5-konfirmasi-akhir.out
80cecdf42d84649b6d6b173741cc9275db9412ff5ccc2c042919568453d9092d  reports/fase9/run1.out
80cecdf42d84649b6d6b173741cc9275db9412ff5ccc2c042919568453d9092d  reports/fase9/run2.out
80cecdf42d84649b6d6b173741cc9275db9412ff5ccc2c042919568453d9092d  reports/fase9/run5-konfirmasi-akhir.out
```

run5 dijalankan sesudah lint diulang pada berkas akhir, jadi gerbang di tabel bagian 1 berlaku
untuk sha256 `rtl/classifier.sv` yang tercatat di bagian 5, dan hasilnya bit-identik dengan dua
jalan sebelumnya.

## 3. Vektor dan bagaimana angkanya diperoleh

`rtl/tb/vektor/fase9/siapkan_vektor_fase9.py` (rc=0, `siapkan_vektor.out`) membaca **hanya**
data emas beku dan menulis 14 berkas hex + `04015.fase9.manifest.json`. Yang dikunci di sana:

1. `rtlplan2/fase5/04015.manifest.fase5.json` → `triage_gate`: predikat
   `ratio > 0.165 and entropy_over_4 > 0.63`, `ratio_register_q16 10813`,
   `entropy_register_q14 10322`, dan seluruh angka lengan. Skrip memastikan
   `rint(0.165*2^16) = 10813` dan `rint(0.63*2^14) = 10322`.
2. Kolom `ratio` dan `entropy4` dari berkas keputusan dibuktikan **sama persis** dengan
   `jendela_fitur[:, 1]`/`[:, 3]` fixture dan `jendela_fitur_berpenanda[:, 1]`/`[:, 3]` vektor;
   kolom `fired` sama dengan predikat float.
3. Kebenaran dasar per jendela: `jendela_kelas_benar` (588) dan `jendela_kelas_berpenanda` (602),
   plus pemeriksaan bahwa kolom `label_class` di `04015.windows.csv` sama baris demi baris.
4. Pengodean kata fitur: ratio Q1.16 (17 bit, maks 40070) dan entropi/4 Q1.14 (15 bit, maks
   14336), pembulatan half-to-even. **Jendela yang berpindah pihak antara pembanding float dan
   pembanding bilangan bulat = 0 pada kedua lengan, untuk aturan round maupun floor maupun
   truncate** — jadi perbandingan dua register itu mereproduksi predikat beku di seluruh 588 dan
   602 jendela.
5. Sensus kedua lengan dibandingkan dengan manifes dan lolos: berpenanda 602 (AFIB 95, N 507)
   fired 189 TP 95 FP 94 FN 0 TN 413; mentah 588 (AFIB 95, N 493) fired 183 TP 95 FP 88 FN 0
   TN 405.
6. Tiga lengan uji tambahan dihitung dari kolom fitur emas yang sama: mutasi t=(0,0) → fired 594,
   penjaga entropi 0x8000 satu lengan → fired 0, satu lengan entropi → fired 191.

## 4. Bukti "ambang dibaca dari register, bukan konstanta"

Tiga jalur, semuanya dengan angka nyata:

1. **Run 3 (sensitivitas register).** Fitur berlengan berpenanda yang sama, tetapi kedua register
   ditulis 0 dan 0: 602 keputusan dibandingkan dengan kolom yang dihitung ulang untuk titik itu →
   `[mutasi] mismatches = 0 out of 602`.
2. **Run 4 (penjaga medan entropi).** Hanya lengan entropi yang dinyalakan (`0x2`) dan medannya
   0x8000, sehingga bit 15 di luar jangkauan fitur 15 bit → seluruh 602 jendela harus normal →
   `[guard] mismatches = 0 out of 602`.
3. **Plusarg pada jalur paritas.** `+RATIO_CODE=10813 +ENT_CODE=10322` memberi hasil identik
   dengan membaca kode dari vektor (bagian 2.3), dan `+RATIO_CODE=0 +ENT_CODE=0`
   (`run4-kendali-negatif.out`) **gagal seketika**:
   `FATAL tb_klasifier: probe decision: class 2 want 1, win_idx 0 want 0, d_class 2`.
   Jadi kolom paritas memang terikat pada kode yang disuntik ke register.

Uji mutasi RTL mengukur gigi jalur 1 dan 2 (`reports/fase9/mutan/`):

| mutan | marked | raw | mutasi | guard | tunggal |
|---|---|---|---|---|---|
| `classifier_konstanta.sv` (ambang jadi konstanta 10813/10322) | 0/602 | **0/588** | **405/602 gagal** | **191/602 gagal** | 0/602 |
| `classifier_tanpa_penjaga.sv` (bit 15 diabaikan) | 0/602 | 0/588 | 0/602 | **594/602 gagal** | 0/602 |

Bacaan penting dan jujur: **lengan paritas sendirian tidak membuktikan register dibaca** — mutan
konstanta lulus 0/588 dan 0/602 pada kedua lengan itu karena kode yang disuntik kebetulan sama
dengan konstantanya. Yang memisahkan adalah run 3, run 4, dan plusarg: pada ketiganya mutan
konstanta gagal sementara RTL asli lulus 0 beda.

## 5. Ringkasan sha256

| berkas | sha256 |
|---|---|
| `model/rantai-afib-lite/rantai.py` (sebelum dan sesudah kerja) | `90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5` |
| `rtl/classifier.sv` | `7077f866cd51be7723b1f48e9559365c7ec909a94e4cafbb979f29bcb6eeec33` |
| `rtl/tb/tb_klasifier.sv` | `42a881a8db1707c812ca13d4cd4c8dcdbadb6102489b6586778ce63c8b6e7a4c` |
| `rtl/tb/vektor/fase9/siapkan_vektor_fase9.py` | `707edd1f8dbf8b4611dd4fc498410c1b2dce7b54c7394ec7f49d1fd085a4f523` |
| `rtl/tb/vektor/fase9/04015.fase9.counts.hex` | `d46121f85a54f89b06ce593b5775e72ba69cad5331295696fddf6aa90b736684` |
| `rtl/tb/vektor/fase9/04015.fase9.manifest.json` | `73dbf293f06deab06b0a75b85283190adaf2450a4543674efb1a1048331d7d29` |
| `rtl-synthesis/reports/fase9/run1.out` | `80cecdf42d84649b6d6b173741cc9275db9412ff5ccc2c042919568453d9092d` |
| `rtl-synthesis/reports/fase9/run2.out` | `80cecdf42d84649b6d6b173741cc9275db9412ff5ccc2c042919568453d9092d` (identik) |
| `rtl-synthesis/reports/fase9/run3-plusarg.out` | `fb6ad1af8dab6bd0b8e8d7019f12c0232ebd8a901c5ccb8ab50fbe15d93b5516` |
| `rtl-synthesis/reports/fase9/run4-kendali-negatif.out` | `5036f981c1baa25e5da532a5cc85b21e91b110e85934fca91ccf36669a9d6235` |
| `rtl-synthesis/reports/fase9/lint-classifier.out` | `6fb1228faae2d364fbb85290230c66e8786a139823ff95631f73a974819b5117` |
| `rtl-synthesis/reports/fase9/lint-tb-klasifier.out` | `d203fd9fcdfc32632c3a503b4e475ae4b3bedc9301f020a5db595f036edeb79d` |
| `rtl-synthesis/reports/fase9/mutan/classifier_konstanta.sv` | `1f40c86f86ff4be14bc98233f7e1a8b598701a03fac64ee86f963163c35a0f28` |
| `rtl-synthesis/reports/fase9/mutan/classifier_tanpa_penjaga.sv` | `a8e92497777014592c31bfbbbcf8503314142d3ba8a5f67e70e7995f5ba9409f` |

Seluruh 14 berkas vektor dan sha256-nya juga tercatat di
`rtl/tb/vektor/fase9/04015.fase9.manifest.json`.

## 6. Penyimpangan dan pekerjaan yang belum selesai (jujur)

1. **Satuan medan register vs kode paritas.** Baris tabel sinyal `i_ratio_thresh` (dan
   `i_entropy_thresh`) menyebut satuan 1/200 dan 1/100 dengan nilai reset 33 dan 63, sedangkan
   kode yang membuat paritas terhadap fixture adalah 10813 (Q1.16) dan 10322 (Q1.14). Berkas ini
   membandingkan medan 16 bit itu **langsung** dengan kata fitur, karena itu satu-satunya bacaan
   yang bebas satuan dan itu yang diminta angka acuan. Konsekuensi yang harus diputuskan pemilik:
   **nilai reset 33 dan 63, kalau dibaca sebagai kode fitur, berarti 0,0005 dan 0,0038**, jadi
   keluar dari reset tanpa menulis register lebih dulu, kedua lengan hampir selalu menyala. Itu
   risiko nyata untuk Fase 10 dan 11. Saya tidak mengubah paket (beku) atau `regs_axi.sv`
   (bukan milik saya) dan tidak memutuskan hal ini.
2. **Pengertian bit lengan b4.** Rencana memberi daftar nama bit, bukan tabel kombinasi. Berkas
   ini membacanya sebagai "AND atas lengan yang terdaftar, dan b4 memaksa kedua lengan terdaftar"
   sehingga nilai reset `5'h0F` memberi tepat gerbang P1 `ratio & entropy`. Bacaan ini konsisten
   dengan `rantai.py:848-878` dan dengan seluruh fixture, tetapi tidak berasal dari dokumen.
   b2 (aturan gelombang T) dan b3 (sumber deret berpenanda) **tidak** memengaruhi gerbang di
   berkas ini; keduanya milik tahap hulu (Fase 6 dan 7) dan itu dinyatakan eksplisit dengan
   pragma lint, bukan dihapus.
3. **`m_conf` tidak punya kolom emas.** Rencana hanya menetapkan arti (jarak ke ambang yang
   mengikat) dan skala 0-1000. Rumusnya (jarak minimum pada skala Q1.16 bersama, digeser
   `CONF_SHIFT = 4`, dijepit di 1000) adalah **pilihan berkas ini**, dan testbench hanya menguji
   sifatnya (rentang, 0 tepat di ambang, monoton, menjenuh) pada 5 kata stimulus. Tidak ada
   paritas angka untuk m_conf dan itu tidak diklaim.
4. **`m_rr_mark` pada langkah 4 blok Fase 9 tidak ada di porta beku.** Langkah itu menulis
   "tulis `m_rr_mark` sebagai salinan penanda deret", tetapi `rtl/classifier.sv` yang dibekukan
   Fase 1 tidak punya porta itu (baris tabel sinyal `m_rr_last`/`m_rr_mark` ada di grup `decide`
   dan disalurkan tahap deret RR, bukan tahap ini). Porta tidak boleh berubah, jadi langkah itu
   tidak dikerjakan di sini; pemiliknya Fase 6/Fase 11.
5. **Semantik penjaga bit 15** diwarisi dari placeholder Fase 1 (bit 15 medan 16 bit di luar
   jangkauan fitur 15 bit → lengan tidak pernah menyala). Dipertahankan, diuji, dan kini
   dibuktikan bergigi oleh mutan B. Bukan keputusan baru, tetapi juga bukan berasal dari dokumen
   rencana.
6. **Lint rantai belum bersih, bukan karena berkas ini.** `./run_lint.sh --chain` mengeluarkan 28
   peringatan: 24 dari `rtl/rr_series.sv` dan 4 dari `rtl/afib_lite_top.sv` (instance
   `peak_detect`). Tidak satu pun menunjuk `classifier.sv` atau `tb_klasifier.sv`; keduanya
   bersih pada lint berkas tunggal. Peringatan itu milik pekerjaan Fase 6 dan Fase 5/10 yang
   sedang berjalan dan **tidak** saya perbaiki.
7. **Cakupan paritas.** Klaim "0 dari 588" berlaku untuk **kata fitur yang diberikan** (Q1.16 dan
   Q1.14 hasil pembulatan dari kolom beku). Fase 8 (pengode fitur) berjalan paralel dan belum
   menyerahkan kata bulatnya, jadi paritas rantai penuh dari sampel ke keputusan baru ada di
   Fase 10. Yang sudah dibuktikan di sini: gerbang dua pembanding ini bit-identik dengan gerbang
   beku pada kedua lengan, untuk kedua lengan fitur itu.
8. **Dua berkas mutan** di `reports/fase9/mutan/` adalah artefak uji, bukan kode produk, dan
   sengaja tidak memenuhi lint.
