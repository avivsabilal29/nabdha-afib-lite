# Squaring and Moving-Window Integrator Equation

Catatan turunan lengkap untuk tahap pengkuadratan persamaan (10) dan tahap integrasi jendela bergerak persamaan (11) Pan-Tompkins halaman 233, beserta contoh soal dan jawabannya. Semua persamaan ditulis dalam LaTeX dan dirender Obsidian. Semua angka di dokumen ini dihitung dengan Python, bukan dikutip dari ingatan. Notebook pendampingnya ada di `nabdha-afib-lite/model/math-equation-afib/03 - squaring-and-moving-window-integrator-equation.ipynb`, dan dokumen pendampingnya adalah [[01 - high-pass-filter-equation|high-pass-filter-equation]] serta [[00 - low-pass-filter-equation|low-pass-filter-equation]].

Tujuan dokumen ini: setelah membacanya, Anda bisa menjelaskan mengapa pengkuadratan dipakai, menurunkan fungsi alih integrator jendela bergerak dari persamaan bedanya, menyebut letak seluruh nolnya, memilih lebar jendela pada laju sampel berapa pun, menghitung keluarannya dengan tangan, dan menjelaskan mengapa integrasi 38 sampel butuh 32 bit pada konvensi fixed-point terkunci.

Dua tahap ini adalah kelanjutan langsung dari rantai yang sudah didokumentasikan. Tahap low-pass dan high-pass membentuk sinyal, tahap turunan menajamkan kemiringan, dan dua tahap di dokumen ini mengubah kemiringan itu menjadi selubung energi yang siap dibandingkan dengan ambang.

## 1. Variabel dan notasi

| Simbol | Arti | Keterangan |
|---|---|---|
| $n$ | indeks sampel | bilangan bulat, $n \ge 0$ |
| $T$ | periode sampling | $T = 1/f_s$ |
| $f_s$ | laju sampling | 200 Hz di makalah, 250 Hz di rancangan AFIB-LITE |
| $N$ | jumlah sampel lebar jendela integrasi | 30 di makalah, 38 di konvensi terkunci |
| $x[n]$ | sampel masukan ke tahap ini | keluaran tahap turunan, ditulis $x(nT)$ di makalah |
| $y[n]$ | sampel keluaran ke tahap ini | ditulis $y(nT)$ di makalah |
| $S[n]$ | akumulator jumlah jendela | jumlah sampel ke-$n$ sampai ke-$(n-N+1)$ |
| $w[n]$ | suku masuk dan keluar jendela | $w[n] = x[n] - x[n-N]$ |
| $z^{-1}$ | operator tunda satu sampel | $z^{-1}X(z) \leftrightarrow x[n-1]$ |
| $H(z)$ | fungsi alih | $H(z) = Y(z)/X(z)$ |
| $\omega$ | frekuensi sudut digital | $\omega = 2\pi f / f_s$ |
| $\delta[n]$ | impuls satuan | 1 di $n = 0$, 0 di tempat lain |
| $r[n]$ | persegi panjang panjang $N$ | 1 untuk $0 \le n \le N-1$ |
| $h[n]$ | tanggapan impuls | keluaran bila masukan adalah $\delta[n]$ |
| $B_S$ | lebar bit keluaran pengkuadratan | 29 bit pada geser 8, 45 bit tanpa geser |
| $B_W$ | lebar bit keluaran jendela | 32 bit pada geser 8, 48 bit tanpa geser |

Angka-angka penting ditulis tebal: **30** adalah lebar jendela di makalah pada 200 sampel per detik, **150 ms** adalah lebar yang setara dengan 30 sampel itu, **37,5** adalah lebar yang sama pada laju terkunci 250 Hz, dan **38** adalah pembulatan ke atas yang masuk ke konvensi terkunci. Satu catatan istilah: makalah menyebut pengkuadratan sebagai *squaring function* dan integrasinya sebagai *moving-window integration*. Dokumen ini memakai istilah pengkuadratan dan integrasi jendela bergerak.

## 2. Pengkuadratan, persamaan (10)

Bentuk asli di halaman 233 adalah

$$
y(nT) = \left[ x(nT) \right]^{2}
$$

dan kalimat sesudahnya di makalah berbunyi: "This makes all data points positive and does nonlinear amplification of the output of the derivative emphasizing the higher frequencies (i.e., predominantly the ECG frequencies)." Terjemahan bebasnya: seluruh titik data menjadi positif, dan keluaran tahap turunan diperkuat secara non linier dengan penekanan pada frekuensi tinggi, yaitu terutama frekuensi EKG.

Persamaan itu hanya perkalian sebuah sampel dengan dirinya sendiri. Tidak ada koefisien, tidak ada memori, dan tidak ada riwayat. Kalimat makalah menyebut dua akibat yang sengaja dipilih: nilai selalu positif, dan penekanan yang tidak linier.

### 2.1 Sifat pertama, seluruh nilai menjadi positif

Untuk setiap bilangan nyata $x$, hasil kuadratnya tidak pernah negatif:

$$
x^{2} \ge 0 \quad \text{untuk setiap } x \in \mathbb{R}
$$

Sebabnya, bila $x \ge 0$ maka $x \cdot x \ge 0$, dan bila $x < 0$ maka $x \cdot x$ adalah perkalian dua bilangan negatif yang hasilnya positif. Hasil kuadrat hanya bernilai nol tepat ketika $x = 0$.

Terukur pada larik masukan bilangan bulat $[-3000, -17, -1, 0, 1, 17, 3000]$, keluarannya adalah $[9000000, 289, 1, 0, 1, 289, 9000000]$, jumlah sampel negatifnya 0 dari 7, dan nilai minimumnya 0. Pada seluruh rekaman AFDB 04015 yang panjangnya 450.000 sampel, jumlah sampel negatif sesudah pengkuadratan juga 0.

Akibat praktisnya untuk ambang: sesudah tahap ini tidak ada lagi nilai negatif, sehingga satu perbandingan ambang sederhana sudah cukup, dan tidak perlu rangkaian penyearah atau nilai absolut. Ini berbeda dari tahap turunan, yang keluarannya masih dua arah.

### 2.2 Sifat kedua, penekanan non linier pada kemiringan besar

Inilah alasan sesungguhnya pengkuadratan dipakai. Misalkan dua kemiringan berbeda dengan perbandingan

$$
r = \frac{\text{kemiringan kecil}}{\text{kemiringan besar}}, \qquad 0 < r < 1
$$

Sesudah pengkuadratan, perbandingan kedua nilai itu menjadi $r^{2}$, dan karena $r^{2} < r$ untuk setiap $r$ di antara nol dan satu, jarak keduanya makin lebar. Dalam desibel, perbandingan sebelum pengkuadratan adalah $20\log_{10} r$, sedangkan sesudahnya

$$
20\log_{10}\left(r^{2}\right) = 40\log_{10} r = 2 \cdot \left(20\log_{10} r\right)
$$

Jadi pengkuadratan tepat menggandakan anggaran desibel. Tambahan penekanannya adalah

$$
\Delta = 20\log_{10} r \ \text{dB}
$$

Tabel berikut hasil perhitungan notebook, bukan kutipan.

| Perbandingan sebelum, $r$ | Perbandingan sesudah, $r^{2}$ | Tambahan penekanan |
|---|---|---|
| 0,50 | 0,250000 | $-6{,}02$ dB |
| 0,25 | 0,062500 | $-12{,}04$ dB |
| 0,10 | 0,010000 | $-20{,}00$ dB |

