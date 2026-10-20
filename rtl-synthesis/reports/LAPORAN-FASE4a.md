# LAPORAN FASE 4a -- derivative.sv dan tb_derivative.sv

Tahap pertama Fase 4 dari plan dokumen 38: turunan lima titik. Berkas yang disunting hanya dua,
keduanya milik fase ini: `rtl/derivative.sv` dan `rtl/tb/tb_derivative.sv`. Berkas beku tidak
disentuh dan sidik jarinya dicatat di bawah. Tidak ada `git add`, tidak ada commit.

Waktu kerja: 20 Oktober 2026, 19.55 sampai 20.10 WIB.

## 0. Ringkasan hasil

| # | Gerbang | Hasil |
|---|---|---|
| G1 | `m_tdata` = kolom emas `04015.turunan.hex`, 450.000 kata | **0 beda dari 450.000**, PASS, keluar 0, dua kali jalan |
| G2 | lint Verilator seluruh rantai | **bersih, keluar 0** (13 sumber, `--chain`) |
| G3 | deret sintetis buatan tangan, 45 kata | **0 beda**, PASS (deret yang sama 6 kata beda bila aturan pembulatan diganti lantai) |
| G4 | sel dan flip-flop `derivative.sv` sendiri, SKY130 | **1.348 sel, 274 flip-flop, 11.176,97 um^2** |

Tiga gerbang lulus penuh. Gerbang keempat lulus sebagai angka, tetapi angkanya **1,72 kali batas
atas plan 4.4** (6.481 um^2); dilaporkan di bagian 3, bukan disembunyikan.

## 1. Gerbang G1, paritas bit terhadap kolom emas

Perintah, persis bentuk yang terbukti di repo, tanpa tambahan apa pun:

```
cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite/rtl-synthesis
./run_sim.sh ../rtl/tb/tb_derivative.sv ../rtl/afib_lite_pkg.sv ../rtl/derivative.sv \
  -- +VECTOR=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0
```

Keluaran mentah, `reports/fase4/sim_derivative_full_450000.log` (log larian kedua, sama hasilnya:
`reports/fase4/sim_derivative_full_450000_run2.log`):

```
tb_derivative: vectors = /home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0
tb_derivative: limit   = 450000 of 450000
tb_derivative: [golden] presented       = 450000
tb_derivative: [golden] outputs         = 450000
tb_derivative: [golden] words compared: 450000
tb_derivative: [golden] mismatches: 0   (m_tdata against turunan)
tb_derivative: [golden] d_der mismatches   = 0
tb_derivative: [golden] sample_idx mismatch= 0
tb_derivative: [golden] tuser mismatches   = 0
tb_derivative: [golden] tlast mismatches   = 0
tb_derivative: [golden] first bad index    = -1
tb_derivative: [golden] overflow pulses    = 0
tb_derivative: [golden] first overflow idx = -1
tb_derivative: [golden] d_valid pulses     = 450000
tb_derivative: [golden] golden format odd  = 0
tb_derivative: [golden] PASS
```

Kode keluar larian; dicatat pada baris terakhir log run2 dan pada `reports/fase4`:

```
sim_full_rc=0
real    2m46.551s
```

Waktu larian penuh 2 menit 32 detik (larian pertama) dan 2 menit 47 detik (larian kedua) di Icarus
12.0, 108.012.985 satuan waktu tersimulasi, satu sampel per 24 siklus. Dua larian penuh memberi
keluaran bit-identik, jadi hasilnya bisa diulang, bukan kebetulan satu jalan.

Bukti tambahan pada larian yang sama, semuanya nol: `sample_idx` yang diteruskan, `tuser` 8 bit,
`tlast`, pulsa `m_overflow`, dan cacah kata emas yang bit atasnya bukan perpanjangan tanda yang
bersih (`golden format odd = 0`, dihitung untuk kedua kolom, masuk dan keluar). `d_valid` berdenyut
450.000 kali, sama dengan `m_tvalid`, sesuai kontrak introspeksi.

## 2. Gerbang G2, lint

```
./run_lint.sh ../rtl/tb/tb_derivative.sv tb_derivative ../rtl/derivative.sv ../rtl/afib_lite_pkg.sv
lint clean: top=tb_derivative sources=3 (/home/avivsabilalm/.../verilator_bin)   lint rc=0

./run_lint.sh --chain
run_lint.sh: top=afib_lite_top sources=13 timing=0
lint clean: top=afib_lite_top sources=13 (...)                                   lint_chain_rc=0
```

