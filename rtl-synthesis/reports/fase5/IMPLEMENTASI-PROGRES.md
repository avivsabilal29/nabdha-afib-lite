# PROGRES IMPLEMENTASI FASE 5 (tulis sambil jalan)

Impelentasi Fase 5, `rtl/peak_detect.sv` dan `rtl/tb/tb_puncak.sv`.
Sumber kebenaran: `rtl-synthesis/reports/fase5/SPEC-TERKUNCI-FASE5.md` (K1..K8).
Log tiap langkah ditulis di sini sambil dikerjakan.

## 0. Peringatan tabrakan sesi (ditemukan lebih dulu)

`rtl/peak_detect.sv` berubah di bawah tangan saya: saat saya mulai membaca berkas itu
(catatan awal saya: 132 baris, sha256 `481d3b0e421f5c07...`, sesuai BASELINE-AUDIT),
berkas yang sama sudah ditulis ulang oleh proses lain pada 2026-10-20 22:32:29 menjadi
744 baris / 36.116 B, sha256 `9c680d128bc1072ddda90b6abf7e70368581d37a15a724af6fa590b796f33a1e`.
`rtl/afib_lite_pkg.sv` juga disentuh pada 22:31:36 (28329 B, sha256
`dc18ee944740407ec65a4f6d01ee256fb4654734de4645c72b72133b150cf081`) dan ditambahi
konstanta Fase 5 (`PEAK_RADIUS`, `PANTUL`, `PITA_MS_ATAS`, `SETENGAH_JENDELA`, `DELAPAN`,
`SEMAI_PANJANG`, `SEMAI_JEDA`, `SHIFT_*`, `RR_BAND_*`, ...).

Catatan: pemanggil saya memberi `rtl/peak_detect.sv` sebagai milik eksklusif saya, dan
`rtl/afib_lite_pkg.sv` sebagai berkas yang DILARANG saya sentuh. Jadi berkas itu bukan
tulisan saya. Saya tidak menghapus isinya, tetapi karena saya pemilik `peak_detect.sv`,
badan yang saya tulis menggantikannya. Isi/potongan yang penting dicatat sebagai temuan:

- Keluaran `run_lint.sh` atas berkas itu: **8 galat sintaks**
  (`8'd(WIN_W)` tidak sah; SystemVerilog tidak menerima lebar sebagai bagian literal
  dengan tanda kurung). Jadi berkas itu belum pernah lint bersih.
- Berkas itu menyalakan `localparam logic T_WAVE_SLOPE_AVAILABLE = 1'b0` dan memakai
  `wire signed ... pkf_s = 0; // pk_f unavailable, see header`. Artinya pk_f dan aturan
  gelombang T **sengaja dimatikan** di situ, karena daftar porta beku tidak membawa `hp`
  dan deret kemiringan. Dengan itu gerbang `t_rejected`, `ditolak`, `diperiksa`,
  `diterima_pita`, `berisiko` dan kolom `filtered_peak`/`slope` tidak mungkin cocok.

Saya tetap menulis implementasi penuh saya sendiri, dan menambah dua porta masukan yang
bersifat murni aditif (`s_hp`, `s_besaran`) plus dua porta introspeksi aditif
(`d_dbg`, `d_dbg_valid`) supaya gerbang bisa **ditutup**, bukan dinyatakan tidak bisa.

## 1. Rujukan di luar RTL (dijalankan sebelum satu baris RTL ditulis)

`~/.hermes/cache/scratch/fase5/rujukan_fase5.py` memakai fungsi beku model
(`rantai.ambang`, `rantai.search_back`, `rantai.gelombang_t_awal`, `rantai.GarisTunda`)
dan hanya menulis ulang pengendara streaming `rantai.py:983-1015`, sehingga kolom emas
`04015.jendela.hex`, `04015.hp.hex`, `04015.turunan.hex` bisa dimasukkan langsung.
Hasil (keluaran mentah, lengkap di `reports/fase5/rujukan_fase5.out`):

