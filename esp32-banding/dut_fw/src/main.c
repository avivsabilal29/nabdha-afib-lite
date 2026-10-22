/*
 * ESP32 DUT -- benchmark rantai AFIB-LITE (port C model Python beku), ESP-IDF 5.3 + FreeRTOS
 * Proyek NABDHA AFIB-LITE (ChipHack26), banding model Python vs ESP32 vs chip.
 *
 * Rekaman (kata stimulus 15 bit yang sama dengan +STIM testbench RTL) ditanam di flash sebagai
 * bagian dari image aplikasi (EMBED_FILES data/stimulus.bin), lalu diputar ulang ke rantai.
 *
 * Perintah lewat USB (UART0, 115200 baud), satu baris per perintah:
 *   INFO                       kepala perangkat, dijawab READY,...
 *   VERIF                      run penuh, cetak QRS + jendela + sidik jari (cek kebenaran)
 *   PROF <rep>                 ukur siklus per sampel dan per tahap
 *   POWER <rep> <idle_s> <act_s>  urutan daya, pin penanda untuk logger INA219
 *   FREQ <80|160|240>          kunci frekuensi CPU untuk PROF/POWER
 *   RT <detik> <fmax> <fmin> <ls>  real-time 250 Hz: fase timer saja, lalu fase rantai
 *   ARM <berpenanda|mentah>    pilih seri interval jendela
 *
 * Pin penanda ke ESP32 logger (kode M1 M0): 0 transisi, 1 bench, 2 idle, 3 real-time.
 * Selama fase ukur tidak ada satu karakter pun dikirim ke UART.
 */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_cpu.h"
#include "esp_err.h"
#include "esp_idf_version.h"
#include "esp_pm.h"
#include "esp_timer.h"
#include "mbedtls/sha256.h"

#include "afib_chain.h"
#include "afib_run.h"
#include "stimulus_info.h"

#define PIN_M0        GPIO_NUM_25    /* penanda bit 0 -> logger GPIO25 */
#define PIN_M1        GPIO_NUM_26    /* penanda bit 1 -> logger GPIO26 */
#define PIN_LED       GPIO_NUM_2     /* LED biru DevKit, dimatikan agar tidak ikut terukur */
#define CON_UART      UART_NUM_0
#define CON_BAUD      115200

extern const uint8_t stim_start[] asm("_binary_stimulus_bin_start");
extern const uint8_t stim_end[]   asm("_binary_stimulus_bin_end");

static char s_sha[65] = "na";
static uint32_t s_fcpu = 240;
static int s_arm = AFIB_ARM_BERPENANDA;
static afib_plat_t s_plat;
static TaskHandle_t s_task;
static bool s_uart_driver;

/* ------------------------------------------------------------------ platform */
static uint32_t plat_cycles(void) { return (uint32_t)esp_cpu_get_cycle_count(); }
static uint64_t plat_us(void) { return (uint64_t)esp_timer_get_time(); }
static void plat_sleep(uint32_t ms) { vTaskDelay(pdMS_TO_TICKS(ms)); }
static void plat_flush(void) { fflush(stdout); uart_wait_tx_idle_polling(CON_UART); }
static void plat_marker(int code)
{
    gpio_set_level(PIN_M0, code & 1);
    gpio_set_level(PIN_M1, (code >> 1) & 1);
}

static void uart_on(void)
{
    if (s_uart_driver) return;
    ESP_ERROR_CHECK(uart_driver_install(CON_UART, 1024, 0, 0, NULL, 0));
    s_uart_driver = true;
}

static void uart_off(void)
{
    if (!s_uart_driver) return;
    plat_flush();
    uart_driver_delete(CON_UART);
    s_uart_driver = false;
}

/* frekuensi CPU terukur: selisih cycle count selama 100 ms esp_timer */
static uint32_t ukur_mhz(void)
{
    uint64_t t0 = esp_timer_get_time();
    uint32_t c0 = plat_cycles();
    while (esp_timer_get_time() - t0 < 100000) { }
    uint32_t c1 = plat_cycles();
    uint64_t t1 = esp_timer_get_time();
    return (uint32_t)(((double)(c1 - c0) / (double)(t1 - t0)) + 0.5);
}

static esp_err_t set_pm(int fmax, int fmin, bool ls)
{
    esp_pm_config_t pm = {.max_freq_mhz = fmax, .min_freq_mhz = fmin, .light_sleep_enable = ls};
    return esp_pm_configure(&pm);
}

