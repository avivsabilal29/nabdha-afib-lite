# LAPORAN FASE 6 (plan 38) -- deret RR dan empat tanda interval

Pekerja: subagent Fase 6. Tanggal: 21 Oktober 2026. Bahasa: Indonesia (istilah teknis Inggris).
Berkas yang dikerjakan: `rtl/rr_series.sv` (isi badan), `rtl/tb/tb_rr.sv` (baru),
`rtl/tb/vektor/fase6/**`, `rtl-synthesis/reports/fase6/**`.
Data emas `rtlplan2/fase5/**` tidak diubah. `model/rantai-afib-lite/rantai.py` tidak diubah
(sha256 sesudah kerja: `90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5`,
sama dengan rantai beku yang diminta).

## 1. Status gerbang

Gerbang Fase 6 apa adanya (kutipan tabel plan): **"tb_rr 0 dari 2.595 interval; panjang antrean
tepat 8 sesudah langkah 24; keempat tanda terbaca"**.

| Bagian gerbang | Status | Angka nyata |
|---|---|---|
| 0 dari 2.595 interval berbeda | LULUS | `tb_rr: intervals compared = 2595` / `interval mismatches = 0 out of 2595` |
| panjang antrean tepat 8 sesudah langkah 24 | LULUS | emas: antrean terakhir tidak penuh = langkah 24, antrean langkah 25 = 8, 0 baris sesudah langkah 24 yang tidak penuh; sintetis: `phase B queue length at step 24 = 8`, langkah pertama penuh = 15, 0 langkah sesudah 24 yang tidak penuh; kolom antrean per langkah cocok 2586/2586 terhadap data emas |
| keempat tanda terbaca | LULUS | `mark census dut = 2186 397 9 3` = `mark census gold = 2186 397 9 3`, dan tiap kode diperiksa > 0 |
| lint bersih | LULUS (berkas Fase 6) | `lint clean: top=rr_series` dan `lint clean: top=tb_rr` (rc=0); `--chain` gagal karena 13 PINMISSING di `rtl/afib_lite_top.sv` milik pekerja lain, 0 dari berkas Fase 6 (lihat bagian 5) |
| robust + deterministik | LULUS | dua jalan penuh byte identik (md5 sama), dua kontrol negatif rc != 0 (lihat bagian 4) |

Bukti tambahan yang ikut lulus pada jalan penuh (bukan bagian gerbang, tapi menjaga gerbang
tidak lulus karena alasan yang salah):
`step rows compared = 2586` dan `step mismatches = 0 out of 2586` (ra1, ra2, panjang antrean,
menyala, disemai, panjang riwayat, gagal, jeda, indeks langkah, panjang jendela delapan),
`end of run counters: steps = 2586, reseeds = 26, menyala total = 1202` (sama dengan manifest
Fase 5: langkah 2586, semai 26, penanda 1202),
`o_rr_long_count = 3` = emas, `event kind/idx/val = 0/0/0`, `beat amplitude mismatch = 0`,
`poll timeouts = 0`, dan semua penjaga saturasi 0 (`ms sat 0, smp sat 0, quotient over 0,
ra1 over 0, remainder over 0`).

## 2. Perintah persis dan keluaran mentah

Semua dari `rtl-synthesis/`.

### 2.1 Lint RTL

```
$ ./run_lint.sh ../rtl/rr_series.sv rr_series ../rtl/afib_lite_pkg.sv
RC=0
  ../rtl/afib_lite_pkg.sv
  ../rtl/rr_series.sv
lint clean: top=rr_series sources=2 (…/debroot/usr/bin/verilator_bin)
```
Log: `rtl-synthesis/reports/fase6/lint-rr_series.log`.

### 2.2 Lint testbench (ikut RTL sebagai sumber)

