# LAPORAN FASE 5: peak_detect.sv dan tb_puncak.sv

Repo: /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
Model beku tidak disentuh: `model/rantai-afib-lite/rantai.py` sha256
`90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5`, sama sebelum dan
sesudah pekerjaan. Tidak ada `git add`, `git commit`, `git checkout`, atau `git stash`.
Tidak ada berkas milik sesi lain yang disentuh.

Berkas yang dilarang juga tidak disentuh: `rtl/*.sv` selain `peak_detect.sv`, `rtl/tb/*`
selain `tb_puncak.sv`, `rtl-synthesis/run_lint.sh`, `run_sim.sh`, `reports/*.native.*`,
`rtl-synthesis/mcy/**`, `rtl/TASK_BRIEF.md`, dan seluruh `rtlplan2/**` (dibaca saja).

Catatan tabrakan sesi: `LAPORAN-FASE5.md` ternyata sudah ditulis sesi lain pada 20 Oktober
2026 23:29:49 (laporan bench `tb_peak_detect.sv` mereka). Saya tidak menghapusnya: salinannya
ada di `rtl-synthesis/reports/fase5/LAPORAN-FASE5.sesi-lain-verifikasi.md`, dan laporan ini
menggantikan berkas di jalur itu sesuai pembagian kepemilikan di penugasan saya.

## 1. Berkas yang disentuh

| Berkas | Keadaan | sha256 | baris |
|---|---|---|---|
| `rtl/peak_detect.sv` | badan nyata menggantikan placeholder; porta/parameter beku tidak berubah lebar atau nama, ditambah empat porta aditif di ujung daftar | `d4cfd9c6c3f77b67f31a26f2b8b8957666c5672becca45cb656dfc823b57d547` | 962 |
| `rtl/tb/tb_puncak.sv` | dibuat, gerbang paritas Fase 5 | `f9b506310ae4317424a671a410e110a00be18db4cc84ad745b7fb08264943eb5` | 523 |
| `rtl/tb/vektor/fase5/siapkan_vektor_fase5.py` | dibuat, penurun vektor dari data emas | `b6944cbf1c34b48c1eec69ac0fffee1de5ea3358648858e167f78ec1b2cdab25` | 143 |
| `rtl/tb/vektor/fase5/04015.*.hex`, `04015.fase5.manifest.json` | dibuat, 12 berkas vektor + manifest berisi sha256 tiap berkas | lihat manifest | |
| `rtl-synthesis/reports/LAPORAN-FASE5.md` | laporan ini | | |
| `rtl-synthesis/reports/fase5/` | seluruh log mentah, riwayat lint, skrip cacah flip-flop, skrip diagnostik | | |
| `rtl-synthesis/reports/fase5/hitung_ff.py` | dibuat, cacah flip-flop per penampan (kedalaman kali lebar, aturan D1) | `eaba8151fb0dcafba23968693a10b976b1ed11bc1a85c39ea6658fb07232c43d` | 188 |

Bukan tulisan saya, disimpan sebagai bukti: `rtl-synthesis/reports/fase5/peak_detect.sv.sesi-lain-9c680d12.bak`
adalah salinan versi `rtl/peak_detect.sv` milik sesi lain pada 20 Oktober 2026 22:32:29
(744 baris, sha256 `9c680d128bc1072ddda90b6abf7e70368581d37a15a724af6fa590b796f33a1e`),
diambil sebelum saya menimpa berkas itu. Versi tersebut tidak lint bersih dan mematikan
jalur gelombang T, jadi gerbangnya tidak mungkin ditutup dari sana.

Data emas yang dipakai, tidak diubah dan tidak diekspor ulang: `rtlplan2/fase0/04015.jendela.hex`,
`04015.hp.hex`, `04015.turunan.hex`, dan delapan CSV `rtlplan2/fase5/04015.*`.

## 2. Persyaratan yang dikutip apa adanya

`rtlplan2/final38.md` baris 122:

> | 5 | Ambang adaptif dan deteksi puncak | `peak_detect.sv` | `tb_puncak` 0 dari 4.777
> puncak; 9 dari 9 `ambang_state`; `qrs` 2.596 dari 2.596; jumlah flip-flop sama dengan
> rencana | 10 jam | pemilik RTL |

Syarat arsitektural dari penugasan: tanpa pembelitan, tanpa latch, satu clock domain,
reset sinkron aktif rendah, dan deterministik (dua kali jalan penuh harus identik).

