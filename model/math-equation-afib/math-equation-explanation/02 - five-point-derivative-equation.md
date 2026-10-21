# Five-Point Derivative Equation

Catatan turunan lengkap untuk tahap turunan lima titik Pan-Tompkins, persamaan (7), (8), dan (9) halaman 233, beserta contoh soal dan jawabannya. Semua persamaan ditulis dalam LaTeX dan dirender Obsidian. Semua angka di dokumen ini dihitung dengan Python, bukan dikutip dari ingatan. Notebook pendampingnya ada di `nabdha-afib-lite/model/math-equation-afib/02 - five-point-derivative-equation.ipynb`, dan dokumen pendampingnya adalah [[00 - low-pass-filter-equation|low-pass-filter-equation]] serta [[01 - high-pass-filter-equation|high-pass-filter-equation]].

Tujuan dokumen ini: setelah membacanya, Anda bisa menurunkan fungsi alih dari persamaan bedanya, menjelaskan mengapa penguatan DC-nya nol dan mengapa keluarannya bipolar, menghitung keluarannya dengan tangan, dan menjelaskan mengapa tahap inilah yang membuang baseline wander di rantai Pan-Tompkins.

## 1. Variabel dan notasi

| Simbol | Arti | Keterangan |
|---|---|---|
| $n$ | indeks sampel | bilangan bulat, $n \ge 0$ |
| $T$ | periode sampling | $T = 1/f_s$ |
| $f_s$ | frekuensi sampling | 200 Hz di makalah, 250 Hz di rancangan AFIB-LITE |
| $x[n]$ | sampel masukan ke-$n$ | ditulis $x(nT)$ di makalah, yaitu sinyal setelah bandpass |
| $y[n]$ | sampel keluaran ke-$n$ | ditulis $y(nT)$ di makalah |
| $z^{-1}$ | operator tunda satu sampel | $z^{-1}X(z) \leftrightarrow x[n-1]$ |
| $H(z)$ | fungsi alih | $H(z) = Y(z)/X(z)$ |
| $u$ | frekuensi ternormalisasi | $u = \omega T = 2\pi f / f_s$ |
| $\delta[n]$ | impuls satuan | 1 di $n = 0$, 0 di tempat lain |
| $h[n]$ | tanggapan impuls | keluaran bila masukan adalah $\delta[n]$ |

Angka-angka penting ditulis tebal: **lima** adalah jumlah tap, **nol** adalah penguatan DC-nya, **dua** adalah tundanya dalam sampel, dan **41,6667 Hz** adalah titik puncak tanggapannya pada $f_s = 250$ Hz.

## 2. Persamaan beda dan fungsi alih

Persamaan aslinya, persamaan (9) di makalah, ditulis dalam bentuk terpusat sehingga memakai satu sampel yang belum datang di kiri dan di kanan:

$$
y(nT) = \frac{1}{8T}\Big[-x(nT - 2T) - 2x(nT - T) + 2x(nT + T) + x(nT + 2T)\Big]
$$

Empat koefisiennya adalah minus satu, minus dua, plus dua, dan plus satu, dengan pembagi delapan. Perhatikan urutannya: dua suku negatif di kiri dan dua suku positif di kanan, jadi tanda pada suku pertama dan keempat berlawanan dengan suku kedua dan ketiga.

Bentuk itu tidak bisa langsung dipasang di perangkat keras yang bekerja sampel per sampel, karena butuh sampel yang belum datang. Substitusi $m = n + 2$ menggeser seluruh indeks dan memberi bentuk kausal:

$$
y[n] = \frac{1}{8T}\Big(x[n] + 2x[n-1] - 2x[n-3] - x[n-4]\Big)
$$

Pergeseran itu menambah tunda dua sampel, dan angka dua sampel itulah yang ditulis makalah di bawah persamaan (9). Dalam implementasi, faktor $T$ tidak dibawa karena hanya mengubah skala waktu, bukan bentuk tanggapan.

Transformasi z dengan definisi $X(z) = \sum_n x[n]z^{-n}$ dan sifat tunda $x[n-k] \leftrightarrow z^{-k}X(z)$ memberi

