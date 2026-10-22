/*
 * seg.h -- pemotong segmen daya per kode penanda, tanpa ketergantungan ESP-IDF
 * (dipakai logger dan uji PC logger_fw/host_test/uji_seg.c).
 */
#ifndef SEG_H
#define SEG_H

#include <stdbool.h>
#include <stdint.h>

#define SEG_DEBOUNCE  3          /* kode baru diterima setelah stabil 3 sampel */
#define SEG_RING_MAX  1000       /* trim maksimum 1000 sampel */

typedef struct { float i_ma, v, p_mw; } seg_smp_t;

typedef struct {
    uint32_t k, n, total;
    uint8_t code;
    uint32_t t0_ms, dur_ms;
    float i_ma, i_sd, v, p_mw, p_min, p_max, e_mj;
} seg_out_t;

typedef struct {
    int trim;                    /* sampel yang dibuang di awal dan akhir segmen */
    uint8_t code, cand;
    int cand_n;
    uint32_t seg_k;
    bool aktif;
    int64_t seg_t0, last_t;
    uint32_t seg_total, ring_n, ring_head, st_n;
    double mean_i, m2_i, sum_v, sum_p, e_uj, p_min, p_max;
    double all_i, all_v, all_p;
    seg_smp_t ring[SEG_RING_MAX];
} seg_state_t;

void seg_init(seg_state_t *s, int trim);
/* satu sampel; kembalikan true bila sebuah segmen bernomor (kode != 0) baru selesai */
bool seg_feed(seg_state_t *s, int64_t t_us, float i_ma, float v, uint8_t code_raw, seg_out_t *out);

#endif
