/*
 * afib_chain.c -- port C rantai AFIB-LITE beku. Setiap blok menyebut baris rantai.py yang
 * diikutinya. Aturan pembulatan Python dipertahankan:
 *   a >> k  pada int Python bertanda = geser aritmetika, membulat ke minus tak hingga.
 *           gcc (x86 dan xtensa) menggeser int bertanda secara aritmetika, jadi sama.
 *   s // 8  dengan s negatif ditulis simetris tanda seperti rantai.py:228.
 */
#include "afib_chain.h"

#include <math.h>
#include <string.h>

#define PROF_BEGIN(c, t)  uint32_t t = (c)->cycles ? (c)->cycles() : 0u
#define PROF_END(c, st, t) do { if ((c)->cycles) { \
        (c)->prof_cyc[st] += (uint32_t)((c)->cycles() - (t)); (c)->prof_calls[st]++; } } while (0)

/* ===================================================================== tahap 0, kuantisasi */
/* rantai.kuantisasi (baris 156-170) lewat adapter.locked_word + Adapter.chain_value, yaitu
 * jalur tools/model_core.SumberKata. Dihitung sekali per hitungan 12 bit saat init, karena
 * hasilnya hanya fungsi dari hitungan; per sampel tinggal satu baca tabel. */
static const double GAIN_COUNT = 2047.0 / 5.0;    /* (2**11 - 1) / 5.0 */

static int32_t kuantisasi_mv(double mv)
{
    double v = rint(mv * GAIN_COUNT);              /* np.rint: bulat ke genap terdekat */
    if (v < -AFIB_CLAMP) v = -AFIB_CLAMP;
    if (v > AFIB_CLAMP) v = AFIB_CLAMP;
    return (int32_t)v * (1 << AFIB_GESER_KIRI);
}

static int32_t count_ke_masukan(int32_t count)
{
    /* locked_word: mv = (count - zero) / gain, gain 200, zero 0 */
    double mv = ((double)count - 0.0) / 200.0;
    int32_t value16 = kuantisasi_mv(mv);
    /* chain_value: (value16 >> 4) / GAIN_COUNT, lalu Rantai.langkah menguantisasi lagi */
    double nilai = (double)(value16 >> AFIB_GESER_KIRI) / GAIN_COUNT;
    return kuantisasi_mv(nilai);
}

/* ===================================================================== bantu */
static inline int32_t ring_get32(const int32_t *r, uint32_t akhir, int32_t idx)
{
    if (idx < 0 || (uint32_t)idx > akhir) return 0;
    return r[(uint32_t)idx & (AFIB_RING - 1)];
}

/* GarisTunda.maks (baris 132-135): nilai terbesar di [lo, hi], potong ke [0, akhir] */
static int64_t ring_maks64(const int64_t *r, uint32_t akhir, int32_t lo, int32_t hi)
{
    if (lo < 0) lo = 0;
    if (hi > (int32_t)akhir) hi = (int32_t)akhir;
    if (hi < lo) return 0;
    int64_t m = r[(uint32_t)lo & (AFIB_RING - 1)];
    for (int32_t i = lo + 1; i <= hi; i++) {
        int64_t v = r[(uint32_t)i & (AFIB_RING - 1)];
        if (v > m) m = v;
    }
    return m;
}

/* GarisTunda.maks_mutlak (baris 137-150) */
static int64_t ring_maks_mutlak32(const int32_t *r, uint32_t akhir, int32_t lo, int32_t hi)
{
    if (lo < 0) lo = 0;
    if (hi > (int32_t)akhir) hi = (int32_t)akhir;
    if (hi < lo) return 0;
    int64_t m = 0;
    for (int32_t i = lo; i <= hi; i++) {
        int64_t v = r[(uint32_t)i & (AFIB_RING - 1)];
        if (v < 0) v = -v;
        if (v > m) m = v;
    }
    return m;
}

static void sisip_urut32(int32_t *v, int n)
{
    for (int i = 1; i < n; i++) {
        int32_t x = v[i];
        int j = i - 1;
        while (j >= 0 && v[j] > x) { v[j + 1] = v[j]; j--; }
        v[j + 1] = x;
    }
}

