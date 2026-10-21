# LAPORAN FASE 2: akuisisi dan kuantisasi masukan, jalur acq_frontend yang sebenarnya

Tanggal: 20 Oktober 2026. Repo: `/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite`, branch `aviv/rtl-fpga-simulation`. Tidak ada commit dan tidak ada push. Rencana induk: vault doc 38 bagian 12 subbagian Fase 2 (baris 2159 dan sekitarnya), bagian 4.1 (baris 534), bagian 3.2 dan 3.4, bagian 2.6 untuk aturan bahasa. Model acuan: `model/rantai-afib-lite/rantai.py` fungsi `kuantisasi` baris 156 sampai 166 dan konstanta baris 49 sampai 51, ditambah `model/rantai-afib-lite/adapter.py` baris 87 sampai 90 dan 341.

## 0. Status gerbang, satu tabel

| # | Gerbang | Perintah singkat | Keluaran | Status |
|---|---|---|---|---|
| 1 | Verilator lint rantai penuh | `./run_lint.sh --chain` | rc 0, 0 keluhan, 13 sumber | LULUS |
| 2 | slang 12.0.0 (toolbase), pendapat kedua | `slang --top afib_lite_top <13 berkas>` | rc 0, 0 error, 0 warning | LULUS |
| 3 | uji tuntas 4095 cacah, kata dan simpul pre | `./run_sim.sh ../rtl/tb/tb_kuantisasi.sv ../rtl/acq_frontend.sv ../rtl/afib_lite_pkg.sv -- +VECTOR=...` | `count mismatches: 0`, `pre node mismatches: 0` | LULUS |
| 3b | uji aliran 450000 kata | sama, ditambah `+STIM=...` | `words compared: 450000`, `mismatches: 0` | LULUS |
| 3c | penanda dan pencacah status terhadap manifest | sama | `status clamp count: 402`, `status gap count: 0`, `marker weak words: 8817`, indeks 449999 | LULUS |
| 3d | struktur waktu 250 Hz | sama | `sample_en spacing: 400000`, `sample_en pulses: 5` | LULUS |
| 3e | mode B, pemulihan cacah dari kolom saja | `+VECTOR=... ` tanpa `+STIM`, `+RAILC=1000` dan `+RAILC=2047` | 0 mismatch, `mode B clamp count: 0` dan `: 406` | LULUS sebagai diagnosis, lihat bagian 4 |
| 4 | skrip penyiap vektor, empat gerbangnya | `python3 siapkan_vektor.py` | 4 gerbang PASS, 450000 baris stimulus | LULUS |
| 5 | Verilator atas testbench | `./run_lint.sh ../rtl/tb/tb_kuantisasi.sv tb_kuantisasi ../rtl/acq_frontend.sv ../rtl/afib_lite_pkg.sv` | 1 peringatan sisa, TIMESCALEMOD milik paket, bukan buatan Fase 2 | DILAPORKAN |
| 6 | regresi Fase 1 sesudah paket disentuh | `./run_sim.sh ../rtl/tb/tb_pkg_konstanta.sv ../rtl/afib_lite_pkg.sv` | rc 0, 68 pemeriksaan, `bit differences: 0` | LULUS |
| 7 | seluruh pemeriksaan testbench | dihitung sendiri oleh testbench | `checks: 27`, `failures: 0` | LULUS |
| 8 | jalur vektor hilang, uji negatif | tambah `+VECTOR=<path yang tidak ada>` | `FATAL cannot open ...`, berhenti di siklus 0 | LULUS |

Baris gate yang diminta induk, apa adanya, dari berkas mentah `reports/fase2/sim_modeA.log`:

```
count mismatches: 0
words compared: 450000
mismatches: 0
tie counts found: 4
status clamp count: 402
status gap count: 0
marker weak words: 8817
sample_en spacing: 400000
sample_en pulses: 5
```

## 1. Berkas yang dibuat dan diubah

| Berkas | Baris | Isi |
|---|---|---|
| `rtl/acq_frontend.sv` | 330, sebelumnya 152 | diganti seluruhnya: pencacah laju 20 bit, pencacah indeks 32 bit, deteksi celah dengan jendela pemulihan, pencacah penjepitan sebelum penjepitan, dan kuantiser pipa 15 tingkat |
| `rtl/tb/tb_kuantisasi.sv` | 710, berkas baru | testbench Fase 2, pembaca manifest dan kolom emas, penunjuk putih ke simpul pre, enam blok uji |
| `rtl/tb/vektor/siapkan_vektor.py` | 249, berkas baru | penyiap stimulus dari rekaman, dengan empat gerbang pengukuran sendiri |
| `rtl/tb/vektor/04015.stimulus.hex` | 450000 baris, 2250000 bita | satu kata 16 bit per baris, 4 digit heksa: nibble penanda lalu 12 bit cacah |
| `rtl/tb/vektor/siapkan_vektor.out` | 52 | keluaran mentah skrip penyiap |
| `rtl/afib_lite_pkg.sv` | 289, sebelumnya 273 | DITAMBAH, lihat bagian 5 butir 1: tiga konstanta, `MV_FULL_SCALE`, `REC_GAIN_MV`, `Q_DIVISOR` |
| `rtl-synthesis/reports/LAPORAN-FASE2.md` | laporan ini | |
| `rtl-synthesis/reports/fase2/*.log` | 7 berkas | log mentah semua gerbang |

