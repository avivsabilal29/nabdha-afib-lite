# LAPORAN FASE 4b: square.sv dan integrator.sv

Repo: /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
Branch: aviv/rtl-fpga-simulation, HEAD 13f666a. Tidak ada commit dan tidak ada `git add`.
Model tetap beku: `model/rantai-afib-lite/rantai.py` sha256 `90df6e5b457307d3` (dicek
ulang sesudah seluruh pekerjaan), adapter, fixture, `afib_lite_pkg.sv`, dan seluruh
`rtl/*.sv` lain tidak disentuh.

## 1. Berkas yang disentuh

| Berkas | Keadaan | sha256 (16 pertama) | baris |
|---|---|---|---|
| rtl/square.sv | diisi, body nyata menggantikan placeholder, port dan lebar tidak berubah | a945899ec328ec93 | 120 |
| rtl/integrator.sv | diisi, body nyata menggantikan placeholder, port dan lebar tidak berubah | 424361755302749b | 149 |
| rtl/tb/tb_square.sv | dibuat, gerbang kuadrat | 16215ef48c1e61d4 | 202 |
| rtl/tb/tb_integrator.sv | dibuat, gerbang jendela | 71cde2d9a2632c74 | 306 |
| rtl-synthesis/reports/LAPORAN-FASE4b.md | dibuat, laporan ini | | |
| rtl-synthesis/reports/fase4/ | dibuat, seluruh log mentah | | |

Vektor emas yang dipakai, tidak diubah dan tidak diekspor ulang:

| Kolom | sha256 (16 pertama) |
|---|---|
| 04015.turunan.hex | 824fcddba95d4ccc |
| 04015.kuadrat.hex | f49a1690c09b9584 |
| 04015.jendela.hex | 9f798e87f793130d |

## 2. Persyaratan yang dikutip apa adanya

Gerbang fase, dokumen 38 bagian 1.3 baris fase 4:

> | 4 | Tiga tahap non-linier | `derivative.sv`, `square.sv`, `integrator.sv` | 0 dari 450.000
> masing-masing; deret sintetis negatif turunan 0 beda; **lebar jendela 37.000 dan 38.000
> terbaca** | 8 jam | pemilik RTL |

Dan baris testbench-nya, dokumen 38 bagian 6, tabel per stage, baris 7:

> | 7 | `tb_integrator.sv` | jendela bergerak 37 dan 38 | `kuadrat` ditambah masukan
> konstan sintetis | `jendela` (450.000) | 0 dari 450.000; **lebar jendela terbaca 37.000 dan
> 38.000 pada masukan konstan 1.000** |

Artinya gerbang lebar jendela itu bukan lebar bit dan bukan parameter panjang jendela: ia
adalah pembacaan nilai. Pada masukan konstan 1.000, jendela selebar N_WIN_ALT = 37
menjumlahkan 37 x 1000 = 37.000 dan jendela selebar N_WIN = 38 menjumlahkan 38 x 1000 =
38.000, jadi angka 37.000 dan 38.000 itu adalah bukti bahwa pasangan bergantian 37 dan 38 di
`rantai.py:274-275` benar-benar terjadi di RTL. Rekurensi yang diuji, `rantai.py:270-275`:
`jumlah += nilai; if i >= 38: jumlah -= x[i-38]; sel = jumlah; if i % 2 == 0 and i >= 37:
sel -= x[i-37]`. Rumus dan pembacaan itu diambil dari dokumen 38 bagian 4.6 (tabel jendela
berjalan) dan diverifikasi ulang di luar RTL sebelum RTL ditulis, lihat bagian 5.

## 3. Arsitektur yang dibangun

### 3.1 square.sv

