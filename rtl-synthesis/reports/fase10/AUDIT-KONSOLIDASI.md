# Konsolidasi Audit — NABDHA AFIB-LITE (21 Oktober 2026, dini hari)

Dasar: dua audit read-only lewat subagent (integritas bukti, antarmuka dan satuan), ditambah dua
pemeriksaan yang saya jalankan sendiri. Tidak ada berkas repo yang disentuh oleh seluruh audit.

## 1. Yang tertutup dan terbukti

| Butir | Hasil | Bukti |
| --- | --- | --- |
| Berkas beku `rantai.py` | sha256 `90df6e5b…4f1fe5`, cocok di semua manifes | audit integritas bagian 1 |
| Berkas beku `afib_lite_pkg.sv` | sha256 `3ea2ab5c…`, cocok | audit integritas bagian 1 |
| 83 entri vektor vs manifes | 82 cocok, 1 beda (hash-diri manifes fase8, cacat yang sudah diakui) | audit integritas bagian 2 |
| Angka gerbang fase 5–11 | semuanya ditemukan, dengan berkas dan nomor baris | audit integritas bagian 4 |
| Peta 38 register `0x00..0x94` | identik driver vs `regs_axi.sv`, termasuk W1C dan WO | audit antarmuka bagian A |
| Satuan ambang | `33/200 → 10813` dan `63/100 → 10322`, galat di bawah 1 LSB | audit antarmuka bagian B |
| Penanda `s_tuser` bit 0..3 dan `s_sample_idx` | tersambung, bit GAP punya konsumen fungsional | audit antarmuka bagian C |
| Asal kolom emas Fase 5 | `04015.peaks.csv` kolom `sample_index` identik dengan larik `puncak` model, 4777 baris, selisih maks 0 | pemeriksaan saya: bandingkan kolom csv vs `fixture/04015_30m.npz` |
| Provenance emas fase 6–9, 11 | skrip punya pemeriksaan ulang terhadap ekspresi model | audit integritas bagian 3 |

## 2. Temuan terbuka

### F1. Selisih cacah `rejected` pada instans `t_rule` mandiri — TERJELASKAN, bukan lubang baru

- `afib_lite_top.sv:648` menyambungkan `.o_reject(tw_reject)`, jadi sinyal yang dibandingkan
  testbench adalah keluaran fungsional, bukan cermin introspeksi (`d_tw` barulah cermin).
- `tb_top.sv:568-576` membandingkan `tw_dalam_pita` dan `tw_reject` dengan bit 1 dan bit 2 kolom
  flag emas per puncak. Cetakan `RULEDBG` hanya diagnostik: **tidak dihitung** ke gerbang.
- Pada kedua lengan 450.000 yang berjalan sekarang, baris `RULEDBG` muncul lagi
  (`row 73 pos 6845`), jadi ini bukan artefak run lama. `RULEDBG order` tidak pernah muncul,
  jadi urutan dan indeks puncak selaras dan perbandingannya sebaris.
- Sifatnya: DUT menolak lebih banyak, konsisten dengan cacah `rejected` 547 vs emas 473 (150k) dan
  2014 vs 1909 (450k).
- Dampak ke keluaran bergerbang: **nihil**. Kolom yang dibandingkan (enam aliran, puncak, irama RR,
  fitur, kelas) tetap nol beda, dan sensus triase per jendela sama dengan emas.
- **Kesimpulan setelah pemeriksaan lanjutan: ini bukan temuan baru.** Selisih ini sudah dijelaskan
  di `rtl-synthesis/reports/fase10/PROGRES.md` bagian *DUA CACAH YANG BERBEDA* (baris 81-103), yang
  memang belum dibaca audit. Isinya: kolom bendera `peak_detect` — yang benar-benar memutuskan
  rantai — **0 beda dari 4777 baris**; yang berbeda adalah instans `t_rule` **mandiri** di top, yang
  menerima acuan `kem_qrs` dari baris rekaman (`EV_QRS`) sedangkan model memajukan acuan itu di dua
  jalur sinyal (`rantai.py:695` dan `:710`) dan kedua jalur itu diikuti `peak_detect`. Keluaran
  instans mandiri hanya masuk mux debug.
