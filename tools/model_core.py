#!/usr/bin/env python3
"""model_core.py -- satu pintu dari kata stimulus 15 bit ke rantai AFIB-LITE beku.

Kontrak masuk testbench RTL, rtl/tb/tb_top.sv:214-215

    s_tdata <= {g_stim[tick][11:0], 4'b0000};
    s_tuser <= {5'd0, g_stim[tick][14:12]};

sehingga kata[11:0] adalah hitungan ADC 12 bit bertanda dan kata[14:12] adalah nibble
penanda adapter (bit 0 clamp, bit 1 gap, bit 2 weak, bit 3 uncertain). Berkas stimulus
ditulis oleh rtl/tb/vektor/siapkan_vektor.py:222, `stim = ((mark & 0xF) << 12) | (counts & 0xFFF)`.

Modul ini TIDAK menyalin logika model. Seluruh mesinnya adalah dua berkas beku

    model/rantai-afib-lite/rantai.py     kelas Rantai, kuantisasi, ambang, seri_berpenanda,
                                         tanda_deret, kumpulkan_jendela
    model/rantai-afib-lite/adapter.py    locked_word (hitungan -> kata 16 bit),
                                         kelas Adapter (_emit, frames, chain_value)

Yang dimiliki modul ini hanya konversi wadah: kata 15 bit -> hitungan 12 bit -> satu nilai
millivolt yang membuat kuantisasi beku menghasilkan kata 16 bit yang sama. Tidak ada satu
baris aritmetika tahap pun yang ditulis ulang di sini.

Impor modul ini tidak punya efek samping: tidak ada berkas dibaca atau ditulis saat impor.

Pemakaian

    kata = [int(x, 16) for x in open("rtl/tb/vektor/04015.stimulus.hex")]
    out = jalankan_model(kata)                       # enam kolom + peristiwa
    out = jalankan_model(kata, lab=lab)              # + fitur/kelas jendela dua lengan
"""
from __future__ import annotations

import pathlib
import sys
import time

import numpy as np

# =============================================================================================
# Titik masuk ke berkas beku. Hanya dua modul model yang diimpor, tidak ada salinan logika.
# =============================================================================================

# Akar repo dihitung dari letak berkas ini (tools/model_core.py), dengan jalur mutlak sebagai
# cadangan supaya modul tetap jalan bila disalin keluar repo.
_AKAR = pathlib.Path(__file__).resolve().parents[1]
REPO = _AKAR if (_AKAR / "model" / "rantai-afib-lite").is_dir() else \
    pathlib.Path("/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite")
MODEL = REPO / "model" / "rantai-afib-lite"
if str(MODEL) not in sys.path:
    sys.path.insert(0, str(MODEL))

import adapter as A  # noqa: E402
import rantai as R  # noqa: E402

# Kontrak kata.
W_KATA = 15
W_HITUNG = 12            # afib_lite_pkg.sv:79-80, hitungan 12 bit bertanda
GESER_KATA = 12          # nibble penanda di atas hitungan
GAIN_MV_PER_HITUNG = 200.0   # dataset/afdb/04015.hea: gain 0 -> default WFDB 200 counts/mV
ZERO_HITUNG = 0.0            # dataset/afdb/04015.hea: zero level 0

KOLOM = ("masukan16", "lp", "hp", "turunan", "kuadrat", "jendela")
PERISTIWA = ("puncak", "qrs", "rr", "rr_mark_raw", "rr_corrected", "rr_mark_corrected",
             "ambang_state", "ambang_kemiringan_puncak", "ambang_puncak_terfilter",
             "rr_average1", "rr_average2", "penanda", "rr_disemai", "rr_menyala_akhir")


def kata_ke_count(kata: np.ndarray) -> np.ndarray:
    """kata[11:0] sebagai hitungan 12 bit bertanda (komplemen dua), int64."""
    k = np.asarray(kata, dtype=np.int64).reshape(-1) & 0xFFFF
    c = k & ((1 << W_HITUNG) - 1)
    return np.where(c >= (1 << (W_HITUNG - 1)), c - (1 << W_HITUNG), c)