/* median_bulat (baris 364-372) */
static int32_t median_bulat(const int32_t *nilai, int m)
{
    if (m == 0) return 0;
    int32_t v[AFIB_SEMAI_PANJANG];
    memcpy(v, nilai, (size_t)m * sizeof(int32_t));
    sisip_urut32(v, m);
    if (m % 2) return v[m / 2];
    return (v[m / 2 - 1] + v[m / 2]) / 2;      /* keduanya positif: // sama dengan / */
}

static void dorong_batas(int32_t *buf, int *n, int cap, int32_t x)
{
    if (*n < cap) { buf[(*n)++] = x; return; }
    memmove(buf, buf + 1, (size_t)(cap - 1) * sizeof(int32_t));
    buf[cap - 1] = x;
}

static int64_t jumlah32(const int32_t *v, int n)
{
    int64_t s = 0;
    for (int i = 0; i < n; i++) s += v[i];
    return s;
}

/* ===================================================================== init */
void afib_init(afib_chain_t *c, int arm)
{
    afib_window_cb_t ow = c->on_window;
    afib_qrs_cb_t oq = c->on_qrs;
    void *ctx = c->ctx;
    afib_cycles_fn_t cy = c->cycles;
    memset(c, 0, sizeof(*c));
    c->on_window = ow; c->on_qrs = oq; c->ctx = ctx; c->cycles = cy;
    c->arm = arm;
    for (int k = 0; k < 4096; k++) {
        int32_t count = (k >= 2048) ? k - 4096 : k;
        c->lut_masukan[k] = (int16_t)count_ke_masukan(count);
    }
    c->scan = AFIB_RADIUS_PUNCAK;
    c->rr_jeda = AFIB_SEMAI_JEDA;
    c->qrs_last = -1;
}

/* ===================================================================== tahap 7, rr() */
/* _dalam_batas (baris 359-361) */
static inline bool dalam_batas(int64_t x, int64_t pembilang, int64_t penyebut)
{
    return (25 * penyebut * x >= 23 * pembilang) && (25 * penyebut * x <= 29 * pembilang);
}

static void tahap_rr(afib_chain_t *c, int32_t x)       /* baris 375-438 */
{
    dorong_batas(c->rr_deret, &c->rr_deret_n, AFIB_DELAPAN, x);
    dorong_batas(c->rr_riwayat, &c->rr_riwayat_n, AFIB_SEMAI_PANJANG, x);
    if (c->rr_deret_n < AFIB_DELAPAN) return;
    int64_t ra1 = jumlah32(c->rr_deret, c->rr_deret_n) >> 3;
    int64_t pembilang = jumlah32(c->rr_antre, c->rr_antre_n);
    int64_t penyebut = c->rr_antre_n;
    int64_t acuan, acuan_penyebut;
    if (penyebut > 0) { acuan = pembilang; acuan_penyebut = penyebut; }
    else              { acuan = ra1;       acuan_penyebut = 1; }
    bool lolos = dalam_batas(x, acuan, acuan_penyebut);
    if (lolos) c->rr_gagal = 0; else c->rr_gagal++;
    c->rr_jeda++;
    if (c->rr_gagal >= AFIB_DELAPAN && c->rr_jeda >= AFIB_SEMAI_JEDA) {   /* semai_aktif */
        int32_t tengah = median_bulat(c->rr_riwayat, c->rr_riwayat_n);
        for (int i = 0; i < AFIB_DELAPAN; i++) c->rr_antre[i] = tengah;
        c->rr_antre_n = AFIB_DELAPAN;
        c->rr_semai++;
        c->rr_gagal = 0;
        c->rr_jeda = 0;
    } else if (lolos) {
        dorong_batas(c->rr_antre, &c->rr_antre_n, AFIB_DELAPAN, x);
    }
    pembilang = jumlah32(c->rr_antre, c->rr_antre_n);
    penyebut = c->rr_antre_n;
    int64_t ra2 = penyebut > 0 ? pembilang / penyebut : ra1;    /* positif: // sama dengan / */
    c->rr_ra1 = ra1; c->rr_ra2 = ra2;
    c->rr_pembilang = pembilang; c->rr_penyebut = penyebut;
    int menyala = 0;
    if (penyebut == AFIB_DELAPAN) {
        menyala = 1;
        for (int i = 0; i < c->rr_deret_n; i++)
            if (!dalam_batas(c->rr_deret[i], pembilang, penyebut)) { menyala = 0; break; }
    }
    c->rr_menyala = menyala;
    c->penanda += (uint32_t)menyala;
    c->langkah++;
}

