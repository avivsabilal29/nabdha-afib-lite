# PROGRES FASE 10 — integrasi rantai penuh AFIB-LITE

Dokumen ini ditulis sambil jalan. Setiap klaim menyebut perintah mentahnya.
Status jujur: ada yang lulus, ada yang belum. Yang belum tidak diklaim lulus.

Berkas yang saya pegang: `rtl/afib_lite_top.sv` (TAHAP 1, TAHAP 5), `rtl/tb/tb_top.sv` (TAHAP 2,
baru), `rtl/peak_detect.sv` + `rtl/t_rule.sv` (TAHAP 5 saja), `rtl-synthesis/reports/fase10/**`,
`rtl-synthesis/reports/LAPORAN-FASE10.md`.

## TAHAP 1 — PENYAMBUNGAN 13 PIN

Selesai dan hijau pada RTL akhir. `./run_lint.sh --chain` keluar `rc=0` dengan 0 peringatan.
Tidak ada tie-off: `s_hp` dari `hp_q` (ring tapis lolos atas), `s_besaran` dari `der3_q` (ring
turunan), `d_dbg`/`d_dbg_valid` dari mux introspeksi yang benar-benar membaca register
`peak_detect`, dan sembilan pin `t_rule` dari jalur puncak (`peak_delta_q`, `peak_kemq_q`, dan
bendera `peak_dvalid_q`/`peak_kvalid_q`). `sha256 rtl/afib_lite_top.sv =
eb852a0bf3b193b61f64fb291d2e5f57f91bc4df6c9aa0dcda1d29af3f8155c5`, sama seperti yang sudah
diverifikasi agen induk (berkas ini **tidak** diubah lagi pada TAHAP 5).

## TAHAP 2 — REPLAY PENUH

Benchmark: `rtl/tb/tb_top.sv`. 450.000 bingkai dari `rtlplan2/fase0/` dilewatkan ke seluruh
rantai; enam larik tapis dibandingkan kata per kata (nilai DAN indeks), ditambah blok puncak,
deret RR, fitur, klasifier, keputusan triase, dan sidik jari port. Setiap jalur gagal memakai
`$fatal(1,...)`.

Sidik jari lintas mesin (empat checksum 64 bit):

| mesin | jalan | CK_STREAM | CK_PEAK | CK_DOWN | CK_EVENT | mismatch |
|---|---|---|---|---|---|---|
| Verilator 5.053 (2-state) | 1 | `b254f0da0524e710` | `ff1f6a10a1028888` | `3fbbce7cafe82708` | `cf143c61d384939e` | 0, `PASS` |
| Verilator 5.053 (2-state) | 2 | `b254f0da0524e710` | `ff1f6a10a1028888` | `3fbbce7cafe82708` | `cf143c61d384939e` | 0, `PASS` |
| Icarus (4-state) | 1 | sama (lihat LAPORAN-FASE10.md) | | | | |

## TAHAP 3 — KONTROL NEGATIF (diulang pada sha TB final)

Tiga kontrol dijalankan ulang karena testbench berubah; ketiganya masih `rc=1` dan bukan error
kompilasi (log di `reports/fase10/nc*.20261021-015857.log`):

- `nc1_lp_word100`: kata emas `lp` ke-100 dirusak di salinan DI LUAR repo →
  `MISM stage1 ord=100 dut=-122384 gold=-122383`, `total mismatches = 1`,
  `FATAL: ../rtl/tb/tb_top.sv:984: tb_top: gate violation`, `rc=1`.
- `nc2_missing_fase5`: direktori `+EXPECT` kosong →
  `FATAL ... FAIL the Fase 5 count vector is missing or short`, `rc=1`.
- `nc3_missing_fase0`: direktori `+VECTOR` tidak ada →
  `FATAL ... FAIL a Fase 0 column is missing or short`, `rc=1`.

## TAHAP 4 — SINTESIS

`./run_synth.sh` rute repo (Yosys 0.33, sel SKY130) untuk top sedang berjalan; angka per modul
(rc=0) ada di `~/.hermes/cache/scratch/synth_all.log`, angka top ada di
`reports/afib_lite_top.native.20261021.{log,json}`. Tanpa peringatan latch.