def kata_ke_penanda(kata: np.ndarray) -> np.ndarray:
    """kata[14:12] sebagai nibble penanda adapter, 0..15."""
    k = np.asarray(kata, dtype=np.int64).reshape(-1) & 0xFFFF
    return (k >> GESER_KATA) & 0xF


class SumberKata(A.Adapter):
    """Adapter yang membawa kolom hitungan 12 bit. Hanya formatnya yang dimiliki kelas ini.

    Konversi hitungan -> nilai yang masuk rantai memakai dua fungsi beku apa adanya:
    A.locked_word (adapter.py:248-259) dan A.Adapter.chain_value (adapter.py:364-371).
    """

    MODE = "stimulus kata"
    SOURCE = "larik kata stimulus 15 bit"
    BLOCK_FRAMES = 1 << 20
    DEFAULT_CHUNK = 1

    def __init__(self, count, gain=GAIN_MV_PER_HITUNG, zero=ZERO_HITUNG):
        super().__init__()
        # Nama atribut sengaja bukan _count: Adapter memakai self._count sebagai dict cacah
        # penanda dan _emit menulis ke sana, jadi menabrak nama itu merusak larik masukan.
        self._hitung = np.asarray(count, dtype=np.int64).reshape(-1)
        self._gain = float(gain)
        self._zero = float(zero)
        self._i = 0

    def open(self):
        return self.declare_rate(R.FS_HZ)

    def read(self):
        if self._i >= self._hitung.size:
            return None
        c = int(self._hitung[self._i])
        self._i += 1
        value16, pre = A.locked_word(c, self._gain, self._zero)
        return self._emit(value16, pre=pre)

    def close(self):
        super().close()


def count_ke_value16(count, gain=GAIN_MV_PER_HITUNG, zero=ZERO_HITUNG) -> int:
    """Kata 16 bit yang dihasilkan front end RTL untuk satu hitungan. Mesin: A.locked_word."""
    return int(A.locked_word(int(count), float(gain), float(zero))[0])


