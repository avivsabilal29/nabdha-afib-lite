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
| `raihan_istirahat_bersih` | 29.662 | 118,6 s | 0 % | 1,1 % | **uji utama jalur sensor -> RTL**, kelas yang diharapkan: normal |
| `raihan_istirahat` | 73.662 | 294,6 s | 4,0 % | 2,0 % | uji penanganan `gap` (rekaman lengkap) |
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

## Hal yang perlu dikonfirmasi Aviv

1. Cacah 12 bit ditulis sebagai **komplemen dua** (-1 = `fff`). Pastikan `acq_frontend.sv` membacanya bertanda.
2. **Clamp** di rekaman ini berasal dari ADC ESP32 yang mentok di pucuk R (sekitar 85 % detak),
   bukan dari cacah > 2047. Bagaimana RTL memperlakukan sampel ber-clamp?
3. Bit `gap` diisi selama LO+/LO- aktif; firmware tidak menambah 131 sampel pemulihan
   (diasumsikan dikerjakan RTL lewat `GAP_RECOVERY`).
4. Data rekaman ini diambil dari orang sehat, jadi hanya menguji jalur dan kelas normal.
   Deteksi AF tetap diuji dengan rekaman AFDB (`04015`).

Grafik analisis: `analisis_raihan_istirahat.png`.
