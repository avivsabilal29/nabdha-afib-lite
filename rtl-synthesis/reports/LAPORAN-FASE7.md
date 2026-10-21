# LAPORAN FASE 7 — blok kanonik aturan gelombang T (rtl/t_rule.sv)

Pemilik berkas: `sa-1-d95120e9` (deleg_cb048085). Repo: `nabdha-afib-lite`.
Tanggal kerja: 2026-10-20/21 (WIB). Status gerbang: **LULUS** (bukti mentah di bawah,
`exit=0`, `PASS`).

Satu paragraf ringkas: `rtl/t_rule.sv` sekarang adalah blok kanonik mandiri untuk aturan
gelombang T (jendela 37 sampel, 4 besaran per kata diterima, satu blok state, satu domain
clock), diuji oleh `rtl/tb/tb_gelombang_t.sv` empat fase dalam satu jalan penuh 450.000 kata
turunan. Bentuk silang `2*kem < kem_qrs` di RTL sama persis dengan kolom emas rekaman
(`in_band`, `t_rejected`) dan dengan rute float yang dihitung testbench dari pasangan yang
sama: **0 beda pada seluruh 26.628 keputusan** (4.777 puncak nyata + 5.452 posisi sintetis +
16.396 baris grid + 3 puncak uji overrun). Selisih bentuk geser **2.048 dari 16.777.216**
tereproduksi di RTL pada grid yang mengandung SETIAP pasangan batas (uji gerbang menghitung
2.048 baris, sama dengan angka vektor) dan asalnya terdokumentasi.

---

## 1. Perintah persis dan keluaran MENTAH

### 1.1 Lint blok dan testbench (dua-duanya bersih)

```
$ cd rtl-synthesis
$ ./run_lint.sh ../rtl/t_rule.sv t_rule ../rtl/afib_lite_pkg.sv
run_lint.sh: top=t_rule sources=2 timing=0
  ../rtl/afib_lite_pkg.sv
  ../rtl/t_rule.sv
lint clean: top=t_rule sources=2 (.../verilator_bin)
exit=0
```
bukti: `reports/fase7/lint-t_rule-04.out`

```
$ ./run_lint.sh ../rtl/tb/tb_gelombang_t.sv tb_gelombang_t ../rtl/t_rule.sv ../rtl/afib_lite_pkg.sv
lint clean: top=tb_gelombang_t sources=3 (.../verilator_bin)
exit=0
```
bukti: `reports/fase7/lint-tb-gelombang-t-10.out`

### 1.2 Lint rantai (--chain): sebelum dan sesudah

```
$ ./run_lint.sh --chain
SEBELUM (rtl/t_rule.sv masih placeholder 104 baris):
  %Warning-PINMISSING: 4   (peak_detect u_peak_detect: s_hp, s_besaran, d_dbg, d_dbg_valid)
  %Warning-UNUSEDSIGNAL: 17
  %Warning-WIDTHEXPAND: 10
  %Warning-WIDTHTRUNC: 3
  %Error: Exiting due to 34 warning(s)        exit=1
SESUDAH (rtl/t_rule.sv diisi):
  %Warning-PINMISSING: 13  (4 lama di peak_detect + 9 port tambahan Fase 7 di t_rule)
  %Error: Exiting due to 13 warning(s)        exit=1
```
bukti mentah: `reports/fase7/lint-chain-sebelum.out`, `reports/fase7/lint-chain-sesudah.out`.

Bacaan jujur: lint rantai **sudah merah sebelum pekerjaan ini** (34 warning, 30 di antaranya
justru berasal dari placeholder `t_rule.sv`: 17 UNUSEDSIGNAL + 10 WIDTHEXPAND + 3 WIDTHTRUNC).
Setelah blok diisi, 30 warning itu hilang dan totalnya turun 34 -> 13. Sisa 13 semuanya
PINMISSING di **instansiasi**, bukan di badan modul: 4 milik Fase 5 (port tambahan
`peak_detect.sv` belum di-wire di `afib_lite_top.sv`, sudah ada sebelum saya) dan 9 milik
Fase 7 (port tambahan `t_rule.sv`). `rtl/afib_lite_top.sv` di luar kepemilikan saya, jadi
wiring-nya dicatat sebagai pekerjaan Fase 10 — lihat bagian 5.

