/*
 * AD8232 ECG -> ESP32, ESP-IDF v5.3 + FreeRTOS
 * Proyek NABDHA AFIB-LITE (ChipHack26)
 *
 * Alur:
 *   gptimer 2 kHz (ISR) --notify--> task_sample (core 1, prioritas tinggi)
 *       baca ADC1_CH0 (mV terkalibrasi) + LO+/LO-
 *       jumlahkan 8 bacaan -> 1 sampel 250 Hz
 *       kurangi dasar, skala ke 200 cacah/mV, jepit ±2047, isi penanda
 *       --queue--> task_tx (core 0)
 *           mode biner : rekaman 8 bita + set header tiap 1 s
 *           mode teks  : baris Teleplot ">ecg:123"
 *   task_led: nyala tetap = elektroda lepas, kedip 1 Hz = merekam,
 *             kedip cepat = menunggu elektroda / kalibrasi dasar
 */
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "driver/gpio.h"
#include "driver/gptimer.h"
#include "driver/uart.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_log.h"
#include "esp_err.h"
#include "esp_timer.h"

#include "app_config.h"
#include "ecg_frame.h"

static const char *TAG = "ecg";

/* ------------------------------------------------------------------ */
typedef struct {
    int16_t counts;
    uint8_t flags;
} ecg_sample_t;

typedef enum {
    ST_WAIT_LEADS = 0,
    ST_CALIBRATING,
    ST_RUNNING,
} app_state_t;

static TaskHandle_t              s_sample_task;
static QueueHandle_t             s_queue;
static gptimer_handle_t          s_timer;
static adc_oneshot_unit_handle_t s_adc;
static adc_channel_t             s_adc_chan;
static adc_cali_handle_t         s_cali;
static bool                      s_cali_ok;
static bool                      s_baseline_auto_ok;
static int32_t                   s_baseline_mv = BASELINE_MV_NOMINAL;

static volatile app_state_t      s_state = ST_WAIT_LEADS;
static volatile bool             s_lead_off = true;

/* statistik (dibaca task_tx di mode teks) */
static volatile uint32_t s_late_ticks;
static volatile uint32_t s_queue_drops;

/* ------------------------------------------------------------------ */
/*  ISR timer 2 kHz: hanya membangunkan task_sample                     */
/* ------------------------------------------------------------------ */
static bool IRAM_ATTR on_timer_alarm(gptimer_handle_t timer,
                                     const gptimer_alarm_event_data_t *edata,
                                     void *user_ctx)
{
    BaseType_t hp_woken = pdFALSE;
    vTaskNotifyGiveFromISR(s_sample_task, &hp_woken);
    return hp_woken == pdTRUE;
}

/* ------------------------------------------------------------------ */
/*  Inisialisasi perangkat keras                                        */
/* ------------------------------------------------------------------ */
static void init_gpio(void)
{
    gpio_config_t in = {
        .pin_bit_mask = (1ULL << PIN_LO_PLUS) | (1ULL << PIN_LO_MINUS),
        .mode         = GPIO_MODE_INPUT,
        .pull_up_en   = GPIO_PULLUP_ENABLE,   /* kabel LO putus -> terbaca lepas */
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&in));

    gpio_config_t out = {
        .pin_bit_mask = (1ULL << PIN_LED),
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&out));
    gpio_set_level(PIN_LED, 0);
}

