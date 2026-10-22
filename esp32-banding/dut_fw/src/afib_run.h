/*
 * afib_run.h -- mode uji yang sama untuk ESP32 dan PC.
 *
 * Semua keluaran adalah baris teks berawalan tag, dibaca oleh tools/banding_esp32.py:
 *
 *   #AFIB,...            kepala run (sumber, rekaman, frekuensi CPU, sha256 stimulus)
 *   Q,k,pos,rr,mark      satu QRS (rr = -1 untuk QRS pertama)
 *   W,...                satu keputusan jendela, fitur sebagai bit double heksadesimal
 *   K,kolom,s1,s2        sidik jari kolom per sampel (sum v, sum (i+1) v, mod 2**64)
 *   C,kunci=nilai,...    penghitung rantai
 *   T,...                hasil pengukuran waktu (PROF)
 *   PH,...               satu fase pengukuran daya
 *   END,mode             mode selesai
 */
#ifndef AFIB_RUN_H
#define AFIB_RUN_H

#include <stdint.h>
#include "afib_chain.h"

#ifdef __cplusplus
extern "C" {
#endif

/* kode pin penanda (M1 M0): 0 transisi, 1 bench aktif, 2 idle, 3 realtime */
enum { MK_NONE = 0, MK_BENCH = 1, MK_IDLE = 2, MK_RT = 3 };

typedef struct {
    const uint16_t *stim;          /* kata stimulus (di ESP32: langsung dari flash) */
    uint32_t n;                    /* jumlah kata */
    const char *rec;               /* nama rekaman */
    const char *src;               /* "esp32" atau "host" */
    const char *stim_sha;          /* sha256 heksadesimal stimulus, atau "na" */
    uint32_t fcpu_mhz;             /* frekuensi CPU saat run, 0 bila tidak diketahui */
    uint32_t (*cycles)(void);      /* pencacah siklus CPU 32 bit */
    uint64_t (*time_us)(void);     /* jam mikrodetik */
    void (*marker)(int code);      /* pin penanda, boleh NULL */
    void (*sleep_ms)(uint32_t ms); /* tidur (idle task), boleh NULL */
    void (*flush)(void);           /* kosongkan keluaran sebelum fase ukur, boleh NULL */
} afib_plat_t;

/* objek rantai bersama (dipakai juga oleh mode RT di main.c) */
afib_chain_t *afib_run_chain(void);

/* run penuh, cetak semua QRS, jendela, sidik jari kolom (pemeriksaan kebenaran) */
void afib_run_verif(const afib_plat_t *p, int arm);
/* pengukuran waktu: total per sampel (tanpa instrumen tahap) lalu rincian per tahap */
void afib_run_prof(const afib_plat_t *p, int arm, int reps);
/* urutan daya: reps x (idle idle_s detik, lalu bench minimal active_s detik) */
void afib_run_power(const afib_plat_t *p, int arm, int reps, int idle_s, int active_s);

#ifdef __cplusplus
}
#endif
#endif