Bacaan tabelnya begini. Bila dua kemiringan berbeda sepuluh kali, sesudah pengkuadratan bedanya menjadi seratus kali, dan tambahan penekanannya 20 dB. Kemiringan yang besar tumbuh jauh lebih cepat daripada kemiringan yang landai, dan itulah yang dimaksud kalimat makalah tentang penguatan non linier.

Untuk kemiringan QRS lawan kemiringan gelombang T, artinya begini. Kemiringan QRS besar, sedangkan kemiringan gelombang T landai. Pengkuadratan menaikkan QRS secara kuadratik, sedangkan gelombang T hanya naik sedikit, sehingga puncak selubung energi didominasi QRS dan gelombang T ikut teredam.

Sifat skala yang dipakai untuk uji juga perlu dicatat, karena di situlah letak keeksakan bilangan bulatnya:

$$
\left(2x\right)^{2} = 4x^{2}, \qquad \left(3x\right)^{2} = 9x^{2}
$$

Terukur pada larik uji 572 bilangan bulat, galat kedua identitas itu 0, bukan 0,0000001. Perkalian bilangan bulat dengan bilangan bulat selalu eksak, selama hasilnya masih muat di lebar kata yang tersedia.

### 2.3 Hasil terukur pada denyut fisiologis

Notebook mengukur sifat ini pada sinyal buatan 250 Hz dengan gelombang P, Q, R, S, T yang fisiologis dan derau yang realistis. Yang diukur adalah puncak kemiringan mutlak keluaran tahap turunan di dalam jendela sekitar QRS dan di dalam jendela gelombang T, diambil nilai mediannya.

| Besaran | Nilai terukur |
|---|---|
| Jumlah denyut terukur | 67 |
| Puncak kemiringan QRS, median | 186182 |
| Puncak kemiringan gelombang T, median | 36488 |
| Perbandingan T terhadap QRS | 0,195980, yaitu $-14{,}1558$ dB |
| Perbandingan sesudah pengkuadratan | 0,038408, yaitu $-28{,}3115$ dB |
| Tambahan penekanan dari pengkuadratan | $-14{,}1558$ dB |
| Puncak kuadrat QRS, median | $3{,}46637 \times 10^{10}$ |
| Puncak kuadrat gelombang T, median | $1{,}33137 \times 10^{9}$ |

Angka itu perlu dibaca jujur. Pengkuadratan memang menggandakan anggaran desibel, dari $-14{,}16$ dB menjadi $-28{,}31$ dB, dan itu sesuai harapan teori. Namun setelah tahap low-pass, high-pass, dan turunan, kemiringan gelombang T sudah naik sampai 0,195980 dari kemiringan QRS, jadi pengkuadratan sendirian menambah penekanan 14,16 dB, bukan 30 dB. Kesimpulannya: pengkuadratan memperlebar jarak QRS dan gelombang T, tetapi belum cukup untuk memisahkan keduanya. Itulah sebabnya makalah masih memerlukan tahap diskriminasi gelombang T di halaman 234, dan tahap itu masuk fase berikutnya di rencana implementasi.

### 2.4 Akibat untuk aritmetika bilangan bulat

Pengkuadratan tidak memerlukan pengali pada perangkat keras sederhana, karena kuadrat dapat dipetakan sebagai perkalian bilangan bulat di dalam blok DSP, atau sebagai tabel untuk masukan yang lebar katanya kecil. Yang perlu dijaga hanya lebar bit. Karena nilai maksimumnya dikuadratkan, lebar bit keluarannya kira-kira dua kali lebar bit masukannya ditambah satu bit tanda. Pada konvensi terkunci, masukan tahap ini adalah keluaran turunan yang sudah digeser kanan 8 bit, dan pengkuadratannya butuh 29 bit. Angka itu dibahas di bagian 8.

## 3. Integrasi jendela bergerak, persamaan (11)

Bentuk asli di halaman 233 adalah

$$
y(nT) = \frac{1}{N}\left[ x(nT - (N-1)T) + x(nT - (N-2)T) + \cdots + x(nT) \right]
$$

dengan keterangan berikutnya: "where N is the number of samples in the width of the integration window." Dalam notasi indeks bulat, persamaan itu adalah rata-rata bergerak $N$ sampel terakhir:

$$
y[n] = \frac{1}{N} \sum_{k=0}^{N-1} x[n-k]
$$

Perhatikan dua hal pada bentuk ini. Pertama, jendelanya menoleh ke belakang, yaitu mengambil $N$ sampel yang berakhir tepat di sampel ke-$n$, bukan jendela yang terpusat di $n$. Kedua, seluruh sampel diberi bobot yang sama, yaitu $1/N$. Bentuk terpusat tidak sesuai persamaan (11), dan itu diperiksa di notebook dengan masukan impuls di indeks 100. Bentuk kausal menaruh puncaknya tepat di indeks 100 dengan nilai 1000, artinya seluruh jendela saat itu terisi penuh oleh impulsnya, sedangkan bentuk terpusat menaruh puncaknya di indeks 82, yaitu 18 sampel atau 72,0 ms lebih awal, sementara tundaan grup kausalnya $(N-1)/2 = 18{,}5$ sampel atau 74,0 ms. Selisih 18 sampel lawan 18,5 sampel itu muncul karena bentuk terpusat menempatkan bagian tengah jendela pada sampel keluaran, sedangkan persamaan (11) menempatkan ujung belakang jendela di sana.

### 3.1 Penurunan fungsi alih

Transformasi z tiap suku, dengan sifat tunda $x[n-k] \leftrightarrow z^{-k}X(z)$:

$$
Y(z) = \frac{1}{N}\sum_{k=0}^{N-1} z^{-k} X(z)
$$

Maka

$$
H(z) = \frac{Y(z)}{X(z)} = \frac{1}{N}\sum_{k=0}^{N-1} z^{-k}
$$

Jumlah deret geometri dengan $N$ suku memberi bentuk tertutup yang lebih sering dipakai:

$$
\sum_{k=0}^{N-1} z^{-k} = \frac{1 - z^{-N}}{1 - z^{-1}}
$$

sehingga

$$
H(z) = \frac{1}{N} \cdot \frac{1 - z^{-N}}{1 - z^{-1}}
$$

Bukti kesamaan itu dengan mengalikan silang: $\left(1 - z^{-1}\right)\sum_{k=0}^{N-1} z^{-k} = 1 - z^{-N}$, karena seluruh suku tengah muncul dua kali dengan tanda berlawanan dan saling menghapus.

Penyebut $1 - z^{-1}$ memiliki satu kutub di $z = 1$, dan pembilang $1 - z^{-N}$ memiliki nol di $z = 1$ juga, sebab $1 - 1^{-N} = 0$. Kutub dan nol itu saling membatalkan, jadi integrator ini sebenarnya filter FIR dengan $N$ koefisien bernilai $1/N$. Sifat ini sama dengan yang sudah dibahas di [[00 - low-pass-filter-equation|low-pass-filter-equation]], dan akibatnya sama: untuk aritmetika terbatas sebaiknya yang diimplementasikan adalah bentuk jumlah berjalan, bukan bentuk rasio dengan umpan balik.

### 3.2 Bentuk rekursif akumulator

Bentuk jumlah langsung memerlukan $N-1$ penjumlahan per sampel. Bentuk rekursifnya hanya memerlukan dua operasi per sampel. Definisikan akumulator $S[n]$ sebagai jumlah $N$ sampel terakhir:

$$
S[n] = \sum_{k=0}^{N-1} x[n-k]
$$

Kurangi $S[n]$ dengan $S[n-1]$:

$$
S[n] - S[n-1] = x[n] - x[n-N]
$$

maka

$$
S[n] = S[n-1] + x[n] - x[n-N], \qquad y[n] = \frac{S[n]}{N}
$$

Satu sampel baru masuk, satu sampel tertua keluar, dan akumulatornya tidak pernah menghitung ulang seluruh jendela. Untuk jendela 38 sampel, ini mengubah 37 penjumlahan menjadi 1 penjumlahan dan 1 pengurangan.

### 3.3 Bukti keeksakan bentuk rekursif

Bentuk rekursif di atas memakai nilai lama $S[n-1]$, jadi secara aljabar ia sama dengan bentuk langsung, tetapi pada perangkat keras tetap perlu diperiksa apakah akumulasi bilangan bulatnya menghasilkan angka yang sama. Notebook mengujinya pada larik masukan bilangan bulat acak panjang 4000 sampel dengan rentang $-500$ sampai $500$:

| Besaran | Nilai terukur |
|---|---|
| Panjang larik uji | 4000 |
| Rentang nilai masukan | $-500$ sampai 500 |
| Galat maksimum bentuk rekursif lawan langsung | 0 |
| $S[3999]$ langsung | $-454$ |
| $S[3999]$ rekursif | $-454$ |

Galatnya nol karena seluruh operasinya penjumlahan dan pengurangan bilangan bulat, dan tidak ada pembagian di dalam rekursinya. Pembagian dengan $N$ hanya dilakukan sekali di ujung, bila memang diperlukan. Pada jendela yang panjangnya pangkat dua, pembagian itu dapat diganti penggeseran bit, sedangkan panjang 38 bukan pangkat dua sehingga pembagiannya perlu diputuskan secara khusus. Hal itu dibahas di bagian 6 dan bagian 10.

### 3.4 Penguatan DC dan penguatan puncak

Substitusi $z = 1$ pada bentuk tertutup memberi hasil bagi $0/0$, jadi batasnya yang dihitung. Cara termudah memakai bentuk jumlah:

$$
H(1) = \frac{1}{N}\sum_{k=0}^{N-1} 1 = \frac{N}{N} = 1
$$

Jadi penguatan DC integrator jendela bergerak adalah tepat satu, tidak bergantung pada $N$. Sinyal yang tidak berubah nilainya akan dilewatkan dengan nilai yang sama, dan itulah sifat rata-rata bergerak yang benar. Terukur pada $N = 38$:

| Besaran | Nilai terukur |
|---|---|
| Penguatan DC | 1,000000000000 |
| Penguatan puncak | 1,000000000000 pada 0 Hz |
| Penguatan puncak sebelum normalisasi $1/N$ | 38, yaitu $N$ |
| Galat relatif rumus tertutup lawan `freqz` | $2{,}964 \times 10^{-13}$ pada 19692 titik uji |
| Galat absolut rumus tertutup lawan `freqz` | $1{,}887 \times 10^{-15}$ |

Kalimat terakhir tabel itu penting. Bila faktor $1/N$ dihilangkan, puncak keluarannya menjadi $N$ kali lipat, yaitu 38 kali, dan seluruh angka lebar bit di bagian 8 berubah. Karena itu faktor $1/N$ bukan hiasan, ia penentu skala.

Sebagai catatan orde besaran, penguatan DC yang sama dengan satu berarti tahap ini tidak menambah headroom pada nilai rata-rata. Yang bertambah besar adalah puncaknya, karena jendela menjumlahkan beberapa sampel besar yang berdekatan. Pada sinyal buatan, puncak kuadrat adalah $1{,}97335 \times 10^{11}$, sedangkan puncak sesudah jendela 38 sampel adalah $1{,}63712 \times 10^{12}$, yaitu 8,2961 kali lebih besar. Pada rekaman nyata, puncak kuadratnya $1{,}52121 \times 10^{13}$ dan puncak selubungnya $1{,}34566 \times 10^{14}$.

### 3.5 Tundaan grup

Tundaan grup rata-rata bergerak panjang $N$ adalah

$$
\tau = \frac{N-1}{2} \ \text{sampel}
$$

Untuk $N = 38$ pada 250 Hz:

$$
\tau = \frac{38-1}{2} = 18{,}5 \ \text{sampel} = 18{,}5 \cdot \frac{1000}{250} = 74{,}0 \ \text{ms}
$$

Terukur dari kemiringan fasa fungsi alihnya, tundaannya 18,500000 sampel, yaitu 74,000000 ms. Terukur dari korelasi silang antara masukan dan keluaran pada masukan acak, tundaannya 18,496390 sampel, yaitu 73,985562 ms. Selisih dua cara pengukuran itu $3{,}6 \times 10^{-3}$ sampel. Tundaan ini perlu dicatat karena berarti selubung energi selalu tertinggal 74 ms dari kompleks QRS yang menghasilkannya.

Makalah menyebut soal tundaan ini di bagian *Fiducial Mark* halaman 233: "The QRS complex corresponds to the rising edge of the integration waveform. The time duration of the rising edge is equal to the width of the QRS complex." Jadi yang dipakai sebagai penanda waktu bukan puncak selubungnya, melainkan tepi naiknya. Alasannya bisa diturunkan sendiri: bila masukan berupa langkah dari 0 ke $A$ pada $n = 0$, akumulatornya naik linear selama $N$ sampel,

$$
y[n] = \frac{A\left(n+1\right)}{N} \quad \text{untuk } 0 \le n \le N-1
$$

sehingga lama tepi naiknya tepat $N$ sampel, dan setelah itu keluarannya mendatar $A$. Untuk masukan yang sempit, lebar tepi naiknya ditentukan lebar jendela, bukan lebar masukannya. Itu terukur di notebook: lebar QRS pada sinyal bersih 72,00 ms, sedangkan tepi naik selubungnya 114,00 ms, jadi tepi naik itu memang lebih panjang daripada QRS.

## 4. Respons frekuensi dan deret nolnya

Substitusi $z = e^{j\omega}$ pada bentuk jumlah, lalu pakai identitas $\left|1 - e^{-j\theta}\right| = 2\sin(\theta/2)$:

$$
\left| H(e^{j\omega}) \right| = \left| \frac{\sin\left(N\omega/2\right)}{N \sin\left(\omega/2\right)} \right|
$$

Bentuk ini adalah fungsi sinc terali, sama seperti rata-rata bergerak panjang enam di [[00 - low-pass-filter-equation|low-pass-filter-equation]], hanya panjangnya berbeda. Pada $\omega$ menuju nol, pembilang dan penyebutnya sama-sama menuju nol, dan batasnya adalah satu, yaitu penguatan DC yang sudah dihitung di bagian 3.4.

### 4.1 Deret nol di kelipatan laju dibagi N

Pembilang nol ketika $\sin(N\omega/2) = 0$ tetapi penyebutnya tidak nol, yaitu ketika

$$
\frac{N\omega}{2} = k\pi \implies \omega = \frac{2\pi k}{N}, \qquad k = 1, 2, \dots, N-1
$$

Dalam satuan frekuensi:

$$
f_k = \frac{k f_s}{N}
$$

Jadi nolnya berderet rapi dengan jarak antar nol sebesar $f_s/N$, mulai dari $f_s/N$ dan berlanjut sampai mendekati frekuensi Nyquist. Pada laju terkunci 250 Hz dan $N = 38$, jarak antar nolnya

$$
\frac{f_s}{N} = \frac{250}{38} = 6{,}578947 \ \text{Hz}
$$

