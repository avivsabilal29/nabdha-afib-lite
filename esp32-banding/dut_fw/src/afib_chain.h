/*
 * afib_chain.h -- port C rantai AFIB-LITE beku (model/rantai-afib-lite/rantai.py)
 *
 * Satu objek state, satu titik masuk per sampel, sama seperti kelas Rantai di Python:
 *
 *     afib_init(&c, AFIB_ARM_BERPENANDA);
 *     for (i = 0; i < n; i++) afib_step(&c, kata[i], NULL);
 *
 * Kata masukan = kata stimulus 15 bit testbench RTL (rtl/tb/vektor/04015.stimulus.hex):
 * kata[11:0] hitungan ADC 12 bit bertanda, kata[14:12] nibble penanda. Model Python
 * (tools/model_core.py, SumberKata) hanya memakai hitungannya, jadi port ini juga begitu.
 *
 * Bagian integer (tahap 0 sampai 7b) identik bit-per-bit dengan rantai.py. Lapisan jendela
 * memakai double seperti rantai.fitur_irama, dengan urutan penjumlahan yang sama dengan numpy,
 * lalu gerbang ambang terkunci T1 0.165 dan T2 0.63 (uji_10_berpenanda.py baris 158-159).
 *
 * Kode ini tidak memanggil malloc dan tidak bergantung pada ESP-IDF, jadi berkas yang sama
 * dikompilasi untuk ESP32 dan untuk uji PC (host_test/host_run.c).
 */
#ifndef AFIB_CHAIN_H
#define AFIB_CHAIN_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- konstanta beku, rantai.py baris 48-68 ---- */
#define AFIB_FS_HZ            250
#define AFIB_CLAMP            2047
#define AFIB_GESER_KIRI       4
#define AFIB_N_A              37
#define AFIB_N_B              38
#define AFIB_RADIUS_PUNCAK    27
#define AFIB_JENDELA_F        25
#define AFIB_PANTUL           50
#define AFIB_BATAS_PITA       360
#define AFIB_SETENGAH_JENDELA 18
#define AFIB_GESER_AMBANG     8
#define AFIB_DELAPAN          8
#define AFIB_SEMAI_PANJANG    32
#define AFIB_SEMAI_JEDA       8
#define AFIB_RR_GAP_CEILING   3000
#define AFIB_RR_MISS_NUM      83
#define AFIB_RR_MISS_DEN      50
#define AFIB_JENDELA_DENYUT   32
#define AFIB_LANGKAH_DENYUT   4
#define AFIB_T1               0.165
#define AFIB_T2               0.63

#define AFIB_RING             64      /* garis tunda hp, turunan, jendela (rantai.py:927-929) */
#define AFIB_PK_RING          512     /* puncak sejak QRS terakhir untuk search back; 04015 butuh 127 */

enum { AFIB_MARK_KEEP = 0, AFIB_MARK_SPLIT = 1, AFIB_MARK_DROP = 2, AFIB_MARK_GAP = 3 };
enum { AFIB_ARM_MENTAH = 0, AFIB_ARM_BERPENANDA = 1 };
enum { AFIB_KELAS_UNDECIDED = 0, AFIB_KELAS_NORMAL = 1, AFIB_KELAS_REVIEW = 2 };

/* tahap untuk profil siklus */
enum { AFIB_ST_FILTER = 0,   /* kuantisasi + LP + HP + turunan + kuadrat + MWI + garis tunda */
       AFIB_ST_PICKER,       /* pemilih puncak selubung (per sampel) */
       AFIB_ST_THRESH,       /* ambang adaptif + gelombang T + search back + RR + irama */
       AFIB_ST_WINDOW,       /* fitur jendela + gerbang kelas */
       AFIB_ST_N };

/* satu keputusan jendela */
typedef struct {
    uint32_t win_no;        /* posisi langkah ke berapa (0,1,2,...) di seri terpilih */
    uint32_t i_start;       /* indeks awal jendela di seri terpilih (= 4 * win_no) */
    int32_t  src_first;     /* indeks interval mentah dari entri pertama jendela */
    int32_t  src_last;      /* indeks interval mentah dari entri terakhir jendela */
    int32_t  qrs_end;       /* sampel QRS penutup interval terakhir jendela */
    uint32_t sample_dec;    /* indeks sampel saat keputusan keluar */
    int32_t  rr_min, rr_max;
    uint8_t  gate_ok;       /* 1 bila 200 <= rr <= 3000 di seluruh jendela */
    uint8_t  kelas;         /* 0 undecided (gerbang rentang gagal), 1 normal, 2 review AF */
    double   rmssd, ratio, pnn50, ent4;
    uint32_t cycles;        /* siklus hitung jendela ini (hanya bila profil aktif) */
} afib_window_t;