$$
Y(z) = \frac{1}{8T}\Big(X(z) + 2z^{-1}X(z) - 2z^{-3}X(z) - z^{-4}X(z)\Big)
$$

Kumpulkan $X$:

$$
H(z) = \frac{Y(z)}{X(z)} = \frac{1}{8T}\Big(1 + 2z^{-1} - 2z^{-3} - z^{-4}\Big) = \frac{B(z)}{A(z)}
$$

Penyebutnya $A(z) = 1$, jadi tidak ada umpan balik dan tahap ini FIR murni. Persamaan (7) di makalah adalah bentuk terpusat yang sama, $\frac{1}{8T}\left(-z^{-2} - 2z^{-1} + 2z + z^{2}\right)$, hanya dengan titik pusatnya di $z^{0}$.

## 3. Tabel koefisien

Bentuk terpusat memakai indeks yang belum datang, sedangkan bentuk kausal memakai riwayat. Keduanya barang yang sama:

| Sampel, bentuk terpusat | Sampel, bentuk kausal | Koefisien | Nilai pecahan | Koefisien bulat |
|---|---|---|---|---|
| $x(nT+2T)$ | $x[n]$ | $+1$ | $0{,}125$ | $1$ |
| $x(nT+T)$ | $x[n-1]$ | $+2$ | $0{,}25$ | $2$ |
| $x(nT)$ | $x[n-2]$ | $0$ | $0$ | $0$ |
| $x(nT-T)$ | $x[n-3]$ | $-2$ | $-0{,}25$ | $-2$ |
| $x(nT-2T)$ | $x[n-4]$ | $-1$ | $-0{,}125$ | $-1$ |
| Jumlah | Jumlah | $0$ | $0$ | $0$ |

Baris terakhir adalah inti seluruh dokumen. Jumlah koefisiennya nol, dan itulah penguatan DC-nya. Turunan tidak melihat nilai rata-rata, hanya perubahannya, dan itu sebabnya baseline wander terbuang di tahap ini.

Kernelnya juga antisimetris: koefisien di indeks 0 dan 4 saling berlawanan, koefisien di indeks 1 dan 3 saling berlawanan, dan koefisien di indeks 2 nol. Karena antisimetris dan jumlahnya nol, fase-nya linear eksak, tundanya tepat dua sampel, dan penguatannya nol di dua titik sekaligus, yaitu dc dan frekuensi Nyquist.

## 4. Respons amplitudo, persamaan (8)

Substitusi $z = e^{ju}$ dengan $u = \omega T$. Faktorkan bentuk terpusat supaya simetrinya terlihat:

$$
B(e^{ju}) = \frac{1}{8}e^{-j2u}\Big(e^{j2u} + 2e^{ju} - 2e^{-ju} - e^{-j2u}\Big) = \frac{1}{8}e^{-j2u}\Big(4j\sin(u) + 2j\sin(2u)\Big)
$$

Modulusnya, dengan $e^{-j2u}$ yang modulusnya satu:

$$
\big|H(e^{ju})\big| = \frac{1}{8}\big|4\sin(u) + 2\sin(2u)\big| = \frac{1}{4}\Big(\sin(2u) + 2\sin(u)\Big)
$$

Kedua faktor di dalam tanda kurung tidak pernah negatif untuk $0 \le u \le \pi$, jadi tanda harga mutlak boleh dibuka. Kembalikan faktor $\frac{1}{T}$ milik makalah dan hasilnya adalah persamaan (8):

$$
\big|H(\omega T)\big| = \frac{1}{4T}\Big[\sin(2\omega T) + 2\sin(\omega T)\Big]
$$

Bentuk itu setara dengan tiga tulisan lain yang berguna:

$$
\sin(2u) + 2\sin(u) = 2\sin(u)\Big(1 + \cos(u)\Big) = 4\sin\left(\frac{u}{2}\right)\cos^{3}\left(\frac{u}{2}\right)
$$