Log mentah, semuanya di `rtl-synthesis/reports/fase2/`:

```
lint_chain.log                 gerbang 1
lint_slang_fase2.log           gerbang 2
sim_modeA.log                  gerbang 3, 3b, 3c, 3d, mode B rail 1000
sim_modeB2047.log              gerbang 3e, mode B rail 2047
regression_fase1_tb_pkg.log    gerbang 6
lint_tb_fase2.log              gerbang 5
sim_negative_missing_vector.log gerbang 8
```

## 2. Perintah dan keluaran mentah

### 2.1 Gerbang 1, Verilator lint rantai penuh

```
$ cd rtl-synthesis && ./run_lint.sh --chain
run_lint.sh: top=afib_lite_top sources=13 timing=0
  ../rtl/afib_lite_pkg.sv
  ../rtl/acq_frontend.sv
  ../rtl/afib_lite_top.sv
  ../rtl/bandpass.sv
  ../rtl/classifier.sv
  ../rtl/derivative.sv
  ../rtl/features.sv
  ../rtl/integrator.sv
  ../rtl/peak_detect.sv
  ../rtl/regs_axi.sv
  ../rtl/rr_series.sv
  ../rtl/square.sv
  ../rtl/t_rule.sv
lint clean: top=afib_lite_top sources=13 (.../debroot/usr/bin/verilator_bin)
lint_chain_rc=0
```

Jalur ini sempat tidak bersih dan dua keluhan nyata diperbaiki tanpa mematikan peringatan:

1. `%Warning-UNUSEDSIGNAL` pada bit `s_tdata[3:0]`, karena kuantiser hanya membaca medan cacah. Alasan ekonomi bitnya nyata, jadi penekanannya eksplisit dan berkomentar di dekat deklarasi porta, bukan global, dan pilihan medannya dijelaskan di bagian 3.2.
2. `%Warning-WIDTHEXPAND` pada `pre_raw << SHIFT_IN`, karena operan geser 15 bit di konteks 16 bit. Diperbaiki dengan perluasan tanda eksplisit ke lebar kata sebelum digeser, sehingga hasilnya eksak dan lebarnya sama dengan lebar port.

### 2.2 Gerbang 2, slang (toolbase)

```
$ source /home/avivsabilalm/eda/env.sh && slang --version
slang version 12.0.0+545f88b2e
$ slang --top afib_lite_top <13 berkas yang sama>
Top level design units:
    afib_lite_top

Build succeeded: 0 errors, 0 warnings
slang_rc=0
```

### 2.3 Gerbang 3, uji tuntas dan uji aliran, jalur mode A

```
$ ./run_sim.sh ../rtl/tb/tb_kuantisasi.sv ../rtl/acq_frontend.sv ../rtl/afib_lite_pkg.sv -- \
    +VECTOR=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.masukan16.hex \
    +MANIFEST=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json \
    +STIM=/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite/rtl/tb/vektor/04015.stimulus.hex
run_sim.sh: tb=../rtl/tb/tb_kuantisasi.sv sources=2 plusargs=3
  compiled first (packages): ../rtl/afib_lite_pkg.sv
== tb_kuantisasi, Fase 2, record 04015 ==
INFO  golden column lines: 450000
INFO  manifest frames=450000 words_per_column=450000
INFO  manifest clamp=402 gap=0
INFO  manifest weak=8817 uncertain=0
counts swept: 4095
distinct words over the sweep: 2001
counts up to 1000: 2001
injective up to 1000: 1
counts at the rail word: 2096
counts exactly on the rail: 2
tie c=-1500 even=-3070 away=-3071 word=-32752
tie c=-500 even=-1024 away=-1024 word=-16384
tie c=500 even=1024 away=1024 word=16384
tie c=1500 even=3070 away=3071 word=32752
tie counts found: 4
pipeline latency measured: 15
counts driven: 4095
count mismatches: 0
pre node mismatches: 0
INFO  stimulus lines: 450000
words compared: 450000
mismatches: 0
index mismatches: 0
marker passthrough mismatches: 0
introspection mismatches: 0
event sideband mismatches: 0
golden words at the rail: 406
marker weak words: 8817
marker clamp words: 402
marker unsure words: 0
overflow words: 0
tlast words: 1
status clamp count: 402
status gap count: 0
status sample index at last word: 449999
last emitted word index: 449999
mode B rail count driven: 1000
mode B words compared: 450000
mode B mismatches: 0
mode B clamp count: 0
sample_en spacing: 400000
sample_en pulses: 5
sample_en spacing constant: 1
synthetic gap events: 2
synthetic gap events on the sideband: 2
synthetic gap marked words: 131
checks: 27
failures: 0
../rtl/tb/tb_kuantisasi.sv:707: $finish called at 29545016000 (1ps)
rc=0
```