`d = s_tdata >>> SHIFT_DER`, aritmetika, lantai, sama dengan `rantai.py:244`; `ku = d * d`,
sama dengan `rantai.py:245`. Lebar dari paket saja: `W_DER` 24 masuk, `W_DV = W_DER -
SHIFT_DER` 16 bit kata tergeser, `W_PROD = W_SQ_WORST` 32 bit menampung hasil kali eksak,
keluaran `W_SQ` 30 bit. Saturasi di `SQ_SAT` 1073741823: bila hasil kali melewatinya,
keluaran menjadi `SQ_SAT` dan `m_overflow` naik, sifatnya sticky dan hanya kata yang
`s_tvalid` boleh menaikkannya. Bit 7:0 dari `s_tdata` memang dibuang oleh geser lantai itu;
penekanan `UNUSEDSIGNAL` lokal dan berkomentar dipasang pada porta, pola yang sama dengan
`rtl/acq_frontend.sv:70-72`. `d_sq` dan `m_tdata` membawa nilai yang sama pada siklus yang
sama: tahap ini hanya punya satu register keluaran, jadi latensi kasatmata satu siklus.

### 3.2 integrator.sv

Garis tunda `LINE_WORDS = N_WIN + 1` = 39 kata, `line_q[k] = x[i-1-k]`, jadi `x[i-38]` dan
`x[i-37]` terbaca bersamaan tanpa penjadwalan tambahan, dan bacaan sebelum kata itu tiba
bernilai nol yang memang kondisi awal nol di model. Akumulator `jumlah_q` selebar
`W_WIN_WORST` = 37 bit dan memuat jumlah 38 kata terakhir saja, persis `rantai.py:270` dan
`:272`; koreksi jendela 37 tidak dilipat ke akumulator, ia dikurangkan pada keluaran saja,
persis `rantai.py:273-275`. Itu bukan detail kosmetik: pada revisi pertama koreksi 37 ikut
masuk ke akumulator, dan hasilnya turun 1.000 tiap sampel sesudah indeks 38 (nilai terbaca
37.000 pada indeks 39 yang seharusnya 38.000). Penjaga `i >= N_WIN` dan `i >= N_WIN_ALT`
memakai `s_sample_idx`, basis waktu PL, bukan pencacah lokal, karena pencacah lokal akan
meleset satu sampel sesudah reset. Keluaran `W_WIN` 33 bit: batas desain 13.316.659.200
memang di atas jangkauan 33 bit (2^33 - 1 = 8.589.934.591), jadi porta menjenuh pada
`{W_WIN{1'b1}}` dan `m_overflow` naik; akumulator internal yang 37 bit tidak pernah
dijenuhkan, karena jumlah terbesar yang mungkin adalah 38 x (2^30 - 1) = 40.802.199.130 <
2^37.

## 4. Gerbang dan hasilnya

### 4.1 Lint, satu modul satu perintah, keluaran mentah di `reports/fase4/`

```
$ ./run_lint.sh ../rtl/square.sv square ../rtl/afib_lite_pkg.sv
run_lint.sh: top=square sources=2 timing=0
  ../rtl/afib_lite_pkg.sv
  ../rtl/square.sv
lint clean: top=square sources=2 (.../debroot/usr/bin/verilator_bin)
rc=0

$ ./run_lint.sh ../rtl/integrator.sv integrator ../rtl/afib_lite_pkg.sv
run_lint.sh: top=integrator sources=2 timing=0
  ../rtl/afib_lite_pkg.sv
  ../rtl/integrator.sv
lint clean: top=integrator sources=2 (.../debroot/usr/bin/verilator_bin)
rc=0
```

Dua testbench juga lint bersih, `--timing` otomatis karena nama berkasnya:

```
$ ./run_lint.sh ../rtl/tb/tb_square.sv tb_square ../rtl/afib_lite_pkg.sv ../rtl/square.sv
lint clean: top=tb_square sources=3 (.../verilator_bin)          rc=0

$ ./run_lint.sh ../rtl/tb/tb_integrator.sv tb_integrator ../rtl/afib_lite_pkg.sv ../rtl/integrator.sv
lint clean: top=tb_integrator sources=3 (.../verilator_bin)      rc=0
```

### 4.2 square: 0 dari 450.000

Perintah dan keluaran mentah (`reports/fase4/sim_tb_square_full.log`):