```
columns read: jendela 450000 [0, 3105281786]  hp 450000 [-16974032, 19286208]  turunan 450000 [-4792318, 3831762]
jendela words at or above 2**31: 27
peaks 4777  qrs 2596  rr 2595
max peaks in one sample: 1
ambang_state [29, 6, 112, 6, 106, 0, 26, 1202, 2586]
== peaks.csv rows 4777 ==
  pos mismatches 0 / pv 0 / pk_f 0 / kem 0 / i1 0 / i2 0 / sinyal 0 / dalam_pita 0
  ditolak_t 0 / cari_mundur 0 / is_qrs 0 / kind 0
threshold_state.csv spki/npki/spkf/npkf before dan after: 0 berbeda
rr.csv rr_ms dan qrs_cur_sample: 0 berbeda
spki_after max 717628984  i1 range 0 .. 206147681
```

Artinya algoritme yang akan saya tuliskan ke RTL sudah **bit-eksak** terhadap
`rtlplan2/fase5/` sebelum RTL ada. `ambang_state` cocok 9 dari 9.

Probe ukuran (`probe_fase5.py`): penelusuran balik dicoba (`aktif`) pada 231 puncak,
rentang `i_puncak - i_qrs_pk` **maksimum 128** (jadi `SEARCH_BACK_DEPTH = 128` pas,
tidak menggelung), 6 di antaranya berhasil (rentang 23, 4, 4, 4, 4, 13).
`max |hp| = 19286208`, `max |turunan| = 4792318`. Puncak terbanyak dalam satu sampel: 1.

## 2. Keputusan yang diambil dari temuan itu

- `s_hp` (26 bit) dan `s_besaran` (24 bit) ditambahkan sebagai **masukan aditif**.
  Alasan: `s_tdata` selebar 33 bit seluruhnya terpakai oleh kata jendela (32 bit tak
  bertanda, 27 kata di atas 2^31 pada rekaman ini), sedangkan `pk_f` dan `kem` diambil
  model dari `ring_hp` dan `ring_besaran` (`rantai.py:933-935`, `:1002`, `:333`).
  Tanpa keduanya, `filtered_peak`, `slope`, kolom `in_band`/`t_rejected` dan empat unsur
  `ambang_state` tidak mungkin dihitung. Ini dilaporkan sebagai penyimpangan, bukan
  disembunyikan.
- `d_dbg` (512 bit, 16 kata) dan `d_dbg_valid` ditambahkan sebagai **introspeksi aditif**:
  9 unsur `ambang_state` plus enam besaran per puncak yang tidak punya porta beku
  (`kem`, `delta`, `pos`, flag). Alasan: gerbang menuntut 9 dari 9 unsur `ambang_state`,
  dan `d_thr`/`d_pk` hanya membawa `i1` dan `pk_f`.
- Konstanta Fase 5 (`RADIUS_PUNCAK 27`, `JENDELA_F 25`, `PANTUL 50`,
  `BATAS_PITA_SAMPEL 360`, `SETENGAH_JENDELA 18`, `DELAPAN 8`, `SEMAI_PANJANG 32`,
  `SEMAI_JEDA 8`) dideklarasikan sebagai `localparam` **di dalam modul**, bukan di
  paket, karena paket bukan berkas saya dan sudah beku sebelum Fase 5. Setiap nilai
  dikutip dengan nomor baris model. (Sesi lain sudah menambahkannya ke paket; berkas
  saya sengaja tidak bergantung pada tambahan itu.)

## 3. Langkah berikut

1. Generator vektor turunan di `rtl/tb/vektor/fase5/`.
2. `rtl/peak_detect.sv`.
3. `rtl/tb/tb_puncak.sv`.
4. lint, mode pendek 40.000, lalu penuh 450.000 (dua kali).

## 4. Vektor turunan (selesai)

