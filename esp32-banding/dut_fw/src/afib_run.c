/*
 * afib_run.c -- mode uji bersama ESP32 dan PC. Lihat afib_run.h untuk protokol baris.
 */
#include "afib_run.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static afib_chain_t g_c;
afib_chain_t *afib_run_chain(void) { return &g_c; }
#define BLK 1024
static uint16_t g_blk[BLK];

static const char *nama_arm(int arm) { return arm == AFIB_ARM_MENTAH ? "mentah" : "berpenanda"; }

static void kepala(const afib_plat_t *p, const char *mode, int arm)
{
    printf("#AFIB,mode=%s,src=%s,rec=%s,n=%" PRIu32 ",arm=%s,fcpu_mhz=%" PRIu32
           ",t1=0.165,t2=0.63,stim_sha=%s\n",
           mode, p->src, p->rec, p->n, nama_arm(arm), p->fcpu_mhz, p->stim_sha);
}

static uint64_t dbits(double x)
{
    uint64_t u;
    memcpy(&u, &x, sizeof(u));
    return u;
}

static void cetak_penghitung(const afib_chain_t *c)
{
    printf("C,puncak=%" PRIu32 ",qrs=%" PRIu32 ",rr=%" PRIu32 ",cari_mundur=%" PRIu32
           ",ditolak_t=%" PRIu32 ",diperiksa=%" PRIu32 ",calon_kedua=%" PRIu32
           ",semai=%" PRId32 ",penanda=%" PRIu32 ",irama_keep=%" PRIu32 ",irama_split=%" PRIu32
           ",irama_drop=%" PRIu32 ",irama_gap=%" PRIu32 ",jendela=%" PRIu32 ",review=%" PRIu32
           ",normal=%" PRIu32 ",undecided=%" PRIu32 ",pk_overflow=%" PRIu32 ",pk_span_max=%" PRIu32 "\n",
           c->n_puncak, c->n_qrs, c->n_rr, c->cari_mundur, c->ditolak, c->diperiksa,
           c->calon_kedua, c->rr_semai, c->penanda, c->ir_kept, c->ir_split, c->ir_dropped,
           c->ir_gap, c->n_win, c->n_win_review, c->n_win_normal, c->n_win_undecided,
           c->pk_overflow, c->pk_span_max);
}

/* ------------------------------------------------------------------ VERIF */
static void cb_qrs(int32_t pos, int32_t rr_ms, int mark, void *ctx)
{
    uint32_t *k = (uint32_t *)ctx;
    printf("Q,%" PRIu32 ",%" PRId32 ",%" PRId32 ",%d\n", *k, pos, rr_ms, mark);
    (*k)++;
}

static void cetak_jendela(const afib_window_t *w)
{
    printf("W,%" PRIu32 ",%" PRIu32 ",%" PRId32 ",%" PRId32 ",%" PRId32 ",%" PRIu32
           ",%" PRId32 ",%" PRId32 ",%u,%u,%016llx,%016llx,%016llx,%016llx,%" PRIu32 "\n",
           w->win_no, w->i_start, w->src_first, w->src_last, w->qrs_end, w->sample_dec,
           w->rr_min, w->rr_max, (unsigned)w->gate_ok, (unsigned)w->kelas,
           (unsigned long long)dbits(w->rmssd), (unsigned long long)dbits(w->ratio),
           (unsigned long long)dbits(w->pnn50), (unsigned long long)dbits(w->ent4), w->cycles);
}

static void cb_win(const afib_window_t *w, void *ctx)
{
    (void)ctx;
    cetak_jendela(w);
}

void afib_run_verif(const afib_plat_t *p, int arm)
{
    static const char *KOL[6] = {"masukan16", "lp", "hp", "turunan", "kuadrat", "jendela"};
    uint32_t kq = 0;
    uint64_t s1[6] = {0}, s2[6] = {0};
    kepala(p, "VERIF", arm);
    g_c.on_qrs = cb_qrs;
    g_c.on_window = cb_win;
    g_c.ctx = &kq;
    g_c.cycles = NULL;
    afib_init(&g_c, arm);
    uint64_t t0 = p->time_us();
    for (uint32_t i0 = 0; i0 < p->n; i0 += BLK) {
        uint32_t m = (p->n - i0 < BLK) ? p->n - i0 : BLK;
        memcpy(g_blk, p->stim + i0, m * sizeof(uint16_t));
        for (uint32_t j = 0; j < m; j++) {
            afib_cols_t cl;
            afib_step(&g_c, g_blk[j], &cl);
            uint64_t idx = (uint64_t)(i0 + j) + 1u;
            int64_t v[6] = {cl.masukan16, cl.lp, cl.hp, cl.turunan, cl.kuadrat, cl.jendela};
            for (int k = 0; k < 6; k++) {
                uint64_t u = (uint64_t)v[k];
                s1[k] += u;
                s2[k] += u * idx;
            }
        }
    }
    uint64_t t1 = p->time_us();
    for (int k = 0; k < 6; k++)
        printf("K,%s,%016llx,%016llx\n", KOL[k], (unsigned long long)s1[k], (unsigned long long)s2[k]);
    cetak_penghitung(&g_c);
    printf("V,us_total=%llu\n", (unsigned long long)(t1 - t0));
    printf("END,VERIF\n");
    g_c.on_qrs = NULL;
    g_c.on_window = NULL;
}

