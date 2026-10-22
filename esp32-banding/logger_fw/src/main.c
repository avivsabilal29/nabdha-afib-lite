/*
 * ESP32 LOGGER -- INA219 + dua pin penanda dari ESP32 DUT, ESP-IDF 5.3 + FreeRTOS
 * Proyek NABDHA AFIB-LITE (ChipHack26), pengukuran daya banding ESP32 vs chip.
 *
 * Rangkaian:
 *   INA219 VCC -> 3V3 logger, GND -> GND bersama, SDA -> GPIO21, SCL -> GPIO22
 *   INA219 VIN+ -> keluaran LDO (sisi sumber), VIN- -> rail 3V3 board DUT (sisi beban)
 *   GPIO25 <- penanda M0 DUT (GPIO25), GPIO26 <- penanda M1 DUT (GPIO26)
 *
 * Laju sampel 1 kHz (esp_timer). Setiap sampel: tegangan shunt (LSB 10 uV), tegangan bus
 * di VIN- (LSB 4 mV) dan kode penanda. Logger memotong data menjadi segmen per kode penanda
 * (1 bench, 2 idle, 3 real-time), membuang TRIM ms di awal dan akhir tiap segmen untuk
 * statistik, dan mencetak satu baris SEG per segmen. Energi segmen dijumlahkan dari semua
 * sampelnya (tanpa trim).
 *
 * Keluaran USB 115200 baud:
 *   #INA,...                                           kepala, dijawab juga untuk INFO
 *   L,t_ms,code,i_mA,v_V,p_mW                          rata-rata 100 ms (pantauan langsung)
 *   SEG,k,code,t0_ms,dur_ms,n,i_mA,i_sd_mA,v_V,p_mW,p_min_mW,p_max_mW,e_mJ
 *   ERR,...                                            galat I2C atau INA219 tidak ada
 * Perintah: INFO | SHUNT <ohm> | TRIM <ms> | LIVE <0|1>
 */
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"

#include "seg.h"

#define PIN_SDA     GPIO_NUM_21
#define PIN_SCL     GPIO_NUM_22
#define PIN_M0      GPIO_NUM_25
#define PIN_M1      GPIO_NUM_26
#define INA_ADDR    0x40
#define CON_UART    UART_NUM_0
#define CON_BAUD    115200
#define PERIOD_US   1000

/* INA219 konfigurasi: BRNG 16 V, PGA /2 (+-80 mV, 0.8 A dengan R100), ADC bus dan shunt
 * 12 bit tanpa rata-rata (532 us), mode shunt+bus kontinu. */
#define INA_CFG     0x099F

typedef enum { MSG_LIVE, MSG_SEG, MSG_ERR } msg_kind_t;
typedef struct {
    msg_kind_t kind;
    uint32_t k, n, t0_ms, dur_ms, t_ms;
    uint8_t code;
    float i_ma, i_sd, v, p_mw, p_min, p_max, e_mj;
    char text[48];
} msg_t;

static i2c_master_dev_handle_t s_dev;
static i2c_master_bus_handle_t s_bus;
static QueueHandle_t s_q;
static TaskHandle_t s_task;
static volatile float s_shunt_ohm = 0.1f;
static volatile int s_trim = 100;          /* sampel = ms */
static volatile bool s_live = true;
static volatile uint32_t s_i2c_err;
static bool s_ina_ok;

/* ------------------------------------------------------------------ INA219 */
static esp_err_t ina_write(uint8_t reg, uint16_t v)
{
    uint8_t b[3] = {reg, (uint8_t)(v >> 8), (uint8_t)v};
    return i2c_master_transmit(s_dev, b, 3, 10);
}

static esp_err_t ina_read(uint8_t reg, uint16_t *v)
{
    uint8_t d[2];
    esp_err_t e = i2c_master_transmit_receive(s_dev, &reg, 1, d, 2, 10);
    if (e == ESP_OK) *v = (uint16_t)((d[0] << 8) | d[1]);
    return e;
}

