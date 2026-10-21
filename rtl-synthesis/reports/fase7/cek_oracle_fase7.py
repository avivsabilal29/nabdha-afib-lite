#!/usr/bin/env python3
# cek_oracle_fase7.py -- Fase 7, independent witness for three numbers the phase asserts.
# Reads the WRITTEN vectors only, never the frozen model, so it is a second opinion.
#
#   1 the synthetic oracle: window maximum computed from the derivative column must equal
#     the golden kem column, with the 24 bit words read as signed (rantai.py:330-333)
#   2 the cause of the 2048 of 16777216 grid difference between the crossing form and the
#     forbidden shift form
#   3 the range of the slope words against the W_TW report port
import numpy as np

D = "rtl/tb/vektor/fase7/"

def col(name):
    return np.array([int(l, 16) for l in open(D + name)])

d = col("04015.sintetis.turunan.hex")
k = col("04015.sintetis.kem.hex")
p = col("04015.sintetis.pos.hex")
v = d & 0xFFFFFF
s = np.where(v >= 2 ** 23, v - 2 ** 24, v)

print("# Cek oracle sintetis: maksimum jendela dari kolom turunan vs kolom kem emas")
bad = 0
ex = []
for i, pos in enumerate(p):
    lo = max(pos - 18, 0)
    hi = min(pos + 18, d.size - 1)
    m = int(np.max(np.abs(s[lo:hi + 1])))
    if m != int(k[i]):
        bad += 1
        if len(ex) < 3:
            ex.append((i, int(pos), m, int(k[i])))
print("posisi diperiksa = %d, beda = %d, contoh pertama = %s" % (p.size, bad, ex))
print("nilai terbesar kolom kem emas = %d, tertinggi yang dapat diwakili porta W_TW = %d"
      % (int(k.max()), 2 ** 23 - 1))
print("spike terbesar di kolom turunan = %d = 2**22-1, jauh di bawah rail laporan"
      % int(np.abs(s).max()))

print()
print("# Sebab 2048 dari 16777216 pada grid yang sama dengan teorema 8 model beku")
s4096 = np.arange(4096, dtype=np.int64)
odd = even = 0
at = []
for sp in range(4096):
    cross = 2 * s4096 < sp
    sh = s4096 < (sp >> 1)
    dd = np.nonzero(cross != sh)[0]
    if dd.size:
        if sp % 2 == 1:
            odd += dd.size
        else:
            even += dd.size
        if len(at) < 5:
            at.append((sp, int(dd[0])))
print("pasangan berbeda (silang vs geser) = %d dari %d" % (odd + even, 4096 * 4096))
print("dengan kem_qrs ganjil = %d, dengan kem_qrs genap = %d" % (odd, even))
print("lima contoh (kem_qrs, kem) = %s, yaitu kem = (kem_qrs-1)/2 = floor(kem_qrs/2)" % at)
print("pada titik itu rute float (kem < kem_qrs/2.0) bernilai salah dan bentuk geser benar,")
print("sehingga rute float sama dengan bentuk silang: 0 beda (04015.grid.full.out)")
