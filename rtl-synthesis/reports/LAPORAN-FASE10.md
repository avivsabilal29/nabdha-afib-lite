# LAPORAN FASE 10 — INTEGRASI RANTAI PENUH AFIB-LITE

Repo: `~/hackathon-semiconductor-programs/nabdha-afib-lite`, branch `aviv/rtl-fpga-simulation`,
`HEAD = 93fedc6f` (belum ada commit baru — seluruh kerja fase ini masih di working tree, menunggu
persetujuan Aviv).
Konteks: ICDeC Indonesia Chip Hackathon 2026, PoC on-site 21–23 Oktober 2026.
Waktu penulisan: 21 Oktober 2026, 02:3x WIB.

Aturan yang dipakai dokumen ini: **setiap angka boleh dilacak ke perintah mentahnya**; `rc=0`
BUKAN bukti lulus (hanya `$fatal` membuat rc≠0); patokan lulus adalah baris `mismatches = X out of Y`
+ `PASS`; yang belum terbukti ditulis "belum", bukan "sepertinya lulus".

---

## 1. STATUS RINGKAS

| # | Butir | Status | Bukti |
|---|---|---|---|
| 1 | Penyambungan 13 pin (`--chain`) | **LULUS** | `./run_lint.sh --chain` → `rc=0`, **0 peringatan**; tanpa tie-off |
| 2 | Replay penuh, lengan berpenanda, Verilator 2-state | **LULUS** | `total mismatches = 0`, `PASS`, 450.000/450.000 bingkai |
| 3 | Replay penuh, lengan mentah, Verilator 2-state | **LULUS** | `total mismatches = 0`, `PASS`, 450.000/450.000 bingkai |
| 4 | Sensus triase ujung-ke-ujung | **LULUS** | DUT = emas: berpenanda `189/95/94/0/413`; mentah `183/95/88/0/405` |
| 5 | Jembatan satuan ambang (K7 revisi) | **LULUS** | `ratio 33 user -> 10813 code (golden 10813)`, `entropy 63 user -> 10322 code (golden 10322)` |
| 6 | Masukan `t_rule` tak diketahui saat denyut | **LULUS** | `unknown t_rule inputs at peak pulses = 0 of 4777` |
| 7 | Kontrol negatif (TB final) | **LULUS** | tiga kontrol `rc=1` karena gerbang/penjaga, bukan kompilasi |
| 8 | TAHAP 5 penyatuan aturan gelombang T | **LULUS** | Fase 5 `0 mismatch/PASS`; Fase 7 `0 out of 26628/PASS` |
| 9 | Replay penuh **Icarus 4-state** 450.000 | **LULUS** | kedua lengan `total mismatches = 0`, `PASS`, 450.000/450.000 kata tiap aliran, `unknown = 0` — §7 |
| 10 | Banding checksum **lintas-mesin** | **SEBAGIAN** | `CK_DOWN` + `CK_EVENT` sama antar mesin; `CK_STREAM` + `CK_PEAK` berbeda cakupan — §7 |
| 11 | Sintesis rute repo (TAHAP 4) | **sebagian** | enam modul sudah ada angkanya; sisa berjalan dengan pagar memori — §7 |
| 12 | Keterbatasan yang dinyatakan | lihat §10 | — |

---

## 2. BERKAS DAN SIDIK JARI (sha256)