static void init_adc(void)
{
    adc_unit_t unit;
    ESP_ERROR_CHECK(adc_oneshot_io_to_channel(PIN_ECG_OUT, &unit, &s_adc_chan));

    adc_oneshot_unit_init_cfg_t ucfg = {
        .unit_id  = unit,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&ucfg, &s_adc));

    adc_oneshot_chan_cfg_t ccfg = {
        .atten    = ADC_ATTEN_DB_12,     /* rentang ~0,15..3,1 V */
        .bitwidth = ADC_BITWIDTH_12,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(s_adc, s_adc_chan, &ccfg));

    /* Kalibrasi pabrik (eFuse) -> bacaan langsung dalam mV, 1 langkah = 1 mV */
    adc_cali_line_fitting_config_t lcfg = {
        .unit_id      = unit,
        .atten        = ADC_ATTEN_DB_12,
        .bitwidth     = ADC_BITWIDTH_12,
        .default_vref = 1100,
    };
    s_cali_ok = (adc_cali_create_scheme_line_fitting(&lcfg, &s_cali) == ESP_OK);
    if (!s_cali_ok) {
        ESP_LOGW(TAG, "kalibrasi ADC tidak tersedia, pakai pendekatan linear");
    }
}

static void init_uart(void)
{
    uart_config_t cfg = {
        .baud_rate  = UART_BAUD,
        .data_bits  = UART_DATA_8_BITS,
        .parity     = UART_PARITY_DISABLE,
        .stop_bits  = UART_STOP_BITS_1,
        .flow_ctrl  = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 256, 4096, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0, &cfg));
}

static void init_timer(void)
{
    gptimer_config_t tcfg = {
        .clk_src       = GPTIMER_CLK_SRC_DEFAULT,
        .direction     = GPTIMER_COUNT_UP,
        .resolution_hz = 1000000,                 /* 1 tick = 1 us */
    };
    ESP_ERROR_CHECK(gptimer_new_timer(&tcfg, &s_timer));

    gptimer_event_callbacks_t cbs = { .on_alarm = on_timer_alarm };
    ESP_ERROR_CHECK(gptimer_register_event_callbacks(s_timer, &cbs, NULL));

    gptimer_alarm_config_t acfg = {
        .reload_count = 0,
        .alarm_count  = 1000000 / SUBSAMPLE_HZ,   /* 500 us */
        .flags.auto_reload_on_alarm = true,
    };
    ESP_ERROR_CHECK(gptimer_set_alarm_action(s_timer, &acfg));
    ESP_ERROR_CHECK(gptimer_enable(s_timer));
}

/* ------------------------------------------------------------------ */
/*  Pembacaan                                                           */
/* ------------------------------------------------------------------ */
static inline bool read_lead_off(void)
{
    /* AD8232: LO+ / LO- HIGH = elektroda lepas (mode dc) */
    return gpio_get_level(PIN_LO_PLUS) || gpio_get_level(PIN_LO_MINUS);
}

/* Satu bacaan ADC. Mengembalikan mV di pin OUT, *rail = true bila mentok rel */
static int read_adc_mv(bool *rail)
{
    int raw = 0;
    if (adc_oneshot_read(s_adc, s_adc_chan, &raw) != ESP_OK) {
        *rail = true;
        return s_baseline_mv;
    }
    if (raw <= ADC_RAIL_MARGIN || raw >= (4095 - ADC_RAIL_MARGIN)) {
        *rail = true;
    }
    int mv;
    if (s_cali_ok) {
        adc_cali_raw_to_voltage(s_cali, raw, &mv);
    } else {
        mv = (raw * ADC_FULL_SCALE_MV) / 4095;
    }
    return mv;
}