### 1.3 Gerbang penuh, JALAN 1 (450.000 kata, semua 4.777 puncak)

```
$ ./run_sim.sh ../rtl/tb/tb_gelombang_t.sv ../rtl/afib_lite_pkg.sv ../rtl/t_rule.sv -- +VECTOR=../rtl/tb/vektor/fase7
tb_gelombang_t: vectors = ../rtl/tb/vektor/fase7
tb_gelombang_t: limit   = 450000 of 450000 frames
tb_gelombang_t: peaks   = 4777, sint words = 60000, stair rows = 16396
tb_gelombang_t: fixture minimum peak spacing = 30 samples
tb_gelombang_t: PH_REAL starts, 4777 of 4777 peaks expected to report
tb_gelombang_t: PH_SINT starts, 5452 sampled positions expected
tb_gelombang_t: PH_STAIR starts, 16396 rows expected
tb_gelombang_t: PH_OVR starts, 3 peaks expected to be served
tb_gelombang_t: PH_REAL words presented   = 450000
tb_gelombang_t: PH_REAL peak pulses       = 4777 of 4777
tb_gelombang_t: PH_REAL verdicts          = 4777 of 4777 expected
tb_gelombang_t: PH_REAL in band verdicts  = 2029
tb_gelombang_t: PH_REAL rejected verdicts = 1909
tb_gelombang_t: PH_REAL slopes with bit 22 set = 0
tb_gelombang_t: PH_REAL overlay mismatches = 0
tb_gelombang_t: PH_REAL kem mismatches    = 0
tb_gelombang_t: PH_REAL dalam_pita mismatches = 0
tb_gelombang_t: PH_REAL reject mismatches = 0
tb_gelombang_t: PH_REAL cross vs float route differences = 0
tb_gelombang_t: PH_REAL cross vs forbidden shift differences = 0
tb_gelombang_t: PH_REAL overflow pulses   = 0
tb_gelombang_t: PH_REAL overrun cycles    = 0
tb_gelombang_t: PH_SINT verdicts          = 5452 of 5452 expected
tb_gelombang_t: PH_SINT index mismatches  = 0
tb_gelombang_t: PH_SINT kem mismatches    = 0
tb_gelombang_t: PH_STAIR verdicts         = 16396 of 16396 expected
tb_gelombang_t: PH_STAIR index mismatches = 0
tb_gelombang_t: PH_STAIR kem mismatches   = 0
tb_gelombang_t: PH_STAIR dalam_pita mismatches = 0
tb_gelombang_t: PH_STAIR reject mismatches = 0
tb_gelombang_t: PH_STAIR cross vs float differences = 0 of 16396 rows
tb_gelombang_t: PH_STAIR cross vs forbidden shift differences = 2048, vector expects 2048
tb_gelombang_t: PH_STAIR grid rows cross vs float differences = 0, vector expects 0
tb_gelombang_t: PH_STAIR saturation flag mismatches = 0 (rail rows = 1)
tb_gelombang_t: PH_OVR verdicts           = 3 of 3 expected
tb_gelombang_t: PH_OVR index mismatches   = 0
tb_gelombang_t: PH_OVR kem mismatches     = 0
tb_gelombang_t: PH_OVR overrun before the tight pair = 0
tb_gelombang_t: PH_OVR overrun seen after = 41
tb_gelombang_t: measured latency = 30 accepted words, expected 30, bad = 0
tb_gelombang_t: words compared = 26628 (real 4777 + sint 5452 + stair 16396 + ovr 3)
tb_gelombang_t: mismatches = 0 out of 26628
tb_gelombang_t: PASS
exit=0
```
bukti: `reports/fase7/jalan1-20261021T002209.out`

### 1.4 JALAN 2 (identik) — determinisme

