# LAPORAN FASE 11 — peta register AXI dan penggerak PS

Rencana: `rtlplan2/final38.md`, Fase 11 (baris 2160-2180), peta register bagian 8.5 (D8),
peta unit ambang bagian 8.8, doc 36 bagian 3.4. Pemilik berkas: baris Fase 11
`rtl-synthesis/reports/KEPEMILIKAN-BERKAS.md`.

Keluaran Fase 11 yang diminta rencana: `rtl/regs_axi.sv`, `rtl/tb/tb_regs_axi.sv`,
`ps_driver_afib.py`. Rencana tidak menyebut jalur direktori untuk berkas ketiga; pilihannya
dilaporkan di bagian 6.

## 1. Gerbang fase dan statusnya

| Gerbang (verbatim rencana) | Status | Bukti |
|---|---|---|
| setiap bacaan sama dengan nilai tulis | **lulus** | bagian 2, `mismatches = 0 out of 4056`, rc=0 |
| `SCRATCH` kembali sama | **lulus** | 0xA5A55A5A ditulis dan dibaca kembali, 6 pola putar penuh |
| penggerak mencetak jumlah slot | **lulus** | bagian 4, `map: 38 slots, 0x00..0x94` |
| penggerak lulus dua pemeriksaan pertama terhadap mock | **lulus** | bagian 4, `init 1/9 ... PASS`, `init 2/9 ... PASS`, `checks: 12, failed: 0` |
| lengan aturan T mati memberi hasil sama dengan fixture lengan itu | **lulus** | bagian 3: 588 keputusan, 0 beda dari fixture lengan mentah |
| lint bersih | **lulus** | `regs_axi` rc=0, `tb_regs_axi` rc=0 (bagian 2.1) |

## 2. Perintah dan keluaran mentah

Semua dijalankan dari `rtl-synthesis`, memakai hanya rute repo.

### 2.1 Lint

```
$ ./run_lint.sh ../rtl/regs_axi.sv regs_axi ../rtl/afib_lite_pkg.sv
lint clean: top=regs_axi sources=2 (…/debroot/usr/bin/verilator_bin)      # rc=0

$ ./run_lint.sh ../rtl/tb/tb_regs_axi.sv tb_regs_axi ../rtl/afib_lite_pkg.sv ../rtl/regs_axi.sv
lint clean: top=tb_regs_axi sources=3 (…/debroot/usr/bin/verilator_bin)   # rc=0
```

### 2.2 Simulasi gerbang, dua jalan identik

```
$ ./run_sim.sh ../rtl/tb/tb_regs_axi.sv ../rtl/afib_lite_pkg.sv ../rtl/regs_axi.sv \
      -- +VECTOR=../rtl/tb/vektor/fase11
$ ... (dijalankan dua kali, log terpisah, rc=0 dua-duanya)
$ cmp -s reports/fase11/sim_gate_A.log reports/fase11/sim_gate_B.log && echo identical
identical
```

Baris mentah penutup, apa adanya:

```
checks: 118
words compared: 4056
mismatches = 0 out of 4056
failures: 0
gate: PASS
PASS
```

Bagian per bagian, dari log yang sama:

```
reset slot comparisons: 38      reset mismatches: 0
round trip comparisons: 180     round trip mismatches: 0
read only slot comparisons: 120 read only slot mismatches: 0
byte lane comparisons: 90       byte lane mismatches: 0
unmapped comparisons: 56        unmapped mismatches: 0
OK   SCRATCH reads back what was written 4277009102      (0xA5A55A5A)
OK   zero strobe write changes nothing 2779077210
OK   zero strobe sample word is not counted 0
OK   CLAMP_THRESH before the ingest test 2047
OK   SAMPLE_IN_STATUS counts one word 1
OK   MARKER_LAST carries the mark 1
OK   clamp count from the mark 1 / from the word rule 2 / unchanged by a low word 2
OK   three words received 3
OK   clear counters clears the word count 0
OK   IRQ_STATUS follows i_irq 31 / IRQ_CLEAR clears the four low sources 16 / reads zero 0
OK   unmapped read 0x98..0x93 returns zero 0, writes answered OKAY
OK   simultaneous write answered / simultaneous read answered
OK   simultaneous read returns the pre write value 2779077210
OK   DEBUG_SEL read equals write 165        (slot 0x90)
OK   DEBUG_VAL reads zero 0                 (slot 0x94)
OK   o_window_step reset 4 / o_window_beats reset 32
```

