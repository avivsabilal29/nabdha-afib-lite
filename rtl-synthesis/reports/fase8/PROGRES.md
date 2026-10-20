# PROGRES Fase 8 -- lapisan fitur jendela 32 interval (rtl/features.sv + rtl/tb/tb_fitur.sv)

Berjalan. Ditulis bertahap; setiap baris membawa perintah atau angka nyata, bukan rencana.

## 1. Pembacaan rencana (jangan mengarang langkah)

- `rtlplan2/final38.md:117` baris tabel Fase 8, gerbang verbatim:
  "`d`, cacah pNN50, dan 16 cacah histogram 0 beda; akar dan entropi dalam 1 LSB dengan 0 kode
  menyimpang lebih dari 1 LSB; cacah histogram 0 dari 602 beda".
- `rtlplan2/final38.md:2103` blok bagian 12, langkah 1..10 dan gerbang tambahan di blok:
  "akar di bawah 0,5 LSB; rasio di bawah 0,75 LSB; entropi per empat di bawah 0,5 LSB; jumlah kode
  menyimpang lebih dari 1 LSB sama dengan 0; cacah histogram 0 dari 602 jendela berbeda; lint bersih".
  Karena blok menuntut 0,5/0,75 LSB, bentuk simpul dipilih yang memberi 0 LSB selisih, bukan bentuk
  literal yang memberi tepat 1 LSB (lihat bagian 3).

## 2. Data emas dan vektor

- Sumber: `rtlplan2/fase5/04015.windows.csv` (602 baris, kolom `rr_00..rr_31`, `d_00..d_30`,
  `bin_00..bin_15`, `cnt_gt50`, `pnn50`, `rmssd`, `ratio`, `ent4`, `mean31`), `04015.rr.csv`
  (2595 interval), fixture `model/rantai-afib-lite/fixture/04015_30m.npz` (lengan mentah).
- Kolom yang paling mudah dipakai (catatan silang untuk pekerja Fase 6/9): `src_start` di
  `04015.windows.csv` dan `04015.decisions.csv` adalah indeks **interval** pada deretnya sendiri,
  bukan indeks sampel; jembatan ke `s_window_idx` adalah `qrs_cur_sample` dari `04015.rr.csv`
  baris `src_start + 31`. Itu yang dipakai di peta vektor.
- Vektor Fase 8: `rtl/tb/vektor/fase8/04015.fase8.*`, **semuanya 32 bit satu kata per baris**
  (8 digit hex, dibaca unsigned; tidak ada kata >= 2**31 yang dibaca signed):
  `rr.hex` 2595 kata `{2'b0, mark[1:0], rr_ms[15:0]}`, `sample.hex` 2595 kata, `gold.d.hex`
  602*31 kata (`d & 0x1FFF`), `gold.bins.hex` 602*4 kata (kata 4r+j memuat bin 4j..4j+3),
  `gold.code.hex` 602*3 kata (tinggi, tengah, rendah dari kata kode 92 bit), `gold.raw.hex`
  588*3 kata, `map.marked.hex` 638*2 kata, `map.raw.hex` 624*2 kata.
  Tata letak kata kode, bit 0 di kanan: `rmssd[17:0]`, `ratio[34:18]`, `ent[49:35]`,
  `mean_q[76:50]`, `cnt50[82:77]`, `pnn50[91:83]`.
- Penyesuaian format ini dilakukan karena `$readmemh` Icarus **memotong** kata yang lebih lebar
  dari memori (baris 25 digit hex dimuat ke memori 96 bit -> digit depan hilang, terlihat sebagai
  `%Warning: Excess hex digits`). Satu kata 32 bit per baris menghilangkan seluruh kelas galat itu.
  Catatan untuk siapa pun yang menulis testbench di repo ini: `bins` adalah kata kunci
  SystemVerilog (covergroup), Icarus menolaknya sebagai nama sinyal; pakai `bin_tab`/`binw`.

## 3. Pemilihan bentuk simpul (diverifikasi lebih dulu di Python, bukan ditebak)

Skrip scratch `~/.hermes/cache/scratch/fase8/verify_nodes.py` mengukur bentuk integer tiap simpul
terhadap kolom emas 602 baris. Keluaran nyata:

```
rows differing  d              : 0
rows differing  16 bins        : 0
rows differing  cnt50          : 0
rows differing  pnn50 code     : 0
code rows diff  rmssd          : 0 worst LSB 0
code rows diff  ratio          : 0 worst LSB 0
code rows diff  ent            : 49 worst LSB 1        <- tabel log2 16 bit (ditolak)
code rows diff  mean_q         : 0 worst LSB 0
codes over 1 LSB               : {'rmssd': 0, 'ratio': 0, 'ent': 0, 'mean_q': 0}
```

`ent_prec.py` menunjukkan 49 selisih entropi itu bukan simpul di batas pembulatan
("rows with frac exactly 0.5: 0", jarak terkecil ke batas 0.0024 LSB) melainkan galat tabel
log2 16 bit; dengan log2 Q24 dan term Q48 selisihnya 0. Bentuk final:

| simpul | bentuk final | selisih kode vs emas (602 baris) |
|---|---|---|
| `d`, `d*d`, `sum_d2` | eksak, akumulator 29 bit | 0 |
| `cnt50` | 31 pembanding eksak pada magnitudo | 0 |
| pNN50 Q1.8 | tabel `PNN[c] = bulat-setengah-genap(c*256/31)` | 0 |
| mean31 Q19.8 | `q0=(x*C31)>>29` (konstanta rencana 17318417) + lipatan sisa negatif + tabel `FRAC[r]` | 0 |
| rmssd Q10.8 | akar digit 29 langkah atas `rad=(sum_d2*31)<<24`, lalu bulat-setengah-genap `R/496` | 0 |
| ratio Q1.16 | `R<<9` dibagi `31*sum_rr` potong-ke-nol, lalu satu tahap bulat-setengah-genap | 0 |
| 16 bin | palang silang eksak `A[k]-A[k+1]`, bin terakhir inklusif | 0 |
| entropi Q1.14 | tabel 17 entri `term(c)=c*(4-log2 c)/64` (log2 Q24, term Q48), geser akhir >>34 bulat-setengah-genap | 0 |

Bentuk literal rencana (akar atas mean_q yang sudah dibulatkan, rasio potong-ke-nol, tabel log2 16
bit, mean_q *floor* penuh) diukur juga: 13 / 293 / 49 / 213 baris berbeda tepat 1 LSB, 0 kode di atas
1 LSB. Itu lulus gerbang tabel tetapi tidak lulus garis 0,5/0,75 LSB di blok bagian 12, jadi bentuk
yang dipakai adalah tabel di atas; setiap penyimpangan dicatat di kepala `rtl/features.sv`.

## 4. Implementasi dan lint

Keputusan arsitektur yang mahal waktu simulasi: setiap larik di RTL diindeks genvar (waktu
elaborasi) atau lewat loop atas vektor padat. Indeks runtime ke larik unpacked di Icarus menjadi
rantai prioritas dan sekitar 30x lebih lambat; probe awal (jaringan sortir 512 penukar atas larik
unpacked) 20.000 siklus memakan 29 s, tidak muat untuk 638 jendela x 2 lengan.

Perintah lint dan keluaran:

```
cd rtl-synthesis
./run_lint.sh ../rtl/features.sv features ../rtl/afib_lite_pkg.sv
run_lint.sh: top=features sources=2 timing=0
lint clean: top=features sources=2 (.../verilator_bin)
```

Waiver lint: dua, keduanya tercakup komentar di dalam berkas.
1. `UNUSEDSIGNAL` pada bit 0,1,2,4 dari `i_arm_select` (dipakai classifier.sv dan top level).
2. `UNUSEDSIGNAL` pada bank kotak putih (`pnn50_q`, `ovf_cnt_q`, `rej_cnt_q`, `win_cnt_q`,
   `d_mullo_q`, `bin_q`) yang dibaca testbench secara hierarkis, konvensi yang sama dengan
   `rr_series.sv` Fase 6.

## 5. Testbench `rtl/tb/tb_fitur.sv` dan TIGA BUG RTL yang ditemukannya