/* ===================================================================== tahap 7b, rr_rhythm */
static int rr_rhythm(afib_chain_t *c, int32_t x)       /* baris 519-566 */
{
    c->ir_raw++;
    int32_t reference = median_bulat(c->ir_hist, c->ir_hist_n);
    if (reference > 0 && (2 * (int64_t)x) < reference) { c->ir_dropped++; return AFIB_MARK_DROP; }
    if (reference > 0 && ((int64_t)AFIB_RR_MISS_DEN * x) > ((int64_t)AFIB_RR_MISS_NUM * reference)) {
        if (x > AFIB_RR_GAP_CEILING) { c->ir_gap++; return AFIB_MARK_GAP; }
        int32_t first = x >> 1;
        int32_t second = x - first;
        dorong_batas(c->ir_hist, &c->ir_hist_n, AFIB_DELAPAN, first);
        dorong_batas(c->ir_hist, &c->ir_hist_n, AFIB_DELAPAN, second);
        c->ir_split++;
        return AFIB_MARK_SPLIT;
    }
    dorong_batas(c->ir_hist, &c->ir_hist_n, AFIB_DELAPAN, x);
    c->ir_kept++;
    return AFIB_MARK_KEEP;
}

/* ===================================================================== lapisan jendela */
/* numpy add.reduce atas larik float64 kontigu: nilai awal identitas 0.0, lalu pairwise_sum
 * atas seluruh n elemen (n < 8 berurutan, 8..128 delapan akumulator). Urutan ini dicek
 * cocok 100% terhadap np.sum di numpy 2.2.6 dan 2.5.3 atas 300.000 larik acak. */
static double np_sum(const double *b, int m)
{
    double s;
    if (m < 8) {
        s = 0.0;
        for (int i = 0; i < m; i++) s += b[i];
        return 0.0 + s;
    }
    double r[8];
    for (int j = 0; j < 8; j++) r[j] = b[j];
    int i;
    for (i = 8; i < m - (m % 8); i += 8)
        for (int j = 0; j < 8; j++) r[j] += b[i + j];
    s = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
    for (; i < m; i++) s += b[i];
    return 0.0 + s;
}

