/*
 * Uji di PC (tanpa ESP32): jalankan logika firmware yang SAMA (ecg_frame.c)
 * pada sinyal ECG sintetis yang "dibaca" ADC 2 kHz, lalu tulis:
 *   - stream.bin   : aliran serial persis seperti dari ESP32 (+ sampah boot,
 *                    satu rekaman hilang, satu bita rusak)
 *   - expected.csv : cacah & penanda yang seharusnya keluar
 * Pengurai Python kemudian dicek terhadap expected.csv.
 *
 *   gcc -O2 -I../src -o test_stream test_stream.c ../src/ecg_frame.c -lm
 *   ./test_stream out_dir
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "ecg_frame.h"

#define FS_SUB   2000
#define NSUB     8
#define GAIN     100
#define BASE_MV  1650
#define SECONDS  20

static double gauss(double t, double mu, double sig, double a)
{
    double d = (t - mu) / sig;
    return a * exp(-0.5 * d * d);
}

/* satu detak PQRST (mV acuan input), t relatif terhadap puncak R (detik) */
static double beat(double t)
{
    return gauss(t, -0.20, 0.025, 0.12) +   /* P */
           gauss(t, -0.03, 0.010, -0.15) +  /* Q */
           gauss(t,  0.00, 0.012, 1.20) +   /* R */
           gauss(t,  0.03, 0.010, -0.25) +  /* S */
           gauss(t,  0.30, 0.050, 0.30);    /* T */
}

int main(int argc, char **argv)
{
    const char *dir = argc > 1 ? argv[1] : ".";
    char path[512];
    snprintf(path, sizeof path, "%s/stream.bin", dir);
    FILE *fb = fopen(path, "wb");
    snprintf(path, sizeof path, "%s/expected.csv", dir);
    FILE *fe = fopen(path, "w");
    if (!fb || !fe) { perror("fopen"); return 1; }
    fprintf(fe, "indeks,cacah,flags\n");

    /* sampah boot ROM sebelum aliran biner */
    const char *boot = "ets Jun  8 2016 00:22:57\r\nrst:0x1 (POWERON_RESET)\r\n\xA5\x5A\x00";
    fwrite(boot, 1, strlen(boot), fb);

    srand(1234);
    /* daftar puncak R: 0..10 s teratur (75 BPM), 10..20 s tak teratur (mirip AF) */
    double peaks[64]; int np = 0; double t = 0.4;
    while (t < SECONDS && np < 64) {
        peaks[np++] = t;
        double rr = (t < 10.0) ? 0.80 : 0.45 + 0.40 * (rand() / (double)RAND_MAX);
        t += rr;
    }

    long nsub_total = (long)SECONDS * FS_SUB;
    int32_t sum = 0; int n = 0; uint8_t flags = 0;
    uint8_t seq = 0; long idx = 0; long out_idx = 0;
    int dropped_done = 0, corrupt_done = 0;

    for (long k = 0; k < nsub_total; k++) {
        double ts = k / (double)FS_SUB;
        double mv_in = 0;
        for (int i = 0; i < np; i++) {
            double d = ts - peaks[i];
            if (d > -0.4 && d < 0.6) mv_in += beat(d);
        }
        /* elektroda lepas 14,0..14,5 s -> keluaran mentok rel atas */
        int lo = (ts >= 14.0 && ts < 14.5);
        int mv_out = lo ? 3100 : (int)lround(BASE_MV + GAIN * mv_in + ((rand() % 7) - 3));
        int rail = (mv_out >= 3090);
        sum += mv_out; n++;
        if (lo) flags |= ECG_FLAG_GAP;
        if (rail) flags |= ECG_FLAG_CLAMP;

        if (n == NSUB) {
            int16_t c = ecg_counts_from_sum(sum, n, BASE_MV, GAIN, 200, 2047, &flags);
            if ((idx % 250) == 0) {
                uint16_t vals[ECG_HDR_COUNT] = {0x0100, GAIN, 3100, 250, BASE_MV, 200, 1, 3};
                for (int f = 0; f < ECG_HDR_COUNT; f++) {
                    uint8_t h[8]; ecg_frame_header(h, (uint8_t)f, vals[f]); fwrite(h, 1, 8, fb);
                }
            }
            uint8_t fr[8];
            ecg_frame_sample(fr, flags, seq, c);
            if (idx == 1000 && !dropped_done) {
                dropped_done = 1;                       /* rekaman ini "hilang" di kabel */
            } else {
                if (idx == 2000 && !corrupt_done) {     /* satu bita rusak -> checksum gagal */
                    corrupt_done = 1;
                    fr[4] ^= 0x10;
                } else {
                    uint8_t ef = flags;
                    if (idx == 1001 || idx == 2001)
                        ef |= ECG_FLAG_GAP;   /* pengurai menandai sampel susulan yang hilang */
                    fprintf(fe, "%ld,%d,%u\n", out_idx++, c, ef);
                }
                fwrite(fr, 1, 8, fb);
            }
            seq++; idx++;
            sum = 0; n = 0; flags = 0;
        }
    }
    fclose(fb); fclose(fe);
    printf("sampel firmware: %ld, sampel diharapkan di pengurai: %ld\n", idx, out_idx);
    return 0;
}