```
$ ./run_lint.sh ../rtl/tb/tb_rr.sv tb_rr ../rtl/afib_lite_pkg.sv ../rtl/rr_series.sv
RC=0
  ../rtl/afib_lite_pkg.sv
  ../rtl/tb/tb_rr.sv
  ../rtl/rr_series.sv
lint clean: top=tb_rr sources=3 (…/debroot/usr/bin/verilator_bin)
```
Log: `rtl-synthesis/reports/fase6/lint-tb_rr.log`.

### 2.3 Jalan penuh (determinisme, gerbang utama)

```
$ ./run_sim.sh ../rtl/tb/tb_rr.sv ../rtl/afib_lite_pkg.sv ../rtl/rr_series.sv -- +VECTOR=../rtl/tb/vektor/fase6
```
Jalan 1 (`reports/fase6/sim-penuh-jalan1-20261021-001238.log`), rc=0:
```
tb_rr: every golden word is defined (38862 columns read)
tb_rr: golden intervals 2595, beats 2596, steps 2586
tb_rr: golden census keep/split/drop/gap = 2186/397/9/3, corrected entries 2983
tb_rr: golden queue not full through step 24, queue at step 25 = 8
tb_rr: intervals compared = 2595
tb_rr: interval mismatches = 0 out of 2595
tb_rr: step rows compared = 2586
tb_rr: step mismatches = 0 out of 2586
tb_rr: mark census dut = 2186 397 9 3
tb_rr: mark census gold = 2186 397 9 3
tb_rr: events rr=2595 window=1 other=0
tb_rr: golden queue length at step 24 = 7, at step 25 = 8, last step not full = 24
tb_rr: golden steps after 24 whose queue is not full = 0, queue full at step 24 = 0
tb_rr: o_rr_long_count = 3, golden intervals above the ceiling = 3
tb_rr: end of run counters: steps = 2586, reseeds = 26, menyala total = 1202
tb_rr: phase B queue length at step 24 = 8
tb_rr: phase B mismatches = 0 out of 39
tb_rr: phase C train intervals = 9, long intervals = 1, counter = 1, expected = 1
tb_rr: phase C long counter after the clear pulse = 0
tb_rr: phase C gap events = 1, window events = 1
tb_rr: mismatches = 0 out of 5220
tb_rr: PASS
../rtl/tb/tb_rr.sv:782: $finish called at 1486376 (1s)
```
(Log `sim-penuh-jalan1-20261021-001118.log` dan `-jalan2-20261021-001134.log` adalah keadaan
lulus yang sama sebelum gerbang `$isunknown` ditambahkan pada bagian 4(b); keduanya bukan bukti
determinisme yang dipakai, yang dipakai adalah pasangan 001238/001240 di bawah.)

Jalan 2 (`reports/fase6/sim-penuh-jalan2-20261021-001240.log`), rc=0, byte identik dengan jalan 1:
```
$ cmp sim-penuh-jalan1-20261021-001238.log sim-penuh-jalan2-20261021-001240.log   # bersih
$ md5sum sim-penuh-jalan1-20261021-001238.log sim-penuh-jalan2-20261021-001240.log
6dbd391bf627df1d046ffa52253a516e  …jalan1-20261021-001238.log
6dbd391bf627df1d046ffa52253a516e  …jalan2-20261021-001240.log
```

### 2.4 Jalan pendek untuk iterasi (bukti bahwa gerbang bukan hanya lulus di ujung)

```
$ ./run_sim.sh ../rtl/tb/tb_rr.sv ../rtl/afib_lite_pkg.sv ../rtl/rr_series.sv -- +VECTOR=../rtl/tb/vektor/fase6 +LIMIT=60
RC=0   mismatches = 0 out of 157
```

### 2.5 Jalan penuh SEBELUM perbaikan tanda (bukti kegagalan yang jujur, disimpan)

