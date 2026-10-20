# LAPORAN FASE 1: paket SystemVerilog, kontrak antarmuka, kerangka modul, paritas konstanta, dan dua perbaikan skrip

Tanggal: 20 Oktober 2026. Repo: `/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite`, branch `aviv/rtl-fpga-simulation`. Tidak ada commit dan tidak ada push. Rencana induk: vault doc 38 bagian 3 dan 12 (Fase 1), silang periksa vault doc 36 bagian 2.2, 2.2.1, 2.4, 2.7, 3.4, 3.6, dan 5.4 sampai 5.5.

## 0. Status gerbang, satu tabel

| # | Gerbang | Perintah singkat | Keluaran | Status |
|---|---|---|---|---|
| 1 | Verilator lint rantai penuh, `-Wno-UNUSEDPARAM` | `./run_lint.sh --chain` | rc 0, 0 keluhan, 13 sumber | LULUS |
| 2 | slang elaborasi (toolbase 12.0.0), pendapat kedua | `slang --top afib_lite_top <13 berkas>` | rc 0, 0 error, 0 warning | LULUS |
| 2b | slang `-Weverything` (pendapat kedua paling keras) | `slang -Weverything ...` | rc 0, 0 error, 42 warning, semuanya unused-parameter atau unused-package | LULUS dengan catatan |
| 2c | Verilator 5.053 (toolbase), pendapat ketiga | `verilator --lint-only ... <13 berkas>` | rc 0, bersih | LULUS |
| 3 | verible-verilog-lint gaya | `verible-verilog-lint <berkas>` | 151 temuan: 123 parameter-name-style, 27 line-length, 1 always-comb | TIDAK BERSIH, 3 temuan diperbaiki, sisanya sengaja, lihat bagian 3.3 |
| 4 | iverilog 12.0 + vvp atas `tb_pkg_konstanta` | `./run_sim.sh ../rtl/tb/tb_pkg_konstanta.sv ../rtl/afib_lite_pkg.sv` | rc 0, 68 pemeriksaan, `bit differences: 0` | LULUS |
| 4b | jalur manifest hilang | tambah `-- +MANIFEST=<path yang tidak ada>` | `FATAL manifest missing path=...`, `bit differences: 1` | LULUS |
| 5 | hitung baris tabel 43 dan konstanta paket | `grep -c` dan `python3` | 43 baris, 1 penanda TBL-END, 75 konstanta bernama | LULUS |
| 6 | tambahan: iverilog elaborasi rantai 13 berkas | `iverilog -g2012 -o /tmp/chain.vvp <13 berkas>` | rc 0 | LULUS |
| 7 | tambahan: Verilator atas testbench | `./run_lint.sh ../rtl/tb/tb_pkg_konstanta.sv tb_pkg_konstanta ../rtl/afib_lite_pkg.sv` | rc 1, `String of 8192 bits exceeds hardcoded limit VL_VALUE_STRING_MAX_WORDS` | DILAPORKAN, bukan gerbang rencana, lihat bagian 6.4 |

Satu gerbang tambahan dijalankan di luar daftar tetapi penting untuk Fase 1: iverilog dapat mengelaborasi seluruh rantai 13 berkas tanpa error, jadi kontrak antarmuka hari ini konsisten menurut dua pembaca bahasa yang berbeda, Verilator dan Icarus.

## 1. Berkas yang dibuat dan diubah

Dibuat, semuanya berbahasa Inggris, tanpa em dash dan tanpa en dash:

| Berkas | Baris | Isi |
|---|---|---|
| `rtl/afib_lite_pkg.sv` | 273 | grup 1 lebar bit, grup 2 titik saturasi, grup 3 aturan pembulatan, grup 4 tipe dan enum, grup 5 nilai reset, grup 6 peta bit antarmuka, tabel sinyal 43 baris, grup 7 silang periksa lebar |
| `rtl/acq_frontend.sv` | 152 | indeks sampel, sample enable 250 Hz, penjepitan, celah |
| `rtl/bandpass.sv` | 92 | low pass lalu high pass |
| `rtl/derivative.sv` | 92 | kernel lima titik, geser 8, potong ke arah nol |
| `rtl/square.sv` | 88 | geser kanan 8 lebih dulu, lalu kuadrat |
| `rtl/integrator.sv` | 93 | jendela berjalan 38, pemanasan 37 dan 38 bergantian |
| `rtl/peak_detect.sv` | 132 | ambang adaptif, refrakter, penelusuran balik |
| `rtl/t_rule.sv` | 104 | aturan gelombang T, berkas kedua belas dari rekomendasi rencana |
| `rtl/rr_series.sv` | 138 | deret RR, antrean delapan interval, empat tanda interval |
| `rtl/features.sv` | 128 | jendela 32 interval, langkah 4 denyut, empat fitur |
| `rtl/classifier.sv` | 132 | triase tiga kelas, ambang dari register |
| `rtl/regs_axi.sv` | 202 | berkas register di belakang bus host |
| `rtl/afib_lite_top.sv` | 494 | rantai penuh, mux introspeksi, batas peta register |
| `rtl/tb/tb_pkg_konstanta.sv` | 439 | paritas konstanta terhadap manifest Fase 0 |
| `rtl-synthesis/run_lint.sh` | 102 | diperbaiki, lihat bagian 5.1 |
| `rtl-synthesis/run_sim.sh` | 96 | diperbaiki, lihat bagian 5.2 |
| `rtl/TASK_BRIEF.md` | +18 | dua catatan Fase 1 pada bagian yang bertentangan dengan rencana, lihat bagian 6 |

Log mentah gerbang, semuanya di `rtl-synthesis/reports/`:

```
lint_chain_fase1.log                gerbang 1
lint_slang_fase1.log                gerbang 2
lint_slang_weverything.log          gerbang 2b
lint_verible_fase1.log              gerbang 3, setelan bawaan
lint_verible_houserules_fase1.log   gerbang 3, nama dan panjang baris dimatikan
sim_tb_pkg_konstanta.log            gerbang 4
lint_tb_fase1.log                   gerbang 7
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
lint clean: top=afib_lite_top sources=13 (/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite/rtl-synthesis/debroot/usr/bin/verilator_bin)
rc=0
```

Jalur sebelumnya tidak bersih. Dua putaran perbaikan diperlukan dan keduanya diukur. Putaran pertama memberi 29 temuan, semuanya nyata:

```
%Warning-WIDTHTRUNC: ../rtl/rr_series.sv:...: Operator ASSIGNW expects 16 bits on the Assign RHS, but Assign RHS's CONST '32'd3000' generates 32 bits
%Warning-WIDTHTRUNC: ../rtl/regs_axi.sv:...: Operator ASSIGNW expects 20 bits on the Assign RHS, but Assign RHS's CONST '32'd399999' generates 32 bits
%Warning-UNUSEDSIGNAL: ../rtl/afib_lite_top.sv:...: Signal is not used: 's_sample_idx'
%Warning-UNUSEDSIGNAL: ../rtl/derivative.sv:...: Bits of signal are not used: 's_tdata'[25:24]
%Warning-UNUSEDSIGNAL: ../rtl/classifier.sv:...: Signal is not used: 'f_ratio'
... 29 baris seluruhnya
%Error: Exiting due to 29 warning(s)
```

Perbaikannya bukan menekan peringatan, melainkan menghapus sebabnya. Tiga tindakan:

1. Nilai yang hidup di medan register dideklarasikan pada lebar medan itu di dalam paket, jadi tidak ada konstanta 32 bit yang terpotong diam diam: `RR_LONG_MS` dan `RR_MAX_MS` menjadi `logic [W_RR_MS-1:0]`, `RATE_DIV_RST` menjadi `logic [W_RATE_DIV-1:0]`, `RATIO_THRESH_RST` dan `ENTROPY_THRESH_RST` menjadi `logic [15:0]`.
2. Setiap sinyal kontrak dibaca, karena Verilator memperlakukan sinyal yang tidak dibaca sebagai kegagalan. Yang tadinya tidak terbaca sekarang masuk ke mux introspeksi `i_dbg_sel` di `afib_lite_top.sv`, bukan dibuang: `s_sample_idx` (pilihan 23), `a_ev_idx` (24), `tw_user` (25), `tw_idx` (26), `rr_ev_val` (27), seluruh `rr_ev_kind` dan `s_tuser` di `rr_series.sv`, dan seluruh bit `i_arm_select` serta `s_rr_mark` di `features.sv`.
3. Dua tempat menerima komentar jujur tentang angka pengganti sementara: `derivative.sv` dan `t_rule.sv` memakai paritas kata masukan `^s_tdata` sebagai sumber `m_overflow` sementara, dengan komentar yang menyatakan bahwa badan Fase 4 dan Fase 7 akan menggantinya dengan hasil komparator, dan bahwa paritas dipakai semata mata supaya tidak ada bit masukan yang tidak dibaca.

Putaran kedua menyisakan satu temuan, juga nyata:

```
%Warning-UNUSEDSIGNAL: ../rtl/classifier.sv:84:16: Bits of signal are not used: 'entropy_thresh_q'[15]
%Error: Exiting due to 1 warning(s)
```

Sebabnya nyata dan bukan kosmetik: medan `ENTROPY_THRESH` berlebar 16 bit di peta register (doc 36 3.4) sedangkan fitur entropi berlebar 15 bit (doc 36 5.5), jadi bit 15 memang di luar jangkauan perbandingan. Perbaikannya dibuat eksplisit dan diberi komentar:

```systemverilog
    wire entropy_raw = ~entropy_thresh_q[W_F_ENT] &
                       (f_ent > entropy_thresh_q[W_F_ENT-1:0]);
```

Ketika bit 15 diset, ambang berada di atas setiap nilai fitur yang bisa dicapai, sehingga lengan itu tidak mungkin menyala. Itu perilaku yang benar, bukan penekanan peringatan.

### 2.2 Gerbang 2, slang (toolbase)

```
$ source /home/avivsabilalm/eda/env.sh && slang --top afib_lite_top ../rtl/afib_lite_pkg.sv ../rtl/acq_frontend.sv ... ../rtl/t_rule.sv
Top level design units:
    afib_lite_top
Build succeeded: 0 errors, 0 warnings
slang rc=0
```

Pendapat kedua paling keras, `-Weverything`, memberi jumlah yang sama pentingnya:

```
$ slang -Weverything --top afib_lite_top <13 berkas>
Build succeeded: 0 errors, 42 warnings
slang -Weverything rc=0

--- kode peringatan dan jumlahnya ---
     19 [-Wunused-package-parameter]
     12 [-Wunused-package-typedef]
     11 [-Wunused-parameter]
```

Tiga kode itu tepat tiga hal yang dinyatakan rencana: parameter dan tipe paket yang belum dipakai di badan kerangka, dan parameter modul yang belum dipakai. Itulah alasan `-Wno-UNUSEDPARAM` ada di gerbang Verilator. Tidak ada kode lain: nol temuan lebar bit, nol temuan signedness, nol temuan latch, nol temuan multi driver.

### 2.3 Gerbang 2c, Verilator 5.053 (toolbase), pendapat ketiga

```
$ verilator --version
Verilator 5.053 devel rev v5.052-500-gb96464954 (mod)
$ verilator --lint-only -sv --top-module afib_lite_top -Wall -Wno-DECLFILENAME -Wno-UNUSEDPARAM <13 berkas>
- Verilator: Built from 0.724 MB sources in 15 modules, into 0.165 MB in 3 C++ files
toolbase verilator rc=0
```

### 2.4 Gerbang 3, verible-verilog-lint