Tulisan terakhir tidak mengandung pengurangan dua suku yang hampir nol, jadi itulah yang dipakai untuk perhitungan numerik di dekat frekuensi Nyquist, sedangkan tulisan pertama dipakai untuk menurunkan titik puncaknya.

Perilaku di ujung pita. Di dc, $u = 0$, sehingga $\big|H\big| = 0$. Di frekuensi Nyquist, $u = \pi$, sehingga $\sin(2\pi) + 2\sin(\pi) = 0$ dan $\big|H\big| = 0$ lagi. Untuk $u$ kecil, $\sin(2u) \approx 2u$ dan $\sin(u) \approx u$, sehingga

$$
\big|H\big| \approx \frac{1}{4T}\left(4\omega T\right) = \omega = 2\pi f
$$

yaitu modulus turunan ideal dalam radian per detik. Itulah sebabnya makalah menyebut tanggapan tahap ini hampir linear antara dc dan 30 Hz.

## 5. Turunan tanggapan amplitudo, titik puncak, dan tunda

Titik puncak dicari dari bentuk kosinus. Misalkan

$$
G(u) = \sin(u)\Big(1 + \cos(u)\Big) = \sin(u) + \tfrac{1}{2}\sin(2u)
$$

Turunannya

$$
G'(u) = \cos(u) + \cos(2u) = 2\cos^{2}(u) + \cos(u) - 1
$$

Nol ketika $\cos(u) = \frac{1}{2}$ atau $\cos(u) = -1$. Akar pertama memberi puncak, akar kedua memberi nol. Karena $u = 2\pi f / f_s$:

$$
u = \frac{\pi}{3} \quad\Longrightarrow\quad f = \frac{f_s}{6}
$$

Pada $f_s = 250$ Hz titik puncaknya **41,6667 Hz**, dan pada $f_s = 200$ Hz titik puncaknya **33,3333 Hz**. Nilai puncaknya:

$$
\big|H\big|_{\max} = \frac{1}{2}\sin\left(\frac{\pi}{3}\right)\left(1 + \cos\left(\frac{\pi}{3}\right)\right) = \frac{1}{2}\cdot\frac{\sqrt{3}}{2}\cdot\frac{3}{2} = \frac{3\sqrt{3}}{8} \approx 0{,}6495191
$$

Dalam skala persamaan (8) nilai itu dikali $f_s$, sehingga menjadi 162,3798 pada 250 Hz dan 129,9038 pada 200 Hz.

Tunda tahap ini tepat dua sampel, dan itu bisa dibuktikan tanpa gambar: kernel antisimetris berorde empat selalu punya tunda grup sama dengan setengah ordenya. Pemeriksaan numerik dari beda fase memberi tunda grup 2,0000000 sampel dengan simpangan terbesar 4,4 kali 10 pangkat minus 9, jadi kalimat makalah di bawah persamaan (9) terbukti.

## 6. Letak nol dan kutub

Penyebutnya satu, jadi tidak ada kutub sama sekali. Nol adalah akar pembilang. Kalikan pembilang dengan $8z^{4}$ untuk menghilangkan pangkat negatif:

$$
8z^{4} \cdot \frac{1}{8}\Big(1 + 2z^{-1} - 2z^{-3} - z^{-4}\Big) = z^{4} + 2z^{3} - 2z - 1
$$

Polinom itu dapat difaktorkan persis, dan faktorisasinya diperiksa suku demi suku di notebook:

$$
z^{4} + 2z^{3} - 2z - 1 = (z - 1)(z + 1)^{3}
$$

Jadi keempat nolnya berada tepat di lingkaran satuan:

| Letak | Multiplisitas | Frekuensi | Akibat |
|---|---|---|---|
| $z = +1$ | satu | dc, 0 Hz | penguatan DC nol, baseline wander terbuang |
| $z = -1$ | tiga | frekuensi Nyquist, 125 Hz pada $f_s = 250$ Hz | derau frekuensi tinggi diredam kuat |
| kutub | nol | tidak ada | tahap ini FIR, keluarannya selalu berhingga |