`reports/fase6/sim-penuh-20261021-000914.log`, rc=1:
```
tb_rr: mark census dut = 2418 165 9 3
tb_rr: mark census gold = 2186 397 9 3
tb_rr: mark=234 mask out of range=0
FATAL: ../rtl/tb/tb_rr.sv:779: tb_rr: gate violation, see the counters above
```
Dua kesalahan nyata yang ketemu dari jalan itu, di jalur tanda (bukan di saluran interval):
1. jendela irama menulis entri GAP padahal model tidak mendorong entri apa pun untuk sebuah
   gap (`rantai.py:536-542` kembali tanpa `_rr_push_window`), dan
2. penunjuk jendela maju satu entri untuk sebuah split padahal model mendorong DUA entri
   (dua paruh), jadi isi jendela 8 entri menyimpang begitu split pertama muncul (interval 20).

## 3. Apa yang diuji testbench

`rtl/tb/tb_rr.sv`, tiga fase dalam satu jalan, semua nilai harapan dari berkas emas atau dari
konstanta paket, tanpa satu pun angka hasil ukur di dalam berkas.

- **Fase A, rekaman emas.** Stimulus = 2596 posisi QRS dari `qrs_sample_index`
  `04015.peaks.csv` (bukan `rtl/peak_detect.sv`, sesuai aturan brief: berkas itu milik pekerja
  Fase 5 dan menggerakkan TB dari keluarannya akan membuat kedua gerbang tak bermakna).
  Dihitung terhadap emas: `d_rr_ms`, `m_rr_last`, `d_rr_smp`, `m_rr_mark` dan bentuk satu
  panas topengnya (kolom `mark_keep/mark_split/mark_drop/mark_gap`), sisi peristiwa
  (jenis/indeks/nilai), amplitudo beat (`d_beat_val_q` terhadap kolom `envelope_value`), dan
  keadaan per langkah: ra1, ra2, panjang antrean, menyala, disemai, panjang riwayat, gagal,
  jeda, indeks langkah, panjang jendela delapan.
- **Fase B, gerbang plan apa adanya.** Deret konstan 40 beat berjarak 200 sampel (800 ms,
  diperiksa ada di dalam pita paket): harapan panjang antrean dihitung dari konstanta paket
  (`DELAPAN`), bukan dari angka ukur; langkah pertama yang penuh harus 15, panjang antrean di
  langkah 24 harus 8, dan tidak boleh ada langkah sesudah 24 yang tidak penuh. Dicetak apa
  adanya: `phase B queue length at step 24 = 8`.
- **Fase C, tanda GAP dan dua penanda samping.** Riwayat 800 ms dibangun lebih dulu (supaya
  syarat missed beat `50x > 83 median` dan plafon `RR_LONG_MS` keduanya benar-benar berlaku;
  ketiga syaratnya diperiksa di TB dengan variabel supaya bukan lipatan konstanta), lalu satu
  interval 4800 ms harus bertanda GAP dan menaikkan `o_rr_long_count`, yang kemudian dibersihkan
  oleh `i_clear_counters`. Setelah itu passthrough: satu siklus dengan bit penanda sampel hilang
  harus memunculkan tepat satu EV_GAP, satu siklus `t_last` tepat satu EV_WINDOW (dihitung oleh
  monitor `always @(posedge clk)` bersaklar fase, bukan oleh gelung poll).

## 4. Robustness dan determinisme (syarat pemilik proyek)

(a) **Dua jalan penuh identik.** Lihat 2.3: dua log ber-timestamp terpisah, `cmp` bersih,
md5 sama `6dbd391bf627df1d046ffa52253a516e`.

