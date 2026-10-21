# Keputusan integrasi menuju Fase 10 (ditetapkan agen induk)

Sumber: laporan akhir pekerja Fase 5 (`sa-0-41f6e8a9`, deleg_4482560c) + verifikasi mandiri induk.
Status: **mengikat untuk pekerja Fase 10.** Jangan diubah tanpa keputusan ulang induk.

## K1 — Empat porta aditif `peak_detect.sv`: DITERIMA, `--chain` merah untuk sekarang

`peak_detect.sv` menambah empat porta di ujung daftar: `s_hp` (26 bit), `s_besaran` (24 bit),
`d_dbg` (448 bit), `d_dbg_valid`. Sebab terukur: `s_tdata` 33 bit habis terpakai kata jendela,
sedangkan `pk_f` dan `kem` diambil model dari ring hp dan ring turunan (`rantai.py:933-935`, `:1002`).
Tanpa keduanya, `filtered_peak`, `slope`, kolom `in_band`/`t_rejected` dan empat unsur `ambang_state`
tidak mungkin dihitung.

Konsekuensi: `./run_lint.sh --chain` **keluar 1** dengan 4 `PINMISSING` di `afib_lite_top.sv:398`.

**Keputusan:** terima `--chain` merah sebagai keadaan sementara yang terdokumentasi — **bukan** karena
diabaikan, tapi karena menyambung empat pin itu bukan pekerjaan satu baris: `s_hp` dan `s_besaran` harus
berasal dari ring hp dan ring turunan yang menurut rencana hidup di modul jalur data, jadi menyambungnya
ke tie-off akan mematikan lint tapi menghasilkan integrasi yang salah secara fungsi (persis jenis
"hijau palsu" yang harus dihindari).

**Tugas Fase 10:** sambungkan keempat pin dengan sumber nyata dari modul jalur data, lalu `--chain`
harus hijau. Sampai itu terjadi, gerbang integrasi Fase 10 tidak boleh dinyatakan lulus dengan
`--chain` merah.

## K2 — Konvensi `m_ev_idx`: pakai indeks yang direkam model

Dua bench menuntut hal berbeda:
- `tb_puncak.sv` (Fase 5): `m_ev_idx` = posisi yang direkam model (`qrs_sample_index`) — untuk enam
  baris penelusuran balik ini posisi yang **lebih awal** (`sp`), bukan `pos` puncak.
- bench sesi lain: `m_ev_idx` = `sample_index` untuk keempat 4.777 baris.

**Keputusan: konvensi Fase 5 yang berlaku.** Dasarnya bukan preferensi, tapi sumber kebenaran: model
beku mencatat event lewat `_catat(sp, j)` untuk penelusuran balik (berbeda dari `_catat(pos, i)` untuk
jalur biasa), dan vektor emas `04015.puncak.evidx` diturunkan dari dump model itu sendiri — jadi ia
memang memuat konvensi campuran tersebut secara sengaja, dan bench Fase 5 lulus 0 beda terhadapnya.
Bench yang menuntut `sample_index` untuk seluruh baris bertentangan dengan model dan harus diperbaiki,
bukan sebaliknya.

## K3 — Bidang entri penampan kandidat: 114 bit (rencana 112)

Rencana `final38.md:1854` menganggarkan 128 x 112 = 14.336 bit. 112 bit (32+32+24+24) tidak cukup
karena `pk_f` terukur mencapai 18.865.152 > 2^24, sehingga bidang 24 bit akan memotongnya.
Susunan yang dipakai: posisi 32 + amplop 32 + besar hp 26 (`W_HP` beku) + besar turunan 24 = 114 bit.

**Keputusan:** diterima. Selisih +256 bit (+1,8 %) dibayar untuk menghindari pemotongan data yang
terbukti ada, bukan untuk kenyamanan.

## K4 — Kode event tak terpakai di paket