/* ------------------------------------------------------------------ PROF */
#define HBIN_SHIFT 4                    /* lebar bin 16 siklus */
#define HBINS 1024                      /* sampai 16384 siklus, sisanya masuk luapan */
static uint32_t g_hist[HBINS + 1];

typedef struct { uint64_t sum; uint32_t n, mx, mn; } stat_t;
static stat_t g_wstat;

static void cb_win_stat(const afib_window_t *w, void *ctx)
{
    (void)ctx;
    g_wstat.sum += w->cycles;
    g_wstat.n++;
    if (w->cycles > g_wstat.mx) g_wstat.mx = w->cycles;
    if (w->cycles < g_wstat.mn) g_wstat.mn = w->cycles;
}

static uint32_t persentil(uint64_t total, double q)
{
    uint64_t target = (uint64_t)(q * (double)total);
    uint64_t acc = 0;
    for (uint32_t b = 0; b <= HBINS; b++) {
        acc += g_hist[b];
        if (acc > target) return (b << HBIN_SHIFT) + (1u << HBIN_SHIFT) / 2;   /* tengah bin */
    }
    return HBINS << HBIN_SHIFT;
}

static uint32_t biaya_kurung(const afib_plat_t *p)
{
    uint32_t mn = 0xFFFFFFFFu;
    for (int i = 0; i < 1000; i++) {
        uint32_t a = p->cycles();
        uint32_t b = p->cycles();
        if (b - a < mn) mn = b - a;
    }
    return mn;
}

void afib_run_prof(const afib_plat_t *p, int arm, int reps)
{
    kepala(p, "PROF", arm);
    const uint32_t ovh = biaya_kurung(p);
    printf("T,ovh,kurung=%" PRIu32 "\n", ovh);

    /* A: total per sampel, rantai tanpa instrumen tahap */
    for (int r = 0; r < reps; r++) {
        memset(g_hist, 0, sizeof(g_hist));
        g_c.on_qrs = NULL; g_c.on_window = NULL; g_c.cycles = NULL;
        afib_init(&g_c, arm);
        uint64_t sum = 0;
        uint32_t mx = 0;
        uint64_t tw = 0;
        for (uint32_t i0 = 0; i0 < p->n; i0 += BLK) {
            uint32_t m = (p->n - i0 < BLK) ? p->n - i0 : BLK;
            memcpy(g_blk, p->stim + i0, m * sizeof(uint16_t));
            uint64_t ta = p->time_us();
            for (uint32_t j = 0; j < m; j++) {
                uint32_t t = p->cycles();
                afib_step(&g_c, g_blk[j], NULL);
                uint32_t dt = p->cycles() - t;
                dt = dt > ovh ? dt - ovh : 0;
                sum += dt;
                if (dt > mx) mx = dt;
                uint32_t b = dt >> HBIN_SHIFT;
                g_hist[b < HBINS ? b : HBINS]++;
            }
            tw += p->time_us() - ta;
        }
        printf("T,A,rep=%d,n=%" PRIu32 ",cyc_sum=%llu,cyc_mean=%.3f,p50=%" PRIu32 ",p90=%" PRIu32
               ",p99=%" PRIu32 ",p999=%" PRIu32 ",max=%" PRIu32 ",us_loop=%llu,jendela=%" PRIu32
               ",review=%" PRIu32 "\n",
               r, p->n, (unsigned long long)sum, (double)sum / (double)p->n,
               persentil(p->n, 0.50), persentil(p->n, 0.90), persentil(p->n, 0.99),
               persentil(p->n, 0.999), mx, (unsigned long long)tw, g_c.n_win, g_c.n_win_review);
        if (r == 0) {
            printf("H,bin=%d", 1 << HBIN_SHIFT);
            for (uint32_t b = 0; b <= HBINS; b++)
                if (g_hist[b]) printf(",%" PRIu32 ":%" PRIu32, b, g_hist[b]);
            printf("\n");
        }
    }

    /* B: rincian per tahap (instrumen menambah sedikit siklus, jadi totalnya tidak dipakai) */
    memset(&g_wstat, 0, sizeof(g_wstat));
    g_wstat.mn = 0xFFFFFFFFu;
    g_c.on_qrs = NULL; g_c.on_window = cb_win_stat; g_c.cycles = p->cycles;
    afib_init(&g_c, arm);
    memset(g_c.prof_cyc, 0, sizeof(g_c.prof_cyc));
    memset(g_c.prof_calls, 0, sizeof(g_c.prof_calls));
    for (uint32_t i0 = 0; i0 < p->n; i0 += BLK) {
        uint32_t m = (p->n - i0 < BLK) ? p->n - i0 : BLK;
        memcpy(g_blk, p->stim + i0, m * sizeof(uint16_t));
        for (uint32_t j = 0; j < m; j++) afib_step(&g_c, g_blk[j], NULL);
    }
    static const char *ST[AFIB_ST_N] = {"filter", "picker", "ambang_rr", "jendela"};
    for (int s = 0; s < AFIB_ST_N; s++)
        printf("T,B,tahap=%s,cyc=%llu,panggil=%" PRIu32 "\n", ST[s],
               (unsigned long long)g_c.prof_cyc[s], g_c.prof_calls[s]);
    printf("T,WIN,n=%" PRIu32 ",cyc_mean=%.1f,cyc_min=%" PRIu32 ",cyc_max=%" PRIu32 "\n",
           g_wstat.n, g_wstat.n ? (double)g_wstat.sum / g_wstat.n : 0.0,
           g_wstat.n ? g_wstat.mn : 0, g_wstat.mx);
    cetak_penghitung(&g_c);
    g_c.cycles = NULL;
    g_c.on_window = NULL;
    printf("END,PROF\n");
}