```
$ diff <(grep -v '^#' jalan1-*.out | grep -v '^20') <(grep -v '^#' jalan2-*.out | grep -v '^20')
IDENTICAL: no line differs between the two full runs
```
bukti: `reports/fase7/jalan1-20261021T002209.out` dan `reports/fase7/jalan2-20261021T002319.out`
(satu-satunya beda antar berkas adalah baris timestamp yang memang dicatat).

### 1.5 Kontrol negatif (satu nilai harapan dirusak di SALINAN, data emas tidak disentuh)

```
$ diff -rq rtl/tb/vektor/fase7 reports/fase7/negatif/vectors
Files .../04015.fase7.kem.hex and .../negatif/vectors/04015.fase7.kem.hex differ      (hanya satu)
$ python3 -c "... lines[99] = int(old,16)+1 ..."
NEG CONTROL: 04015.fase7.kem.hex line 100 0004C19A -> 0004C19B
$ ./run_sim.sh ../rtl/tb/tb_gelombang_t.sv ../rtl/afib_lite_pkg.sv ../rtl/t_rule.sv -- +VECTOR=reports/fase7/negatif/vectors
tb_gelombang_t: PH_REAL kem mismatches    = 1
tb_gelombang_t: PH_REAL dalam_pita mismatches = 0
tb_gelombang_t: PH_REAL reject mismatches = 0
tb_gelombang_t: PH_REAL cross vs float route differences = 0
tb_gelombang_t: PH_SINT kem mismatches    = 0
tb_gelombang_t: PH_STAIR kem mismatches   = 0
tb_gelombang_t: PH_STAIR cross vs float differences = 0 of 16396 rows
tb_gelombang_t: measured latency = 30 accepted words, expected 30, bad = 0
tb_gelombang_t: mismatches = 1 out of 26628
tb_gelombang_t: FAIL
FATAL: ../rtl/tb/tb_gelombang_t.sv:781: tb_gelombang_t: gate violation, see the counters above
exit=1
```
bukti: `reports/fase7/negatif/kontrol-negatif-20261021T002417.out`,
`reports/fase7/negatif/diff-vs-golden.txt`. Diff lengkap lawan jalan 1 membuktikan hanya satu
penghitung yang berubah (kem 0 -> 1) sementara semua klaim nol lain tetap nol: keputusan
`in_band`/`t_rejected` **tidak ikut berubah** karena kem yang rusak hanya satu baris.

### 1.6 Saksi oracle dan sebab 2.048

```
$ python3 rtl-synthesis/reports/fase7/cek_oracle_fase7.py
posisi diperiksa = 5453, beda = 0, contoh pertama = []
nilai terbesar kolom kem emas = 4194303, tertinggi yang dapat diwakili porta W_TW = 8388607
spike terbesar di kolom turunan = 4194303 = 2**22-1, jauh di bawah rail laporan
pasangan berbeda (silang vs geser) = 2048 dari 16777216
dengan kem_qrs ganjil = 2048, dengan kem_qrs genap = 0
lima contoh (kem_qrs, kem) = [(1, 0), (3, 1), (5, 2), (7, 3), (9, 4)], yaitu kem = (kem_qrs-1)/2 = floor(kem_qrs/2)
exit=0
```
bukti: `reports/fase7/cek-oracle-fase7.out` (skripnya `reports/fase7/cek_oracle_fase7.py`).

---

## 2. Tabel gerbang

Teks gerbang verbatim dari `rtlplan2/final38.md:124`:
> | 7 | Aturan gelombang T | blok gelombang T (nama berkas menyusul, lihat 3.4) | bentuk silang
> sama dengan rute float pada seluruh pasangan nyata, 0 beda; selisih 2.048 dari 16.777.216 pada
> grid didokumentasikan | 4 jam | pemilik RTL |

