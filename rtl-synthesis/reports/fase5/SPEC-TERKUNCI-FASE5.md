# SPESIFIKASI TERKUNCI — FASE 5: Ambang adaptif dan deteksi puncak

Dokumen ini adalah **satu-satunya sumber kebenaran** untuk Fase 5. Disusun oleh agen induk dari
tiga hasil riset (plan §4.7/§4.8, model beku `rantai.py`, dan kontrak data emas `rtlplan2/fase5/`).
Implementer dan verifier **wajib** membaca dokumen ini sebelum menyentuh berkas apa pun.

## 0. Kepemilikan berkas (eksklusif — ada sesi lain yang bekerja di repo ini)

Boleh ditulis **hanya**:

| Berkas | Keadaan |
|---|---|
| `rtl/peak_detect.sv` | ganti badan placeholder dengan badan nyata; **porta, parameter, dan nama sinyal TIDAK boleh berubah** |
| `rtl/tb/tb_puncak.sv` | berkas baru |
| `rtl-synthesis/reports/fase5/**` | berkas baru (log mentah) |
| `rtl-synthesis/reports/LAPORAN-FASE5.md` | berkas baru (laporan) |

**DILARANG disentuh:** `model/**` (beku; sha256 `rantai.py` harus tetap `90df6e5b457307d3…`),
`rtl/*.sv` selain `peak_detect.sv`, `rtl/tb/*` selain `tb_puncak.sv`,
`rtl-synthesis/run_lint.sh`, `rtl-synthesis/run_sim.sh`, `rtl-synthesis/reports/*.native.*`,
`rtl-synthesis/mcy/**` (milik sesi lain), `rtl-synthesis/reports/LAPORAN-AUDIT-BENCH.md`,
`rtl/TASK_BRIEF.md`. **Tidak ada `git add`, tidak ada commit, tidak ada `git checkout`.**

## 1. Gerbang yang harus lulus (verbatim dari plan 38)

Baris tabel fase 5, `rtlplan2/final38.md:122`:

> | 5 | Ambang adaptif dan deteksi puncak | `peak_detect.sv` | `tb_puncak` 0 dari 4.777 puncak; 9 dari 9 `ambang_state`; `qrs` 2.596 dari 2.596; jumlah flip-flop sama dengan rencana | 10 jam | pemilik RTL |

Baris testbench, `rtlplan2/final38.md:908`:

> | 8 | `tb_puncak.sv` | pemilih puncak, ambang adaptif, penelusuran balik | `jendela` | `puncak` (4.777), empat larik ambang, `qrs` (2.596) | 0 dari 4.777 puncak; 9 dari 9 unsur `ambang_state`; 2.596 denyut sama |

Langkah fase (verbatim, `final38.md:2054-2060`): tulis (1) antrean monoton dua pembanding untuk
pemilih puncak; (2) pemindai berurutan 51 nilai untuk maksimum mutlak `hp`; (3) ambang i1 30 bit dan
i2 29 bit dengan pembaruan eksponensial `(7a + p) >> 3`; (4) penyemaian dari dua detik pertama;
(5) penampan kandidat 128 entri dengan penanda luapan; (6) penelusuran balik dengan palang silang
83/50; (7) lint lalu simulasi.

Risiko yang dinyatakan plan: identitas `(7a + p) >> 3` **gagal** bila potong-ke-arah-nol dipakai
(terukur 87.316 dari 200.000 pasangan), dan kekeliruan itu muncul sebagai penyimpangan ambang yang
tumbuh perlahan, bukan galat tunggal.

## 2. Keputusan yang dikunci agen induk (jangan diubah tanpa melapor)

**K1 — Semua pergeseran kanan aritmetika (RND_FLOOR).** Pakai `>>>` pada nilai bertanda, atau
`(7*a + p) >>> 3` pada word. `a + ((p-a) >> 3)` **identik** dengan `(7a+p) // 8` (Teorema 6).
Truncation-toward-zero dilarang di seluruh berkas ini.

**K2 — Mulai dari nol, bukan disemai angka.** Model memulai `spki=npki=spkf=npkf=0`
(`rantai.py:612`), sehingga `i1=f1=i2=0` dan puncak pertama dengan `pv>0` langsung dianggap sinyal.
Paritas bit memerlukan **nol**. Frasa plan "penyemaian dari dua detik pertama" adalah *akibat*
(pemanasan 23–32 denyut), bukan instruksi menulis nilai semai. Jangan mengarang nilai semai.