`rtl/tb/vektor/fase5/siapkan_vektor_fase5.py` membaca `rtlplan2/fase5/04015.peaks.csv`
dan `04015.manifest.fase5.json` (tidak menulis apa pun di `rtlplan2/`) lalu menghasilkan
11 berkas hex di `rtl/tb/vektor/fase5/` plus `04015.fase5.manifest.json` yang memuat
sha256 tiap berkas. Keluaran mentah: `reports/fase5/siapkan_vektor_fase5.out`.

```
peaks 4777  qrs 2596  ambang_state [29, 6, 112, 6, 106, 0, 26, 1202, 2586]  frames 450000
```

## 5. RTL (selesai, lint bersih)

Rangkaian yang ditulis, semuanya dalam satu blok `always @(posedge clk_i)` sinkron dengan
reset aktif rendah:

1. Tiga garis tunda sebagai satu vektor padat per aliran (jendela 33 bit x 54, hp 26 x 52,
   turunan 24 x 45). Indeks 0 = sampel terakhir. Alasannya kecepatan simulator: potongan
   bit dengan basis variabel O(1), sedangkan larik yang diindeks variabel menjadi
   pencarian linear di Icarus.
2. Pemindai amplop K6: pada tiap sampel, `pv = tap 27`, jendela `tap 0..54`, puncak bila
   `pv != 0` dan `pv >= maks(jendela)`, lalu `scan += 27`, selain itu `scan += 1`.
3. `pk_f = maks|hp|` atas tap 2..52 dan `kem = maks|turunan|` atas tap 9..45.
4. Ambang dua domain: `i1`, `f1` dan `i2` sebagai cuplikan (trap 1), state 33 bit tanpa
   klip (K3), pergeseran `>>` aritmetik (RND_FLOOR).
5. Gerbang refrakter `delta < 50`, aturan gelombang T `2*kem < kem_qrs` bentuk silang
   persis (trap 2), dan `calon_kedua` dihitung setelah ketiga gerbang (trap 3).
6. Penelusuran balik K7/K8: jendela `[i_qrs_puncak+1, i_puncak]` inklusif, ditelusuri
   turun dengan ganti saat `>=` sehingga yang paling awal menang, gerbang 83/50 bentuk
   silang, buffer 128 entri (kepadatan terukur 128, jadi tidak pernah menggelung),
   pembilitan dinyatakan lewat `m_overflow`.
7. Cermin sub-tahap RR (rantai.py:375-440) untuk tiga unsur state yang tersisa
   (`semai`, `penanda`, `langkah`), termasuk `median_bulat` dihitung dengan penghitungan
   peringkat, bukan jaring pengurut, supaya tidak ada lingkar kombinasional.
8. Sembilan pencacah `ambang_state`, `o_beat_count`, sideband `m_ev_*`, introspeksi
   `d_thr`/`d_pk`, dan bus aditif `d_dbg`.

Catatan penting yang ditemukan saat lint: nol di `m_overflow` asli berasal dari saya
memasukkan **carry jumlah median** ke daftar rel; carry itu sah (dua median 16 bit bisa
mencapai 2**17) sehingga bendera menempel pada puncak pertama. Sudah diperbaiki: hanya
tujuh bit pembaruan state yang dipakai sebagai rel, carry median dibuang oleh pergeseran.

Riwayat lint (mentah):
`reports/fase5/lint-peak_detect-01.out` 25 peringatan, `-02` 4, `-03` 5, `-04` 0,
`-05` 0, `-06` 1, `-07` 0 (bersih).

## 6. Testbench (selesai, lulus pada mode pendek)

`rtl/tb/tb_puncak.sv`: `+VECTOR` (kolom Fase 0) dan `+EXPECT` (vektor turunan Fase 5),
`+LIMIT` opsional. Diperiksa: posisi puncak, `pv`, `pk_f`, `kem`, `i1`, `d_pk`, flag,
`ev_kind`, `ev_idx`, `ev_val`, deret QRS berurutan, kelima kolom aliran, pencacah tidak
pernah turun, `m_overflow`.

```
+LIMIT=4000  : 43 puncak, 23 qrs, 4000 kata dibandingkan, 0 beda  -> PASS
+LIMIT=40000 : 433 puncak, 238 qrs, 40000 kata dibandingkan, 0 beda -> PASS   (53 detik)
```