### 2.3 Kontrol negatif testbench (harapan dirusak di SALINAN)

Salinan vektor di `$TMPDIR/fase11-neg3/vektor`, satu kata kelas fixture mentah diubah
`00000001` menjadi `00000002`. Berkas asli tidak disentuh.

```
$ sed -i '1s/.*/00000002/' $SCR/vektor/f11.mentah.kelas.hex
$ ./run_sim.sh ../rtl/tb/tb_regs_axi.sv ../rtl/afib_lite_pkg.sv ../rtl/regs_axi.sv \
      -- +VECTOR=$SCR/vektor                                    # rc=1
MISMATCH arm run mentah window 0 got=1 want=2
FAIL arm mismatches got=1 want=0
mismatches = 1 out of 4056
gate: FAIL, see the lines above
FATAL: ../rtl/tb/tb_regs_axi.sv:1125: tb_regs_axi: 1 mismatches, 1 failures
```

Satu harapan yang salah membuat testbench gagal dan rc != 0, jadi `PASS` di bagian 2.2
bukan hasil dari pemeriksaan yang tidak pernah membandingkan apa pun. `PASS` dengan
`words compared: 0` juga gagal di testbench ini, dijaga eksplisit.

### 2.4 Lint rantai penuh

```
$ ./run_lint.sh --chain                                            # rc=1
%Warning-PINMISSING: ../rtl/afib_lite_top.sv:398:17: Cell has missing pin: 's_hp' …
%Warning-PINMISSING: ../rtl/afib_lite_top.sv:410:12: Cell has missing pin: 'i_peak_valid' …
%Error: Exiting due to 13 warning(s)
```

Ketiga belas peringatan itu semuanya di `afib_lite_top.sv` baris 398 dan 410, yaitu
instansiasi modul milik fase lain yang sedang berubah di pohon yang sama (pekerja paralel).
Tidak satu pun menunjuk `rtl/regs_axi.sv` atau testbench fase ini: lint kedua berkas fase 11
sendiri bersih, rc=0, di bagian 2.1. Kembalinya rantai ke bersih bergantung pada integrasi
fase lain, bukan pada berkas ini.

## 3. Gerbang lengan: ARM_SELECT mematikan lengan aturan T

Titik operasi **disuntikkan lewat bus lalu dibaca kembali** sebelum lengan dinilai, karena
fixture dibuat pada titik operasi model sedangkan nilai reset D8 adalah titik operasi yang
sama dalam satuan kasar. Rencana mengingatkan hal ini sendiri di catatan risiko Fase 9
(final38.md baris 2137): memakai nilai reset alih-alih menyuntik titik operasi berarti
membandingkan apel dengan jeruk.

```
OK   RATIO_THRESH reset code 33
OK   ENTROPY_THRESH reset code 63
OK   RATIO_THRESH reset code is the same point as the Q16 code
OK   ENTROPY_THRESH reset code is the same point as the Q14 code
OK   RATIO_THRESH injected code read back 10813
OK   ENTROPY_THRESH injected code read back 10322
OK   o_ratio_thresh follows the injected code 10813
OK   o_entropy_thresh follows the injected code 10322
arm run berpenanda arm=0x0f windows=602 fired=189 TP=95 FP=94 FN=0 TN=413
arm run t_off      arm=0x0b windows=588 fired=183 TP=95 FP=88 FN=0 TN=405
arm run mentah     arm=0x07 windows=588 fired=183 TP=95 FP=88 FN=0 TN=405
arm run tunggal    arm=0x02 windows=602 fired=191
arm run guard      arm=0x02 ent=0x00008000 windows=602 fired=0
arm run either     arm=0x1f windows=602 fired=299 TP=95 FP=204
arm comparisons: 3584
arm mismatches: 0
```