**K3 — Lebar state anti-pembelitan.** Register state (`spki`, `npki`, `spkf`, `npkf`) disimpan pada
lebar node jendela (**33 bit**) tanpa klip, karena `spki` terukur sampai **717.628.984** dan
plafonnya adalah rel jendela. Node `i1`/`f1` disempitkan ke `W_THR` (30) hanya saat diekspor ke
`d_thr`, dan `i2 = i1 >>> 1` (29 bit). Setiap flip-flop tambahan di luar daftar penampan wajib
dilaporkan sebagai penyimpangan dengan alasan.

**K4 — Semantik porta introspeksi (porta beku, nama berbeda dari plan).**
`d_thr` = `i1` (ambang adaptif, 30 bit) pada puncak yang sedang diproses;
`d_pk` = `pk_f` (maksimum mutlak `hp` pada `pos-25 .. pos+25`, terukur maks 18.865.152 → muat 30 bit).
Plan menyebut `d_peak_val` (33 bit) yang **tidak ada** di daftar porta beku — perbedaan ini
dilaporkan, bukan diam-diam diubah.

**K5 — Pemetaan peristiwa (sideband).** `m_ev_valid` tinggi satu siklus per peristiwa;
`m_ev_kind` = `EV_QRS` (1) untuk QRS diterima **termasuk** hasil penelusuran balik,
`EV_PEAK_CAND` (2) untuk setiap kandidat puncak yang ditolak, `EV_NONE` (0) selain itu.
`m_ev_idx` = indeks **sampel** peristiwa. `m_ev_val` = nilai amplop `pv` (32 bit).
`o_beat_count` = cacah QRS diterima sejak reset (dinaikkan pada `i_clear_counters` → 0).

**K6 — Batas pemindai mengikuti jalur streaming.** Model batch (`rantai.py:297`) mengecualikan
`i = n-r`; jalur streaming (`rantai.py:987`) memasukkannya. **Vektor emas dihasilkan jalur
streaming**, jadi RTL memakai syarat `scan + RADIUS_PUNCAK <= n` (inklusif). `scan` adalah state
lintas sampel, nilai awal `RADIUS_PUNCAK`.

**K7 — Tie-break penelusuran balik: `v > best` ketat.** Pada nilai amplop sama, kandidat **paling
awal** (indeks terkecil) menang (`rantai.py:593`). Rentang pemindaian kandidat:
`j = i_qrs_puncak + 1 .. i_puncak` **inklusif** (kandidat boleh puncak saat ini sendiri).

**K8 — Penampan kandidat berbatas tetap.** `SEARCH_BACK_DEPTH = 128` entri, lebar jarak 15 bit,
**tanpa indeks dari nilai data**; luapan ditandai (`m_overflow` + laporan), bukan menggelung.

## 3. Algoritme (dari model beku `model/rantai-afib-lite/rantai.py`)

### 3.1 Pemindaian puncak (per sampel, state lintas sampel)

```
scan = 27                                   # state, init RADIUS_PUNCAK (:940)
while scan + 27 <= n:                       # :987-993
    v = ring_sel[scan]                      # nilai node jendela (amplop) pada indeks scan
    if v > 0 and v >= maks(ring_sel[scan-27 .. scan+27]):
        terima kandidat puncak `scan`;  scan += 27
    else:
        scan += 1
```
Baca indeks di luar rentang → **0** (`GarisTunda.ambil`, `:112-113`). Jendela 55 nilai = 2×27+1.
Rekomendasi plan B: **antrean monoton dua pembanding per sampel**, bukan pohon 55 lebar
(pohon = 123× terlalu dalam: 961,1976 ns).

### 3.2 Per puncak: nilai amplop, nilai terfilter, kemiringan

```
pv   = ring_sel[pos]                                   # :1001  nilai amplop di puncak
pk_f = ring_hp.maks_mutlak(pos - 25, pos + 25)          # :1002  JENDELA_F = 25 → 51 nilai
kem  = ring_besaran.maks_mutlak(max(pos-18,0), pos+18)  # :333   SETENGAH_JENDELA = 18 → 37 nilai
```
`pk_f` dan `kem` = maksimum **mutlak**. Ring: `ring_hp`, `ring_besaran`, `ring_sel`, masing-masing
64 kata (`:933-935`), 32 bit.

### 3.3 Ambang adaptif (snapshot SEBELUM pembaruan apa pun)

```
i1 = npki + ((spki - npki) >>> 2)      # :655  RND_FLOOR
f1 = npkf + ((spkf - npkf) >>> 2)      # :656  RND_FLOOR
i2 = i1 >>> 1                          # :657
sinyal = (pv > i1)                     # :662  perbandingan KETAT
delta  = (i_qrs == None) ? None : (pos - i_qrs)          # :663-664  satuan SAMPEL
if sinyal and delta != None and delta < PANTUL: sinyal = False   # :665-666  PANTUL = 50
```
Pembaruan (baris model → bentuk RTL eksak):