Nol lipat tiga di Nyquist itu penting untuk tahap sesudahnya. Tahap pengkuadratan mengubah amplitudo menjadi kuadratnya, sehingga komponen yang amplitudonya besar akan mendominasi. Karena tahap turunan sudah menekan Nyquist dengan nol lipat tiga, masukan ke pengkuadrat tidak membawa riak Nyquist yang besar. Inilah salah satu alasan rantai Pan-Tompkins tidak meledak meskipun tapis high-pass di depannya punya kutub tepat di $z = -1$.

## 7. Angka terukur pada dua laju sampling

Semua angka di tabel ini hasil perhitungan, bukan kutipan. Kolom "per sampel" adalah modulus vektor koefisien bulat, dan kolom "persamaan (8)" adalah angka yang sama dikali $f_s$ karena persamaan (8) membawa faktor $\frac{1}{T}$.

| Besaran | $f_s = 200$ Hz | $f_s = 250$ Hz |
|---|---|---|
| Penguatan DC | 0 | 0 |
| Penguatan di frekuensi Nyquist | 0 | 0 |
| Titik puncak | **33,3333 Hz** | **41,6667 Hz** |
| Penguatan puncak, per sampel | 0,6495191 | 0,6495191 |
| Penguatan puncak, persamaan (8) | 129,9038 | 162,3798 |
| Penguatan 5 Hz, per sampel | 0,1554715 | 0,1248391 |
| Penguatan 5 Hz, persamaan (8) | 31,0943 | 31,2098 |
| Penguatan 15 Hz, per sampel | 0,4292495 | 0,3551991 |
| Penguatan 15 Hz, persamaan (8) | 85,8499 | 88,7998 |
| Rasio penguatan 15 Hz terhadap 5 Hz | 2,7610 | 2,8453 |
| Tunda grup | 2 sampel | 2 sampel |

Dua hal untuk rancangan AFIB-LITE. Pertama, titik puncak turun dari 41,6667 Hz ke 33,3333 Hz ketika laju diturunkan dari 250 Hz ke 200 Hz, tetapi penguatan puncaknya tidak berubah sama sekali karena bentuk kernelnya sama; yang berpindah hanya letaknya, sebab titik puncak selalu di $f_s/6$. Kedua, pita 5 sampai 15 Hz justru mendapat penguatan sedikit berbeda antar laju, dan pada 250 Hz penguatan 5 Hz lebih kecil daripada pada 200 Hz. Tidak ada penolakan pita di dalam 5 sampai 30 Hz, jadi tahap turunan ini tidak pernah memotong pita QRS.

## 8. Contoh hitung tangan A, tanggapan impuls

Masukan $x[0] = 8$ dan $x[n] = 0$ untuk $n > 0$. Amplitudo delapan dipilih supaya keluarannya bilangan bulat dan tabelnya bisa dicocokkan persis. Setiap baris adalah satu sampel, setiap kolom adalah satu suku persamaan beda kausal:

| $n$ | $x[n]$ | $2x[n-1]$ | $0 \cdot x[n-2]$ | $-2x[n-3]$ | $-x[n-4]$ | jumlah | $y[n]$ |
|---|---|---|---|---|---|---|---|
| 0 | 8 | 0 | 0 | 0 | 0 | 8 | **1** |
| 1 | 0 | 16 | 0 | 0 | 0 | 16 | **2** |
| 2 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| 3 | 0 | 0 | 0 | $-16$ | 0 | $-16$ | **$-2$** |
| 4 | 0 | 0 | 0 | 0 | $-8$ | $-8$ | **$-1$** |
| 5 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |

Baris $n = 3$ dibaca begini: $x[3]$ dan $x[2]$ nol, sedangkan $x[0] = 8$ muncul lagi sebagai $-2x[3-3] = -16$. Jadi keluaran turun menjadi minus dua. Setelah $n = 4$ semua suku nol dan keluaran berhenti di nol. Bentuk tertutupnya, dan pemeriksaan di notebook memakai masukan impuls satuan sehingga langsung memberi koefisiennya:

$$
h[n] = \frac{1}{8}\Big(\delta[n] + 2\delta[n-1] - 2\delta[n-3] - \delta[n-4]\Big)
$$

Jadi $h = 0{,}125, \ 0{,}25, \ 0, \ -0{,}25, \ -0{,}125$ dan $\sum_n h[n] = 0$. Jalan kedua untuk penguatan DC: jumlahkan tanggapan impulsnya, hasilnya nol. Dua jalan, satu angka. Dukungannya lima sampel, dan itu menjelaskan mengapa tahap ini hanya butuh empat register riwayat masukan.

## 9. Contoh hitung tangan B, satu pulsa segitiga QRS

Masukan kedua adalah satu pulsa segitiga, yaitu bentuk kasar satu kompleks QRS sesudah bandpass. Nilainya dibuat kelipatan delapan supaya keluarannya bilangan bulat:

$$
x[4] = 8, \quad x[5] = 16, \quad x[6] = 24, \quad x[7] = 16, \quad x[8] = 8
$$

Di luar rentang itu nilainya nol. Pulsa ini simetris terhadap sampel $n = 6$:

| $n$ | $x[n]$ | $2x[n-1]$ | $0 \cdot x[n-2]$ | $-2x[n-3]$ | $-x[n-4]$ | jumlah | $y[n]$ |
|---|---|---|---|---|---|---|---|
| 4 | 8 | 0 | 0 | 0 | 0 | 8 | **1** |
| 5 | 16 | 16 | 0 | 0 | 0 | 32 | **4** |
| 6 | 24 | 32 | 0 | 0 | 0 | 56 | **7** |
| 7 | 16 | 48 | 0 | $-16$ | 0 | 48 | **6** |
| 8 | 8 | 32 | 0 | $-32$ | $-8$ | 0 | **0** |
| 9 | 0 | 16 | 0 | $-48$ | $-16$ | $-48$ | **$-6$** |
| 10 | 0 | 0 | 0 | $-32$ | $-24$ | $-56$ | **$-7$** |
| 11 | 0 | 0 | 0 | $-16$ | $-16$ | $-32$ | **$-4$** |
| 12 | 0 | 0 | 0 | 0 | $-8$ | $-8$ | **$-1$** |

Baris $n = 8$ dibaca begini: sisi turun pulsa mulai masuk, jadi $2x[7] = 32$ dikurangi $-2x[5] = -32$ dan $-x[4] = -8$, jumlahnya tepat nol. Keluarannya adalah

$$
y[4], \ y[5], \ \dots, \ y[12] = \Big(1, \ 4, \ 7, \ 6, \ 0, \ -6, \ -7, \ -4, \ -1\Big)
$$

Jumlahnya nol, puncak positifnya tujuh di $n = 6$ pada sampel kemiringan naik terbesar, dan puncak negatifnya minus tujuh di $n = 10$ pada sampel kemiringan turun terbesar. Keluarannya antisimetris terhadap $n = 8$, yaitu $y[8-j] = -y[8+j]$.

Bentuk bipolar itu bukan cacat, melainkan sifat turunan: sisi naik memberi nilai positif dan sisi turun memberi nilai negatif. Tanpa tahap pengkuadratan sesudahnya, kedua sisi itu akan saling menghapus ketika diintegrasikan, dan satu kompleks QRS akan terlihat seperti tidak ada. Inilah alasan urutan rantai Pan-Tompkins tidak boleh ditukar.

## 10. Kasus sebelum dan sesudah pada sinyal QRS 250 Hz

Sinyal di sini adalah keluaran bandpass, bukan ECG mentah, karena itulah masukan tahap turunan. ECG disintesis dari gelombang P, Q, R, S, T berbentuk Gaussian pada 70 bpm dan 250 Hz, lalu dilewatkan low-pass koefisien 1 sampai 6 dan high-pass rekursif, keduanya dinormalisasi ke penguatan DC satu.