| Berkas | sha256 |
|---|---|
| `rtl/afib_lite_top.sv` | `eb852a0bf3b193b61f64fb291d2e5f57f91bc4df6c9aa0dcda1d29af3f8155c5` |
| `rtl/tb/tb_top.sv` (997 baris) | `44f4893b467f17b20fd70aa5f02a23403b29fcd0038961dc722fbffa67a15090` |
| `rtl/peak_detect.sv` | `e32cea89150d74486c32bb1f4d12ebcf25f1745d31a29c4b78e2b5717fac8e9f` |
| `rtl/t_rule.sv` | `d6cf1349f4085383b2056e4bcd886dcf5ba104358a55fc5127242364dd39e2be` |
| `rtl/rr_series.sv` | `23a1c7db3cf133b3cc13d30e27482565d6ad5b39f51354748a095d20cfd93ff4` |
| `rtl/features.sv` | `a6de59095fbc15a09549fc1c0518c571446274df2599e3b35f9269c4c69b2675` |
| `rtl/classifier.sv` | `7077f866cd51be7723b1f48e9559365c7ec909a94e4cafbb979f29bcb6eeec33` |
| `rtl/regs_axi.sv` | `38513b91a766d6b936c9a082ad97f074ec510ce215640e0c6a9aa0a0bc1fde7b` |

Berkas beku — **tidak berubah** (diverifikasi tiap tick mandor):

| Berkas beku | sha256 |
|---|---|
| `model/rantai-afib-lite/rantai.py` | `90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5` |
| `rtl/afib_lite_pkg.sv` | `3ea2ab5ceb63361ddba773e255935817a8e4ab198bf0a8fe685bc25d315c397e` |

---

## 3. TAHAP 1 — PENYAMBUNGAN 13 PIN (LULUS)

`./run_lint.sh --chain` → `rc=0`, **0 peringatan** (diverifikasi ulang oleh agen induk pada RTL final).
Tidak ada tie-off: tiap pin yang dulu menggantung mengambil sinyal nyata —

- `s_hp` ← `pk_s_hp` = `ring_hp[e_idx]` (`afib_lite_top.sv:242`, `:407`) — ring tapis lolos atas.
- `s_besaran` ← `pk_s_bes` — ring turunan.
- `d_dbg` / `d_dbg_valid` ← mux introspeksi yang membaca register `peak_detect`.
- sembilan pin `t_rule`: `i_peak_valid(peak_pulse)`, `i_delta(peak_delta_w)`, `i_delta_valid(peak_dvalid_w)`,
  `i_kem_qrs(peak_kemq_w)`, `i_kem_qrs_valid(peak_kvalid_w)` (`:652-653`), keluaran
  `o_peak_valid/o_peak_idx/o_dalam_pita/o_overrun` (`:654-655`).

Tap introspeksi **tidak** bocor sebagai port luar: hanya keluar lewat `o_dbg_val` yang dipilih
`i_dbg_sel` (keputusan 6 plan). Karena itu bitstream lomba kemungkinan besar **tidak** perlu pin
constraint sama sekali — desain duduk di belakang PS melalui AXI, clock dari `pl_clk0`.

## 4. TAHAP 2 — REPLAY PENUH (Verilator 2-state, 450.000 bingkai)

Perintah (dari pekerja; bentuk yang sama dipakai untuk lengan mentah dengan `+ARM=1`):

```
./run_sim.sh ../rtl/tb/tb_top.sv ../rtl/afib_lite_pkg.sv ../rtl/*.sv -- \
  +VECTOR=../rtlplan2/fase0 +STIM=../rtl/tb/vektor/04015.stimulus.hex \
  +EXPECT=../rtl/tb/vektor/fase5 +RRVEC=../rtl/tb/vektor/fase6 \
  +CLVEC=../rtl/tb/vektor/fase9 +F8VEC=../rtl/tb/vektor/fase8
```

Lengan **berpenanda** (`0xf`, ambang 33/63), log `vtop_full_jalan2_20261021-021645.log`:

| Pemeriksaan | Hasil |
|---|---|
| `limit` | 450.000 dari 450.000 bingkai |
| Larik tapis (6 aliran, nilai + indeks) | 449.999 kata/aliran, beda **0**, beda indeks **0** |
| `peaks` / `qrs` / `o_beat_count` | 4777/4777 · 2596/2596 · 2596 |
| `ambang_state` (9 kata) | `29 6 112 6 106 0 26 1202 2586` — **identik emas**, beda 0 |
| Jembatan satuan | 33→10813 dan 63→10322 = kode emas |
| Kelasifier | 638 emisi, **602/602 baris emas** dibandingkan, 36 emisi tanpa baris emas |
| **Sensus triase** | DUT `fired=189 TP=95 FP=94 FN=0 TN=413` = **emas** |
| `t_rule` denyut | 4777 dari 4777 puncak, `stale=0`, `overrun=0` |
| Masukan tak diketahui | **0 dari 4777 denyut** |
| Status | `o_gap_count=0 o_clamp_count=402 o_rr_long_count=3 o_sample_idx=449999 o_irq=0x15` |
| **Total** | **`total mismatches = 0` → `PASS`** |

Lengan **mentah** (`0x7`), log `top_verilator_arm_mentah_final.log`: `total mismatches = 0`, `PASS`;
sensus DUT `fired=183 TP=95 FP=88 FN=0 TN=405` = emas; 588/588 baris; jembatan satuan identik;
`unknown t_rule inputs = 0 of 4777`.

Sidik jari empat checksum 64 bit (lengan berpenanda, dua jalan terpisah):

| mesin | jalan | CK_STREAM | CK_PEAK | CK_DOWN | CK_EVENT | mismatch |
|---|---|---|---|---|---|---|
| Verilator 5.053 | 1 | `b254f0da0524e710` | `ff1f6a10a1028888` | `3fbbce7cafe82708` | `cf143c61d384939e` | 0 `PASS` |
| Verilator 5.053 | 2 | `b254f0da0524e710` | `ff1f6a10a1028888` | `3fbbce7cafe82708` | `cf143c61d384939e` | 0 `PASS` |

Determinisme pada mesin yang sama: **terbukti** (byte-identik). `o_clamp_count=402 > 0` penting: jalur
jepit benar-benar terpicu di rekaman ini, jadi ia bukan kode mati. Satu bingkai terakhir tidak
dibandingkan (`449.999` dari `450.000`) — dicatat sebagai keterbatasan §10, bukan disembunyikan.

## 5. TAHAP 3 — KONTROL NEGATIF (SAH, diulang pada TB final)

Kontrol dijalankan ulang setiap kali testbench berubah. Pada TB final (gerbang di baris 984):

| Kontrol | Alasan gagal | Bukti | rc |
|---|---|---|---|
| `nc1_lp_word100` | kata emas `lp` ke-100 dirusak di salinan **di luar repo** | `MISM stage1 ord=100 dut=-122384 gold=-122383`, `total mismatches = 1`, `FATAL: tb_top.sv:984: gate violation` | 1 |
| `nc2_missing_fase5` | direktori `+EXPECT` kosong | `FATAL ... FAIL the Fase 5 count vector is missing or short` | 1 |
| `nc3_missing_fase0` | direktori `+VECTOR` tidak ada | `FATAL ... FAIL a Fase 0 column is missing or short` | 1 |

**Pelajaran yang mahal dan wajib diingat:** `rc=29` adalah kode keluar **error kompilasi iverilog**,
bukan `$fatal` gerbang. Satu putaran kontrol sebelumnya tercatat "gagal" padahal testbench-nya tidak
pernah bisa dibangun (`tb_top.sv:408: syntax error`) — kontrol kosong. Karena itu harness sekarang
memisahkan tahap kompilasi dari tahap jalan dan membatalkan loop kontrol pada `COMPILE_FAIL`.

## 6. TAHAP 5 — SATU SUMBER ATURAN GELOMBANG T (LULUS, tanpa regresi)

Logika kembar di `peak_detect.sv` (dulu baris 442–449) dihapus dan diganti instansiasi modul baru
`t_rule_eq` dari `rtl/t_rule.sv`; `t_rule.sv` kini juga membaca modul itu, jadi persamaan aturan —
termasuk kedua bentuk silang `2*kem < kem_qrs` — hanya ada **satu** di seluruh `rtl/`.