Sumber kebenaran perilaku: `rtl-synthesis/reports/fase5/SPEC-TERKUNCI-FASE5.md`
(klausa K1..K8) dan model beku `rantai.py`. Delapan jebakan paritas yang dokumen itu
sebut diikuti satu per satu: `ambang` memakai cuplikan `i1`/`f1`/`i2` sebelum pembaruan,
state 33 bit tanpa klip, pergeseran aritmetik, bentuk silang untuk gerbang T dan gerbang
penelusuran balik, `calon_kedua` dihitung setelah ketiga gerbang, ketaksamaan ketat pada
pemilihan kandidat, dan pembalikan `i2 < v <= i1`.

## 3. Arsitektur yang dibangun

Satu blok `always @(posedge clk_i)` untuk seluruh state, reset sinkron aktif rendah, satu
clock domain, tanpa latch, tanpa gelung kombinasional. Isinya, berurutan:

1. **Tiga garis tunda sebagai vektor padat**, satu vektor per aliran (`sel_vec` jendela
   54 x 33 bit, `hp_vec` 52 x 26, `bes_vec` 45 x 24), indeks 0 = sampel terakhir. Bentuk
   ini dipilih karena potongan bit berindeks variabel O(1) di simulator, sedangkan larik
   berindeks variabel menjadi pencarian linear. Larik yang tersisa hanya antrean RR, dan
   panjangnya tetap delapan atau 32.
2. **Pemindai amplop** (K6): `pv` = tap 27, jendela = tap 0..54, puncak bila `pv != 0` dan
   `pv >= maks(jendela)`; lalu `scan += 27`, selain itu `scan += 1`, dengan `scan` adalah
   indeks sampel.
3. **`pk_f = maks |hp|` atas tap 2..52 dan `kem = maks |turunan|` atas tap 9..45**, dua
   besaran yang di model datang dari ring `hp` dan ring turunan (`rantai.py:333`, `:1002`).
4. **Ambang dua domain** (K3): `i1 = npki + ((spki-npki) >>> 2)`, `f1` sama atas
   `spkf`/`npkf`, `i2 = i1 >> 1`, keempat state 33 bit tanpa klip, semua pergeseran
   aritmetik. `i1`/`f1`/`i2` adalah cuplikan beku pada puncak itu.
5. **Gerbang refrakter 50 sampel**, **aturan gelombang T** (`2*kem < kem_qrs` dalam bentuk
   silang, tanpa pembagian), dan `calon_kedua` dihitung setelah ketiga gerbang.
6. **Penelusuran balik** (K7/K8): gerbang `200*delta*penyebut > 83*pembilang` dengan
   cadangan `ra1`, jendela `[i_qrs_puncak+1, i_puncak]` inklusif ditelusuri turun dengan
   penggantian pada `>=` sehingga kandidat paling awal menang, syarat `i2 < v <= i1`,
   penampan 128 entri dengan penanda luapan. Penanda luapan tidak pernah menyala pada
   rekaman ini (`m_overflow` 0 sepanjang dua jalan penuh, tanpa pulsa dan tanpa tepi naik),
   dan penyimpangan 128 entri adalah jumlah puncak yang dibutuhkan penelusuran balik paling
   jauh, bukan angka yang saya ukur di sini.
7. **Cermin sub-tahap RR** (`rantai.py:375-440`) untuk tiga unsur state yang tersisa
   (`semai`, `penanda`, `langkah`), termasuk `median_bulat` yang dihitung dengan cacah
   peringkat, bukan jaringan pengurut, agar blok kombinasional tetap asiklik.
8. **Sembilan pencacah `ambang_state`**, `o_beat_count`, sideband `m_ev_*`,
   introspeksi `d_thr`/`d_pk`, dan bus aditif `d_dbg` (14 kata 32 bit).

Porta aditif di ujung daftar (dilaporkan di bagian 6): `s_hp` (26 bit), `s_besaran`
(24 bit), `d_dbg` (448 bit), `d_dbg_valid`. Peta kata `d_dbg`: 0..8 = sembilan unsur
`ambang_state` dalam urutan model (`rantai.py:1051-1053`), 9 = nilai amplop, 10 =
kemiringan, 11 = bendera, 12 = posisi puncak, 13 = rel internal dan lengan penelusuran
balik.

## 4. Gerbang dan hasilnya

### 4.1 Lint

```
$ cd rtl-synthesis && ./run_lint.sh ../rtl/peak_detect.sv peak_detect ../rtl/afib_lite_pkg.sv
lint_rc=0 warn=0
```