## TAHAP 5 — SATU SUMBER ATURAN GELOMBANG T

Selesai. Logika kembar `peak_detect.sv` (yang dulu berdiri sendiri di baris 442-449) dihapus dan
diganti instansiasi modul baru `t_rule_eq` di `rtl/t_rule.sv`; `t_rule.sv` sendiri sekarang juga
membaca modul itu, jadi persamaan aturan (dan kedua bentuk silang) hanya ada **satu** di `rtl/`.

Dampak pada rute yang sudah terdokumentasi: perintah Fase 5 (`run_sim.sh tb_puncak.sv pkg
peak_detect.sv`) sekarang harus menyertakan `../rtl/t_rule.sv`, karena `peak_detect.sv`
menginstansiasi modul dari berkas itu. Perintah Fase 7 tidak berubah (modulnya ada di berkas yang
sudah dibaca). Semua ini dilaporkan di `LAPORAN-FASE10.md`.

## CACAT YANG SUDAH DIPERBAIKI (dan bukti angkanya)

1. **Array log testbench kedalaman 1024 vs 4777 denyut.** Tiga array `fed_*` sedalam `WIN_CAP`
   (1024) dibaca sampai indeks 4777, jadi tiap pembacaan di atas 1023 memberi X di Icarus dan 0 di
   Verilator. Itulah baris `fed delta=x kemq=x qrs_at_capture=x` yang mulai di baris 1109: X di
   pembukuan bench, bukan di DUT. Kedalaman diubah ke `PK_CAP`; pada jalan 150.000 baris 1109
   sekarang berbunyi `fed delta=66 kemq=1091684 qrs_at_capture=103657 pulse=1110`, dan **0** baris
   `fed delta=x`.
2. **Penjaga masukan `t_rule`.** Ditambahkan `$isunknown` pada `i_delta`, `i_kem_qrs`,
   `i_delta_valid`, `i_kem_qrs_valid` di tiap denyut puncak, dijumlahkan ke total gerbang dan
   dicetak sendiri (`unknown t_rule inputs at peak pulses = 0 of 4777`). Ini yang membuat
   perbandingan dua mesin sah di jalur vonis: Verilator 2-state menyembunyikan X.
3. **Sensus lengan mentah.** Cabang `+ARM=1` membandingkan kelas DUT terhadap `g_asli` yang tidak
   pernah diisi (`04015.mentah.asli.hex` ada, 588 kata, tapi tidak dibaca), sehingga sensus DUT
   keluar `TP=0 FP=183` dan gerbang gagal di bench, bukan di desain. Sekarang berkas itu dibaca.

## DUA CACAH YANG BERBEDA: `rejected` vs `golden t_rejected` (penjelasan yang diminta)

`tb_top: t_rule peak pulses=1587 of 1587 peaks, rejected=547, golden t_rejected in range=473`
hidup berdampingan dengan `total mismatches = 0` karena:

- `twp_seen` = cacah denyut `o_peak_valid` instans `t_rule` mandiri di top; **digerbang**
  (`twp_seen` harus sama dengan cacah puncak emas dalam rentang).
- `twr_seen` (`rejected`) = cacah denyut itu yang `o_reject`-nya 1 — cacah vonis **DUT**.
- `exp_rej` (`golden t_rejected in range`) = cacah **kolom emas** `04015.puncak.flag.hex` yang bit 2
  (`t_rejected`) menyala pada baris yang sama, `pos + 27 < limit_n`.
- Selisihnya **persis** cacah baris yang menyimpang satu per satu, bukan artefak definisi:
  - jalan 150.000: 547 − 473 = **74**, dan baris `RULEDBG` yang tercetak = **74**, semuanya
    `dut rej=1 gold rej=0`; **0** baris `dut rej=0 gold rej=1`; **0** baris beda `dalam_pita`.
  - jalan 450.000 (Verilator): 2014 − 1909 = **105** = **105** baris `RULEDBG`, semuanya
    `dut rej=1 gold rej=0`.
