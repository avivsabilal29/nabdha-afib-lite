/*
 * app_config.h — semua angka yang boleh diubah ada di sini.
 *
 * Rujukan: catatan vault 44 "Jalur Sensor AD8232 ke Model, Simulasi RTL, dan FPGA"
 * dan kontrak RTL rtl/afib_lite_pkg.sv (CLAMP_COUNT 2047, REC_GAIN_MV 200).
 */
#pragma once

/* ------------------------------------------------------------------ */
/*  Versi firmware (masuk ke rekaman header)                           */
/* ------------------------------------------------------------------ */
#define FW_VERSION_MAJOR 1
#define FW_VERSION_MINOR 0

/* ------------------------------------------------------------------ */
/*  Pin — sama dengan firmware lama ADB232_HeartRate.ino               */
/* ------------------------------------------------------------------ */
#define PIN_LO_PLUS      32   /* LO+  (elektroda LA / kuning) */
#define PIN_LO_MINUS     33   /* LO-  (elektroda RA / merah)  */
#define PIN_ECG_OUT      36   /* OUT AD8232 -> GPIO36 = ADC1_CH0 (VP) */
#define PIN_LED          2    /* LED bawaan DevKit V1 */

/* ------------------------------------------------------------------ */
/*  PENGUATAN KIT — WAJIB DIUKUR (catatan 44, uji #1)                  */
/*  Masukkan sinus 1 mV p-p, baca OUT di osiloskop:                    */
/*    100 mV p-p -> 100 ;  400 mV p-p -> 400 ;  ~1,1 V p-p -> 1100      */
/* ------------------------------------------------------------------ */
#define KIT_GAIN         1100

/* ------------------------------------------------------------------ */
/*  Pencuplikan: timer 2 kHz, jumlah 8 bacaan -> 250 Hz                */
/* ------------------------------------------------------------------ */
#define SUBSAMPLE_HZ     2000
#define SUBSAMPLES       8
#define SAMPLE_HZ        (SUBSAMPLE_HZ / SUBSAMPLES)   /* = 250 */

/* ------------------------------------------------------------------ */
/*  Skala kata sampel (kontrak RTL)                                    */
/* ------------------------------------------------------------------ */
#define COUNTS_PER_MV    200    /* REC_GAIN_MV */
#define CLAMP_COUNT      2047   /* CLAMP_COUNT */

/* ------------------------------------------------------------------ */
/*  Dasar sinyal (REFOUT AD8232, ~setengah rel)                        */
/*  0  = ukur otomatis saat boot (rata-rata 2 s, elektroda terpasang)  */
/*  >0 = pakai nilai tetap ini (mV), mis. hasil ukur multimeter uji #2 */
/* ------------------------------------------------------------------ */
#define BASELINE_MV_FIXED      0
#define BASELINE_MV_NOMINAL    1650   /* cadangan bila elektroda lepas saat boot */
#define BASELINE_MEASURE_MS    2000
#define BASELINE_WAIT_LEADS_MS 10000

/* ------------------------------------------------------------------ */
/*  ADC internal ESP32                                                  */
/* ------------------------------------------------------------------ */
#define ADC_FULL_SCALE_MV  3100   /* atenuasi 12 dB, dicatat di header */
#define ADC_RAIL_MARGIN    16     /* raw <=16 atau >=4079 dianggap mentok rel -> clamp */
#define ADC_SOURCE_ID      1      /* 1 = ADC internal ESP32, 2 = ADS1015 (belum) */

/* ------------------------------------------------------------------ */
/*  Serial                                                              */
/* ------------------------------------------------------------------ */
#define UART_BAUD          115200
#define HEADER_EVERY_N     SAMPLE_HZ   /* satu set header per detik */

/* Mode keluaran: diset dari platformio.ini (-DECG_OUTPUT_TEXT=0/1) */
#ifndef ECG_OUTPUT_TEXT
#define ECG_OUTPUT_TEXT 0
#endif
