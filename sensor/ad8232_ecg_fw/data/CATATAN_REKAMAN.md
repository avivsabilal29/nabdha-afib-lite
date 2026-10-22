# Catatan rekaman AD8232 untuk simulasi RTL

Semua berkas di folder ini dibuat oleh `tools/ecg_ingest.py` dari aliran serial firmware
`ad8232_ecg_fw` (ESP32, ESP-IDF 5.3.1). Format mengikuti catatan vault 44.

## Format `.stim.hex`

Satu baris per sampel, 4 digit heks, 250 Hz:

    [14] weak   [13] gap   [12] clamp   [11:0] cacah (komplemen dua 12 bit, 200 cacah/mV)

Sama dengan tata letak `rtl/tb/vektor/04015.stimulus.hex`:

    s_tdata <= {g_stim[tick][11:0], 4'b0000};
    s_tuser <= {5'd0, g_stim[tick][14:12]};

## Berkas

| Sesi | Sampel | Durasi | Gap | Clamp | Pakai untuk |
|---|---|---|---|---|---|
| `raihan_duduk30m_bersih` | 72.250 | 289,0 s | 0 % | 0,99 % | **uji utama jalur sensor -> RTL (mulai 22 Okt)**: 407 QRS, 83,3 BPM, 94/94 jendela normal, 0 RR janggal (median lokal) |
| `raihan_duduk30m` | 449.924 | 1799,7 s | 0 % | 1,10 % | rekaman 30 menit lengkap (fw 1.1): 2450 QRS, 85,2 BPM, 598 normal / 6 review; berisi 89 s datar TANPA gap (detik 49-138) dan 14 detak prematur |
| `raihan_istirahat_bersih` | 29.662 | 118,6 s | 0 % | 1,1 % | uji utama lama (fw 1.0), digantikan `raihan_duduk30m_bersih` |
| `raihan_istirahat` | 73.662 | 294,6 s | 4,0 % | 2,0 % | uji penanganan `gap` (rekaman lengkap) |
| `raihan_istirahat2` | 74.852 | 299,4 s | 1,6 % | 0,3 % | **jangan dipakai untuk uji utama**: 129 s sinyal datar (ECG hilang tanpa penanda gap, kontak kabel/colokan putus-sambung); blok bersih terpanjang hanya 26 s |
| `sintetis` | 15.000 | 60 s | 0,8 % | 0,8 % | sinyal buatan: 30 s teratur 75 BPM + 30 s RR acak mirip AF |

Subjek: Raihan, duduk istirahat, 21 Okt 2026. Firmware `KIT_GAIN 1100` (perkiraan, belum diukur
dengan pembangkit sinyal), dasar 1636 mV, sampel hilang 0, checksum error 0.
Detak: median RR 203 sampel (812 ms), sekitar 74 BPM.

## Isi rekaman lengkap `raihan_istirahat` per segmen

| Detik | Kondisi |
|---|---|
| 0-57 | bersih |
| 59-133 | elektroda goyah: QRS melemah, dengung 50 Hz naik, `gap` berkedip 10-20 % |
| 133-175 | sinyal hilang-timbul, sebagian TANPA penanda gap -> detak terlewat, RR tampak acak (bisa memicu "perlu tinjauan" palsu) |
| 176-294 | bersih (artefak gerak singkat sekitar detik 240-245); inilah potongan `_bersih_` |

## Rekaman `raihan_duduk30m` (22 Okt 2026)

Subjek Raihan, duduk diam 30 menit. ESP32 khusus AD8232 di COM14 (board yang dipasang sebelum cek kualitas ke-6),
firmware **fw 1.1** (header `fw_version` = 257 = 0x0101), `KIT_GAIN 1100` (masih perkiraan),
dasar terukur 1674 mV. Perintah:
`python tools/ecg_ingest.py --port COM14 --seconds 1830 --sesi raihan_duduk30m --skip-seconds 30`.

Aliran: 457.424 rekaman sampel sah, sampel hilang 0, putus urutan 0, checksum error 0,
laju 250 Hz. `.stim.hex` identik dengan `.npz` (diperiksa ulang lewat `model_core.baca_stimulus`).

Analisis `tools/analisis_rekaman.py` (rantai beku lewat `model_core.jalankan_model`, jalur yang
sama dengan `acuan_model.py`; jendela 32 interval langkah 4, lengan berpenanda, gerbang 0,165 / 0,63):

| Ukuran | `raihan_duduk30m` | `raihan_duduk30m_bersih` |
|---|---|---|
| QRS rantai / R detektor pita 5-15 Hz | 2450 / 2450 (2449 berpasangan, tunda 32 sampel) | 407 / 407 (406 berpasangan) |
| RR median, BPM | 704 ms, 85,2 BPM | 720 ms, 83,3 BPM |
| RR janggal (0,7-1,3 x median lokal 33 detak) | 13 | 0 (median global: 1, yaitu QRS pertama di sampel 57 = transien awal rantai) |
| Penanda RR 7b (0 / 1 / 3) | 16 / 2432 / 1 | 1 / 405 / 0 |
| Jendela normal / review / gagal gerbang | 598 / 6 / 0 | 94 / 0 / 0 |
| Median RMSSD/rerata, pNN50, entropi/4 | 0,052; 0,161; 0,683 | 0,051; 0,161; 0,695 |
| Detik datar tanpa gap | 87 | 0 |
| Dengung 50 Hz (median / p95, cacah) | 39,8 / 88,3 | 63,9 / 79,3 |

Segmen (detik sesudah buangan 30 s):

| Detik | Kondisi |
|---|---|
| 0-48 | bersih |
| **49-138** | **sinyal datar tanpa penanda gap** (std 0,7-5 cacah, dengung 50 Hz ikut hilang ~3 cacah): masalah perangkat keras yang sama dengan `raihan_istirahat2` dan cek kualitas ke-5, diduga jack 3,5 mm/soket/header AD8232. Pulih sendiri di detik 138. Rantai melihatnya sebagai satu RR 88.184 ms |
| 150-288, 289-447, 562-851, 1107-1389, 1390-1531 | bersih (segmen terpanjang 562-851 = potongan `_bersih_`) |
| 149, 288, 447, 561, 851, 956, 1081, 1106, 1389, 1531, 1572, 1690, 1774, 1777 | **detak prematur**: RR sekitar 470-510 ms lalu jeda kompensasi 850-1030 ms (jumlah sekitar 2 x median), kompleks lebar yang mentok rel ADC (+269, clamp) lalu defleksi negatif lebar. Pola fisiologis, bukan artefak (grafik `ektopik_raihan_duduk30m.png`). Enam jendela review (detik 959-979, rasio 0,166-0,175) dipicu detak di detik 956 |
| 1013 | clamp di luar puncak R tanpa RR janggal (artefak singkat) |

Rekomendasi berkas uji:
1. **Utama: `raihan_duduk30m_bersih`** (289 s, target 300 s kurang 11 s). Kelas yang diharapkan: semua 94 jendela normal.
2. Uji panjang: `raihan_duduk30m` (sama panjang dengan 04015). Menguji perilaku rantai pada sinyal datar tanpa gap dan detak prematur; jawaban model ada di `analisis_raihan_duduk30m.json` (kunci `jendela`, `qrs_rantai`).

Cek kualitas sebelum merekam: `tools/cek_kualitas.py`, hasil di `cek_kualitas/` (9 cek, lulus di cek ke-9).
Dari pengalaman hari ini: dengung 50 Hz paling dipengaruhi pad merah/kuning (ganti dan gosok kulit:
54,8 -> 22,3 cacah), dan gap di fw 1.0 berkedip setiap 20 ms mengikuti puncak dengung.

### Perubahan firmware fw 1.1

`gap` dari LO+/LO- sekarang hanya dipasang bila LO tinggi di 8 dari 8 subsampel (4 ms terus-menerus,
`LO_GAP_MIN_SUBSAMPLES` di `app_config.h`). Di fw 1.0 satu subsampel sudah cukup, sehingga dengung
50 Hz membuat `gap` berkedip 1 sampel tiap 20 ms (cek ke-4: 154 kedipan, 1,02 %). Gap karena tick
terlambat atau antrean penuh tidak berubah.

## Hal yang perlu dikonfirmasi Aviv

1. Cacah 12 bit ditulis sebagai **komplemen dua** (-1 = `fff`). Pastikan `acq_frontend.sv` membacanya bertanda.
2. **Clamp** di rekaman ini berasal dari ADC ESP32 yang mentok di pucuk R (sekitar 85 % detak),
   bukan dari cacah > 2047. Bagaimana RTL memperlakukan sampel ber-clamp?
3. Bit `gap` diisi selama LO+/LO- aktif; firmware tidak menambah 131 sampel pemulihan
   (diasumsikan dikerjakan RTL lewat `GAP_RECOVERY`).
4. Data rekaman ini diambil dari orang sehat, jadi hanya menguji jalur dan kelas normal.
   Deteksi AF tetap diuji dengan rekaman AFDB (`04015`).
5. Mulai fw 1.1 definisi `gap` dari lead-off lebih longgar (lihat di atas). Sinyal datar tanpa gap
   (detik 49-138 `raihan_duduk30m`) tidak bisa ditandai firmware; apakah RTL perlu detektor
   "sinyal datar" sendiri?
6. Skala: kontrak sensor 200 cacah/mV, front end menyekala ulang ke 409,4/mV
   (`model_core.GAIN_MV_PER_HITUNG`, `A.locked_word`). `KIT_GAIN` belum diukur, jadi amplitudo mV
   bisa meleset; RR tidak terpengaruh.

Grafik analisis: `analisis_raihan_duduk30m.png`, `analisis_raihan_duduk30m_bersih.png`,
`ektopik_raihan_duduk30m.png`; lama: `analisis_raihan_istirahat.png`, `perbandingan_rekaman.png`.