Log: `reports/fase4/lint_chain_derivative.out`. Lint testbench dijalankan dengan `--timing`, karena
script menambahkan flag itu sendiri untuk berkas berawalan `tb_`; jadi testbench ini ikut di-lint,
bukan hanya desainnya. Peringatan lint yang muncul pada percobaan pertama dan cara menutupnya ada di
bagian 5.

## 3. Gerbang G4, sel, flip-flop, dan luas; satu ketidaksepakatan

`run_synth.sh` **tidak jalan** untuk modul yang mengimpor paket, dan ini cacat script yang terukur,
bukan cacat berkas saya: script hanya menerima satu sumber, jadi `read_verilog` tidak pernah membaca
`afib_lite_pkg.sv`. Keluarannya:

```
./run_synth.sh ../rtl/derivative.sv derivative sky130_fd_sc_hd__tt_025C_1v80.lib
1. Executing Verilog-2005 frontend: ../rtl/derivative.sv
../rtl/derivative.sv:99: ERROR: Failed to evaluate system function `$clog2' with non-constant value.
synth rc=1
```

Pesan itu muncul karena `SHIFT_DER` belum dikenal sama sekali, bukan karena `$clog2`: paketnya memang
tidak pernah dibaca. Fase 3 menemukan hal yang sama untuk `bandpass.sv` dan memakai urutan pass yang
identik dengan paket dibaca lebih dulu (lihat `LAPORAN-FASE3.md` bagian 5). Saya memakai perintah
yang sama, tanpa mengubah urutan pass, flag, atau pustakanya:

```
export PATH="$PWD/debroot/usr/bin:$PATH"
export YOSYS_DATDIR="$PWD/debroot/usr/share/yosys"
yosys -l reports/fase4/derivative.native.20261020.log -p "
    read_verilog -sv ../rtl/afib_lite_pkg.sv ../rtl/derivative.sv;
    hierarchy -top derivative;
    synth -top derivative;
    dfflibmap -liberty sky130_fd_sc_hd__tt_025C_1v80.lib;
    abc -liberty sky130_fd_sc_hd__tt_025C_1v80.lib;
    opt_clean;
    stat -liberty sky130_fd_sc_hd__tt_025C_1v80.lib;
    write_json reports/fase4/derivative.native.20261020.json"
python3 area_report.py reports/fase4/derivative.native.20261020.json \
    sky130_fd_sc_hd__tt_025C_1v80.lib
```

Keluaran mentah (`reports/fase4/synth_derivative_area.out`, log lengkap
`reports/fase4/derivative.native.20261020.log`):

```
run at 2026-10-20T20:02:39+0700
yosys rc=0
netlist       : reports/fase4/derivative.native.20261020.json
library       : sky130_fd_sc_hd__tt_025C_1v80.lib  (428 cells described)
cells mapped  : 1348  (flip-flops 274, combinational 1074)
area          : 11176.97 um^2   (flops 5485.26 um^2, combinational 5691.71 um^2)
flop share    : 49.1 percent of the area
  sky130_fd_sc_hd__nand2_1           x  513   3.754 um^2 each
  sky130_fd_sc_hd__dfxtp_1           x  274  20.019 um^2 each
  sky130_fd_sc_hd__a21boi_0          x  226   7.507 um^2 each
   Number of cells:               1348
   Chip area for module '\derivative': 11176.969600
