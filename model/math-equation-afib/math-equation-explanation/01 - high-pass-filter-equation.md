# High-Pass Filter Equation

Catatan turunan lengkap untuk tapis high-pass rekursif Pan-Tompkins, persamaan (6) halaman 232, beserta contoh soal dan jawabannya. Semua persamaan ditulis dalam LaTeX dan dirender Obsidian. Semua angka di dokumen ini dihitung dengan Python, bukan dikutip dari ingatan. Notebook pendampingnya ada di `nabdha-afib-lite/model/math-equation-afib/01 - high-pass-filter-equation.ipynb`, dan dokumen pendampingnya adalah [[00 - low-pass-filter-equation|low-pass-filter-equation]].

Tujuan dokumen ini: setelah membacanya, Anda bisa menurunkan fungsi alih dari persamaan bedanya, menjelaskan mengapa keluaran filter ini selalu bergantian tanda, menghitung keluarannya dengan tangan, dan menjelaskan mengapa kutub di frekuensi Nyquist tidak membuat rangkaian Pan-Tompkins meledak. Yang bisa dihitung dengan tangan ditandai.

## 1. Variabel dan notasi

| Simbol | Arti | Keterangan |
|---|---|---|
| $n$ | indeks sampel | bilangan bulat, $n \ge 0$ |
| $T$ | periode sampling | $T = 1/f_s$ |
| $f_s$ | frekuensi sampling | 200 Hz di makalah, 250 Hz di rancangan AFIB-LITE |
| $x[n]$ | sampel masukan ke-$n$ | ditulis $x(nT)$ di makalah |
| $y[n]$ | sampel keluaran ke-$n$ | ditulis $y(nT)$ di makalah |
| $z^{-1}$ | operator tunda satu sampel | $z^{-1}X(z) \leftrightarrow x[n-1]$ |
| $H(z)$ | fungsi alih | $H(z) = Y(z)/X(z)$ |
| $\omega$ | frekuensi sudut digital | $\omega = 2\pi f / f_s$ |
| $d[n]$ | suku paksa | seluruhnya tersusun dari masukan, tidak bergantung pada keluaran |
| $\delta[n]$ | impuls satuan | 1 di $n = 0$, 0 di tempat lain |
| $\mathbf{1}_{n \ge m}$ | penanda langkah | 1 bila $n \ge m$, 0 bila tidak |

Angka-angka penting ditulis tebal: **16** adalah tunda cabang all-pass, **32** adalah tunda umpan maju dan sekaligus satu-satunya koefisien, dan **5 Hz** adalah klaim cutoff bawah di makalah yang dibahas di bagian 13.

## 2. Langkah 1, buka tanda kurung siku

Persamaan aslinya:

$$
y[n] = 32x[n-16] - \Big[\, y[n-1] + x[n] - x[n-32] \,\Big]
$$

Kurung siku hanya mengelompokkan tiga suku. Buka dengan mengalikan tanda minus ke dalamnya:

$$
-\Big[\,y[n-1] + x[n] - x[n-32]\,\Big] = -y[n-1] - x[n] + x[n-32]
$$

$$
y[n] = 32x[n-16] - y[n-1] - x[n] + x[n-32]
$$

## 3. Langkah 2, kumpulkan keluaran dan beri nama suku paksa

Pindahkan $-y[n-1]$ ke kiri:

$$
y[n] + y[n-1] = 32x[n-16] - x[n] + x[n-32]
$$

Ruas kanan bergantung pada masukan saja, jadi beri nama:

$$
d[n] = 32x[n-16] - x[n] + x[n-32]
$$

$$
y[n] + y[n-1] = d[n]
$$

## 4. Langkah 3, selesaikan rekurensinya

$$
y[n] = d[n] - y[n-1]
$$

Buka satu per satu dengan syarat awal riwayat bernilai nol:

$$
\begin{aligned}
y[0] &= d[0] - 0 \\
y[1] &= d[1] - y[0] = d[1] - d[0] \\
y[2] &= d[2] - d[1] + d[0] \\
y[3] &= d[3] - d[2] + d[1] - d[0]
\end{aligned}
$$