/* Tunggu elektroda terpasang, lalu ukur dasar (REFOUT) rata-rata 2 s */
static void measure_baseline(void)
{
#if BASELINE_MV_FIXED > 0
    s_baseline_mv = BASELINE_MV_FIXED;
    s_baseline_auto_ok = false;
    return;
#else
    s_state = ST_WAIT_LEADS;
    int waited = 0;
    while (read_lead_off() && waited < BASELINE_WAIT_LEADS_MS) {
        s_lead_off = true;
        vTaskDelay(pdMS_TO_TICKS(10));
        waited += 10;
    }
    if (read_lead_off()) {
        s_baseline_mv = BASELINE_MV_NOMINAL;
        s_baseline_auto_ok = false;
        ESP_LOGW(TAG, "elektroda belum terpasang, dasar nominal %d mV", (int)s_baseline_mv);
        return;
    }

    s_state = ST_CALIBRATING;
    s_lead_off = false;
    int64_t sum = 0;
    int n = 0;
    const int64_t t_end = esp_timer_get_time() + (int64_t)BASELINE_MEASURE_MS * 1000;
    while (esp_timer_get_time() < t_end) {   /* berbasis waktu, tak bergantung tick */
        bool rail = false;
        sum += read_adc_mv(&rail);
        n++;
        vTaskDelay(1);                       /* 1 ms bila CONFIG_FREERTOS_HZ=1000 */
    }
    s_baseline_mv = (int32_t)(sum / n);
    s_baseline_auto_ok = true;
    ESP_LOGI(TAG, "dasar terukur %d mV dari %d bacaan", (int)s_baseline_mv, n);
#endif
}

/* ------------------------------------------------------------------ */
/*  task_sample: inti pencuplikan                                       */
/* ------------------------------------------------------------------ */
static void task_sample(void *arg)
{
    measure_baseline();
    s_state = ST_RUNNING;
    ESP_ERROR_CHECK(gptimer_start(s_timer));

    int32_t sum_mv   = 0;
    int     n        = 0;
    int     lo_n     = 0;        /* jumlah subsampel dengan LO tinggi */
    uint8_t flags    = 0;
    bool    carry_gap = false;   /* sampel sebelumnya hilang -> tandai sampel ini */

    for (;;) {
        /* pdFALSE: ambil satu tick per putaran, tick tertunda tidak hilang */
        uint32_t pending = ulTaskNotifyTake(pdFALSE, pdMS_TO_TICKS(100));
        if (pending == 0) {
            continue;                        /* timer berhenti? tunggu lagi */
        }
        if (pending > 2) {                   /* tertinggal > 1 ms: waktu tak lagi tepat */
            flags |= ECG_FLAG_GAP;
            s_late_ticks++;
        }

        bool rail = false;
        bool lo   = read_lead_off();
        int  mv   = read_adc_mv(&rail);

        sum_mv += mv;
        n++;
        if (lo)   lo_n++;
        if (rail) flags |= ECG_FLAG_CLAMP;
        s_lead_off = lo;

        if (n >= SUBSAMPLES) {
            if (lo_n >= LO_GAP_MIN_SUBSAMPLES) {
                flags |= ECG_FLAG_GAP;
            }
            if (carry_gap) {
                flags |= ECG_FLAG_GAP;
                carry_gap = false;
            }
            ecg_sample_t s;
            s.counts = ecg_counts_from_sum(sum_mv, n, s_baseline_mv, KIT_GAIN,
                                           COUNTS_PER_MV, CLAMP_COUNT, &flags);
            s.flags  = flags;
            if (xQueueSend(s_queue, &s, 0) != pdTRUE) {
                s_queue_drops++;
                carry_gap = true;
            }
            sum_mv = 0;
            n      = 0;
            lo_n   = 0;
            flags  = 0;
        }
    }
}

/* ------------------------------------------------------------------ */
/*  task_tx: kirim ke PC                                                */
/* ------------------------------------------------------------------ */
#if !ECG_OUTPUT_TEXT
static void send_header_set(void)
{
    uint16_t vals[ECG_HDR_COUNT] = {
        [ECG_HDR_FW_VERSION]    = (FW_VERSION_MAJOR << 8) | FW_VERSION_MINOR,
        [ECG_HDR_KIT_GAIN]      = KIT_GAIN,
        [ECG_HDR_ADC_FS_MV]     = ADC_FULL_SCALE_MV,
        [ECG_HDR_SAMPLE_HZ]     = SAMPLE_HZ,
        [ECG_HDR_BASELINE_MV]   = (uint16_t)s_baseline_mv,
        [ECG_HDR_COUNTS_PER_MV] = COUNTS_PER_MV,
        [ECG_HDR_ADC_SOURCE]    = ADC_SOURCE_ID,
        [ECG_HDR_STATUS]        = (s_cali_ok ? 1 : 0) | (s_baseline_auto_ok ? 2 : 0),
    };
    uint8_t buf[ECG_FRAME_LEN * ECG_HDR_COUNT];
    for (int i = 0; i < ECG_HDR_COUNT; i++) {
        ecg_frame_header(&buf[i * ECG_FRAME_LEN], (uint8_t)i, vals[i]);
    }
    uart_write_bytes(UART_NUM_0, buf, sizeof(buf));
}
#endif