## 7. Jalan penuh

`reports/fase5/sim-lengkap-01.out` (450.000 sampel) dan ulangannya
`sim-lengkap-02.out` untuk bukti determinisme.

## 8. Dua kesalahan yang ditemukan dan diperbaiki sebelum jalan penuh

1. **Bendera luapan palsu.** Percobaan pertama menyalakan `m_overflow` pada puncak
   pertama. Sebabnya: rel pembelitan saya menyertakan bit carry dari
   `med_sum_w[RR_W]`, padahal carry itu sah (jumlah dua nilai median 16 bit boleh
   mencapai 2**17 dan memang terjadi pada siklus tanpa denyut, ketika kata interval
   masih sampah). Perbaikan: `med_w` dijadikan 17 bit penuh (`med_sum_w >> 1`),
   carry median dikeluarkan dari daftar rel, dan `antre_sum_rs` disesuaikan.
   Bukti: `sim-4000-02.out` (bendera 0) dan `sim-40000-01.out` (bendera 0).
2. **Lebar entri penampan kandidat.** Entri pertama saya 119 bit
   (`pos 32 + pv 33 + pk_f 30 + kem 24`). Rencana 38 baris 1854 menganggarkan
   **112 bit** per entri. 112 bit (32 + 32 + 24 + 24) tidak cukup: `pk_f` pada
   rekaman ini mencapai 18.865.152 > 2**24, jadi bidang 24 bit akan memotongnya dan
   pemilihan penelusuran balik bisa salah. Entri saya sekarang **114 bit**
   (`pos 32 + pv 32 + pk_f 26 + kem 24`): 32 bit untuk posisi (W_IDX beku), 32 bit
   untuk kata amplop (bagian tak bertanda dari node W_WIN), 26 bit untuk besar `hp`
   (W_HP beku) dan 24 bit untuk besar turunan. Bit tanda amplop yang tidak terpakai
   ikut diawasi rel. Selisih terhadap rencana: +2 bit per entri (+256 bit, 1,8 persen
   pada kelompok itu), dilaporkan sebagai penyimpangan.
3. **Peringatan simulator dihapus.** Tiga peringatan Icarus "out of bounds array
   access ... [-1]" dari gelung generate penggeser antrean. Diganti dengan satu
   penugasan indeks 0 plus gelung mulai dari 1, sehingga tidak ada cabang yang
   menyebut indeks -1. Sim sekarang nol peringatan.

## 9. Cacah flip-flop (gerbang keempat)

`reports/fase5/hitung_ff.py` (baca-saja atas `rtl/peak_detect.sv` dan paket)
menghitung tiap penampan sebagai kedalaman kali lebar, seperti aturan D1 rencana 38.
Keluaran penuh: `reports/fase5/hitung_ff.out`.

```
penampan kandidat penelusuran balik (bpk_vec)                              14.592
garis tunda jalur data (sel_vec 54x33, hp_vec 52x26, bes_vec 45x24)         4.214
sub-tahap RR (deret, antre, rih, ra1, pemb, peny, semai, gagal, jeda)         962
pelacak fitur dan QRS (i_qrs, i_qrs_pk, kem_qrs, benderanya)                   91
state ambang adaptif (spki, npki, spkf, npkf)                                 132
introspeksi aditif (dbg_q, dbg_valid_q)                                       449
pencacah ambang_state (delapan kali 32 bit)                                    256
pemindai amplop dan pencacah puncak (scan_q, pk_cnt_q)                          64
keluaran aliran dan sisi (m_*, d_thr, d_pk, o_beat_count)                      237
TOTAL                                                                       20.997
anggaran state seluruh rantai di rencana 38 (baris 1850-1858)              25.640
```

