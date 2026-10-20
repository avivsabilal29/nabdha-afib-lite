# Bukti pendukung Fase 10

Berkas di direktori ini disalin dari area kerja `~/.hermes/cache/scratch/fase10/` pada
21 Oktober 2026 sekitar 04:40 WIB, supaya klaim angka di `LAPORAN-FASE10.md` punya rumah **di dalam
repo**. Alasannya temuan audit F6: sebagian bukti hanya hidup di area kerja, dan area kerja bisa
terhapus.

| Berkas | Klaim yang disokong |
|---|---|
| `icarus_full_450k_INDUK.log` | lengan berpenanda Icarus: `total mismatches = 0`, `PASS`, 450.000 kata tiap aliran, `unknown = 0` |
| `icarus_full_450k_mentah_INDUK.log` | lengan mentah Icarus: sama, 450.000 kata tiap aliran |
| `top_icarus_full_450k_final.log` | jalur Icarus penuh lewat testbench top (bukti pendamping) |
| `top_verilator_arm_mentah_final.log` | lengan mentah Verilator, dipakai untuk banding lintas mesin |
| `checksum_matrix.json` | empat checksum kedua mesin: `CK_STREAM`, `CK_PEAK`, `CK_DOWN`, `CK_EVENT` |
| `synth_summary_INDUK.txt` | enam angka sintesis rute repo (`acq_frontend` sampai `rr_series`) |
| `synth_sisa_summary.txt` | sisa sintesis: `classifier`, `regs_axi`, `t_rule` (gagal pemeriksaan area), `features` (dihentikan), `peak_detect` (habis memori di dalam pagar), `afib_lite_top` |
| `fase5_short_after_tahap5.log` | jalankan pendek Fase 5 sesudah Tahap 5 |

Dua catatan pembacaan yang sengaja tidak dirapikan supaya tidak menyesatkan:

1. Icarus melaporkan 450.000 kata dan Verilator 449.999 kata pada aliran yang sama. Selisih satu kata
   itu belum saya jelaskan secara mekanis, dan saya sebut apa adanya. Patokan gerbang tidak
   bergantung padanya: perbandingan kata demi kata atas 450.000 baris lolos di kedua mesin, dan
   checksum yang sah untuk banding lintas mesin adalah `CK_DOWN`/`CK_EVENT` (lihat §7.2).
2. Log sintesis berukuran megabyte (`features`, `peak_detect`, `afib_lite_top`) **tidak** disalin ke
   sini. Angka dan sebab kegagalannya sudah diringkas di `synth_sisa_summary.txt` dan di §7.5.
