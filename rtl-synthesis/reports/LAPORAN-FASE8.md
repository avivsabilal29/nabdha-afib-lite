# LAPORAN FASE 8 -- lapisan fitur jendela 32 interval (`rtl/features.sv`)

Rekaman lengkap langkah demi langkah ada di `rtl-synthesis/reports/fase8/PROGRES.md`. Dokumen ini
hanya berisi perintah, keluaran mentah, tabel gerbang, dan batasan yang belum diuji.

## 1. Berkas milik fase ini

| berkas | keterangan |
|---|---|
| `rtl/features.sv` | lapisan fitur: jendela 32 interval, langkah 4 beat, empat tap + peristiwa jendela |
| `rtl/tb/tb_fitur.sv` | testbench gerbang fase 8, dua lengan x dua jalan dalam satu simulasi |
| `rtl/tb/vektor/fase8/ekspor_vektor_fase8.py` | eksportir vektor emas dari `rtlplan2/fase5/` |
| `rtl/tb/vektor/fase8/04015.fase8.*` | 10 berkas vektor emas (semua 32 bit satu kata per baris) |
| `rtl-synthesis/reports/fase8/` | log simulasi mentah, `PROGRES.md`, dan dokumen ini |

Porta dan parameter `features` tidak diubah. Tidak ada berkas pekerja lain yang disentuh
(`peak_detect.sv`, `rr_series.sv`, `t_rule.sv`, `classifier.sv`, `regs_axi.sv`, `afib_lite_top.sv`,
`model/**`, `run_lint.sh`, `run_sim.sh`).

## 2. Perintah persis

```sh
# vektor emas, dari akar repo
python3 rtl/tb/vektor/fase8/ekspor_vektor_fase8.py

# lint
cd rtl-synthesis
./run_lint.sh ../rtl/features.sv features ../rtl/afib_lite_pkg.sv
./run_lint.sh ../rtl/tb/tb_fitur.sv tb_fitur ../rtl/afib_lite_pkg.sv ../rtl/features.sv

# jalan pendek (biaya simulasi Icarus, selalu duluan)
./run_sim.sh ../rtl/tb/tb_fitur.sv ../rtl/afib_lite_pkg.sv ../rtl/features.sv \
    -- +VECTOR=../rtl/tb/vektor/fase8 +LIMIT=60

# jalan penuh, dua kali, log ber-timestamp
./run_sim.sh ../rtl/tb/tb_fitur.sv ../rtl/afib_lite_pkg.sv ../rtl/features.sv \
    -- +VECTOR=../rtl/tb/vektor/fase8 > reports/fase8/jalan-penuh-1-20261021-004418.log 2>&1
./run_sim.sh ../rtl/tb/tb_fitur.sv ../rtl/afib_lite_pkg.sv ../rtl/features.sv \
    -- +VECTOR=../rtl/tb/vektor/fase8 > reports/fase8/jalan-penuh-2-20261021-004418.log 2>&1
cmp reports/fase8/jalan-penuh-1-20261021-004418.log \
    reports/fase8/jalan-penuh-2-20261021-004418.log
sha256sum reports/fase8/jalan-penuh-*.log
```

## 3. Keluaran gerbang mentah

Vektor, dari `ekspor_vektor_fase8.py` (perintah terakhir, setelah format vektor diubah ke satu
kata 32 bit per baris):

```
intervals raw/marked      : 2595 2583
emissions raw/marked      : 624 638
golden rows raw/marked    : 588 602
rejections raw/marked     : 17 0
marked  d/bin/cnt/pnn dif : 0 0 0 0
marked  code differ       : {'rmssd': 0, 'ratio': 0, 'ent': 0, 'mean_q': 0}
marked  code over 1 LSB   : {'rmssd': 0, 'ratio': 0, 'ent': 0, 'mean_q': 0}
marked  code worst LSB    : {'rmssd': 0, 'ratio': 0, 'ent': 0, 'mean_q': 0}
raw     over 1 LSB / worst: 0 {'rmssd': 1, 'ratio': 0, 'ent': 0, 'pnn50': 0}
```

Lint:

```
lint clean: top=features sources=2 (/home/avivsabilalm/.../verilator_bin)
lint clean: top=tb_fitur sources=3 (/home/avivsabilalm/.../verilator_bin)
```

Jalan penuh nomor 1, `/home/avivsabilalm/.../rtl-synthesis/reports/fase8/jalan-penuh-1-20261021-004418.log`
(41 baris, isi dipotong hanya pada nama direktori):