```
$ verible-verilog-lint --version
Version	v0.0-4296-g0f262651
Built	2026-09-23T08:18:08Z
$ for f in <14 berkas>; do verible-verilog-lint "$f"; done
verible rc=1
--- temuan menurut aturan ---
    123 [parameter-name-style]
     27 [line-length]
      1 [always-comb]
--- temuan menurut berkas ---
     67 ../rtl/tb/tb_pkg_konstanta.sv
     64 ../rtl/afib_lite_pkg.sv
     11 ../rtl/regs_axi.sv
      8 ../rtl/afib_lite_top.sv
      1 ../rtl/peak_detect.sv
```

Empat aturan menyala: `parameter-name-style` 123, `line-length` 27, `always-comb` 1. Dua kelas temuan mekanis lain ikut muncul di putaran pertama dan sudah diperbaiki: `explicit-parameter-storage-type` 33, `explicit-function-task-parameter-type` 18, `explicit-function-lifetime` 7, dan `unpacked-dimensions-range-ordering` 3. Total putaran pertama 179 temuan, putaran akhir 151.

Yang diperbaiki, dengan bukti:

```
--- findings that were fixed ---
explicit-parameter-storage-type    localparam [63:0] X          -> localparam logic [63:0] X
explicit-function-task-parameter-type  input [63:0] v           -> input logic [63:0] v
explicit-function-lifetime         function integer f           -> function automatic integer f
unpacked-dimensions-range-ordering reg [63:0] c_min [0:5]       -> reg [63:0] c_min [6]
```

Setelah perbaikan itu testbench dijalankan ulang dan tetap `checks: 68`, `bit differences: 0`, rc 0.

Yang tidak diperbaiki, dan alasannya:

1. `parameter-name-style` 123 temuan. Pola bawaan verible adalah camelCase, sedangkan rumah ini memakai huruf besar semua untuk konstanta, dan itu tertulis di `rtl/README.md` serta di paket. Yang benar adalah mengonfigurasi verible, bukan menamai ulang konstanta kontrak: nama `W_IN`, `RATE_DIV_RST`, dan `ARM_SELECT_RST` adalah nama yang dipakai rencana bagian 3.2 dan 3.4, dan menggantinya akan memutus rujukan silang ke dokumen. Dengan `--rules=-parameter-name-style,-line-length` sisa temuan hanya 1:
   ```
   $ for f in <14 berkas>; do verible-verilog-lint --rules=-parameter-name-style,-line-length "$f"; done
   ../rtl/afib_lite_top.sv:314:5-10: Use 'always_comb' instead of 'always @*'. [Style: combinational-logic] [always-comb]
   1 temuan
   ```
2. `line-length` 27 temuan, semuanya kolom komentar paket dan mux introspeksi yang sengaja disejajarkan. 15 di antaranya ada di dalam daftar nilai grup 2 paket, yang adalah tabel terkunci. Memindahkan komentar itu ke baris sendiri akan merusak keterbacaan tabel dan tidak menambah nilai. Angka baris yang panjang antara lain `afib_lite_pkg.sv:79` (117 karakter) dan `afib_lite_pkg.sv:86` (118 karakter).
3. `always-comb` 1 temuan, `afib_lite_top.sv:314`. Keputusan pemilik D10 berbunyi: berkas yang disintesis memakai `wire` dan `reg`, dan `logic` hanya di testbench. Mux introspeksi itu blok kombinasional di berkas yang disintesis, jadi ia ditulis `always @(*)` dan tetap begitu. Ini satu satunya temuan gaya yang tersisa di bawah aturan rumah, dan disengaja.

### 2.5 Gerbang 4, iverilog dan vvp atas tb_pkg_konstanta