Keluaran mentah `reports/fase5/lint-peak_detect-12.out`. Riwayat: `-01` 25 peringatan,
`-02` 4, `-03` 5, `-04` 0, `-05` 0, `-06` 1, `-07` 0, `-08` 0, `-09` 0, `-10` 0,
`-11` 0, `-12` 0. Tidak ada latch: setiap `always @(*)` menulis seluruh keluarannya di
setiap jalur.

**Lint seluruh rantai tidak hijau, dan tidak bisa hijau tanpa menyentuh berkas di luar
kepemilikan saya:**

```
$ ./run_lint.sh --chain
%Warning-PINMISSING: ../rtl/afib_lite_top.sv:398:17: Cell has missing pin: 's_hp'
%Warning-PINMISSING: ../rtl/afib_lite_top.sv:398:17: Cell has missing pin: 's_besaran'
%Warning-PINMISSING: ../rtl/afib_lite_top.sv:398:17: Cell has missing pin: 'd_dbg'
%Warning-PINMISSING: ../rtl/afib_lite_top.sv:398:17: Cell has missing pin: 'd_dbg_valid'
%Error: Exiting due to 4 warning(s)
chain_rc=1
```

Keluaran mentah `reports/fase5/lint-chain-01.out`. Keempat pin itu adalah porta aditif
dari bagian 6; `afib_lite_top.sv` ada di daftar berkas yang dilarang saya sentuh. Ini
temuan untuk agen induk, bukan sesuatu yang saya paksa: menyambungkan empat pin (satu
baris tiap pin) atau menerima `--chain` merah.

### 4.2 Mode pendek, dijalankan sebelum jalan penuh

Minimal 40.000 sampel, karena gerbang jendela baru terbuka setelah itu.

```
$ cd rtl-synthesis && ./run_sim.sh ../rtl/tb/tb_puncak.sv ../rtl/afib_lite_pkg.sv \
    ../rtl/peak_detect.sv -- +VECTOR=../rtlplan2/fase0 +EXPECT=../rtl/tb/vektor/fase5 +LIMIT=4000
tb_puncak: peaks dut = 43 expected = 43
tb_puncak: qrs   dut = 23 expected = 23
tb_puncak: words compared = 4000 of 4000
tb_puncak: peak position mismatches = 0
tb_puncak: ambang_state mismatches = 0
tb_puncak: mismatches = 0
tb_puncak: PASS
```

`+LIMIT=100000`, dipakai saat mengejar pengelaran palsu penelusuran balik:

```
tb_puncak: peaks dut = 1069 expected = 1069
tb_puncak: qrs   dut = 515 expected = 515
tb_puncak: words compared = 100000 of 100000
tb_puncak: peak position mismatches = 0
tb_puncak: ambang_state mismatches = 0
tb_puncak: mismatches = 0
tb_puncak: PASS
```

Keluaran mentah `reports/fase5/sim-4000-03.out`, `sim-40000-02.out`,
`sim-100000-diag2.out`. Dua yang terakhir dijalankan pada revisi terakhir:
`+LIMIT=40000` memberi 433 puncak, 238 denyut, 40.000 dari 40.000 kata, 0 ketidakcocokan
(bagian gerbang jendela baru terbuka setelah 40.000 sampel, jadi ini panjang pendek
terpendek yang sah). Tangkapan saat masih gagal (`sim-90000-diag.out`,
`sim-100000-diag.out`, `sim-lengkap-01.out`) ikut disimpan karena memuat baris
`MISM peak#...` yang jadi bukti saat mencari cacat.

**Kontrol negatif, supaya jelas bench ini bergigi.** Satu kata pada salinan
`04015.puncak.i1.hex` di luar repo dibalik satu bit (kata ke-5, `010a0f9b` menjadi
`010a0f9a`; seluruh berkas vektor asli tidak disentuh), lalu testbench dijalankan dengan
`+LIMIT=4000`:

```
$ ./run_sim.sh ../rtl/tb/tb_puncak.sv ../rtl/afib_lite_pkg.sv ../rtl/peak_detect.sv \
    -- +VECTOR=../rtlplan2/fase0 +EXPECT=$HOME/.hermes/cache/scratch/fase5/vektor_rusak2 +LIMIT=4000
tb_puncak: peak position mismatches = 0
tb_puncak: peak i1 mismatches       = 1
tb_puncak: mismatches = 1
tb_puncak: FAIL phase=2 npk=43/43 nqrs=23/23 nout=4000/4000 mism=1 amb=0 nonmono=0 ovf=0
FATAL: ../rtl/tb/tb_puncak.sv:517: tb_puncak: gate violation, see the counters above
negA_rc=1
```