```
$ ./run_sim.sh ../rtl/tb/tb_square.sv ../rtl/afib_lite_pkg.sv ../rtl/square.sv \
    -- +VECTOR=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0
tb_square: limit   = 450000 of 450000
tb_square: presented = 450000
tb_square: outputs   = 450000
tb_square: compared  = 450000
tb_square: d_sq mismatches    = 0
tb_square: m_tdata mismatches = 0
tb_square: sample_idx mismatch= 0
tb_square: tuser mismatches   = 0
tb_square: tlast mismatches   = 0
tb_square: golden format odd  = 0
tb_square: overflow pulses    = 0
tb_square: d_valid pulses     = 450000
tb_square: mismatches = 0 out of 450000
tb_square: PASS
```

`overflow pulses = 0` pada seluruh 450.000 kata, sesuai perkiraan induk: kuadrat terbesar
di kolom emas 350438400 jauh di bawah `SQ_SAT` 1073741823, jadi penjenuhan tidak boleh
menyala sekali pun, dan penanda itu ikut jadi syarat PASS. Kalau ia menyala, laporan ini
akan menuliskannya sebagai temuan, bukan menutupinya dengan penjepitan lain.

Mode pendek juga sudah dijalankan lebih dulu, `+LIMIT=20000`, 0 dari 20000, PASS
(`reports/fase4/sim_tb_square_lim20000.log`).

### 4.3 integrator: 0 dari 450.000 dan lebar jendela 37.000 / 38.000

Perintah dan keluaran mentah (`reports/fase4/sim_tb_integrator_full.log`):

```
$ ./run_sim.sh ../rtl/tb/tb_integrator.sv ../rtl/afib_lite_pkg.sv ../rtl/integrator.sv \
    -- +VECTOR=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0
tb_integrator: limit   = 450000 of 450000
tb_integrator: phase A  = window width gate, constant input 1000, 80 words
tb_integrator: phase A outputs checked = 80 of 80
tb_integrator: phase A window width 37 reads = 37000
tb_integrator: phase A window width 38 reads = 38000
tb_integrator: phase A mismatches = 0
tb_integrator: presented = 450000
tb_integrator: outputs   = 450000
tb_integrator: compared  = 450000
tb_integrator: d_win mismatches   = 0
tb_integrator: m_tdata mismatches = 0
tb_integrator: sample_idx mismatch = 0
tb_integrator: tuser mismatches   = 0
tb_integrator: tlast mismatches   = 0
tb_integrator: jendela words at or above 2**31 = 27
tb_integrator: overflow pulses    = 0
tb_integrator: d_valid pulses     = 450000
tb_integrator: mismatches = 0 out of 450000
tb_integrator: PASS
```

Dua hal yang dicetak di situ adalah gerbangnya sendiri. Pertama, `mismatches = 0 out of
450000`: `d_win` dan `m_tdata` sama dengan `04015.jendela.hex` untuk seluruh 450.000 kata.
Kedua, `phase A window width 37 reads = 37000` dan `phase A window width 38 reads = 38000`:
itulah persyaratan "lebar jendela 37.000 dan 38.000 terbaca pada masukan konstan 1.000",
dan yang dicetak bukan konstanta yang diketik di testbench, melainkan `d_win` yang benar
benar keluar dari DUT pada indeks genap pertama dan indeks ganjil pertama sesudah
N_WIN_ALT = 37, lalu dibandingkan dengan N_WIN_ALT x 1.000 dan N_WIN x 1.000. Fase A juga
memeriksa 80 kata pembuka terhadap (indeks + 1) x 1.000, yaitu bentuk jendela yang belum
penuh, dan 0 dari 80 berbeda.

`jendela words at or above 2**31 = 27` adalah bukti bahwa kolom itu dibaca sebagai 32 bit
tanpa tanda: 27 kata di kolom emas berada di atas 2^31 (terbesar 3105281786), dan testbench
mendeklarasikan memorinya `reg [31:0]` tanpa pernah membaca satu kolom pun sebagai nilai
32 bit bertanda. Setiap kata keluaran dibandingkan pada lebar porta penuh 33 bit terhadap
kata emas yang diperluas nol, jadi bit ke-33 yang menyimpang tidak bisa bersembunyi di
balik separuh rendah yang cocok.