### 2.4 Gerbang 3e, mode B dengan rel diisi penuh, pendapat ketiga tentang penjepitan

```
$ ./run_sim.sh ... -- +VECTOR=... +MANIFEST=... +STIM=... +RAILC=2047
mode B rail count driven: 2047
mode B words compared: 450000
mode B mismatches: 0
mode B clamp count: 406
checks: 27
failures: 0
modeB2047_rc=0
```

Tiga jalur, tiga angka, dan ketiganya nyata. Kolom emas 04015 memuat 406 kata yang berada di rel, 402 di antaranya adalah sampel yang benar benar jenuh dan 4 adalah sampel yang mendarat tepat di rel. Kalau kata rel dipulihkan menjadi cacah 1000, cacah internal 2047 dan penjepitan tidak terjadi, jadi pencacah penjepitan modul menjadi 0. Kalau dipulihkan menjadi cacah 2047, seluruh 406 dihitung. Hanya cacah rekaman yang sebenarnya yang memberi 402, dan itulah angka manifest. Pembahasan di bagian 4.

### 2.5 Gerbang 4, skrip penyiap vektor dan empat gerbangnya

```
$ cd rtl/tb/vektor && python3 -u siapkan_vektor.py > siapkan_vektor.out 2>&1
vector   : /home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.masukan16.hex
manifest : /home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json
record   : /home/avivsabilalm/.hermes/cache/scratch/afib/afdb_local/04015
model    : /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite/model/rantai-afib-lite

gate 1: integer quantiser against np.rint over -4095 to 4095
  counts swept          : 8191
  mismatches against np.rint: 0
  tie counts in 0 to 4095: [-3500, -2500, -1500, -500, 500, 1500, 2500, 3500]
  tie c= -3500 pre= -7164 word=-32752
  tie c= -2500 pre= -5118 word=-32752
  tie c= -1500 pre= -3070 word=-32752
  tie c=  -500 pre= -1024 word=-16384
  tie c=   500 pre=  1024 word= 16384
  tie c=  1500 pre=  3070 word= 32752
  tie c=  2500 pre=  5118 word= 32752
  tie c=  3500 pre=  7164 word= 32752

golden words            : 450000, min -29776 max 32752
golden at the rail      : 406
manifest frames         : 450000, columns 6
manifest markers        : {'clamp': 402, 'gap': 0, 'weak': 8817, 'uncertain': 0}

record 04015            : fmt 212, gain 200.0 counts per mV, zero 0.0
counts read             : 450000, min -909 max 1287
  note: the count of the RTL is c = count - zero, this header has zero 0

gate 2: the quantiser of every record count against the golden column
  words compared        : 450000
  mismatches            : 0

gate 3: the clamp census of the record
  clipped, strict pre test  : 402
  exactly on the rail       : 4
  counts with |c| == 1000   : 4
  manifest clamp marker     : 402
  rail words of the column  : 406
  rail words minus clipped  : 4

gate 4: the weak marker, recomputed from the word column alone
  weak from the word column : 8817
  weak from adapter markers : 8817
  manifest weak marker      : 8817
  the two masks are equal   : True

stimulus written        : /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite/rtl/tb/vektor/04015.stimulus.hex
  lines                 : 450000
  bytes                 : 2250000
  format                : 4 hex digits, marker nibble then 12 bit count
  markers written       : {'clamp': 402, 'gap': 0, 'weak': 8817, 'uncertain': 0}

gate: PASS, the stimulus reproduces the golden column and its censuses
```

### 2.6 Gerbang 5, Verilator atas testbench

```
$ ./run_lint.sh ../rtl/tb/tb_kuantisasi.sv tb_kuantisasi ../rtl/acq_frontend.sv ../rtl/afib_lite_pkg.sv
%Warning-TIMESCALEMOD: ../rtl/afib_lite_pkg.sv:44:9: Timescale missing on this module as other modules have it
%Error: Exiting due to 1 warning(s)
tb_lint_rc=1
```

