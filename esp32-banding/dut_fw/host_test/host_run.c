/*
 * host_run.c -- jalankan rantai C yang SAMA dengan firmware di PC, keluaran protokol sama.
 *
 *   gcc -O2 -I../src -o host_run host_run.c ../src/afib_chain.c ../src/afib_run.c -lm
 *   ./host_run ../data/04015.stim.bin 04015 verif > host_04015.log
 *   python ../../tools/banding_esp32.py periksa host_04015.log
 *
 * Mode: verif | prof | mentah (verif lengan mentah)
 */
#define _POSIX_C_SOURCE 199309L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "afib_chain.h"
#include "afib_run.h"

static uint64_t now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}
static uint32_t host_cycles(void) { return (uint32_t)now_ns(); }   /* nanodetik, bukan siklus */
static uint64_t host_us(void) { return now_ns() / 1000ull; }

int main(int argc, char **argv)
{
    if (argc < 3) {
        fprintf(stderr, "pakai: %s <stim.bin> <rekaman> [verif|prof|mentah]\n", argv[0]);
        return 2;
    }
    const char *mode = argc > 3 ? argv[3] : "verif";
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint16_t *stim = malloc((size_t)sz);
    if (!stim || fread(stim, 1, (size_t)sz, f) != (size_t)sz) { fprintf(stderr, "baca gagal\n"); return 1; }
    fclose(f);

    afib_plat_t p;
    memset(&p, 0, sizeof(p));
    p.stim = stim;
    p.n = (uint32_t)(sz / 2);
    p.rec = argv[2];
    p.src = "host";
    p.stim_sha = "na";
    p.fcpu_mhz = 0;
    p.cycles = host_cycles;
    p.time_us = host_us;

    if (!strcmp(mode, "prof")) afib_run_prof(&p, AFIB_ARM_BERPENANDA, 3);
    else if (!strcmp(mode, "mentah")) afib_run_verif(&p, AFIB_ARM_MENTAH);
    else afib_run_verif(&p, AFIB_ARM_BERPENANDA);
    free(stim);
    return 0;
}