Terhadap blok beku `rtlplan2/fase5/04015.manifest.fase5.json` butir `triage_gate`:

| Lengan | windows | fired | TP | FP | FN | TN | fixture manifes |
|---|---|---|---|---|---|---|---|
| berpenanda, `ARM_SELECT` 0x0F | 602 | 189 | 95 | 94 | 0 | 413 | sama persis |
| aturan T mati, `ARM_SELECT` 0x0B (b2 clear) | 588 | 183 | 95 | 88 | 0 | 405 | sama persis dengan `raw_arm` |
| deret mentah, `ARM_SELECT` 0x07 (b3 clear) | 588 | 183 | 95 | 88 | 0 | 405 | sama persis dengan `raw_arm` |

Jadi "lengan aturan T mati" menghasilkan **0 dari 588 keputusan berbeda** dari fixture lengan
mentah, dan kedua penafsiran bit yang mungkin untuk lengan mentah (b2 clear ala `TASK_BRIEF`
dan b3 clear ala ekspor vektor Fase 9) mendarat pada fixture yang sama; keduanya dijalankan
dan dicetak, bukan salah satu saja.

Yang **tidak** dibuktikan bagian ini, dan sudah tertulis di kepala berkas uji: jalur data
aturan gelombang T ada di Fase 7 dan sumber deret berpenanda ada di Fase 6. Yang diuji di
sini adalah semantik lengan pada tingkat register: bit lengan menyeleksi sumber fitur mana
yang dinilai, dan hasilnya sama dengan fixture lengan itu.

### 3.1 Temuan satuan ambang (dilaporkan, bukan disembunyikan)

Rencana memuat dua penulisan untuk kode ambang yang sama titiknya:

- peta D8 bagian 8.5 (baris 1184-1185) dan paket beku: `RATIO_THRESH` 33 satuan **1/200**,
  `ENTROPY_THRESH` 63 satuan **1/100**.
- gerbang F5c Fase 5 (baris 850) dan gerbang Fase 9 (baris 2133): kode ambang register
  "10.813 pada Q16" dan "10.322 pada Q14" menurut doc 36 bagian 3.4.

Keduanya titik operasi yang sama: 33/200 = 0,165 dan 10813/65536 = 0,164994; 63/100 = 0,63
dan 10322/16384 = 0,630005. Selisihnya di bawah satu LSB satuan masing-masing, dan itu yang
diperiksa testbench dalam bilangan bulat:

```
|33*65536 - 10813*200| = 88  <= 200
|63*16384 - 10322*100| =  8  <= 100
```

Berkas register mengikuti peta D8 dan paket beku (33 dan 63) karena itu yang final untuk
fase ini. Paritas fixture pada bagian 3 memakai kode skala model yang disuntikkan, sesuai
arahan rencana sendiri. Keputusan mana yang dipakai untuk paritas model jangka panjang adalah
keputusan pemilik rencana, dan angkanya ada di sini supaya bisa diputuskan.

## 4. Penggerak PS

Jalur yang dipilih: **`ps/ps_driver_afib.py`** (rencana hanya menyebut nama berkas, tanpa
direktori; `ps/` dipilih supaya berkas RTL dan berkas sisi PS tidak bercampur di akar repo).
Dijalankan dengan juru bahasa venv repo:

```
$ ~/.venvs/afib-lite/bin/python ps/ps_driver_afib.py --out rtl-synthesis/reports/fase11/ps_driver
driver self-test against the register-semantics MOCK, not against a board
map: 38 slots, 0x00..0x94 (frozen map 36 slots 0x00..0x8C plus DEBUG_SEL 0x90 and DEBUG_VAL 0x94 of plan decision 9)
base address: /proc/device-tree/afib_lite (from the device tree, never a constant)
fixture: 450000 words, 4777 peaks, 588 feature rows, chain sha256 90df6e5b457307d3
feature row 0: [217.23422768389736, 0.3031880358463327, 0.45161290322580644, 0.5880542503656206]
  init 1/9 versi      0x00010001
  init 1/9 VERSION_ID is not zero                PASS
  init 2/9 scratch    0xA5A55A5A (ok)
  init 2/9 SCRATCH reads back what was written   PASS
  init 3/9 irq_clear 0x00000000
  init 4/9 ctrl_stop 0x00000000
  init 5/9 rate_div 0x00061A7F
  init 6/9 format_cfg 0x004C00FA
  init 7/9 ambang ratio=0x00000021 entropy=0x0000003F arm=0x0000000F
  init 8/9 ctrl 0x00000001
  init 9/9 status 0x00000081
run1 burst: {'samples_in': 60000, 'writes_in': 60000, 'windows': 155, 'beats': 648, 'gap': 0, 'clamp': 0, 'ovf': 0, 'idx': 60000} in 0.144 s (418 kS/s host side)
  latency: windows=155 | pipeline tail samples min 3 max 3 | tap group delay samples 40 (model says 40.11) | window fill s train min 9.7
  csv: rtl-synthesis/reports/fase11/ps_driver/window.pl.04015.20261021.01.csv (155 rows)
  first 3 rows: [(0, 1, 3, 40), (1, 1, 3, 40), (2, 1, 3, 40)]
  class histogram of the logged windows: {1: 60, 2: 95}
  csv row 1  : 0,32,91,2925,2928,3,40,2837,11.348,1,112,61,59,56,0,0,0,0,2925,<ts_host>
run2 realtime: {'samples_in': 1250, …, 'idx': 1250}, wall 5.000 s for 1250 samples (expected 5.000 s)
run3 clamp stress: {'samples_in': 6000, …, 'clamp': 6000, 'ovf': 0, 'idx': 6000, 'marker_last': '0x1', 'status': '0xD1'}
run4 gap injection: gap=2 ovf=0 idx=4000
run5 measure csv: rtl-synthesis/reports/fase11/ps_driver/measure.energi.pl.20261021.01.csv
checks: 12, failed: 0
OK: driver logic exercised end to end against the mock           # rc=0
```

Angka-angka itu sama dengan keluaran penggerak terukur milik rencana sendiri
(`rtlplan2/ps_driver_test/run.log` dan final38.md baris 1351-1368, "kutipan apa adanya"),
kecuali dua hal yang dilaporkan di bagian 6 butir 1 dan 2.

Kontrol negatif penggerak: satu jawaban mock dirusak sengaja (SCRATCH membaca nol).

```
$ ~/.venvs/afib-lite/bin/python ps/ps_driver_afib.py --negatif …      # rc=1
  init 2/9 SCRATCH reads back what was written   FAIL: wrote 0xA5A55A5A, read 0x00000000
checks: 12, failed: 1
FAIL: driver self test against the mock
```

Jalur papan `--backend uio` membaca alamat dasarnya lewat perangkat UIO dari device tree
(bukan konstanta) dan **belum terverifikasi: tidak ada papan, overlay, maupun `/dev/uioN` di
mesin ini**; tanpa perangkat ia berhenti dengan pesan yang menyebutkan sebabnya.

## 5. Peta register yang diimplementasikan

Hasil akhir **38 slot**, 0x00 sampai 0x94, langkah 4 bita. 36 slot pertama adalah peta beku
bagian 8.5; dua slot terakhir adalah keputusan butir 9 rencana (final38.md baris 2238) yang
menerima pasangan `DEBUG_SEL`/`DEBUG_VAL` di 0x90/0x94 dan menaikkan jumlah slot dari 36
menjadi 38.

