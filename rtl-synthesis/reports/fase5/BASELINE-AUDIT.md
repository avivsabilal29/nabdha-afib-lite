# BASELINE AUDIT FASE 5 — dihitung ulang oleh agen induk (bukan dikutip dari laporan)

Dihitung langsung dari `rtlplan2/fase5/04015.*` pada 2026-10-20 oleh agen induk, sebelum
implementasi dimulai. Dipakai untuk mengaudit klaim implementer/verifier.

## Angka kunci (hasil hitung ulang independen)

| Besaran | Nilai | Cara hitung |
|---|---|---|
| baris `peaks.csv` | 4777 | jumlah baris data |
| `is_qrs == 1` | 2596 | cacah kolom `is_qrs` |
| `is_qrs == 0` | 2181 | cacah kolom `is_qrs` |
| baris `rr.csv` | 2595 | jumlah baris data |
| baris `threshold_state.csv` | 4777 | jumlah baris data |
| census `event_kind` (peaks.csv) | {'qrs': 2590, 'rejected_t': 1909, 'noise': 272, 'qrs_search_back': 6} | total 4777 |
| census `event_type` (threshold_events.csv) | {'search_back_refit': 6, 't_wave_reject': 1909} | 1915 baris |
| `i1` min .. max | 0 .. 206147681 | kolom `i1` |
| `i2 == i1 >> 1` | True pada seluruh 4777 baris | uji kesetaraan |
| `spki_after` maksimum | **717628984** (bit_length 30) | kolom `spki_after` |

## Implikasi yang dikunci (dipakai sebagai kriteria audit)

1. **Awal dari nol terkonfirmasi**: puncak pertama (`sample_index` 91) punya `i1 = 0`, `i2 = 0`,
   `spki_before = npki_before = 0`, dan tetap `signal = 1` karena `pv > 0`. Ini bukti angka K2.
2. **State ambang wajib >= 30 bit tanpa pembelitan**: `spki_after` maks 717628984 > 2^29-1 =
   536870911 (jangkauan bertanda 29 bit) dan < 2^30-1 = 1073741823. Desain menyimpannya pada
   33 bit (rel jendela) sesuai K3; tidak boleh ada klip.
3. **`i1` muat 30 bit** (maks 206147681 < 2^28), sehingga porta `d_thr` (30 bit) aman.
4. **Census peristiwa diambil dari `peaks.csv:event_kind`**, bukan dari `threshold_events.csv`
   (yang hanya memuat 1915 baris refit/tolak-T).

## Sidik jari berkas saat baseline diambil

- `rtl/peak_detect.sv` : `481d3b0e421f5c07de83bd938f09a76fb2a3bd9f881117c95525d327d6de71ab` (placeholder, 5962 B)
- `model/rantai-afib-lite/rantai.py` : `90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5`