Polanya berganti tanda tiap suku dengan urutan terbalik, sehingga bentuk umumnya

$$
y[n] = \sum_{k=0}^{n}(-1)^{\,n-k}\,d[k] = (-1)^{n}\sum_{k=0}^{n}(-1)^{k}\,d[k]
$$

Bentuk ini saya uji terhadap rekursi langsung untuk masukan impuls, langkah, dan masukan acak bulat. Ketiganya cocok persis. Inilah sebabnya keluaran filter ini selalu mengandung komponen bergantian tanda yang tidak pernah hilang.

## 5. Langkah 4, contoh impuls dihitung penuh

Masukan $x[n] = \delta[n]$, jadi

$$
d[n] = 32\delta[n-16] - \delta[n] + \delta[n-32]
$$

Tiga lompatan: $-1$ di $n = 0$, $+32$ di $n = 16$, $+1$ di $n = 32$.

| $n$ | $x[n]$ | $32x[n-16]$ | $-y[n-1]$ | $-x[n]$ | $+x[n-32]$ | $y[n]$ |
|---|---|---|---|---|---|---|
| 0 | 1 | 0 | 0 | $-1$ | 0 | **$-1$** |
| 1 | 0 | 0 | $+1$ | 0 | 0 | **$+1$** |
| 2 | 0 | 0 | $-1$ | 0 | 0 | **$-1$** |
| 3 | 0 | 0 | $+1$ | 0 | 0 | **$+1$** |
| 15 | 0 | 0 | $+1$ | 0 | 0 | **$+1$** |
| 16 | 0 | $32$ | $-1$ | 0 | 0 | **$31$** |
| 17 | 0 | 0 | $-31$ | 0 | 0 | **$-31$** |
| 18 | 0 | 0 | $+31$ | 0 | 0 | **$31$** |
| 19 | 0 | 0 | $-31$ | 0 | 0 | **$-31$** |
| 31 | 0 | 0 | $+31$ | 0 | 0 | **$31$** |
| 32 | 0 | 0 | $-31$ | 0 | $+1$ | **$32$** |
| 33 | 0 | 0 | $-32$ | 0 | 0 | **$-32$** |
| 34 | 0 | 0 | $+32$ | 0 | 0 | **$32$** |

Baris $n = 16$ dibaca begini: impuls asli muncul 16 langkah lalu, jadi $32x[0] = 32$, sementara baris sebelumnya bernilai $+1$ sehingga $-y[15] = -1$, dan hasilnya $31$. Setelah $n = 32$ keluaran menetap bergantian antara $32$ dan $-32$, tidak pernah kembali ke nol. Bentuk tertutup tanggapan impuls, yang saya uji melawan tabel di atas:

$$
h[n] = (-1)^{n}\Big[\,-1 + 32\cdot\mathbf{1}_{n \ge 16} + \mathbf{1}_{n \ge 32}\,\Big]
$$

## 6. Langkah 5, contoh langkah satuan

Masukan $x[n] = 1$ untuk semua $n \ge 0$, jadi

$$
d[n] = 32\cdot\mathbf{1}_{n \ge 16} - 1 + \mathbf{1}_{n \ge 32}
$$

| $n$ | $x[n]$ | $32x[n-16]$ | $-y[n-1]$ | $-x[n]$ | $+x[n-32]$ | $y[n]$ |
|---|---|---|---|---|---|---|
| 0 | 1 | 0 | 0 | $-1$ | 0 | **$-1$** |
| 1 | 1 | 0 | $+1$ | $-1$ | 0 | **$0$** |
| 2 | 1 | 0 | $0$ | $-1$ | 0 | **$-1$** |
| 3 | 1 | 0 | $+1$ | $-1$ | 0 | **$0$** |
| 15 | 1 | 0 | $+1$ | $-1$ | 0 | **$0$** |
| 16 | 1 | $32$ | $0$ | $-1$ | 0 | **$31$** |
| 17 | 1 | $32$ | $-31$ | $-1$ | 0 | **$0$** |
| 18 | 1 | $32$ | $0$ | $-1$ | 0 | **$31$** |
| 31 | 1 | $32$ | $-31$ | $-1$ | 0 | **$0$** |
| 32 | 1 | $32$ | $0$ | $-1$ | $+1$ | **$32$** |
| 33 | 1 | $32$ | $-32$ | $-1$ | $+1$ | **$0$** |

