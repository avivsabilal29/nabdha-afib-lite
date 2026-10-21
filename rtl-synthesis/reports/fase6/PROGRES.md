# PROGRES Fase 6 (plan 38) -- rtl/rr_series.sv + rtl/tb/tb_rr.sv

Pekerja: subagent Fase 6. Bahasa: Indonesia. Semua klaim di bawah ada buktinya di berkas
log yang disebut.

## 1. Masukan dan data emas (tidak diubah)
- rtlplan2/fase5/04015.rr.csv (2595 baris), 04015.peaks.csv (4777 baris, 2596 QRS),
  04015.manifest.fase5.json.
- rtl/tb/vektor/fase6/siapkan_vektor_fase6.py mengubah CSV emas menjadi kolom hex; skrip ini
  memeriksa 22 invarian data emas dan laporannya ada di
  rtl-synthesis/reports/fase6/siapkan_vektor_fase6.out (checks failed: 0, PASS).
- Angka acuan yang dipakai gerbang: rr_intervals 2595, rr_corrected_entries 2983,
  census keep/split/drop/gap = 2186/397/9/3, langkah 2586, semai 26, penanda 1202,
  antrean tidak penuh sampai langkah 24, antrean di langkah 25 = 8, interval di atas plafon 3.

## 2. RTL rtl/rr_series.sv
- Porta dan parameter beku tidak diubah.
- Urutan keputusan tanda = rantai.py:526-559: palsu (2x < median rujukan) dulu, lalu missed
  beat (50x > 83 median rujukan), lalu plafon absolut RR_LONG_MS untuk GAP, sisanya SPLIT,
  sisanya KEEP. Rujukan = median bulat jendela delapan interval (rantai.py:364-372).
- Lint Verilator bersih: rtl-synthesis/reports/fase6/lint-rr_series.log (rc=0,
  'lint clean: top=rr_series'), dan lint testbench bersih:
  rtl-synthesis/reports/fase6/lint-tb_rr.log.

## 3. Testbench rtl/tb/tb_rr.sv
Tiga fase dalam satu jalan:
- Fase A: deret QRS emas (2596 beat dari peaks.csv). Setiap interval dibandingkan dengan
  rr_ms, m_rr_last, d_rr_smp, m_rr_mark dan bentuk satu-panas topengnya, ditambah sisi
  peristiwa (jenis/indeks/nilai) dan amplitudo beat. Setiap langkah yang dikomit
  dibandingkan ra1, ra2, panjang antrean, menyala, disemai, panjang riwayat, gagal, jeda,
  indeks langkah, panjang jendela delapan.
- Fase B: gerbang plan apa adanya, "panjang antrean tepat 8 sesudah langkah 24", pada deret
  konstan 40 beat berjarak tetap; harapan panjang antrean dihitung dari konstanta paket.
- Fase C: tanda GAP pada stimulus sintetis (riwayat 800 ms lebih dulu supaya syarat missed
  beat dan plafon terpenuhi), penghitung interval panjang dan pembersihannya, lalu
  passthrough EV_GAP (bit penanda sampel hilang) dan EV_WINDOW (t_last).

## 4. Riwayat percobaan (ringkas, semua kegagalan nyata)
1. Lint RTL pertama: 13 UNUSEDSIGNAL (bank introspeksi d_step_*), 2 WIDTHTRUNC (konstanta bit
   atas), 1 WIDTHTRUNC (ra1 >> 3), WIDTHEXPAND med_which_q, UNUSEDSIGNAL bit atas div_quo_q /
   div_rem_q, s_ev_val tidak dipakai. Perbaikan: med_which_q jadi 1 bit; MED_BIT_TOP dan
   DIV_BIT_TOP jadi ekspresi berukuran; ra1 dipotong eksplisit dengan penjaga ra1_over_c;
   div_quo_q/div_rem_q satu bit lebih sempit dengan penjaga div_rem_bad; s_ev_val dipakai
   sebagai d_beat_val_q (amplitudo beat terakhir, digerbang di TB); bank introspeksi diberi
   satu blok waivers UNUSEDSIGNAL yang didokumentasikan (porta beku, tanpanya TB tidak bisa
   melihat keadaan per langkah).