Mode pendek, `+LIMIT=20000`, juga 0 dari 20000 dan PASS
(`reports/fase4/sim_tb_integrator_lim20000.log`).

### 4.4 lint seluruh rantai, bukti tambahan

```
$ ./run_lint.sh --chain
run_lint.sh: top=afib_lite_top sources=13 timing=0
lint clean: top=afib_lite_top sources=13 (.../verilator_bin)     rc=0
```

### 4.5 dua kali jalan pada berkas yang diserahkan

Kedua gerbang paritas dijalankan ulang pada berkas akhir yang punya sha256 di tabel bagian
1, dan keluarannya identik kata per kata dengan jalan pertama (satu-satunya beda adalah
baris `sim rc=0` yang hanya ada di log jalan pertama):

```
diff <(grep -v '^run_sim\|^  ' sim_tb_square_full.log)     <(..._run2.log)     -> identik
diff <(grep -v '^run_sim\|^  ' sim_tb_integrator_full.log) <(..._run2.log)     -> identik
```

Log jalan kedua: `reports/fase4/sim_tb_square_full_run2.log` dan
`reports/fase4/sim_tb_integrator_full_run2.log`, keduanya `rc=0` dan `PASS`.

## 5. Pemeriksaan di luar RTL lebih dulu

Sebelum satu baris SystemVerilog ditulis, rekurensi kedua tahap dijalankan ulang dengan
Python murni atas kolom emas yang sama (`rujukan_fase4b.py`, di luar repo). Hasilnya:
square 0 berbeda dari 450.000 dengan faktor geser terbesar 18720 dan 0 kejadian saturasi;
jendela 0 berbeda dari 450.000, terbesar 3105281786, 27 kata di atas 2^31; dan pada masukan
konstan 1.000 deretnya bergantian 38000, 37000, 38000, 37000 mulai indeks 37. Skrip itu
yang menetapkan arti gerbang lebar jendela sebelum RTL ada, jadi gerbang di bagian 4.3
bukan tafsir sesudah fakta.

## 6. Penyimpangan, dan hal yang belum dikerjakan

1. `LAT_CYCLES` tidak dibaca di dalam badan kedua modul. Keduanya punya tepat satu register
   keluaran, jadi latensi kasatmata 1 siklus, dan nilainya harus 1. Parameter itu tetap ada
   karena daftar porta dan parameter sudah beku, dan `run_lint.sh` memang mematikan
   `UNUSEDPARAM` untuk alasan ini. Pada square, enam tingkat pipa larik pengali dari
   dokumen 38 bagian 4.5 berada di dalam unit pengali bersama, bukan di daftar porta ini.
2. Jadwal 2 siklus per sampel dari dokumen 38 bagian 4.6 (kandidat C, satu penjumlah 35 bit
   dipakai dua kali, garis tunda 39 kata di LUTRAM) tidak dibangun. Alasannya aritmetika:
   `rantai.py:270-275` memecah operasinya menjadi pembaruan akumulator tiga suku
   (`jumlah + nilai - x[i-38]`) dan koreksi keluaran satu suku (`- x[i-37]`, hanya indeks
   genap). Pass kedua dari penjumlah yang dipakai ulang karena itu hanya membawa satu
   pengurangan, sehingga tidak membayar mesin keadaan dan penampan 39 kata yang dihitung
   rencana. Badan yang dibangun mengevaluasi kedua operasi itu sebagai satu pohon
   tambah/kurang 37 bit empat operan, satu siklus per sampel, dan pemisahan akumulator
   lawan keluaran tetap eksak seperti model. Ini keputusan area dan waktu, bukan paritas:
   gerbangnya tidak bergantung padanya.