sehingga nol pertama ada di 6,578947 Hz, nol kedua di 13,157895 Hz, nol ketiga di 19,736842 Hz, dan seterusnya. Nilai yang tepat di titik nol itu harus nol. Notebook mengujinya dengan menghitung jumlah langsung $\sum_k e^{-j\omega k}/N$ pada frekuensi tepat:

| $k$ | $f_k$ (Hz) | $\left| H \right|$ dari jumlah langsung | $\left| H \right|$ dari rumus tertutup |
|---|---|---|---|
| 1 | 6,578947 | $5{,}673 \times 10^{-17}$ | $3{,}903 \times 10^{-17}$ |
| 2 | 13,157895 | $1{,}158 \times 10^{-16}$ | $3{,}916 \times 10^{-17}$ |
| 3 | 19,736842 | $6{,}548 \times 10^{-17}$ | $3{,}938 \times 10^{-17}$ |
| 4 | 26,315789 | $2{,}028 \times 10^{-16}$ | $3{,}970 \times 10^{-17}$ |
| 5 | 32,894737 | $1{,}910 \times 10^{-16}$ | $1{,}565 \times 10^{-16}$ |

Angka-angka itu bukan nol yang eksak, melainkan sisa pembulatan titik apung, dan besarnya di bawah $10^{-16}$, yaitu di bawah presisi mesin untuk nilai orde satu. Uji pendukungnya, jumlah seluruh akar unity orde 38 adalah $3{,}854 \times 10^{-15}$, yaitu nol.

Konsekuensi rancangan yang perlu dicatat: pada 250 Hz, nol pertama jatuh di 6,578947 Hz dan nol kedua di 13,157895 Hz. Di situlah dua pitanya. Karena sinyal EKG yang penting untuk QRS justru berada di sekitar nol kedua itu, integrator jendela bergerak bukan tapis pita yang netral terhadap QRS, dan itulah sebabnya lebar jendelanya harus dipilih dengan hati-hati.

### 4.2 Puncak sidelobe pertama

Nilai maksimum di antara dua nol berdekatan terjadi di sekitar $\omega \approx 2\pi(k + 1/2)/N$. Terukur, puncak sidelobe pertamanya berada di 9,412029 Hz dengan penguatan 0,217741, yaitu $-13{,}24$ dB. Jadi di antara nol pertama dan nol kedua, tapis ini masih melewatkan sekitar 21,77 persen amplitudonya. Angka itu dipakai sebagai acuan bila tim ingin menghitung seberapa besar kontribusi pita di antara dua nol terhadap selubung energi.

## 5. Lebar jendela dan perbandingannya dengan angka makalah

Makalah memberi panduan pemilihan lebar jendela dalam satu paragraf di halaman 233. Kutipannya: "The number of samples N in the moving window is important. Generally, the width of the window should be approximately the same as the widest possible QRS complex. If the window is too wide, the integration waveform will merge the QRS and T complexes together. If it is too narrow, some QRS complexes will produce several peaks in the integration waveform. These can cause difficulty in subsequent QRS detection processes. The width of the window is determined empirically. For our sample rate of 200 samples/s, the window is 30 samples wide (150 ms)."

Tiga hal dari paragraf itu. Pertama, lebar jendela hendaknya kira-kira selebar QRS terlebar yang mungkin, jadi patokannya adalah lebar QRS, bukan lebar gelombang lain. Kedua, jendela yang terlalu lebar membuat QRS dan gelombang T menyatu di selubungnya, sehingga penanda waktu menjadi kabur. Ketiga, jendela yang terlalu sempit membuat satu kompleks QRS menghasilkan beberapa puncak, sehingga tahap deteksi sesudahnya bisa salah menghitung satu denyut menjadi beberapa denyut.

Angka yang dipakai makalah adalah 30 sampel pada 200 sampel per detik, dan makalah sendiri menyebutnya setara 150 ms:

$$
\frac{30}{200} = 0{,}150 \ \text{s} = 150 \ \text{ms}
$$

Jadi patokan yang dipertanggungjawabkan makalah adalah 150 ms, sedangkan 30 sampel hanyalah bentuk 150 ms pada laju 200 Hz. Karena tim memakai laju terkunci yang berbeda, yang harus dijaga adalah 150 ms-nya, lalu diubah menjadi sampel pada laju masing-masing.

### 5.1 Tabel lebar jendela pada beberapa laju sampel

Tabel ini seluruhnya hasil perhitungan, bukan kutipan.

| Laju sampel (Hz) | Lebar 150 ms (sampel) | Dibulatkan (sampel) | Panjang dibulatkan (ms) | Galat terhadap 150 ms (ms) |
|---|---|---|---|---|
| 100 | 15,00 | 15 | 150,0 | 0,0 |
| 125 | 18,75 | 19 | 152,0 | 2,0 |
| 200 | 30,00 | 30 | 150,0 | 0,0 |
| 250 | 37,50 | 38 | 152,0 | 2,0 |
| 360 | 54,00 | 54 | 150,0 | 0,0 |
| 500 | 75,00 | 75 | 150,0 | 0,0 |

Baris 200 Hz mereproduksi angka makalah, yaitu 30 sampel. Baris 250 Hz adalah laju terkunci AFIB-LITE, dan di situ 150 ms menjadi 37,5 sampel, yaitu angka yang tidak bulat. Karena lebar jendela harus bilangan bulat, pilihannya jatuh antara 37 sampel dan 38 sampel.

### 5.2 Mengapa jendela bergantian 37 dan 38

Jendela 37 sampel panjangnya 148,0 ms, yaitu 2,0 ms lebih pendek dari 150 ms. Jendela 38 sampel panjangnya 152,0 ms, yaitu 2,0 ms lebih panjang dari 150 ms. Jadi keduanya menyimpang 2 ms, hanya dengan tanda berlawanan. Bila jendela dipakai bergantian 37, 38, 37, 38, dan seterusnya, panjang rata-ratanya menjadi

$$
\frac{37 + 38}{2} = 37{,}5 \ \text{sampel} = 150{,}000 \ \text{ms}
$$

yaitu tepat 150 ms. Galat rata-ratanya nol, bukan 2 ms. Itulah alasan jendela bergantian dipakai. Angka 38 masuk ke konvensi terkunci karena ia adalah pembulatan ke atas dari 37,5 dan sekaligus panjang jendela yang dipakai di seluruh anggaran bit bagian 8, sedangkan pasangan 37 dipakai bergantian agar rata-ratanya kembali tepat 150 ms.

Perlu dicatat satu keterbatasan skema bergantian ini: pola 37 dan 38 hanya menghasilkan rata-rata tepat 150 ms bila keduanya dipakai dengan jumlah kemunculan yang sama banyak. Untuk jumlah sampel yang ganjil, satu sampel di ujungnya tidak berpasangan, sehingga rata-ratanya bergeser setengah sampel. Pergeseran setengah sampel itu setara 2 ms, jadi pengaruhnya sama dengan memakai jendela tetap.

### 5.3 Perbandingan tiga skema

Tabel berikut hasil perhitungan notebook pada 250 Hz.

| Skema | Panjang rata-rata (sampel) | Panjang rata-rata (ms) | Galat (ms) | Nol pertama (Hz) | Tundaan grup (sampel) | Tundaan grup (ms) |
|---|---|---|---|---|---|---|
| Tetap 37 sampel | 37,0 | 148,0 | $-2{,}0$ | 6,756757 | 18,00 | 72,0 |
| Tetap 38 sampel | 38,0 | 152,0 | 2,0 | 6,578947 | 18,50 | 74,0 |
| Bergantian 37 dan 38 | 37,5 | 150,0 | 0,0 | 6,666667 | 18,25 | 73,0 |