2. Lint TB: continue tidak didukung Icarus pada mode yang dipakai -> diganti if/else;
   got ganda (VARHIDDEN) -> diganti step_pulse; NEQCASE butuh lebar sama -> perluasan nol
   eksplisit; CMPCONST pada m_rr_mark > MARK_GAP -> diganti uji keanggotaan empat kode.
3. Sim +LIMIT=30 pertama: penghitung peristiwa di dua gelung poll menghitung pulsa yang sama
   dua kali dan melewatkan pulsa di siklus berjalan -> diganti monitor always @(posedge clk)
   dengan saklar per fase. Pola "periksa siklus berjalan lalu maju" juga memperbaiki EV_WINDOW
   dan EV_GAP yang tadinya tidak terbaca.
4. Sim +LIMIT=30 kedua: harapan tanda GAP di fase C salah karena riwayat kosong pada DUT
   (median rujukan = 0 -> KEEP, sesuai rantai.py:528-529). Diperbaiki dengan riwayat 800 ms
   lebih dulu, dan syarat missed beat + plafon diperiksa di TB dengan variabel supaya bukan
   lipatan konstanta.
5. Sim +LIMIT=30 ketiga: posisi beat panjang salah (5600 ms, bukan 4800) dan hitungan harapan
   interval panjang salah. Diperbaiki; sekarang PASS rc=0 dengan 97 baris dibandingkan.

## 5. Hasil akhir (21 Oktober 2026)
- Lint RTL bersih (rc=0, `lint clean: top=rr_series`); lint TB bersih (rc=0,
  `lint clean: top=tb_rr`). Log: reports/fase6/lint-rr_series.log, lint-tb_rr.log.
- `run_lint.sh --chain` gagal: 13 PINMISSING di ../rtl/afib_lite_top.sv (berkas pekerja lain),
  0 dari rr_series.sv / tb_rr.sv. Log: reports/fase6/lint-chain.log.
- Dua perbaikan nyata di jalur tanda, ditemukan dari jalan penuh yang gagal
  (reports/fase6/sim-penuh-20261021-000914.log, census dut 2418/165/9/3 lawan emas
  2186/397/9/3):
  (a) entri GAP tidak boleh didorong ke jendela irama (rantai.py:536-542 kembali tanpa push),
  (b) penunjuk jendela harus maju dua entri untuk sebuah split (dua paruh), bukan satu.
- Jalan penuh lulus rc=0: interval mismatches 0/2595, step mismatches 0/2586,
  census tanda dut = emas = 2186/397/9/3, antrean langkah 25 = 8, langkah tidak penuh terakhir
  = 24, penghitung akhir 2586/26/1202, o_rr_long_count 3, mismatches 0/5220, PASS.
- Determinisme: dua jalan penuh ber-timestamp byte identik, md5 6dbd391bf627df1d046ffa52253a516e
  (sim-penuh-jalan1-20261021-001238.log dan sim-penuh-jalan2-20261021-001240.log).
- Kontrol negatif 1: satu nilai harapan diubah di salinan vektor (mutasi-negatif, baris 100
  rr.hex 3b8 -> 3b9) -> rc=1, 4 ketidakcocokan terdeteksi.
- Kontrol negatif 2: direktori vektor hilang -> semua kata emas X dan X !== X bukan mismatch,
  jadi dulu terbaca lulus; TB sekarang memeriksa `$isunknown` setiap kata emas dan berhenti
  dengan rc=1 (38862 kata X).
- Laporan lengkap: rtl-synthesis/reports/LAPORAN-FASE6.md.