| Bagian gerbang | Status | Bukti mentah |
|---|---|---|
| Blok gelombang T ada, satu berkas, mandiri | LULUS | `rtl/t_rule.sv` 380 baris, `lint clean` top=t_rule |
| Testbench bernama dari plan 3.4/7.1 | LULUS | `rtl/tb/tb_gelombang_t.sv` 788 baris, `lint clean` |
| Bentuk silang sama dengan kolom emas `in_band` | LULUS | PH_REAL dalam_pita mismatches = 0 dari 4777; banding 2029 benar |
| Bentuk silang sama dengan kolom emas `t_rejected` | LULUS | PH_REAL reject mismatches = 0 dari 4777; banding 1909 benar |
| Bentuk silang sama dengan **rute float**, 0 beda, pasangan nyata | LULUS | PH_REAL cross vs float = 0; PH_STAIR grid rows cross vs float = 0 dari 16396 |
| Selisih 2.048 dari 16.777.216 didokumentasikan | LULUS | sebab diukur (`cek-oracle-fase7.out`: 2048, semua kem_qrs ganjil, kem = floor(kem_qrs/2)); identitasnya di `04015.grid.full.out`; RTL mereproduksi 2048 baris |
| Lint bersih (berkas Fase 7) | LULUS | `lint-t_rule-04.out`, `lint-tb-gelombang-t-10.out`, dua-duanya `exit=0` |
| Dua jalan penuh identik | LULUS | diff jalan1 vs jalan2 tanpa beda |
| Kontrol negatif membuktikan TB bisa GAGAL | LULUS | `kontrol-negatif-*.out`: mismatches 1, FAIL, `$fatal`, exit=1 |
| Satu domain clock, reset sinkron aktif rendah, tanpa latch, tanpa primitif vendor, tanpa indeks dari nilai data | LULUS | satu `always @(posedge clk_i)` + satu `always @(*)` untuk lane; lint -Wall bersih (LATCH/UNDRIVEN/SYNCASYNCNET tidak muncul); alamat tap dari penghitung `scan_q`, bukan dari data |
| Kemiringan dilaporkan walau aturan mati (rantai.py:648-670) | LULUS | baris tepi "rule disabled" tetap melaporkan m_tdata, dalam_pita = 0 |
| Kasus tepi | LULUS | delta 89 vs 90 vs 91, 2*kem = kem_qrs tepat, kem_qrs = 0, delta None, kem_qrs None, aturan mati, rail saturasi — semua 0 beda (bagian 6) |
| Latensi terdokumentasi dan terukur | LULUS | `19 + 10 + 1 = 30` kata diterima, terukur 30, `bad = 0` |

---

## 3. Apa yang dibangun (isi teknis)

`rtl/t_rule.sv`, satu blok state, tanpa primitif vendor:

* **Jendela 37 sampel** (`2*SETENGAH_JENDELA+1`, rantai.py:59) di-*scan* serial 4 besaran per
  kata diterima, bentuk yang direkomendasikan plan 4.10 ("A, serial scanner of 37 values").
  Karena 37 bukan pangkat dua, enam slot lane terakhir dimask ke nol, jadi maksimum tidak
  pernah melihat sampel di luar `[pos-18, pos+18]` walaupun register line terus terisi.
* **delta** langsung dari porta `i_delta` (satuan sampel), **tidak** direkonstruksi; `delta`
  None dipetakan ke `i_delta_valid = 0` (rantai.py:664).
* **`dalam_pita`** = `i_rule_enable & delta_valid & kem_qrs_valid & ((delta<<2) < 360)`,
  `delta<<2` sebagai aritmetika lurus (lantai), bukan potong-ke-arah-nol (rantai.py:338-339).
* **`ditolak_t`** = bentuk silang `2*kem < kem_qrs` pada lebar 26 bit (`{kem,1'b0}` lawan
  ekstensi nol `kem_qrs`), **bukan** `kem < (kem_qrs >> 1)` (rantai.py:340).
* **`kem` selalu diukur**, terlepas dari `i_rule_enable` (rantai.py:648-670).
* **Saturasi laporan**: `m_tdata` dijepit ke `2**W_TW-1` dan `m_overflow` sticky, sementara
  pembanding tetap memakai besaran penuh yang belum dijepit; model beku tidak punya rail ini,
  jadi satu baris tepi khusus menguji perbedaannya (bagian 6).