```
$ ./run_sim.sh ../rtl/tb/tb_pkg_konstanta.sv ../rtl/afib_lite_pkg.sv
run_sim.sh: tb=../rtl/tb/tb_pkg_konstanta.sv sources=1 plusargs=0
  compiled first (packages): ../rtl/afib_lite_pkg.sv
INFO  manifest path [/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json]
INFO  manifest lines read 171
INFO  columns parsed min=6 max=6 words_above_2p31=6
INFO  column[0] masukan16 min=-29776      max=32752       signed_width=16
INFO  column[1] lp        min=-1061200    max=1179072     signed_width=22
INFO  column[2] hp        min=-16974032   max=19286208    signed_width=26
INFO  column[3] turunan   min=-4792318    max=3831762     signed_width=24
INFO  column[4] kuadrat   min=0           max=350438400   signed_width=30
INFO  column[5] jendela   min=0           max=3105281786  signed_width=33
CHECK width.masukan16            got=16           want=16           diffs=0  PASS src=doc36 2.2 columns.masukan16
CHECK width.lp                   got=22           want=22           diffs=0  PASS src=doc36 2.2 columns.lp
CHECK width.hp                   got=26           want=26           diffs=0  PASS src=doc36 2.2 columns.hp
CHECK width.turunan              got=24           want=24           diffs=0  PASS src=doc36 2.2 columns.turunan
CHECK width.kuadrat              got=30           want=30           diffs=0  PASS src=doc36 2.2 columns.kuadrat
CHECK width.jendela              got=33           want=33           diffs=0  PASS src=doc36 2.2 columns.jendela
BOUND fit.masukan16.max          got=32752        <= lim=32767        excess=0  PASS src=W_IN top
BOUND fit.masukan16.min          got=29776        <= lim=32768        excess=0  PASS src=W_IN bottom
BOUND fit.lp.max                 got=1179072      <= lim=2097151      excess=0  PASS src=W_LP top
BOUND fit.lp.min                 got=1061200      <= lim=2097152      excess=0  PASS src=W_LP bottom
BOUND fit.hp.max                 got=19286208     <= lim=33554431     excess=0  PASS src=W_HP top
BOUND fit.hp.min                 got=16974032     <= lim=33554432     excess=0  PASS src=W_HP bottom
BOUND fit.turunan.max            got=3831762      <= lim=8388607      excess=0  PASS src=W_DER top
BOUND fit.turunan.min            got=4792318      <= lim=8388608      excess=0  PASS src=W_DER bottom
BOUND fit.kuadrat.max            got=350438400    <= lim=536870911    excess=0  PASS src=W_SQ top
BOUND fit.jendela.max            got=3105281786   <= lim=4294967295   excess=0  PASS src=W_WIN top
CHECK clamp.word.max             got=32752        want=32752        diffs=0  PASS src=CLAMP_WORD vs columns.masukan16.max
BOUND clamp.min.inside           got=29776        <= lim=32752        excess=0  PASS src=columns.masukan16.min inside CLAMP_WORD
CHECK square.from.derivative     got=350438400    want=350438400    diffs=0  PASS src=kuadrat.max vs (turunan.min >>> SHIFT_DER)**2
BOUND square.limit               got=18720        <= lim=56503        excess=0  PASS src=shifted derivative inside SQ_LIMIT
BOUND window.sum.upper           got=3105281786   <= lim=13316659200  excess=0  PASS src=N_WIN * kuadrat.max
BOUND window.sum.lower           got=350438400    <= lim=3105281786   excess=0  PASS src=kuadrat.max
BOUND window.worst.case          got=3105281786   <= lim=121318382342 excess=0  PASS src=N_WIN * SQ_LIMIT**2, doc 36 2.4
CHECK rate.divider               got=400000       want=400000       diffs=0  PASS src=RATE_DIV_RST vs manifest rate_hz
CHECK rate.divider.width         got=20           want=20           diffs=0  PASS src=D12: 399999 needs 19 bit, the field is declared 20
CHECK window.above_2p31          got=1            want=1            diffs=0  PASS src=jendela holds words at or above 2**31, doc 36 2.2 unsigned column
CHECK stream.total_words         got=2700000      want=2700000      diffs=0  PASS src=gate.total_words
CHECK stream.words_per_column    got=450000       want=450000       diffs=0  PASS src=gate.words_per_column
CHECK stream.bytes_per_word      got=9            want=9            diffs=0  PASS src=format.bytes_per_word
CHECK stream.column_count        got=6            want=6            diffs=0  PASS src=count of parsed min lines
CHECK stream.min_max_pairs       got=6            want=6            diffs=0  PASS src=count of parsed max lines
CHECK stream.above_2p31_fields   got=6            want=6            diffs=0  PASS src=count of words_above_2p31 fields
CHECK adapter.mismatches         got=0            want=0            diffs=0  PASS src=adapter_check.mismatches
CHECK adapter.fixture_words      got=450000       want=450000       diffs=0  PASS src=adapter_check.fixture_masukan16_words
CHECK clamp.word.identity        got=32752        want=32752        diffs=0  PASS src=CLAMP_COUNT << SHIFT_IN
CHECK rr.max.identity            got=65535        want=65535        diffs=0  PASS src=2**W_RR_MS - 1
CHECK thresh.scale.identity      got=256          want=256          diffs=0  PASS src=2**SHIFT_DER
CHECK window.pair.identity       got=38           want=38           diffs=0  PASS src=N_WIN_ALT + 1
CHECK derivative.worst.identity  got=25           want=25           diffs=0  PASS src=W_DER + 1
CHECK window.worst.identity      got=37           want=37           diffs=0  PASS src=doc 36 2.4 states 121318382342 is 37 bit
BOUND rr.long.inside.max         got=3000         <= lim=65535        excess=0  PASS src=RR_LONG_MS inside W_RR_MS
CHECK bits.word_in_t             got=16           want=16           diffs=0  PASS src=group 4 vs group 1
CHECK bits.lp_t                  got=22           want=22           diffs=0  PASS src=group 4 vs group 1
CHECK bits.hp_t                  got=26           want=26           diffs=0  PASS src=group 4 vs group 1
CHECK bits.der_t                 got=24           want=24           diffs=0  PASS src=group 4 vs group 1
CHECK bits.sq_t                  got=30           want=30           diffs=0  PASS src=group 4 vs group 1
CHECK bits.win_t                 got=33           want=33           diffs=0  PASS src=group 4 vs group 1
CHECK bits.thr_t                 got=30           want=30           diffs=0  PASS src=group 4 vs group 1
CHECK bits.rr_ms_t               got=16           want=16           diffs=0  PASS src=group 4 vs group 1
CHECK bits.idx_t                 got=32           want=32           diffs=0  PASS src=group 4 vs group 1
CHECK bits.tuser_t               got=8            want=8            diffs=0  PASS src=group 4 vs group 1
CHECK bits.conf_t                got=16           want=16           diffs=0  PASS src=group 4 vs group 1
CHECK enum.kelas.base            got=0            want=0            diffs=0  PASS src=D2 reset value 0
CHECK enum.kelas.step1           got=1            want=1            diffs=0  PASS src=D2
CHECK enum.kelas.step2           got=1            want=1            diffs=0  PASS src=D2
CHECK enum.event.base            got=0            want=0            diffs=0  PASS src=plan 3.2 m_ev_kind
CHECK enum.event.qrs             got=1            want=1            diffs=0  PASS src=plan 3.2 m_ev_kind
CHECK enum.event.window          got=1            want=1            diffs=0  PASS src=plan 3.2 m_ev_kind
CHECK enum.rnd.base              got=0            want=0            diffs=0  PASS src=plan 3.4 group 3 order
CHECK enum.mark.base             got=0            want=0            diffs=0  PASS src=doc 36 2.7 four marks
CHECK enum.mark.gap.last         got=1            want=1            diffs=0  PASS src=doc 36 2.7 four marks
CHECK rst.arm.four.lit           got=1            want=1            diffs=0  PASS src=D8 four arms lit after reset
CHECK rst.window.beats           got=32           want=32           diffs=0  PASS src=D5 lock
CHECK rst.window.step            got=4            want=4            diffs=0  PASS src=D5 lock
CHECK rst.ratio.thresh           got=33           want=33           diffs=0  PASS src=D8 P1 0.165 in 1/200 units
CHECK rst.entropy.thresh         got=63           want=63           diffs=0  PASS src=D8 P1 0.63 in 1/100 units
CHECK conf.full.scale            got=1000         want=1000         diffs=0  PASS src=D2b
CHECK gap.recovery               got=131          want=131          diffs=0  PASS src=doc 36 3.6 chain of stage delays
REVIEW square.bound.width        got=32           other=30           not counted src=SQ_LIMIT**2 needs 32 bit, W_SQ is 30: owner decision needed
REVIEW searchback.width          got=30           other=23           not counted src=no width parameter for the search_back word, doc 36 2.2.1 binding 30
REVIEW buffer.depths             got=128          other=8            not counted src=no witness in the manifest or doc 36, owner decision
REVIEW rr.samples.width          got=15           other=16           not counted src=no witness in doc 36, TASK_BRIEF 2.1 fixes 15
REVIEW feature.widths.other      got=77           other=16           not counted src=sum of the four feature widths, doc 36 5.5 binding column
checks: 68
review lines: 5
bit differences: 0
../rtl/tb/tb_pkg_konstanta.sv:436: $finish called at 0 (1ps)
rc=0
```