- Baris-baris itu **tidak digerbang**: vonis yang digerbang baris-per-baris adalah kolom bendera
  `peak_detect` (yang benar-benar memutuskan di rantai), dan itu `flags = 0` beda dari 4777 baris.
  Yang membandingkan vonis instans mandiri hanya mencetak; jumlahnya dilaporkan lewat `NOTE`.
- Penyebab terukurnya: acuan `kem_qrs` untuk instans mandiri di top diambil dari baris rekaman
  (`EV_QRS`) sedangkan model memajukan acuan itu di jalur sinyal diterima (`rantai.py:695`) dan di
  jalur cari-mundur (`:710`); `peak_detect` mengikuti **kedua** jalur itu, instans mandiri tidak.
  Karena `pita` (in-band) cocok 100 % dan hanya `ditolak` yang meleset ke satu arah (DUT lebih
  ketat), selisih 74/105 itulah cacah baris `dut rej=1 gold rej=0`.

## BACAAN `$readmemh` YANG DISENGAJA

`$readmemh` memperingatkan rentang baca lebih besar dari berkas (mis. `04015.fase8.map.marked.hex`
dan empat berkas Fase 9 `[0:1023]`). Ini disengaja: array cadangan dibaca penuh, sisa entri tetap
X, dan penjaga `unknown golden words used = 0` (serta penjaga anchor di awal jalan) yang menutupnya
— sebuah berkas vektor yang hilang atau terpotong tidak bisa lolos sebagai 0. Baris laporan
`tb_top: unknown golden words used = 0` adalah buktinya.

## PERUBAHAN 21 OKTOBER 2026 (dini hari)

1. **Harness `run_sim.sh`: jalur `.vvp` bisa ditimpa lewat `SIM_OUT`.** Cacatnya nyata: `OUT` adalah
   jalur tetap `reports/sim/tb_top.vvp`, dan dua jalankan yang mulai pada detik yang sama (kedua
   lengan Fase 10) saling menimpa berkas itu sehingga `vvp` berhenti dengan
   `words.cc:377 Assertion 'array_label ? array!=0 : true' failed ... Aborted` (`rc=134`). Setelah
   perubahan, tiap lengan memakai jalur sendiri; jalur bawaan tidak berubah.
2. **Dua lengan Icarus 450.000 lulus.** `total mismatches = 0`, `PASS`, 450.000/450.000 kata tiap
   aliran, `unknown = 0`. Angka penuh di `LAPORAN-FASE10.md` §7.1. Banding checksum lintas-mesin ada
   di §7.2: `CK_DOWN` dan `CK_EVENT` sama antar mesin, `CK_STREAM` dan `CK_PEAK` berbeda cakupan.
3. **Sintesis berat dipagari memori.** `yosys` untuk `peak_detect` pernah membengkak 1,65 GB → 7,33 GB
   dalam satu menit dan dihentikan; sebelumnya ledakan yang sama memicu pembunuh OOM kernel dan
   menewaskan pekerja lain. Sisa sintesis kini dijalankan lewat `synth_sisa.sh` dengan `ulimit -v`
   per modul, satu modul pada satu waktu.
4. **Temuan jalur ingest papan.** Kolom emas `masukan16` adalah nilai **sesudah** penguatan front-end
   (cacah x 2047/1000), sedangkan `s_tdata` menerima cacah mentah. Menyuapkan kolom itu apa adanya ke
   `SAMPLE_FIFO` akan menggandakan penguatan. Rincian: `TEMUAN-INTERFACE-INGEST.md`.
5. **Verifikasi asal kolom emas Fase 5 ditambahkan.**
   `rtl/tb/vektor/fase5/verifikasi_fase5.py` membandingkan kolom emas terhadap larik model; enam
   pemeriksaan cocok, `rc=0`.
6. **Lint rantai dijalankan ulang** dan lognya disimpan di repo:
   `reports/fase10/lint_chain_20261021.log` (`rc=0`, tanpa keluaran peringatan).