* **Latensi 30 kata diterima** = `PEAK_DEPTH 19 + SCAN_CYC 10 + LAT_CYCLES 1`; tahap keputusan
  (`vq_q`) yang membuat angka itu **tidak bergantung cadence**: laporan disajikan pada kata
  DITERIMA berikutnya, jadi pulsa selalu jatuh di beat yang diterima, baik caller memberi kata
  tiap siklus maupun tiap delapan siklus. `LAT_CYCLES` (parameter beku = 1) akhirnya terpakai
  secara struktural.
* **Jarak puncak minimum** = `SCAN_CYC = 10` kata diterima; pelanggaran tidak menghasilkan
  keputusan palsu, hanya `o_overrun` sticky + kandidat dibuang. Rekaman nyata minimum 30
  (testbench mencetaknya), grid 37.

## 4. Berkas yang ditulis

| Berkas | Isi |
|---|---|
| `rtl/t_rule.sv` | blok kanonik (badan diisi; nama/lebar/arah porta beku tidak berubah, 9 port tambahan di-append) |
| `rtl/tb/tb_gelombang_t.sv` | testbench gerbang 4 fase, tanpa satu pun angka hasil ukur yang diketik |
| `rtl/tb/vektor/fase7/siapkan_vektor_fase7.py` | reduksi vektor dari kolom Fase 0 beku + fixture Fase 5 beku |
| `rtl/tb/vektor/fase7/04015.{turunan,stair.*,sintetis.*,fase7.*}.hex` | 16 berkas vektor + `04015.grid.full.out` + `04015.fase7.manifest.json` |
| `rtl-synthesis/reports/LAPORAN-FASE7.md` | laporan ini |
| `rtl-synthesis/reports/fase7/**` | PROGRES.md, bukti lint/sim mentah, kontrol negatif, saksi oracle, harness debug |

`model/rantai-afib-lite/rantai.py` **tidak disentuh**: sha256 sesudah kerja
`90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5` (sama seperti sebelum).

## 5. Antarmuka yang DIKUNCI untuk Fase 10 + temuan logika kembar

### 5.1 Antarmuka beku yang tidak diubah
`clk_i, rst_ni, s_tdata[W_DER-1:0], s_tvalid, s_tlast, s_tuser[W_TUSER-1:0],
s_sample_idx[W_IDX-1:0], i_rule_enable, m_tdata[W_TW-1:0], m_tvalid, m_overflow, m_tlast,
m_tuser[W_TUSER-1:0], m_sample_idx[W_IDX-1:0], o_reject, d_valid, d_tw[W_TW-1:0]`.

### 5.2 Sembilan port tambahan (APPEND, tidak ada nama/lebar/arah beku yang berubah)
```
input  wire                  i_peak_valid;     // 1 pulsa pada kata DITERIMA milik kandidat puncak
input  wire [W_IDX-1:0]      i_delta;          // pos - i_qrs dalam SAMPEL (rantai.py:664)
input  wire                  i_delta_valid;    // 0 = delta None
input  wire [W_DER-1:0]      i_kem_qrs;        // kemiringan QRS tercatat terakhir
input  wire                  i_kem_qrs_valid;  // 0 = kem_qrs None
output wire                  o_peak_valid;     // 1 beat diterima: kualifikasi tiga di bawah
output wire [W_IDX-1:0]      o_peak_idx;       // indeks sampel puncak yang divonis
output wire                  o_dalam_pita;     // rantai.py:338-339
output wire                  o_overrun;        // sticky: kandidat datang saat serializer sibuk
```
`i_rule_enable` **ditangkap bersama kandidat** (masuk payload line 19 kata), sehingga vonis
memakai saklar sebagaimana saat puncak itu lewat — bukan saklar 30 kata kemudian.