/* rantai.fitur_irama (baris 848-861) */
void afib_fitur(const int32_t rr_in[AFIB_JENDELA_DENYUT], double *rmssd_o, double *ratio_o,
                double *pnn50_o, double *ent4_o)
{
    const int N = AFIB_JENDELA_DENYUT;
    double rr[AFIB_JENDELA_DENYUT];
    for (int i = 0; i < N; i++) rr[i] = (double)rr_in[i];

    double d2[AFIB_JENDELA_DENYUT - 1];
    double big[AFIB_JENDELA_DENYUT - 1];
    for (int i = 0; i < N - 1; i++) {
        double d = rr[i + 1] - rr[i];
        d2[i] = d * d;
        big[i] = (fabs(d) > 50.0) ? 1.0 : 0.0;
    }
    /* semua suku bilangan bulat < 2**53, jadi jumlahnya eksak dalam urutan apa pun */
    double rmssd = sqrt(np_sum(d2, N - 1) / (double)(N - 1));
    double pnn50 = np_sum(big, N - 1) / (double)(N - 1);
    double mean = np_sum(rr, N) / (double)N;

    int32_t s[AFIB_JENDELA_DENYUT];
    memcpy(s, rr_in, sizeof(s));
    sisip_urut32(s, N);
    const int32_t *core = s + 8;                /* s[8:-8], 16 nilai (size 32 > 20) */
    const int NC = N - 16;
    double lo = (double)core[0], hi = (double)core[NC - 1];
    /* np.linspace(lo, hi, 17): y = k * step + lo, step = (hi - lo) / 16, ujung = hi */
    double edges[17];
    double delta = hi - lo;
    double step = delta / 16.0;
    for (int k = 0; k < 17; k++) {
        if (step == 0.0) edges[k] = ((double)k / 16.0) * delta + lo;
        else             edges[k] = (double)k * step + lo;
    }
    edges[16] = hi;
    edges[16] += 1e-9;
    /* np.histogram dengan tepi larik: bin k = [e_k, e_k+1), bin terakhir tertutup */
    int cnt[16] = {0};
    for (int i = 0; i < NC; i++) {
        double v = (double)core[i];
        for (int k = 0; k < 16; k++) {
            bool masuk = (k < 15) ? (v >= edges[k] && v < edges[k + 1])
                                  : (v >= edges[k] && v <= edges[k + 1]);
            if (masuk) { cnt[k]++; break; }
        }
    }
    int total = 0;
    for (int k = 0; k < 16; k++) total += cnt[k];
    /* Inti selalu 16 nilai, jadi p = c/16 dan hanya 16 suku p*log2(p) yang mungkin. Suku itu
     * diambil dari numpy (identik di numpy 2.2.6 dan 2.5.3), karena log2 newlib di ESP32
     * berbeda 1 ulp dari log2 glibc pada beberapa nilai. Dengan tabel ini entropi ESP32
     * identik bit dengan model; tanpa tabel bedanya sekitar 1e-16 dan kelas tidak berubah. */
    static const double SUKU16[17] = {
        0.0,
        -0x1.0000000000000p-2, -0x1.8000000000000p-2, -0x1.cfafec54831f2p-2, -0x1.0000000000000p-1,
        -0x1.0c7dd3427f3b2p-1, -0x1.0fafec54831f2p-1, -0x1.0b270a12cf8b1p-1, -0x1.0000000000000p-1,
        -0x1.de1f89fb12baap-2, -0x1.b1f74d09fcecap-2, -0x1.7c8f655dcff16p-2, -0x1.3ebfb1520c7c6p-2,
        -0x1.f277e31978369p-3, -0x1.593850967c58cp-3, -0x1.658a44d62bf97p-4, 0x0.0p+0,
    };
    double terms[16];
    int m = 0;
    for (int k = 0; k < 16; k++) {
        if (cnt[k] > 0) {
            if (total == 16) {
                terms[m++] = SUKU16[cnt[k]];
            } else {
                double p = (double)cnt[k] / (double)total;
                terms[m++] = p * log2(p);
            }
        }
    }
    double h = -np_sum(terms, m);
    *rmssd_o = rmssd;
    *ratio_o = rmssd / mean;
    *pnn50_o = pnn50;
    *ent4_o = h / 4.0;
}

/* satu interval baru di seri terpilih; keluarkan jendela bila langkahnya jatuh di sini.
 * kumpulkan_jendela (baris 799-826): for i in range(0, size - 32, 4) berarti jendela i
 * sudah pasti ada begitu seri mencapai panjang i + 33, jadi keputusannya keluar saat entri
 * ke-(i+33) datang, dengan isi entri i .. i+31. */