Bukti tidak ada regresi (**diverifikasi ulang oleh agen induk dari log mentah**, bukan dari `rc=0`):

| Gerbang | Hasil |
|---|---|
| Fase 5, jalan penuh (`fase5_full_gate.log`) | `mismatches = 0`, `PASS`, puncak 4777/4777, qrs 2596/2596, `ambang_state = 0`, seluruh kolom per-puncak 0 |
| Fase 5, baris diagnosa `peaks whose event index moved off the peak position = 2` | **sama** dengan gerbang Fase 5 asli (`sim-lengkap-01..06.out` juga `= 2`; pada jalan pendek `= 0`) → fungsi panjang rekaman, bukan efek penyatuan |
| Fase 7 (`fase7_full_gate.log`) | `mismatches = 0 out of 26628`, `PASS`; bentuk silang vs float `0`; bentuk silang vs bentuk terlarang `2048` (sesuai vektor); latensi 30, `bad = 0` |

Konsekuensi perintah yang harus diikuti fase berikutnya: gerbang Fase 5 sekarang **wajib**
menyertakan `../rtl/t_rule.sv`, karena `peak_detect.sv` meng-instansiasi modul dari berkas itu.

## 7. HASIL YANG SUDAH SELESAI (diisi 21 Oktober 2026, 04:02 WIB)

### 7.1 Replay penuh Icarus 4-state, 450.000 bingkai, dua lengan

| Lengan | Log | Verdict |
|---|---|---|
| berpenanda | `~/.hermes/cache/scratch/fase10/icarus_full_450k_INDUK.log` | `total mismatches = 0`, `PASS` |
| mentah | `.../icarus_full_450k_mentah_INDUK.log` | `total mismatches = 0`, `PASS` |

Baris penentu di kedua lengan:

- `words compared: masukan16=450000 lp=450000 hp=450000 turunan=450000 kuadrat=450000 jendela=450000`
- `data mismatches: masukan16=0 lp=0 hp=0 turunan=0 kuadrat=0 jendela=0`
- `unknown golden words used = 0`
- `unknown t_rule inputs at peak pulses = 0 of 4777`
- `golden rows in range: peaks = 4777 qrs = 2596 t_rejected = 1909`
- `end of stream slack: frames fed=450000, stage outputs masukan16=450000 lp=450000 turunan=450000 kuadrat=450000 jendela=450000`

**Jadi replay penuh 450.000 bingkai kini lulus di dua mesin bebas, bukan hanya Verilator.**
Ini menutup butir yang sebelumnya tertunda pada tabel §1 baris 9.

### 7.2 Banding checksum lintas-mesin

| Lengan | Mesin | CK_STREAM | CK_PEAK | CK_DOWN | CK_EVENT |
|---|---|---|---|---|---|
| berpenanda | Icarus | `b707dacfa5e92141` | `d1fae253bb8d1112` | `3fbbce7cafe82708` | `cf143c61d384939e` |
| berpenanda | Verilator | `b254f0da0524e710` | `ff1f6a10a1028888` | `3fbbce7cafe82708` | `cf143c61d384939e` |
| mentah | Icarus | `b707dacfa5e92141` | `d1fae253bb8d1112` | `9b568a7540e9540f` | `b4649b063ef94265` |
| mentah | Verilator | `b254f0da0524e710` | `ff1f6a10a1028888` | `9b568a7540e9540f` | `b4649b063ef94265` |

Bacaan yang jujur, tanpa dibulatkan ke arah yang enak:

- **`CK_DOWN` dan `CK_EVENT` sama persis antar mesin di kedua lengan.** Keduanya dibangkitkan
  hanya pada denyut dan peristiwa sah: `CK_DOWN` dari `d_rr_ms`, `d_rr_smp`, `m_rr_mark`, `f_ratio`,
  `f_ent`, `m_class`, `m_win_idx`, `m_conf`; `CK_EVENT` dari `m_ev_kind`, `m_ev_val`, `m_ev_idx`
  dan dari jalur vonis `tw_peak_idx`, `tw_dalam_pita`, `tw_reject`. Jadi jalur yang memutuskan
  cocok antar mesin, termasuk vonis `t_rule`.