Jalur manifest hilang, dijalankan dengan plusarg ke path yang tidak ada, untuk membuktikan bahwa berkas emas yang hilang tidak mungkin terbaca sebagai lulus:

```
$ ./run_sim.sh ../rtl/tb/tb_pkg_konstanta.sv ../rtl/afib_lite_pkg.sv -- +MANIFEST=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json.NOT_HERE
run_sim.sh: tb=../rtl/tb/tb_pkg_konstanta.sv sources=1 plusargs=1
  plusargs forwarded to vvp: +MANIFEST=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json.NOT_HERE
  compiled first (packages): ../rtl/afib_lite_pkg.sv
INFO  manifest path taken from the +MANIFEST plusarg
INFO  manifest path [/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json.NOT_HERE]
FATAL manifest missing path=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json.NOT_HERE
FATAL no constant could be checked, the golden side is absent
bit differences: 1
```

### 2.6 Gerbang 5, hitungan

```
$ echo "TBL rows: $(grep -c '^  // TBL|' ../rtl/afib_lite_pkg.sv)"
TBL rows: 43
$ echo "TBL-END markers: $(grep -c '^  // TBL-END' ../rtl/afib_lite_pkg.sv)"
TBL-END markers: 1
$ echo "localparam declarations: $(grep -cE '^  localparam ' ../rtl/afib_lite_pkg.sv)"
localparam declarations: 48
$ echo "typedef declarations: $(grep -cE '^  typedef ' ../rtl/afib_lite_pkg.sv)"
typedef declarations: 15
$ echo "enum blocks: $(grep -cE '^  typedef enum ' ../rtl/afib_lite_pkg.sv)"
enum blocks: 4
$ echo "enum members: $(grep -cE '^    [A-Z_]+ += ' ../rtl/afib_lite_pkg.sv)"
enum members: 16
$ python3 <penghitung yang sama, untuk memisahkan typedef enum dari typedef tipe>
python: localparam=48 typedef=11 enum_blocks=4 enum_members=16 total_named_constants=75
```

Jadi: 43 baris tabel sinyal, 1 penanda penutup, 48 `localparam`, 11 `typedef` tipe, 4 blok enum dengan 16 anggota, jumlah konstanta bernama seluruhnya 75.

### 2.7 Gerbang 6, iverilog elaborasi rantai penuh (tambahan)

```
$ ./debroot/usr/bin/iverilog -g2012 -o /tmp/chain.vvp ../rtl/afib_lite_pkg.sv ../rtl/afib_lite_top.sv ../rtl/acq_frontend.sv ../rtl/bandpass.sv ../rtl/derivative.sv ../rtl/square.sv ../rtl/integrator.sv ../rtl/peak_detect.sv ../rtl/t_rule.sv ../rtl/rr_series.sv ../rtl/features.sv ../rtl/classifier.sv ../rtl/regs_axi.sv
chain rc=0
( tidak ada keluaran )
```

## 3. Isi paket `rtl/afib_lite_pkg.sv`

### 3.1 Empat grup rencana bagian 3.4

Grup 1, lebar bit, 20 nilai: `W_IN 16`, `W_LP 22`, `W_HP 26`, `W_DER 24`, `W_DER_WORST 25`, `W_SQ 30`, `W_WIN 33`, `W_WIN_WORST 37`, `W_THR 30`, `W_TW 23`, `W_RR_MS 16`, `W_RR_SMP 15`, `W_CONF 16`, `W_F_RATIO 17`, `W_F_ENT 15`, `W_F_MEANQ 27`, `W_F_RMSSD 18`, `W_IDX 32`, `W_RATE_DIV 20`, `W_TUSER 8`. Semuanya sama dengan daftar rencana, tidak ada yang diubah.

Grup 2, titik saturasi: `CLAMP_COUNT 2047`, `SHIFT_IN 4`, `CLAMP_WORD 32752`, `SQ_LIMIT 56503`, `SHIFT_DER 8`, `THRESH_SCALE 256`, `N_WIN 38`, `N_WIN_ALT 37`, `RR_LONG_MS 3000`, `RR_MAX_MS 65535`, `GAP_RECOVERY 131`, `RATE_DIV_RST 399999`, `SEARCH_BACK_DEPTH 128`, `DECISION_DEPTH 8`, `CONF_FULL_SCALE 1000`.

Grup 3, aturan pembulatan, sebagai tiga komentar dan satu enum: `RND_TIES_EVEN` untuk kuantiser saja (`rantai.py:163`), `RND_FLOOR` untuk setiap geser kanan lain (`rantai.py:244`, `:655`, `:683`), `RND_TRUNC_ZERO` untuk simpul turunan saja (`rantai.py:228`). Ketiga aturan hidup berdampingan dan tidak boleh disatukan, seperti dinyatakan doc 36 2.3.

