# LAPORAN FASE 5 — bench event-stream dan verifikasi independen

Status: **sebagian lulus, sebagian gagal, dua gerbang tidak dapat dijalankan**. Semua angka di
bawah adalah keluaran mentah dari run terakhir, pada revisi DUT yang dicatat di §1.

## 0. Keadaan berkas yang saya temukan (tabrakan sesi — baca ini dulu)

Saat saya mulai, `rtl/peak_detect.sv` **sudah ditulis ulang oleh sesi lain** yang mengklaim
kepemilikan eksklusif atas berkas itu, dengan spesifikasi tertulisnya sendiri:

- `rtl-synthesis/reports/fase5/SPEC-TERKUNCI-FASE5.md` (2 025), `IMPLEMENTASI-PROGRES.md` (22:39),
  `peak_detect.sv.sesi-lain-9c680d12.bak` (22:32 — salinan mereka atas berkas saya),
  `lint-peak_detect-01..04.out`, `siapkan_vektor_fase5.out`.
- Spesifikasi mereka: `rtl/peak_detect.sv` milik mereka, `rtl/tb/tb_puncak.sv` bench mereka,
  dan `rtl/*.sv` lain **dilarang disentuh** (termasuk `afib_lite_top.sv`).

Saya **tidak menimpa** berkas itu. Dua penulis pada satu berkas menghasilkan dua versi tanpa galat,
dan berkas itu sedang mereka sunting saat laporan ini ditulis (mtime 23:05:11, dan mereka masih
menjalankan lint iteratif). Jadi:

- **Butir 1 brief (isi `rtl/peak_detect.sv`) tidak saya kerjakan**: berkasnya bukan milik saya, dan
  menggantinya akan (a) menghapus pekerjaan sesi lain, (b) membuat gerbang census 4 arah yang mereka
  sudah tutup menjadi tidak mungkin lagi (versi daftar-porta-beku tidak dapat menjalankan aturan
  gelombang T — lihat §3.1). Implementasi saya sendiri tidak pernah lint bersih sebelum tertimpa;
  salinannya hanya tersisa di `.bak` milik mereka dan **bukan** deliverable (catatan mereka: 8 galat
  sintaks saat mereka menyalinnya).
- **Butir 2** (`afib_lite_pkg.sv`): tambahan Group 8 (nama baru, tidak ada nilai grup 1..7 yang
  berubah) sudah ada di berkas. Regresi `tb_pkg_konstanta` tetap **lulus** (68 checks, 0 bit
  differences) — jadi tambahan itu tidak merusak apa pun.
- **Butir 3 (bench event) saya kerjakan penuh**: `rtl/tb/tb_peak_detect.sv`, nama berbeda dari
  `tb_puncak.sv` milik mereka, jadi tidak bertabrakan. Bench ini **independen**: vektornya saya
  generate sendiri dari CSV emas, bukan dari vektor mereka.
- **Butir 4/5**: `rtl/tb/vektor/fase5-verifikasi-aviv/` dan laporan ini.

Bukti bahwa vektor saya memang sama dengan mereka (silang-cek dua generator independen): untuk
kolom yang sama, sha256 identik — `04015.puncak.pos.hex` `ef950fbf…`, `pv.hex` `3dc8e376…`,
`pkf.hex` `5239077e…`, `i1.hex` `e4518eb1…`, `ambang_state` `e8032e25…`. CSV sumber
`04015.peaks.csv` sha256 `500e6c0b8065544a220bc6c9a08fe64669137c7aa97d2e9a33c6bdf8d31e13a9`.

## 1. Gerbang yang saya jalankan, keluaran mentah

DUT: `rtl/peak_detect.sv` sha256 `186e964b902916b083f38e29beb5b17d6e3575f0562f8a188598a34b9c981d42`
(identik sebelum dan sesudah run). Bench: `rtl/tb/tb_peak_detect.sv` sha256
`39fd5e1125b099a1623245aa4e1078d13c07883ed9022a2ace3214f0bb3aa19d`.
Rekaman: 450000 sampel, `+LIMIT` tidak dipakai (jalur default = seluruh rekaman).