- Testbench sendiri menyatakan ini, bukan menyembunyikannya:
  `NOTE t_rule rejected peak verdicts dut=2014 gold=1909 (dut is stricter; the rule output feeds
  only the debug mux)` dan `NOTE ... deviation, not gated`.
- Cacahnya konsisten di tiga jalur: 150.000 Verilator → 547 − 473 = 74 = 74 baris `RULEDBG`;
  450.000 Verilator → 2014 − 1909 = 105 = 105 baris; dan **450.000 Icarus juga 105 baris** —
  mesin kedua mereproduksi angka mesin pertama.
- Yang tetap perlu disebut dalam laporan akhir: perbedaan ini **nyata ada**, terkurung di jalur
  debug, dan bukan bukti kesetaraan yang gagal. Jangan dihapus dari laporan, cukup dinyatakan.

### F2. Kata masuk jalur papan belum sama dengan kata yang dipakai gerbang

Rincian lengkap di `TEMUAN-INTERFACE-INGEST.md`. Ringkas: kolom emas `masukan16` adalah nilai
sesudah penguatan front-end (cacah x 2047/1000 x 16), sedangkan `s_tdata` menerima cacah mentah.
Fixture yang diputar `ps_driver_afib.py` berisi nilai sesudah penguatan. Kalau disuapkan apa adanya
ke `SAMPLE_FIFO`, rantai akan berpenguatan dua kali.

### F3. `0x6C` dan `0x70` tidak punya konsumen di RTL

`regs_axi.sv:377-394` hanya membukukan tulisan; pencacahnya tidak keluar ke porta mana pun
(`:151-158`) dan tidak ada jalur ke `acq_frontend`. Jadi papan belum bisa disuapi sampel sama sekali
sampai jembatan FIFO dibuat.

### F4. Enam angka dikutip tanpa log pendukung — 5 dari 6 sudah ditindak

| Angka | Keadaan semula | Tindakan 21 Oktober 2026 |
| --- | --- | --- |
| `19.995` beda | tidak ada log | **ditandai di sumbernya**: `LAPORAN-AUDIT-BENCH.md` bagian A2 kini memuat blok "Status bukti" yang menyatakan salinan RTL tersuntik dan log jalannya tidak disimpan, sehingga angkanya tidak bisa diulang dari artefak |
| `1.516` dan `3.608` pada nodus `pre` | tidak ada log | sama seperti di atas |
| `8 mutan timeout` | tidak ada log | **dibiarkan**: penjelasannya ada di laporan (batas 120 detik per simulasi) tetapi cacahnya tidak berjejak; ini satu-satunya butir yang tinggal catatan |
| `86,80 %` | log alat mencetak 59,00 % dan 67,80 %; 86,80 % hitungan sendiri | **TERBUKTI dari basis data kampanye**: `mutations` 1.000, `tags` = `COVERED` 278 / `UNCOVERED` 132, `results` = `FAIL` 278 / `PASS` 132, `results` 410 + `queue` 590 = 1.000, sehingga `(1000-132)/1000 = 86,80 %`. Jejak kuerinya kini tertulis di `LAPORAN-AUDIT-BENCH.md` bagian A3 |
| `17 siklus/sampel` sebagai "pengukuran bench" | sebenarnya konstanta rancangan, `tb_derivative.sv:57` | **dikoreksi di sumbernya**: kalimat di `LAPORAN-AUDIT-BENCH.md` bagian A5 kini menyatakan 17 siklus adalah latensi rancangan (disebut di komentar `CAD = 24`), bukan hasil ukur tersendiri |
| rantai lint `rc=0, 0 peringatan` | log lint repo memuat `Exiting due to 13 warning(s)` | **diukur ulang**: log baru di dalam repo, `reports/fase10/lint_chain_20261021.log` (`rc=0`, senyap); 13 peringatan itu milik `fase11` (`PINMISSING` Verilator), bukan rantai fase 5–10 |

Sisa yang masih perlu dijaga: satu cacah (`8 mutan timeout`) dan dua angka efek suntikan yang sudah
dinyatakan statusnya di laporan sumber. Yang tidak boleh dilakukan adalah mengutipnya sebagai
keluaran alat.

### F5. Hash `adapter.py` di dokumen lama — snapshot historis, bukan nilai salah