```

Versi alat: Yosys 0.33 (git sha1 2584903a060), rute native, `dfflibmap` sebelum `abc`, corner
tt 25,0 C 1,80 V. Pembanding jujur dari repo ini: `demo_counter` 33 sel / 316,5536 um^2,
`bandpass` 4.855 sel / 41.508,56 um^2.

Empat belas peringatan yosys yang unik semuanya jinak dan semuanya kelas yang sama dengan yang
dilaporkan Fase 3: `Replacing memory \x_hist_q with list of registers` (memang disengaja, garis tunda
5 kali 26 bit digeser satu kata per sampel), catatan parser `abc` tentang sel liberty yang ekspresi
pin-nya tidak bisa ia baca (234 kali, seluruh pustaka), dan `The network is combinational` pada jalur
`sl_a`/`sl_b`. Log juga menyatakan sendiri `No latch inferred for signal` untuk kedua jalur itu, jadi
tidak ada latch.

Ketidaksepakatan yang harus dibaca Aviv: plan 4.4 memberi batas atas **532 sel / 6.481 um^2** untuk
tahap ini; terukur **1.348 sel / 11.176,97 um^2**, yaitu 2,53 kali jumlah sel dan 1,72 kali luas.
Dua sebab, keduanya terbaca dari log. Pertama, separuh luasnya register: 274 flip-flop kali
20,019 um^2 = 5.485 um^2, 49,1 persen. Kedua, sisa luasnya adalah penyempitan operan 36 bit: jendela
operan selebar 36 bit dengan dua mux 4-ke-1 dan satu komplemen 36 bit memakan 1.074 sel
kombinasional untuk satu penambah 9 bit. Sisi jujurnya, batas plan untuk bandpass juga tidak tercapai
di rute yang sama (2.710 sel menurut plan, 4.855 sel terukur), jadi batas bagian 4 memang batas
perkiraan, bukan angka yang sudah terverifikasi. Yang belum saya kerjakan dan sebaiknya menjadi milik
pemilik luas: mempersempit jendela operan per lintasan, dan menjalankan lintasan bias pembulatan
dengan tiga irisan saja (bias hanya menambah 1 ke bit 3 ke atas, jadi irisan 9+9+6 cukup).

Inventaris register yang ditulis di RTL: 299 bit (garis tunda 130, akumulator 28, carry 1, bendera
lengket 1, pencacah jadwal 6, sideband 41, keluaran 92). Yosys melaporkan 274, selisih 25 bit, dan
sebabnya terukur: `opt_merge` menggabungkan `d_der` ke `m_tdata` (24 bit, masukan D identik) dan
`d_valid` ke `m_tvalid` (1 bit, masukan D identik). Kedua pasang tetap terdorong dan keduanya
dibandingkan testbench, jadi tidak ada perilaku yang hilang; yang hilang hanya flip-flop kembar.
Angka 274 karena itu bukan tanda register yang salah tulis.

## 4. Gerbang G3, deret sintetis buatan tangan

Gerbang plan 4 meminta "deret sintetis negatif turunan 0 beda", dan TASK_BRIEF bagian 3 menuntut
vektor sintetis dengan jumlah mentah `[0, 2, 1, 0, -1, -2]`. Deretnya ada di dalam
`rtl/tb/tb_derivative.sv` (`SYN_IN` dan `SYN_EXP`) dan dijalankan sebagai larian kedua di dalam
testbench yang sama, sesudah larian emas, dengan reset di antaranya. Jumlah mentahnya sendiri
dihitung dengan tangan dan ditulis sebagai komentar per kata; lima bagiannya:

| Bagian | Masukan | Jumlah mentah s | Yang dibuktikan |
|---|---|---|---|
| A | `[0, 1, 0, 0, 0]` | 0, 2, 1, 0, -1, -2 | deret yang diminta plan dan brief; lantai memberi -1 di ekor |
| B | `[0, 10, 0, 0, 0]` | 0, 20, 10, 0, -10, -20 | lantai memberi -2, -3 sedangkan potong-ke-nol memberi -1, -2 |
| C | `[0, -10, 0, 0, 0]` | 0, -20, -10, 0, 10, 20 | cerminnya, bukti yang sama pada tanda lain |
| D | `[0, A, 0, 0, 0]` | 0, 2A, A, 0, -A, -2A | jangkauan lebar, A = 12.000.000 di dalam \|hp\| <= 19.286.208 yang terukur |
| E | `[A, A, 0, -A, -A]` | 2A, 3A, A, -3A, -6A, ... | -6A = -72.000.000, y = -9.000.000 menjenuhkan 24 bit |

Keluaran mentah (`reports/fase4/sim_derivative_full_450000.log`, larian penuh yang sama):

```
tb_derivative: [synthetic] length          = 45
tb_derivative: [synthetic] outputs         = 45
tb_derivative: [synthetic] words compared: 45
tb_derivative: [synthetic] mismatches: 0   (floor shift differs on 6)
tb_derivative: [synthetic] d_der mismatches   = 0
tb_derivative: [synthetic] sample_idx mismatch= 0
tb_derivative: [synthetic] first bad index    = -1
tb_derivative: [synthetic] first overflow idx = 40 (expected 40)
tb_derivative: [synthetic] overflow pulses    = 5 (expected 5)
tb_derivative: [synthetic] PASS
tb_derivative: PASS
```

## 5. Kualitas bukti: apa yang benar-benar ditangkap gerbang ini

Tiga pemeriksaan yang membuat gerbang ini tidak kosong, semuanya terukur.

**(a) Fixture memang buta terhadap aturan pembulatan.** Saya menjalankan kernel yang sama dengan
python atas kolom emas (`/home/avivsabilalm/.hermes/cache/scratch/fase4/synth.py`, keluaran penuh
`synth.out`):

```
[golden] words                  = 450000
[golden] trunc mismatches       = 0
[golden] floor mismatches       = 0  (mutation check)
[golden] raw sums not %8 == 0   = 0
[golden] y range                = [-4792318, 3831762]  fits W_DER=24: True
[golden] hp range               = [-16974032, 19286208]
[golden] saturated words        = 0
```

Nol dari 450.000 jumlah mentah punya sisa bagi 8, jadi geser lantai mereproduksi seluruh kolom emas.
Ini mengulang jebakan yang sudah diukur plan 5.4 dan TASK_BRIEF bagian 3, dan sekaligus menjelaskan
kenapa G1 saja tidak cukup.

**(b) Mutasi aturan pembulatan, dijalankan sungguhan.** Saya menyalin `derivative.sv` ke scratch,
mengganti bias menjadi nol (jadi `y = akumulator >> 3`, geser lantai), dan menjalankan testbench yang
tidak diubah terhadap salinan itu. Keluaran mentah `reports/fase4/mutation_floor_shift.log`:

```
tb_derivative: [golden] mismatches: 0   (m_tdata against turunan)
tb_derivative: [golden] PASS
tb_derivative: [synthetic] mismatches: 6   (floor shift differs on 6)
tb_derivative: [synthetic] FAIL
tb_derivative: FAIL
mutation_rc=1
```

Artinya: satu-satunya yang menangkap kesalahan pembulatan itu adalah deret sintetis, dan testbench
menutup gerbangnya dengan keluar 1. Berkas yang dimutasi **tidak** ada di `rtl/`; ia hanya di
`/home/avivsabilalm/.hermes/cache/scratch/fase4/derivative_floor.sv`.

**(c) Kegagalan pertama yang tertangkap, dan penyebabnya.** Percobaan pertama lulus lint tetapi
memberi 19.997 dari 20.000 kata berbeda dengan beda pertama di indeks 3. Selisihnya tepat sebesar
suku yang seharusnya dikurangkan: RTL menghitung `a + b + 1`, bukan `a - b`, karena operan pengurang
belum dibalik. Perbaikan satu baris: `der_add_b = der_sub ? ~der_b_raw : der_b_raw`, pola yang sama
dengan `bandpass.sv`. Jadi G1 memang punya gigi terhadap kesalahan nyata, bukan hanya terhadap
mutasi yang saya rancang.

## 6. Rancangan yang dipakai, dan ketidaksepakatan lain yang dilaporkan

Persamaan (`rantai.py:227`, `:228`), syarat awal nol, `x[i-2]` sengaja tidak dipakai:

```
s = 2*x[i] + x[i-1] - x[i-3] - 2*x[i-4]
y = s // 8 bila s >= 0, -((-s) // 8) bila s < 0
```

Bentuk RTL adalah bentuk yang direkomendasikan plan 4.4 sendiri, `y = (s + (s < 0 ? 7 : 0)) >> 3`,
dengan 7 = `SHIFT_DER - 1` dan 3 = `log2(SHIFT_DER)`. Identitasnya eksak: untuk s < 0,
`floor((s + 7) / 8) == ceil(s / 8) == trunc(s / 8)`; jadi bias satu sisi menggantikan pemisahan tanda
dan hanya butuh satu penambah, bukan negasi. Semua lebar dan tetapan diambil dari `afib_lite_pkg`:
`SHIFT_DER` untuk pembagi 8, `W_HP` untuk masukan, `W_DER` untuk keluaran, `W_DER_WORST` untuk lebar
hasil 25 bit. Operasi murni tanpa pengali: dua suku bernilai 2 ditulis sebagai penyambungan
(`{x0_ext, 1'b0}`), bukan pergeseran dengan tetapan yang diketik.

Akumulator 28 bit, dipotong 9 bit, satu penambah 9 bit dipakai ulang untuk empat lintasan:

| Lintasan | Operasi |
|---|---|
| 0 | `2*x[i] + x[i-1]` |
| 1 | `- x[i-3]`, lewat komplemen satu ditambah carry masuk irisan 0 |
| 2 | `- 2*x[i-4]`, bentuk yang sama |
| 3 | `+ 7` bila s negatif; `y = akumulator >> 3` hanya penyambungan kawat |

Empat irisan (9+9+9+1 = 28 bit) kali empat lintasan = 16 siklus, ditambah satu siklus terima:
latensi tetap **17 siklus**, `LAT_CYCLES = 17`, tanpa `tready` di dalam (D1). Satu sampel ada di
dalam tahap pada satu waktu, jadi sideband (`tlast`, `tuser`, `sample_idx`) cukup satu set register.

Ketidaksepakatan dan keputusan, semuanya perlu dibaca Aviv:

1. **Siklus.** Plan 4.4 menulis "4 siklus per sampel". Angka itu mengandaikan penambah 24 bit tanpa
   irisan, sedangkan plan yang sama menolak kandidat itu di barisnya sendiri (`add_c_24`
   42,2128 ns lawan 7,8194 ns tersedia). Dengan aturan irisan maksimum 9 bit dari pembuka bagian 4,
   hitungan jujurnya 16 siklus aritmetika ditambah satu siklus terima, dan `LAT_CYCLES` memuat 17.
   Terhadap 400.000 siklus yang tersedia per sampel pada 250 Hz, selisih ini tidak berarti.
2. **`LAT_CYCLES` bawaannya berubah dari 1 menjadi 17.** Daftar port tidak disentuh sama sekali, byte
   per byte sama dengan kerangka Fase 1; yang berubah hanya nilai bawaan parameter, sama seperti yang
   dilakukan `bandpass.sv` (1 menjadi 16). Nilai 1 pada kerangka adalah penanda tempat, bukan jadwal.
3. **Perilaku saat menjenuh belum ditentukan plan.** `m_tdata` menjenuhkan pada +-8388607 lalu
   menaikkan `m_overflow`, meniru `bandpass.sv` di batas tahap yang sama, supaya tanda dan besaran
   tidak berbalik sebelum tahap kuadrat. Model beku tidak pernah mencapai kasus ini pada 04015
   (0 kata menjenuh dari 450.000), jadi ini keputusan rancangan, bukan hasil ukur. Kalau Aviv memilih
   pemotongan bit rendah, yang berubah hanya `y_sat` dan satu kata yang diharapkan di deret sintetis
   indeks 40.
4. **`m_overflow` juga menyala bila `s_tvalid` datang saat tahap sibuk.** Tanpa `tready` di dalam,
   bendera itu pengganti jabat tangan penjaga kehilangan kata (plan 3.3). Pada rekaman 04015 kedua
   sumber itu nol, dan angka nol itu dilaporkan testbench: 0 pulsa pada 450.000 sampel, jadi tidak
   ada kata yang hilang dan tidak ada kata yang menjenuh.
5. **Lebar akumulator tidak punya tetapan di paket.** `6 * max|hp| = 115.717.248` butuh 28 bit
   bertanda, sedangkan paket hanya punya `W_HP_ACC = 27` (batas `|32*x16|`). Menambah tetapan ke
   `afib_lite_pkg.sv` dilarang untuk saya (berkas itu bukan milik fase ini), jadi lebarnya ditulis
   sebagai ekspresi `W_HP + 2` dengan alasan lengkap di kepala berkas. Usulan ke Aviv: satu tetapan
   `W_DER_ACC = 28` di paket supaya angka itu tidak lagi berupa ekspresi di modul.

Peringatan lint yang muncul pada percobaan pertama dan cara menutupnya, tanpa mengubah aritmetika:
`WIDTHEXPAND` pada tetapan bias (ditutup dengan memecahnya menjadi `TRUNC_BIAS32` 32 bit lalu
menambal eksplisit, karena Icarus menolak operan penyambungan yang lebarnya tidak pasti),
`UNUSEDSIGNAL` pada bit tertinggi dua operan tergeser (ditutup dengan mengambil kedua operan satu bit
lebih sempit, seperti `bandpass.sv`), dan `UNUSEDSIGNAL` pada tiga bit bawah akumulator yang memang
dibuang pembagian 8 (ditutup dengan menyusun `y_full` langsung dari potongan yang dipakai).

## 7. Berkas, sidik jari, dan letak log mentah

| Berkas | Keadaan | sha256 |
|---|---|---|
| `rtl/derivative.sv` | baru, 268 baris | `30ec0d9385aa089cc61b3e1f4cf220091bb9578871d5f4e2ce43f89b3965df2c` |
| `rtl/tb/tb_derivative.sv` | baru, 383 baris | `f83d0ff5a4024ee8d2568d9458b950fe2c3dced161d0db9dcb748587f02465ef` |
| `rtl/afib_lite_pkg.sv` | tidak disentuh | `1bf69b5edfdd57a2fabd04573ba4aba0cbd6b202d042657631cc2b8fb1c31e0b` |
| `model/rantai-afib-lite/rantai.py` | tidak disentuh | `90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5` |

Log mentah, semuanya di `rtl-synthesis/reports/fase4/`:

| Berkas | Isi |
|---|---|
| `sim_derivative_full_450000.log` | G1, larian penuh 450.000, PASS |
| `sim_derivative_full_450000_run2.log` | G1 larian kedua, bit-identik, `sim_full_rc=0` |
| `sim_derivative_short_20000.log` | larian pendek `+LIMIT=20000`, dipakai saat menutup cacat pertama |
| `lint_chain_derivative.out` | G2, `run_lint.sh --chain`, `lint_chain_rc=0` + lint testbench |
| `derivative.native.20261020.log`, `.json` | G4, log yosys lengkap dan netlist |
| `synth_derivative_area.out` | G4, keluaran `area_report.py` dan cap waktu saat dijalankan |
| `mutation_floor_shift.log` | mutasi geser lantai: emas PASS, sintetis FAIL 6, keluar 1 |

Dua catatan kerapian. Pertama, percobaan `run_synth.sh` yang gagal meninggalkan log separuh di
`rtl-synthesis/reports/derivative.native.20261020.log` (2.216 bita, berisi galat `$clog2`); log yang
sah adalah yang di `fase4/`, dan berkas itu sebaiknya dihapus Aviv. Kedua, direktori
`reports/fase4/` dipakai bersama oleh pekerjaan `square.sv` dan `integrator.sv` (fase 4b), jadi nama
berkas log di situ seluruhnya memuat kata `derivative` supaya tidak bertabrakan.

## 8. Yang belum dibuktikan, supaya tidak diklaim lebih

1. **Verilator 5.020 hanya dipakai sebagai lint**, bukan simulator kedua. Rencana 7.1 butir 3
   meminta replay di dua mesin. Belum dikerjakan di sini.
2. **Lint testbench memakai `--timing`**, tetapi testbench tidak dijalankan di Verilator, jadi tidak
   ada bukti `$readmemh` Icarus dan Verilator memberi hasil sama. Pada Fase 3 juga tidak.
3. **Tidak ada bukti formal** (`sby`, `eqy`, `mcy`) bahwa latensi tetap tidak pernah menahan atau
   bahwa `m_overflow` tidak bisa menyala tanpa sebab. Yang ada baru simulasi 450.000 sampel ditambah
   45 kata sintetis; `mcy` bisa dijalankan sebagai langkah berikutnya.
4. **Batas atas timing 100 MHz belum diukur** untuk tahap ini; yang ada hanya jumlah sel dan luas.
   Satu penambah 9 bit per siklus adalah alasan desainnya, bukan hasil pengukuran OpenSTA (alat itu
   tidak ada di mesin ini, sesuai plan 2.1).
5. **Berkas sinyal `s_tready` tidak ada di modul ini** dan memang tidak boleh ada (D1). Kalau kelak
   diputuskan ada tekan-balik, modul ini harus ditulis ulang pada bagian jadwalnya.
