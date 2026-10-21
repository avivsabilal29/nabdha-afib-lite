/*
 * ecg_frame.h — skala cacah, penanda, dan rekaman 8 bita.
 *
 * Modul ini sengaja tidak memakai API ESP-IDF sama sekali, supaya bisa
 * dikompilasi dan diuji di PC (host_test/) dengan gcc biasa.
 *
 * Rekaman sampel (catatan 44 bagian 4.3), 8 bita:
 *   [0] 0xA5  [1] 0x5A  [2] penanda  [3] urutan 0..255
 *   [4..5] cacah int16 little-endian  [6] 0x00  [7] jumlah bita 0..6 mod 256
 *
 * Rekaman header: format sama, penanda bit3 = 1,
 *   [3] = ID kolom (ECG_HDR_*), [4..5] = nilai uint16 LE.
 *   Header TIDAK memakan nomor urut sampel dan tidak menggantikan sampel.
 */
#pragma once
#include <stdint.h>
#include <stdbool.h>

#define ECG_SYNC0        0xA5
#define ECG_SYNC1        0x5A
#define ECG_FRAME_LEN    8

/* Bit penanda — sama dengan s_tuser di RTL (TU_CLAMP, TU_GAP, TU_WEAK) */
#define ECG_FLAG_CLAMP   0x01
#define ECG_FLAG_GAP     0x02
#define ECG_FLAG_WEAK    0x04   /* tidak diisi firmware: butuh jendela 1 s di PS */
#define ECG_FLAG_HEADER  0x08   /* di aliran serial: rekaman ini header */

/* ID kolom header */
enum {
    ECG_HDR_FW_VERSION    = 0,  /* major<<8 | minor */
    ECG_HDR_KIT_GAIN      = 1,  /* V/V */
    ECG_HDR_ADC_FS_MV     = 2,  /* rentang penuh ADC, mV */
    ECG_HDR_SAMPLE_HZ     = 3,  /* 250 */
    ECG_HDR_BASELINE_MV   = 4,  /* dasar sinyal yang dikurangkan, mV */
    ECG_HDR_COUNTS_PER_MV = 5,  /* 200 */
    ECG_HDR_ADC_SOURCE    = 6,  /* 1 = internal ESP32, 2 = ADS1015 */
    ECG_HDR_STATUS        = 7,  /* bit0 kalibrasi ADC eFuse ok, bit1 dasar otomatis ok */
    ECG_HDR_COUNT         = 8
};

/* Pembagian lantai (floor), sama dengan geser kanan aritmetika untuk pangkat dua */
int32_t ecg_floor_div(int32_t num, int32_t den);

/*
 * Ubah jumlah n bacaan ADC (mV di pin OUT) menjadi cacah 200/mV acuan input.
 *   cacah = 200 * (rata2 - dasar) / gain = 25 * (jumlah8 - 8*dasar) / gain
 * Untuk gain 100 dan n = 8 ini persis (jumlah - 8*dasar) >> 2 (catatan 44 bag. 9).
 * Bila n != 8 (jarang: ada tick terlewat) jumlah dinormalkan ke 8 bacaan.
 * Hasil dijepit ±CLAMP_COUNT; bila terjepit, *flags |= ECG_FLAG_CLAMP.
 */
int16_t ecg_counts_from_sum(int32_t sum_mv, int32_t n, int32_t baseline_mv,
                            int32_t kit_gain, int32_t counts_per_mv,
                            int32_t clamp_count, uint8_t *flags);

uint8_t ecg_checksum(const uint8_t *frame);   /* jumlah bita 0..6 mod 256 */

void ecg_frame_sample(uint8_t out[ECG_FRAME_LEN], uint8_t flags, uint8_t seq, int16_t counts);
void ecg_frame_header(uint8_t out[ECG_FRAME_LEN], uint8_t field_id, uint16_t value);

/* Kata stimulus 15 bit untuk +STIM: [14] weak [13] gap [12] clamp [11:0] cacah */
uint16_t ecg_stim_word(int16_t counts, uint8_t flags);