Kode `EV_REJECTED_T` / `EV_NOISE` yang ditambahkan sesi lain ke `afib_lite_pkg.sv` tidak dipakai
`peak_detect.sv`: sideband-nya hanya membawa `EV_QRS` dan `EV_PEAK_CAND`, sesuai vektor emas Fase 5.
**Keputusan:** jangan dihapus dulu (paket = berkas bersama); Fase 10 memutuskan apakah kode itu dipakai
`classifier.sv`/`features.sv` atau dihapus bersama-sama pada saat yang sama.

## K5 — Angka flip-flop belum gerbang

`hitung_ff.py` melaporkan **20.997 bit konstruksi** untuk `peak_detect.sv` terhadap anggaran
**25.640 bit untuk seluruh rantai** (`final38.md:1679-1686`). Membandingkan satu modul dengan anggaran
seluruh rantai tidak bermakna, tapi arahnya menggembirakan (di bawah anggaran). Rincian per kelompok
memang berbeda dari alokasi rencana: penampan kandidat +256, sub-tahap RR +66, lapisan fitur -1141,
keluaran keputusan -787, introspeksi aditif 449 tidak dianggarkan.

**Keputusan:** angka flip-flop **bukan gerbang lulus** sampai ada sintesis. Sintesis rute repo
(`run_synth.sh`) belum dijalankan karena `yosys 0.70` mesin ini macet di pass ABC, dan angka antar rute
tidak boleh dibandingkan. Fase 10 wajib menjalankan `run_synth.sh` (rute repo 0.33) dan melaporkan
angka nyata per modul.

## Tugas yang diwariskan ke Fase 10

1. Sambungkan 4 porta aditif dengan sumber nyata → `--chain` hijau (K1).
2. Satukan logika kembar `t_rule.sv` dan `peak_detect.sv` (keputusan lama: `t_rule.sv` kanonik).
3. Kontrol negatif panjang penuh 450.000 khusus gerbang `ambang_state` (Fase 5 hanya punya versi
   jalan pendek yang sah untuk larik per-puncak).
4. Uji luapan sintetis (`final38.md:1944`) — belum dikerjakan Fase 5.
5. Verifikasi paket aliran per fase terhadap vektor emas (`m_tdata`/`m_tuser`/`m_tlast`/`m_sample_idx`
   baru diperiksa terhadap perilaku terbaca, bukan vektor emas).
6. Jalankan `run_synth.sh` dan laporkan angka FF nyata (K5).

---

# Tambahan setelah gelombang Fase 6, 7, 11 selesai

## K6 — 9 porta baru di `t_rule.sv`: DITERIMA

Fase 7 mengubah `t_rule.sv` menjadi blok kanonik mandiri dan menambah 9 porta (urutan append dikunci
di laporannya): `i_peak_valid`, `i_delta`, `i_delta_valid`, `i_kem_qrs`, `i_kem_qrs_valid`,
`o_peak_valid`, `o_peak_idx`, `o_dalam_pita`, `o_overrun`. Sebabnya sah: blok kanonik tidak boleh
merekonstruksi kolom perantara sendiri, ia harus **menerima** `delta`/`kem_qrs`. Latensi sekarang
terdokumentasi dan terukur: 19 + 10 + 1 = 30 kata diterima; jarak puncak minimum 10.

Konsekuensi: `--chain` menjadi 13 `PINMISSING` (4 dari Fase 5 di baris 398, 9 dari Fase 7 di baris 410)
— **turun** dari 34 sebelum kerja Fase 7, yang 30 di antaranya berasal dari placeholder `t_rule.sv`.

**Keputusan:** diterima; penyambungan di `afib_lite_top.sv` = tugas Fase 10. Sesudah tersambung,
salinan logika di `peak_detect.sv` (baris 124-125, 216, 446) dihapus dan `peak_detect.sv` memakai
`t_rule.sv` langsung, tanpa mengubah `t_rule.sv` lagi.

## K7 — Satuan ambang: paket beku yang berlaku