| Gerbang | Hasil mentah | Putusan |
|---|---|---|
| Jumlah event = 4777 | `expected peaks 4777, events seen 4777, introspection pulses 4777` | **LULUS** |
| Kata diterima = 450000 | `accepted words 450000` | **LULUS** |
| Nilai puncak (`m_ev_val`) per event | `val 0` mismatch dari 4777 | **LULUS** |
| Indeks puncak (`m_ev_idx`) per event | `idx 5` mismatch dari 4777 | **GAGAL** (5) |
| Kind bus (`m_ev_kind`) | `kind 1` mismatch dari 4777 | **GAGAL** (1) |
| Kelas 4 arah (flag word 11) | `class checkpoints 4777, class mismatches 15` | **GAGAL** (15) |
| Ambang `d_thr` = kolom `i1` | `d_thr 509` mismatch dari 4777 | **GAGAL** (509) |
| `d_pk` = kolom `filtered_peak` | `d_pk 0` mismatch dari 4777 | **LULUS** |
| Jalur kata diteruskan apa adanya | `forwarded word mismatches idx 0 data 0 user 0 last 0` | **LULUS** |
| Determinism | 2 run byte identical, md5 `b1e01b7ac92ea3f814dcfabb8670f771` | **LULUS** |
| `o_beat_count` = 2596 | `o_beat_count 2600` | **GAGAL** (+4) |
| `ambang_state` 9 dari 9 | got `[29, 9, 112, 6, 106, 0, 27, 1196, 2586]` want `[29, 6, 112, 6, 106, 0, 26, 1202, 2586]` — 3 dari 9 berbeda (`cari_mundur` 9↔6, `penanda` 27↔26, `langkah` 1196↔1202) | **GAGAL** (3/9) |
| Census 4 arah | got `{qrs 2591, search_back 9, rejected_t 1911, noise 266}` want `{2590, 6, 1909, 272}` | **GAGAL** |
| Checkpoint ambang dibandingkan | `threshold checkpoints compared 4777 (d_thr) + 4777 (d_pk) = 9554`, plus 1 checkpoint `ambang_state` = **9555** | informasi |
| `m_overflow` | `m_overflow cycles 0` (0 diharapkan; dilaporkan, tidak digerbang) | informasi |
| Lint bench | `run_lint.sh ../rtl/tb/tb_peak_detect.sv tb_peak_detect …` → **exit 0, lint clean** | **LULUS** |
| Lint seluruh rantai | `./run_lint.sh --chain` → **exit 1**, 4 × `%Warning-PINMISSING: ../rtl/afib_lite_top.sv:398` untuk `s_hp`, `s_besaran`, `d_dbg`, `d_dbg_valid` | **GAGAL** |
| Sintesis Yosys (sky130) | lihat §6 | — |

### 1.1 Titik divergensi pertama (bukti mentah)

Mismatch pertama di `d_thr` muncul pada **event 983**, yaitu tepat sesudah peristiwa penelusuran
balik pertama (event 921 dan 982 adalah dua baris walk pertama). Mismatch terakhir yang dicetak:

```
tb_peak_detect: d_thr ev 983 got 195877376 want 157394329
tb_peak_detect: d_thr ev 984 got 168900049 want 167295513
tb_peak_detect: d_thr ev 985 got 166238060 want 164633524
tb_peak_detect: d_thr ev 986 got 176952761 want 149236087
tb_peak_detect: d_thr ev 987 got 172991782 want 145275108
tb_peak_detect: idx  ev 1791 got 172277 want 172509
tb_peak_detect: idx  ev 1792 got 172277 want 172647
tb_peak_detect: kind ev 1836 got 1 want beat 0
```

Tiga pengamatan independen menunjuk satu penyebab: `cari_mundur` 9 lawan 6 (tiga penelusuran balik
berlebih), `o_beat_count` 2600 lawan 2596 (+4 denyut), dan `langkah` 1196 lawan 1202 (urutan langkah
RR bergeser). Semua 509 penyimpangan `d_thr` berada **setelah** walk pertama; event 0..920 cocok
penuh (smoke `+LIMIT=20000`, 216 event, 0 mismatch di semua kolom). Jadi lokusnya adalah jalur
`search_back`, bukan pemindai puncak, bukan pengali silang 83/50 itu sendiri.

## 2. Apa yang terverifikasi dengan baik

- Jumlah event, nilai puncak, penanda introspeksi, `d_pk`, jalur kata, dan determinisme: lulus penuh.
- Pemindai puncak dan ambang adaptif sebelum walk pertama: bit-eksak (216 event pertama, 0 mismatch).
- Peta ulang census dari flag word saya buktikan benar terhadap kolom emas
  (`census_4way_from_flags` == `census_4way`, `match True`), jadi pembacaan kelas 4 arah dari bus
  introspeksi sahih; yang gagal adalah RTL-nya, bukan pembacaannya.

## 3. Penyimpangan dari rencana dan dari brief (temuan, bukan sesuatu yang saya paksa)