| jalur | model | baris | bentuk RTL |
|---|---|---|---|
| puncak diterima | `spki += (pv - spki) >> 3` | 683 | `spki' = (7*spki + pv) >>> 3` |
| diterima, `pk_f > f1` | `spkf += (pk_f - spkf) >> 3` | 685 | `(7*spkf + pk_f) >>> 3` |
| diterima, `pk_f <= f1` | `npkf += (pk_f - npkf) >> 3` | 687 | `(7*npkf + pk_f) >>> 3` |
| bukan sinyal (noise) | `npki += (pv - npki) >> 3` | 699 | `(7*npki + pv) >>> 3` |
| bukan sinyal (noise) | `npkf += (pk_f - npkf) >> 3` | 700 | `(7*npkf + pk_f) >>> 3` |
| refit, `vf > f1` | `spkf += (vf - spkf) >> 2` | 706 | `(3*spkf + vf) >>> 2` — pakai nilai **pre-update** |
| refit, `vf <= f1` | `npkf += (vf - npkf) >> 2` | 708 | `(3*npkf + vf) >>> 2` |
| refit | `spki += (v - spki) >> 2` | 709 | `(3*spki + v) >>> 2` |

Aturan gelombang T (`:340`, `:671-677`): `ditolak_t = dalam_pita and (2*kem < kem_qrs)`; hanya
diperiksa bila `sinyal` masih benar dan `dalam_pita`. `dalam_pita = (delta != None) and
((delta << 2) < BATAS_PITA_SAMPEL)` dengan `BATAS_PITA_SAMPEL = 360` (`:58`, `:68`, `:338`).

Kandidat kedua (`:680-681`): `if not sinyal and pv > i2: calon_kedua += 1` — dihitung **sesudah**
refrakter dan gelombang T boleh mematikan `sinyal`.

### 3.4 Penelusuran balik (`:569-600`)

```
if i_qrs == None: return None                       # :572-573
delta = pos - i_qrs
if penyebut > 0: aktif = (200 * delta * penyebut) > (83 * pembilang)     # :580-581
elif ra1 > 0:    aktif = (200 * delta) > (83 * ra1)                     # :582-583
else:            aktif = False
if not aktif: return None
best = None
for j = i_qrs_puncak+1 .. i_puncak:                  # :589-591  inklusif
    v = puncak_nilai[j]
    if (i2 < v <= i1) and (best == None or v > best[1]): best = (..., j)  # :593 ketat
```
Komparator: `200*delta*penyebut <= 200*32767*8 = 52.427.200` dan `83*pembilang <= 43.515.240`
→ **26 bit unsigned** cukup. Saat refit berhasil, QRS dicatat pada indeks sampel `sp` (bukan `pos`).

### 3.5 Jadwal (plan §4.7/§4.8)

6 siklus per puncak untuk jalur ambang (ambang, ambang terfilter, i2, SPKI, SPKF/NPKF, palang
silang), 1 siklus per sampel untuk pemindai puncak, ditambah 51 siklus per puncak untuk pemindai
maksimum mutlak. Latensi kasatmata dinyatakan lewat `m_sample_idx`, bukan lewat hitungan siklus TB.

## 4. Konvensi testbench (wajib diikuti; dari testbench fase 1–4 yang sudah ada)

1. `+VECTOR=<dir>` **wajib**; tanpa itu cetak galat lalu `$finish`. Plusarg selalu **sesudah `--`**.
2. Vektor dibaca `$readmemh` dari direktori itu; memori **tepat sebesar `NWORD` manifes**;
   `reg [31:0] mem [0:449999]` untuk kolom 450.000 kata.
3. **Tidak ada satu pun angka hasil ukur yang ditulis di dalam testbench** (`final38.md:890-897`).
4. Kolom emas **wajib dibaca unsigned**; 27 kata kolom `jendela` bernilai di atas 2³¹ (maks
   3.105.281.786). Bandingkan dengan `!==` setelah perluasan nol ke lebar porta penuh.
5. Cetak baris ringkasan `mismatches = %0d out of %0d` **dan** `PASS`. **PASS dengan
   `words compared: 0` adalah kegagalan, bukan lulus** (`final38.md:896-897`).
6. `rc=0` **bukan** bukti lulus: hanya `$fatal` membuat rc≠0. Karena itu TB wajib memanggil
   `$fatal(1, …)` pada setiap pelanggaran gerbang.
7. Masukan TB: `s_tdata` ← kolom `04015.jendela.hex` (keluaran `integrator.sv`),
   `s_sample_idx` = indeks, `s_tuser` = `feed[7:0]`, `s_tlast` = 1 pada kata terakhir.