```
run_sim.sh: tb=../rtl/tb/tb_fitur.sv sources=2 plusargs=1
  plusargs forwarded to vvp: +VECTOR=../rtl/tb/vektor/fase8
  compiled first (packages): ../rtl/afib_lite_pkg.sv
tb_fitur: vectors   = ../rtl/tb/vektor/fase8
tb_fitur: limit     = 2595 of 2595 intervals
tb_fitur: arm A emissions = 638 of 638, pass 2 = 638
tb_fitur: arm B emissions = 624 of 624, pass 2 = 624
tb_fitur: arm A golden rows compared = 602 of 602, pass 2 = 602
tb_fitur: arm B golden rows compared = 588 of 588, pass 2 = 588
tb_fitur: d mismatches          = 0
tb_fitur: histogram mismatches  = 0
tb_fitur: pNN50 count mismatch  = 0
tb_fitur: pNN50 code mismatch   = 0
tb_fitur: four code mismatches  = 0
tb_fitur: sample_end mismatch   = 0
tb_fitur: ev_kind mismatch      = 0
tb_fitur: ev_val high bits      = 0
tb_fitur: d_valid pulse mismatch= 0
tb_fitur: windows dropped (ovf) = 0
tb_fitur: range gate count wrong= 0
tb_fitur: oracle words unknown  = 0
tb_fitur: arm B rows over 1 LSB = 0 (worst 1 LSB)
tb_fitur: comparisons run       = 602 arm A + 588 arm B
tb_fitur: digest A pass1/pass2  = 99b99f28 / 99b99f28
tb_fitur: digest B pass1/pass2  = 4499c5f6 / 4499c5f6
tb_fitur: mismatches = 0 out of 1190
tb_fitur: PASS
$finish called at 4567765 (1s)
```

Jalan penuh nomor 2: keluaran identik, `cmp` bersih, sha256 sama (lihat tabel).

## 4. Tabel gerbang

| gerbang (verbatim baris tabel rencana) | status | angka nyata |
|---|---|---|
| `d` 0 beda | **lulus** | 602/602 baris lengan berpenanda bit-exact, `d mismatches = 0` |
| cacah pNN50 0 beda | **lulus** | `pNN50 count mismatch = 0` (dari `m_ev_val[5:0]`) dan `pNN50 code mismatch = 0` |
| 16 cacah histogram 0 beda | **lulus** | `histogram mismatches = 0`, 16 bin per baris, 602 baris |
| 0 dari 602 cacah histogram beda | **lulus** | baris emas yang dibandingkan = 602 dari 602 (bukan subset) |
| akar dalam 1 LSB, 0 kode > 1 LSB | **lulus** | lengan berpenanda worst 0 LSB; lengan mentah worst tepat 1 LSB, `arm B rows over 1 LSB = 0` |
| entropi dalam 1 LSB, 0 kode > 1 LSB | **lulus** | `ent` worst 0 LSB di kedua lengan (`code worst LSB ent: 0`, `raw worst ent: 0`) |
| rasio di bawah 0,75 LSB (blok bagian 12) | **lulus** | `ratio` worst 0 LSB di kedua lengan |
| lint bersih | **lulus** | `lint clean` untuk `features` dan `tb_fitur`, 0 warning |
| deterministik dua jalan penuh | **lulus** | `cmp` dua log bersih; sha256 log sama; digest A/B sama di dalam simulasi (masing-masing lengan dijalankan dua kali) |
| `rc != 0` saat gagal | **lulus** | enam kontrol negatif semuanya `rc=1` dengan baris `FATAL` (bagian 6) |

Yang **belum** diuji dan tidak diklaim: jalur `ovf` (snapshot jatuh saat unit sibuk) hanya
diverifikasi sebagai `ovf_cnt_q = 0`, jalur jatuhnya sendiri tidak pernah dipicu; `i_clear_counters`
di tengah aliran, `i_enable` rendah, reset di tengah jendela, dan bit 0..2 `i_arm_select` tidak
diuji di sini (pemiliknya `classifier.sv` dan top level).

## 5. Perlakuan khusus yang harus diketahui pembaca

1. **Tiga bug RTL ditemukan testbench dan diperbaiki** di `rtl/features.sv` (rincian di
   `PROGRES.md` bagian 5): offset field `dvec_q` dihitung 5 bit sehingga melingkar; `abin_w[16]`
   di luar jangkauan sehingga `d_ent` = `x` untuk setiap jendela dan `bin_q[15]` = `x`; kode pNN50
   dibaca satu cacahan terlalu awal sehingga satu langkah rendah setiap `|d|` terakhir > 50 ms.
   Ketiganya akan membuat gerbang gagal total; setelah perbaikan 0 beda.
2. **`d`, 16 bin, kode pNN50 dan empat tap diperiksa lewat kotak putih** (`dvec_q`, `bin_q`,
   `pnn50_q`) dengan rujukan hierarkis, karena RTL hanya mengeluarkan empat tap dan cacah pNN50.
   Konvensi ini sudah dipakai `tb_kuantisasi.sv` (`dut.pre_raw`). Porta yang mengekspor `d` bukan
   bagian dari kontrak beku, jadi tidak ditambahkan.