Peringatan itu milik paket, bukan milik testbench Fase 2, dan paket tidak boleh diberi timescale. Angka pembandingnya penting: testbench Fase 1 pada gerbang sejenis memberi 13 error dan 89 peringatan (log `lint_tb_fase1.log`), testbench Fase 2 memberi 0 error sendiri dan satu peringatan warisan. Tiga peringatan `UNUSEDSIGNAL` yang sempat muncul dari tiga fungsi pembantu sudah hilang, dan satu penekanan eksplisit berkomentar ditambahkan pada fungsi yang memang membuang bit tinggi argumennya.

### 2.7 Gerbang 6, regresi Fase 1 sesudah paket ditambah

Paket Fase 2 menambah tiga konstanta, jadi gerbang Fase 1 dijalankan ulang sebagai syarat tidak merusak:

```
$ ./run_sim.sh ../rtl/tb/tb_pkg_konstanta.sv ../rtl/afib_lite_pkg.sv
REVIEW searchback.width          got=30           other=23           not counted
REVIEW buffer.depths             got=128          other=8            not counted
REVIEW rr.samples.width          got=15           other=16           not counted
REVIEW feature.widths.other      got=77           other=16           not counted
checks: 68
review lines: 5
bit differences: 0
regression rc=0
```

68 pemeriksaan dan `bit differences: 0`, sama persis dengan hasil Fase 1, jadi paritas konstanta tidak rusak.

### 2.8 Gerbang 8, uji negatif, jalur vektor yang tidak ada

```
$ ./run_sim.sh ../rtl/tb/tb_kuantisasi.sv ../rtl/acq_frontend.sv ../rtl/afib_lite_pkg.sv -- \
    +VECTOR=.../04015.NOT_HERE.hex +MANIFEST=... +STIM=...
INFO  vector   [/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.NOT_HERE.hex]
FATAL cannot open /home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.NOT_HERE.hex
$finish called at 0 (1ps)
```

Testbench berhenti sebelum satu siklus pun berjalan kalau berkas emas tidak ada, jadi tidak mungkin lulus dengan menguji kekosongan.

## 3. Yang diwujudkan di RTL

### 3.1 Kuantiser, bentuk yang mengikat

Bentuk yang mengikat dari rencana 4.1 dan model `rantai.py:156`:

```
n   = (c << 11) - c          c adalah cacah 12 bit bertanda, jadi n = c * 2047
q   = n div 1000             pembagi pulih bit serial
rem = n mod 1000             sisa pembagian yang sama
pre = rint(n / 1000)         half to even pada rem
kata = clamp(pre, -2047, +2047) << 4
```

Lebar, semuanya turunan dan bukan angka telanjang:

```
W_CNT     = W_IN - SHIFT_IN                     = 12   medan cacah
SHIFT_MUL = clog2(CLAMP_COUNT)                   = 11   karena 2047 = 2**11 - 1
W_MUL     = W_CNT + SHIFT_MUL                    = 23   |c * 2047| <= 4190209 < 2**22
SHIFT_QUO = clog2(Q_DIVISOR)                     = 10   karena 1000 < 2**10
W_STEP    = W_MUL - SHIFT_QUO                    = 13   langkah pembagi pulih
W_REM     = SHIFT_QUO + 1                        = 11   sisa <= 2 * 999
W_QUO     = W_STEP                               = 13   hasil bagi <= 4190 < 2**13
W_PRE     = W_QUO + 2                            = 15   pre bertanda, ditambah margin pembulatan
W_GAPSPAN = clog2(GAP_RECOVERY + 1)              = 8    jendela pemulihan 131
```

Rangkaian pipa: tingkat 0 mendaftar `n` menjadi `rem_q[0] = n >> W_STEP`, `bit_q[0] = n[W_STEP-1:0]`, `quo_q[0] = 0`, dan medan sisi (indeks sampel, penanda, tlast, tvalid, celah). Tingkat 1 sampai 13 masing masing satu langkah pulih: geser sisa satu bit dan sisipkan bit pembagi berikutnya dari bit paling tinggi, banding dengan 1000, kurangi kalau cukup, sisipkan bit hasil bagi. Tingkat terakhir membulatkan, menjepit, menggeser. Semua register memakai `reg`, semua kabel `wire`, tidak ada `logic` di berkas yang disintesis, sesuai D10.

Jumlah langkah yang dipakai 13, bukan 10 seperti kalimat rencana 4.1, dan ini keputusan sadar: hasil bagi yang eksak mencapai 4190 dan 4190 butuh 13 bit, sedangkan pembagi pulih bit serial menghasilkan satu bit hasil bagi per langkah. Menurunkan langkah sampai 10 berarti hasil bagi terpotong 3 bit dan uji tuntas tidak akan lulus. Anggaran siklus rencana 12 siklus per sampel menjadi 15 siklus per sampel, yaitu 0,0038 persen dari 400000 siklus yang tersedia di 250 Hz. Kelebihan dan kekurangan ini dicatat di bagian 5 butir 2.