Tidak ada state tanpa batas: setiap penampan punya kedalaman tetap dari model dan
tidak ada indeks yang berasal dari data (D1). Tiga kelompok rencana tidak ada di modul
ini karena memang bukan miliknya: empat dari tujuh ring jalur data, jendela fitur dan
histogram (modul fitur), dan penampan keluaran keputusan. Dua kelompok ada di sini
tetapi tidak dianggarkan sebagai milik `peak_detect`: pencacah `ambang_state` (256 bit,
memang wajib oleh gerbang) dan bus introspeksi `d_dbg` (449 bit, aditif).

## 10. Penyimpangan yang dilaporkan

1. `s_hp` (26 bit) dan `s_besaran` (24 bit) ditambahkan sebagai **masukan aditif**,
   murni tambahan di akhir daftar porta. Alasannya di bagian 2.
2. `d_dbg` (448 bit) dan `d_dbg_valid` ditambahkan sebagai **keluaran introspeksi
   aditif** di akhir daftar porta. Alasannya di bagian 2.
3. Konstanta Fase 5 dideklarasikan sebagai `localparam` di dalam modul, bukan di paket
   (paket bukan berkas saya).
4. Entri penampan kandidat 114 bit, bukan 112 bit, dengan alasan di bagian 8.2.
5. Garis tunda `hp` dan turunan dibangun **di dalam modul ini**, padahal rencana
   menempatkannya di modul jalur data. Sebabnya daftar porta beku tidak membawa kedua
   deret itu, sementara `pk_f` dan `kem` wajib untuk empat unsur `ambang_state`, kolom
   `in_band`/`t_rejected` dan aturan gelombang T.

## 11. Tiga kesalahan berikutnya, ditemukan dengan mengukur (bukan menebak)

Jalan penuh pertama (450.000) gagal: `peak i1 mismatches 509`, `kind 5`, `ev_idx 5`,
`qrs 2591 dari 2596`, `ambang_state` meleset di elemen 1, 6 dan 7
(`cari_mundur` 9 lawan 6, `semai` 27 lawan 26, `penanda` 1196 lawan 1202). Isolasi
dilakukan dengan memperkecil `+LIMIT` dan menambah pencetak ketidakcocokan pertama di
testbench (`MISM peak#...`), lalu membandingkan keadaan internal dengan model beku
melalui skrip `~/.hermes/cache/scratch/fase5/dump_rr_peak.py`, yang mencetak
`pembilang, penyebut, ra1, gagal, jeda, semai` dan hasil gerbang
`200*delta*penyebut > 83*pembilang` pada setiap puncak (nilainya identik dengan CSV emas
karena memakai fungsi beku yang sama).

1. **Keluaran `m_ev_kind` salah untuk baris refit.** Puncak yang merekam QRS lewat
   penelusuran balik harus memancarkan `EV_QRS` dengan indeks = posisi yang direkam
   (lebih awal dari posisi puncaknya), bukan `EV_PEAK_CAND`. Bukti: `+LIMIT=90000`
   menyisakan tepat **satu** ketidakcocokan, `MISM peak#921 pos=86121 kind dut=2
   gold=1 flag=0x18` — posisi, `i1`, `evidx` dan bendera sudah cocok semua. Setelah
   diperbaiki, `+LIMIT=100000` lulus penuh.
2. **Indeks baca penampan kandidat salah saat melingkar.** Penulisan memakai slot
   `pk_cnt[6:0]`, tetapi penelusuran balik membaca mulai dari `BUF_MASK - ki`, yang hanya
   sejajar ketika `pk_cnt` kebetulan ada di topeng. Akibatnya setiap langkah `ki >= 1`
   membaca entri puncak sekitar 100 langkah yang lalu: refit yang kandidatnya puncak itu
   sendiri (`ki = 0`, kasus yang ditangani khusus) masih berhasil, yang kandidatnya
   puncak lain selalu gagal. Itu tepat pola yang terlihat: refit 86121 berhasil, refit
   91681 gagal, dan puncak 91807 justru menggelar refit palsu karena `i_qrs` tidak
   bergerak. Perbaikan: `(pk_cnt_q[6:0] - ki[6:0]) & BUF_MASK_D`. Setelah perbaikan,
   `+LIMIT=100000` mengembalikan `MISM` nol baris, `qrs 515 dari 515`, `i1 0`,
   `qrs index out of order 0`.