`f6444932…` adalah nilai yang berlaku. Saya verifikasi ulang alih-alih percaya catatan: `sha256sum`
berkas kerja memberi `f644493255ee1218d8ca49c37aae3858253a8ca2ddd0aa7371bc2fde24ccdba1`, dan
`git status` bersih terhadap `HEAD`, jadi isinya sama dengan yang di `HEAD` dan di
`KEPEMILIKAN-BERKAS.md`.

Nilai `b4adaa17…` di `rtlplan/qformat_*.txt:9` dan `rtlplan/A-lebar-bit.md:14` **bukan angka yang
salah**, melainkan nilai yang tercatat ketika dokumen itu ditulis. Buktinya ada di dalam repo:
`rtlplan/H1-adapter-fix.md:8` mencatat kembalinya `adapter.py` ke keadaan itu, dan blok `:389-391`
memperlihatkan ketiga nilai berdampingan (`sebelum revert`, `blob di index`, `sesudah revert`).

Konsekuensinya menentukan cara memperbaikinya: blok fingerprint di dokumen itu adalah **keluaran
mentah alat**, dan menyuntingnya justru menghapus jejak versi yang dirujuk. Yang benar adalah
memberi keterangan, dan itu sudah dikerjakan: tabel §0 `rtlplan/A-lebar-bit.md` kini menyebut nilai
`b4adaa17…` sebagai nilai saat dokumen ditulis sekaligus menyebut nilai yang berlaku sekarang.
Temuan ini karena itu saya turunkan dari "nilai salah" menjadi "butuh keterangan".

### F6. Angka gerbang hanya hidup di luar repo — SUDAH DIPERIKSA dan ditutup untuk Fase 10

Temuan ini benar untuk Fase 10, tetapi tidak untuk fase sebelumnya. Pemeriksaan 21 Oktober 2026:
`rtl-synthesis/reports/` sudah memuat direktori bukti per fase — `fase2` 7 berkas, `fase4` 23,
`fase5` 44, `fase6` 12, `fase7` 57, `fase8` 15, `fase9` 13 — berisi log jalankan penuh, log lint dan
keluaran kontrol negatifnya. Jadi angka fase 5–9 memang sudah punya rumah di repo.

Yang benar-benar hanya hidup di area kerja adalah bukti Fase 10: **log lulus 450.000 kedua lengan
Icarus**, log lengan mentah Verilator, matriks checksum, dan provenance sintesis. Semuanya sudah
disalin ke `rtl-synthesis/reports/fase10/bukti/` lengkap dengan indeks `BACA.md` yang menyebut klaim
apa yang disokong tiap berkas. Log sintesis berukuran megabyte sengaja tidak disalin; angkanya
diringkas di `synth_sisa_summary.txt` dan di §7.5 laporan.

### F7. Pembanding mock PS tidak identik dengan RTL — SUDAH DIUKUR dan gerbangnya diperbaiki

Keadaan semula: `ps_driver_afib.py` membandingkan fitur dalam satuan tampilan register
(`round(f_ratio x 200) > 33`, `round(f_entropy x 100) > 63`), sedangkan RTL membandingkan kata fitur
dalam skalanya sendiri setelah **batas top menjembatani** kedua register itu. Register 16 bit memang
berisi kode 1/200 dan 1/100 (`rtl/classifier.sv:83-84`), tetapi modulnya membandingkan kata Q1.16 dan
Q1.14 terhadap nilai terjembatani (`:128-129`, `:132-135`). Selisihnya tepat setengah LSB register.

Saya ukur akibatnya, tidak hanya menyebutnya. Aturan sisi RTL yang saya pakai
(`q16 > 10813`, `q14 > 10322`) mereproduksi sensus emas manifes fase 9
(`arms.mentah.census.fired = 183`) tepat, jadi pengukuran ini berdiri di atas aturan yang benar.

| | mock (semula) | RTL | beda |
|---|---|---|---|
| menyala atas 588 jendela | 176 | 183 | **7 jendela** |
| lengan rasio | 284 | 286 | 2 |
| lengan entropi | 178 | 185 | 7 |

Ketujuh jendela beralasan sama: `entropy_over_4` bernilai 0,63044 sampai 0,63266, yang di Q1.14
melewati ambang 10322 (RTL menyala) tetapi membulat ke kode 63 dalam satuan 1/100 sehingga `63 > 63`
gagal (mock tidak menyala). Empat di antaranya `0,63109937` (`q14 = 10340`).