| Offset | Nama | Akses | Nilai reset | Catatan implementasi |
|---|---|---|---|---|
| 0x00 | CTRL | RW | 0x00000000 | b0 `o_enable`, b2 `o_clear_counters`, bit lain disimpan dan terbaca |
| 0x04 | STATUS | RO | 0x00000001 | mengikuti `i_status` |
| 0x08 | IRQ_STATUS | RO | 0x00000000 | `i_irq` kurang bit yang dibersihkan lewat 0x0C |
| 0x0C | IRQ_CLEAR | W1C | 0x00000000 | tulis satu membersihkan sumber; baca selalu nol |
| 0x10 | CLASS_OUT | RO | 0x00000000 | port beku tidak membawa masukan kelas |
| 0x14 | CONFIDENCE | RO | 0x00000000 | idem |
| 0x18 | RR_LAST | RO | 0x00000000 | idem |
| 0x1C | BEAT_COUNT | RO | 0x00000000 | idem |
| 0x20 | GAP_COUNT | RO | 0x00000000 | **dihitung di berkas ini** dari penanda celah |
| 0x24 | SAMPLE_IDX | RO | 0x00000000 | idem kelas: tanpa masukan |
| 0x28 | WINDOW_COUNT | RO | 0x00000000 | idem |
| 0x2C | CLAMP_COUNT | RO | 0x00000000 | **dihitung di berkas ini** dari aturan penjepitan |
| 0x30 | FIFO_OVF_COUNT | RO | 0x00000000 | tetap nol: tidak ada FIFO yang bisa luapan di sini |
| 0x34 | RR_LONG_COUNT | RO | 0x00000000 | tanpa masukan |
| 0x38 | RR_MARK_LAST | RO | 0x00000000 | tanpa masukan |
| 0x3C | RATIO_THRESH | RW, bidang 16 | 0x00000021 = **33** | satuan 1/200; 33 berarti 0,165; `o_ratio_thresh` = bit 15:0 |
| 0x40 | ENTROPY_THRESH | RW, bidang 16 | 0x0000003F = **63** | satuan 1/100; 63 berarti 0,63; `o_entropy_thresh` = bit 15:0 |
| 0x44 | ARM_SELECT | RW | 0x0000000F | b0 rasio, b1 entropi, b2 aturan T, b3 deret berpenanda, b4 kedua wajib/cukup satu |
| 0x48 | FEAT_RATIO | RO | 0x00000000 | tanpa masukan |
| 0x4C | FEAT_ENTROPY | RO | 0x00000000 | tanpa masukan |
| 0x50 | FORMAT_CFG | RW | 0x004C00FA | disimpan apa adanya |
| 0x54 | RATE_DIV | RW, bidang 20 | 0x00061A7F | `o_rate_div` = bit 19:0 |
| 0x58 | THRESH_SCALE | RW | 0x00000100 | disimpan |
| 0x5C | RR_BAND_LO | RW | 0x0000005C | disimpan |
| 0x60 | RR_BAND_HI | RW | 0x00000074 | disimpan |
| 0x64 | VERSION_ID | RO | 0x00010001 | konstanta |
| 0x68 | SCRATCH | RW | 0x00000000 | bukti tulis-baca bus, 0xA5A55A5A |
| 0x6C | SAMPLE_FIFO | WO | 0x00000000 | satu kata sampel; dihitung ke 0x74, tidak dihitung kalau semua strobe rendah |
| 0x70 | SAMPLE_MARK | WO | 0x00000000 | b3:0 menempel pada kata berikutnya |
| 0x74 | SAMPLE_IN_STATUS | RO | 0x00000000 | b15:0 jumlah kata; b23:16 tingkat FIFO **selalu nol di sini** |
| 0x78 | MARKER_LAST | RO | 0x00000000 | penanda kata terakhir yang benar-benar diterima |
| 0x7C | CLAMP_THRESH | RW | 0x000007FF | kata ditandai hanya kalau **melebihi** nilai ini |
| 0x80 | GAP_RECOVERY | RW | 0x00000083 | disimpan |
| 0x84 | REPLAY_LEN | RW | 0x00000000 | disimpan |
| 0x88 | IDX_TAP_LAST | RO | 0x00000000 | tanpa masukan |
| 0x8C | IDX_DEC_LAST | RO | 0x00000000 | tanpa masukan |
| 0x90 | DEBUG_SEL | RW, bidang 8 | 0x00000000 | keputusan 9; disimpan penuh dan terbaca kembali |
| 0x94 | DEBUG_VAL | RO | 0x00000000 | keputusan 9; membaca nol karena port beku tidak membawa kata introspeksi |