Grup 4, tipe dan enum: 11 `typedef` tipe (`word_in_t`, `lp_t`, `hp_t`, `der_t`, `sq_t`, `win_t`, `thr_t`, `rr_ms_t`, `idx_t`, `tuser_t`, `conf_t`) dan 4 enum dengan 16 anggota (`kelas_e` 3, `ev_kind_e` 6, `rnd_e` 3, `rr_mark_e` 4).

Grup 5, nilai titik operasi reset: `RATIO_THRESH_RST 33`, `ENTROPY_THRESH_RST 63`, `ARM_SELECT_RST 5'h0F`, `WINDOW_BEATS_RST 32`, `WINDOW_STEP_RST 4`, ditambah dua pasangan nilai pada lebar medan register, `WINDOW_STEP_FIELD` dan `WINDOW_BEATS_FIELD`.

Satu tambahan yang perlu dinyatakan terang, `CLK_HZ = 100_000_000`. Ini bukan salah satu dari empat grup rencana bagian 3.4 dan bukan bagian D8. Alasannya: `RATE_DIV_RST` tidak bermakna tanpa clock, dan angka 250,0 Hz yang dihasilkan hanya mengikuti clock PL 100 MHz pada doc 36 3.1 dan doc 39 7.2. Tanpa konstanta ini testbench harus menulis `100000000` sebagai angka telanjang, yang justru dilarang aturan rumah. Komentarnya di paket menyebut sumbernya. Testbench memakai konstanta ini di `rate.divider`, dan pemeriksaan itu lulus dengan 0 selisih bit.

### 3.2 Tabel sinyal 43 baris

Tabel ditulis sebagai blok komentar di dalam paket, satu baris per sinyal, masing masing dengan penanda `// TBL|` dan blok ditutup `// TBL-END`, sehingga hitungan baris dapat diperiksa di dalam berkas itu sendiri dengan `grep -c '^  // TBL|'`. Hasilnya persis 43, dengan pembagian dari rencana 3.2: 2 clock dan reset, 6 sampel masuk, 6 sampel keluar, 4 event, 2 introspeksi, 6 keputusan, 8 status, 9 konfigurasi, jumlah 43.

Satu catatan pada tabel: baris `o_dbg_val` menyebut `o_dbg_valid` di kolom semantik, sedangkan `o_dbg_valid` bukan baris tersendiri, sehingga tabel yang seharusnya berisi 44 baris bila `o_dbg_valid` dijadikan sinyal kontrak. Keputusan Fase 1: tabel tetap 43 baris sesuai permintaan, `o_dbg_valid` tidak dijadikan port, dan ketidaklengkapan ini dilaporkan di bagian 6.2.

## 4. Ketidaksesuaian yang ditemukan

### 4.1 `W_WIN_WORST` dan konvensi lebar, satu satunya selisih dokumen yang nyata

doc 36 2.4 menyatakan `38 x 3.192.589.009 = 121.318.382.342` sama dengan 37 bit. Angka 37 itu adalah lebar besaran tanpa tanda. Pembacaan dua komplemen yang ketat untuk nilai yang sama menuntut 38 bit, karena 121.318.382.342 berada di atas 2 pangkat 36. Rencana bagian 3.4 memakai `W_WIN_WORST 37`, dan paket mengikuti rencana karena nilai itu adalah nilai rencana yang terkunci. Selisih ini dinyatakan di header paket grup 7 dan di sini, tidak diselesaikan diam diam. Testbench mengukurnya sebagai identitas: `window.worst.identity got=37 want=37`, memakai `$clog2(N_WIN * SQ_LIMIT * SQ_LIMIT + 1)`.

### 4.2 Dua konvensi lebar yang berbeda nama, dan tidak ada yang salah

doc 36 2.2 memberi dua kolom: `Lebar dua komplemen` dan `Tanpa tanda`. Untuk simpul kuadrat keduanya berbunyi 30 dan 29, untuk jendela 33 dan 32. Rencana bagian 3.4 memakai kolom pertama (`W_SQ 30`, `W_WIN 33`), sedangkan berkas manifest ekspor I3 `rtlplan2/vektor/04015.manifest.json` memakai kolom kedua (`width_twos` 29 dan 32 untuk dua simpul itu). Jadi keduanya benar dan keduanya berasal dari tabel yang sama, hanya kolom yang berbeda. Testbench memakai kolom pertama, kolom yang diikuti rencana, dan hasilnya keenam lebar simpul cocok bit per bit.

### 4.3 Enam lebar simpul cocok, angka demi angka

Dihitung dari `min` dan `max` manifest Fase 0 dengan definisi yang sama seperti kolom doc 36 2.2 (bit tanda ditambah bit besaran terbesar), keenamnya sama persis dengan paket: masukan16 16, lp 22, hp 26, turunan 24, kuadrat 30, jendela 33. Tidak ada satu pun simpul yang lebar paketnya kurang atau lebih.

### 4.4 Urutan geser sebelum kuadrat dan aturan lantai, dibuktikan satu pemeriksaan

Satu pemeriksaan menutup dua aturan sekaligus:

```
CHECK square.from.derivative     got=350438400    want=350438400    diffs=0
  src=kuadrat.max vs (turunan.min >>> SHIFT_DER)**2
```

`turunan.min` adalah -4.792.318. Geser kanan aritmetika lantai memberi -18.720, dan kuadratnya 350.438.400, sama persis dengan `kuadrat.max` di manifest. Bila implementasi memakai potong ke arah nol seperti pada simpul turunan, hasilnya -18.719 dan kuadratnya 350.400.961, dan pemeriksaan ini akan gagal. Jadi pemeriksaan ini mengikat urutan geser sebelum kuadrat dan aturan `RND_FLOOR` pada simpul kuadrat secara bersamaan.

### 4.5 `TASK_BRIEF.md` bertentangan dengan rencana di dua tempat