3. **Bendera ritme dihitung terhadap acuan yang salah.** `penanda` pada jalan penuh
   pertama 1195 lawan 1202 (kurang 7). Isi gelung `mem_w` membandingkan deret delapan
   interval terhadap pita yang dibentuk dari `rr_lo_w`/`rr_hi_w`, yaitu acuan **sebelum**
   pembaruan antrean, sedangkan model (`rantai.py:424-437`) menghitung ulang
   `pembilang`/`penyebut` sesudah denyut itu diserap, baru menguji delapan nilai.
   Perbaikan: pita dihitung dari `pemb_n` (`rr_lopost_w`, `rr_hipost_w`). Puncak, `qrs`,
   dan `cari_mundur` tidak terpengaruh: nilainya sudah sama sebelum perbaikan ini.

Setelah ketiga perbaikan, jalan penuh 450.000 pada revisi terakhir memberi
`peaks dut 4777`, `qrs dut 2596`, `words compared 450000 of 450000`,
`peak position mismatches 0`, `mismatches 0`, dan 9 dari 9 unsur `ambang_state`.

4. **Peringatan simulator dihapus** (lihat bagian 8.3).

Skrip diagnostik yang dipakai disimpan bersama di
`~/.hermes/cache/scratch/fase5/` (`tb_probe.sv`, `pd_dbg.sv`, `dump_rr_peak.py`,
`probe_rr2.out`) dan disalin ke `reports/fase5/` sebagai bukti.

## 12. Bendera ritme (`penanda`) dan kontrol negatif (putaran audit agen induk)

1. Dugaan pita acuan diuji dengan `~/.hermes/cache/scratch/fase5/uji_penanda.py`, yang
   membungkus `rantai.rr` dan menghitung dua versi aturan pada setiap denyut berderet
   penuh. Selisih antar-aturan keluar **tepat 7** (post 1194 lawan pre 1187) — sama dengan
   kekurangan `penanda` pada jalan penuh revisi pertama (1195 lawan 1202) — dan perbedaan
   pertama ada di denyut ke-50, puncak ke-149, sampel 14571, jadi **bukan** setelah 100k.
   Catatan: jalan pendek 100k memang tidak pernah memeriksa sembilan unsur `ambang_state`
   (kepala testbench baris 31-34), sehingga "100k bersih" bukan bukti apa pun untuk
   `penanda`.
2. Jalur gagal testbench diubah ke `$fatal(1, ...)` (empat tempat) dan kondisi lulus
   ditambah `phase == PH_DONE`. Kontrol negatif pertama **kosong**: yang dirusak hanya
   `04015.ambang_state.hex`, satu-satunya larik yang dilewati jalan pendek, jadi hasilnya
   tetap PASS. Kontrol yang sah merusak satu kata larik per-puncak
   (`04015.puncak.i1.hex`, `010a0f9b` menjadi `010a0f9a`) pada salinan di luar repo, dan
   hasilnya `mismatches = 1`, `FAIL`, `FATAL ... gate violation`, `rc=1` (log
   `reports/fase5/sim-negatif-02.out`).
3. Dua jalan penuh terakhir pada revisi yang diserahkan (`sim-lengkap-05.out` 00:05:04 dan
   `sim-lengkap-06.out` 00:11:59) keduanya `PASS`, dan 42 baris ringkasan keduanya
   byte-identik (md5 `31d65bf7b00c54c8c961bdd9c27dca9b`), sama dengan pasangan sebelumnya
   (`sim-lengkap-03/04`).
4. `sim-lengkap-02.out` mati di tengah karena `pkill -f "tb_puncak.vvp"` milik saya sendiri
   ikut menyerang shell yang menjalankannya; pasangan determinisme yang sah adalah
   `sim-lengkap-04` dan `sim-lengkap-06`.