/* ------------------------------------------------------------------ POWER */
static void jalan_sekali(const afib_plat_t *p, int arm)
{
    afib_init(&g_c, arm);
    for (uint32_t i0 = 0; i0 < p->n; i0 += BLK) {
        uint32_t m = (p->n - i0 < BLK) ? p->n - i0 : BLK;
        memcpy(g_blk, p->stim + i0, m * sizeof(uint16_t));
        for (uint32_t j = 0; j < m; j++) afib_step(&g_c, g_blk[j], NULL);
    }
}

static void tanda(const afib_plat_t *p, int code) { if (p->marker) p->marker(code); }

static void jeda(const afib_plat_t *p, uint32_t ms)
{
    if (p->flush) p->flush();
    if (p->sleep_ms) p->sleep_ms(ms);
}

void afib_run_power(const afib_plat_t *p, int arm, int reps, int idle_s, int active_s)
{
    kepala(p, "POWER", arm);
    printf("PLAN,reps=%d,idle_s=%d,active_s=%d,urutan=idle-bench\n", reps, idle_s, active_s);
    g_c.on_qrs = NULL; g_c.on_window = NULL; g_c.cycles = NULL;
    jeda(p, 500);
    for (int r = 0; r < reps; r++) {
        /* fase idle: task tidur, idle task FreeRTOS menjalankan WAITI */
        tanda(p, MK_IDLE);
        uint64_t t0 = p->time_us();
        if (p->sleep_ms) p->sleep_ms((uint32_t)idle_s * 1000u);
        uint64_t t1 = p->time_us();
        tanda(p, MK_NONE);
        printf("PH,%d,idle,%llu,%llu,0,0,0,0\n", r, (unsigned long long)t0,
               (unsigned long long)(t1 - t0));
        jeda(p, 300);

        /* fase bench: rantai penuh diulang sampai minimal active_s detik */
        tanda(p, MK_BENCH);
        t0 = p->time_us();
        uint32_t loops = 0;
        do {
            jalan_sekali(p, arm);
            loops++;
        } while (p->time_us() - t0 < (uint64_t)active_s * 1000000ull);
        t1 = p->time_us();
        tanda(p, MK_NONE);
        printf("PH,%d,bench,%llu,%llu,%" PRIu32 ",%llu,%" PRIu32 ",%" PRIu32 "\n", r,
               (unsigned long long)t0, (unsigned long long)(t1 - t0), loops,
               (unsigned long long)loops * p->n, g_c.n_win, g_c.n_win_review);
        jeda(p, 300);
    }
    printf("END,POWER\n");
}