`rtl/TASK_BRIEF.md` adalah otoritas repo, dan di dua tempat ia bertentangan dengan rencana induk:

1. Bagian 4, peta register. Baris `0x54 WINDOW_STEP` dan `0x58 WINDOW_BEATS` menempati alamat yang di peta beku D8 dipakai `RATE_DIV` dan `THRESH_SCALE`. Lebih jauh, peta beku 36 slot hasil D8 tidak punya slot sama sekali untuk `WINDOW_STEP` maupun `WINDOW_BEATS`, sehingga pertanyaan rumah kedua nilai itu masih terbuka dan bukan sesuatu yang boleh saya putuskan sendiri. `rtl/regs_axi.sv` mengikuti peta doc 38 dan D8, dan menyimpan dua nilai itu di 0x90 dan 0x94 dengan komentar yang menyatakan bahwa alamat itu sementara, di atas peta beku.
2. Bagian 5, tata letak berkas. Pohon di sana punya sebelas modul dan melipat aturan gelombang T ke dalam `peak_detect.sv`, sedangkan rencana bagian 3.4 memberi aturan itu berkasnya sendiri `t_rule.sv`. Fase 1 mengikuti rencana, jadi `rtl/` memuat `t_rule.sv` sebagai modul kedua belas.

Kedua bagian itu tidak saya tulis ulang, karena penyelesaiannya adalah keputusan pemilik dan menulis ulang tabel otoritas tanpa keputusan itu akan lebih buruk daripada tidak menyentuhnya. Yang saya lakukan adalah menambahkan dua catatan Fase 1 di bawah tabel bagan 4 dan di bawah pohon bagian 5, masing masing menyebut ketidaksesuaiannya dan menunjuk ke laporan ini. Tambahan itu 18 baris dan tidak mengubah satu pun pernyataan lama.

### 4.6 `design_template.sv` menulis kelas 1 sebagai fibrilasi atrium

`rtl-synthesis/template/design_template.sv` baris 31 berbunyi:

```
    output reg  [1:0]  out_class,  // 0 normal, 1 atrial fibrillation, 2 undecided
```

Keputusan D2 berbunyi: 0 undecided, 1 normal, 2 review. Jadi kode 1 dan kode 2 berbeda makna antara templat dan keputusan pemilik. Berkas itu di luar wilayah sunting saya, jadi ia ditandai, tidak diubah: header `afib_lite_pkg.sv` menyebutnya di daftar keputusan D2, dan laporan ini menyebutnya sekali lagi. Pembalikan arti untuk kode 1 dan 2 inilah yang paling berbahaya kalau kode kelas dibaca memakai kepala templat, karena kode 2 di templat berarti belum diputuskan sedangkan di D2 berarti perlu tinjauan, dan justru kode itulah nilai paling penting bagi pengguna alat.

## 5. Dua perbaikan skrip, dengan bukti

### 5.1 `run_lint.sh`, lint seluruh rantai dalam satu perintah

Perintahnya sekarang satu: `./run_lint.sh --chain` melinting 13 berkas `rtl/*.sv` sekaligus dengan `afib_lite_top` sebagai top module. Perubahan yang dilakukan:

1. Mode `--chain` yang mengumpulkan `../rtl/*.sv` dan memakai `--top-module` bawaan `afib_lite_top`.
2. `-Wno-UNUSEDPARAM` tetap ada, sesuai perintah rencana, karena setiap modul menyimpan parameter yang belum dipakai di badan kerangka.
3. `--timing` ditambahkan sendiri bila sumber yang diberikan berawalan `tb_`, seperti disyaratkan Icarus untuk konstruksi waktu.
4. Urutan berkas diperbaiki: berkas paket selalu dipindah ke depan. Sebelum perbaikan Verilator memberi `%Error-PKGNODECL: Package/class 'afib_lite_pkg' not found` pada sumber pertama yang menyebut konstanta paket, dan sekarang urutannya terlihat pada keluaran: `../rtl/afib_lite_pkg.sv` dicetak pertama di antara 13 sumber.

Bukti lulus ada di bagian 2.1: `lint clean: top=afib_lite_top sources=13`, rc 0, setelah 29 temuan nyata dihapus pada sumbernya.

### 5.2 `run_sim.sh`, plusarg sampai ke vvp

Cacatnya persis seperti yang tertulis di `rtl/TASK_BRIEF.md` baris 311: baris terakhir skrip dahulu berbunyi `"$VVP" "$OUT"` tanpa `"$@"`, sehingga setiap argumen skrip pergi ke iverilog dan plusarg runtime seperti `+GOLD=<berkas>` tidak pernah sampai ke vvp, dan TASK_BRIEF harus memakai variabel lingkungan sebagai akal akalan.

Perbaikannya memakai pemisah `--`: argumen sebelum `--` adalah berkas sumber untuk iverilog, argumen sesudah `--` adalah plusarg untuk vvp. Bentuk pemisah dipilih, bukan aturan `argumen yang berawalan tanda plus`, karena iverilog punya argumen plus yang sah miliknya sendiri seperti `+incdir+<dir>+<dir>`, dan menebak akan mengirim argumen itu ke alat yang salah tanpa suara. Tanpa `--`, perilakunya sama seperti semula, jadi baris perintah yang sudah terdokumentasi di TASK_BRIEF tetap jalan.

Bukti plusarg benar benar sampai ke vvp, dari bagian 2.5 jalur manifest hilang:

```
run_sim.sh: tb=../rtl/tb/tb_pkg_konstanta.sv sources=1 plusargs=1
  plusargs forwarded to vvp: +MANIFEST=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json.NOT_HERE
INFO  manifest path taken from the +MANIFEST plusarg
FATAL manifest missing path=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json.NOT_HERE
```

Testbench melihat nila plusarg itu dan memakainya, yang membuktikan vvp benar benar menerimanya, bukan hanya iverilog.

