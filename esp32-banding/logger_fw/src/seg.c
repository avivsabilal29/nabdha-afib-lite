/*
 * seg.c -- pemotong segmen daya. Satu segmen = deretan sampel dengan kode penanda yang sama
 * (setelah debouncing). Statistik membuang `trim` sampel di awal dan di akhir segmen supaya
 * transien perpindahan fase tidak ikut; energi dijumlahkan dari semua sampel segmen.
 */
#include "seg.h"

#include <math.h>
#include <string.h>

void seg_init(seg_state_t *s, int trim)
{
    memset(s, 0, sizeof(*s));
    if (trim < 0) trim = 0;
    if (trim > SEG_RING_MAX) trim = SEG_RING_MAX;
    s->trim = trim;
    s->p_min = 1e9;
    s->p_max = -1e9;
}

static void reset_seg(seg_state_t *s, int64_t t)
{
    s->seg_t0 = t;
    s->last_t = t;
    s->seg_total = s->ring_n = s->ring_head = s->st_n = 0;
    s->mean_i = s->m2_i = s->sum_v = s->sum_p = s->e_uj = s->all_i = s->all_v = s->all_p = 0;
    s->p_min = 1e9;
    s->p_max = -1e9;
}

static void tambah_stat(seg_state_t *s, const seg_smp_t *m)
{
    s->st_n++;
    double d = m->i_ma - s->mean_i;
    s->mean_i += d / s->st_n;
    s->m2_i += d * (m->i_ma - s->mean_i);
    s->sum_v += m->v;
    s->sum_p += m->p_mw;
    if (m->p_mw < s->p_min) s->p_min = m->p_mw;
    if (m->p_mw > s->p_max) s->p_max = m->p_mw;
}

static void tutup(seg_state_t *s, seg_out_t *o)
{
    memset(o, 0, sizeof(*o));
    o->k = s->seg_k++;
    o->code = s->code;
    o->total = s->seg_total;
    o->t0_ms = (uint32_t)(s->seg_t0 / 1000);
    o->dur_ms = (uint32_t)((s->last_t - s->seg_t0) / 1000);
    o->e_mj = (float)(s->e_uj / 1000.0);
    if (s->st_n > 0) {
        o->n = s->st_n;
        o->i_ma = (float)s->mean_i;
        o->i_sd = s->st_n > 1 ? (float)sqrt(s->m2_i / (s->st_n - 1)) : 0.0f;
        o->v = (float)(s->sum_v / s->st_n);
        o->p_mw = (float)(s->sum_p / s->st_n);
        o->p_min = (float)s->p_min;
        o->p_max = (float)s->p_max;
    } else {                                    /* segmen lebih pendek dari 2 x trim */
        o->n = s->seg_total;
        o->i_ma = (float)(s->all_i / s->seg_total);
        o->v = (float)(s->all_v / s->seg_total);
        o->p_mw = (float)(s->all_p / s->seg_total);
        o->p_min = o->p_max = o->p_mw;
    }
}

bool seg_feed(seg_state_t *s, int64_t t, float i_ma, float v, uint8_t k, seg_out_t *out)
{
    bool selesai = false;
    if (k != s->code) {
        if (k == s->cand) s->cand_n++;
        else { s->cand = k; s->cand_n = 1; }
    } else {
        s->cand_n = 0;
    }
    if (k != s->code && s->cand_n >= SEG_DEBOUNCE) {
        if (s->aktif && s->seg_total > 0) {
            tutup(s, out);
            selesai = true;
        }
        s->code = k;
        s->cand_n = 0;
        s->aktif = (k != 0);
        reset_seg(s, t);
    }
    if (!s->aktif) return selesai;

    float p = v * i_ma;
    int64_t dt = s->seg_total == 0 ? 1000 : t - s->last_t;
    s->e_uj += (double)p * (double)dt / 1000.0;          /* mW x us = nJ, /1000 = uJ */
    s->last_t = t;
    s->all_i += i_ma; s->all_v += v; s->all_p += p;
    seg_smp_t m = {i_ma, v, p};
    const uint32_t trim = (uint32_t)s->trim;
    if (trim == 0) {
        tambah_stat(s, &m);
    } else if (s->ring_n == trim) {
        seg_smp_t old = s->ring[s->ring_head];
        if (s->seg_total >= 2 * trim) tambah_stat(s, &old);   /* sampel ke-(total - trim) >= trim */
        s->ring[s->ring_head] = m;
        s->ring_head = (s->ring_head + 1) % trim;
    } else {
        s->ring[(s->ring_head + s->ring_n) % trim] = m;
        s->ring_n++;
    }
    s->seg_total++;
    return selesai;
}