Baris $n = 17$ dibaca begini: $32x[1] = 32$, lalu $-y[16] = -31$, lalu $-x[17] = -1$, jumlahnya $0$. Indeks genap bernilai dan indeks ganjil nol, dengan rata-rata $16$, yaitu penguatan DC-nya. Masukan tetap menghasilkan keluaran tetap, tetapi bercampur ripple Nyquist yang berlangsung terus.

## 7. Langkah 6, fungsi alih

Transformasi z tiap suku:

$$
\begin{aligned}
y[n] &\leftrightarrow Y(z) \\
y[n-1] &\leftrightarrow z^{-1}Y(z) \\
x[n] &\leftrightarrow X(z) \\
x[n-16] &\leftrightarrow z^{-16}X(z) \\
x[n-32] &\leftrightarrow z^{-32}X(z)
\end{aligned}
$$

Substitusi ke hasil bagian 3:

$$
Y(z) + z^{-1}Y(z) = 32z^{-16}X(z) - X(z) + z^{-32}X(z)
$$

$$
Y(z)\big(1 + z^{-1}\big) = X(z)\big(32z^{-16} - 1 + z^{-32}\big)
$$

$$
H(z) = \frac{32z^{-16} - 1 + z^{-32}}{1 + z^{-1}}
$$

Bentuk ini sama dengan persamaan (4) di makalah, hanya urutan sukunya berbeda.

## 8. Langkah 7, pecah menjadi dua cabang

$$
32z^{-16} - 1 + z^{-32} = 32z^{-16} - \big(1 - z^{-32}\big)
$$

$$
H(z) = \frac{32z^{-16}}{1+z^{-1}} - \frac{1 - z^{-32}}{1+z^{-1}}
$$

Suku pertama adalah akumulator yang diberi masukan 16 sampel lalu dengan penguatan 32. Suku kedua adalah pengurangnya. Inilah arti kalimat makalah tentang mengurangkan keluaran tapis low-pass orde satu dari all-pass.

## 9. Langkah 8, ubah suku pengurang menjadi deret berhingga

$$
\frac{1 - z^{-32}}{1 + z^{-1}} = \sum_{k=0}^{31}(-1)^{k}z^{-k} = 1 - z^{-1} + z^{-2} - z^{-3} + \dots - z^{-31}
$$

Buktinya dengan mengalikan ruas kanan dengan $(1 + z^{-1})$ lalu menjumlahkan kedua baris:

$$
\begin{aligned}
1\cdot\Big(1 - z^{-1} + z^{-2} - \dots - z^{-31}\Big) &= 1 - z^{-1} + z^{-2} - \dots - z^{-31} \\
z^{-1}\cdot\Big(1 - z^{-1} + z^{-2} - \dots - z^{-31}\Big) &= z^{-1} - z^{-2} + \dots + z^{-31} - z^{-32}
\end{aligned}
$$

Setiap suku tengah muncul dua kali dengan tanda berlawanan, jadi semuanya saling menghapus dan hanya tersisa

$$
(1 + z^{-1})\sum_{k=0}^{31}(-1)^{k}z^{-k} = 1 - z^{-32}
$$

Terbukti. Uji numerik terhadap `freqz` memberi galat maksimum $1{,}9 \times 10^{-11}$.

## 10. Langkah 9, respons amplitudo

Substitusi $z = e^{j\omega}$. Pembilang, setelah mengeluarkan $e^{-j16\omega}$ yang modulusnya satu:

$$
32e^{-j16\omega} - 1 + e^{-j32\omega} = e^{-j16\omega}\Big(32 - 2j\sin(16\omega)\Big)
$$