Selisih letak nol pertama antara jendela tetap 37 dan tetap 38 adalah 0,177809 Hz, sedangkan selisih antara skema bergantian dan tetap 38 adalah 0,087719 Hz. Selisih tundaan grup antara skema tetap 37 dan tetap 38 adalah 0,5 sampel, yaitu 2,0 ms. Ketiga angka itu kecil, dan pengukuran selubung pada sinyal buatan memastikan kecilnya memang tidak berdampak besar:

| Skema | Puncak selubung, rata-rata | Lebar setengah puncak (ms) | Puncak QRS dibagi luar | Tunda puncak (ms) |
|---|---|---|---|---|
| Bergantian 37 dan 38 | $4{,}190120 \times 10^{10}$ | 152,0 | 2,178522 | 116,0 |
| Tetap 37 | $4{,}245729 \times 10^{10}$ | 148,0 | 2,221492 | 116,0 |
| Tetap 38 | $4{,}134987 \times 10^{10}$ | 152,0 | 2,137251 | 116,0 |

Selisih puncak jendela tetap 37 terhadap skema bergantian adalah $+1{,}3272$ persen, dan jendela tetap 38 memberi $-1{,}3158$ persen. Tundaan puncaknya sama untuk ketiga skema, yaitu 116,0 ms terukur pada sinyal buatan, yang memang berbeda dari tundaan grup teori 74 ms karena tunda puncak bergantung bentuk denyutnya, bukan hanya pada jendelanya. Kesimpulannya, untuk bentuk selubung, ketiga skema itu sama saja di bawah 1,4 persen. Skema bergantian tetap dipakai karena keunggulannya ada di patokan 150 ms yang dipertanggungjawabkan makalah.

## 6. Hitungan tangan rata-rata bergerak

Bagian ini memberi dua contoh. Yang pertama memakai $N$ kecil supaya bisa dihitung di atas kertas, dan yang kedua memakai $N = 38$ pada rekaman nyata.

### 6.1 Contoh soal, rata-rata bergerak lima sampel

Masukan $x[n]$ adalah deret bilangan bulat

| $n$ | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| $x[n]$ | 3 | 1 | 4 | 1 | 5 | 9 | 2 | 6 | 5 | 3 | 5 | 8 | 9 | 7 | 9 |

Hitung $y[n] = \left(x[n] + x[n-1] + x[n-2] + x[n-3] + x[n-4]\right)/5$, dengan nilai di luar larik dianggap nol.

| $n$ | $x[n]$ | $x[n-1]$ | $x[n-2]$ | $x[n-3]$ | $x[n-4]$ | $S[n]$ | $y[n]$ |
|---|---|---|---|---|---|---|---|
| 0 | 3 | 0 | 0 | 0 | 0 | 3 | 0,6 |
| 1 | 1 | 3 | 0 | 0 | 0 | 4 | 0,8 |
| 2 | 4 | 1 | 3 | 0 | 0 | 8 | 1,6 |
| 3 | 1 | 4 | 1 | 3 | 0 | 9 | 1,8 |
| 4 | 5 | 1 | 4 | 1 | 3 | 14 | 2,8 |
| 5 | 9 | 5 | 1 | 4 | 1 | 20 | 4,0 |
| 6 | 2 | 9 | 5 | 1 | 4 | 21 | 4,2 |
| 7 | 6 | 2 | 9 | 5 | 1 | 23 | 4,6 |
| 8 | 5 | 6 | 2 | 9 | 5 | 27 | 5,4 |
| 9 | 3 | 5 | 6 | 2 | 9 | 25 | 5,0 |
| 10 | 5 | 3 | 5 | 6 | 2 | 21 | 4,2 |
| 11 | 8 | 5 | 3 | 5 | 6 | 27 | 5,4 |
| 12 | 9 | 8 | 5 | 3 | 5 | 30 | 6,0 |
| 13 | 7 | 9 | 8 | 5 | 3 | 32 | 6,4 |
| 14 | 9 | 7 | 9 | 8 | 5 | 38 | 7,6 |

Baris $n = 12$ dibaca begini: sampel $x[12] = 9$, $x[11] = 8$, $x[10] = 5$, $x[9] = 3$, $x[8] = 5$, jumlahnya 30, dan dibagi 5 menjadi 6,0. Notebook memeriksa bahwa jumlah lima suku pada setiap baris sama dengan $x[n-4]$ sampai $x[n]$, dan hasilnya benar untuk seluruh baris.

Sekarang bandingkan dengan bentuk rekursifnya untuk baris yang sama. Karena $S[11] = 27$, maka

$$
S[12] = S[11] + x[12] - x[7] = 27 + 9 - 6 = 30
$$

dan hasilnya sama, 30, tanpa menjumlahkan lima suku. Dua operasi menggantikan lima suku. Hal yang sama berlaku untuk jendela 38 sampel pada rekaman nyata, dan di situ selisihnya adalah 37 penjumlahan.

### 6.2 Contoh soal, jendela 38 sampel pada rekaman nyata

Notebook mengambil satu sampel dari keluaran tahap turunan pada rekaman AFDB 04015, yaitu $n = 1234$, lalu menuliskan seluruh 38 suku yang masuk ke jendela itu.

| Besaran | Nilai terukur |
|---|---|
| Sampel pertama jendela, $x[1197]$ | 327 |
| Sampel terakhir jendela, $x[1234]$ | $-191$ |
| Jumlah 38 suku, $S[1234]$ | $-960$ |
| $S[1234]$ dibagi 38 | $-25{,}263157894736842$ |
| $S[1234]$ dari bentuk langsung | $-960$ |
| Jumlah 38 suku sama dengan bentuk langsung | Benar |
| $S[n]$ rekursif sama dengan bentuk langsung | Benar |

Bacaan barisnya begini: jendela yang berakhir di sampel ke-1234 dimulai dari sampel ke-1197, karena $1234 - 37 = 1197$. Suku pertamanya 327 dan suku terakhirnya $-191$, jumlahnya $-960$, dan dibagi 38 menjadi sekitar $-25{,}26$. Karena nilai tengahnya negatif, sampel itu memang berada di daerah antara dua kompleks QRS, bukan di puncak selubung.

### 6.3 Pembagian dengan 38

Ada satu hal yang tidak bisa dihindari pada lebar jendela 38: pembagian dengan 38 tidak dapat diganti penggeseran bit, karena 38 bukan pangkat dua. Tiga jalan yang tersedia, dan pilihannya perlu diputuskan tim:

1. Membagi dengan 38 memakai pembagi bilangan bulat, yang memerlukan beberapa siklus atau sebuah blok pembagi.
2. Tidak membagi sama sekali di RTL, lalu menyesuaikan ambangnya. Karena ambang dibandingkan dengan $S[n]$ dan bukan dengan $y[n]$, ambangnya hanya perlu dikalikan 38. Pada aritmetika bilangan bulat, cara ini tidak menambah galat apa pun.
3. Membulatkan lebar jendela menjadi pangkat dua terdekat, yaitu 32 sampel atau 64 sampel, sehingga pembagiannya menjadi penggeseran bit. Namun 32 sampel panjangnya 128 ms dan 64 sampel 256 ms, dan keduanya menyimpang jauh dari patokan 150 ms makalah, sehingga cara ini bertentangan dengan bagian 5.

