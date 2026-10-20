# PROGRES Fase 11 (plan 38) — regs_axi + penggerak PS

Pemilik: `sa-2-aa48f005`. Berkas eksklusif sesuai `rtl-synthesis/reports/KEPEMILIKAN-BERKAS.md`
baris Fase 11. Catatan apa adanya, ditulis sambil jalan.

## 2026-10-20 (malam) — pembukaan

- Baca `rtlplan2/final38.md`: tabel fase baris 115-130 (baris Fase 11 = 128), blok lengkap
  `### Fase 11` baris 2160-2180, peta register final `### 8.5` baris 1148-1240, penggerak PS
  `### 8.6` baris 1242-1285, dan `rtl/TASK_BRIEF.md` bagian 4 (peta lama 25 slot) + catatan Fase 1.
- Gerbang Fase 11 yang harus lulus (verbatim, baris 128): `tb_regs_axi` setiap bacaan sama dengan
  nilai tulis; `ARM_SELECT` mematikan lengan aturan T dan hasilnya sama dengan fixture lengan itu;
  penggerak mencetak jumlah slot dan dua pemeriksaan pertama lulus terhadap mock.
- Keadaan awal: `rtl/regs_axi.sv` 202 baris, masih PLACEHOLDER (10 slot, tanpa jalur byte,
  tanpa slot 36 peta beku). Lint baseline bersih (rc=0).

## Temuan awal (angka, bukan klaim)

1. **Port beku vs peta 36 slot.** Porta `regs_axi` beku (Fase 1) hanya membawa `i_status`,
   `i_irq`, dan tujuh keluaran konfigurasi. Peta final 8.5 menuntut 36 slot RO/RW, di antaranya
   penghitung datapath (`SAMPLE_IDX`, `BEAT_COUNT`, `CLASS_OUT`, `FEAT_*`, dua cap indeks) dan
   jalur masuk sampel (`SAMPLE_FIFO`, `SAMPLE_MARK`) yang sumbernya ada di tingkat atas, bukan di
   berkas ini. Jadi seluruh 36 slot bisa **didekode** dan diuji di bus, tetapi tidak seluruh slot
   bisa **digerakkan** tanpa menambah port. Sesuai brief induk ("porta/parameter beku tidak
   berubah") peta lengkap diimplementasikan sebagai decode + penyimpanan, dan tautan datapath
   yang hilang dilaporkan sebagai pekerjaan belum selesai, bukan disembunyikan.
2. **Gap peta 8.5: tidak ada slot `WINDOW_STEP` / `WINDOW_BEATS`.** Peta 8.5 memakai `0x00` sampai
   `0x8C` penuh, sedangkan D8/plan 13.3 mewajibkan dua parameter jendela itu di register dan porta
   `o_window_step` / `o_window_beats` beku wajib tetap ada. Dua slot sementara dipertahankan di
   `0x90` dan `0x94` (di atas peta beku), sama seperti catatan di `regs_axi.sv` placeholder dan
   `TASK_BRIEF.md` catatan Fase 1. Dilaporkan sebagai temuan, bukan diputuskan sendiri.
3. **b2 vs b3 pada gerbang lengan.** Brief induk memetakan `ARM_SELECT` b2 (aturan gelombang T)
   mati ke fixture lengan mentah 588 baris. Di pohon repo, generator vektor Fase 9
   (`rtl/tb/vektor/fase9/siapkan_vektor_fase9.py`, baris 193 dan 150) memetakan lengan mentah ke
   `ARM_SELECT = 0x07` (b3 = sumber deret, bukan b2). Dua pemetaan diuji di testbench dan
   perbedaannya dilaporkan.
4. **Perbaikan protokol pada placeholder.** `wr_en` placeholder mensyaratkan `(|s_axi_wstrb)`,
   sehingga tulis dengan semua strobe rendah tidak pernah dijawab `bvalid` (master menggantung).
   Diganti: setiap tulis dijawab, tetapi hanya byte yang strobenya menyala yang mengubah register.

## Langkah berikutnya

- [x] Vektor uji `rtl/tb/vektor/fase11/**` + manifes (generator di `reports/fase11/`)
- [x] `rtl/regs_axi.sv` badan penuh
- [x] `rtl/tb/tb_regs_axi.sv`
- [x] Penggerak PS (jalur plan)
- [x] Kontrol negatif + dua jalan identik + lint
- [x] `LAPORAN-FASE11.md`

## Penutup, 2026-10-21 (terukur, bukan rencana)

Daftar di atas sudah terisi seluruhnya. Yang benar-benar diukur, semuanya dari log di
direktori ini:

- Lint: `run_lint.sh` `regs_axi` rc=0 dan `tb_regs_axi` rc=0. Rantai penuh rc=1 oleh 13
  peringatan `PINMISSING` di `afib_lite_top.sv` baris 398/410, milik instansiasi fase lain
  yang sedang berubah; tidak satu pun menunjuk berkas fase 11.
- Simulasi `tb_regs_axi`: `checks: 118`, `words compared: 4056`,
  `mismatches = 0 out of 4056`, `failures: 0`, `gate: PASS`, rc=0. Dua jalan byte identik.
- Lengan: berpenanda 602 jendela, fired 189, TP 95, FP 94, FN 0, TN 413; aturan T mati
  (0x0B) 588 jendela, fired 183, TP 95, FP 88, FN 0, TN 405; deret mentah (0x07) sama
  dengan lengan mentah. 0 beda dari fixture, 3584 perbandingan kelas.
- Satu harapan yang dirusak di salinan vektor: `mismatches = 1 out of 4056`,
  `gate: FAIL`, rc=1, `FATAL` di baris 1125.
- Penggerak PS `ps/ps_driver_afib.py`: 38 slot, sembilan langkah inisialisasi, 12 pemeriksaan,
  `checks: 12, failed: 0`, rc=0; angkanya sama dengan keluaran terukur rencana. Kontrol
  negatif penggerak rc=1.

Dua temuan yang muncul di kerja ini dan sudah masuk `LAPORAN-FASE11.md`:

1. Slot 0x90/0x94 bernama `DEBUG_SEL`/`DEBUG_VAL` menurut keputusan rencana butir 9, dan
   jumlah slot menjadi 38; penggerak mencetaknya 38 sedangkan keluaran terukur lama rencana
   masih 36. Pasangan port beku `o_window_step`/`o_window_beats` kini digerakkan konstanta
   paket, bukan slot, karena peta 8.5 tidak memuat kedua nama itu.
2. Ambang 33 (1/200) dan 63 (1/100) di peta D8 adalah titik operasi yang sama dengan 10.813
   Q16 dan 10.322 Q14 yang disebut gerbang F5c/Fase 9, setara di bawah satu LSB satuan
   masing-masing; paritas fixture memakai kode skala model yang disuntikkan lewat bus.

Belum selesai: FIFO kedalaman 64 langkah 3 (butuh keputusan port konsumen), jalur papan
`--backend uio` (tidak ada papan di mesin ini), dan sambungan `DEBUG_SEL`/`DEBUG_VAL` ke mux
introspeksi yang hidup di balik port beku top level.