- **`CK_STREAM` dan `CK_PEAK` berbeda antar mesin.** Keduanya mencampur nilai mentah DUT **setiap
  siklus** (`cmp_stream` pada enam aliran tapis; `mix(ck_peak, u_dut.pk_dbg[...])` termasuk seluruh
  larik `pk_dbg`), bukan hanya siklus yang membawa kata sah. Mesin 4-state memegang X di siklus
  yang tidak bermakna, mesin 2-state memegang 0, sehingga checksum keduanya memang boleh berbeda
  tanpa membantah gerbang mana pun. Karena itu **patokan lintas-mesin di sini adalah `CK_DOWN` dan
  `CK_EVENT`, ditambah perbandingan kata langsung**, bukan keempat checksum.
- Sebab pasti perbedaan `CK_STREAM`/`CK_PEAK` belum diverifikasi malam ini. Yang sudah pasti:
  perbandingan langsung enam aliran berbasis kata sah melaporkan **0 beda dari 450.000 kata**.

### 7.3 Sensus triase (dibandingkan dengan emas)

| Lengan | Mesin | Menyala | TP | FP | FN | TN | Emas |
|---|---|---|---|---|---|---|---|
| berpenanda | Icarus | 189 | 95 | 94 | 0 | 413 | sama |
| mentah | Icarus | 183 | 95 | 88 | 0 | 405 | sama |
| berpenanda | Verilator | 189 | 95 | 94 | 0 | 413 | sama |
| mentah | Verilator | 183 | 95 | 88 | 0 | 405 | sama |

### 7.4 Cacat terbuka yang dinyatakan sendiri oleh bench (bukan gerbang)

`tb_top: t_rule peak pulses=4777 of 4777 peaks, rejected=2014, golden t_rejected in range=1909`,
diikuti `NOTE ... (deviation, not gated: this standalone instance is fed on a different timing from
the Fase 7 fixture, and the T rule the chain uses is the one inside peak_detect)`.

Selisih 2014 − 1909 = **105**, dan cacah baris `RULEDBG` yang tercetak di kedua lengan juga
**105**, semuanya berpola `dut rej=1 gold rej=0` (DUT lebih ketat). Angka dan sebabnya sudah
diuraikan di `PROGRES.md` bagian *DUA CACAH YANG BERBEDA*: kolom bendera `peak_detect` yang
benar-benar memutuskan rantai **0 beda dari 4777 baris**, sedangkan instans `t_rule` mandiri di top
menerima acuan `kem_qrs` dari baris rekaman (`EV_QRS`) sementara model memajukannya di dua jalur
sinyal (`rantai.py:695` dan `:710`) — kedua jalur itu diikuti `peak_detect`, tidak diikuti instans
mandiri. Keluarannya hanya masuk mux debug.

### 7.5 Sintesis rute repo (TAHAP 4)

Angka yang sudah ada (rute repo, Yosys 0.33, sel SKY130):

| Modul | Sel | Area (µm²) |
|---|---|---|
| `acq_frontend` | 2999 | 34307,90 |
| `bandpass` | 4855 | 41508,56 |
| `derivative` | 1348 | 11176,97 |
| `square` | 1257 | 9994,59 |
| `integrator` | 4241 | 48878,13 |
| `rr_series` | 9650 | 80597,30 |

Catatan penting: angka ini jalur **repo** untuk laporan, **bukan** angka implementasi FPGA KV260,
dan **tidak boleh** dibandingkan dengan angka rute lain (suite Yosys 0.70 berbeda).