Pilihan kedua yang paling murah di perangkat keras, dan itulah sebabnya bagian 8 mengukur lebar bit keluaran $S[n]$, bukan keluarannya sesudah dibagi.

## 7. Kasus sebelum dan sesudah, dua tingkat

Notebook mengukur seluruh tahap pada sinyal buatan yang komponennya dapat dikendalikan, supaya setiap perubahan bentuk gelombang bisa dipertanggungjawabkan. Sinyalnya 20,0 detik atau 5000 sampel pada 250 Hz, 70 denyut per menit, 22 denyut, dengan gelombang P, Q, R, S, dan T yang fisiologis. Derau yang ditambahkan adalah wander 0,08 satuan pada 0,3 Hz, jala-jala 0,20 satuan pada 50 Hz, dan derau otot 0,08 satuan pada pita 20 sampai 100 Hz. Puncak sinyal bersihnya 1,00455 satuan, dan puncak kata masukannya 9200 hitungan pada skala konvensi terkunci.

Pengukurannya disusun sebagai dua tingkat, sesuai yang diminta. Tingkat pertama membandingkan keluaran tahap turunan dengan keluarannya sesudah pengkuadratan. Tingkat kedua membandingkan keluaran sesudah pengkuadratan dengan keluarannya sesudah integrasi jendela 38 sampel. Kolom terakhir adalah puncak QRS dibagi puncak di luar QRS, yaitu ukuran seberapa jauh puncaknya menonjol dari latarnya.

### 7.1 Tabel pengukuran

Denyut yang diukur adalah denyut 4 sampai 22 dari 22 denyut, supaya denyut pertama yang masih mengandung transien awal tidak ikut dihitung.

| Tingkat | Puncak | Puncak lokal per denyut, median | Lebar setengah puncak (ms) | Tepi naik (ms) | Puncak QRS dibagi luar |
|---|---|---|---|---|---|
| 1 masukan tahap, keluaran turunan | $4{,}442240 \times 10^{5}$ | 3,0 | 72,0 | 412,0 | 4,630155 |
| 1 keluaran sesudah pengkuadratan | $1{,}973350 \times 10^{11}$ | 2,0 | 56,0 | 28,0 | 15,947508 |
| 2 keluaran sesudah jendela 38 | $1{,}637120 \times 10^{12}$ | 2,0 | 152,0 | 114,0 | 2,137251 |

### 7.2 Membaca tingkat pertama, sebelum dan sesudah pengkuadratan

Sebelum pengkuadratan, keluaran turunan memiliki puncak $4{,}442240 \times 10^{5}$ dan puncak QRS dibagi luar hanya 4,630155. Angka 4,6 itu artinya puncak QRS hanya sekitar lima kali puncak latarnya, dan itu memang terlalu rapat untuk dipisahkan dengan ambang yang aman. Lebar setengah puncaknya 72,0 ms, sama dengan lebar QRS, sedangkan tepi naiknya 412,0 ms karena di sinyal itu masih ada beberapa puncak lokal (median 3,0 puncak per denyut) akibat derau otot.

Sesudah pengkuadratan, puncaknya naik menjadi $1{,}973350 \times 10^{11}$, dan puncak QRS dibagi luar naik dari 4,630155 menjadi 15,947508, yaitu lebih dari tiga kali lebih baik. Itulah kerja pengkuadratan yang dijelaskan di bagian 2.2: kemiringan besar tumbuh secara kuadratik sedangkan kemiringan kecil tidak. Lebar setengah puncaknya menyusut dari 72,0 ms menjadi 56,0 ms, artinya puncaknya makin tajam, dan jumlah puncak lokalnya turun dari 3,0 menjadi 2,0.

Perhatikan juga kekasarannya. Ukuran kekasaran yang dipakai notebook adalah median selisih mutlak antara sampel berdekatan dibagi median nilainya. Sesudah pengkuadratan, kekasarannya 0,919042, yaitu hampir satu. Artinya nilai selubung berubah hampir sebesar nilainya sendiri dari satu sampel ke sampel berikutnya. Untuk membandingkan dengan ambang, sinyal sekasar itu akan membuat ambang terlewati berkali-kali di dalam satu denyut.

### 7.3 Membaca tingkat kedua, sebelum dan sesudah integrasi jendela 38

Sesudah integrasi jendela 38 sampel, puncaknya menjadi $1{,}637120 \times 10^{12}$, kekasarannya turun dari 0,919042 menjadi 0,027305, yaitu 33,66 kali lebih halus. Inilah alasan utama tahap integrasi ada. Kolom lebar setengah puncaknya berubah dari 56,0 ms menjadi 152,0 ms, dan itu bukan cacat melainkan sifat yang dipakai: selubung QRS menjadi bonggol yang lebarnya kira-kira selebar jendelanya, sehingga tepi naiknya dapat dipakai sebagai penanda waktu seperti yang ditulis makalah di bagian *Fiducial Mark*.

Harga yang harus dibayar terlihat di kolom terakhir: puncak QRS dibagi luar turun dari 15,947508 menjadi 2,137251, karena jendela merata-ratakan puncak yang tajam dengan latar di sekitarnya. Jadi dua tahap ini bekerja berlawanan arah dan keduanya diperlukan: pengkuadratan mempertajam dan memperlebar jarak puncak terhadap latar, sedangkan jendela menghaluskan dan sebagai gantinya memakai lebar tepi naik. Yang tersisa sesudah kedua tahap itu masih harus diselesaikan oleh tahap penentuan ambang dan deteksi puncak di fase berikutnya.

### 7.4 Angka selubung yang dapat dipakai untuk ambang

Dua angka berikut dipakai untuk merancang ambang di fase berikutnya. Pertama, rasio puncak selubung terhadap puncak kuadrat pada sinyal buatan adalah 8,2961. Kedua, pada rekaman nyata AFDB 04015, puncak kuadratnya $1{,}52121 \times 10^{13}$ dengan median $1{,}93935 \times 10^{9}$, sehingga rasionya 7843,922. Sesudah integrasi, puncak selubungnya $1{,}34566 \times 10^{14}$ dengan median $2{,}95887 \times 10^{11}$, sehingga rasionya turun menjadi 454,787. Selubung yang berada di atas 20 kali mediannya menutupi 18,8176 persen waktu rekaman. Angka 18,8 persen itu menunjukkan bahwa jendela 38 sampel pada rekaman fibrilasi atrium yang padat masih menyisakan hampir seperlima waktu di atas 20 kali median, jadi ambang tetap harus dipilih dengan hati-hati.

## 8. Catatan fixed-point memakai konvensi terkunci

Bagian ini memakai konvensi yang sudah dikunci tim dan seluruhnya diukur pada rekaman AFDB 04015. Konvensinya adalah sebagai berikut.

1. Masukan rentangnya plus minus 5 mV dengan 12 bit signifikan, dijepit pada plus minus 2047 hitungan, dan disimpan dalam kata 16 bit yang nilainya digeser ke kiri 4 bit. Jadi skalanya 409,4 hitungan per mV.
2. Low-pass memakai koefisien 1 sampai 6 tanpa pengali, dan keluaran maksimumnya 1,179 juta sehingga butuh 22 bit.
3. High-pass memakai koefisien 32 dan 1 dan 1, bersifat rekursif, keluaran maksimumnya 19,29 juta sehingga butuh 26 bit, dan yang dipakai 28 bit.
4. Turunan memakai koefisien 1 dan 2 dengan pembagian 8, keluaran maksimumnya 3,90 juta sehingga butuh 23 bit, lalu hasilnya digeser kanan 8 bit sehingga faktor skala ambangnya 256.
5. Sesudah geser 8 itu, pengkuadratan butuh 29 bit dan integrasi jendela 38 sampel butuh 32 bit. Tanpa geser sama sekali, kuadrat butuh 45 bit dan jendelanya 48 bit. Dengan geser 4, jendelanya tepat 40 bit, sama dengan angka `int40` di dokumen 31.
6. Tidak ada pengali di seluruh rantai, dan keeksakan aritmetika bilangan bulatnya sudah terbukti dengan galat relatif 0,000e+00.