Bentuk testbench: satu jalan memuat keempat lengan (A berpenanda, B mentah) dan **mengulang
tiap lengan dua kali**, jadi determinisme diukur di dalam simulasi yang sama:
`PH_RST0 -> A1 -> RST1 -> B1 -> RST2 -> A2 -> RST3 -> B2 -> DONE`. Testbench menyalurkan
**seluruh 2595 interval** dengan tanda masing-masing, jadi penyaring deret berpenanda dikerjakan
DUT sendiri (bukan di testbench). Setiap emisi dibandingkan dengan baris peta
(`map.marked.hex`/`map.raw.hex`); untuk baris beremasan penuh, 31 `d`, 16 bin, cacah pNN50, kode
pNN50 dan empat tap dibandingkan bit-per-bit; untuk lengan mentah, empat kode dibandingkan dengan
toleransi 1 LSB dan jumlah baris di atas 1 LSB dihitung. Digest FNV-1a atas **semua** nilai tiap
emisi (termasuk seluruh 31 `d` dan 16 bin dari kotak putih) dibandingkan antara dua jalan.

Perintah dan keluaran (mode pendek dulu, biaya simulasi Icarus):

```
cd rtl-synthesis
./run_sim.sh ../rtl/tb/tb_fitur.sv ../rtl/afib_lite_pkg.sv ../rtl/features.sv \
    -- +VECTOR=../rtl/tb/vektor/fase8 +LIMIT=60
```

Jalan pendek pertama (sebelum perbaikan) bersih untuk peta/kind/idx/ovf/rej tetapi:
`d mismatches = 7`, `histogram mismatches = 7`, `four code mismatches = 7`,
`pnn50 code mismatch = 59 dari 92`, `d_ent = x`. Tiga bug RTL nyata, semuanya ditemukan
testbench dan semuanya di berkas milik fase ini:

1. **`dvec_q` tergeser tumpang tindih.** `dvec_q <= ... << (cnt_q[4:0] - IDX_ONE) * W_D5`
   menghitung offset dalam konteks 5 bit, jadi 3*13=39 melingkar jadi 7: field `d` saling
   menimpa (terukur `dvec_q[12:0]=7952` vs emas 16, field teratas 0 vs emas 8184) padahal
   `sum_d2`/`rmssd`/`mean_q` sudah eksak. Perbaikan: `W_D9 = W_D[8:0]` (9 bit, cukup untuk
   30*13=390) dan `doff_w = ({3'd0,cnt_q} - 9'd1) * W_D9`.
2. **`abin_w[16]` di luar jangkauan.** Larik dideklarasikan `[0:CNT_EDGE]` = 0..15, tetapi
   `bins_w[15] = abin_w[15] - abin_w[16]` membaca indeks di luar jangkauan -> `x` -> `bins_w[15]=x`
   -> `ent_sum_w = x` -> **`d_ent = x` untuk setiap jendela** dan `bin_q[15] = x`.
   Perbaikan: larik `[0:CNT_CORE]` (0..16) dan `abin_w[16] = 0` eksplisit (sisi terakhir
   histogram rencana memang inklusif, jadi `bin[15] = A[15] - A[16] = A[15]`).
3. **Kode pNN50 dibaca satu cacahan terlalu awal.** `pnn50_q <= PNN_FLAT[cnt50_q*W_FRACT +: W_PNNT]`
   diletakkan di siklus `S_DIFF` terakhir, di mana `cnt50_q` belum menerima pembanding ke-31
   (kenaikan itu mendarat di tepi yang sama). Terukur: emisi 1 `pnn=107` vs emas `116` (tepat satu
   langkah), dan hanya baris yang `|d|` terakhirnya > 50 ms yang terpengaruh. Perbaikan: pembacaan
   dipindah ke `S_BINS`, saat `cnt50_q` sudah final. `m_ev_val` (cacah) tidak pernah salah.

Setelah perbaikan, jalan pendek yang sama:

```
tb_fitur: arm A golden rows compared = 92 of 602, pass 2 = 92
tb_fitur: d mismatches          = 0
tb_fitur: histogram mismatches  = 0
tb_fitur: pNN50 count mismatch  = 0
tb_fitur: pNN50 code mismatch   = 0
tb_fitur: four code mismatches  = 0
tb_fitur: sample_end mismatch   = 0
tb_fitur: ev_kind mismatch      = 0
tb_fitur: windows dropped (ovf) = 0
tb_fitur: mismatches = 0 out of 14
tb_fitur: SMOKE OK
```

Lint ulang setelah ketiga perbaikan: `lint clean: top=features sources=2`.

## 6. Kontrol mutu testbench (dari catatan mandor fase)

`$fatal` di setiap jalur: setiap pelanggaran memanggil `$fatal(1, ...)` sehingga `rc != 0`;
`$finish` hanya di jalur lulus. Syarat lulus bukan lagi "tidak ada penghitung mismatch" saja,
tetapi seluruh keadaan akhir: fase mencapai `PH_DONE` di dalam anggaran siklus, cacah emisi
per lengan tepat (638/638/624/624), cacah baris emas yang benar-benar dibandingkan tepat
(602/602/588/588), kedua digest sama, `d_valid` satu per jendela, `ovf_cnt_q = 0`,
`rej_cnt_q = 624 lengan B`, dan `win_cnt_q` akhir.

Guard X dua lapis:
1. Sentinel saat pemuatan: ujung (dan tengah) ke-8 tabel emas diperiksa `$isunknown` sebelum
   dipakai sebagai oracle; berkas hilang/pendek langsung `$fatal`.
2. Per emisi: kata emas, kata peta, dan kotak putih yang X dihitung di `mis_x`, dan
   `mis_x == 0` ikut menjadi syarat lulus.

Perbaikan penting yang ditemukan sendiri saat memeriksa catatan itu: **digest FNV-1a jalan penuh
pertama (yang saya kutip ke mandor) tercetak `xxxxxxxx`**, karena emisi tanpa baris emas membaca
`cod_tab[3*FFFFFFFF...]` di luar jangkauan. `x !== x` bernilai **0** di Verilog, jadi uji
determinisme dua jalan itu hampa. Digest sekarang hanya memuat nilai hidup ditambah kata emas
saat ada barisnya (`ev_vw` dipaksa 0 jika tidak ada baris), dan digest yang X ditolak eksplisit.

Kontrol negatif, semuanya pada **salinan vektor di luar repo** (`~/.hermes/cache/scratch/fase8/nc1..nc6`),
direktori `rtl/tb/vektor/fase8/` tidak disentuh:

| kontrol | kerusakan | rc | bukti mentah |
|---|---|---|---|
| nc1 | satu kata `d` emas (kata 0) dirusak `00000010` -> `00000011` | 1 | `d mismatches = 1`, `mismatches = 1 out of 4`, `FATAL ... smoke comparison failed` |
| nc2 | `gold.d.hex` dipotong 100 dari 18662 kata | 1 | `FAIL 1 vector tables are X at their ends`, `FATAL ... golden vectors missing or short` |
| nc3 | `map.marked.hex` dipotong 20 dari 1276 kata | 1 | `FAIL 1 vector tables are X at their ends`, `FATAL ...` |
| nc4 | direktori vektor tidak ada | 1 | `FAIL 8 vector tables are X at their ends`, `FATAL ...` |
| nc5 | X di TENGAH `gold.bins.hex` (baris 5..8 = baris emas 1) | 1 | `oracle words unknown = 2`, `histogram mismatches = 1` |
| nc6 | X di TENGAH `map.marked.hex` (sample_end + baris emisi 4) | 1 | `oracle words unknown = 1`, `sample_end mismatch = 1` |

nc5 dan nc6 ada khusus untuk dua jebakan yang disebut mandor: (a) larik yang dilewati di mode
yang dijalankan, dan (b) `$readmemh` yang meninggalkan X sehingga `X !== X` tidak terhitung beda.
Di nc6 baris peta yang X akan membuat emisi itu *dilewati* secara diam-diam kalau tidak ada
`$isunknown(ev_row32)`.

Mode pendek (T=+LIMIT) mencetak **lima baris SKIP eksplisit** untuk gerbang yang tidak diuji dan
hanya mencetak `SMOKE OK, the full gate is NOT claimed`; tidak ada gerbang yang dilonggarkan
diam-diam.