8. `+LIMIT=<n>` (bawaan 450.000) untuk mode pendek; jalankan mode pendek lebih dulu, lalu penuh.

## 5. Nilai harapan (dari `rtlplan2/fase5/LAPORAN-FASE5.md`, data emas jangan diubah)

| Besaran | Nilai |
|---|---|
| Baris `puncak` | 4.777 |
| `is_qrs` puncak | 2.596 |
| Baris `rr` | 2.595 |
| `ambang_state` (9 unsur) | `[29, 6, 112, 6, 106, 0, 26, 1202, 2586]` |
| Census peristiwa | `qrs` 2.590; `rejected_t` 1.909; `noise` 272; `qrs_search_back` 6 |
| Census pembaruan | `spki_update` 2.590; `t_wave_reject` 1.909; `npki_update` 272; `search_back_refit` 6 |
| Mark RR | keep 2.186; split 397; drop 9; gap 3 |
| `lo_i1 .. hi_i1` | 0 … 206.147.681 |
| `search_back` rentang | 34.794.360 … 145.902.581 |
| `i2 == i1 >> 1` | benar pada seluruh 4.777 puncak |

`ambang_state` urut = `[calon_kedua, cari_mundur, diperiksa, ditolak, diterima_pita, berisiko,
semai, penanda, langkah]` (`rantai.py:1051-1053`). **`state["ditolak"]` (6) BUKAN peristiwa
`rejected_t` (1.909)** — dua definisi berbeda untuk nama yang mirip.

## 6. Jebakan paritas yang wajib dinyatakan eksplisit

1. Snapshot pre-update: `i1, f1, i2`, `lo_i1/hi_i1`, dan `delta` dihitung **sebelum** pembaruan;
   `_catat` menaikkan `i_qrs`/`i_qrs_puncak` **sesudahnya**.
2. `i_qrs = None` mematikan tiga hal: gerbang refrakter, `dalam_pita`, dan penelusuran balik.
3. `sinyal` dimodifikasi tiga tempat berurutan: `pv > i1` → refrakter → gelombang T. `calon_kedua`
   dihitung sesudah semuanya.
4. `puncak_nilai[pos]` di-append **sebelum** `ambang()`; `puncak_terfilter` dan `puncak_kemiringan`
   **sebelum** `search_back()`. Keempat larik sejajar dengan larik `puncak`.
5. Asimetri jalur refit: `:706` memakai lokal `spkf` (pre-update), `:708` memakai `state["npkf"]`
   (yang sudah ditulis `:700`). Setara hanya karena jalur itu tidak dieksekusi bersama.
6. `spki - npki` dan `spkf - npkf` **bisa negatif** → pergeseran harus aritmetika.
7. Baca indeks di luar rentang/kapasitas → **0** (kondisi awal nol), bukan galat.
8. Pemindai menunda 27 sampel (`scan + 27 <= n`).

## 7. Perintah (repo-pinned saja — JANGAN pakai `~/eda`)

```bash
cd rtl-synthesis
./run_lint.sh ../rtl/peak_detect.sv peak_detect ../rtl/afib_lite_pkg.sv
./run_lint.sh ../rtl/tb/tb_puncak.sv tb_puncak ../rtl/afib_lite_pkg.sv ../rtl/peak_detect.sv
./run_lint.sh --chain
./run_sim.sh ../rtl/tb/tb_puncak.sv ../rtl/afib_lite_pkg.sv ../rtl/peak_detect.sv -- +VECTOR=<dir> [+LIMIT=n]
```
Toolchain: `rtl-synthesis/debroot` (Yosys 0.33, Icarus 12.0, Verilator 5.020). **Jangan** memakai
`~/eda/oss-cad-suite` (yosys 0.70 di mesin ini macet di pass ABC, dan angka antar rute tidak boleh
dibandingkan). Vektor emas: `rtlplan2/fase0/` (juga tersedia di
`~/.hermes/cache/scratch/rtlplan2/fase0` lewat symlink). Data rujukan Fase 5: `rtlplan2/fase5/`.

## 8. Pelaporan (wajib)

Tulis `rtl-synthesis/reports/LAPORAN-FASE5.md` dengan gaya laporan Fase 4: kutip persyaratan apa
adanya, tabel berkas + sha256, keluaran gerbang **mentah**, bagian "penyimpangan dan hal yang belum
dikerjakan" yang jujur, dan perintah ulang. Simpan log mentah di `rtl-synthesis/reports/fase5/`.
Laporkan setiap poin yang **tidak** bisa ditutup melalui porta beku — jangan diklaim lulus.
