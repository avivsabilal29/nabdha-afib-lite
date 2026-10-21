# TEMUAN: kata masuk jalur papan (PS -> s_tdata) belum sama dengan kata yang dipakai gerbang

Tanggal: 21 Oktober 2026, ~03:30 WIB. Ditemukan saat menyiapkan jembatan PS ke `s_tdata` untuk venue.
Belum ada perubahan RTL yang dilakukan atas temuan ini.

## Bukti

1. Porta masuk top menerima kata Q12.4: `acq_frontend.sv:150`
   `wire signed [W_CNT-1:0] cnt_in = s_tdata[W_IN-1:SHIFT_IN];` jadi 12 bit cacah ada di bit 15..4.
2. Front-end menerapkan penguatan: `acq_frontend.sv:154`
   `prod_s = (cnt_ext <<< SHIFT_MUL) - cnt_ext;` yaitu cacah x 2047, lalu dibagi 1000.
3. Testbench menyuapkan cacah mentah: `rtl/tb/tb_top.sv:205`
   `s_tdata <= {g_stim[tick][11:0], 4'b0000};` dengan `g_stim` = kolom stimulus 15 bit.
4. Kolom emas `masukan16` = keluaran front-end (sesudah penguatan). Enam sampel pertama:

   | stimulus (15 bit) | cacah 12-bit | `s_tdata` = cacah<<4 | kolom `masukan16` | rasio |
   |---|---|---|---|---|
   | `0fc9` | -55 | -880 | -1808 | 32,87 |
   | `0fc5` | -59 | -944 | -1936 | 32,81 |
   | `0fc2` | -62 | -992 | -2032 | 32,77 |
   | `0fc1` | -63 | -1008 | -2064 | 32,76 |
   | `0fc4` | -60 | -960 | -1968 | 32,80 |
   | `0fc0` | -64 | -1024 | -2096 | 32,75 |

   Rasio teoretis 2047/1000 x 16 = 32,752. Cocok.
5. Berkas `rtlplan2/fase0/04015.masukan16.hex` dan larik `masukan16` di
   `model/rantai-afib-lite/fixture/04015_30m.npz` berisi nilai yang sama (dibandingkan: identik).
6. Driver PS menyuapkan larik itu apa adanya ke `SAMPLE_FIFO`:
   `ps/ps_driver_afib.py:411` `self.bus.write(IDX["SAMPLE_FIFO"], int(w) & 0xFFFF);` dengan
   `words = z["masukan16"]`.

## Akibat

Kalau PS menulis nilai `masukan16` (sesudah penguatan) ke FIFO dan FIFO itu menyuapi `s_tdata`,
rantai menerapkan penguatan sekali lagi. Yang harus disuapkan adalah kata cacah mentah, yaitu
kolom stimulus 15 bit (`rtl/tb/vektor/04015.stimulus.hex`) yang dibentuk menjadi `{cacah, 4'b0}`.

Driver mock tidak menangkap cacat ini karena ia model Python, bukan RTL: penguatan itu tidak ada
di dalam mock.

## Tindakan yang disarankan

1. Jembatan FIFO menyuapi `s_tdata` dengan kata cacah mentah, bukan larik `masukan16`.
2. Driver PS punya mode "ingest" yang membaca kolom stimulus 15 bit dan menyusun kata 16 bit
   sebelum menulis ke `SAMPLE_FIFO`, terpisah dari mode tulis-dan-baca register yang sekarang.
3. Uji terima: pada papan, putar ulang rekaman 04015 dan bandingkan cacah register
   (`0x1C BEAT_COUNT`, `0x28 WINDOW_COUNT`, `0x10 CLASS_OUT`) dengan emas. Kalau penguatan
   dua kali terjadi, `BEAT_COUNT` tidak akan 2596.