Perubahan dari usulan awal di peta: dua slot 0x90/0x94 sebelumnya diberi nama
`WINDOW_STEP`/`WINDOW_BEATS` di draf kepala berkas. Keputusan butir 9 rencana memberi nama
`DEBUG_SEL`/`DEBUG_VAL` untuk dua slot itu, dan peta bagian 8.5 memang **tidak** memuat
`WINDOW_STEP`/`WINDOW_BEATS`: keduanya ada di tabel bentrok offset (baris 1232-1233) sebagai
nama dari dokumen lama pada 0x54/0x58 yang dibuang D8. Karena itu:

- 0x90/0x94 sekarang `DEBUG_SEL`/`DEBUG_VAL` (keputusan 9),
- pasangan port beku `o_window_step`/`o_window_beats` tetap ada dan **tidak** lagi berasal dari
  slot: keduanya digerakkan dari konstanta paket (`WINDOW_STEP_FIELD` 4 dan
  `WINDOW_BEATS_FIELD` 32), yang persis perannya di top level: `afib_lite_top.sv:249-250`
  memakai masukan papan kalau tidak nol dan pasangan ini sebagai nilai cadangan. Jenis port
  berubah dari `output reg` menjadi `output wire`; nama, lebar, arah, dan urutan tidak berubah,
  dan instansiasi di `afib_lite_top.sv:468` tetap cocok.

### 5.1 Kebijakan nilai tersimpan dan byte lane

Tulisan menyimpan 32 bit penuh dan bacaan mengembalikannya apa adanya, **termasuk bit di atas
bidang yang dideklarasikan**, jadi "setiap bacaan sama dengan nilai tulis" berlaku pada lebar
penuh untuk setiap slot writable. Bidang adalah apa yang keluar dari berkas ini. Alternatifnya
(mask saat tulis) akan membuat bacaan 0xFFFFFFFF mengembalikan 0x0000FFFF; pilihan yang
diambil dilaporkan di sini supaya bisa diputuskan.

Byte lane dihormati (`s_axi_wstrb`), dan tulisan dengan semua strobe rendah dijawab OKAY serta
tidak mengubah apa pun — AXI4-Lite menjamin respons untuk setiap tulis yang diterima.

## 6. Penyimpangan, temuan, dan pekerjaan yang belum selesai

1. **Jumlah slot 36 lawan 38.** Keluaran penggerak terukur milik rencana
   (`rtlplan2/ps_driver_test/run.log` baris 2) mencetak `map: 36 slots, 0x00..0x8C`.
   Penggerak fase ini mencetak `38 slots, 0x00..0x94`, karena keputusan butir 9 rencana
   (baris 2238) justru meminta kedua dokumen diperbarui menjadi 38 slot — dan rencana sendiri
   menyebut bahwa penggerak yang mencetak jumlah slot akan memperlihatkan perbedaan itu di
   depan juri. Perbedaan ini disengaja dan mengikuti keputusan, bukan kelalaian; angka 38 juga
   yang diuji testbench (`vector map slot count 38`, `frozen slot count 36`).
2. **Satuan ambang.** Lihat bagian 3.1: peta D8 dan paket beku memakai 33 (1/200) dan 63
   (1/100), sementara gerbang F5c dan Fase 9 menyebut kode 10.813 Q16 dan 10.322 Q14 untuk
   titik operasi yang sama. Keduanya diperiksa setara di dalam satu LSB; keputusan mana yang
   menjadi satuan paritas model jangka panjang ada di tangan pemilik rencana.