static void jendela_masuk(afib_chain_t *c, int32_t rr_ms, int32_t src, int32_t qrs)
{
    const uint32_t W = AFIB_JENDELA_DENYUT, R = AFIB_JENDELA_DENYUT + 1;
    uint32_t k = c->sel_n;                  /* indeks entri baru */
    c->sel_rr[k % R] = rr_ms;
    c->sel_src[k % R] = src;
    c->sel_qrs[k % R] = qrs;
    c->sel_n = k + 1;
    if (k < W) return;
    uint32_t i0 = k - W;
    if (i0 % AFIB_LANGKAH_DENYUT) return;

    PROF_BEGIN(c, t0);
    afib_window_t w;
    memset(&w, 0, sizeof(w));
    int32_t seg[AFIB_JENDELA_DENYUT];
    int32_t mn = 0x7fffffff, mx = -0x7fffffff;
    for (uint32_t j = 0; j < W; j++) {
        int32_t v = c->sel_rr[(i0 + j) % R];
        seg[j] = v;
        if (v < mn) mn = v;
        if (v > mx) mx = v;
    }
    w.win_no = i0 / AFIB_LANGKAH_DENYUT;
    w.i_start = i0;
    w.src_first = c->sel_src[i0 % R];
    w.src_last = c->sel_src[(i0 + W - 1) % R];
    w.qrs_end = c->sel_qrs[(i0 + W - 1) % R];
    w.sample_dec = c->n;
    w.rr_min = mn; w.rr_max = mx;
    w.gate_ok = !(mn < 200 || mx > 3000);
    if (w.gate_ok) {
        afib_fitur(seg, &w.rmssd, &w.ratio, &w.pnn50, &w.ent4);
        /* nilai_gerbang (baris 872-878): p = (ratio > t1) & (entropy > t2) */
        w.kelas = (w.ratio > AFIB_T1 && w.ent4 > AFIB_T2) ? AFIB_KELAS_REVIEW : AFIB_KELAS_NORMAL;
    } else {
        w.kelas = AFIB_KELAS_UNDECIDED;     /* model membuang jendela ini, tidak memutuskan */
    }
    c->n_win++;
    if (w.kelas == AFIB_KELAS_REVIEW) c->n_win_review++;
    else if (w.kelas == AFIB_KELAS_NORMAL) c->n_win_normal++;
    else c->n_win_undecided++;
    if (c->cycles) w.cycles = (uint32_t)(c->cycles() - t0);
    PROF_END(c, AFIB_ST_WINDOW, t0);
    if (c->on_window) c->on_window(&w, c->ctx);
}

/* _catat (baris 624-642) */
static void catat(afib_chain_t *c, int32_t pos, uint32_t i_puncak)
{
    int32_t prev = c->qrs_last;
    c->n_qrs++;
    c->qrs_last = pos;
    c->has_qrs = true;
    c->i_qrs = pos;
    c->i_qrs_puncak = (int32_t)i_puncak;
    if (prev < 0) {
        if (c->on_qrs) c->on_qrs(pos, -1, -1, c->ctx);
        return;
    }
    int32_t rr_ms = (pos - prev) << 2;
    int32_t src = (int32_t)c->n_rr;
    c->n_rr++;
    int mark = rr_rhythm(c, rr_ms);
    if (rr_ms >= 250 && rr_ms <= 2000) tahap_rr(c, rr_ms);
    if (c->on_qrs) c->on_qrs(pos, rr_ms, mark, c->ctx);
    /* seri jendela: mentah memakai semua interval, berpenanda membuang DROP dan GAP
     * (seri_berpenanda, baris 764-783). Nilai yang dipakai selalu interval mentahnya. */
    if (c->arm == AFIB_ARM_MENTAH || mark == AFIB_MARK_KEEP || mark == AFIB_MARK_SPLIT)
        jendela_masuk(c, rr_ms, src, pos);
}

/* search_back (baris 569-603). Mengembalikan indeks puncak kandidat, atau -1. */
static int64_t search_back(afib_chain_t *c, int32_t pos, uint32_t i_puncak, int64_t i1, int64_t i2)
{
    if (!c->has_qrs) return -1;
    int64_t delta = (int64_t)pos - c->i_qrs;
    bool aktif;
    if (c->rr_penyebut > 0)  aktif = 200 * delta * c->rr_penyebut > 83 * c->rr_pembilang;
    else if (c->rr_ra1 > 0)  aktif = 200 * delta > 83 * c->rr_ra1;
    else                     aktif = false;
    if (!aktif) return -1;
    int64_t best = -1;
    int64_t best_v = 0;
    uint32_t a = (uint32_t)(c->i_qrs_puncak + 1);
    if (i_puncak - a + 1 > c->pk_span_max) c->pk_span_max = i_puncak - a + 1;
    if (i_puncak - a + 1 > AFIB_PK_RING) {            /* tidak pernah terjadi pada 04015 */
        c->pk_overflow++;
        a = i_puncak + 1 - AFIB_PK_RING;
    }
    for (uint32_t j = a; j <= i_puncak; j++) {
        int64_t v = c->pk_val[j & (AFIB_PK_RING - 1)];
        if (i2 < v && v <= i1 && (best < 0 || v > best_v)) { best = j; best_v = v; }
    }
    return best;
}