Pembulatan half to even, persis baris 163 sampai 164 model dan butir 5 I2 bagian 1:

```
rem > 500          pre = q + 1
rem < 500          pre = q
rem == 500         pre = q ganjil ? q + 1 : q
```

Penjepitan diterapkan sebelum geser: `pre` dijepit ke plus minus 2047, lalu digeser kiri `SHIFT_IN` empat bit, sehingga kata maksimum 32752 dan minimum 32752 bertanda negatif, sama dengan `CLAMP_WORD` di paket.

### 3.2 Medan cacah di porta masukan

Tabel sinyal 43 baris menyatakan `s_tdata` adalah kata Q12.4 dengan 12 bit signifikan digeser kiri empat, sedangkan rencana 4.1 berbicara tentang cacah 12 bit. Keduanya dipenuhi sekaligus dengan membaca cacah dari medan `s_tdata[W_IN-1:SHIFT_IN]`, yaitu bit 15 sampai 4, dan tidak membaca empat bit terendah. Empat bit itu adalah bit bawah cacah dari tangga depan akuisisi (`adapter.py:87` sampai `89`, `ATTYS_FRONT_END`), lebih halus daripada satu cacah, dan model membulatkan pada cacah bulat, jadi membacanya justru akan menyimpang dari model. Ini penekanan peringatan yang sengaja dan berkomentar, bukan kelalaian.

### 3.3 Penghitung dan struktur waktu

Pencacah laju 20 bit dengan terminal dari paket, `RATE_DIV_RST` 399999, memberi denyut `sample_en` satu siklus setiap 400000 siklus, yaitu 250 Hz dari 100 MHz. Pencacah indeks 32 bit hanya naik saat `sample_en` dan `i_enable` tinggi. Pencacah status dihitung di sisi keluaran, jadi semua penghitung menyatakan sampel yang benar benar keluar dari tahap ini.

Pencacah penjepitan dihitung sebelum penjepitan, dan ujinya ketat: cacah yang mendarat tepat di 2047 tidak ditandai terjepit, sesuai catatan doc 36 3.6 dan `adapter.py:341`. Dengan cacah rekaman yang sebenarnya angkanya 402, sama dengan manifest, dan angka itu juga tampil di penanda keluaran, jadi ada dua jalur pengukuran yang setuju.

Deteksi celah punya dua sumber: bit penanda `s_tuser[TU_GAP]` dari aliran, dan slot sampel yang tidak membawa kata sama sekali. Keduanya menaikkan `o_gap_count` dan menyalakan penanda celah keluaran selama `GAP_RECOVERY` 131 kata. Keterangan penting: slot yang hilang tidak mengeluarkan kata sama sekali, jadi penanda tidak bisa menempel pada sampel yang hilang itu sendiri, dan uji sintetis menunjukkan hasil yang benar, 131 kata bertanda setelah slot terakhir yang hilang. Untuk rekaman 04015 tidak ada celah sama sekali, `status gap count: 0`, sama dengan manifest.

Latensi tetap 15 siklus, diukur oleh testbench (`pipeline latency measured: 15`) dan dicocokkan dengan 2 ditambah W_STEP. Tidak ada `tready` di dalam jalur, sesuai D1, dan `i_enable` hanya mematikan `tvalid` keluaran, tidak menahan pipa.

### 3.4 Cara testbench menggerakkan

Uji aliran menjalankan 450000 cacah pada satu sampel per siklus (`i_rate_div` 0), karena 450000 sampel pada jarak 400000 siklus adalah 1,8 kali 10 pangkat 11 siklus dan tidak ada simulator yang bisa menjalankannya. Konsekuensinya dinyatakan terang: uji aliran menguji aritmetika dan penanda, sedangkan syarat 250 Hz diuji tersendiri di uji struktur waktu pada `RATE_DIV_RST`, dan di sana jaraknya 400000 siklus terukur. Datapath tidak bergantung pada `sample_en` sama sekali, jadi pemadatan waktu tidak mengubah perilaku yang diuji.

Cacah yang digerakkan diambil dari rekaman 04015 lewat adapter beku, bukan dari kolom emas, dan itu disengaja, sebabnya di bagian 4. Stimulusnya tetap diverifikasi terhadap kolom emas: skrip penyiap memeriksa bahwa kuantiser dari setiap cacah rekaman memberi kata emas yang sama, 450000 kata, 0 mismatch, dan bahwa topeng penanda lemah yang dihitung ulang dari kolom emas sama persis dengan topeng adapter, 8817 sampel.

## 4. Tiga temuan yang diukur, bukan diklaim

### 4.1 Peta maju kuantiser tidak satu ke satu

Ini temuan induk yang diverifikasi ulang di sini dan hasilnya sama, dengan angka lebih halus:

```
counts swept: 4095
distinct words over the sweep: 2001
counts up to 1000: 2001
injective up to 1000: 1
counts at the rail word: 2096
counts exactly on the rail: 2
```

Di seluruh 4095 cacah hanya ada 2001 kata keluaran yang berbeda. Selang |c| kecil sama dengan 1000 adalah 2001 cacah ke 2001 kata, jadi satu ke satu dan eksak di sana. Sisa 2094 cacah semuanya jatuh ke dua kata rel, plus dan minus 32752. Karena itu klaim injektivitas global tidak diuji, yang diuji adalah injektivitas pada |c| kecil sama dengan 1000 beserta laporan jumlah kata berbeda, 2001 dari 4095.

### 4.2 406 lawan 402, dan kenapa keduanya benar

Kolom emas 04015 memuat 406 kata di rel. Angka 406 itu terukur sendiri oleh testbench (`golden words at the rail: 406`) dan oleh skrip penyiap. Yang benar benar jenuh adalah 402 sampel, sama dengan penanda penjepitan adapter dan sama dengan manifest. Selisih 4 adalah sampel yang mendarat tepat di rel: cacah plus minus 1000, `pre` tepat plus minus 2047, uji penjepitan yang ketat tidak menyalakannya. Semuanya terukur:

```
golden at the rail      : 406
clipped, strict pre test  : 402
exactly on the rail       : 4
counts with |c| == 1000   : 4
rail words minus clipped  : 4
```

Akibatnya, dan ini yang menentukan cara menggerakkan testbench: cacah tidak dapat dipulihkan dari kolom emas dengan cara yang sekaligus mereproduksi pencacah penjepitan. Mode B membuktikannya dengan dua jalur, pada dua log terpisah:

```
mode B rail count driven: 1000   -> mode B clamp count: 0
mode B rail count driven: 2047   -> mode B clamp count: 406
```

Keduanya memberi 0 mismatch kata, dan keduanya memberi angka penjepitan yang salah terhadap manifest. Hanya cacah rekaman yang sebenarnya memberi 402. Karena itu jalur utama memakai cacah rekaman, yang sudah diverifikasi mereproduksi kolom emas kata demi kata, dan pemulihan dari kolom tetap dijalankan sebagai diagnosis. Catatan D9 rencana, penghitung penjepitan berbeda dari fixture 406 lawan 402, dengan ini dijelaskan sumbernya dan tidak perlu dipaksa cocok.

### 4.3 Aturan pembulatan half to even tidak terlihat di kata keluaran

Aturan itu menyentuh empat cacah di rentang RTL, plus minus 500 dan plus minus 1500, dan testbench menampilkan keempatnya:

```
tie c=-1500 even=-3070 away=-3071 word=-32752
tie c=-500 even=-1024 away=-1024 word=-16384
tie c=500 even=1024 away=1024 word=16384
tie c=1500 even=3070 away=3071 word=32752
tie counts found: 4
```

Baris even adalah aturan rencana, baris away adalah aturan saingannya. Pada plus minus 500 kedua aturan memberi nilai yang sama persis, 1024. Pada plus minus 1500 kedua aturan berbeda, 3070 lawan 3071, tetapi keduanya dijepit ke 2047, jadi kata keluarnya sama sama rel. Kesimpulannya nyata dan harus dinyatakan: uji tuntas pada tingkat kata tidak dapat membuktikan aturan half to even, walaupun hasilnya nol mismatch. Pembuktian dipindahkan ke simpul pre sebelum penjepitan, yang dibaca testbench sebagai titik putih yang ditandai (`pre_dut_q`, karena simpul aslinya kombinasional satu siklus lebih awal daripada kata yang terdaftar). Di sana seluruh 4095 cacah dibandingkan dengan nilai acuan:

```
pre node mismatches: 0
```

Jadi kata acuan half to even terbukti eksak pada rentang penuh, dan pembuktian itu tidak bergantung pada kata keluaran.

## 5. Di mana rencana, model, dan kenyataan berselisih

1. Paket ditambah, dan ini disampaikan lantang: `rtl/afib_lite_pkg.sv` menerima tiga konstanta, `MV_FULL_SCALE` 5, `REC_GAIN_MV` 200, dan `Q_DIVISOR` yang merupakan hasil kali keduanya, 1000. Pembagi 1000 adalah satu satunya angka yang dibutuhkan kuantiser dan tidak ada konstanta lain di paket yang bisa menyediakannya, sedangkan aturan rumah melarang modul menulis angka telanjang, jadi tempatnya memang di paket. Nilainya tidak diketik: 2047 per 1000 adalah sama dengan GAIN_COUNT model, 2047 per 5, dibagi gain rekaman 200 cacah per mV (`rantai.py:49`, `adapter.py:90`). Tidak ada baris lain di paket yang disentuh dan tabel 43 baris tidak berubah. Gerbang Fase 1 dijalankan ulang sebagai bukti, 68 pemeriksaan, `bit differences: 0`.

