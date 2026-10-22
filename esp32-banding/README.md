# esp32-banding — rantai AFIB-LITE di ESP32 sebagai pembanding chip

Rantai AFIB-LITE yang sama persis dengan model Python beku (`model/rantai-afib-lite/rantai.py`)
dijalankan sebagai firmware ESP32. Rekaman dataset diputar ulang dari flash, lalu diukur tiga hal:

1. **kebenaran**: triase ESP32 harus identik dengan model Python (acuan),
2. **waktu proses**: siklus CPU per sampel, per tahap, dan per keputusan jendela,
3. **daya/energi**: INA219 di rail 3V3 DUT, dibaca ESP32 kedua (logger).

Masukannya adalah kata stimulus yang sama dengan `+STIM` testbench RTL
(`rtl/tb/vektor/04015.stimulus.hex`), jadi model, RTL, dan ESP32 makan data yang identik.

## Isi folder

| Berkas | Fungsi |
|---|---|
| `dut_fw/` | Proyek PlatformIO ESP-IDF 5.3 untuk ESP32 yang diuji (DUT) |
| `dut_fw/src/afib_chain.c/.h` | Port C rantai beku; satu berkas untuk ESP32 dan uji PC |
| `dut_fw/src/afib_run.c/.h` | Mode VERIF / PROF / POWER, protokol baris keluaran |
| `dut_fw/src/main.c` | Perintah serial, pin penanda, mode real-time 250 Hz |
| `dut_fw/data/stimulus.bin` | Rekaman yang ditanam di flash (dibuat `siapkan_stimulus.py`) |
| `dut_fw/host_test/host_run.c` | Menjalankan `afib_chain.c` yang sama di PC (gcc) |
| `logger_fw/` | Proyek PlatformIO untuk ESP32 logger INA219 1 kHz |
| `logger_fw/src/seg.c` | Pemotong segmen daya per kode penanda (diuji `host_test/uji_seg.c`) |
| `tools/siapkan_stimulus.py` | `.hex` → `stimulus.bin` + `stimulus_info.h` (sha256) |
| `tools/acuan_model.py` | Jawaban acuan model Python → `acuan/<rec>.<arm>.json` |
| `tools/banding_esp32.py` | `periksa` / `jalankan` / `analisis` → `hasil/<waktu>/SUMMARY.md` |
| `chip.contoh.json` | Isian angka sisi chip untuk tabel perbandingan |

## Status verifikasi (22 Okt 2026, rekaman 04015, 450.000 sampel)

- Uji PC (gcc) terhadap model Python: 6 kolom per sampel identik, 2596 QRS, penanda irama sama,
  638 posisi jendela, 638 fitur identik bit, 638 kelas sama → PASS. Lengan `mentah` juga PASS.
- Firmware dikompilasi dengan ESP-IDF v5.3.1 + xtensa-esp-elf 13.2.0 tanpa peringatan, dan
  dijalankan di emulator QEMU-ESP32 Espressif: sha256 stimulus di flash cocok, VERIF identik bit
  dengan model (PASS), PROF/POWER/RT 240 MHz tetap berjalan.
- Di emulator, penggantian frekuensi CPU (FREQ 80/160, DFS) dan light sleep crash di register
  RTC/PLL yang tidak diemulasi. Di board asli fitur itu standar ESP-IDF, tapi belum terbukti di
  board kita: bila crash, pakai `--freqs 240 --rt-fmin 240 --rt-no-sleep`.
- Kontrol negatif: ambang T1 digeser 0.165 → 0.17, pemeriksa melaporkan 1 jendela beda (REVIEW).
- Angka siklus dari emulator **bukan** angka hardware; angka resmi harus dari board.

## Perintah singkat (dari akar repo)

```
python esp32-banding/tools/siapkan_stimulus.py --record 04015
python esp32-banding/tools/acuan_model.py --record 04015
python esp32-banding/tools/banding_esp32.py jalankan --dut COM5 --logger COM6
python esp32-banding/tools/banding_esp32.py analisis esp32-banding/hasil/<waktu> --chip esp32-banding/chip.json
```

Langkah uji lengkap (rangkaian, flash, urutan, cara membaca hasil) ada di catatan sesi uji.

Data: MIT-BIH Atrial Fibrillation Database (PhysioNet, ODC-By 1.0). Goldberger dkk., Circulation 101(23):e215-e220, 2000.