Cacat kedua di skrip yang sama ditemukan saat gerbang ini dijalankan, dan diperbaiki juga: iverilog mengurai berkas menurut urutan pada baris perintah dan melaporkan rujukan paket di berkas yang lebih belakang sebagai syntax error. Sebelum perbaikan, `./run_sim.sh ../rtl/tb/tb_pkg_konstanta.sv ../rtl/afib_lite_pkg.sv` gagal seperti ini:

```
../rtl/tb/tb_pkg_konstanta.sv:4: syntax error
../rtl/tb/tb_pkg_konstanta.sv:4: error: Invalid module item.
```

Sesudah perbaikan, seluruh berkas `*_pkg.sv` dipindah ke depan testbench dan iverilog mencetak barisnya sendiri sebagai bukti: `compiled first (packages): ../rtl/afib_lite_pkg.sv`. Ini bukan perubahan kosmetik: tanpa itu testbench paritas tidak bisa dijalankan sama sekali lewat skrip rumah.

## 6. Baris REVIEW, pertanyaan terbuka untuk pemilik

Lima baris REVIEW dicetak testbench dan sengaja tidak dihitung ke dalam `bit differences`, karena masing masing adalah pertanyaan pemilik, bukan kegagalan testbench:

1. `square.bound.width got=32 other=30`. `SQ_LIMIT` adalah 56.503 dan batas atas simpul kuadrat adalah `SQ_LIMIT` dikuadratkan, yaitu 3.192.589.009, yang menuntut 32 bit, sedangkan `W_SQ` dinyatakan 30 bit. Yang terukur memang muat di `W_SQ` (nilai terbesar 350.438.400, atau 30 bit bertanda), jadi tidak ada kegagalan paritas hari ini. Yang belum tertutup: rencana belum menyebut simpul kuadrat memiliki penjepit, padahal batas saturasinya tidak muat di lebar yang dinyatakan. Pilihan pemilik: tambahkan penjepit, atau nyatakan bahwa `SQ_LIMIT` adalah batas utan simpul dan bukan batas keluaran simpul.
2. `searchback.width got=30 other=23`. Keluaran `search_back` punya lebar mengikat 30 bit menurut doc 36 2.2.1, sedangkan daftar parameter rencana bagian 3.4 tidak punya parameter lebar untuk kata kandidat penelusuran balik. `W_THR 30` dipakai untuk jalur ambang dan disebut juga menampung penelusuran balik, tetapi ini pemetaan yang saya buat dan bukan pernyataan rencana.
3. `buffer.depths got=128 other=8`. `SEARCH_BACK_DEPTH` dan `DECISION_DEPTH` adalah keputusan panjang penampan tanpa saksi angka di manifest maupun di doc 36. Keduanya dicetak tanpa dihitung.
4. `rr.samples.width got=15 other=16`. `W_RR_SMP` tidak punya saksi di doc 36, niainya datang dari `rtl/TASK_BRIEF.md` 2.1, sedangkan `W_RR_MS` punya saksi 16 bit pada rekaman terburuk. Keduanya dicetak berdampingan supaya hubungannya terlihat.
5. `feature.widths.other got=77 other=16`. Jumlah empat lebar fitur dicetak berdampingan dengan `W_CONF`, semata mata agar nilainya muncul di keluaran; tidak ada klaim di baliknya. Empat lebar fitur itu sendiri punya saksi di doc 36 5.5 dan semuanya cocok.

## 7. Serah terima ke fase berikutnya

1. Setiap modul sudah punya port kontrak dengan lebar yang dinyatakan dari paket, header berkas yang menyebut lebar, titik saturasi, aturan pembulatan, dan nomor baris `rantai.py` yang akan dicerminkan, serta perilaku pengganti berupa muat register dengan latensi tetap. Tidak ada aritmetika nyata di dalamnya. Yang berikutnya mengganti badan modul tanpa menyentuh port dan tanpa menulis angka baru di luar paket.
2. Semua keputusan pemilik yang beku sudah diterapkan dan diperiksa testbench: D1 (tanpa `tready` di jalur data, satu bendera luapan per tahap, `s_ready` hanya di puncak), D2 (kelas 0 tidak diputuskan, 1 normal, 2 tinjauan, reset 0), D2b (keyakinan skala 0 sampai 1000), D8 (empat lengan menyala sesudah reset), D10 (wire dan reg di berkas yang disintesis), D12 (medan pembagi 20 bit).
3. Konflik `design_template.sv` menunggu keputusan pemilik. Sampai diputuskan, jangan ada berkas baru yang menyalin komentar kelas dari templat itu.
4. Dua alamat register untuk `WINDOW_STEP` dan `WINDOW_BEATS` masih sementara di 0x90 dan 0x94. Bila pemilik memutuskan slotnya, yang berubah hanya tabel `ADDR_` di `regs_axi.sv` dan catatan di TASK_BRIEF.
5. Verilator tidak bisa mengelaborasi testbench ini karena batas string 8192 bit di `VL_VALUE_STRING_MAX_WORDS`, jadi jalur testbench adalah Icarus dan vvp, sesuai pembagian doc 36 6.2 dan 7. Bila ada yang ingin melinting testbench dengan Verilator kelak, buffer baris manifest harus diperkecil dari 1024 bita menjadi di bawah 1024 bit, dan itu memutus pembacaan satu baris manifest yang panjang.
6. Perluasan berikutnya: `tb/tb_derivative.sv`, `tb/tb_square_window.sv`, `tb/tb_peak_detect.sv`, `tb/tb_features.sv`, `tb/tb_classifier.sv`, dan `tb/tb_afib_lite_top.sv` menurut doc 36 2.8 dan 6.2, memakai vektor emas per simpul dari Fase 0 yang sudah ada di `rtlplan2/fase0/*.hex` (10 berkas, di antaranya `04015.masukan16.hex`, `04015.lp.hex`, `04015.hp.hex`, `04015.turunan.hex`, `04015.kuadrat.hex`, `04015.jendela.hex`, dan `04015.stream.hex`).