static void info(void)
{
    printf("READY,fw=afib-esp32-bench,ver=1,idf=%s,rec=%s,n=%" PRIu32 ",stim_sha=%s,sha_ok=%d,"
           "fcpu_mhz=%" PRIu32 ",arm=%s,pin_m0=%d,pin_m1=%d,chain_bytes=%u\n",
           esp_get_idf_version(), STIM_REC, s_plat.n, s_sha, strcmp(s_sha, STIM_SHA256) == 0,
           s_fcpu, s_arm == AFIB_ARM_MENTAH ? "mentah" : "berpenanda", PIN_M0, PIN_M1,
           (unsigned)sizeof(afib_chain_t));
}

/* ------------------------------------------------------------------ real-time 250 Hz */
static void on_tick(void *arg) { (void)arg; xTaskNotifyGive(s_task); }

static void run_rt(int detik, int fmax, int fmin, int ls)
{
    printf("#AFIB,mode=RT,src=esp32,rec=%s,n=%" PRIu32 ",arm=%s,fcpu_mhz=%d,t1=0.165,t2=0.63,stim_sha=%s\n",
           STIM_REC, s_plat.n, s_arm == AFIB_ARM_MENTAH ? "mentah" : "berpenanda", fmax, s_sha);
    uint32_t total = (uint32_t)detik * AFIB_FS_HZ;
    if (total > s_plat.n) total = s_plat.n;
    plat_flush();
    vTaskDelay(pdMS_TO_TICKS(300));
    uart_off();                       /* driver UART memegang kunci APB, lepas selama fase */
    esp_err_t e = set_pm(fmax, fmin, ls != 0);

    esp_timer_handle_t tm;
    const esp_timer_create_args_t ta = {.callback = on_tick, .name = "fs250"};
    ESP_ERROR_CHECK(esp_timer_create(&ta, &tm));
    ulTaskNotifyTake(pdTRUE, 0);
    ESP_ERROR_CHECK(esp_timer_start_periodic(tm, 1000000 / AFIB_FS_HZ));

    /* fase 1: timer 250 Hz berjalan, task bangun tiap sampel, rantai tidak dijalankan */
    plat_marker(MK_IDLE);
    uint64_t a0 = plat_us();
    uint32_t telat0 = 0;
    for (uint32_t k = 0; k < total;) {
        uint32_t got = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (got > 1) telat0 += got - 1;
        k += got;
    }
    uint64_t a1 = plat_us();
    plat_marker(MK_NONE);
    vTaskDelay(pdMS_TO_TICKS(300));

    /* fase 2: satu sampel per tik, rantai berjalan seperti perangkat sungguhan */
    afib_chain_t *rt = afib_run_chain();
    rt->on_qrs = NULL; rt->on_window = NULL; rt->cycles = NULL;
    afib_init(rt, s_arm);
    uint64_t csum = 0;
    uint32_t cmax = 0, telat = 0;
    ulTaskNotifyTake(pdTRUE, 0);
    plat_marker(MK_RT);
    uint64_t b0 = plat_us();
    for (uint32_t k = 0; k < total; k++) {
        uint32_t got = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (got > 1) telat += got - 1;
        uint32_t t = plat_cycles();
        afib_step(rt, s_plat.stim[k], NULL);
        uint32_t dt = plat_cycles() - t;
        csum += dt;
        if (dt > cmax) cmax = dt;
    }
    uint64_t b1 = plat_us();
    plat_marker(MK_NONE);
    esp_timer_stop(tm);
    esp_timer_delete(tm);
    set_pm((int)s_fcpu, (int)s_fcpu, false);
    uart_on();
    printf("PH,0,rtidle,%llu,%llu,0,%" PRIu32 ",0,0,telat=%" PRIu32 ",fmax=%d,fmin=%d,ls=%d\n",
           (unsigned long long)a0, (unsigned long long)(a1 - a0), total, telat0, fmax, fmin, ls);
    printf("PH,0,rt,%llu,%llu,0,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",cyc_mean=%.2f,cyc_max=%" PRIu32
           ",telat=%" PRIu32 ",fmax=%d,fmin=%d,ls=%d,pm_err=%d\n",
           (unsigned long long)b0, (unsigned long long)(b1 - b0), total, rt->n_win, rt->n_win_review,
           (double)csum / (double)total, cmax, telat, fmax, fmin, ls, (int)e);
    printf("END,RT\n");
}