$$
\big|32 - 2j\sin(16\omega)\big| = \sqrt{32^{2} + 4\sin^{2}(16\omega)} = 2\sqrt{256 + \sin^{2}(16\omega)}
$$

Penyebut, memakai $\big|1 + e^{-j\omega}\big| = 2\cos(\omega/2)$ untuk $|\omega| < \pi$:

$$
\big|1 + e^{-j\omega}\big| = 2\cos(\omega/2)
$$

Hasil bagi keduanya, faktor 2 saling menghapus:

$$
\big|H(e^{j\omega})\big| = \frac{\sqrt{256 + \sin^{2}(16\omega)}}{\cos(\omega/2)}
$$

Persis persamaan (5) makalah. Uji terhadap seluruh spektrum `freqz`: galat relatif maksimum $2{,}8 \times 10^{-12}$.

## 11. Langkah 10, kutub dan nol

Kutub dari penyebut:

$$
1 + z^{-1} = 0 \implies z = -1
$$

Satu kutub tunggal di $z = -1$, yaitu di frekuensi Nyquist $f_s/2$, dan modulusnya satu tanpa pasangan di dalam filter ini.

Nol dari pembilang, dengan memisalkan $w = z^{-16}$:

$$
w^{2} + 32w - 1 = 0 \implies w = \frac{-32 \pm \sqrt{1028}}{2}
$$

$$
w_{1} = +0{,}0312, \qquad w_{2} = -32{,}0312
$$

Karena tidak ada $w$ yang modulusnya satu, tidak ada nol di lingkaran satuan. Pemeriksaan numerik: 32 nol, enam belas pada radius $0{,}8052$ dan enam belas pada radius $1{,}2419$, dan jumlah nol tepat di lingkaran satuan adalah **nol**. Itulah sebabnya filter ini tidak punya takik, sehingga pita QRS tidak terpotong.

## 12. Langkah 11, contoh hitung tangan untuk tanggapan

**Di $f = 0$.** $\sin(16\omega) = 0$ dan $\cos(\omega/2) = 1$:

$$
\big|H(0)\big| = \frac{\sqrt{256}}{1} = 16
$$

**Di $f = f_s/32 = 6{,}25$ Hz.** $16\omega = \pi$, jadi $\sin(\pi) = 0$, dan $\cos(\pi/32) = 0{,}99518$:

$$
\big|H(6{,}25)\big| = \frac{16}{0{,}99518} = 16{,}077
$$

Nilai `freqz` di titik itu $16{,}077417$. Aturan umum: setiap kali $\sin(16\omega) = 0$, yaitu di kelipatan $f_s/32$, penguatannya hanya $16/\cos(\omega/2)$.

**Di $f = 5$ Hz.** $16\omega = 2{,}513$ rad dan $\sin(2{,}513) = 0{,}5878$:

$$
\big|H(5)\big| = \frac{\sqrt{256 + 0{,}3456}}{\cos(0{,}0785)} = \frac{16{,}0108}{0{,}99692} = 16{,}060
$$

## 13. Temuan tentang klaim cutoff 5 Hz

Makalah menulis bahwa cutoff bawah filter ini sekitar 5 Hz. Persamaan yang tercetak tidak melakukan itu. Penguatan DC-nya 16, dan kurvanya naik dari 16 menjadi 22 dalam rentang 0 sampai 50 Hz. Pasangan low-pass kali high-pass punya puncak di DC sebesar 577,07 dengan pita $-3$ dB dari 0 sampai 10,98 Hz, jadi tidak ada potongan bawah sama sekali.

Potongan bawah baru muncul ketika tahap turunan ikut dihitung. Rantai lengkap low-pass kali high-pass kali turunan lima titik memberi penguatan DC $7{,}2 \times 10^{-5}$, puncak 165,06 pada 11,74 Hz, dan pita $-3$ dB dari 5,77 sampai 18,58 Hz. Tahap turunan sendiri bernilai 0,00000 di DC dan naik sampai 0,62247 di 20 Hz.