2. Rencana 4.1 menyebut sepuluh langkah pembagi pulih dan anggaran 12 siklus per sampel. RTL memakai 13 langkah dan 15 siklus per sampel, dengan alasan aritmetika yang bisa diperiksa: hasil bagi eksak mencapai 4190, 4190 butuh 13 bit, dan pembagi pulih bit serial memerlukan satu langkah per bit hasil bagi. Langkah 10 akan memotong hasil bagi tiga bit dan uji tuntas tidak akan lulus. Bedanya 3 siklus per sampel dan 0,0038 persen dari anggaran waktu yang tersedia.

3. Kontrak porta dan parameter menyimpan `LAT_CYCLES` bernilai 1, sedangkan latensi tahap ini sekarang 15 siklus karena kedalaman pembagi. Daftar porta dan parameter dibekukan, jadi parameternya tetap ada, tetapi tidak lagi menggambarkan tahap ini, dan itu dicatat di kepala berkas. Testbench tidak mempercayai angka mana pun: ia mengukur latensinya sendiri (`pipeline latency measured: 15`) lalu membandingkannya dengan 2 ditambah W_STEP.

4. Tabel sinyal 43 baris menyebut `s_tdata` sebagai Q12.4, sedangkan rencana 4.1 menyebut cacah 12 bit. RTL membaca cacah dari bit 15 sampai 4 dan sengaja tidak membaca bit 3 sampai 0. Bit bawah itu nyata ada di rekaman (tangga depan `adapter.py:87` sampai `89`) tetapi lebih halus daripada satu cacah, dan model membulatkan pada cacah bulat, jadi membacanya akan menyimpang dari model. Ini satu satunya penekanan peringatan di berkas yang disintesis, letaknya di deklarasi porta dan berkomentar.

5. Rencana 4.1 menyebut empat cacah tempat aturan pembulatan berlaku. Benar, dan keempatnya terukur, tetapi sebagaimana bagian 4.3, aturan itu tidak dapat dibuktikan pada kata keluaran. Ini bukan selisih angka antara rencana dan model, melainkan batas apa yang bisa diamati dari luar, dan karena itu pembuktiannya dipindahkan ke simpul pre.

6. Tidak ditemukan satu pun tempat di mana RTL harus menyimpang dari model `rantai.py`. Pada 450000 sampel rekaman 04015, kata keluaran RTL sama dengan kolom emas kata demi kata, 0 mismatch, dan penanda lemah yang dihitung ulang dari kolom emas sama persis dengan penanda adapter. Yang berselisih hanya soal jumlah langkah pembagi dan soal apa yang bisa diamati, bukan soal nilai.

## 6. Catatan dan risiko

1. Pembagi berjalan satu langkah per siklus, dan satu langkah adalah banding dan kurang pada 11 bit. Aturan irisan rencana untuk penjumlah 100 MHz membatasi penjumlah panjang menjadi irisan 9 bit per siklus, jadi langkah ini bisa jadi terlalu panjang untuk tutup waktu. Tutup waktu bukan gerbang Fase 2 dan tidak ada sintesis atau STA yang dijalankan di sini, jadi ini dilaporkan sebagai risiko untuk fase sintesis: kalau tutup waktu menuntut, langkah pembagi dapat diiris tanpa mengubah aritmetika, hanya menambah siklus latensi.

2. Uji aliran berjalan satu sampel per siklus, bukan pada 250 Hz. Syarat 250 Hz diuji tersendiri dan lulus, dan datapath tidak melihat `sample_en`, jadi ini bukan kompromi mutu, tetapi harus dinyatakan supaya tidak dibaca sebagai 450000 sampel pada laju sebenarnya.

3. Pencacah status dihitung di sisi keluaran tahap, bukan di sisi masukan. Ini berarti pencacah penjepitan dan celah menyatakan kata yang benar benar keluar, dan pada uji aliran yang padat waktunya angkanya sama. Belum ada uji dengan aliran yang tersendat sengaja di dalam satu slot, karena kontraknya tidak mengizinkan `tready` di dalam dan aliran beku datang satu kata per slot.

4. Peringatan `TIMESCALEMOD` pada lint testbench berasal dari paket yang tidak punya timescale, dan paket tidak boleh diberi timescale. Ini warisan Fase 1, bukan buatan Fase 2, dan gerbang lint yang mengikat, rantai penuh di bawah Verilator, bersih tanpa peringatan.