static void task_tx(void *arg)
{
    uint32_t index = 0;
#if !ECG_OUTPUT_TEXT
    uint8_t  seq   = 0;
#endif
    ecg_sample_t s;

    for (;;) {
        if (xQueueReceive(s_queue, &s, portMAX_DELAY) != pdTRUE) {
            continue;
        }
#if ECG_OUTPUT_TEXT
        char line[48];
        int len = snprintf(line, sizeof(line), ">ecg:%d\n>gap:%d\n>clamp:%d\n",
                           s.counts,
                           (s.flags & ECG_FLAG_GAP) ? 1 : 0,
                           (s.flags & ECG_FLAG_CLAMP) ? 1 : 0);
        uart_write_bytes(UART_NUM_0, line, len);
        if ((index % SAMPLE_HZ) == 0) {
            len = snprintf(line, sizeof(line), "dasar=%dmV telat=%u buang=%u\n",
                           (int)s_baseline_mv, (unsigned)s_late_ticks,
                           (unsigned)s_queue_drops);
            uart_write_bytes(UART_NUM_0, line, len);
        }
#else
        if ((index % HEADER_EVERY_N) == 0) {
            send_header_set();
        }
        uint8_t f[ECG_FRAME_LEN];
        ecg_frame_sample(f, s.flags, seq, s.counts);
        uart_write_bytes(UART_NUM_0, f, sizeof(f));
        seq++;
#endif
        index++;
    }
}

/* ------------------------------------------------------------------ */
/*  task_led: indikator                                                 */
/* ------------------------------------------------------------------ */
static void task_led(void *arg)
{
    uint32_t t = 0;
    for (;;) {
        int level;
        switch (s_state) {
        case ST_WAIT_LEADS:
        case ST_CALIBRATING:
            level = (t / 2) % 2;                  /* kedip cepat 5 Hz */
            break;
        default:
            level = s_lead_off ? 1 : ((t % 20) < 2); /* lepas: nyala; normal: kedip 1 Hz */
            break;
        }
        gpio_set_level(PIN_LED, level);
        t++;
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

/* ------------------------------------------------------------------ */
void app_main(void)
{
    ESP_LOGI(TAG, "AD8232 ECG fw %d.%d, gain kit %d, mode %s",
             FW_VERSION_MAJOR, FW_VERSION_MINOR, KIT_GAIN,
             ECG_OUTPUT_TEXT ? "teks" : "biner");

    init_gpio();
    init_adc();
    init_timer();
    init_uart();

#if !ECG_OUTPUT_TEXT
    /* Di mode biner, log teks akan merusak aliran -> matikan semua log */
    esp_log_level_set("*", ESP_LOG_NONE);
#endif

    s_queue = xQueueCreate(64, sizeof(ecg_sample_t));   /* ~256 ms cadangan */
    configASSERT(s_queue);

    xTaskCreatePinnedToCore(task_tx,  "tx",  4096, NULL, 10, NULL, 0);
    xTaskCreatePinnedToCore(task_led, "led", 2048, NULL, 2,  NULL, 0);
    xTaskCreatePinnedToCore(task_sample, "sample", 4096, NULL,
                            configMAX_PRIORITIES - 2, &s_sample_task, 1);
}