typedef void (*afib_window_cb_t)(const afib_window_t *w, void *ctx);
typedef void (*afib_qrs_cb_t)(int32_t pos, int32_t rr_ms, int mark, void *ctx);
typedef uint32_t (*afib_cycles_fn_t)(void);

/* enam kolom per sampel, untuk pemeriksaan bit-exact */
typedef struct {
    int32_t masukan16, lp, hp, turunan;
    int64_t kuadrat, jendela;
} afib_cols_t;

typedef struct {
    /* ---- konfigurasi ---- */
    int arm;
    afib_window_cb_t on_window;
    afib_qrs_cb_t    on_qrs;
    void            *ctx;
    afib_cycles_fn_t cycles;          /* NULL = profil mati */
    uint64_t         prof_cyc[AFIB_ST_N];
    uint32_t         prof_calls[AFIB_ST_N];

    /* ---- tahap sampel ---- */
    uint32_t n;                       /* indeks sampel berikutnya */
    int16_t  lut_masukan[4096];       /* hitungan 12 bit -> masukan16 (kuantisasi beku) */
    int32_t  lp_x[13]; int lp_xi;     /* x[i-12..i], cincin */
    int32_t  lp_y1, lp_y2;
    int32_t  hp_x[33];                /* garis tunda 33 */
    int32_t  hp_y1;
    int32_t  tur_x[5];
    int64_t  mwi_x[39];
    int64_t  mwi_sum;

    int32_t  ring_hp[AFIB_RING];
    int32_t  ring_tur[AFIB_RING];
    int64_t  ring_sel[AFIB_RING];
    uint32_t scan;

    /* ---- ambang (rantai.ambang_awal) ---- */
    int64_t spki, npki, spkf, npkf;
    bool    has_qrs, has_kem_qrs;
    int32_t i_qrs, i_qrs_puncak;
    int64_t kem_qrs;
    uint32_t n_puncak;                /* jumlah puncak selubung sejauh ini */
    int32_t pk_pos[AFIB_PK_RING];
    int64_t pk_val[AFIB_PK_RING];
    int64_t pk_f[AFIB_PK_RING];
    int64_t pk_kem[AFIB_PK_RING];
    uint32_t pk_overflow;
    uint32_t pk_span_max;             /* puncak terbanyak yang pernah ditelusuri search back */

    /* penghitung, rantai.ambang_awal */
    uint32_t calon_kedua, cari_mundur, diperiksa, ditolak, diterima_pita, berisiko,
             penanda, langkah;
    uint32_t n_qrs, n_rr;
    int32_t  qrs_last;

    /* ---- tahap RR (rantai.rr) ---- */
    int32_t rr_deret[AFIB_DELAPAN]; int rr_deret_n;
    int32_t rr_riwayat[AFIB_SEMAI_PANJANG]; int rr_riwayat_n;
    int32_t rr_antre[AFIB_DELAPAN]; int rr_antre_n;
    int32_t rr_gagal, rr_jeda, rr_semai, rr_menyala;
    int64_t rr_ra1, rr_ra2, rr_pembilang, rr_penyebut;

    /* ---- irama 7b (rantai.rr_rhythm) ---- */
    int32_t ir_hist[AFIB_DELAPAN]; int ir_hist_n;
    uint32_t ir_raw, ir_kept, ir_split, ir_dropped, ir_gap;

    /* ---- jendela ---- */
    int32_t  sel_rr[AFIB_JENDELA_DENYUT + 1];   /* cincin 33 entri seri terpilih */
    int32_t  sel_src[AFIB_JENDELA_DENYUT + 1];
    int32_t  sel_qrs[AFIB_JENDELA_DENYUT + 1];
    uint32_t sel_n;                             /* panjang seri terpilih sejauh ini */
    uint32_t n_win, n_win_review, n_win_normal, n_win_undecided;
} afib_chain_t;

void afib_init(afib_chain_t *c, int arm);
/* satu sampel masuk; cols boleh NULL */
void afib_step(afib_chain_t *c, uint16_t kata, afib_cols_t *cols);
/* fitur satu jendela 32 interval, persis rantai.fitur_irama */
void afib_fitur(const int32_t rr[AFIB_JENDELA_DENYUT], double *rmssd, double *ratio,
                double *pnn50, double *ent4);

#ifdef __cplusplus
}
#endif
#endif