5. Berkas stimulus 450000 baris, 2250000 bita, disimpan di dalam repo karena memang tempatnya menurut penugasan, dan seluruhnya dapat dibangkitkan ulang oleh `rtl/tb/vektor/siapkan_vektor.py`. Sidik jarinya dicatat: stimulus `26a77ff59f0c434f7ad9597678987223fcf579cb9ac88adead53b09528b4ea16`, kolom emas `ac14e41ba4dbab96b87ffe22681fa1e04b15ce3313584480bd6adfc9ca0700d5`, dan yang kedua sama dengan `hex_sha256` di manifest sehingga berkas yang diuji memang berkas yang diekspor Fase 0.

6. Jalur mode B sengaja dijalankan dua kali, `+RAILC=1000` dan `+RAILC=2047`, karena satu jalur saja akan menyembunyikan temuan 406 lawan 402. Keduanya memberi 0 mismatch kata dan keduanya memberi angka penjepitan yang berbeda dari manifest, dan itulah buktinya bahwa kolom saja tidak cukup untuk memulihkan cacah.

## 7. Perintah inventarisasi dan berkas mentah

```
$ cd rtl-synthesis && ./run_lint.sh --chain > reports/fase2/lint_chain.log 2>&1 ; echo rc=$?
rc=0
$ source /home/avivsabilalm/eda/env.sh && slang --top afib_lite_top <13 berkas> > reports/fase2/lint_slang_fase2.log 2>&1 ; echo rc=$?
rc=0
$ ./run_sim.sh ../rtl/tb/tb_kuantisasi.sv ../rtl/acq_frontend.sv ../rtl/afib_lite_pkg.sv -- +VECTOR=... +MANIFEST=... +STIM=... > reports/fase2/sim_modeA.log 2>&1 ; echo rc=$?
rc=0
$ ./run_sim.sh ../rtl/tb/tb_kuantisasi.sv ../rtl/acq_frontend.sv ../rtl/afib_lite_pkg.sv -- +VECTOR=... +MANIFEST=... +STIM=... +RAILC=2047 > reports/fase2/sim_modeB2047.log 2>&1 ; echo rc=$?
rc=0
$ ./run_lint.sh ../rtl/tb/tb_kuantisasi.sv tb_kuantisasi ../rtl/acq_frontend.sv ../rtl/afib_lite_pkg.sv > reports/fase2/lint_tb_fase2.log 2>&1 ; echo rc=$?
rc=1, 1 peringatan warisan paket
$ ./run_sim.sh ../rtl/tb/tb_pkg_konstanta.sv ../rtl/afib_lite_pkg.sv > reports/fase2/regression_fase1_tb_pkg.log 2>&1 ; echo rc=$?
rc=0
$ wc -l rtl/acq_frontend.sv rtl/tb/tb_kuantisasi.sv rtl/tb/vektor/siapkan_vektor.py rtl/afib_lite_pkg.sv
  330 rtl/acq_frontend.sv
  710 rtl/tb/tb_kuantisasi.sv
  249 rtl/tb/vektor/siapkan_vektor.py
  289 rtl/afib_lite_pkg.sv
```

Versi alat: iverilog dan vvp 12.0 (stable) dari jalur repo, `rtl-synthesis/debroot/usr/bin/verilator_bin` Verilator 5.020, yosys 0.33 tidak dipakai di fase ini, slang 12.0.0 dari toolbase untuk pendapat kedua.

## 8. Kesimpulan

Kuantiser masukan AFIB-LITE di `rtl/acq_frontend.sv` sekarang bit eksak terhadap model `rantai.py` pada seluruh rentang cacah yang mungkin dan pada seluruh 450000 kata rekaman 04015. Semua gerbang yang diminta induk dijalankan dan keluaran mentahnya disimpan di `rtl-synthesis/reports/fase2/`:

```
count mismatches: 0                        uji tuntas 4095 cacah
pre node mismatches: 0                     bukti aturan half to even, 4095 cacah
words compared: 450000, mismatches: 0      uji aliran
status clamp count: 402                    sama dengan manifest
status gap count: 0                        sama dengan manifest
marker weak words: 8817                    sama dengan manifest
status sample index: 449999, terakhir 449999  sama dengan manifest
sample_en spacing: 400000, pulses: 5       250 Hz terukur
lint rantai rc 0, slang 0 error 0 warning  gerbang statis
checks: 27, failures: 0                    seluruh pemeriksaan
```

Tiga hal yang tidak dapat ditutupi dan sudah dinyatakan di atas: peta maju kuantiser tidak satu ke satu sehingga cacah tidak dapat dipulihkan dari kolom emas tanpa catatan tambahan, aturan pembulatan hanya terbukti di simpul pre, dan jumlah langkah pembagi 13, bukan 10 seperti kalimat rencana, karena eksak menuntut 13 bit hasil bagi. Tidak ada commit dan tidak ada push. Satu berkas di luar daftar yang ditugaskan tersentuh, `rtl/afib_lite_pkg.sv`, untuk tiga konstanta yang diminta lantang di butir 1 bagian 5.