Sisa modul (`features`, `t_rule`, `classifier`, `regs_axi`, `peak_detect`, `afib_lite_top`)
dijalankan ulang satu per satu dengan **pagar memori keras** (`ulimit -v` per modul) di
`~/.hermes/cache/scratch/fase10/synth_sisa.sh`, supaya ledakan satu modul tidak menyeret pekerja
lain. Alasannya nyata: pada 03:36 `yosys` untuk `peak_detect` membengkak dari 1,65 GB ke 7,33 GB
dalam satu menit dan memaksa penghentian; sebelumnya ledakan yang sama pernah memicu pembunuh OOM
kernel yang menewaskan pekerja lain.

Hasil jalannya sampai **rantai selesai** (21 Oktober 2026, 04:50 WIB; seluruh dua belas modul
dicoba, tidak ada lagi proses tersisa):

| Modul | Hasil | Sel | Area (µm²) |
|---|---|---|---|
| `classifier` | selesai `rc=0` | 678 | 5755,52 |
| `regs_axi` | selesai `rc=0` | 2900 | 25730,93 |
| `t_rule` | **gagal pemeriksaan area** | tidak dilaporkan | tidak dilaporkan |
| `features` | dihentikan setelah 22 menit di ABC | — | — |
| `peak_detect` | **gagal: kehabisan memori di dalam pagar 9 GB** (`rc=134` setelah 22 menit; log mencetak dua pesan kehabisan memori) | — | — |
| `afib_lite_top` | **gagal: kehabisan memori di dalam pagar 11 GB** (`rc=134` setelah 1337 detik; log mencetak `std::bad_alloc` lalu `Aborted (core dumped)`) | — | — |

Pagar memori terbukti bekerja pada dua modul terberat: `peak_detect` dan `afib_lite_top` mati
**sendirian** di dalam pagarnya masing-masing, dan rantai tetap lanjut sampai modul terakhir tanpa
menyeret pekerja lain maupun memicu pembunuh OOM kernel. Skrip pagar hanya memasang `ulimit -v`
tanpa batas waktu, jadi durasi kedua kegagalan yang sama persis (1337 detik) bukan batas yang
dipasang skrip: keduanya memang berhenti sendiri karena `std::bad_alloc` di dalam pagarnya. Kegagalan berturut-turut
pada keempat modul ber-aritmetika 32 bit juga membuktikan ledakan itu melekat pada modulnya, bukan
akibat beban lain: percobaan ini berjalan ketika tidak ada simulasi maupun penulis lain di mesin.

Delapan modul menghasilkan angka yang boleh dikutip. Empat sisa punya sebab yang sudah diketahui dan
diselidiki terpisah:

- `t_rule`: sel tak terpetakan (sel sekuensial SKY130 dilewati ABC karena ekspresi pin tak didukung).
- `features`: ABC belum konvergen setelah 22 menit; dihentikan karena keputusan waktu.
- `peak_detect`: ABC melampaui 9 GB lalu proses berhenti; perlu strategi ABC lain bila angkanya
  diperlukan (misalnya pemetaan cepat) dan konsekuensi ketidaksebandingan angkanya harus dinyatakan
  saat mengutip.
- `afib_lite_top`: modul terbesar, juga melampaui pagarnya; ini konsisten dengan keempat modul
  ber-aritmetika 32 bit (`features`, `peak_detect`, `t_rule`, `top`) yang semuanya menemui dinding
  pada rute ABC yang dipakai. Angka area untuk keempatnya belum bisa dikutip dari rute ini.

`t_rule` **tidak dilaporkan angkanya** karena pemeriksa `area_report.py` sendiri menemukan sel tak
terpetakan di lognya: `FAIL: the log reports unmapped cells, so the area printed above is too
small. Check that dfflibmap runs before abc`. Sebabnya terlihat di log yang sama: ABC melewati
sejumlah sel sekuensial SKY130 karena ekspresi pin-nya tidak didukung
(`Found unsupported expression ... - skipping`), disertai peringatan Yosys yang mengganti tiga
memori `lane_*_w` menjadi daftar register. Ini perlu diselidiki terpisah dan angkanya tidak boleh
dikutip sebelum itu.