### 5.3 Temuan logika kembar (untuk Fase 10, jangan diabaikan)
`rtl/peak_detect.sv` memuat salinan aturan yang sama di dalamnya, karena daftar portanya yang
beku tidak membawa kemiringan:
```
peak_detect.sv:124  localparam int unsigned BATAS_PITA_SAMPEL = 360;   // rantai.py:58 dan :68
peak_detect.sv:125  localparam int unsigned SETENGAH_JENDELA  = 18;    // rantai.py:59
peak_detect.sv:216  localparam logic [31:0] N_PITA = BATAS_PITA_SAMPEL;
peak_detect.sv:446  // 2 * kem < kem_qrs, exact cross form, never kem < (kem_qrs >> 1)
```
Artinya ada DUA sumber kebenaran untuk aturan yang sama. Penyatuan satu-sumber = pekerjaan
Fase 10, dan antarmuka di 5.2 sudah dikunci supaya penyatuan itu bisa dilakukan tanpa mengubah
`t_rule.sv` lagi: `peak_detect.sv` cukup menghubungkan sinyal puncak + delta + kem_qrs ke blok
ini (atau memakai blok ini secara langsung) lalu memakai `o_dalam_pita`/`o_reject`.
Konsekuensi lint yang harus ikut ditutup di Fase 10: `afib_lite_top.sv:410` (instansiasi
`t_rule u_t_rule`) belum menghubungkan 9 port tambahan, dan `afib_lite_top.sv:398`
(instansiasi `peak_detect`) masih kurang 4 port tambahan Fase 5 — total 13 PINMISSING adalah
satu-satunya sisa lint rantai.

## 6. Kasus tepi (semua lewat, 0 beda)

| Kasus | Nilai | Hasil RTL | Hasil benar |
|---|---|---|---|
| batas dalam_pita bawah | delta 89 | in band, `delta<<2 = 356 < 360` | tolak bila 2*kem < kem_qrs |
| batas dalam_pita tepat | delta 90 | `360 < 360` salah -> di luar pita | di luar pita |
| di atas batas | delta 91 | di luar pita | di luar pita |
| silang tepat sama | 2*kem = kem_qrs | tidak menolak (bentuk `<` ketat) | tidak menolak |
| silang tepat di bawah | 2*kem = kem_qrs - 1 | menolak | menolak |
| kem = 0, kem_qrs = 1 | — | menolak (0 < 0,5) | menolak |
| kem_qrs = 0 | — | tidak menolak | tidak menolak |
| delta None (belum ada QRS) | `i_delta_valid = 0` | kem diukur, dalam_pita 0 | 0 (rantai.py:338) |
| kem_qrs None | `i_kem_qrs_valid = 0` | kem diukur, dalam_pita 0 | 0 (rantai.py:338) |
| aturan mati | `i_rule_enable = 0` | kem **tetap** dilaporkan, dalam_pita 0 | rantai.py:648-670 |
| puncak 10 kata diterima | jarak tepat `SCAN_CYC` | dilayani, `o_overrun` tetap 0 | kontrak blok |
| puncak 9 kata diterima | jarak terlalu rapat | **dibuang**, `o_overrun` sticky, tidak ada vonis palsu | kontrak blok |
| slope 3.995.970 lawan 7.991.941 | 2*kem < kem_qrs | menolak | menolak |
| slope 3.995.970 lawan 7.991.940 | tepat batas | tidak menolak | tidak menolak |
| slope terbesar yang muat porta laporan | 8.388.607 lawan 16.777.215 | menolak di puncak atas | 2*kem = 2^24-2 < 2^24-1 |
| turunan paling negatif | -8.388.608 lawan 16.777.215 | kata laporan jenuh 8.388.607, `m_overflow` = 1, **tidak** menolak (2*kem = 2^24 di atas apa pun yang dapat dibawa porta 24 bit) | satu-satunya pasangan di mana kata laporan berbeda dari nilai yang dibandingkan |

## 7. Penyimpangan, kesalahan yang ditemukan, dan pekerjaan belum selesai (jujur)

1. **Kesalahan saya di agen vektor (sudah diperbaiki, terbukti).** Garis sintetis 60.000 kata
   dulu dimasukkan ke `M.GarisTunda(64)` — ring buffer 64 slot — sehingga setiap kueri posisi
   awal dijawab dengan ekor garis dan kolom kem emas salah untuk ~5.450 posisi
   ("max golden kem = 2091718" sebelum, "4194303" sesudah, lihat
   `siapkan_vektor_fase7-02.out` lawan `-05.out`). Kapasitas sekarang `SINT_WORDS` dan saksi
   independen `cek_oracle_fase7.py` menunjukkan 0 beda atas 5.453 posisi.