/* ambang (baris 645-751) */
static void ambang(afib_chain_t *c, int32_t pos, uint32_t i_puncak, int64_t pv, int64_t pk_f)
{
    int64_t spki = c->spki, npki = c->npki, spkf = c->spkf, npkf = c->npkf;
    int64_t i1 = npki + ((spki - npki) >> 2);
    int64_t f1 = npkf + ((spkf - npkf) >> 2);
    int64_t i2 = i1 >> 1;
    bool sinyal = pv > i1;
    bool ada_delta = c->has_qrs;
    int64_t delta = ada_delta ? (int64_t)pos - c->i_qrs : 0;
    if (sinyal && ada_delta && delta < AFIB_PANTUL) sinyal = false;
    c->pk_f[i_puncak & (AFIB_PK_RING - 1)] = pk_f;

    /* gelombang_t (baris 318-341), besaran "turunan" */
    int32_t lo = pos - AFIB_SETENGAH_JENDELA;
    if (lo < 0) lo = 0;
    int64_t kem = ring_maks_mutlak32(c->ring_tur, c->n, lo, pos + AFIB_SETENGAH_JENDELA);
    bool dalam_pita = ada_delta && c->has_kem_qrs && ((delta << 2) < AFIB_BATAS_PITA);
    bool ditolak_t = dalam_pita && (2 * kem < c->kem_qrs);
    c->pk_kem[i_puncak & (AFIB_PK_RING - 1)] = kem;

    if (sinyal && dalam_pita) {
        c->diperiksa++;
        if (ditolak_t) { sinyal = false; c->ditolak++; }
        else c->diterima_pita++;
    }
    if (!sinyal && pv > i2) c->calon_kedua++;
    if (sinyal) {
        c->spki = spki + ((pv - spki) >> 3);
        if (pk_f > f1) c->spkf = spkf + ((pk_f - spkf) >> 3);
        else           c->npkf = npkf + ((pk_f - npkf) >> 3);
        if (ada_delta && c->has_kem_qrs && ((delta << 2) < AFIB_BATAS_PITA)) {
            if (c->kem_qrs > 0 && (2 * kem < c->kem_qrs)) c->berisiko++;
        }
        c->kem_qrs = kem; c->has_kem_qrs = true;
        catat(c, pos, i_puncak);
        return;
    }
    c->npki = npki + ((pv - npki) >> 3);
    c->npkf = npkf + ((pk_f - npkf) >> 3);
    int64_t j = search_back(c, pos, i_puncak, i1, i2);
    if (j >= 0) {
        uint32_t jj = (uint32_t)j & (AFIB_PK_RING - 1);
        int64_t v = c->pk_val[jj], vf = c->pk_f[jj], vk = c->pk_kem[jj];
        c->cari_mundur++;
        if (vf > f1) c->spkf = spkf + ((vf - spkf) >> 2);
        else         c->npkf = c->npkf + ((vf - c->npkf) >> 2);
        c->spki = spki + ((v - spki) >> 2);
        c->kem_qrs = vk; c->has_kem_qrs = true;
        catat(c, c->pk_pos[jj], (uint32_t)j);
    }
}

