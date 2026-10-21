# Low-Pass Filter Equation

Catatan turunan lengkap untuk tapis low-pass rekursif Pan-Tompkins beserta contoh soal dan jawabannya. Semua persamaan ditulis dalam LaTeX dan dirender Obsidian. Semua angka di dokumen ini dihitung dengan Python, dan notebook pendampingnya ada di `nabdha-afib-lite/model/math-equation-afib/00 - low-pass-filter-equation.ipynb`.

Tujuan dokumen ini: setelah membacanya, Anda bisa menurunkan fungsi alih dari persamaan bedanya, menjelaskan mengapa persamaan itu bisa disederhanakan, dan menghitung keluarannya dengan tangan.

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
| $\delta[n]$ | impuls satuan | 1 di $n = 0$, 0 di tempat lain |
| $u[n]$ | langkah satuan | 1 untuk $n \ge 0$ |
| $r[n]$ | persegi panjang panjang enam | 1 untuk $0 \le n \le 5$ |
| $h[n]$ | tanggapan impuls | keluaran bila masukan adalah $\delta[n]$ |

Penulisan $x(nT)$ dan $x[n]$ menyatakan hal yang sama. $T$ hanya skala waktu, jadi dokumen ini memakai $x[n]$ supaya persamaannya pendek.

## 2. Persamaan beda dan fungsi alih

Persamaan aslinya:

$$
y[n] = 2y[n-1] - y[n-2] + x[n] - 2x[n-6] + x[n-12]
$$

Tiga suku pertama memakai keluaran lama, jadi itu umpan balik. Dua suku terakhir memakai masukan lama, jadi itu umpan maju. Tidak ada pengali di dalamnya, hanya penjumlahan dan penggeseran.

Transformasi z dengan definisi $X(z) = \sum_n x[n]z^{-n}$ dan sifat tunda $x[n-k] \leftrightarrow z^{-k}X(z)$ memberi

$$
Y(z) = 2z^{-1}Y(z) - z^{-2}Y(z) + X(z) - 2z^{-6}X(z) + z^{-12}X(z)
$$

Kumpulkan $Y$ di kiri dan $X$ di kanan:

$$
Y(z)\left(1 - 2z^{-1} + z^{-2}\right) = X(z)\left(1 - 2z^{-6} + z^{-12}\right)
$$

Maka

$$
H(z) = \frac{Y(z)}{X(z)} = \frac{1 - 2z^{-6} + z^{-12}}{1 - 2z^{-1} + z^{-2}}
$$

Penyebut berasal dari umpan balik, pembilang dari umpan maju. Persamaan beda dan fungsi alih ini barang yang sama, hanya ditulis berbeda.

## 3. Penyederhanaan, tiga langkah

**Langkah pertama, kenali bentuk kuadrat.** Dengan $a = 1$ dan $b = z^{-6}$, identitas $(a-b)^2 = a^2 - 2ab + b^2$ memberi

$$
1 - 2z^{-6} + z^{-12} = \left(1 - z^{-6}\right)^2
$$

Dengan $a = 1$ dan $b = z^{-1}$, penyebutnya menjadi

$$
1 - 2z^{-1} + z^{-2} = \left(1 - z^{-1}\right)^2
$$

**Langkah kedua, pakai deret geometri.** Untuk $N = 6$ berlaku

$$
1 - z^{-6} = \left(1 - z^{-1}\right)\left(1 + z^{-1} + z^{-2} + z^{-3} + z^{-4} + z^{-5}\right)
$$

Buktinya dengan mengalikan: suku di dalam kurung saling menghapus kecuali suku pertama dan terakhir. Secara umum $1 - z^{-N} = \left(1 - z^{-1}\right)\sum_{k=0}^{N-1} z^{-k}$.

**Langkah ketiga, batalkan.** Faktor $1 - z^{-1}$ muncul di pembilang dan penyebut, jadi keduanya hilang:

$$
H(z) = \frac{\left(1 - z^{-6}\right)^2}{\left(1 - z^{-1}\right)^2}
= \left(\frac{1 - z^{-6}}{1 - z^{-1}}\right)^2
= \left(\sum_{k=0}^{5} z^{-k}\right)^2
$$

Inilah jawaban mengapa persamaan itu bisa disederhanakan. Umpan balik adalah jumlah berjalan berganda, umpan maju adalah selisih kedua jendela enam sampel, dan keduanya saling membatalkan. Yang tersisa: dua rata-rata bergerak panjang enam yang bertingkat.

## 4. Akibat penyederhanaan

**Tanggapan impuls.** Karena $H(z) = H_1(z)^2$ dengan $H_1(z) = \sum_{k=0}^{5} z^{-k}$, maka $h$ adalah konvolusi dua persegi panjang, $h = r * r$:

$$
h[n] = \begin{cases} n+1, & 0 \le n \le 5 \\ 11-n, & 6 \le n \le 10 \\ 0, & \text{lainnya} \end{cases}
$$

Jadi $h = 1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1$. Bentuk tertutup ini sudah saya bandingkan dengan rekursinya, dan keduanya identik. Karena $h[n]$ berhingga, filter ini sebenarnya FIR, meskipun persamaannya terlihat rekursif. Dua pole di $z = 1$ dibatalkan tepat oleh dua nol dari pembilang.

**Penguatan DC.** Substitusi pada bentuk yang sudah disederhanakan, bukan pada bentuk rasio:

$$
H(1) = \left(\sum_{k=0}^{5} 1\right)^2 = 6^2 = 36
$$

Jalan kedua: jumlahkan tanggapan impulsnya, $\sum_n h[n] = 36$. Dua jalan, satu angka.

**Nol frekuensi.** Pembilang nol ketika $z^6 = 1$, yaitu $z_k = e^{j2\pi k/6}$, sehingga nolnya ada di

$$
f_k = \frac{k f_s}{6}
$$

**Besar tanggapan frekuensi.** Substitusi $z = e^{j\omega}$ dan identitas $\left|1 - e^{-j\theta}\right| = 2\sin(\theta/2)$ memberi bentuk tertutup

$$
\left|H(e^{j\omega})\right| = \left(\frac{\sin(3\omega)}{\sin(\omega/2)}\right)^2
$$

## 5. Angka terukur pada dua frekuensi sampling

Semua angka di tabel ini hasil perhitungan, bukan kutipan.

| Besaran | $f_s = 200$ Hz | $f_s = 250$ Hz |
|---|---|---|
| Penguatan DC | 36,00 | 36,00 |
| Penguatan 5 Hz | 33,48 | 34,37 |
| Penguatan 15 Hz | 17,90 | 23,32 |
| Titik $-3$ dB | **10,78 Hz** | **13,47 Hz** |
| Penguatan 50 Hz | 2,00 | 1,00 |
| Penolakan 50 Hz | 25,11 dB | 31,13 dB |
| Nol pertama | 33,33 Hz | 41,67 Hz |
| Nol berikutnya | 66,67, 100, 133,33, 166,67 Hz | 83,33, 125, 166,67, 208,33 Hz |

Dua hal penting untuk rancangan AFIB-LITE. Pertama, koefisien yang sama menghasilkan titik potong yang berbeda ketika frekuensi sampling berubah, dari 10,78 Hz menjadi 13,47 Hz, jadi pita lolos melebar 25 persen. Kedua, penolakan jala-jala justru membaik, dari 25,11 dB menjadi 31,13 dB, karena 50 Hz berpindah dari $f_s/4$ ke $f_s/5$. Pada 250 Hz, $\omega = 2\pi/5$, sehingga $\sin(3\omega) = -\sin(\pi/5)$ dan $\sin(\omega/2) = \sin(\pi/5)$, dan rasionya tepat 1.

## 6. Contoh soal dan jawaban

### Soal A, masukan impuls

Masukan $x[n] = \delta[n]$. Bagian umpan majunya menjadi

$$
w[n] = x[n] - 2x[n-6] + x[n-12] = \delta[n] - 2\delta[n-6] + \delta[n-12]
$$

Umpan balik adalah jumlah berjalan berganda dari $w$, sehingga $y[n] = \sum_{i=0}^{n}\sum_{j=0}^{i} w[j]$. Karena $\sum\sum\delta = n+1$ untuk $n \ge 0$:

$$
y[n] = \begin{cases} n+1, & 0 \le n \le 5 \\ (n+1) - 2(n-5) = 11-n, & 6 \le n \le 11 \\ (n+1) - 2(n-5) + (n-11) = 0, & n \ge 12 \end{cases}
$$

Bentuk ini menjelaskan setiap baris tabel hitung tangan. Baris $n = 6$ memberi $11-6 = 5$, baris $n = 8$ memberi $11-8 = 3$, dan mulai $n = 12$ semua suku saling menghapus sehingga keluarannya nol.

### Soal B, masukan pulsa enam sampel

Masukan $x[n] = u[n] - u[n-6] = r[n]$. Maka

$$
y[n] = (h * x)[n] = (r * r * r)[n]
$$

yaitu konvolusi tiga persegi panjang panjang enam. Di datarannya, keluaran adalah jumlah enam nilai $h$ berturut-turut di sekitar puncak:

$$
y_{\text{dataran}} = \sum_{k=3}^{8} h[k] = 4 + 5 + 6 + 5 + 4 + 3 = 27
$$

dan nilai sebelum dataran:

$$
y[5] = \sum_{k=0}^{5} h[k] = 1 + 2 + 3 + 4 + 5 + 6 = 21
$$

Kedua angka itu muncul di tabel hitung tangan, dan sekarang Anda bisa menurunkannya, bukan sekadar menghitungnya.