2. **Kesalahan saya di tabel kasus tepi (sudah diperbaiki, terbukti).** Baris rail dulu
   memakai `kem_qrs = 16777217`, yang **tidak muat** porta `W_DER = 24` dan terpotong menjadi 1
   di TB. Bukti mentah pengesanannya:
   `DBG stair reject row=16394 der=8388608 sp=16777217 delta=10 flg=31 dut_rej=0 dut_pita=1`.
   Diganti dua baris yang benar-benar dapat diwakili (8.388.607 lawan 16.777.215, dan
   -8.388.608 lawan 16.777.215). Ini juga menjelaskan satu-satunya `reject` yang gagal di
   laporan sementara sebelumnya.
3. **Dua bug RTL yang ditemukan oleh gerbang ini (sudah diperbaiki, terbukti).**
   (a) akumulator maksimum jendela mewarisi nilai puncak sebelumnya (`smag_q` tidak di-reset
   pada kata awal scan) — gejalanya kem tertinggal satu puncak; (b) laporan disajikan pada
   siklus drain sehingga latensi berbeda antar cadence — ditutup oleh tahap keputusan `vq_q`.
4. **Selisih 5451 lawan 5452 (sudah diselaraskan).** Manifest sempat menulis
   `sint_pos_usable = 5451` (batas konservatif `p + 47`), sementara kontrak blok butuh `p + 30`;
   rumus di agen vektor diselaraskan ke kontrak, semuanya 5452 dilaporkan.
5. **Belum selesai / di luar kepemilikan saya:** wiring 9 port tambahan di
   `rtl/afib_lite_top.sv:410` (Fase 10), plus 4 PINMISSING lama milik Fase 5 di
   `afib_lite_top.sv:398`. Karena itu lint rantai `--chain` masih `exit=1` walaupun 30 warning
   placeholder hilang dan `t_rule.sv`/TB sendiri bersih.
6. **Belum ada:** sintesis/implementasi blok ini (di luar gerbang Fase 7), integrasi
   `rtl/afib_lite_top.sv`, dan penyatuan satu-sumber dengan `peak_detect.sv`.

## 8. sha256 setiap berkas yang saya tulis (bukti)

