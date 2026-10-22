# AD8232 ECG → ESP32 (VS Code + PlatformIO + ESP-IDF/FreeRTOS)

Firmware perekam ECG untuk NABDHA AFIB-LITE. Keluarannya mengikuti catatan vault 44:
sampel 250 Hz, **200 cacah per mV**, dijepit ±2047, penanda `clamp`/`gap`, dikirim sebagai
rekaman biner 8 bita. Di PC, skrip `tools/ecg_ingest.py` mengubahnya menjadi `.csv`,
`.stim.hex` (untuk `+STIM` testbench Aviv), `.npz`, dan `manifest.json`.

> Buka berkas ini di VS Code dengan **Ctrl+Shift+V** supaya tampil rapi (pratinjau Markdown).

---

## Daftar isi

0. [Isi folder](#0-isi-folder)
1. [Siapkan perangkat lunak (sekali saja)](#1-siapkan-perangkat-lunak-sekali-saja)
2. [Buka proyek di VS Code](#2-buka-proyek-di-vs-code)
3. [Kenali tombol PlatformIO](#3-kenali-tombol-platformio)
4. [Rangkai perangkat keras](#4-rangkai-perangkat-keras)
5. [Uji pertama: mode teks + grafik Teleplot](#5-uji-pertama-mode-teks--grafik-teleplot)
6. [Ukur penguatan kit lalu set `KIT_GAIN`](#6-ukur-penguatan-kit-lalu-set-kit_gain)
7. [Rekam data sungguhan: mode biner + `ecg_ingest.py`](#7-rekam-data-sungguhan-mode-biner--ecg_ingestpy)
8. [Serahkan ke Aviv (simulasi RTL)](#8-serahkan-ke-aviv-simulasi-rtl)
9. [Tanpa sensor: data sintetis](#9-tanpa-sensor-data-sintetis)
10. [Cara kerja firmware (RTOS)](#10-cara-kerja-firmware-rtos)
11. [Format data](#11-format-data)
12. [Masalah umum dan solusinya](#12-masalah-umum-dan-solusinya)

---

## 0. Isi folder

```
ad8232_ecg_fw/
├── platformio.ini            konfigurasi PlatformIO (board, ESP-IDF, 2 environment)
├── CMakeLists.txt            berkas proyek ESP-IDF (jangan diubah)
├── sdkconfig.defaults        setelan ESP-IDF (tick FreeRTOS 1 kHz, flash 4 MB)
├── src/
│   ├── app_config.h          ← SEMUA angka yang boleh diubah ada di sini
│   ├── main.c                task FreeRTOS: sampling, kirim, LED
│   ├── ecg_frame.c / .h      skala cacah, penanda, rekaman 8 bita (bisa diuji di PC)
│   └── CMakeLists.txt
├── tools/
│   ├── ecg_ingest.py         serial/.bin → csv, stim.hex, npz, manifest
│   ├── make_synthetic_stream.py   aliran tiruan tanpa perangkat keras
│   └── requirements.txt
├── host_test/test_stream.c   uji logika firmware di PC (opsional, perlu gcc)
└── data/                     hasil rekaman ditaruh di sini
```

---

## 1. Siapkan perangkat lunak (sekali saja)

> ⚠️ **Langkah 1.4 mengunduh sekitar 1–1,5 GB** (ESP-IDF + toolchain) dan butuh 10–30 menit.
> Kerjakan selagi internetnya bagus, **sebelum** dibutuhkan di venue.

### 1.1 Pasang Python 3

1. Buka <https://www.python.org/downloads/windows/>, unduh **Python 3.11** atau 3.12 (Windows installer 64-bit).
2. Jalankan installer. **Centang "Add python.exe to PATH"** di layar pertama, lalu klik *Install Now*.
3. Cek: buka *Command Prompt*, ketik `python --version`. Harus muncul `Python 3.11.x` atau 3.12.

Python dipakai oleh PlatformIO dan oleh skrip `tools/ecg_ingest.py`.

### 1.2 Pasang driver USB ESP32

1. Colok ESP32 ke laptop dengan kabel USB **data** (kabel khusus cas tidak bisa).
2. Buka **Device Manager** → **Ports (COM & LPT)**.
   - Kalau muncul `Silicon Labs CP210x ... (COM5)` atau `USB-SERIAL CH340 (COM5)`, driver sudah ada. **Catat nomor COM-nya.**
   - Kalau muncul *Unknown device* dengan tanda kuning, pasang drivernya:
     - chip **CP2102** (kotak kecil persegi dekat port USB): driver "CP210x Universal Windows Driver" dari situs Silicon Labs;
     - chip **CH340**: driver CH341SER dari situs WCH.
3. Cabut-colok lagi, lalu pastikan port COM muncul.

### 1.3 Pasang ekstensi PlatformIO IDE di VS Code

1. Buka **VS Code**.
2. Tekan **Ctrl+Shift+X** (panel Extensions).
3. Ketik `PlatformIO IDE` di kotak cari. Pilih yang dari **PlatformIO**, lalu klik **Install**.
4. Tunggu sampai muncul pesan *"PlatformIO IDE has been successfully installed"* (pojok kanan bawah). Klik **Reload Now** bila diminta.
5. Ikon **kepala alien** muncul di bilah kiri. Itu menu PlatformIO.

Ekstensi tambahan yang berguna (opsional, Ctrl+Shift+X lalu cari):
- **C/C++** (Microsoft): bantuan kode dan lompat ke definisi. Biasanya ikut terpasang bersama PlatformIO.
- **Teleplot** (alexnesnes): grafik sinyal langsung dari serial. Dipakai di langkah 5.

### 1.4 Unduh ESP-IDF lewat PlatformIO (otomatis)

Langkah ini berjalan otomatis saat kamu membuka proyek dan menekan Build pertama kali (langkah 2–3).
PlatformIO akan mengunduh:
- `platform espressif32@6.9.0`
- `framework-espidf` (ESP-IDF **v5.3.1**, sudah termasuk FreeRTOS)
- toolchain `xtensa-esp-elf 13.2.0`, `esptool`, `cmake`, `ninja`

Kamu tidak perlu memasang ESP-IDF secara manual.

---

## 2. Buka proyek di VS Code

1. VS Code → **File → Open Folder…**
2. Pilih folder `D:\Data raihan\Bismillah Hackathon\chiphack26\ad8232_ecg_fw`, lalu klik **Select Folder**.
   Kalau muncul pertanyaan *"Do you trust the authors…"*, klik **Yes, I trust**.
3. PlatformIO mendeteksi `platformio.ini` dan mulai menyiapkan proyek (lihat pojok kanan bawah).
   Pertama kali, tunggu sampai unduhan selesai.

> ⚠️ **WAJIB: path proyek tidak boleh mengandung spasi.** PlatformIO + ESP-IDF menolak build
> dengan pesan `Error: Detected a whitespace character in project paths.`
> Folder `D:\Data raihan\Bismillah Hackathon\...` mengandung spasi, jadi **salin** folder
> `ad8232_ecg_fw` ke `D:\pio\ad8232_ecg_fw`, hapus folder `.pio` di salinan itu, lalu buka
> `D:\pio\ad8232_ecg_fw` di VS Code. Kerjakan semua build dan rekaman dari salinan ini.

---

## 3. Kenali tombol PlatformIO

Di **bilah status bawah** VS Code ada ikon-ikon kecil:

| Ikon | Nama | Fungsi |
|---|---|---|
| ✓ | Build | kompilasi firmware |
| → | Upload | kompilasi lalu tulis ke ESP32 |
| 🗑 | Clean | hapus hasil build |
| 🔌 | Serial Monitor | lihat keluaran serial |
| `>_` | New Terminal | terminal dengan perintah `pio` siap pakai |
| `env:esp32dev` | Switch env | pilih environment |

**Dua environment** di proyek ini (atur lewat tombol `env:...` di bilah bawah):

| Environment | Keluaran | Dipakai untuk |
|---|---|---|
| `esp32dev` | **biner**, rekaman 8 bita | rekaman sungguhan untuk model dan RTL |
| `esp32dev_text` | **teks**, `>ecg:123` | melihat sinyal di Serial Monitor atau Teleplot |

Cara lain lewat menu alien: **PlatformIO → PROJECT TASKS → esp32dev (atau esp32dev_text) → General → Build / Upload / Monitor**.

Cara lewat terminal (klik ikon `>_` PlatformIO dulu):

```bash
pio run -e esp32dev_text                 # build mode teks
pio run -e esp32dev_text -t upload       # upload mode teks
pio device monitor -b 115200             # buka monitor (Ctrl+C untuk keluar)
pio run -e esp32dev -t upload            # upload mode biner
```

### 3.1 Build pertama (cek instalasi)

1. Pilih environment **`env:esp32dev_text`** di bilah bawah.
2. Klik **✓ Build**.
3. Pertama kali akan lama karena mengunduh lalu mengompilasi ESP-IDF (±950 berkas). Build berikutnya hanya beberapa detik.
4. Berhasil kalau terminal menampilkan `========== [SUCCESS] Took xx seconds ==========`.

---

## 4. Rangkai perangkat keras

### 4.1 Kabel AD8232 → ESP32 DevKit

| Pin modul AD8232 | Pin ESP32 | Keterangan |
|---|---|---|
| `3.3V` | `3V3` | **jangan** ke 5V/VIN |
| `GND` | `GND` | |
| `OUTPUT` | `GPIO36` (label **VP**) | ADC1 kanal 0 |
| `LO-` | `GPIO33` | elektroda lepas |
| `LO+` | `GPIO32` | elektroda lepas |
| `SDN` | tidak disambung | (internal sudah aktif) |

Pin ini sama dengan firmware lama `ADB232_HeartRate.ino`, jadi kabel yang sudah ada tidak perlu diubah.

### 4.2 Elektroda (3 titik)

| Kabel | Warna umum | Posisi |
|---|---|---|
| RA | merah | bawah tulang selangka kanan |
| LA | kuning | bawah tulang selangka kiri |
| RL | hijau | perut kanan bawah (acuan) |

### 4.3 Keselamatan

- Saat elektroda menempel di orang, **cabut charger laptop** (laptop pakai baterai) atau pakai power bank. Jangan ada alat bertegangan jala-jala yang terhubung ke rangkaian subjek.
- Pengukuran dengan pembangkit sinyal dan osiloskop dilakukan di **kit kedua**, bukan di kit yang menempel di orang (catatan 44 bagian 10).

---

## 5. Uji pertama: mode teks + grafik Teleplot

1. Pilih **`env:esp32dev_text`**, lalu klik **→ Upload**.
   - Kalau terminal macet di `Connecting........___`, **tahan tombol BOOT** di ESP32 sampai muncul `Writing at 0x...`, lalu lepas.
2. Klik **🔌 Serial Monitor**. Kamu akan melihat:
   ```
   I (312) ecg: AD8232 ECG fw 1.0, gain kit 100, mode teks
   I (2350) ecg: dasar terukur 1648 mV dari 2000 bacaan
   >ecg:12
   >gap:0
   >clamp:0
   ...
   dasar=1648mV telat=0 buang=0
   ```
3. **Arti LED biru di ESP32:**
   - kedip cepat: menunggu elektroda terpasang atau sedang mengukur dasar (2 detik pertama, **diamlah**);
   - kedip 1 kali per detik: merekam normal;
   - nyala terus: elektroda lepas (bit `gap` = 1).
4. **Lihat grafiknya:** tutup Serial Monitor dulu (ikon tong sampah di panel terminal), lalu
   klik ikon **Teleplot** di bilah bawah (atau **Ctrl+Shift+P** → ketik `Teleplot` → pilih perintah
   untuk membuka Teleplot). Di jendela Teleplot,
   pilih port **COM5**, baud **115200**, klik **Open**. Grafik `ecg`, `gap`, dan `clamp` akan muncul.
   Puncak R normal dengan penguatan 100 sekitar **+200 cacah** (1 mV × 200).

> Port COM hanya bisa dibuka oleh **satu program** pada satu waktu. Tutup Serial Monitor atau
> Teleplot sebelum upload atau menjalankan `ecg_ingest.py`.

---

## 6. Ukur penguatan kit lalu set `KIT_GAIN`

Ini langkah paling menentukan (catatan 44 bagian 5 dan uji #1). Banyak modul AD8232 yang beredar
penguatannya **bukan 100**.

1. Pakai kit B (tanpa orang). Masukkan sinus **1 mV p-p, 1 Hz** dari pembangkit sinyal ke input
   elektroda. Kalau pembangkit tidak bisa sekecil itu, pakai pembagi resistor, misalnya 1 V p-p
   lewat 10 kΩ : 10 Ω.
2. Baca amplitudo pin `OUTPUT` di osiloskop:

   | OUT terbaca | Penguatan | Set di `src/app_config.h` |
   |---|---|---|
   | ~100 mV p-p | 100 | `#define KIT_GAIN 100` (direkomendasikan) |
   | ~400 mV p-p | 400 | `#define KIT_GAIN 400` |
   | ~1,1 V p-p | ~1100 | `#define KIT_GAIN 1100` (rentang hanya ±1,4 mV, R mudah terpotong) |

3. Buka `src/app_config.h` di VS Code, ubah `KIT_GAIN`, simpan (**Ctrl+S**), lalu upload ulang.
4. Cek: dengan sinus 1 mV p-p, puncak `ecg` di Teleplot harus sekitar **±100 cacah**
   (catatan 44 uji #4). Dengan 5 mV p-p, sekitar ±500 dan `clamp` tetap 0 (uji #5).

Pilihan opsional di `app_config.h`:
- `BASELINE_MV_FIXED`: isi angka mV hasil ukur multimeter di OUT tanpa sinyal (uji #2, sekitar 1650) kalau tidak mau pengukuran otomatis saat boot.
- `PIN_LED`: ganti kalau LED board kamu bukan di GPIO2.

---

## 7. Rekam data sungguhan: mode biner + `ecg_ingest.py`

### 7.1 Upload firmware biner

1. Pilih **`env:esp32dev`**, lalu klik **→ Upload**.
2. Jangan buka Serial Monitor. Isinya hanya karakter acak karena datanya biner, dan itu memang normal.

### 7.2 Pasang paket Python (sekali saja)

Di terminal VS Code (**Ctrl+`**), dari folder proyek:

```bash
pip install -r tools/requirements.txt
```

### 7.3 Rekam

```bash
python tools/ecg_ingest.py --port COM5 --seconds 60 --sesi subjekA_duduk
```

- `--port`: nomor COM dari Device Manager.
- `--seconds`: lama rekaman. Rekam minimal 60 detik; untuk analisis AF lebih baik 5 menit (`--seconds 300`).
- `--sesi`: nama bebas tanpa spasi, misalnya `sinus1mv`, `sinus5mv`, `lepas_elektroda`, `subjekA`.
- `--skip-seconds 3`: opsional, membuang 3 detik pertama.

Selama merekam, layar menampilkan status tiap detik:

```
  t=  12.0s sampel=  3000 cacah_terakhir=    35 gap_1s=  0 cksum_err=1 hilang=0
```

`cksum_err` bernilai 1–2 di awal itu wajar (sisa teks boot ESP32). Yang harus **0** adalah `hilang`.

### 7.4 Hasil di folder `data/`

```
data/ad8232_subjekA_duduk_250hz.bin            bita mentah (simpan! bisa diurai ulang)
data/ad8232_subjekA_duduk_250hz.csv            dibuka di Excel/pandas
data/ad8232_subjekA_duduk_250hz.stim.hex       untuk testbench RTL
data/ad8232_subjekA_duduk_250hz.npz            untuk model Python
data/ad8232_subjekA_duduk_250hz.manifest.json  penguatan, dasar, statistik, ringkasan
```

Mengurai ulang berkas `.bin` (misalnya setelah memperbaiki skrip):

```bash
python tools/ecg_ingest.py --from-bin data/ad8232_subjekA_duduk_250hz.bin --sesi subjekA_duduk
```

---

## 8. Serahkan ke Aviv (simulasi RTL)

Kirim **`.stim.hex` + `.manifest.json`** (dan `.npz` untuk Bryan). Tata letak hexnya sama dengan
`rtl/tb/vektor/04015.stimulus.hex`, jadi testbench bisa langsung membacanya:

```systemverilog
s_tdata <= {g_stim[tick][11:0], 4'b0000};   // cacah 12 bit, nibble bawah nol
s_tuser <= {5'd0, g_stim[tick][14:12]};     // {weak, gap, clamp}
```

Contoh menjalankan (sesuaikan dengan skrip Aviv):

```bash
vvp sim.vvp +STIM=data/ad8232_subjekA_duduk_250hz.stim.hex
```

> **Konfirmasi dengan Aviv:** cacah di bit 11:0 ditulis sebagai **komplemen dua** 12 bit
> (−1 → `fff`). Pastikan `acq_frontend.sv` membacanya sebagai bertanda.

---

## 9. Tanpa sensor: data sintetis

Untuk menguji alur sampai testbench **sebelum** sensor siap:

```bash
python tools/make_synthetic_stream.py --seconds 60 --out data/sintetis.bin
python tools/ecg_ingest.py --from-bin data/sintetis.bin --sesi sintetis
```

Isinya 30 detik ritme teratur (75 BPM, RR = 200 sampel), lalu 30 detik RR acak mirip AF,
dengan 0,5 detik elektroda lepas. Hasil `data/ad8232_sintetis_250hz.stim.hex` bisa langsung dicoba Aviv.

**Uji logika firmware di PC (opsional, perlu gcc atau MSYS2):**

```bash
cd host_test
gcc -O2 -I../src -o test_stream test_stream.c ../src/ecg_frame.c -lm
./test_stream .
python ../tools/ecg_ingest.py --from-bin stream.bin --sesi hosttest --out .
```

Uji ini menjalankan `ecg_frame.c` (kode yang sama persis dengan di ESP32) pada sinyal sintetis,
sengaja menyisipkan sampah boot, satu rekaman hilang, dan satu bita rusak, lalu memastikan
pengurai menghasilkan cacah dan penanda yang identik.

---

## 10. Cara kerja firmware (RTOS)

```
 gptimer 2 kHz ──ISR──► vTaskNotifyGiveFromISR
                              │
            ┌─────────────────▼──────────────────┐
            │ task_sample  (core 1, prioritas 23) │
            │  baca ADC1_CH0 (mV terkalibrasi)    │
            │  baca LO+ / LO-                     │
            │  jumlahkan 8 bacaan = 1 sampel      │
            │  cacah = floor(25·(Σ − 8·dasar)/G)  │
            │  jepit ±2047, isi clamp / gap       │
            └─────────────────┬──────────────────┘
                     xQueueSend (64 slot ≈ 256 ms)
            ┌─────────────────▼──────────────────┐
            │ task_tx  (core 0, prioritas 10)     │
            │  tiap 250 sampel: 8 rekaman header  │
            │  rekaman sampel 8 bita → UART0      │
            └────────────────────────────────────┘
            task_led (core 0, prioritas 2): indikator
```

Alasan desainnya:

- **Timer perangkat keras, bukan `millis()`.** Ketukan 2 kHz datang tepat dari gptimer, jadi 2000 / 8 = 250 Hz pas, tanpa jitter dari `loop()` (jebakan di catatan 44 bagian 7).
- **ISR hanya membangunkan task.** `adc_oneshot_read()` tidak boleh dipanggil di dalam ISR, jadi pembacaan ADC dilakukan di task berprioritas tinggi yang dipasang di core 1, terpisah dari core 0 yang mengurus UART.
- **`ulTaskNotifyTake(pdFALSE)`**: ketukan yang tertunda tidak hilang. Kalau task sempat tertinggal lebih dari 1 ms, sampel itu diberi `gap` supaya jujur soal waktunya.
- **Queue** memisahkan pencuplikan dari pengiriman. Kalau UART tersendat, sampel yang terbuang ditandai `gap` pada sampel berikutnya.
- **`gap` dari LO+/LO- (fw 1.1):** sampel diberi `gap` bila LO tinggi di sedikitnya
  `LO_GAP_MIN_SUBSAMPLES` dari 8 bacaan (bawaan 8, artinya lead-off terus-menerus 4 ms). Di fw 1.0
  satu bacaan saja sudah cukup, sehingga puncak dengung 50 Hz yang sesaat menyentuh ambang
  lead-off AD8232 membuat `gap` berkedip tiap 20 ms (cek kualitas 22 Okt 2026). Elektroda yang
  benar-benar lepas tetap terdeteksi karena LO-nya tinggi terus.
- **Skala:** kalibrasi ADC bawaan ESP-IDF (`adc_cali_raw_to_voltage`, memakai data pabrik di eFuse) membuat 1 langkah = 1 mV di OUT. Untuk gain 100: Σ8 >> 2 = 2 × rata-rata = 200 cacah per mV, persis catatan 44 bagian 9.
- **Dasar sinyal** (REFOUT, sekitar 1,65 V) diukur 2 detik saat boot setelah elektroda terpasang dan dicatat di header.
- **Mode biner mematikan semua log** (`esp_log_level_set("*", ESP_LOG_NONE)`) supaya teks tidak menyusup ke aliran. Teks boot ROM sebelum `app_main` tetap muncul, dan pengurai melewatinya lewat sinkronisasi `A5 5A` + checksum.

---

## 11. Format data

**Rekaman sampel (8 bita, little-endian)**

| Ofset | Isi |
|---|---|
| 0–1 | `A5 5A` |
| 2 | penanda: bit0 clamp, bit1 gap, bit2 weak (selalu 0), bit3 = 0 |
| 3 | nomor urut 0–255 (berputar) |
| 4–5 | cacah int16, 200/mV, ±2047 |
| 6 | `00` |
| 7 | jumlah bita 0–6 mod 256 |

**Rekaman header** (8 rekaman sekali per detik, sebelum sampel ke-0, 250, 500, …): penanda bit3 = 1,
bita 3 = ID kolom, bita 4–5 = nilai.

| ID | Kolom | Contoh |
|---|---|---|
| 0 | versi firmware | `0x0100` = 1.0 |
| 1 | penguatan kit | 100 |
| 2 | rentang penuh ADC (mV) | 3100 |
| 3 | laju cuplik | 250 |
| 4 | dasar (mV) | 1648 |
| 5 | cacah per mV | 200 |
| 6 | sumber ADC | 1 = internal ESP32 |
| 7 | status | bit0 kalibrasi eFuse ok, bit1 dasar otomatis ok |

> Catatan 44 menyebut header "sebagai pengganti rekaman sampel". Di sini header **disisipkan**
> (tidak mengganti sampel), supaya aliran 250 Hz tidak bolong satu sampel tiap detik.
> Header juga tidak memakan nomor urut sampel. Bebannya (250 + 8) × 8 = 2064 B/s, sekitar 18% dari 115200 baud.

**Baris `.stim.hex`:** `[14] weak  [13] gap  [12] clamp  [11:0] cacah (komplemen dua)`.
Contoh: cacah +250 tanpa penanda menjadi `00fa`; cacah −120 dengan gap menjadi `2f88`.

**Kolom `.csv`:** `indeks,cacah,clamp,gap,weak,tegangan_mv` (`tegangan_mv` = cacah / 200, mV acuan input).

---

## 12. Masalah umum dan solusinya

| Gejala | Penyebab | Solusi |
|---|---|---|
| Ikon alien tidak muncul | ekstensi belum selesai terpasang | tunggu, lalu **Ctrl+Shift+P → Developer: Reload Window** |
| Build pertama gagal di tengah unduhan | internet putus | klik Build lagi; kalau tetap gagal, hapus folder `C:\Users\<nama>\.platformio\packages\framework-espidf` lalu Build ulang |
| `Error: Detected a whitespace character in project paths.` | path proyek mengandung spasi | salin proyek ke `D:\pio\ad8232_ecg_fw`, hapus `.pio` di salinan, buka dari situ |
| Nama user Windows mengandung spasi dan toolchain gagal | `.platformio` di `C:\Users\Nama Spasi\` | buat folder `C:\pio_core`, set variabel lingkungan `PLATFORMIO_CORE_DIR=C:\pio_core`, restart VS Code |
| `Failed to connect to ESP32: Wrong boot mode` | ESP32 tidak masuk mode unduh | tahan **BOOT** saat `Connecting...` |
| `could not open port 'COM5': PermissionError` | port dipakai program lain | tutup Serial Monitor, Teleplot, atau Arduino IDE |
| Port COM tidak muncul | kabel cas saja atau driver belum ada | ganti kabel; pasang driver CP210x/CH340 |
| LED kedip cepat terus 10 detik | elektroda lepas saat boot | tempel elektroda lalu tekan **EN/RST**; dasar dipakai nominal 1650 mV |
| `ecg` di Teleplot selalu ±2047 dan `clamp` = 1 | penguatan kit jauh di atas `KIT_GAIN` atau elektroda lepas | ukur penguatan (bagian 6) |
| Sinyal penuh derau 50 Hz | kabel elektroda panjang atau dekat charger | cabut charger, pilin kabel, pastikan RL terpasang |
| `tidak ada sampel sah` di `ecg_ingest.py` | firmware masih mode teks atau baud salah | upload `env:esp32dev`, pakai `--baud 115200` |
| `hilang` > 0 di `ecg_ingest.py` | kabel USB atau hub bermasalah | colok langsung ke laptop, ganti kabel |

---

*Disusun untuk ChipHack26, tim NABDHA AFIB-LITE. Rujukan: catatan vault 44, datasheet AD8232 Rev. D,
dokumentasi ESP-IDF v5.3 (gptimer, adc_oneshot, adc_cali, FreeRTOS task notification).*