Peta D8 dan paket beku memakai 33 (satuan 1/200) dan 63 (1/100); dokumen 36 menyebut 10.813 (Q16) dan
10.322 (Q14) untuk **titik operasi yang sama**. Fase 11 memakai nilai paket sebagai reset dan
menyuntikkan kode model lewat bus untuk paritas fixture, dengan kesetaraan diperiksa dalam bilangan
bulat: |33·65536 − 10813·200| = 88 ≤ 200 dan |63·16384 − 10322·100| = 8 ≤ 100.

**Keputusan:** register mengikuti paket beku (33/63), karena paket sudah beku dan `regs_axi.sv` tidak
boleh mendahuluinya. Dokumen 36 tidak diubah. Untuk laporan akhir/pitch: sebut **satu** titik operasi
saja (0,165 dan 0,63) supaya di depan juri tidak ada dua angka untuk satu hal.

## K8 — 14 slot RO yang tidak bisa digerakkan dari luar: DIBIARKAN (disengaja)

Porta beku `regs_axi.sv` hanya membawa `i_status` dan `i_irq`, sehingga 12 slot RO membaca nilai
resetnya, `DEBUG_VAL` (0x94) membaca nol (mux introspeksi ada di balik `i_dbg_sel` milik top level),
dan `FIFO_OVF_COUNT` tetap nol (tidak ada konsumen FIFO di porta beku). FIFO masukan kedalaman 64
belum diimplementasikan.

**Keputusan: jangan lebarkan daftar porta sekarang.** Menambah konsumen FIFO + mux introspeksi adalah
perubahan struktural yang lebih besar daripada nilainya untuk PoC, sedangkan slot-slot itu tetap ada
dan tetap bisa ditulis-dibaca. **Fase 10 wajib menuliskan ini di laporan akhir sebagai keterbatasan
yang disengaja** — bukan sebagai "lulus".

## Tambahan tugas Fase 10

7. Satukan `t_rule.sv` dengan `peak_detect.sv` (K6) dan hapus salinannya.
8. **Uji sambungan hulu-hilir yang belum ada**: Fase 6 sengaja digerakkan dari kolom emas dan tidak
   menginstansiasi `peak_detect.sv`, jadi kesetaraan bit-akurat hanya berlaku bila posisi QRS masukan
   benar. Fase 10 harus menguji rantai nyata `peak_detect → rr_series` dan menutup celah ini.
9. Bila Fase 10 memilih memberi porta introspeksi, ganti rujukan hierarkis yang dipakai `tb_rr.sv`
   (`u_dut.phase_q`, `u_dut.d_step_*`, `u_dut.hist_len_q`) dan cabut blok waiver lint di
   `rr_series.sv` — itu satu-satunya waiver di berkas itu.
10. Dokumentasikan K8 (14 slot RO statis, FIFO 64 belum ada) sebagai keterbatasan yang disengaja.

---

# Revisi K7 dan keputusan tambahan (setelah Fase 8 & 9 selesai)

## K7 DIREVISI — satuan ambang: konversi di batas top, bukan 33/63 apa adanya

K7 semula ("register mengikuti paket beku 33/63") tidak lengkap, dan berhenti di situ berbahaya.
Temuan Fase 9: `classifier.sv` membandingkan medan ambang 16 bit itu **langsung** terhadap kata fitur
Q1.16 / Q1.14 — paritasnya hanya tercapai dengan menyuntikkan kode 10813 / 10322 lewat plusarg. Bila
`afib_lite_top.sv` meneruskan 33 / 63 apa adanya, pembanding melihat 0,0005 dan 0,0038, sehingga kedua
lengan hampir **selalu** menyala dan kelas keluar "perlu tinjau" untuk nyaris setiap jendela. Penggerak
PS (Fase 11) menulis 33 / 63 dalam satuan pengguna, jadi jembatannya harus ada di dalam RTL.