3. **Port beku tidak membawa 14 sumber bacaan.** Dua belas slot RO membaca nilai resetnya
   karena tidak ada masukan untuknya, `FIFO_OVF_COUNT` tetap nol karena tidak ada konsumen
   FIFO di port beku, dan `DEBUG_VAL` 0x94 membaca nol karena mux introspeksi hidup di balik
   port `i_dbg_sel` milik top level (`afib_lite_top.sv:95`, catatan rencana di I1 baris 120).
   Hanya tiga penghitung sisi masuk yang dimiliki berkas ini (`CLAMP_COUNT`, `GAP_COUNT`, dan
   cacah kata/`MARKER_LAST`). Menutup celah itu perlu keputusan pemilik untuk melebarkan daftar
   port; tanpa keputusan itu, slot itu tetap ada dan tetap bisa ditulis-dibaca, tetapi
   nilainya tidak bisa bergerak.
4. **Mock dan RTL sengaja berbeda di dua hal**, keduanya ditulis di docstring penggerak:
   mock menyimpan FIFO kedalaman 64 dan melaporkan tingkatnya di bit 23:16 `SAMPLE_IN_STATUS`
   serta kolom `fifo_level` CSV, sedangkan port beku `regs_axi` tidak punya konsumen FIFO
   sehingga bidang itu nol di perangkat keras; dan mock menghitung cacah sisi masuk pada
   *slot sampel*, sementara berkas register menghitungnya pada *tulis strobed*. Yang bisa
   diamati penggerak (`SAMPLE_IN_STATUS`, `MARKER_LAST`, `CLAMP_COUNT`, `GAP_COUNT`) sama di
   kedua sisi, tetapi mock **bukan** RTL dan tidak membuktikan RTL.
5. **Pekerjaan yang belum selesai, jujur:** FIFO kedalaman 64 dari langkah 3 rencana tidak
   diimplementasikan (butuh keputusan port konsumen, lihat butir 3); jalur `--backend uio`
   belum pernah menyentuh papan; `DEBUG_SEL`/`DEBUG_VAL` belum tersambung ke mux introspeksi
   karena itu milik port beku top level; lint rantai penuh masih rc=1 oleh 13 peringatan
   `PINMISSING` di `afib_lite_top.sv` milik pekerja paralel (bagian 2.4), bukan oleh berkas
   fase ini.
6. **Determinisme.** Dua jalan testbench byte identik (sha256 log sama). Penggerak dua kali
   juga identik kecuali dua baris yang sifatnya waktu dinding (`kS/s host side` dan kolom
   `ts_host` di CSV); seluruh angka yang diperiksa (`checks`) berasal dari cacah, bukan waktu,
   jadi tidak ada pemeriksaan yang bergantung pada detak mesin.

## 7. Berkas fase 11 dan sidik jari

| Berkas | sha256 |
|---|---|
| `rtl/regs_axi.sv` | lihat keluaran `sha256sum` pada laporan agen induk |
| `rtl/tb/tb_regs_axi.sv` | idem |
| `ps/ps_driver_afib.py` | idem |
| `rtl-synthesis/reports/fase11/gen_vektor_fase11.py` | idem |
| `rtl/tb/vektor/fase11/*.hex`, `f11.manifest.json` | 16 berkas, dihitung di laporan agen induk |
| `model/rantai-afib-lite/rantai.py` | **90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5** (beku, tidak berubah, diverifikasi generator pada setiap jalan) |

Berkas milik fase lain tidak disentuh: `rtl/peak_detect.sv`, `rtl/rr_series.sv`,
`rtl/t_rule.sv`, `rtl/features.sv`, `rtl/classifier.sv`, `rtl/tb/tb_puncak.sv`,
`rtl/afib_lite_top.sv`, `rtl/afib_lite_pkg.sv`, `rtl-synthesis/run_lint.sh`,
`rtl-synthesis/run_sim.sh`, `rtl-synthesis/mcy/**`, `model/**`, `rtl/TASK_BRIEF.md`.