/* ===================================================================== satu sampel */
void afib_step(afib_chain_t *c, uint16_t kata, afib_cols_t *cols)
{
    PROF_BEGIN(c, t0);
    const uint32_t n = c->n;
    /* tahap 0 */
    int32_t masukan = c->lut_masukan[kata & 0xFFFu];

    /* tahap 1, tapis_lp (baris 173-192): y = 2 y1 - y2 + x - 2 x[-6] + x[-12] */
    int xi = c->lp_xi;
    c->lp_x[xi] = masukan;
    int32_t x6 = c->lp_x[(xi + 13 - 6) % 13];
    int32_t x12 = c->lp_x[(xi + 1) % 13];        /* (xi - 12) mod 13 */
    int32_t lp = 2 * c->lp_y1 - c->lp_y2 + masukan - 2 * x6 + x12;
    c->lp_y2 = c->lp_y1; c->lp_y1 = lp;
    c->lp_xi = (xi + 1) % 13;

    /* tahap 2, tapis_hp (baris 197-216): y = 32 x[i-16] - (y1 + x[i] - x[i-32]) */
    int32_t *hx = c->hp_x;
    hx[n % 33] = lp;
    int32_t h16 = (n >= 16) ? hx[(n - 16) % 33] : 0;
    int32_t h32 = (n >= 32) ? hx[(n - 32) % 33] : 0;
    int32_t hp = 32 * h16 - (c->hp_y1 + lp - h32);
    c->hp_y1 = hp;

    /* tahap 3, turunan (baris 221-235) */
    int32_t *tx = c->tur_x;
    tx[n % 5] = hp;
    int32_t t1 = (n >= 1) ? tx[(n - 1) % 5] : 0;
    int32_t t3 = (n >= 3) ? tx[(n - 3) % 5] : 0;
    int32_t t4 = (n >= 4) ? tx[(n - 4) % 5] : 0;
    int64_t s = 2 * (int64_t)hp + t1 - t3 - 2 * (int64_t)t4;
    int32_t tur = (int32_t)(s >= 0 ? s / 8 : -((-s) / 8));

    /* tahap 4, kuadrat (baris 240-254): geser dulu, lalu kuadrat */
    int64_t d = (int64_t)(tur >> AFIB_GESER_AMBANG);
    int64_t ku = d * d;

    /* tahap 5, jendela (baris 259-284) */
    int64_t *mx = c->mwi_x;
    mx[n % 39] = ku;
    c->mwi_sum += ku;
    if (n >= AFIB_N_B) c->mwi_sum -= mx[(n - AFIB_N_B) % 39];
    int64_t sel = c->mwi_sum;
    if ((n % 2) == 0 && n >= AFIB_N_A) sel -= mx[(n - AFIB_N_A) % 39];

    c->ring_hp[n & (AFIB_RING - 1)] = hp;
    c->ring_tur[n & (AFIB_RING - 1)] = tur;
    c->ring_sel[n & (AFIB_RING - 1)] = sel;
    if (cols) {
        cols->masukan16 = masukan; cols->lp = lp; cols->hp = hp; cols->turunan = tur;
        cols->kuadrat = ku; cols->jendela = sel;
    }
    PROF_END(c, AFIB_ST_FILTER, t0);

    /* pemilih puncak selubung (Rantai.langkah baris 983-995), tunda tetap RADIUS_PUNCAK */
    PROF_BEGIN(c, t1p);
    uint32_t scan = c->scan;
    while (scan + AFIB_RADIUS_PUNCAK <= n) {
        int64_t v = c->ring_sel[scan & (AFIB_RING - 1)];
        if (v > 0 && v >= ring_maks64(c->ring_sel, n, (int32_t)scan - AFIB_RADIUS_PUNCAK,
                                      (int32_t)(scan + AFIB_RADIUS_PUNCAK))) {
            uint32_t pos = scan;
            scan += AFIB_RADIUS_PUNCAK;
            c->scan = scan;
            PROF_END(c, AFIB_ST_PICKER, t1p);

            /* satu puncak ke tahap ambang (baris 997-1008) */
            PROF_BEGIN(c, t2);
            uint32_t ip = c->n_puncak++;
            int64_t pv = c->ring_sel[pos & (AFIB_RING - 1)];
            int64_t pkf = ring_maks_mutlak32(c->ring_hp, n, (int32_t)pos - AFIB_JENDELA_F,
                                             (int32_t)pos + AFIB_JENDELA_F);
            c->pk_pos[ip & (AFIB_PK_RING - 1)] = (int32_t)pos;
            c->pk_val[ip & (AFIB_PK_RING - 1)] = pv;
            ambang(c, (int32_t)pos, ip, pv, pkf);
            PROF_END(c, AFIB_ST_THRESH, t2);
            t1p = c->cycles ? c->cycles() : 0u;
        } else {
            scan += 1;
        }
    }
    c->scan = scan;
    PROF_END(c, AFIB_ST_PICKER, t1p);
    c->n = n + 1;
}