**Keputusan:** konversi dilakukan di batas `afib_lite_top.sv`: `medan × 65536/200` (33 → 10813) dan
`medan × 16384/100` (63 → 10322). Angka eksak dari pengukuran Fase 11: |33·65536 − 10813·200| = 88 ≤ 200
dan |63·16384 − 10322·100| = 8 ≤ 100. `afib_lite_pkg.sv` (beku), `regs_axi.sv`, dan `classifier.sv`
(tidak diubah — keduanya sudah lulus gerbang).

**Bukti yang wajib menyertainya:** jalan penuh Fase 10 harus membandingkan **keluaran keputusan triase**
terhadap fixture emas (588 baris mentah / 602 berpenanda) dan sensus manifes (`triage_gate`: TP 95 /
FP 94 / FN 0 / TN 413, fired 189 berpenanda; 95 / 88 / 0 / 405, fired 183 mentah). Checksum saja tidak
cukup: checksum konsisten dengan dirinya sendiri meski skalanya salah.

## K9 — Penyaring kelas belum ada: 36 emisi berlebih di lengan berpenanda

Tidak ada porta label irama, jadi penyaring kelas tidak diimplementasikan. Lengan berpenanda
mengeluarkan 638 emisi terhadap 602 baris emas; 36 emisi tanpa baris emas ditandai `FFFFFFFF` dan tidak
dibandingkan. Lengan mentah 624 emisi / 588 baris.

**Keputusan:** konvensi ini diikuti apa adanya di Fase 10 — **jangan** memotong data supaya angkanya
menjadi 602/588 — dan dicatat sebagai keterbatasan di laporan akhir.

## K10 — `m_conf` tidak punya kolom emas

Rencana hanya menetapkan artinya (jarak ke ambang yang mengikat, skala 0–1000). Rumusnya pilihan Fase 9
(jarak minimum pada skala Q1.16 bersama, digeser 4, dijepit 1000) dan hanya diuji sebagai **properti**
(rentang, 0 tepat di ambang, monoton, menjenuh) pada 5 kata stimulus.

**Keputusan:** jangan klaim paritas angka untuk `m_conf`; sebut sebagai pilihan implementasi yang diuji
sifatnya.

## Keterbatasan Fase 8 yang harus diwarisi ke laporan akhir

- Jalur `ovf` (snapshot jatuh saat unit sibuk) **tidak pernah dipicu**; hanya diverifikasi `ovf_cnt_q = 0`
  sepanjang jalan penuh.
- Lengan mentah memakai **fixture** sebagai oracle (sumber berbeda dari kolom emas): satu baris rmssd
  menyimpang tepat 1 LSB, jadi bukan bit-exact. Klaim "akar di bawah 0,5 LSB" hanya berlaku di lengan
  berpenanda (0 LSB).
- Testbench menyalurkan satu interval tiap 44 siklus (pilihan biaya simulasi). **Throughput kecepatan
  nyata tidak diklaim**; yang dibuktikan hanya bahwa mesin tidak tertinggal pada laju cadangan itu.
- Belum diuji: `i_clear_counters` di tengah aliran, `i_enable` rendah, reset di tengah jendela.
- Cacat kosmetik eksportir: manifest Fase 8 memuat hash dirinya sendiri dari versi sebelumnya.

## Keterbatasan Fase 9 yang diwarisi

- **Lengan paritas sendirian tidak membuktikan ambang dibaca dari register**: mutan berkonstanta
  10813/10322 tetap lulus. Yang memisahkan hanya run sensitivitas register, run penjaga bit 15, dan
  jalur plusarg — ketiganya sudah dijalankan dengan angka nyata. Jangan mengutip paritas sebagai bukti
  "ambang dari register".
- Bit 15 medan entropi adalah penjaga yang diwarisi dari placeholder Fase 1 (di luar jangkauan fitur
  15 bit), dipertahankan dan diuji, bukan keputusan baru.
- Langkah `m_rr_mark` tidak dikerjakan di `classifier.sv` (portanya tidak ada di daftar beku); milik
  tahap deret RR / `regs_axi`.