Jadi jalur gagal memanggil `$fatal(1, ...)` dan kode keluarnya **1**, bukan 0. Keluaran
mentah `reports/fase5/sim-negatif-02.out`. Kontrol negatif pertama saya
(`sim-negatif-01.out`) **kosong dan tidak sah** dan saya catat di sini supaya tidak
terlihat seperti bukti: yang saya rusak waktu itu hanya `04015.ambang_state.hex`,
sementara sembilan unsur `ambang_state` memang sengaja tidak diperiksa pada jalan pendek
(lihat kepala testbench, baris 31-34), jadi hasilnya `PASS` — kontrol yang merusak
satu-satunya larik yang dilewati tidak membuktikan apa pun. Kontrol yang sah di atas
merusak larik per-puncak yang memang dibandingkan pada jalan pendek.

### 4.3 Jalan penuh 450.000, dan determinisme

Dua jalan penuh berturut-turut pada revisi yang diserahkan (RTL `d4cfd9c6…`, bench
`f9b50631…`), log terpisah dan berstempel waktu: `reports/fase5/sim-lengkap-05.out`
(23:58:31 sampai 00:05:04) dan `sim-lengkap-06.out` (sampai 00:11:59). Keluaran mentah
jalan pertama, apa adanya:

```
=== run A (full 450000) start 23:58:31 HEAD 93fedc6
tb_puncak: golden peaks = 4777, qrs = 2596, ambang_state words = 9
tb_puncak: ambang_state[0] dut = 29 golden = 29
tb_puncak: ambang_state[1] dut = 6 golden = 6
tb_puncak: ambang_state[2] dut = 112 golden = 112
tb_puncak: ambang_state[3] dut = 6 golden = 6
tb_puncak: ambang_state[4] dut = 106 golden = 106
tb_puncak: ambang_state[5] dut = 0 golden = 0
tb_puncak: ambang_state[6] dut = 26 golden = 26
tb_puncak: ambang_state[7] dut = 1202 golden = 1202
tb_puncak: ambang_state[8] dut = 2586 golden = 2586
tb_puncak: peaks dut = 4777 expected = 4777
tb_puncak: qrs   dut = 2596 expected = 2596
tb_puncak: beats o_beat_count = 2596
tb_puncak: words compared = 450000 of 450000
tb_puncak: peak position mismatches = 0
tb_puncak: peak pv mismatches       = 0
tb_puncak: peak pk_f mismatches     = 0
tb_puncak: peak kem mismatches      = 0
tb_puncak: peak i1 mismatches       = 0
tb_puncak: peak flag mismatches     = 0
tb_puncak: peak kind mismatches     = 0
tb_puncak: peak ev_idx mismatches   = 0
tb_puncak: peak ev_val mismatches   = 0
tb_puncak: qrs index out of order   = 0
tb_puncak: stream m_tdata mismatch  = 0
tb_puncak: stream sample_idx        = 0
tb_puncak: stream tuser mismatch    = 0
tb_puncak: stream tlast mismatch    = 0
tb_puncak: golden signal flags = 2590 in_band = 2029 t_rejected = 1909 refit = 6
tb_puncak: peaks whose event index moved off the peak position = 2
tb_puncak: counter decreases = 0
tb_puncak: m_overflow pulses = 0 (rising edges 0)
tb_puncak: d_valid pulses    = 4777
tb_puncak: ambang_state mismatches = 0
tb_puncak: mismatches = 0
tb_puncak: PASS
runA_rc=0 end 00:05:04
```

Jalan kedua memberi ringkasan yang sama, `PASS`, `runB_rc=0 end 00:11:59`, dengan durasi
lebih panjang karena mesin dipakai bersama.

**Determinisme, dua kali, diukur bukan diklaim.** Ke-42 baris `tb_puncak:` dari kedua
jalan penuh diambil, lalu dibandingkan byte per byte:

```
$ grep "^tb_puncak:" sim-lengkap-05.out > /tmp/c.txt ; grep "^tb_puncak:" sim-lengkap-06.out > /tmp/d.txt
$ diff /tmp/c.txt /tmp/d.txt && echo IDENTICAL
IDENTICAL
$ md5sum /tmp/c.txt /tmp/d.txt
31d65bf7b00c54c8c961bdd9c27dca9b  /tmp/c.txt
31d65bf7b00c54c8c961bdd9c27dca9b  /tmp/d.txt
```

Pasangan penuh yang lebih dahulu (`sim-lengkap-03.out` 23:49:04 dan `sim-lengkap-04.out`
23:55:57, revisi RTL yang sama, bench sebelum `$fatal` ditambahkan di jalur gagal)
memberi md5 yang **sama persis**, `31d65bf7b00c54c8c961bdd9c27dca9b`. Empat jalan penuh
450.000, empat ringkasan identik.