Gambar 3 di halaman 232 mendukung pembacaan ini. Kurvanya naik dari sekitar $-60$ dB di 0,1 Hz, memuncak dekat 0 dB di sekitar 10 Hz, lalu turun. Caption-nya menyebut 3 dB bandwidth 5 sampai 11 Hz. Kurva naik dari frekuensi rendah itu tidak bisa dihasilkan oleh pasangan low-pass kali high-pass saja.

Konsekuensi praktis: pembuangan baseline wander dan DC di rangkaian Pan-Tompkins berasal dari tahap turunan, bukan dari persamaan (6). Kalau tim memasang dua tahap pertama saja dan mengharapkan baseline hilang, itu tidak akan terjadi.

## 14. Catatan perangkat keras

1. Rekursinya satu pengurangan, $y[n] = d[n] - y[n-1]$. Satu register dan satu subtractor cukup.
2. $d[n]$ butuh tiga operasi: geser lima bit untuk $32x[n-16]$, kurangi $x[n]$, tambah $x[n-32]$. Total empat operasi per sampel dan nol pengali.
3. Memori state 33 kata: 32 untuk $x$ dan 1 untuk $y$, sekitar 66 byte per kanal pada 16 bit.
4. Kutub di $z = -1$ membuat keluaran bergantian selamanya. Dalam kaskade Pan-Tompkins ini tidak menyimpang karena tapis low-pass punya nol di $z = -1$ dan $z = +1$. Terukur: high-pass sendiri di 100 Hz bernilai $2{,}6 \times 10^{17}$, sedangkan kaskadenya $2{,}9 \times 10^{-5}$. Urutan yang benar adalah high-pass dulu, lalu low-pass, seperti di makalah.
5. Pembatalan itu eksak hanya di aljabar. Di fixed-point akan tersisa ripple Nyquist, jadi sediakan margin akumulator dan uji dengan masukan DC selama beberapa ribu sampel.
6. Headroom: penguatan 32 berarti 5 bit, dan low-pass menyusul 5,17 bit. Untuk ADC 12 bit, state high-pass butuh sekitar 17 bit dan state low-pass sekitar 18 bit sebelum margin.

## 15. Perbandingan dengan dokumen low-pass

| Besaran | Low-pass, persamaan (3) | High-pass, persamaan (6) |
|---|---|---|
| Penguatan DC tahap | 36 | 16, sedangkan makalah menyebut 32 sebagai koefisien |
| Tunda | 5 sampel, makalah menulis 6 | 16 sampel, cocok dengan makalah |
| Kutub | ganda di $z = 1$, dibatalkan pembilang | tunggal di $z = -1$, dibatalkan kaskade |
| Nol di lingkaran satuan | ada, di kelipatan $f_s/6$ | tidak ada |
| Titik $-3$ dB sendiri | 10,78 Hz pada $f_s = 200$ Hz | tidak ada, respons naik monoton |
| Pertumbuhan bit | 5,17 bit | 5 bit |
| State | 14 kata | 33 kata |
| Bentuk setara | dua rata-rata bergerak panjang enam bertingkat | akumulator dikurangi jumlah bergantian 32 tap |

## 16. Rujukan

1. Pan J, Tompkins WJ. *A Real-Time QRS Detection Algorithm.* IEEE Transactions on Biomedical Engineering, 1985, BME-32(3):230-236. DOI 10.1109/TBME.1985.325532. Persamaan (4), (5), dan (6) ada di halaman 232, dan dibaca langsung dari salinan PDF di `~/.hermes/cache/scratch/explore/pan-tompkins-1985.pdf`.
2. Salinan penuh naskah: https://www.robots.ox.ac.uk/~gari/teaching/cdt/A3/readings/ECG/Pan+Tompkins.pdf
3. Cermin cadangan: https://people.ece.cornell.edu/land/courses/ece5030/labs/s2014/Pan_Tompkins.pdf
4. Dokumen pendamping: [[00 - low-pass-filter-equation|low-pass-filter-equation]]