3. **Penyaring kelas tidak diimplementasikan** (tidak ada porta untuk label irama). Karena itu
   lengan berpenanda mengeluarkan 638 jendela sementara berkas emas berisi 602 baris: 602 baris itu
   semua lolos penyaring kelas di `rantai.py:818`, dan 36 emisi tambahan tanpa baris emas dilaporkan
   di peta sebagai `FFFFFFFF` dan tidak dibandingkan. Lengan mentah: 624 emisi, 588 baris emas
   (penyaring kelas membuang 36 baris pertama, sumbernya `decisions.csv`).
4. **Cadangan kecepatan simulasi**: testbench menyalurkan satu interval tiap 44 siklus. Itu pilihan
   biaya simulasi Icarus (jalan penuh ≈ 4,57 juta satuan waktu, ≈ 9 menit dinding per jalan), bukan
   batas perangkat keras; `ovf_cnt_q = 0` membuktikan mesin tidak pernah tertinggal pada cadangan ini.
5. **Bentuk simpul dipilih bukan bentuk literal rencana**: bentuk literal lulus gerbang "1 LSB"
   tetapi tidak lulus garis 0,5/0,75 LSB di blok bagian 12; bentuk yang dipakai memberi 0 LSB.
   Rincian pengukuran dan alasan ada di `PROGRES.md` bagian 3.

## 6. Kontrol negatif (bukti bench benar-benar bisa merah)

Semua pada salinan vektor di luar repo (`~/.hermes/cache/scratch/fase8/nc1..nc6`); direktori
`rtl/tb/vektor/fase8/` tidak disentuh.

| kontrol | kerusakan | rc | bukti mentah |
|---|---|---|---|
| nc1 | satu kata `d` emas dirusak (`00000010` -> `00000011`) | 1 | `d mismatches = 1`, `mismatches = 1 out of 4`, `FATAL ... smoke comparison failed` |
| nc2 | `gold.d.hex` dipotong 100 dari 18662 kata | 1 | `FAIL 1 vector tables are X at their ends`, `FATAL ... golden vectors missing or short` |
| nc3 | `map.marked.hex` dipotong 20 dari 1276 kata | 1 | `FAIL 1 vector tables are X at their ends` |
| nc4 | direktori vektor tidak ada | 1 | `FAIL 8 vector tables are X at their ends` |
| nc5 | X di tengah `gold.bins.hex` | 1 | `oracle words unknown = 2`, `histogram mismatches = 1` |
| nc6 | X di tengah `map.marked.hex` (sample_end + baris) | 1 | `oracle words unknown = 1`, `sample_end mismatch = 1` |

Log mentah: `reports/fase8/sim-nc1.log` ... `sim-nc6.log`, `sim-smoke.log`, `sim-full.log`.

Mode pendek mencetak lima baris `SKIP` eksplisit dan `SMOKE OK, the full gate is NOT claimed`,
jadi tidak ada gerbang yang dilonggarkan tanpa dicatat.

## 7. sha256

Daftar lengkap ada di `rtl-synthesis/reports/fase8/SHA256.txt` (ditulis paling akhir, setelah
seluruh berkas selesai, memuat `features.sv`, `tb_fitur.sv`, eksportir, 11 berkas vektor,
`PROGRES.md`, dokumen ini, dan semua log simulasi). Nilai kunci, semuanya dihitung setelah kerja
selesai:

| berkas | sha256 |
|---|---|
| `rtl/features.sv` | `a6de59095fbc15a09549fc1c0518c571446274df2599e3b35f9269c4c69b2675` |
| `rtl/tb/tb_fitur.sv` | `26da322cbefbeb869255fce2dd877826aec6a608f8db004de104c8249edd9690` |
| `rtl/tb/vektor/fase8/ekspor_vektor_fase8.py` | `026ab9e0cf6038a69c2284a91296c6b935db5f11ac638bbfdd5919181875c499` |
| `jalan-penuh-1-20261021-004418.log` | `31e64f4bd314dae11252a26903880d8be14ec587391fe033d093f7850b369b13` |
| `jalan-penuh-2-20261021-004418.log` | `31e64f4bd314dae11252a26903880d8be14ec587391fe033d093f7850b369b13` |
| `model/rantai-afib-lite/rantai.py` | `90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5` |

`rantai.py` tidak disentuh: sha256 di atas sama sebelum dan sesudah kerja ini, dan itulah hash
model beku yang juga dirujuk `04015.fase8.manifest.json` (`frozen_model_sha256`).

Catatan jujur soal manifest: `04015.fase8.manifest.json` ikut masuk daftar `files_sha256` di
dalamnya sendiri lewat pola glob, jadi entri untuk berkas manifest tersebut berisi hash manifest
**versi sebelumnya** dan tidak akan pernah cocok dengan dirinya sendiri. Sepuluh berkas vektor
lainnya diverifikasi cocok dengan manifest (`python3` membaca ulang dan membandingkan, 10 dari 10
cocok, 1 yang tidak cocok adalah manifest itu sendiri). Ini cacat kosmetik di eksportir, bukan
pada data gerbang: seluruh vektor yang dipakai gerbang cocok dengan manifest.