Catatan kejujuran untuk pasangan `sim-lengkap-01/02`: `sim-lengkap-02.out` **mati di
tengah** (02:20 berjalan, ringkasan kosong, `run2_rc=0`). Penyebabnya saya sendiri:
saya menjalankan `pkill -f "tb_puncak.vvp"` untuk membebaskan CPU sebelum menyunting
RTL, dan pola itu ikut menyerang shell yang sedang menjalankan jalan penuh itu. Tidak ada
yang disembunyikan: jalan penuh kedua yang sah adalah `sim-lengkap-04` dan
`sim-lengkap-06`.

### 4.4 Cacah flip-flop

Perintah `python3 rtl-synthesis/reports/fase5/hitung_ff.py`, keluaran penuh
`reports/fase5/hitung_ff.out`. Skrip menghitung setiap penampan sebagai kedalaman kali
lebar (aturan D1 dokumen 38 baris 1679-1686).

| Kelompok state | bit di modul ini | rencana 38 baris 1850-1858 |
|---|---|---|
| penampan kandidat penelusuran balik, 128 entri x 114 bit | 14.592 | 14.336 (128 x 112) |
| garis tunda jalur data yang dibangun di modul ini (sel, hp, turunan) | 4.214 | 8.152 (tujuh ring, milik seluruh rantai) |
| sub-tahap RR (deret, antre, riwayat, ra1, pemb, peny, semai, gagal, jeda) | 962 | 896 |
| pelacak fitur dan QRS (i_qrs, i_qrs_pk, kem_qrs dan benderanya) | 91 | 1.232 (lapisan fitur) |
| state ambang adaptif (spki, npki, spkf, npkf) | 132 | di dalam lapisan ambang |
| pencacah ambang_state, delapan kali 32 bit | 256 | |
| pemindai amplop dan pencacah puncak | 64 | |
| keluaran aliran dan sisi (m_*, d_thr, d_pk, o_beat_count) | 237 | 1.024 (penampan keluaran keputusan) |
| introspeksi aditif (dbg_q, dbg_valid_q) | 449 | tidak dianggarkan |
| **jumlah modul ini** | **20.997** | 25.640 (anggaran state seluruh rantai) |

Selisih per kelompok, jujur: penampan kandidat +256 bit (+1,8 persen) karena entri 114 bit
sedangkan rencana 112 bit; sub-tahap RR +66 bit (+7,4 persen) karena kata 16 bit dan
pembilang 20 bit; pelacak fitur jauh lebih kecil (-1.141) karena rencana menganggarkan
seluruh lapisan fitur sedangkan yang wajib di sini hanya satu posisi QRS, satu indeks
puncak, dan satu kemiringan acuan; lapisan keluaran lebih kecil (-787) karena tidak ada
penampan keputusan pada fase ini. Yang bisa saya klaim: tidak ada state tanpa batas,
setiap penampan punya kedalaman tetap dari model, dan tidak ada indeks yang berasal dari
data.

## 5. Pemeriksaan di luar RTL lebih dulu

`~/.hermes/cache/scratch/fase5/rujukan_fase5.py` memakai fungsi beku model
(`rantai.ambang`, `rantai.search_back`, `rantai.gelombang_t_awal`, `rantai.GarisTunda`)
dan hanya menulis ulang pengendara streaming `rantai.py:983-1015`, jadi kolom emas bisa
dimasukkan langsung. Hasilnya **bit-eksak** terhadap keempat CSV emas:

```
peaks 4777  qrs 2596  rr 2595
max peaks in one sample: 1
ambang_state [29, 6, 112, 6, 106, 0, 26, 1202, 2586]
== peaks.csv rows 4777 ==
  pos mismatches 0 / pv 0 / pk_f 0 / kem 0 / i1 0 / i2 0 / sinyal 0 / dalam_pita 0
  ditolak_t 0 / cari_mundur 0 / is_qrs 0 / kind 0
threshold_state.csv spki/npki/spkf/npkf before dan after: 0 berbeda
rr.csv rr_ms dan qrs_cur_sample: 0 berbeda
```

Keadaan sub-tahap RR juga dibandingkan langsung dengan model memakai
`~/.hermes/cache/scratch/fase5/dump_rr_peak.py`, yang mencetak `pembilang, penyebut,
ra1, gagal, jeda, semai` dan hasil gerbang penelusuran balik pada setiap puncak
(salinannya `reports/fase5/bukti-dump_rr_peak.out`). Keluaran itulah yang memutuskan
bahwa gerbang di puncak 91681 memang harus lulus:

```
PK  982 pos   91681 i1 197634271 i2  98817135 iqrs   91343 delta    338 pemb    6200 peny  8 ra1     726
   -> after: pemb    6200 peny  8 ra1     791 gagal  2 jeda 14 semai 12 cari 2
```

Cacat `penanda` yang terakhir juga diuji dengan mengukur. `~/.hermes/cache/scratch/fase5/uji_penanda.py`
(salinan `reports/fase5/bukti-uji_penanda.py`) memakai fungsi beku yang sama, membungkus
`rantai.rr`, dan pada setiap denyut yang deret delapannya sudah penuh menghitung dua versi
aturan: pita dibentuk dari acuan **sesudah** antrean diperbarui (aturan model) dan pita
dibentuk dari acuan **sebelum** (aturan revisi RTL pertama):

```
beats with a full deret (checked)      = 2557
langkah (all in band beats)            = 2592
penanda under the post update band     = 1194   (model state says 1194)
penanda under the pre update band      = 1187   (first RTL revision gave 1195)
difference post minus pre              = 7
first disagreement at checked beat #50 (peak index 149, sample 14571): post 1 pre 0
```

Selisih antar-aturan **tepat 7**, sama dengan kekurangan yang terukur pada jalan penuh
revisi pertama (`penanda` 1195 lawan 1202). Perbedaan pertama muncul pada denyut ke-50,
puncak ke-149, sampel 14571 — **jauh sebelum 100.000**. Karena itu dugaan "selisihnya
muncul setelah 100k sebab potongan 100k bersih" tidak berlaku: sembilan unsur
`ambang_state` memang sengaja tidak dibandingkan pada jalan pendek (kepala testbench
baris 31-34), jadi jalan 100k tidak pernah memeriksa `penanda` sama sekali. Catatan:
pengendara di skrip ini bukan pengendara bit-eksak `rujukan_fase5.py`, jadi angka
mutlaknya bergeser (`langkah` 2592 lawan 2586 pada emas); yang dipakai di sini adalah
selisih antar-aturan dan titik perbedaan pertama, yang tidak bergantung pada pergeseran
itu. Bukti penutupnya adalah gerbangnya sendiri: setelah pita dihitung dari acuan sesudah
pembaruan, jalan penuh memberi `ambang_state[7] dut = 1202 golden = 1202`.

## 6. Penyimpangan, dan hal yang belum dikerjakan

**Penyimpangan yang dilaporkan, tidak disembunyikan:**

1. `s_hp` (26 bit) dan `s_besaran` (24 bit) ditambahkan sebagai masukan aditif di ujung
   daftar porta. Alasan: `s_tdata` selebar 33 bit seluruhnya terpakai kata jendela
   (32 bit tak bertanda, 27 kata di atas 2^31 pada rekaman ini), sedangkan `pk_f` dan
   `kem` diambil model dari ring `hp` dan ring turunan (`rantai.py:933-935`, `:1002`).
   Tanpa keduanya, `filtered_peak`, `slope`, kolom `in_band`/`t_rejected`, dan empat
   unsur `ambang_state` tidak mungkin dihitung. Konsekuensinya `./run_lint.sh --chain`
   merah (bagian 4.1), karena `afib_lite_top.sv` bukan berkas saya.
2. `d_dbg` (448 bit) dan `d_dbg_valid` ditambahkan sebagai keluaran introspeksi aditif di
   ujung daftar porta, sebab gerbang menuntut 9 dari 9 unsur `ambang_state` sementara
   `d_thr`/`d_pk` hanya membawa `i1` dan `pk_f`.
3. Konstanta Fase 5 dideklarasikan sebagai `localparam` **di dalam modul**, bukan di
   `afib_lite_pkg.sv`, karena paket itu bukan berkas saya dan sudah beku sebelum Fase 5.
   Setiap nilai dikutip dengan nomor baris model di komentar.
4. Entri penampan kandidat **114 bit** sedangkan rencana baris 1854 menganggarkan 112 bit.
   112 bit (32+32+24+24) tidak cukup: `pk_f` pada rekaman ini mencapai 18.865.152 > 2^24,
   jadi bidang 24 bit akan memotongnya dan pemilihan kandidat bisa salah. Susunan saya:
   posisi 32 bit, kata amplop 32 bit, besar `hp` 26 bit (lebar `W_HP` beku), besar turunan
   24 bit. Selisih +256 bit pada kelompok itu.
5. Garis tunda `hp` dan turunan dibangun **di dalam modul ini**, padahal rencana
   menempatkannya di modul jalur data, sebab daftar porta beku tidak membawa kedua deret
   itu.