static bool ina_init(void)
{
    if (i2c_master_probe(s_bus, INA_ADDR, 50) != ESP_OK) return false;
    if (ina_write(0x00, 0x8000) != ESP_OK) return false;        /* reset */
    vTaskDelay(pdMS_TO_TICKS(2));
    if (ina_write(0x00, INA_CFG) != ESP_OK) return false;
    uint16_t back = 0;
    if (ina_read(0x00, &back) != ESP_OK) return false;
    return back == INA_CFG;
}

static void head(void)
{
    printf("#INA,ver=1,ina=%s,addr=0x%02x,shunt_ohm=%.4f,cfg=0x%04x,pga_mv=80,adc_bit=12,"
           "period_us=%d,trim_ms=%d,lsb_shunt_uv=10,lsb_bus_mv=4,i2c_err=%" PRIu32 ",pin_m0=%d,pin_m1=%d\n",
           s_ina_ok ? "ok" : "TIDAK_ADA", INA_ADDR, (double)s_shunt_ohm, INA_CFG, PERIOD_US, s_trim,
           s_i2c_err, PIN_M0, PIN_M1);
}

/* ------------------------------------------------------------------ sampling */
static void on_tick(void *arg) { (void)arg; xTaskNotifyGive(s_task); }

static inline uint8_t baca_kode(void)
{
    return (uint8_t)(gpio_get_level(PIN_M0) | (gpio_get_level(PIN_M1) << 1));
}

static seg_state_t s_seg;
static volatile int s_trim_req = -1;      /* TRIM baru diterapkan di awal segmen berikutnya */

static void task_sample(void *arg)
{
    (void)arg;
    seg_init(&s_seg, s_trim);
    double l_i = 0, l_v = 0, l_p = 0;     /* pantauan langsung, rata-rata 100 sampel */
    uint32_t l_n = 0;
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        int64_t t = esp_timer_get_time();
        if (!s_ina_ok) continue;                 /* task_print mencoba ulang tiap detik */
        uint16_t rs = 0, rb = 0;
        if (ina_read(0x01, &rs) != ESP_OK || ina_read(0x02, &rb) != ESP_OK) {
            s_i2c_err++;
            continue;
        }
        float i_ma = (float)(int16_t)rs * 0.01f / s_shunt_ohm;   /* 10 uV per LSB */
        float v = (float)(rb >> 3) * 0.004f;                       /* 4 mV per LSB */
        uint8_t k = baca_kode();
        if (s_trim_req >= 0 && !s_seg.aktif) {
            s_seg.trim = s_trim_req > SEG_RING_MAX ? SEG_RING_MAX : s_trim_req;
            s_seg.ring_n = s_seg.ring_head = 0;
            s_trim_req = -1;
        }
        seg_out_t o;
        if (seg_feed(&s_seg, t, i_ma, v, k, &o)) {
            msg_t m = {.kind = MSG_SEG, .k = o.k, .code = o.code, .t0_ms = o.t0_ms, .dur_ms = o.dur_ms,
                       .n = o.n, .i_ma = o.i_ma, .i_sd = o.i_sd, .v = o.v, .p_mw = o.p_mw,
                       .p_min = o.p_min, .p_max = o.p_max, .e_mj = o.e_mj};
            xQueueSend(s_q, &m, 0);
        }
        l_i += i_ma; l_v += v; l_p += v * i_ma; l_n++;
        if (l_n >= 100) {
            if (s_live) {
                msg_t m = {.kind = MSG_LIVE, .t_ms = (uint32_t)(t / 1000), .code = s_seg.code,
                           .i_ma = (float)(l_i / l_n), .v = (float)(l_v / l_n), .p_mw = (float)(l_p / l_n)};
                xQueueSend(s_q, &m, 0);
            }
            l_i = l_v = l_p = 0;
            l_n = 0;
        }
    }
}