| Besaran | Sebelum turunan | Sesudah turunan |
|---|---|---|
| Amplitudo maksimum | 0,7141 | 0,1066 |
| Nilai puncak ke puncak | 0,7339 | 0,2038 |
| Rata-rata | 0,0618 | $-6{,}9 \times 10^{-20}$ |
| Jumlah seluruh sampel | tidak dicetak | 0 dibanding jumlah nilai mutlaknya |
| Jumlah sampel positif | tidak dicetak | 283 |
| Jumlah sampel negatif | tidak dicetak | 605 |

Empat hal yang bisa dibaca dari tabel itu. Pertama, rata-rata keluaran turunan nol sampai ketelitian mesin, sedangkan masukannya punya rata-rata 0,0618; jadi tahap ini memang membuang komponen searah pada level sinyal, bukan hanya pada level koefisien. Kedua, keluaran turunan hadir dengan kedua tanda. Ketiga, rasio amplitudo maksimum keluaran terhadap masukan adalah 0,1493, jauh lebih kecil daripada penguatan puncak 0,6495, karena puncak tanggapan ada di 41,6667 Hz sedangkan energi QRS berada di 5 sampai 15 Hz. Keempat, puncak keluaran jatuh **dua sampel** dari sampel kemiringan terbesar masukan, yaitu persis tunda tahap ini.

Ada satu angka lagi yang berguna untuk membaca gambar: tunda bandpass di depan tahap turunan pada 10 Hz adalah 19,8644 sampel, terdiri dari 5,0000 sampel dari low-pass dan 14,8644 sampel dari high-pass. Itulah sebabnya puncak pada panel keluaran bergeser ke kanan terhadap puncak R pada ECG bersih, padahal terhadap kemiringan terbesar pada masukannya sendiri puncaknya menempel dalam dua sampel. Kalau tim mengukur letak puncak R dari keluaran turunan, tunda 19,8644 sampel itu harus dikurangi sebelum dihitung sebagai waktu.

## 11. Catatan fixed-point, konvensi terkunci

Konvensi di bawah ini dikunci di [[afib-lite/afib-rtl/34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown]], bagian 3.7, dan angkanya diukur pada rekaman AFDB `04015`, 30 menit, 450.000 sampel. Masukan rantai adalah rentang plus minus 5 mV pada 12 bit signifikan, dijepit pada plus minus 2047 hitungan, lalu diletakkan di depan kata 16 bit dengan nilai digeser ke kiri 4 bit.

| Tahap | Nilai maksimum terukur | Lebar minimum | Lebar yang dipakai | Catatan |
|---|---|---|---|---|
| Masukan | 32.752 hitungan | 16 bit | 16 bit | penjepitan 2047, geser kiri 4 bit |
| Low-pass, koefisien 1 sampai 6 | 1.179.072 hitungan | 22 bit | 28 bit | jumlah koefisien 36, tanpa pengali |
| High-pass, rekursif | 19.286.208 hitungan | 26 bit | 28 bit | koefisien 32 dan 1 dan 1, tahap terlebar di rantai tapis |
| Turunan lima titik | 3.900.266 hitungan | 23 bit | 28 bit | koefisien 1 dan 2 dengan pembagian 8 |
| Turunan sesudah geser kanan 8 bit | 15.236 hitungan | 15 bit | 16 bit | faktor skala ambang 256 |

Pilihan penggeseran sesudah turunan diukur satu per satu:

| Geser $s$ | Faktor skala $2^{s}$ | Nilai maksimum turunan | Lebar minimum |
|---|---|---|---|
| 0 | 1 | 3.900.266 | 23 bit |
| 4 | 16 | 243.767 | 19 bit |
| **8** | **256** | **15.236** | **15 bit** |
| 12 | 4.096 | 953 | 11 bit |

Yang dikunci adalah geser 8, karena itulah titik terkecil yang membuat tahap pengkuadratan dan integrasi sesudahnya muat di kata 32 bit. Akibatnya ambang keputusan dan nilai SPKI serta NPKI harus dibagi dengan faktor skala ambang:

$$
\text{faktor skala ambang} = 2^{s}, \qquad s = 8 \Rightarrow 256
$$

