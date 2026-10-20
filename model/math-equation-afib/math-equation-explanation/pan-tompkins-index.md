# Peta Persamaan Pan-Tompkins ke Dokumen dan Notebook

Dokumen ini adalah peta induk. Fungsinya menjawab satu pertanyaan, yaitu rumus mana berada di dokumen mana, dijalankan di notebook mana, dan angka apa yang sudah dikunci untuknya. Seluruh dokumen dan notebook berada di folder yang sama, yaitu `math-equation-afib`.

## 1. Urutan rantai

```
sinyal 16 bit pada 250 Hz
  -> low-pass (persamaan 3)
  -> high-pass (persamaan 6)
  -> turunan lima titik (persamaan 9)
  -> pengkuadratan (persamaan 10)
  -> integrasi jendela 150 milidetik (persamaan 11)
  -> ambang adaptif (persamaan 12 sampai 23)
  -> interval RR (persamaan 24 sampai 29)
  -> diskriminasi gelombang T (halaman 234)
  -> keputusan jendela dan triase tiga kelas
```

## 2. Peta tahap ke berkas

| Tahap | Dokumen | Notebook | Angka kunci yang terkunci |
|---|---|---|---|
| Low-pass | [[00 - low-pass-filter-equation|low-pass-filter-equation]] | `00 - low-pass-filter-equation.ipynb` | penguatan DC 36, nol di kelipatan $f_s$ dibagi 6, 10,78 Hz pada 200 Hz dan 13,47 Hz pada 250 Hz |
| High-pass | [[01 - high-pass-filter-equation|high-pass-filter-equation]] | `01 - high-pass-filter-equation.ipynb` | penguatan DC bergantian 16 dan 0, kutub tunggal di $z = -1$, keluaran 32 pada sampel ke-32 |
| Turunan lima titik | [[02 - five-point-derivative-equation|five-point-derivative-equation]] | `02 - five-point-derivative-equation.ipynb` | penguatan DC nol eksak, puncak 41,6667 Hz sama dengan $f_s$ dibagi 6, magnitude 0,6495, tunda grup 2 sampel |
| Pengkuadratan dan integrasi jendela | [[03 - squaring-and-moving-window-integrator-equation|squaring-and-moving-window-integrator-equation]] | `03 - squaring-and-moving-window-integrator-equation.ipynb` | penambahan 14,16 dB, jendela 150 milidetik sama dengan 37,5 sampel sehingga dipakai bergantian 37 dan 38, nol pertama 6,6667 Hz, penampan 1.216 flip-flop |
| Ambang adaptif | [[04 - adaptive-threshold-equations|adaptive-threshold-equations]] | `04 - adaptive-threshold-equations.ipynb` | lima kunci P3, bentuk selisih wajib bit-identik, geser kanan dengan bias 3,49 hitungan, pemotongan separuh melipatgandakan calon palsu 10,29 kali, pemanasan 23 denyut |
| Interval RR | [[05 - rr-interval-averaging-equations|rr-interval-averaging-equations]] | `05 - rr-interval-averaging-equations.ipynb` | lima kunci P4, bacaan antrean selalu delapan interval, batas eksak 23 per 25, bentuk 30 per 32 dilarang, aturan penyemaian ulang P4-5 |
| Diskriminasi gelombang T | [[06 - t-wave-discrimination|t-wave-discrimination]] | `06 - t-wave-discrimination.ipynb` | lima kunci P5, kemiringan dari keluaran turunan, bentuk silang eksak, jendela 37 sampel, batas 0,90 milivolt |
| Risiko gabungan | [[07 - combined-risk-measurements|combined-risk-measurements]] | tidak ada, pengukuran berbasis skrip | pemotongan separuh menaikkan calon jalur kedua 12,36 kali, kisi 8 milidetik memikul 1,05 dari 16,59 poin, pembulatan nol dampak |
| Desain end to end | [[end-to-end-validation-design]] | `07 - end-to-end-chain.ipynb` | rantai fase 6 dijalankan utuh, tiga tingkat validasi lulus sesuai porsinya, titik operasi terkunci P1 0,165 dan 0,63, hasilnya di [[hasil-rantai-end-to-end]] |

## 3. Keputusan terkunci menurut lapisan

| Lapisan | Butir yang dikunci |
|---|---|
| Ambang adaptif | P3-1 sampai P3-5, termasuk bentuk selisih wajib, geser kanan, pemotongan separuh, inisialisasi maksimum dua detik, dan kriteria irama tidak teratur |
| Interval RR | P4-1 sampai P4-5, termasuk bacaan antrean, batas bawah eksak, satuan sampel, penampan lebar 14 bit, dan penyemaian ulang |
| Gelombang T | P5-1 sampai P5-5, termasuk aturan dipakai, kemiringan dari keluaran turunan, bentuk silang, jendela 37 sampel, dan batas 0,90 milivolt |
| Anggaran jalur | R4 tanpa pembagian 38, R5 jendela bergantian 37 dan 38, R6 penampan melingkar, R7 fase 3 sampai 5 berjalan paralel |
| Produk | 250 Hz dan 16 bit, target kematangan pasca final adalah sintesis ke PDK SKY130 dan bukan GDS |
| Triase | titik operasi terkunci P1 pada ambang rasio 0,165 dan ambang entropi 0,63, dipilih hanya dari rekaman 04015, dengan cadangan P2 0,165 dan 0,67 serta acuan lama P5 0,210 dan 0,70 |
| Kernel | orientasi kernel turunan lima titik yang dipertahankan adalah $[2, 1, 0, -1, -2]$, dengan puncak 34,4839 Hz pada 250 Hz dan penguatan puncak 0,6839538 |

Ringkasan seluruh butir di atas berada di [[34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown]].

## 4. Anggaran latensi jalur

| Tahap | Tundaan grup | Setara waktu pada 250 Hz |
|---|---|---|
| Low-pass | 5 sampel | 20,0 milidetik |
| High-pass | 14,86 sampel | 59,4 milidetik |
| Turunan lima titik | 2 sampel | 8,0 milidetik |
| Integrasi jendela | 18,25 sampel | 73,0 milidetik |
| Jumlah | 40,11 sampel | 160,4 milidetik |

Keputusan jendela memerlukan 32 denyut, sehingga pada 80 denyut per menit keputusan pertama muncul setelah 24,0 detik dan diperbarui setiap 4 denyut atau 3,0 detik.

## 5. Batas yang harus disebut apa adanya

1. Anotasi AFDB adalah anotasi irama, bukan anotasi denyut, sehingga seluruh angka kepekaan adalah klasifikasi jendela.
2. Ambang gerbang AND yang lama tidak boleh dipindahkan ke deret detektor sendiri.
3. Batas keberlakuan aturan gelombang T adalah 0,90 milivolt, di atas itu aturan gagal karena gelombang T sudah setinggi QRS.
4. Jeda panjang pada deret interval RR, terukur 51.064 milidetik pada rentang 285,60 sampai 336,66 detik, ternyata bukan cacat rantai ambang melainkan lead mati pada rekaman 04015. Diagnosis serta perbaikan tahap 7b beserta angka sebelum dan sesudahnya ada di [[hasil-rantai-end-to-end]]. Deret RR terkoreksi belum dikonsumsi lapisan jendela, jadi seluruh angka akurasi masih memakai deret mentah.
5. Pemisahan latih dan uji pada tingkat rekaman belum ada.