### Soal C, dua frekuensi yang bisa dihitung tangan

**Pada $f = f_s/6$**, yaitu 33,33 Hz untuk $f_s = 200$ Hz, maka $\omega = \pi/3$ dan $3\omega = \pi$, sehingga $\sin(3\omega) = 0$ dan

$$
\left|H\right| = 0
$$

**Pada $f = f_s/4$**, yaitu 50 Hz, maka $\omega = \pi/2$, sehingga $\sin(3\omega) = \sin(3\pi/2) = -1$ dan $\sin(\omega/2) = \sin(\pi/4) = \sqrt{2}/2$:

$$
\left|H\right| = \left(\frac{1}{\sqrt{2}/2}\right)^2 = \left(\sqrt{2}\right)^2 = 2
$$

Angka ini sama dengan hasil numerik, yaitu 2,000000. Penolakan 50 Hz sebesar 25,11 dB karena itu bisa diturunkan di atas kertas tanpa kalkulator.

**Titik $-3$ dB** diperoleh dari $\left(\sin(3\omega)/\sin(\omega/2)\right)^2 = 36/\sqrt{2} = 25{,}46$, yang memberi $\omega \approx 0{,}339$ rad, sehingga

$$
f = \frac{\omega f_s}{2\pi} \approx 10{,}78 \ \text{Hz}
$$

Itulah asal angka "sekitar 11 Hz" di makalah.

## 7. Tunda filter

Tunda grup satu tahap rata-rata bergerak panjang $N$ pada DC adalah $(N-1)/2$. Untuk $N = 6$ nilainya 2,5 sampel, dan dua tahap bertingkat memberi **5 sampel**. Angka itu cocok dengan puncak $h[n]$ di indeks 5. Makalah menulis tunda 6 sampel, dan selisih satu sampel ini tidak mengubah perilaku filter secara berarti, tetapi baik untuk Anda ketahui ketika membandingkan posisi puncak.

## 8. Mengapa aritmetika fixed-point tidak sama dengan aljabar

Pembatalan pole di atas eksak dalam aljabar, tetapi tidak eksak dalam aritmetika terbatas. Kalau Anda menjalankan bentuk rekursif dengan masukan DC sebesar $c$, suku pole menghasilkan komponen yang tumbuh seperti $c \cdot n$, sehingga keluaran merangkak naik tanpa batas. Tiga konsekuensinya:

1. Implementasikan bentuk FIR-nya, yaitu dua rata-rata bergerak panjang enam. Bentuk itu tidak punya umpan balik, jadi keluarannya pasti berhingga.
2. Kalau tetap memakai bentuk rekursif, jangan memberi DC dalam waktu lama. Inilah alasan tahap high-pass dipasang tepat sesudah tahap ini.
3. Sediakan ruang bit untuk penguatan 36, yaitu sekitar $\log_2 36 = 5{,}17$ bit tambahan di atas lebar masukan.

## 9. Hubungan ke rancangan AFIB-LITE

Rancangan tim memakai $f_s = 250$ Hz. Koefisien yang sama memberi titik potong 13,47 Hz, jadi pita 5 sampai 15 Hz yang menjadi target QRS tetap lewat, dan sinyal 15 Hz turun 3,77 dB saja. Penolakan 50 Hz naik ke 31,13 dB. Kalau tim ingin titik potong persis 11 Hz seperti di makalah, koefisien jendelanya harus diubah, bukan frekuensinya saja.

Pada tahap fixed-point, keluaran tapis ini tumbuh 36 kali, jadi akumulator 16 bit bisa meluap untuk masukan 12 bit. Notebook pendamping mengukur selisih bentuk rekursif dan bentuk FIR setelah kuantisasi `int16`, dan angkanya bisa Anda pakai sebagai dasar penentuan lebar bit RTL.

## 10. Rujukan

1. Pan J, Tompkins WJ. *A Real-Time QRS Detection Algorithm.* IEEE Transactions on Biomedical Engineering, 1985, BME-32(3):230-236. DOI 10.1109/TBME.1985.325532. Salinan penuh: https://www.robots.ox.ac.uk/~gari/teaching/cdt/A3/readings/ECG/Pan+Tompkins.pdf
2. Task Force ESC dan NASPE. *Heart rate variability: standards of measurement, physiological interpretation, and clinical use.* European Heart Journal, 1996, 17(3):354-381. DOI 10.1093/oxfordjournals.eurheartj.a014868
3. Dash S, Chon KH, Lu S, Raeder EA. *Automatic real time detection of atrial fibrillation.* Annals of Biomedical Engineering, 2009, 37(9):1701-1709. DOI 10.1007/s10439-009-9740-z
4. Notebook pendamping: `nabdha-afib-lite/model/math-equation-afib/00 - low-pass-filter-equation.ipynb`