6. Kolom `qrs_sample_index` pada data emas tidak dapat diturunkan dari `is_qrs`: dua baris
   refit merekam di posisi yang lebih awal dan dua baris lain justru menerima QRS itu.
   Testbench memakai konvensi penurun vektor: baris yang merekam QRS memancarkan `EV_QRS`
   dengan indeks = posisi yang direkam. Ini bertentangan dengan pembacaan bench sesi lain
   (yang menuntut `m_ev_idx` = `sample_index` untuk keempat 4.777 baris, lihat
   `reports/fase5/LAPORAN-FASE5.sesi-lain-verifikasi.md` bagian 3.4). Konvensi di sini
   mengikuti generator vektor dan K7 di `SPEC-TERKUNCI-FASE5.md`, dan untuk keempat baris
   itu kolom `sample_index` memang bukan posisi yang direkam. Keputusan kontrak ini perlu
   diputuskan agen induk karena dua bench menuntut hal yang berbeda.
7. Jalur gagal testbench awalnya hanya `$finish`, sehingga jalan penuh yang gagal
   (`sim-lengkap-01.out`, `ambang_state[7]` meleset) tetap keluar dengan `rc=0`. Itu
   sudah diperbaiki: tiga jalur gagal (`+VECTOR` hilang, `+EXPECT` hilang, kapasitas di
   luar batas) dan jalur putusan akhir sekarang `$fatal(1, ...)`, dan kondisi lulus juga
   menuntut `phase == PH_DONE` supaya jalan yang kehabisan siklus tidak bisa lulus.
   Bukti: `sim-negatif-02.out` gagal dengan `negA_rc=1`.
8. `rtl/afib_lite_pkg.sv` bertambah kode event `EV_REJECTED_T`/`EV_NOISE` dari sesi lain.
   Modul ini tidak memakainya (sideband hanya `EV_QRS` dan `EV_PEAK_CAND`, sesuai
   vektor emas Fase 5), dan regresi paket sesi lain tetap lulus menurut laporan mereka.

**Belum dikerjakan / tidak diklaim:**

1. Gerbang "jumlah flip-flop sama dengan rencana" belum ditutup **tepat angka**: cacah
   konstruksi 20.997 bit terhadap anggaran seluruh rantai 25.640 bit, dengan rincian
   selisih per kelompok di bagian 4.4. Belum ada sintesis: rute repo `run_synth.sh` tidak
   dijalankan di sini karena yosys 0.70 di mesin ini macet di pass ABC dan angka antar rute
   tidak boleh dibandingkan (sesi lain juga melaporkan yosys mereka belum selesai setelah
   20 menit di pass TECHMAP).
2. Keluaran `m_tdata`/`m_tuser`/`m_tlast`/`m_sample_idx` hanya diperiksa terhadap perilaku
   terbaca (`m_tvalid` memakai deret yang sama dengan `d_valid`); tidak ada vektor emas
   untuk paket aliran tingkat fase, jadi yang diuji adalah kesetaraan dengan kolom jendela
   pada waktu yang sama.
3. Kode `EV_REJECTED_T`/`EV_NOISE` yang ditambahkan sesi lain ke paket tidak dipakai modul
   ini: sideband hanya memancarkan `EV_QRS` dan `EV_PEAK_CAND`, sesuai vektor emas Fase 5.
4. Uji luapan sintetis (rencana baris 1944) belum ada. Yang tersedia: rel dan penanda
   luapan, dengan bukti tidak ada rel yang menyala dan `m_overflow` 0 pada dua jalan penuh.
5. Determinisme diuji sebagai dua jalan penuh identik pada revisi yang diserahkan
   (bagian 4.3); tidak ada uji acak atau uji variasi parameter lain.
6. Kontrol negatif dijalankan pada jalan pendek dengan larik per-puncak yang rusak
   (`sim-negatif-02.out`, `rc=1`). Kontrol negatif sepanjang 450.000 yang khusus membuat
   gerbang `ambang_state` gagal belum dijalankan; yang membuktikan gerbang itu aktif
   adalah perbandingan `sim-lengkap-01.out` (`ambang_state[7]` 1195 lawan 1202, FAIL)
   dengan `sim-lengkap-05.out` (1202 lawan 1202, PASS) pada revisi yang sama kecuali
   perbaikan pita.
7. `o_beat_count` dan kolom aliran lain diperiksa pada waktu yang sama dengan jendela;
   tidak ada vektor emas untuk paket aliran per fase.

## 7. Log mentah