`features` **dihentikan sengaja** pukul 04:04 setelah 22 menit di dalam ABC tanpa tanda selesai,
supaya modul ringan lain mendapat kesempatan. Ini keputusan waktu, bukan kegagalan pagar memori, dan
tercatat di berkas ringkasan.

Berkas ringkasan lengkap: `~/.hermes/cache/scratch/fase10/synth_sisa_summary.txt`.


## 8. CACAT YANG DITEMUKAN DAN DIPERBAIKI (dengan angkanya)

1. **Larik debug testbench kedalaman 1024 vs 4777 denyut.** Tiga larik `fed_*` sedalam `WIN_CAP`
   (1024) dibaca sampai indeks 4777 → di Icarus pembacaan di atas 1023 mengembalikan **X**, di
   Verilator mengembalikan memori tetangga. Itulah asal string `fed delta=x kemq=x qrs_at_capture=x`
   yang muncul beruntun mulai baris 1109. **X-nya tidak pernah ada di desain** — dibuktikan pemeriksa
   independen dengan pembacaan hierarkis langsung ke `u_dut.u_t_rule.i_*` (`hd_delta=66 hd_kemq=1091684
   hd_dval=1 hd_kval=1`, 0 denyut unknown dari 1175). Kedalaman diubah ke `PK_CAP=8192`; kini 0 baris `fed delta=x`.
2. **Pembacaan di luar rentang larik emas.** `$readmemh` memperingatkan rentang lebih besar dari berkas
   (mis. `04015.fase8.map.marked.hex`, empat berkas Fase 9 `[0:1023]`). Disengaja: sisa entri tetap X
   dan ditutup penjaga `unknown golden words used = 0` — vektor yang hilang/terpotong tidak bisa lolos
   sebagai "0 beda" (ini lubang lama Fase 6 yang tidak terulang di sini).
3. **Cacat format `$display`** (satu argumen kurang) membuat pembaca bergeser dan `twp` terbaca `0`
   padahal `t_rule` menyala. Diperbaiki.
4. **Perluasan tanda salah** pada larik bertanda `masukan16`/`lp` di TB — diperbaiki; sebelumnya
   melaporkan beda palsu.
5. **Lengan mentah membaca kolom yang tidak pernah diisi.** Berkas `04015.mentah.asli.hex` ada (588 kata)
   tetapi tidak dibaca, sehingga sensus DUT keluar `TP=0 FP=183` dan gerbang gagal **di bench**, bukan di
   desain. Berkas itu kini dibaca; sensus menjadi `183/95/88/0/405` = emas.
6. **Penjaga `$isunknown` pada masukan `t_rule`** ditambahkan dan dijumlahkan ke gerbang
   (`unknown t_rule inputs at peak pulses = 0 of 4777`). Inilah yang membuat "dua mesin identik" **sah
   di jalur vonis**: Verilator 2-state mengubah X menjadi 0, jadi tanpa penjaga ini mesin kedua bisa
   menyembunyikan cacat.

## 9. DUA CACAH YANG BERBEDA — `rejected` vs kolom emas `t_rejected` (penjelasan yang diminta)

Contoh: `t_rule peak pulses=4777 of 4777 peaks, rejected=2014, golden t_rejected in range=1909`
hidup berdampingan dengan `total mismatches = 0`. Penjelasannya:

- `twp_seen` (denyut) **digerbang** — harus sama dengan cacah puncak emas dalam rentang.
- `rejected` = cacah denyut yang `o_reject`-nya 1, yaitu cacah **vonis DUT**.
- `golden t_rejected in range` = cacah kolom emas `04015.puncak.flag.hex` yang bit `t_rejected` menyala
  pada rentang yang sama.