### 3.1 Daftar porta beku tidak dapat memenuhi gerbang census
`rtl/afib_lite_pkg.sv`/`afib_lite_top.sv` tidak membawa `hp` dan deret kemiringan ke tahap ini, dan
aturan gelombang T (`t_rejected`, 1909 dari 4777 puncak) membutuhkannya. Dengan daftar porta beku,
`ditolak`, `diperiksa`, `diterima_pita`, `berisiko` tidak mungkin dihasilkan, jadi census 4 arah
mustahil. Sesi lain menyelesaikannya dengan **dua porta masukan tambahan** (`s_hp`, `s_besaran`) dan
**dua porta introspeksi tambahan** (`d_dbg`, `d_dbg_valid`) plus parameter `LAT_CYCLES`. Itu pilihan
kontrak yang berbeda dari brief saya, dan konsekuensinya nyata:

### 3.2 Akibatnya gerbang "lint --chain exit 0" tidak dapat lulus
Karena `afib_lite_top.sv` tidak menyambungkan empat porta baru itu, dan spesifikasi sesi lain
melarang menyentuh berkas itu, `./run_lint.sh --chain` **exit 1** dengan 4 `PINMISSING`. Gerbang
brief ("lint clean, exit 0") dan gerbang census **tidak dapat dipenuhi bersamaan** tanpa mengubah
`afib_lite_top.sv`. Ini keputusan untuk agen induk: menyambungkan porta di top (menyentuh berkas
milik sesi lain) atau menerima `--chain` merah.

### 3.3 Bus event tidak punya kosakata untuk census 4 arah
`W_EVKIND=3` mendefinisikan 0 none, 1 QRS, 2 peak candidate, 3 RR, 4 decision window, 5 lost sample.
Tidak ada kode untuk "T wave rejection" atau "noise". Karena itu bench saya membaca kelas 4 arah dari
word 11 `d_dbg` (b0 `signal`, b2 `t_rejected`, b3 `search_back`) — pemetaan yang sudah diverifikasi
sama dengan kolom `event_kind` di §2. Lima dari enam baris walk membawa `signal=0`, jadi bit walk
harus diuji lebih dulu; itu sebabnya pemetaan "is_qrs" naif salah dan saya perbaiki.

### 3.4 Dua baris walk membawa indeks denyut, bukan indeks puncak
`04015.peaks.csv` menyimpan dua indeks untuk baris walk: `sample_index` 91681/172509 lawan
`qrs_sample_index` 91611/172277. Revisi terpasang membawa indeks **denyut** pada baris walk (1 dari 5
penyimpangan `idx` terkonfirmasi begitu: `idx ev 1791 got 172277 want 172509`). Brief meminta
"index plus value equal for every one of the 4777" terhadap `sample_index`; konvensi yang terpasang
berbeda pada baris seperti itu.

### 3.5 Jadwal (latensi) terukur — penyimpangan dari plan 4.7/4.8
Plan menghargai 6 siklus per puncak untuk jalur ambang, antrean dua pembanding untuk jendela 55
sampel, dan pemindai serial 51 siklus untuk maksimum absolut. Implementasi terpasang: **satu sampel
per siklus** diterima, seluruh jalur per-puncak **kombinasional**, event muncul **1 siklus**
(`LAT_CYCLES=1`) sesudah sampel yang melahirkannya; `m_ev_valid`/`d_valid` terdaftar dari `peak_w`.
Terukur: 450000 siklus untuk 450000 sampel (1 sampel/siklus), 0 siklus tunggu. Ini penyimpangan
area/timing yang dilaporkan, bukan penyimpangan paritas.

### 3.6 Diagnostik iverilog (bukan bug)
`../rtl/peak_detect.sv:602,603,609: warning: returning 'bx for out of bounds array access
deret_q[-1] / antre_q[-1] / rih_q[-1]` — akses itu berada di dalam ternary `(gd == 0) ? … : …`, jadi
nilai `'bx` tidak pernah terpilih. Kosmetik, tetapi iverilog mencetaknya di setiap kompilasi.

## 4. Simulator: iverilog terlalu lambat untuk tahap ini
iverilog mencapai ~39% rekaman dalam 470 s (≈8 ms/siklus, ≈20 menit per rekaman), jadi seluruh
rekaman dijalankan dengan simulasi terkompilasi Verilator:

```
verilator --binary --timing -Wno-fatal -j 2 --top-module tb_peak_detect \
  ../rtl/afib_lite_pkg.sv ../rtl/peak_detect.sv ../rtl/tb/tb_peak_detect.sv -o tbpk
./tbpk +VECTOR=… +GOLD=…          → 3.0 s per rekaman 450000 sampel
```

`run_sim.sh`/iverilog tetap dipakai untuk smoke `+LIMIT=20000` (216 event, 0 mismatch), jadi bench
ini tetap bench rumah yang bisa dijalankan script repo.

## 5. Yang tidak dapat saya jalankan atau tidak dapat diverifikasi

1. `rtl/peak_detect.sv` versi daftar-porta-beku: **tidak ada** (lihat §0). Karena itu "census 4 arah
   dari bus event" versi brief tidak dapat diukur pada artefak apa pun.
2. `spki`, `npki`, `spkf`, `npkf` tidak punya porta introspeksi; keadaan ambang hanya terverifikasi
   lewat `d_thr` (= `i1`, fungsi keduanya) per puncak dan lewat 9 unsur `ambang_state` di akhir
   rekaman, bukan per checkpoint `threshold_state.csv`.
3. Word 9/10/12/13 `d_dbg` (`pv`, `kem`, `pos`, rail) tidak saya gerbangi: tidak ada kolom emas untuk
   rail, dan `pv`/`pos` sudah terwakili `m_ev_val`/`m_ev_idx`.
4. Verifikasi ulang klaim "algoritme bit-eksak" milik sesi lain
   (`~/.hermes/cache/scratch/fase5/rujukan_fase5.py`) tidak saya jalankan: itu artefak mereka, dan
   yang penting bagi saya adalah RTL-nya, bukan pengendara Python-nya.

## 6. Sintesis

Perintah: `./run_synth.sh ../rtl/peak_detect.sv peak_detect` (pustaka
`sky130_fd_sc_hd__tt_025C_1v80.lib`, otomatis membaca `afib_lite_pkg.sv`).

**Belum selesai saat laporan ini ditulis — gerbang ini belum dapat saya nyatakan lulus atau gagal.**
Setelah 20 menit proses masih berada di pass `TECHMAP` (`reports/peak_detect.native.20261020.log`
2,5 MB dan tumbuh; `%cpu` yosys 99,9%). Penyebab yang terlihat: bentuk silang `83/50` di jalur RR
memaksa perkalian lebar (32 bit × 16 bit, lebih dari satu) dipetakan ke gerbang lalu ke pustaka
sky130, dan `abc -liberty` sesudahnya adalah bagian termahal. Jadi belum ada angka sel, flip-flop,
atau luas yang bisa saya kutip.

Proses ini saya serahkan ke agen induk lewat `process_manage` (handoff). Keluarannya:
`rtl-synthesis/reports/fase5-verifikasi-aviv/synth.out` dan blok `stat -liberty` di ujung
`reports/peak_detect.native.20261020.log`. Sebagai pembanding, tahap lain di repositori ini memakai
jalur yang sama dan selesai (mis. `bandpass.native.20261020.json` 23 MB), jadi lambatnya khas tahap
ini, bukan khas mesin.

## 7. Cara reproduksi

```
cd rtl-synthesis && source /home/avivsabilalm/eda/env.sh
# vektor (dari CSV emas; tidak pernah disunting tangan)
/home/avivsabilalm/.venvs/jupyter/bin/python \
  rtl/tb/vektor/fase5-verifikasi-aviv/ekspor_vektor_puncak.py
# lint bench
./run_lint.sh ../rtl/tb/tb_peak_detect.sv tb_peak_detect ../rtl/afib_lite_pkg.sv ../rtl/peak_detect.sv
# smoke (iverilog) dan rekaman penuh (terkompilasi)
./run_sim.sh ../rtl/tb/tb_peak_detect.sv ../rtl/afib_lite_pkg.sv ../rtl/peak_detect.sv -- \
  +VECTOR=../rtl/tb/vektor/fase5-verifikasi-aviv +GOLD=<rtlplan2>/vektor +LIMIT=20000
verilator --binary --timing -Wno-fatal -j 2 --top-module tb_peak_detect -Mdir <scratch>/vpk_aviv \
  ../rtl/afib_lite_pkg.sv ../rtl/peak_detect.sv ../rtl/tb/tb_peak_detect.sv -o tbpk
<scratch>/vpk_aviv/tbpk +VECTOR=… +GOLD=…
```

Log mentah: `rtl-synthesis/reports/fase5-verifikasi-aviv/{lint-bench,lint-chain,verilator-build}.out`,
`vrun1.log`, `vrun2.log`, `synth.out`.
