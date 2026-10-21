#include "ecg_frame.h"

int32_t ecg_floor_div(int32_t num, int32_t den)
{
    int32_t q = num / den;
    int32_t r = num % den;
    if ((r != 0) && ((r < 0) != (den < 0))) {
        q -= 1;
    }
    return q;
}

int16_t ecg_counts_from_sum(int32_t sum_mv, int32_t n, int32_t baseline_mv,
                            int32_t kit_gain, int32_t counts_per_mv,
                            int32_t clamp_count, uint8_t *flags)
{
    if (n <= 0 || kit_gain <= 0) {
        *flags |= ECG_FLAG_GAP;
        return 0;
    }
    /* jumlah setara 8 bacaan, relatif terhadap dasar (satuan: mV x 8 di OUT) */
    int32_t diff8 = (n == 8) ? (sum_mv - 8 * baseline_mv)
                             : ecg_floor_div((sum_mv - n * baseline_mv) * 8, n);
    /* counts_per_mv / 8 = 25 untuk 200 cacah/mV */
    int32_t counts = ecg_floor_div(diff8 * counts_per_mv, 8 * kit_gain);

    if (counts > clamp_count) {
        counts = clamp_count;
        *flags |= ECG_FLAG_CLAMP;
    } else if (counts < -clamp_count) {
        counts = -clamp_count;
        *flags |= ECG_FLAG_CLAMP;
    }
    return (int16_t)counts;
}

uint8_t ecg_checksum(const uint8_t *frame)
{
    uint32_t s = 0;
    for (int i = 0; i < 7; i++) {
        s += frame[i];
    }
    return (uint8_t)(s & 0xFF);
}

void ecg_frame_sample(uint8_t out[ECG_FRAME_LEN], uint8_t flags, uint8_t seq, int16_t counts)
{
    uint16_t u = (uint16_t)counts;
    out[0] = ECG_SYNC0;
    out[1] = ECG_SYNC1;
    out[2] = (uint8_t)(flags & 0x07);      /* bit3 selalu 0 untuk sampel */
    out[3] = seq;
    out[4] = (uint8_t)(u & 0xFF);
    out[5] = (uint8_t)(u >> 8);
    out[6] = 0x00;
    out[7] = ecg_checksum(out);
}

void ecg_frame_header(uint8_t out[ECG_FRAME_LEN], uint8_t field_id, uint16_t value)
{
    out[0] = ECG_SYNC0;
    out[1] = ECG_SYNC1;
    out[2] = ECG_FLAG_HEADER;
    out[3] = field_id;
    out[4] = (uint8_t)(value & 0xFF);
    out[5] = (uint8_t)(value >> 8);
    out[6] = 0x00;
    out[7] = ecg_checksum(out);
}

uint16_t ecg_stim_word(int16_t counts, uint8_t flags)
{
    uint16_t w = (uint16_t)counts & 0x0FFF;          /* 12 bit komplemen dua */
    if (flags & ECG_FLAG_CLAMP) w |= (1u << 12);
    if (flags & ECG_FLAG_GAP)   w |= (1u << 13);
    if (flags & ECG_FLAG_WEAK)  w |= (1u << 14);
    return w;
}