## 7. Keadaan sekarang dan yang belum

Sudah diverifikasi: bentuk simpul vs kolom emas di Python (0 beda `d`/16 bin/`cacah` pNN50/kode
pNN50, 0 LSB empat kode di 602 baris); lint bersih `features` dan `tb_fitur`; jalan penuh
`mismatches = 0 out of 1190` + `PASS` (log `sim-full.log`, TB sebelum pengerasan kontrol);
jalan pendek dengan guard baru 0 beda dan digest nyata; enam kontrol negatif semuanya rc=1.

Belum:
- [x] dua jalan penuh ber-timestamp dengan `cmp`/`sha256`
- [x] `rtl-synthesis/reports/LAPORAN-FASE8.md`
- [x] sha256 berkas keluaran

## 8. Dua jalan penuh (determinisme) dan sha256

```
./run_sim.sh ../rtl/tb/tb_fitur.sv ../rtl/afib_lite_pkg.sv ../rtl/features.sv \
    -- +VECTOR=../rtl/tb/vektor/fase8 > reports/fase8/jalan-penuh-1-20261021-004418.log 2>&1
./run_sim.sh ../rtl/tb/tb_fitur.sv ../rtl/afib_lite_pkg.sv ../rtl/features.sv \
    -- +VECTOR=../rtl/tb/vektor/fase8 > reports/fase8/jalan-penuh-2-20261021-004418.log 2>&1
cmp jalan-penuh-1-20261021-004418.log jalan-penuh-2-20261021-004418.log   # bersih
sha256sum jalan-penuh-*.log
```

Keduanya: `rc=0`, `PASS`, `mismatches = 0 out of 1190`, `oracle words unknown = 0`,
`arm B rows over 1 LSB = 0 (worst 1 LSB)`, digest A `99b99f28`, digest B `4499c5f6`
(sama di kedua jalan dan sama antara jalan 1 dan jalan 2 di dalam satu simulasi).
`cmp` bersih dan sha256 kedua log identik: `31e64f4bd314dae11252a26903880d8be14ec587391fe033d093f7850b369b13`.
Tidak ada baris `FATAL` di keduanya (`grep -c FATAL` = 0 untuk masing-masing), jadi `rc=0` di sini
memang berarti lulus, dan kontrol negatif bagian 6 membuktikan jalur gagal memberi `rc=1`.
Biaya: ≈ 4,57 juta satuan waktu (≈ 9 menit dinding) per jalan penuh.

sha256 berkas yang saya tulis (dari akar repo):

```
a6de59095fbc15a09549fc1c0518c571446274df2599e3b35f9269c4c69b2675  rtl/features.sv
26da322cbefbeb869255fce2dd877826aec6a608f8db004de104c8249edd9690  rtl/tb/tb_fitur.sv
026ab9e0cf6038a69c2284a91296c6b935db5f11ac638bbfdd5919181875c499  rtl/tb/vektor/fase8/ekspor_vektor_fase8.py
90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5  model/rantai-afib-lite/rantai.py
31e64f4bd314dae11252a26903880d8be14ec587391fe033d093f7850b369b13  reports/fase8/jalan-penuh-1-20261021-004418.log
31e64f4bd314dae11252a26903880d8be14ec587391fe033d093f7850b369b13  reports/fase8/jalan-penuh-2-20261021-004418.log
```

sha256 kesepuluh berkas vektor ada di `rtl/tb/vektor/fase8/04015.fase8.manifest.json`, dan daftar
lengkap seluruh berkas fase ini di `rtl-synthesis/reports/fase8/SHA256.txt`.

Catatan jujur: entri `04015.fase8.manifest.json` di dalam `files_sha256` manifest itu sendiri
berisi hash manifest versi sebelumnya (berkas itu ikut terjaring pola glob), jadi entri itu tidak
pernah cocok dengan dirinya sendiri. Sepuluh berkas vektor lainnya diverifikasi cocok saat
dibaca ulang. Cacat kosmetik eksportir, bukan masalah data gerbang.