Perbaikan diterapkan di `ps_driver_afib.py:_emit_window`: gerbangnya kini memakai skala RTL — `q16`
dan `q14` dibandingkan dengan `round(kode x 2**frac / satuan)`, yaitu 10813 dan 10322, seluruhnya
dengan aritmetika bilangan bulat tanpa float. Uji ulang lewat kelas `MockBackend` yang asli: mock
menyala **183**, sama dengan RTL, **0 putusan berbeda**. Ujinya ikut disimpan supaya bisa diulang:
`ps/uji_mock_vs_rtl.py` (`LULUS`, `rc=0`; sebelum perbaikan berkas ini melaporkan `BEDA (7 jendela)`).

Dua sisa yang **belum** saya ubah karena belum terukur, dan sebaiknya belum diklaim setara:

1. **Semantik bit b4 `ARM_SELECT`.** Mock memperlakukan b4 sebagai pemilih gabungan OR
   (`arm & 0x10` menghasilkan `ok_ratio or ok_ent`), sedangkan `classifier.sv:121-123`
   memperlakukannya sebagai pemaksa kedua lengan (`b0|b4`, `b1|b4` sehingga keduanya wajib).
   Golden memakai `arm = 0x0F` dan `0x07`, jadi bit itu tidak pernah tersentuh jalur emas —
   perbedaannya laten, bukan aktif.
2. **Nilai register tampilan.** Mock menulis `FEAT_RATIO`/`FEAT_ENTROPY` dalam satuan 1/200 dan
   1/100 serta menghitung `CONFIDENCE = abs(RATIO_THRESH - kode) x CONF_SCALE` (`CONF_SCALE = 4`),
   sedangkan `classifier.sv:101-107` menghitung keyakinan pada skala Q1.16 bersama lalu menggeser
   kanan `CONF_SHIFT = 4`. Keduanya belum dibandingkan dengan vektor emas, jadi belum bisa
   dinyatakan sama maupun berbeda.

### F8. Skrip penyiap vektor Fase 5 tidak memverifikasi sendiri — SUDAH DITUTUP

`siapkan_vektor_fase5.py` hanya melakukan `assert` struktural lalu mempack `04015.peaks.csv`, tanpa
menghitung ulang ekspresi model seperti skrip fase lain. Lubang bukti itu kini ditutup **di dalam
repo**: `rtl/tb/vektor/fase5/verifikasi_fase5.py` membandingkan kolom emas terhadap larik model dan
keluar dengan kode bukan nol bila ada beda. Hasil jalannya:

```
verifikasi fase 5: asal kolom emas terhadap model
  OK   jumlah baris: 4777 == larik puncak model
  OK   sample_index identik dengan larik puncak (4777 baris, beda 0)
  OK   bendera bit 1 == kolom in_band (4777 baris, beda 0)
  OK   bendera bit 2 == kolom t_rejected (4777 baris, beda 0)
  OK   04015.puncak.pos.hex identik dengan sample_index (4777 kata, beda 0)
  OK   cacah is_qrs == panjang larik qrs model (2596)
LULUS: 6 pemeriksaan cocok   (rc=0)
```

## 3. Urutan tindak lanjut yang saya sarankan

1. ~~F1 dulu: cari sebab perbedaan `o_reject`~~ **sudah dijelaskan, bukan lubang**: selisihnya
   berasal dari instans `t_rule` mandiri yang mengambil acuan `kem_qrs` dari baris rekaman, dan
   jalur itu hanya masuk mux debug. Modul `peak_detect` yang benar-benar memutuskan rantai nol beda
   dari 4.777 baris. Rinciannya di `PROGRES.md:81-103` dan §7.3 laporan.
2. F2 dan F3: kerjakan bersama saat jembatan ingest dibangun untuk venue. Ini pekerjaan **berikutnya
   yang paling menentukan**, karena tanpa jembatan itu papan belum bisa disuapi sampel.
3. F7: samakan pembanding mock PS dengan satuan register RTL supaya batas nyala tidak berbeda
   setengah LSB.
4. Sisa angka sintesis: `t_rule` perlu diselidiki pemetaannya, dan `features`/`peak_detect`/`top`
   perlu strategi ABC lain bila angkanya memang diperlukan.