### 8.1 Pengukuran ulang seluruh tahap

Notebook mengukur ulang setiap tahap pada rekaman itu, dan hasilnya sebagai berikut.

| Besaran | Nilai terukur |
|---|---|
| Header rekaman | 04015, 250 Hz, 450000 sampel, kanal ECG1 12 bit |
| Sinyal | maksimum 6,4350 mV, puncak ke puncak 10,9800 mV |
| Kata masukan | maksimum 32752 hitungan, lebar 16 bit |
| Sampel terjepit | 402 dari 450000 |
| Low-pass | maksimum $1{,}17907 \times 10^{6}$, lebar 22 bit |
| High-pass | maksimum $1{,}92862 \times 10^{7}$, lebar 26 bit |
| Turunan | maksimum $3{,}90027 \times 10^{6}$, lebar 23 bit |

Ketiga angka lebar bit untuk low-pass, high-pass, dan turunan itu sama dengan konvensi terkunci, dan itu sekaligus memastikan rantai tahap sebelumnya di dokumen ini tersambung dengan benar. Ada satu catatan kejujuran yang perlu ditulis: 402 sampel dari 450.000 terjepit pada batas plus minus 2047, yaitu sekitar 0,089 persen. Penjepitan itu terjadi di masukan dan tidak memengaruhi lebar bit tahap sesudahnya karena jepitannya justru membatasi nilai maksimumnya.

### 8.2 Tabel penggeseran sesudah tahap turunan

Tabel berikut adalah inti keputusan fixed-point untuk dua persamaan di dokumen ini. Seluruh angkanya hasil pengukuran, dan kolom faktor skala ambang adalah pengali yang harus dipakai pada ambang bila nilainya dibandingkan dengan keluaran yang sudah digeser.

| Geser (bit) | Turunan maksimum | Lebar kuadrat (bit) | Kuadrat maksimum | Lebar jendela 38 (bit) | Jendela maksimum | Faktor skala ambang |
|---|---|---|---|---|---|---|
| 0 | 3900266 | 45 | 15212074870756 | 48 | 134565509007600 | 1 |
| 4 | 243767 | 37 | 59422350289 | 40 | 525646276334 | 16 |
| 8 | 15236 | 29 | 232135696 | 32 | 2053318817 | 256 |
| 12 | 953 | 21 | 908209 | 24 | 8020056 | 4096 |

Bacaan tabelnya begini. Tanpa penggeseran apa pun sesudah turunan, pengkuadratan memerlukan 45 bit dan jendela 38 sampel memerlukan 48 bit, dan keduanya tidak muat di kata 32 bit. Setelah geser kanan 8 bit, pengkuadratan hanya memerlukan 29 bit dan jendela 38 sampel memerlukan 32 bit, sehingga keduanya muat di kata 32 bit, dengan jendelanya tepat menyentuh batas. Nilai maksimumnya juga tercatat: kuadrat 232135696 dan jendela 2053318817 pada geser 8.

Baris geser 4 adalah baris yang dipakai untuk memverifikasi angka `int40` di dokumen 31. Di situ jendela 38 sampel tepat memerlukan 40 bit, sama dengan angka yang sudah tertulis di dokumen itu. Kesesuaian ini penting karena berarti konvensi terkunci dan pengukuran di notebook ini saling menopang, bukan sekadar saling mengutip.

Pemilihan geser 8 untuk konvensi terkunci juga punya alasan aritmetika yang rapi: geser 8 bit sama dengan pembagian dengan 256, yang merupakan pangkat dua, sehingga seluruh operasinya tetap penggeseran dan penjumlahan. Faktor skala ambangnya karena itu menjadi 256, dan angka itu lebih mudah dipetakan ke perangkat keras daripada 409 atau 38.

### 8.3 Keeksakan aritmetika bilangan bulat

Notebook menjalankan seluruh rantai dua kali, sekali dengan bilangan bulat dan sekali dengan pecahan, lalu membandingkan keluarannya.

| Tahap | Galat relatif maksimum |
|---|---|
| Pengkuadratan | 0,000e+00 |
| Jendela 38 | 0,000e+00 |

Galatnya benar-benar nol, bukan 0,000001, karena seluruh operasi di kedua tahap itu penjumlahan, pengurangan, dan perkalian bilangan bulat, tanpa pembagian di dalam lintasannya. Seluruh koefisien pada tahap sebelumnya juga bilangan bulat, jadi tidak ada galat kuantisasi koefisien. Kesimpulannya, rantai ini dapat diimplementasikan sebagai aritmetika bilangan bulat sepenuhnya dengan perilaku bit yang dapat diprediksi.

### 8.4 Pemeriksaan kesesuaian dengan konvensi terkunci

Sebelas angka konvensi terkunci diperiksa satu per satu terhadap pengukuran ulang di notebook.

| Besaran | Konvensi terkunci (bit) | Terukur di notebook (bit) | Selisih |
|---|---|---|---|
| Masukan, lebar kata | 16 | 16 | 0 |
| Low-pass, lebar minimum | 22 | 22 | 0 |
| High-pass, lebar minimum | 26 | 26 | 0 |
| Turunan, lebar minimum tanpa geser | 23 | 23 | 0 |
| Kuadrat tanpa geser, lebar minimum | 45 | 45 | 0 |
| Jendela 38 tanpa geser, lebar minimum | 48 | 48 | 0 |
| Kuadrat pada geser 8, lebar minimum | 29 | 29 | 0 |
| Jendela 38 pada geser 8, lebar minimum | 32 | 32 | 0 |
| Jendela 38 pada geser 4, lebar minimum | 40 | 40 | 0 |
| Kuadrat pada geser 12, lebar minimum | 21 | 21 | 0 |
| Jendela 38 pada geser 12, lebar minimum | 24 | 24 | 0 |

Jumlah baris yang cocok 11 dari 11, dan selisih terbesarnya 0 bit.

### 8.5 Ringkasan fixed-point untuk dua persamaan fase ini

1. Pengkuadratan butuh 29 bit sesudah geser 8, dan 45 bit tanpa geser sama sekali.
2. Integrasi jendela 38 butuh 32 bit sesudah geser 8, 40 bit pada geser 4, dan 48 bit tanpa geser.
3. Tidak ada pengali di kedua tahap. Pengkuadratan adalah satu perkalian bilangan bulat, dan integrasi adalah satu penjumlahan dan satu pengurangan pada akumulator.
4. Aritmetika bilangan bulatnya eksak, dengan galat relatif 0,000e+00 pada kedua tahap.
5. Pada perangkat keras, integrasi dapat dipetakan ke satu akumulator 32 bit dengan dua operasi per sampel, ditambah satu penampan melingkar 38 kata yang menyimpan sampel lama supaya sampel yang keluar jendela dapat dibaca. Bila memori lebih murah daripada daya, bentuk langsung dengan 37 penjumlahan per sampel dapat dipakai tanpa penampan itu.

## 9. Hubungan ke rancangan AFIB-LITE

