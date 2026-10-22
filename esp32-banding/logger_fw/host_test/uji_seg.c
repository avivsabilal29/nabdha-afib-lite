/*
 * uji_seg.c -- uji PC pemotong segmen logger dengan arus sintetis yang jawabannya diketahui.
 *   gcc -O2 -I../src -o uji_seg uji_seg.c ../src/seg.c -lm && ./uji_seg
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include "seg.h"

static seg_state_t S;
static int gagal;

static void cek(const char *apa, double dapat, double harap, double tol)
{
    int ok = fabs(dapat - harap) <= tol;
    printf("  %-34s %12.5f  harap %12.5f  %s\n", apa, dapat, harap, ok ? "OK" : "GAGAL");
    if (!ok) gagal++;
}

int main(void)
{
    /* urutan: 0 (0.5 s), idle 2 (20 s, 30 mA), 0 (0.3 s), bench 1 (20 s, 45 mA dengan lonjakan
     * 200 mA selama 50 ms di awal dan 50 ms di akhir), 0 (0.3 s), rt 3 (0.15 s, terlalu pendek
     * untuk trim), lalu 0. Pin kode berkedip 1 sampel di tengah idle (harus diabaikan). */
    struct { int code; int n; double ma; } fase[] = {
        {0, 500, 10}, {2, 20000, 30}, {0, 300, 10}, {1, 20000, 45}, {0, 300, 10}, {3, 150, 20}, {0, 500, 10}};
    seg_init(&S, 100);
    int64_t t = 0;
    seg_out_t o, hasil[8];
    int nh = 0;
    srand(1);
    for (unsigned f = 0; f < sizeof(fase) / sizeof(fase[0]); f++) {
        for (int i = 0; i < fase[f].n; i++) {
            double ma = fase[f].ma + ((rand() / (double)RAND_MAX) - 0.5) * 0.4;   /* derau +-0.2 mA */
            int code = fase[f].code;
            if (fase[f].code == 1 && (i < 50 || i >= fase[f].n - 50)) ma = 200.0;
            if (fase[f].code == 2 && i == 7000) code = 0;                       /* glitch 1 sampel */
            if (seg_feed(&S, t, (float)ma, 3.30f, (uint8_t)code, &o)) hasil[nh++] = o;
            t += 1000;
        }
    }
    printf("segmen tercatat: %d (harap 3)\n", nh);
    if (nh != 3) gagal++;
    for (int i = 0; i < nh; i++)
        printf("SEG,%u,%u,%u,%u,%u,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n", hasil[i].k, hasil[i].code,
               hasil[i].t0_ms, hasil[i].dur_ms, hasil[i].n, hasil[i].i_ma, hasil[i].i_sd, hasil[i].v,
               hasil[i].p_mw, hasil[i].p_min, hasil[i].p_max, hasil[i].e_mj);
    if (nh == 3) {
        printf("idle:\n");
        cek("kode", hasil[0].code, 2, 0);
        cek("durasi ms", hasil[0].dur_ms, 20000, 5);
        cek("arus rata-rata mA", hasil[0].i_ma, 30.0, 0.01);
        cek("daya rata-rata mW", hasil[0].p_mw, 99.0, 0.05);
        cek("energi mJ (P x 20 s)", hasil[0].e_mj, 99.0 * 20.0, 2.0);
        printf("bench (lonjakan 200 mA di 50 ms awal/akhir harus terbuang trim 100 ms):\n");
        cek("kode", hasil[1].code, 1, 0);
        cek("arus rata-rata mA", hasil[1].i_ma, 45.0, 0.01);
        cek("daya maks mW (tanpa lonjakan)", hasil[1].p_max, 45.2 * 3.3, 0.5);
        cek("jumlah sampel statistik", hasil[1].n, 20000 - 2 * 100 - 3, 6);
        printf("rt pendek (150 sampel < 2 x trim, pakai rata-rata tanpa trim):\n");
        cek("kode", hasil[2].code, 3, 0);
        cek("arus rata-rata mA", hasil[2].i_ma, 20.0, 0.5);
    }
    printf("%s\n", gagal ? "UJI SEGMEN: GAGAL" : "UJI SEGMEN: LULUS");
    return gagal != 0;
}