/* ------------------------------------------------------------------ cetak dan perintah */
static void task_print(void *arg)
{
    (void)arg;
    msg_t m;
    uint32_t err_last = 0;
    for (;;) {
        bool dapat = xQueueReceive(s_q, &m, pdMS_TO_TICKS(1000)) == pdTRUE;
        if (dapat) {
            if (m.kind == MSG_LIVE) {
                printf("L,%" PRIu32 ",%u,%.3f,%.4f,%.3f\n", m.t_ms, m.code, (double)m.i_ma, (double)m.v,
                       (double)m.p_mw);
            } else if (m.kind == MSG_SEG) {
                printf("SEG,%" PRIu32 ",%u,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n",
                       m.k, m.code, m.t0_ms, m.dur_ms, m.n, (double)m.i_ma, (double)m.i_sd, (double)m.v,
                       (double)m.p_mw, (double)m.p_min, (double)m.p_max, (double)m.e_mj);
            }
        }
        if (!s_ina_ok && !dapat) {
            printf("ERR,INA219 tidak menjawab di 0x%02x (cek SDA21 SCL22 VCC GND)\n", INA_ADDR);
            s_ina_ok = ina_init();
            if (s_ina_ok) head();
        } else if (s_i2c_err != err_last) {
            printf("ERR,i2c_err=%" PRIu32 "\n", s_i2c_err);
            err_last = s_i2c_err;
        }
        fflush(stdout);     /* tiap baris langsung ke UART; semburan ~4 KB di PC berasal dari read() host, bukan dari sini */
    }
}

static void task_cmd(void *arg)
{
    (void)arg;
    char line[64];
    int n = 0;
    for (;;) {
        uint8_t ch;
        if (uart_read_bytes(CON_UART, &ch, 1, pdMS_TO_TICKS(100)) <= 0) continue;
        if (ch == '\r') continue;
        if (ch != '\n') { if (n < (int)sizeof(line) - 1) line[n++] = (char)ch; continue; }
        line[n] = 0;
        n = 0;
        float f;
        int a;
        if (!strncmp(line, "INFO", 4)) head();
        else if (sscanf(line, "SHUNT %f", &f) == 1 && f > 0) { s_shunt_ohm = f; head(); }
        else if (sscanf(line, "TRIM %d", &a) == 1 && a >= 0 && a <= SEG_RING_MAX) { s_trim = a; s_trim_req = a; head(); }
        else if (sscanf(line, "LIVE %d", &a) == 1) { s_live = a != 0; head(); }
        else if (line[0]) printf("ERR,perintah tidak dikenal: %s\n", line);
    }
}

void app_main(void)
{
    uart_set_baudrate(CON_UART, CON_BAUD);
    uart_driver_install(CON_UART, 512, 0, 0, NULL, 0);
    esp_log_level_set("i2c.master", ESP_LOG_NONE);   /* galat I2C dilaporkan sendiri lewat ERR */

    gpio_config_t in = {
        .pin_bit_mask = (1ULL << PIN_M0) | (1ULL << PIN_M1),
        .mode = GPIO_MODE_INPUT,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,   /* DUT mati = kode 0, bukan pin mengambang */
    };
    gpio_config(&in);

    i2c_master_bus_config_t bc = {
        .i2c_port = I2C_NUM_0, .sda_io_num = PIN_SDA, .scl_io_num = PIN_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,   /* modul INA219 biasanya sudah punya pull-up 10k */
    };
    ESP_ERROR_CHECK(i2c_new_master_bus(&bc, &s_bus));
    i2c_device_config_t dc = {.dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = INA_ADDR,
                              .scl_speed_hz = 400000};
    ESP_ERROR_CHECK(i2c_master_bus_add_device(s_bus, &dc, &s_dev));
    s_ina_ok = ina_init();

    s_q = xQueueCreate(64, sizeof(msg_t));
    head();
    xTaskCreatePinnedToCore(task_print, "print", 4096, NULL, 5, NULL, 0);
    xTaskCreatePinnedToCore(task_cmd, "cmd", 3072, NULL, 4, NULL, 0);
    xTaskCreatePinnedToCore(task_sample, "sample", 4096, NULL, 10, &s_task, 1);

    esp_timer_handle_t tm;
    const esp_timer_create_args_t ta = {.callback = on_tick, .name = "ina1k"};
    ESP_ERROR_CHECK(esp_timer_create(&ta, &tm));
    ESP_ERROR_CHECK(esp_timer_start_periodic(tm, PERIOD_US));
}