def jalankan_model(kata, lab=None, aturan_t: bool = True, semai_aktif: bool = True,
                   jendela: bool = True) -> dict:
    """Kata stimulus 15 bit -> seluruh keluaran rantai beku.

    kata          larik kata 15 bit (int, 0..32767). Panjang n menentukan panjang run.
    lab           larik label irama per sampel dari R.label_irama atas anotasi .atr. Bila
                  None, bagian jendela tidak dihitung, karena kelas jendela adalah fungsi
                  anotasi dan bukan fungsi kata stimulus. Lihat catatan batas di bawah.
    aturan_t      saklar aturan gelombang T rantai (Rantai.__init__).
    semai_aktif   saklar penyemaian ulang RR (Rantai.__init__).
    jendela       hitung fitur/kelas jendela dua lengan ketika lab tersedia.

    Kembalian dict. Kunci yang selalu ada:
      masukan16 lp hp turunan kuadrat jendela   int64 (n,)  enam kolom per sampel
      count                                     int64 (n,)  hitungan 12 bit bertanda
      penanda_masukan                           int64 (n,)  nibble kata[14:12]
      marker_adapter                            int64 (n,)  byte penanda adapter.A._emit
      puncak qrs rr rr_mark_raw rr_corrected rr_mark_corrected
      ambang_state ambang_kemiringan_puncak ambang_puncak_terfilter
      rr_average1 rr_average2 penanda_rr rr_disemai
      detik                                     float       waktu jalan rantai saja
    Kunci yang hanya ada bila lab diberikan dan jendela True:
      jendela_fitur jendela_kelas                   lengan mentah  (SUMBER_MENTAH)
      jendela_fitur_berpenanda jendela_kelas_berpenanda   lengan berpenanda
      sumber_interval rr_berpenanda tanda
    """
    kata_arr = np.asarray(kata, dtype=np.int64).reshape(-1)
    if kata_arr.size:
        lo, hi = int(kata_arr.min()), int(kata_arr.max())
        if lo < 0 or hi > (1 << W_KATA) - 1:
            raise ValueError("kata di luar 15 bit: min %d max %d" % (lo, hi))
    count = kata_ke_count(kata_arr)
    nibble = kata_ke_penanda(kata_arr)

    src = SumberKata(count)
    src.open()
    rantai = R.Rantai(semai_aktif=semai_aktif, aturan_t=aturan_t, besaran="turunan")

    marker = np.empty(count.size, dtype=np.int64)
    t0 = time.perf_counter()
    step = rantai.langkah
    nilai = src.chain_value
    i = 0
    for blok in src.frames(chunk=1):
        for s in blok:
            marker[i] = s.marker
            i += 1
            step(nilai(s))
    detik = time.perf_counter() - t0
    hasil = rantai.hasil()
    cacah = src.markers()
    src.close()

    out = {"detik": float(detik), "count": count, "penanda_masukan": nibble,
           "marker_adapter": marker, "cacah_penanda_adapter": cacah}
    for k in KOLOM:
        out[k] = np.asarray(hasil[k], dtype=np.int64)
    for k in PERISTIWA:
        out[k] = np.asarray(hasil[k], dtype=np.int64)
    out["rentang"] = rantai.rentang_terukur()

    if lab is not None and jendela:
        qrs = out["qrs"]
        lab_arr = np.asarray(lab)
        rr_ms = np.diff(qrs) / R.FS_HZ * 1000.0
        tanda = np.asarray(R.tanda_deret(rr_ms), dtype=np.int64)
        fitur_m, kelas_m = R.kumpulkan_jendela(qrs, lab_arr, sumber=R.SUMBER_MENTAH)
        fitur_b, kelas_b = R.kumpulkan_jendela(qrs, lab_arr,
                                               sumber=R.SUMBER_BERPENANDA, mark=tanda)
        rr_ber, sumber_interval = R.seri_berpenanda(rr_ms, tanda)
        out["jendela_fitur"] = np.asarray(fitur_m, dtype=float)
        out["jendela_kelas"] = np.asarray([str(x) for x in kelas_m], dtype="U6")
        out["jendela_fitur_berpenanda"] = np.asarray(fitur_b, dtype=float)
        out["jendela_kelas_berpenanda"] = np.asarray([str(x) for x in kelas_b], dtype="U6")
        out["sumber_interval"] = np.asarray(sumber_interval, dtype=np.int64)
        out["rr_berpenanda"] = np.asarray(rr_ber, dtype=float)
        out["tanda"] = tanda
    return out


def baca_stimulus(path) -> np.ndarray:
    """Berkas stimulus 4 digit hex per baris -> larik kata 15 bit."""
    return np.array([int(x, 16) for x in pathlib.Path(path).read_text().split()],
                    dtype=np.int64)


def baca_kolom_hex(path) -> np.ndarray:
    """Kolom emas fase0, 8 digit hex per baris, sebagai pola 32 bit apa adanya (0..2**32-1).

    Ekspor fase0 (ekspor_vektor.py:61-76) menulis pola 32 bit: nilai negatif sebagai komplemen
    dua, nilai positif apa adanya. Kolom jendela memuat nilai di atas 2**31 (maksimum
    3105281786), jadi tafsir bertanda 32 bit akan salah untuk kolom itu. Karena itu pola
    mentah yang dikembalikan di sini dan pembandingan dilakukan modulo 2**32.
    """
    return np.array([int(x, 16) & 0xFFFFFFFF for x in pathlib.Path(path).read_text().split()],
                    dtype=np.int64)


def baca_kolom_hex_bertanda(path) -> np.ndarray:
    """Tafsir bertanda 32 bit. Hanya sah untuk kolom yang seluruh nilainya di bawah 2**31."""
    raw = baca_kolom_hex(path)
    return np.where(raw >= 2 ** 31, raw - 2 ** 32, raw)


if __name__ == "__main__":  # pragma: no cover - dipakai untuk uji cepat manual
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    stim = baca_stimulus(REPO / "rtl" / "tb" / "vektor" / "04015.stimulus.hex")[:n]
    o = jalankan_model(stim)
    print("sampel %d, %.3f s, puncak %d, qrs %d"
          % (n, o["detik"], o["puncak"].size, o["qrs"].size))