(b) **Kontrol negatif.** Salinan vektor di `rtl/tb/vektor/fase6/mutasi-negatif/` (data emas
`rtlplan2/fase5/**` tidak disentuh), satu nilai harapan diubah: baris 100 `04015.rr.hex`
`000003b8` -> `000003b9`:
```
$ ./run_sim.sh ../rtl/tb/tb_rr.sv ../rtl/afib_lite_pkg.sv ../rtl/rr_series.sv -- +VECTOR=../rtl/tb/vektor/fase6/mutasi-negatif
KONTROL_NEGATIF_RC=1
MISM interval=99 d_rr_ms dut=952 gold=953
MISM interval=99 m_rr_last dut=952 gold=953
MISM step row 100 carries interval 952, the driven one is 953
tb_rr: interval mismatches = 4 out of 2595
tb_rr: mismatches = 4 out of 5220
FATAL: ../rtl/tb/tb_rr.sv:820: tb_rr: gate violation, see the counters above
```
Log: `reports/fase6/sim-kontrol-negatif.log`.
Kontrol negatif kedua, yang menemukan kelemahan nyata di TB saya sendiri: direktori vektor yang
tidak ada membuat `$readmemh` meninggalkan isi memori sebagai X, dan `X !== X` TIDAK dihitung
sebagai ketidakcocokan, jadi jalan itu akan terbaca lulus dengan jumlah baris penuh. Sekarang TB
memeriksa setiap kata emas dengan `$isunknown` sebelum dipakai sebagai oracle:
```
$ ./run_sim.sh ../rtl/tb/tb_rr.sv ../rtl/afib_lite_pkg.sv ../rtl/rr_series.sv -- +VECTOR=../rtl/tb/vektor/tidak-ada-dir
KONTROL_VEKTOR_HILANG_RC=1
FATAL: ../rtl/tb/tb_rr.sv:310: tb_rr: FAIL 38862 golden words are unknown, the vector directory is missing, short or unreadable
```
Log: `reports/fase6/sim-kontrol-vektor-hilang.log`.

(c) **Satu domain clock, reset sinkron aktif rendah, tanpa latch, tanpa primitif vendor,
tanpa indeks penampan dari nilai data.** Di `rtl/rr_series.sv` hanya ada satu blok berclock:
`always @(posedge clk_i)` (baris 537), sisanya empat blok `always @(*)` murni kombinasional;
reset sinkron aktif rendah (`if (!rst_ni)` di dalam blok berclock, tidak ada `posedge rst_ni`);
tidak ada primitif vendor (tidak ada IBUF/LUT/RAMB/DSP/Xilinx/ALTERA); Verilator lint bersih
sehingga tidak ada LATCH/WIDTH; semua gelung pencarian berbatas tetap (8 slot jendela, 8 slot
antrean, 32 slot riwayat, 16 langkah median, 20 langkah pembagian). Penunjuk cincin
(`hist_w_q`, `deret_w_q`, `riwayat_w_q`, `antre_w_q`) adalah penghitung dengan putaran, bukan
alamat yang berasal dari nilai interval; indeks `div_num_q[div_bit_q]` adalah pemilih bit dari
pembagi restoring 20 langkah tetap. Ini saya tulis eksplisit karena brief melarang indeks yang
berasal dari nilai data, dan penunjuk cincin adalah satu-satunya indeks "berjalan" di berkas ini.

## 5. Penyimpangan, batasan, dan pekerjaan yang belum selesai (jujur)

1. **`run_lint.sh --chain` GAGAL, tetapi bukan karena berkas Fase 6.** Log
   `reports/fase6/lint-chain.log`: 13 `%Warning-PINMISSING`, semuanya di
   `../rtl/afib_lite_top.sv` (mis. `Cell has missing pin: 'o_overrun'` pada instans `t_rule`),
   0 dari `rr_series.sv` dan 0 dari `tb_rr.sv`. `afib_lite_top.sv` milik pekerja paralel dan
   tidak boleh saya sentuh, jadi lint rantai penuh tidak bisa saya tutup di fase ini.