/* ------------------------------------------------------------------ perintah */
static int baca_baris(char *buf, int cap)
{
    int n = 0;
    for (;;) {
        uint8_t ch;
        int r = uart_read_bytes(CON_UART, &ch, 1, pdMS_TO_TICKS(100));
        if (r <= 0) continue;
        if (ch == '\r') continue;
        if (ch == '\n') { buf[n] = 0; return n; }
        if (n < cap - 1) buf[n++] = (char)ch;
    }
}

static void task_bench(void *arg)
{
    (void)arg;
    char line[96];
    info();
    for (;;) {
        int n = baca_baris(line, sizeof(line));
        if (n == 0) continue;
        char cmd[16] = {0};
        int a = 0, b = 0, c = 0, d = 0;
        char word[16] = {0};
        sscanf(line, "%15s", cmd);
        s_plat.fcpu_mhz = s_fcpu;
        if (!strcmp(cmd, "INFO")) {
            info();
        } else if (!strcmp(cmd, "VERIF")) {
            afib_run_verif(&s_plat, s_arm);
        } else if (!strcmp(cmd, "PROF")) {
            if (sscanf(line, "%*s %d", &a) != 1 || a < 1) a = 3;
            plat_flush();
            vTaskDelay(pdMS_TO_TICKS(200));
            afib_run_prof(&s_plat, s_arm, a);
        } else if (!strcmp(cmd, "POWER")) {
            if (sscanf(line, "%*s %d %d %d", &a, &b, &c) != 3) { a = 5; b = 20; c = 20; }
            afib_run_power(&s_plat, s_arm, a, b, c);
        } else if (!strcmp(cmd, "FREQ")) {
            if (sscanf(line, "%*s %d", &a) != 1) a = 240;
            esp_err_t e = set_pm(a, a, false);
            if (e == ESP_OK) s_fcpu = (uint32_t)a;
            vTaskDelay(pdMS_TO_TICKS(50));
            printf("OK,FREQ,%d,err=%d,ukur_mhz=%" PRIu32 "\n", a, (int)e, ukur_mhz());
            printf("END,FREQ\n");
        } else if (!strcmp(cmd, "RT")) {
            if (sscanf(line, "%*s %d %d %d %d", &a, &b, &c, &d) != 4) { a = 60; b = 240; c = 40; d = 1; }
            run_rt(a, b, c, d);
        } else if (!strcmp(cmd, "ARM")) {
            sscanf(line, "%*s %15s", word);
            s_arm = !strcmp(word, "mentah") ? AFIB_ARM_MENTAH : AFIB_ARM_BERPENANDA;
            printf("OK,ARM,%s\nEND,ARM\n", s_arm == AFIB_ARM_MENTAH ? "mentah" : "berpenanda");
        } else {
            printf("ERR,perintah tidak dikenal: %s\n", line);
        }
        plat_flush();
    }
}

void app_main(void)
{
    gpio_config_t io = {
        .pin_bit_mask = (1ULL << PIN_M0) | (1ULL << PIN_M1) | (1ULL << PIN_LED),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&io);
    plat_marker(MK_NONE);
    gpio_set_level(PIN_LED, 0);
    gpio_sleep_sel_dis(PIN_M0);         /* pin penanda tetap dikemudikan saat light sleep */
    gpio_sleep_sel_dis(PIN_M1);

    uart_set_baudrate(CON_UART, CON_BAUD);
    uart_on();

    s_plat.stim = (const uint16_t *)stim_start;
    s_plat.n = (uint32_t)((stim_end - stim_start) / 2);
    s_plat.rec = STIM_REC;
    s_plat.src = "esp32";
    s_plat.cycles = plat_cycles;
    s_plat.time_us = plat_us;
    s_plat.marker = plat_marker;
    s_plat.sleep_ms = plat_sleep;
    s_plat.flush = plat_flush;

    unsigned char h[32];
    mbedtls_sha256(stim_start, (size_t)(stim_end - stim_start), h, 0);
    for (int i = 0; i < 32; i++) sprintf(s_sha + 2 * i, "%02x", h[i]);
    s_plat.stim_sha = s_sha;

    set_pm(240, 240, false);
    s_fcpu = 240;
    s_plat.fcpu_mhz = s_fcpu;

    /* core 1 hanya untuk benchmark; core 0 menangani UART, esp_timer dan tick */
    xTaskCreatePinnedToCore(task_bench, "bench", 8192, NULL, 10, &s_task, 1);
}
