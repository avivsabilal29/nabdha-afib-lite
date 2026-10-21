# Dataset pengujian AFIB-LITE

Rekaman EKG yang dipakai menguji rantai fase 6. Semuanya berasal dari PhysioNet dan
diunduh lewat cermin resmi `https://physionet-open.s3.amazonaws.com/<basisdata>/1.0.0/<berkas>`
pada 19 Oktober 2026. Rekaman mentah tidak di-commit ke git, lihat `.gitignore`.

## Rekaman yang dipakai

| Berkas | Basis data | Laju | Kanal | Peran dalam pengujian |
|---|---|---|---|---|
| `afdb/04015` | MIT-BIH Atrial Fibrillation | 250 Hz | ECG1 | rekaman tempat seluruh ambang dan keputusan diturunkan, dan sumber fixture beku `model/rantai-afib-lite/fixture/04015_30m.npz` |
| `afdb/04043` | MIT-BIH Atrial Fibrillation | 250 Hz | ECG1 | rekaman uji hold-out, nyaris terpisah sempurna sehingga angkanya harus dicurigai |
| `afdb/04126` | MIT-BIH Atrial Fibrillation | 250 Hz | ECG1 | rekaman uji hold-out, rekaman tersulit, spesifisitas paling rendah |
| `nsrdb/16265` | MIT-BIH Normal Sinus Rhythm | 128 Hz | ECG1 | kontrol non fibrilasi, sekaligus uji jalur laju yang bukan 250 Hz |
| `mitdb/100` | MIT-BIH Arrhythmia | 360 Hz | MLII | uji kesesuaian denyut dan ketahanan laju, bukan klasifikasi jendela |

## Sidik jari berkas rekaman

```
daf57082aae76af63e401950a5713ac70a30e6dec32bb9d3dce51ef58bd98e4d afdb/04015.dat
0799eb0da3303a59ee200345d0d1efc812cf5a664e8159c5972590ec6208e460 afdb/04043.dat
02978abdaab2121d486807668ca5a4ed033ee40f301f64f217ca935f34b49468 afdb/04126.dat
b2ea3c250e56e48f4b7b90697832b8ecd1afa1e0bb31f2dcfea4ed6e1075a639 mitdb/100.dat
7e4571cada2f59d583ba173b2bd7e7ade1184f6dffcbd378014319f94a21111b nsrdb/16265.dat
```

## Kandidat pemilihan rekaman

Dua puluh lima berkas `afdb/*.hea` dan `afdb/*.atr` dari seluruh kandidat AFDB adalah
bukti metode pemilihan rekaman uji. Aturannya ditetapkan lebih dulu, yaitu paling banyak
AFIB di dalam jendela 30 menit tetap dengan share N sekurangnya 25 persen, lalu diterapkan
ke seluruh kandidat. Yang terpilih adalah `04126`. Skrip pemilihnya ada di
`afdb/scan_rhythm.py` dan `afdb/scan_first30.py`.

Berkas `.dat` untuk kandidat yang tidak terpilih sengaja tidak diunduh, hanya header dan
anotasinya, karena hanya itu yang dibutuhkan pemilihan.

## Batasan panjang berkas, jangan terjebak

Header ketiga rekaman AFDB menyatakan panjang sekitar sepuluh jam, tetapi berkas `.dat`
di direktori ini hanya memuat jendela tigapuluh menit pertama, yaitu 450.000 sampel pada
250 Hz. Pembaca wajib memotong di 450.000 sampel, misalnya dengan `wfdb.rdrecord(..., sampto=450000)`.
Tanpa pemotongan itu wfdb melempar `ValueError` broadcast karena header dan isi berkas
tidak sinkron. Jendela pemilihan rekaman, termasuk jeda lead mati pada 04015, seluruhnya
berada di dalam tigapuluh menit itu sehingga tidak ada yang hilang untuk pengujian ini.

## Jalur lama masih hidup

`/home/avivsabilalm/nabdha-data` sekarang adalah symlink ke direktori ini, supaya skrip uji
yang sudah dibekukan di `model/rantai-afib-lite/` tetap bisa dijalankan tanpa diubah.

## Lisensi dan sitasi

Basis data PhysioNet punya lisensinya masing masing. MIT-BIH Atrial Fibrillation Database
memakai ODC Attribution License 1.0. Kalau rekaman ini atau angka turunannya dipublikasikan,
sertakan sitasi basis datanya, misalnya satu baris di slide sumber data.

Goldberger A, Amaral L, Glass L, Hausdorff J, Ivanov PCh, Mark R, Mietus J, Moody GB,
Peng CK, Stanley HE. PhysioBank, PhysioToolkit, and PhysioNet: Components of a New Research
Resource for Complex Physiologic Signals. Circulation 101(23):e215-e220, 2000.