Rancangan tim memakai laju terkunci 250 Hz, sedangkan makalah memakai 200 sampel per detik. Tiga akibatnya sebagai berikut.

Pertama, lebar jendela pada laju terkunci adalah 37,5 sampel, sehingga dipakai jendela bergantian 37 dan 38 sampel agar rata-ratanya tepat 150 ms. Rata-rata panjang jendela skema bergantian adalah 150,000 ms dengan galat 0,000 ms, sedangkan jendela tetap 37 dan tetap 38 masing-masing menyimpang 2,0 ms. Selisih bentuk selubung ketiga skema di bawah 1,4 persen, jadi pilihan bergantian itu aman dari sisi gelombang sekaligus tepat dari sisi patokan waktu.

Kedua, nol integratornya berpindah karena lebar jendelanya berpindah. Pada 250 Hz dengan $N = 38$, nol pertama ada di 6,578947 Hz dan nol kedua di 13,157895 Hz, sedangkan pada makalah 200 Hz dengan $N = 30$, nol pertamanya 6,666667 Hz dan nol keduanya 13,333333 Hz. Pergeserannya kecil, di bawah 0,18 Hz, jadi pita di antara dua nol itu tetap berada di daerah yang sama, yaitu daerah yang memuat energi utama kompleks QRS.

Ketiga, anggaran bitnya ditentukan oleh pengukuran pada rekaman nyata, bukan oleh perkiraan. Dengan geser kanan 8 bit sesudah tahap turunan, pengkuadratan memerlukan 29 bit dan jendela 38 sampel memerlukan 32 bit, sehingga keduanya muat di kata 32 bit. Bila tim memilih tidak menggeser sama sekali, kedua tahap itu memerlukan 45 bit dan 48 bit, dan pilihannya harus diambil sebelum RTL ditulis karena memengaruhi seluruh jalur datanya.

Satu hal yang perlu diingat saat membaca keluaran kedua tahap ini di RTL: selubung energi yang dihasilkan bukan sinyal EKG lagi, melainkan sudah menjadi selubung tanpa makna morfologis. Nilai sampelnya tidak dapat dibaca sebagai milivolt. Yang tersisa hanyalah puncak dan tepi naiknya, dan justru itulah yang dibutuhkan tahap penentuan ambang di fase berikutnya.

## 10. Keputusan yang dikunci 18 Oktober 2026

Empat keputusan rekayasa dikunci Aviv pada 18 Oktober 2026 malam dan berlaku mulai sekarang, menggantikan daftar pertanyaan tim yang sebelumnya ada di bagian ini. Satu butir sengaja tidak ikut dikunci karena menyangkut anggaran area dan sumber daya, bukan aritmetika.

1. **Pembagian dengan 38 tidak dilakukan di RTL, dan faktor tetapnya dibuang.** Sebagai gantinya, ambang dikalikan 38. Dua alasan mendasarinya. Pertama, pembaginya hilang sama sekali dari jalur data, sehingga tidak ada pembagi bilangan bulat yang perlu dipetakan. Kedua, makalah Pan-Tompkins sendiri memaklumkan pembuangan faktor tetap karena ambangnya adaptif, jadi skalanya memang boleh diserap ke dalam ambang. Rincian pilihan ini ada di bagian 6.3.
2. **Jendela integrasi memakai bentuk bergantian 37 dan 38 sampel**, bukan dibulatkan ke pangkat dua 32 sampel. Alasannya terukur dan sudah dibandingkan di bagian 5.3: bentuk bergantian memberi tepat 150,0 ms, jendela tetap 37 memberi 148,0 ms, jendela tetap 38 memberi 152,0 ms, sedangkan 32 sampel menyimpang 22 ms dari patokan 150 ms sehingga ikut menggeser letak titik potong tapis. Pembulatan ke pangkat dua memang menyederhanakan pembagian, tetapi harganya adalah patokan waktu yang dipertanggungjawabkan makalah.
3. **Penampan melingkar dipakai untuk jendela integrasi**, dengan satu tambah dan satu kurang per sampel, bukan 37 penjumlahan per sampel. Catatan yang perlu ditulis apa adanya: penyimpanannya berukuran 38 kata dikali 32 bit, sama dengan 1.216 flip-flop, yaitu 2,52 kali seluruh flip-flop demo integrator yang terukur 482. Jadi blok ini berisiko menjadi penyumbang area terbesar, dan pilihan antara flip-flop atau BRAM untuk penampan itu tidak dikunci di sini melainkan dibahas pada butir terakhir bagian ini.
4. **Semua ambang yang ditulis dalam satuan milivolt dikalikan 256 lebih dulu**, konsisten dengan penggeseran kanan 8 bit pada tahap turunan, dan dikalikan 38 bila pembagian jendela dibuang. Faktor 256 berasal dari geser 8 yang diukur di bagian 8.2, sedangkan pengali 38 berasal dari butir 1 di atas.

Catatan yang tidak berubah: tahap diskriminasi gelombang T di halaman 234 tetap dikerjakan di fase berikutnya, karena pengukuran di bagian 2.3 menunjukkan gelombang T masih bernilai 0,038408 dari QRS sesudah pengkuadratan, jadi pengkuadratan sendirian memang belum memisahkan keduanya.

### 10.1 Butir yang belum dikunci

Pemilihan penampan 1.216 flip-flop pada butir 3, yaitu antara flip-flop atau BRAM, **tetap menunggu keputusan** tim area, yaitu Raihan. Butir ini tidak dikunci Aviv pada 18 Oktober 2026 karena menyangkut anggaran area dan sumber daya, bukan aritmetika atau bentuk gelombang.

## 11. Rujukan

1. Pan J, Tompkins WJ. *A Real-Time QRS Detection Algorithm.* IEEE Transactions on Biomedical Engineering, 1985, BME-32(3):230-236. DOI 10.1109/TBME.1985.325532. Persamaan (10) dan (11), paragraf *Squaring Function*, paragraf *Moving-Window Integration*, dan bagian *Fiducial Mark* ada di halaman 233. Kalimat tentang lebar jendela yang disarankan dan angka 30 sampel pada 200 sampel per detik ada di paragraf sesudah persamaan (11). Halaman itu dibaca langsung dari salinan PDF di `~/.hermes/cache/scratch/explore/pan-tompkins-1985.pdf`, dan seluruh kutipan di dokumen ini disalin dari gambar halaman, bukan dari hasil ekstraksi teks.
2. Salinan penuh naskah: https://www.robots.ox.ac.uk/~gari/teaching/cdt/A3/readings/ECG/Pan+Tompkins.pdf
3. Cermin cadangan: https://people.ece.cornell.edu/land/courses/ece5030/labs/s2014/Pan_Tompkins.pdf
4. Mood A, Graybill F, Boes D. *Introduction to the Theory of Statistics.* McGraw-Hill, 1974. Dipakai di makalah sebagai rujukan perhitungan statistik pada tahap ambang, halaman 234.
5. Dokumen pendamping di vault: [[00 - low-pass-filter-equation|low-pass-filter-equation]], [[01 - high-pass-filter-equation|high-pass-filter-equation]]
6. Dokumen konvensi dan breakdown: 31 - Memahami AFIB-LITE (Masalah, Kondisi Hari Ini, Logika Matematis); 34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown
7. Notebook pendamping: `nabdha-afib-lite/model/math-equation-afib/03 - squaring-and-moving-window-integrator-equation.ipynb`
8. Data uji: PhysioNet MIT-BIH Atrial Fibrillation Database, rekaman 04015, 250 Hz, 450000 sampel. https://physionet.org/content/afdb/