Penggeseran tidak mengubah bentuk gelombang, hanya skalanya, karena pembagiannya pangkat dua.

Tidak ada pengali di tahap ini. Yang ada hanya penjumlahan, pengurangan, dan satu pembagian delapan. Perkalian dengan dua dan dengan satu dipetakan menjadi penggeseran dan penyambungan kabel, jadi nol pengali keras. Karena seluruh koefisiennya bilangan bulat, tidak ada galat kuantisasi koefisien sama sekali.

Keeksakan aritmetika bilangan bulat diperiksa pada potongan 20.000 sampel dari rekaman yang sama, memakai bilangan bulat Python sebagai acuan dan operasi pecahan sebagai pembanding:

| Tahap | Galat relatif, bulat lawan pecahan |
|---|---|
| Low-pass | 0,000e+00 |
| High-pass | 0,000e+00 |
| Pembilang turunan | 0,000e+00 |
| Turunan sesudah geser 8 | 0,000e+00 |

Nolnya eksak, bukan hasil pembulatan, karena setiap nilai antara masih muat persis di bilangan pecahan 64 bit dan pembagian delapan hanya menggeser eksponen. Jumlah sampel yang berbeda sesudah geser kanan 8 bit adalah nol dari 20.000. Satu-satunya sumber galat yang tersisa di seluruh rantai adalah penjepitan masukan, dan itu terukur 402 sampel dari 450.000 karena sinyal AFDB `04015` mencapai 6,435 mV.

## 12. Yang berbeda dari catatan lama

Catatan lama menyebut tahap turunan memuncak sekitar 11,74 Hz dengan penguatan DC sekitar 7 kali 10 pangkat minus 5. Kedua angka itu salah alamat. Yang benar, dan sudah diukur di notebook:

| Klaim catatan lama | Hasil pengukuran | Keterangan |
|---|---|---|
| Titik puncak tahap turunan sekitar 11,74 Hz | **41,6667 Hz** pada $f_s = 250$ Hz | titik puncak selalu di $f_s/6$, yaitu tiga setengah kali lebih tinggi |
| Penguatan DC tahap turunan sekitar $7 \times 10^{-5}$ | **0 eksak** | jumlah koefisiennya nol, jadi penguatan DC harus nol |
| Pita sampai 20 Hz | penguatan masih naik, puncak baru di 41,6667 Hz | pada 20 Hz penguatan baru 0,4520 dari puncak 0,6495 |

Angka 11,74 Hz dan penguatan DC kecil itu bukan milik tahap turunan, melainkan milik **rantai lengkap** low-pass kali high-pass kali turunan. Pada $f_s = 200$ Hz rantai itu memuncak di 11,99 Hz dan pitanya 5,90 sampai 18,91 Hz, jadi angkanya memang dekat sekali. Yang penting: pelabelan per tahap itulah yang selama ini kurang, sama seperti temuan di dokumen [[01 - high-pass-filter-equation|high-pass-filter-equation]] bagian 13, bahwa pembuangan baseline wander datang dari tahap turunan dan bukan dari persamaan (6). Dokumen ini menegaskan hal yang sama dari sisi sebaliknya: tahap turunan memang membuang dc, tetapi puncaknya jauh lebih tinggi daripada 11,74 Hz, dan tidak ada penolakan pita bawah di tahap ini karena kurvanya berangkat dari nol lalu naik monoton sampai 41,6667 Hz.

## 13. Hubungan ke rancangan AFIB-LITE

Rancangan tim memakai $f_s = 250$ Hz dengan 12 bit signifikan dan akumulator tapis 28 bit. Tiga hal yang bisa langsung dipakai:

1. Titik puncak tahap turunan di 41,6667 Hz berada jauh di atas pita QRS 5 sampai 15 Hz, jadi tahap ini tidak memotong pita yang menjadi target triase. Penguatannya di 5 Hz 0,1248 dan di 15 Hz 0,3552 per sampel, naik 2,8453 kali di antara keduanya.
2. Karena penguatan DC-nya nol dan nolnya ada di dc, tahap inilah satu-satunya tahap di rantai yang membuang baseline wander secara eksak. Kalau tim melewatkan tahap ini, baseline tidak akan hilang, sebagaimana diukur di dokumen [[01 - high-pass-filter-equation|high-pass-filter-equation]].
3. Keluarannya bipolar, jadi tahap pengkuadratan harus dipasang tepat sesudahnya. Pembatalan kedua sisi QRS tidak bisa dihindari dengan menggeser tahap turunan ke belakang integrasi.
4. Lebar bit 23 bit tanpa geser dan 15 bit sesudah geser 8 adalah angka yang harus dipakai saat menyusun RTL: akumulator 28 bit yang sudah dikunci menampung keduanya dengan margin, dan keeksakan aritmetika bilangan bulat membuat golden vector testbench bisa dibandingkan eksak, tanpa toleransi.

### Catatan orientasi kernel, dikunci 20 Oktober 2026

Analisis di atas memakai kernel lima tap berorientasi $[1, 2, 0, -2, -1]$, dan
seluruh angka di catatan ini berlaku untuk orientasi itu. Rantai AFIB-LITE
mengimplementasikan orientasi kebalikannya, $[2, 1, 0, -1, -2]$, sehingga angka
muncaknya berbeda dan klaim $f_s/6$ di catatan ini tidak boleh dikutip untuk rantai.

Dihitung ulang secara eksak pada 20 Oktober 2026:

| Besaran | Rantai $[2, 1, 0, -1, -2]$ | Catatan ini $[1, 2, 0, -2, -1]$ |
|---|---|---|
| Letak muncak | $0{,}1379356 f_s$ | tepat $f_s/6$ |
| Muncak pada 250 Hz | **34,4839 Hz** | 41,6667 Hz |
| Muncak pada 200 Hz | **27,5872 Hz** | 33,3333 Hz |
| Penguatan puncak, per sampel | **0,6839538** | 0,6495191 |
| Penguatan DC | 0 | 0 |
| Penguatan di $f_s/6$ | 0,6495191 | 0,6495191 |
| Penguatan di $f_s/4$ | 0,25 | 0,5 |
| Tunda grup | 2 sampel | 2 sampel |

Dua orientasi ini identik pada gain DC nol, pada gain di $f_s/6$, dan pada tunda
grup dua sampel. Yang membedakan hanya letak muncak dan gain di $f_s/4$. Karena
turunan lima titik Pan-Tompkins yang kanonik adalah
$\frac{1}{8}(2x[n] + x[n-1] - x[n-3] - 2x[n-4])$, orientasi yang dipakai rantai
adalah bentuk kanonik itu, dan perubahan orientasi akan menggeser seluruh angka
deteksi yang sudah tervalidasi. Keputusan Aviv pada 20 Oktober 2026: pertahankan
orientasi rantai, dan seluruh angka terukur tetap berlaku.

## 14. Rujukan

1. Pan J, Tompkins WJ. *A Real-Time QRS Detection Algorithm.* IEEE Transactions on Biomedical Engineering, 1985, BME-32(3):230-236. DOI 10.1109/TBME.1985.325532. Persamaan (7), (8), dan (9) ada di halaman 233, dan dibaca langsung dari gambar halaman 600 dpi salinan PDF di `~/.hermes/cache/scratch/explore/pan-tompkins-1985.pdf` karena lapisan teksnya rusak.
2. Salinan penuh naskah: https://www.robots.ox.ac.uk/~gari/teaching/cdt/A3/readings/ECG/Pan+Tompkins.pdf
3. Cermin cadangan: https://people.ece.cornell.edu/land/courses/ece5030/labs/s2014/Pan_Tompkins.pdf
4. Dokumen pendamping: [[00 - low-pass-filter-equation|low-pass-filter-equation]] dan [[01 - high-pass-filter-equation|high-pass-filter-equation]]
5. Notebook pendamping: `nabdha-afib-lite/model/math-equation-afib/02 - five-point-derivative-equation.ipynb`