```
d82daf1c8b78ab92182294ed1c0547a2241d856476b99ef4dfcd5fa2f6ae73e3  rtl/t_rule.sv
d731cc43e504d87569b4eab4ad8bf3a40e4c7fefce716f7b4f7d4c257a8e3d85  rtl/tb/tb_gelombang_t.sv
b460cdeb5638051b635726f44ebaea86a994c56c974b80e037970d74e9ebaf5e  rtl/tb/vektor/fase7/siapkan_vektor_fase7.py
ee43138f397b02ee40379b59c050d83dde307ac39333cb5e5bc4670921a66275  rtl/tb/vektor/fase7/04015.fase7.counts.hex
80ed6cdbd6e100b0403018b2476ec720782df1fd997bdfe4344cdf9e5e6d18f4  rtl/tb/vektor/fase7/04015.fase7.delta.hex
cf7390a14bc19cc0f905ade3b6b0b5d805c5597546221f0e817504f6ea862dd9  rtl/tb/vektor/fase7/04015.fase7.flag.hex
9d71b0110a40cd786c661460556315f0da480edf7ccb3281fdfd5db261080d99  rtl/tb/vektor/fase7/04015.fase7.kem.hex
c2461a00ef6bb621be10b999fd505b33fe5959d69236ba4e0cabee71c5aa1b4f  rtl/tb/vektor/fase7/04015.fase7.kemqrs.hex
ecdb8fe3a094e9bc086c72d0e481d98a5ae056990cc11f7442ef4f09363b182a  rtl/tb/vektor/fase7/04015.fase7.pos.hex
219d46864b18a633e0a9994194b22949fa5bf88a9bee1050c8acbfd0391a9200  rtl/tb/vektor/fase7/04015.sintetis.kem.hex
23b1367e64d71725a26850a76eac73611a26b0d9c3f90f07a04b2bb936cd0d79  rtl/tb/vektor/fase7/04015.sintetis.pos.hex
9305281ebc37ceef045e3eff12a84a6992fff9b2a1b4633d3f92f9c75be3f0e9  rtl/tb/vektor/fase7/04015.sintetis.turunan.hex
ff2fea6e0b671fd6482bb5f4ecfe08c87a383003feb86cc397950312dcd79ed7  rtl/tb/vektor/fase7/04015.stair.delta.hex
0676704b868c71455d61bd82ede5400361d177f814ee856c7be5dbb3dd019e5d  rtl/tb/vektor/fase7/04015.stair.der.hex
b03988873b801f987e17d585cd4e89c44708ee07ae18ac3a82f323a70cda5a18  rtl/tb/vektor/fase7/04015.stair.flag.hex
b1a706d9eed8b28d76d23b8812151eea958427f2f413fb19e5b5539ef0a08d64  rtl/tb/vektor/fase7/04015.stair.sp.hex
824fcddba95d4ccce8a484948ef392b242e724b4c30539247440a488d57e1710  rtl/tb/vektor/fase7/04015.turunan.hex
58a82da2f0d43e506efeb59781e7c89c07206740faa7916d13190068bf549d05  rtl/tb/vektor/fase7/04015.grid.full.out
04dc04a746b0a2a000ad9f6ba2dc55d105e3ad3957f5b673f120eb22d5b90c55  rtl/tb/vektor/fase7/04015.fase7.manifest.json
8170a83a1ccd1624924e35994b03c6d6e4929b26cf1ed44cd7938a015c406cec  rtl-synthesis/reports/fase7/cek_oracle_fase7.py
9890870e4f6dbe605b2e34077dab2b6d87a50d6ca06a619dadbd5034654d27e2  rtl-synthesis/reports/fase7/cek-oracle-fase7.out
782ef84c98e55e2c6aec338f6c9bfc30efc0c7f197744cf23688d87f6a0db5da  rtl-synthesis/reports/fase7/lint-t_rule-04.out
d1346b2f8b2d6442cd777b0b428f73195cfac302387c2557be2bc59a72c4c861  rtl-synthesis/reports/fase7/lint-tb-gelombang-t-10.out
17c1e859c5141ff73a9b362fef720dcb0483764f845a67004e39f926a355f46f  rtl-synthesis/reports/fase7/lint-chain-sebelum.out
b36177c50661037b62dfa0a180179e5c297e2f89f501141620d81c1ee5faa324  rtl-synthesis/reports/fase7/lint-chain-sesudah.out
2a8755e79390ec3c422e422a945c9d7a925d07f2850d397ebc8f4d3cc212ad6d  rtl-synthesis/reports/fase7/jalan1-20261021T002209.out
4b0354dd7b7714203fafcdc78ed379d3b18d007623c76d8d7d13e3a609543824  rtl-synthesis/reports/fase7/jalan2-20261021T002319.out
6c1e31375edfa5241906adc7267d406f6fe1d40cb35eb876d50ca5ce5b353a19  rtl-synthesis/reports/fase7/negatif/diff-vs-golden.txt
0c78735a63dc9525bee714965a24a7c89fcfa7894ce75d016ae1b4799a90dd44  rtl-synthesis/reports/fase7/negatif/kontrol-negatif-20261021T002417.out
```

Catatan kepemilikan: mtime `rtl/peak_detect.sv`, `rtl/tb/tb_puncak.sv`, `rtl/rr_series.sv`,
`rtl/features.sv`, `rtl/classifier.sv` yang berdekatan dengan jam kerja ini berasal dari
pekerja paralel lain, bukan dari saya; tidak satu pun dari berkas itu ada dalam daftar tulis
saya, dan `model/rantai-afib-lite/rantai.py` masih ber-sha256
`90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5`.