2. **Satu blok waiver lint di `rtl/rr_series.sv`.** Porta beku tidak boleh berubah dan kata
   pemilik proyek juga melarang menambah porta, sedangkan `rtl/peak_detect.sv` (Fase 5) diberi
   porta introspeksi `d_dbg`/`d_dbg_valid` sebagai penyimpangan yang dilaporkan. Saya tidak boleh
   menambah porta, jadi bank introspeksi `d_step_*` (bacaan gerbang Fase 6 nomor 2 dan 3) dibaca
   TB lewat rujukan hierarkis, dan Verilator menandai keenam belas deklarasi itu `UNUSEDSIGNAL`
   karena tidak ada pembaca di dalam modul. Blok
   `/* verilator lint_off UNUSEDSIGNAL */ … /* verilator lint_on UNUSEDSIGNAL */` membungkus
   HANYA bank itu, dan ini satu-satunya waiver di berkas. Semua sinyal lain bersih tanpa waiver.
3. **Gerbang 2 dan 3 tidak bisa dibuktikan tanpa rujukan hierarkis** karena alasan pada butir 2;
   bila pemilik proyek lebih suka porta introspeksi (seperti `peak_detect.sv`), porta beku harus
   dibuka lebih dulu.
4. **Integrasi hulu belum diuji, dan itu memang disengaja.** TB tidak menginstansiasi
   `peak_detect.sv`; jadi kesetaraan bit-akurat `rr_series` terhadap model hanya dibuktikan bila
   masukan posisi QRS benar, dan itu menjadi tanggung jawab gerbang Fase 5. Uji sambungan
   hulu-hilir perlu fase lanjutan.
5. **`o_rr_long_count` tidak punya pasangan di model.** Model tidak menghitung penghitung
   interval panjang; angka emas 3 dihitung skrip vektor dari deret emas
   (`rr_ms > RR_LONG_MS`, konstanta paket) dan diperiksa konsisten dengan census gap 3. Jadi
   gerbang ini adalah "titik di atas ambang" yang sama, bukan keluaran model yang independen.
6. **Batas panjang larik di TB ditulis sebagai literal** (2596/2595/2586/16) tetapi diperiksa
   saat jalan terhadap blok counts emas dan menjadi `$fatal` bila berbeda, jadi batas basi
   menjadi kegagalan keras, bukan lulus sebagian. Angka yang sama juga tercatat di manifest
   vektor beserta sha256 masukan dan model.
7. **`+LIMIT=n` hanya menggerbangi awalan n beat.** Akhir jalan (penghitung langkah, census)
   sengaja dilewati pada jalan pendek dan dicetak sebagai `SKIP end of run counters`, supaya
   jalan pendek tidak pernah terbaca sebagai lulus penuh.
8. **Belum diuji:** perilaku `i_enable=0` di tengah interval, `s_ev_kind` selain EV_QRS pada
   masukan, dan `i_clear_counters` di tengah proses (hanya diuji dalam keadaan idle pada Fase C).
9. **Kepatuhan berkas.** Yang ditulis hanya `rtl/rr_series.sv`, `rtl/tb/tb_rr.sv` (nama ini belum
   dipakai, sudah diperiksa), `rtl/tb/vektor/fase6/**` (termasuk salinan kontrol negatif),
   `rtl-synthesis/reports/fase6/**`, dan laporan ini. Tidak ada `git add/commit/checkout/stash`
   yang dijalankan, tidak ada berkas terlarang yang disentuh, `model/rantai-afib-lite/rantai.py`
   tetap pada sha256 beku (dibuktikan di bagian atas).

## 6. Cara mengulang bukti

```
cd rtl-synthesis
./run_lint.sh ../rtl/rr_series.sv rr_series ../rtl/afib_lite_pkg.sv
./run_lint.sh ../rtl/tb/tb_rr.sv tb_rr ../rtl/afib_lite_pkg.sv ../rtl/rr_series.sv
./run_sim.sh ../rtl/tb/tb_rr.sv ../rtl/afib_lite_pkg.sv ../rtl/rr_series.sv -- +VECTOR=../rtl/tb/vektor/fase6
./run_sim.sh ../rtl/tb/tb_rr.sv ../rtl/afib_lite_pkg.sv ../rtl/rr_series.sv -- +VECTOR=../rtl/tb/vektor/fase6/mutasi-negatif
```