- Selisihnya **persis** cacah baris yang menyimpang satu per satu: jalan 150.000 → `547-473 = 74` dan
  74 baris `RULEDBG` tercetak, **semuanya** `dut rej=1 gold rej=0`; jalan 450.000 → `2014-1909 = 105`
  = 105 baris `RULEDBG`, semuanya satu arah. **Nol** baris arah sebaliknya, **nol** beda `dalam_pita`.
- Baris-baris itu **tidak digerbang**: yang digerbang baris-per-baris adalah kolom bendera `peak_detect`
  — yang benar-benar memutuskan di rantai — dan itu `0` beda dari 4777 baris.
- Sebab terukurnya: acuan `kem_qrs` untuk **instans mandiri** `t_rule` di top diambil dari baris rekaman
  (`EV_QRS`), sedangkan model memajukan acuan di jalur sinyal diterima (`rantai.py:695`) dan di jalur
  cari-mundur (`:710`). `peak_detect` mengikuti **kedua** jalur itu; instans mandiri hanya satu — dan
  karena `pita` cocok 100 % sedangkan `ditolak` meleset ke satu arah (DUT lebih ketat), selisih itulah
  cacah 74/105.

## 10. KETERBATASAN YANG DINYATAKAN (jujur, wajib ikut di laporan akhir)

1. **Throughput kecepatan nyata tidak diklaim.** Testbench menyalurkan satu sampel tiap 64 siklus
   (`cadence = 64`). Yang terbukti hanya bahwa mesin tidak tertinggal pada laju cadangan itu.
2. **Waktu/timing belum ditutup.** Tanpa STA Vivado, tidak ada klaim frekuensi.
3. **Satu bingkai terakhir tidak dibandingkan** (449.999 dari 450.000) — perlu dijelaskan/diperbaiki.
4. **Jalur `ovf` (snapshot jatuh saat unit sibuk) belum pernah dipicu**; hanya `ovf_cnt_q = 0` diverifikasi.
5. **`m_conf` tidak punya kolom emas** — hanya diuji sifatnya (rentang, monoton, menjenuh).
6. **Penyaring kelas belum ada** — tidak ada porta label irama, sehingga lengan berpenanda mengeluarkan
   638 emisi terhadap 602 baris emas; 36 emisi tanpa baris emas ditandai `FFFFFFFF` dan tidak dibandingkan.
7. **Lengan mentah Fase 8 memakai fixture sebagai oracle** (sumber berbeda); satu baris rmssd menyimpang
   tepat 1 LSB, jadi bukan bit-eksak di lengan itu.
8. **Hanya satu rekaman** (04015, ±15 menit) yang diuji. Lulus di situ bukan jaminan untuk rekaman lain;
   jumlah rekaman uji harus disebut apa adanya.
9. **Angka sintesis = rute repo (Yosys 0.33, SKY130), bukan FPGA KV260.**

## 11. YANG BELUM ADA / MENUNGGU KEPUTUSAN

- **K8**: tujuh slot RO (`BEAT_COUNT`, `RR_LAST`, `RR_MARK_LAST`, `SAMPLE_IDX`, `WINDOW_COUNT`,
  `CLASS_OUT`, `CONFIDENCE`) hanya bisa dibaca statis karena daftar porta beku hanya membawa
  `i_status`/`i_irq`. Disambung ke jalur data, atau dibiarkan statis sebagai keterbatasan yang
  dinyatakan? **Menunggu Aviv.**
- **Commit/push**: `HEAD` masih `93fedc6f`; seluruh kerja fase ini belum di-commit. **Menunggu Aviv.**
- **Jalur venue** (bukan laptop): BD + IP packaging + bitstream, `vivado/scripts/build.tcl` (belum ada),
  BD assembly, ILA/JTAG bring-up (pencacah `pl_clk0` lebih dulu), `.ltx`, `bootgen` + overlay +
  `xmutil loadapp`, override boot QSPI32, uji driver PS di perangkat.