Semua di `rtl-synthesis/reports/fase5/`:

| Berkas | Isi |
|---|---|
| `IMPLEMENTASI-PROGRES.md` | log progres yang ditulis sambil jalan, termasuk empat cacat yang ditemukan dan cara menemukannya |
| `lint-peak_detect-01..12.out`, `lint-chain-01.out` | riwayat lint modul dan lint rantai |
| `sim-4000-01..03.out`, `sim-40000-02.out`, `sim-90000-diag.out`, `sim-100000-diag*.out` | riwayat simulasi dan tangkapan diagnostik |
| `sim-lengkap-05.out`, `sim-lengkap-06.out` | dua jalan penuh 450.000 pada revisi terakhir, `PASS`, ringkasan identik |
| `sim-lengkap-03.out`, `sim-lengkap-04.out` | pasangan jalan penuh sebelumnya, ringkasan identik dengan md5 yang sama |
| `sim-lengkap-01.out` | jalan penuh yang masih gagal (`ambang_state[7]` 1195 lawan 1202), disimpan sebagai pembanding |
| `sim-lengkap-02.out` | jalan penuh yang mati di tengah karena `pkill` saya sendiri; bukan bukti |
| `sim-negatif-02.out` | kontrol negatif yang sah: larik per-puncak dirusak, `FAIL`, `$fatal`, `rc=1` |
| `sim-negatif-01.out` | kontrol negatif kosong (hanya larik yang dilewati jalan pendek yang dirusak); bukan bukti |
| `hitung_ff.py`, `hitung_ff.out` | cacah flip-flop per penampan |
| `bukti-tb_probe.sv`, `bukti-probe_rr1.out`, `bukti-probe_rr2.out` | probe keadaan internal (di luar repo) |
| `bukti-dump_rr_peak.py`, `bukti-dump_rr_peak.out` | keadaan sub-tahap RR dari model beku |
| `bukti-uji_penanda.py`, `bukti-uji_penanda.out` | dua aturan `penanda`, selisih 7, titik perbedaan pertama |
| `siapkan_vektor_fase5.out` | log penurunan vektor |
| `peak_detect.sv.sesi-lain-9c680d12.bak`, `LAPORAN-FASE5.sesi-lain-verifikasi.md` | berkas sesi lain yang disimpan, bukan tulisan saya |

## 8. Perintah ulang, apa adanya

```
cd rtl-synthesis
./run_lint.sh ../rtl/peak_detect.sv peak_detect ../rtl/afib_lite_pkg.sv
./run_lint.sh --chain                     # merah: 4 PINMISSING di afib_lite_top.sv
python3 reports/fase5/hitung_ff.py
python3 ../rtl/tb/vektor/fase5/siapkan_vektor_fase5.py
./run_sim.sh ../rtl/tb/tb_puncak.sv ../rtl/afib_lite_pkg.sv ../rtl/peak_detect.sv \
    -- +VECTOR=../rtlplan2/fase0 +EXPECT=../rtl/tb/vektor/fase5 +LIMIT=40000
./run_sim.sh ../rtl/tb/tb_puncak.sv ../rtl/afib_lite_pkg.sv ../rtl/peak_detect.sv \
    -- +VECTOR=../rtlplan2/fase0 +EXPECT=../rtl/tb/vektor/fase5
```

Tanpa `+LIMIT` testbench memakai seluruh 450.000 sampel. `rc=0` bukan bukti lulus: hanya
`$fatal` yang membuat `rc != 0`, karena itu lulus ditentukan baris `tb_puncak: PASS`
beserta baris penghitung di atasnya, dan PASS dengan `words compared: 0` diperlakukan
sebagai gagal (testbench memeriksa `nout == limit_n`).

## 9. sha256 berkas yang diserahkan

```
d4cfd9c6c3f77b67f31a26f2b8b8957666c5672becca45cb656dfc823b57d547  rtl/peak_detect.sv
f9b506310ae4317424a671a410e110a00be18db4cc84ad745b7fb08264943eb5  rtl/tb/tb_puncak.sv
b6944cbf1c34b48c1eec69ac0fffee1de5ea3358648858e167f78ec1b2cdab25  rtl/tb/vektor/fase5/siapkan_vektor_fase5.py
eaba8151fb0dcafba23968693a10b976b1ed11bc1a85c39ea6658fb07232c43d  rtl-synthesis/reports/fase5/hitung_ff.py
90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5  model/rantai-afib-lite/rantai.py
```

Baris terakhir adalah model beku, disertakan sebagai bukti tidak tersentuh: nilainya sama
dengan catatan di kepala laporan ini.