3. Lebar akumulator internal diambil `W_WIN_WORST` = 37 bit, bukan "batas desain 35 bit"
   dari tabel dokumen 38 bagian 4.6. Alasannya: 37 bit adalah konstanta paket sendiri
   (38 x SQ_LIMIT^2 = 121318382342) dan ia membuktikan akumulator tidak bisa membelit untuk
   masukan apa pun yang muat di porta `W_SQ` (38 x (2^30 - 1) = 40802199130 < 2^37),
   sedangkan 35 bit adalah batas terukur terhadap kuadrat terbesar satu rekaman.
4. Penekanan `UNUSEDSIGNAL` lokal dan berkomentar pada porta `s_tdata` square: geser lantai
   memang membuang `SHIFT_DER` bit bawah, jadi ekonominya nyata. Pola dan alasannya sama
   dengan `rtl/acq_frontend.sv:70-72` dan laporan Fase 2 bagian 3.2.
5. Gerbang "deret sintetis negatif turunan 0 beda" di baris fase 4 yang sama adalah milik
   `derivative.sv`, berkas pemilik lain. Gerbang itu tidak dijalankan di sini dan tidak
   dilaporkan lulus.
6. Revisi pertama `integrator.sv` salah dan ditemukan sendiri oleh fase A, bukan oleh kolom
   emas: koreksi jendela 37 dilipat ke akumulator sehingga jendela menyusut satu suku tiap
   sampel. Angka mentahnya disimpan utuh di
   `reports/fase4/sim_tb_integrator_lim20000.rev1.log` (fase A membaca 17000 dan 17000,
   41 dari 80 berbeda, 19961 dari 20000 kata berbeda, 19882 siklus keluaran dengan
   `m_overflow` tinggi). Berkas itu tidak dihapus: ia bukti proses, bukan hasil akhir.
7. Tidak ada commit, tidak ada `git add`. `model/`, `rtl/afib_lite_pkg.sv`,
   `rtl/derivative.sv`, dan seluruh `rtl/*.sv` lain tidak disentuh; hash rantai.py dicek
   ulang sesudah pekerjaan dan tetap `90df6e5b457307d3`.

## 7. Log mentah

```
rtl-synthesis/reports/fase4/lint_square.out
rtl-synthesis/reports/fase4/lint_integrator.out
rtl-synthesis/reports/fase4/lint_tb_square.out
rtl-synthesis/reports/fase4/lint_tb_integrator.out
rtl-synthesis/reports/fase4/lint_chain_fase4b.out
rtl-synthesis/reports/fase4/sim_tb_square_lim20000.log
rtl-synthesis/reports/fase4/sim_tb_square_full.log
rtl-synthesis/reports/fase4/sim_tb_integrator_lim20000.log
rtl-synthesis/reports/fase4/sim_tb_integrator_lim20000.rev1.log
rtl-synthesis/reports/fase4/sim_tb_integrator_full.log
rtl-synthesis/reports/fase4/sim_tb_square_full_run2.log
rtl-synthesis/reports/fase4/sim_tb_integrator_full_run2.log
```

Skrip pemeriksaan di luar RTL: `/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase4b/rujukan_fase4b.py`.

## 8. Perintah ulang, apa adanya

```
cd ~/hackathon-semiconductor-programs/nabdha-afib-lite/rtl-synthesis
./run_lint.sh ../rtl/square.sv square ../rtl/afib_lite_pkg.sv
./run_lint.sh ../rtl/integrator.sv integrator ../rtl/afib_lite_pkg.sv
./run_sim.sh ../rtl/tb/tb_square.sv ../rtl/afib_lite_pkg.sv ../rtl/square.sv -- +VECTOR=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0
./run_sim.sh ../rtl/tb/tb_integrator.sv ../rtl/afib_lite_pkg.sv ../rtl/integrator.sv -- +VECTOR=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0
```

Plusarg selalu sesudah pemisah `--`. `+LIMIT=<n>` memperpendek fase kolom emas saja; fase
lebar jendela tetap 80 kata, dan bawaan tanpa `+LIMIT` adalah 450.000 kata penuh.

