# Rata-Rata Interval RR dan Penanda Irama Pan-Tompkins

Catatan turunan lengkap untuk tahap rata-rata interval RR dan penanda irama Pan-Tompkins, persamaan (24) sampai (29) halaman 234, beserta contoh soal dan jawabannya. Semua persamaan ditulis dalam LaTeX dan dirender Obsidian. Semua angka di dokumen ini dihitung dengan Python, bukan dikutip dari ingatan. Notebook pendampingnya ada di `nabdha-afib-lite/model/math-equation-afib/05 - rr-interval-averaging-equations.ipynb`, dan dokumen pendampingnya adalah [[02 - five-point-derivative-equation|five-point-derivative-equation]] serta [[03 - squaring-and-moving-window-integrator-equation|squaring-and-moving-window-integrator-equation]].

Tujuan dokumen ini: setelah membacanya, Anda bisa menjelaskan mengapa ada dua rata-rata interval RR dan apa bedanya, menurunkan rata-rata delapan interval sebagai penjumlah bergeser tanpa pengali, menyebut tiga batas sebagai pengali tetap beserta biaya aproksimasi pangkat duanya, menjalankan prosedur search back langkah demi langkah, menjelaskan arti penanda irama teratur, menghitung satu deret interval RR dengan tangan, dan menjelaskan mengapa batas bawah 0,92 tidak boleh diaproksimasi sembarangan pada konvensi fixed-point yang sudah dikunci.

Tahap ini adalah tahap terakhir sebelum keputusan denyut. Masukannya adalah urutan kompleks QRS yang sudah keluar dari tahap ambang, dan keluarannya adalah laju dasar, tiga batas waktu, dan satu penanda irama teratur. Yang tidak dikerjakan di sini adalah aturan diskriminasi gelombang T, dan antarmukanya ditulis di bagian 11.

## 1. Variabel dan notasi

| Simbol | Arti | Keterangan |
|---|---|---|
| $n$ | indeks denyut | bilangan bulat, $n \ge 7$ supaya delapan interval tersedia |
| $RR_n$ | interval RR ke-$n$ | jarak waktu dua kompleks QRS berurutan |
| $RR'_n$ | interval RR yang lolos batas | hanya yang berada di antara $RR_{LOW}$ dan $RR_{HIGH}$ |
| $RR_{AVERAGE1}$ | rata-rata delapan interval terakhir | persamaan (24), tanpa penyaringan sama sekali |
| $RR_{AVERAGE2}$ | rata-rata interval yang lolos | persamaan (25), dasar ketiga batas |
| $RR_{LOW}$ | batas bawah | persamaan (26), 92 persen $RR_{AVERAGE2}$ |
| $RR_{HIGH}$ | batas atas | persamaan (27), 116 persen $RR_{AVERAGE2}$ |
| $RR_{MISSED}$ | batas kelewatan | persamaan (28), 166 persen $RR_{AVERAGE2}$ |
| $S_8[n]$ | jumlah delapan interval terakhir | $S_8[n] = \sum_{k=0}^{7} RR_{n-k}$ |
| $b$ | jumlah interval yang lolos batas | dari 0 sampai 8 di antara delapan terakhir |
| $T$ | periode satu denyut | $T = 60 / \text{laju}$ |
| $f_s$ | laju sampel | 250 Hz pada rancangan terkunci AFIB-LITE |
| $\leftarrow$ | penugasan | persamaan (29), $RR_{AVERAGE2} \leftarrow RR_{AVERAGE1}$ |

Angka-angka penting ditulis tebal: **delapan** adalah panjang jendela rata-rata, **0,125** adalah faktor skalanya yang setara geser kanan tiga bit, **92**, **116**, dan **166** persen adalah tiga pengali batas, dan **0,66** adalah bagian dari satu interval yang menjadi tunda tambahan prosedur search back.

Satu kalimat sumber yang perlu diingat sejak awal, karena seluruh bagian 3 sampai bagian 8 adalah penguraiannya. Halaman 234 berbunyi: "Two RR-interval averages are maintained. One is the average of the eight most-recent beats. The other is the average of the eight most-recent beats having RR intervals that fall within certain limits. The reason for maintaining these two separate averages is to be able to adapt to quickly changing or irregular heart rates."

## 2. Persamaan (24), rata-rata delapan interval sebagai penjumlah bergeser

Bentuk asli di halaman 234 adalah

$$
RR_{AVERAGE1} = 0{,}125 \left( RR_{n-7} + RR_{n-6} + \cdots + RR_{n} \right)
$$

dengan keterangan "where $RR_n$ is the most-recent RR interval". Tulis jumlah delapan interval terakhir sebagai satu besaran tersendiri:

$$
S_8[n] = \sum_{k=0}^{7} RR_{n-k} = RR_{n-7} + RR_{n-6} + \cdots + RR_{n}
$$

maka

$$
RR_{AVERAGE1} = 0{,}125 \, S_8[n] = \frac{S_8[n]}{8}
$$

Faktor 0,125 sama dengan dua pangkat tiga negatif, yaitu $2^{-3}$, jadi perkaliannya menjadi geser kanan tiga bit. Yang lebih penting untuk perangkat keras, jumlahnya sendiri tidak perlu dihitung dari delapan suku setiap denyut. Kurangi $S_8[n]$ dengan $S_8[n-1]$:

$$
S_8[n] - S_8[n-1] = RR_{n} - RR_{n-8}
$$

sehingga

$$
S_8[n] = S_8[n-1] + RR_{n} - RR_{n-8}
$$

Dua operasi saja per denyut: satu interval baru masuk, satu interval tertua keluar. Itulah sebabnya yang dibutuhkan hanyalah penampan melingkar delapan kata, dan pada konvensi terkunci penampan melingkar memang sudah dipakai untuk jendela integrasi 37 dan 38 sampel.

### 2.1 Galat geser kanan tiga bit

Untuk bilangan bulat, geser kanan tiga bit sama dengan pembagian delapan dengan pembulatan ke bawah, bukan sama dengan nilai pecahannya. Selisihnya adalah sisa bagi terhadap delapan, dibagi delapan, jadi selalu di bawah 0,875. Notebook mengujinya pada 6000 interval bilangan bulat acak dalam rentang 250 sampai 2000 ms, dan hasilnya:

| Besaran | Nilai terukur |
|---|---|
| Jumlah jendela diuji | 5993 |
| Identitas $8 \lfloor S_8/8 \rfloor \le S_8$ | benar untuk seluruh jendela |
| Identitas $S_8 < 8 \lfloor S_8/8 \rfloor + 8$ | benar untuk seluruh jendela |
| Galat maksimum geser kanan 3 | 0,8750 |
| Galat rata-rata geser kanan 3 | 0,4312 |
| Fraksi jendela dengan galat nol | 0,1312 |
| Galat maksimum dengan pembulatan tambah 4 lebih dulu | 0,5000 |
| Galat rata-rata dengan pembulatan tambah 4 | 0,2455 |

Jadi dua baris terakhir itu pilihan rancangan: tanpa pembulatan galatnya sampai 0,875 satuan, dengan penambahan empat sebelum geser galatnya paling besar 0,5 satuan. Pada laju 250 Hz satu interval RR dalam milidetik selalu kelipatan empat, sehingga sisa baginya hanya nol atau empat dan galatnya paling besar 0,5 ms.

### 2.2 Angka terukur pada rekaman AFDB 04015

Deret RR rekaman itu dibangun dari keluaran tahap integrasi jendela bergantian. Satu sifat tak terduga terukur di situ dan perlu ditulis sebelum angka lainnya.

| Besaran | Nilai terukur |
|---|---|
| Panjang rekaman | 450.000 sampel, 1800,0 detik |
| Sampel terjepit pada plus minus 2047 | 402 sampel, yaitu 0,089 persen |
| Puncak pemetik A, ambang persentil | 2523 |
| Puncak pemetik B, ambang adaptif | 2660 |
| Kesesuaian dua pemetik dalam 100 ms | 2364 dari 2523, yaitu 0,9370 |
| Interval RR yang lolos topeng mutu | 2269 dari 2522, yaitu 0,8997 |
| Interval RR dalam milidetik yang kelipatan 8 | 2522 dari 2522, yaitu 1,0000 |
| RR di luar rentang 250 sampai 2000 ms | 10 dari 2522, yaitu 0,0040 |
| Laju denyut median | 81,52 denyut per menit |

Sebab kelipatan delapan itu adalah jendela bergantian. Pada rekaman, puncak selubung yang dipilih pemetik selalu jatuh pada indeks ganjil, 1,0000 dari 2523 puncak, sedangkan pada jendela tetap 38 sampel hanya 0,4796 yang ganjil. Rata-rata nilai selubung pada indeks ganjil 2,004484 kali sepuluh pangkat dua belas, dan pada indeks genap 1,951732 kali sepuluh pangkat dua belas, rasionya 1,027028. Jendela 38 sampel selalu jatuh pada indeks ganjil, jadi untuk sinyal tidak negatif jumlah jendelanya selalu sedikit lebih besar di sana, dan puncaknya terbias ke sana. Akibat lanjutannya dua: penanda waktu denyut terkunci pada kelipatan dua sampel, dan galat geser kanan tiga bit pada rekaman ini terukur nol seluruhnya.

Satu jendela teladan dari rekaman, delapan interval pertama: 584, 600, 944, 576, 576, 960, 584, dan 600 ms. Jumlahnya 5424, digeser kanan tiga bit menjadi 678, dan dibagi delapan juga 678,0000. Dua jalan, satu angka.

## 3. Mengapa ada dua rata-rata dan apa bedanya

Makalah menyebut alasannya dalam satu kalimat: "to be able to adapt to quickly changing or irregular heart rates". Yang membedakan keduanya adalah perannya, dan peran itu saling mengunci dalam tiga titik.

1. Tiga batas persamaan (26) sampai (28) ditetapkan dari $RR_{AVERAGE2}$, karena batas yang ditetapkan dari rata-rata yang sudah disaring tidak akan tersapu oleh satu interval palsu.
2. Bila kedelapan interval terakhir semuanya berada di dalam batas, persamaan (29) memaksa $RR_{AVERAGE2}$ sama dengan $RR_{AVERAGE1}$. Jadi saat ritme benar-benar teratur, kedua rata-rata itu bertemu kembali, dan itulah satu-satunya jalan keluarnya kembali dari keadaan tersaring.
3. Bila tidak semua interval lolos, $RR_{AVERAGE2}$ dibiarkan memakai interval yang lolos saja, sehingga ia memegang laju dasar dan tidak ikut melompat mengikuti interval yang tidak wajar.

### 3.1 Dua bacaan persamaan (25)

Persamaan (25) menjumlahkan delapan interval bertanda aksen, sedangkan kalimat di atasnya menyebut rata-rata kedua sebagai "the average of the eight most-recent beats having RR intervals that fall within certain limits". Dari dua kalimat itu lahir dua bacaan yang sah, dan keduanya diukur di notebook:

| Bacaan | Isi | Kelebihan | Cacat |
|---|---|---|---|
| Langsung | rata-rata interval yang lolos di antara delapan interval terakhir | selalu memakai interval segar | jumlah sampelnya bisa nol sehingga rata-rata membeku |
| Antrean | rata-rata delapan interval lolos terakhir, yaitu bacaan harfiah persamaan (25) | selalu memakai delapan sampel | angka yang dipegang bisa sudah tua |

### 3.2 Berapa sering kedua rata-rata berbeda

| Bacaan | Langkah diuji | Berbeda lebih dari 0,5 ms | Beda median | Beda maksimum | Berbeda pada kelas N | Beda median kelas N | Berbeda pada kelas AFIB | Beda median kelas AFIB |
|---|---|---|---|---|---|---|---|---|
| Langsung | 2515 | 0,6425 | 132,667 ms | 1180,000 ms | 0,5821 | 64,000 ms | 1,0000 | 327,000 ms |
| Antrean | 2515 | 0,6406 | 123,000 ms | 894,000 ms | 0,5797 | 59,000 ms | 1,0000 | 331,000 ms |

Bacaan tabelnya begini. Pada seluruh rekaman kedua rata-rata berbeda pada 64,25 persen langkah, dan pada kelas AFIB keduanya berbeda pada 100,00 persen langkah dengan beda median 327 ms. Artinya pada fibrilasi atrium rata-rata yang disaring tidak pernah menyamai rata-rata yang tidak disaring, dan itulah perilaku yang diharapkan: yang disaring sengaja tidak mengikuti interval yang tidak wajar. Yang lebih penting untuk rancangan adalah ekornya, yaitu beda maksimum 1180 ms, dan sebabnya diterangkan di bagian 3.3.

### 3.3 Apa yang terjadi saat banyak interval jatuh di luar batas

Jawaban atas pertanyaan apakah $RR_{AVERAGE2}$ menjadi tidak stabil karena memakai sedikit sampel adalah tidak, tetapi ada cacat lain yang lebih halus, yaitu pembekuan. Sebaran jumlah interval yang lolos $b$ pada bacaan langsung:

| Jumlah lolos $b$ | Langkah | Fraksi |
|---|---|---|
| 0 | 875 | 0,3479 |
| 1 | 204 | 0,0811 |
| 2 sampai 3 | 285 | 0,1133 |
| 4 sampai 6 | 206 | 0,0819 |
| 7 atau 8 | 945 | 0,3757 |

Rata-rata $b$ adalah 3,7237 dengan minimum 0. Pada 34,79 persen langkah tidak ada satu pun interval yang lolos, dan pada keadaan itu $RR_{AVERAGE2}$ tidak berubah, terbukti karena pada 0,9737 langkah dengan $b$ sama dengan nol perubahannya nol. Kegoyahan yang muncul saat $b$ kecil justru lebih kecil daripada saat $b$ besar:

| Jumlah lolos $b$ | Langkah | Perubahan median $RR_{AVERAGE2}$ | Perubahan maksimum |
|---|---|---|---|
| 0 | 1079 | 0,000 ms | 96,000 ms |
| 1 | 369 | 0,000 ms | 81,600 ms |
| 2 sampai 3 | 388 | 3,267 ms | 64,000 ms |
| 4 sampai 6 | 253 | 2,400 ms | 39,600 ms |
| 7 atau 8 | 944 | 1,000 ms | 15,857 ms |

Baris pertama menunjukkan mekanismenya: dengan nol sampel, keluaran tidak bergoyang karena tidak ada yang dihitung, dan yang terjadi adalah pembekuan. $RR_{AVERAGE2}$ berubah pada 1082 dari 2514 langkah, jeda bekunya median 1 denyut, dan jeda terpanjang 413 denyut, yaitu 304,0 detik, dengan nilai yang dipegang tetap 996,0 ms. Jadi cacat sesungguhnya bukan goyangan melainkan angka yang basi selama lima menit, dan itu perlu disadari karena $RR_{AVERAGE2}$ menetapkan batas $RR_{MISSED}$ yang dipakai prosedur search back.

## 4. Persamaan (26) sampai (28), tiga batas sebagai pengali tetap

Bentuk asli di halaman 234 adalah

$$
RR_{LOW} = 0{,}92 \, RR_{AVERAGE2}
$$

$$
RR_{HIGH} = 1{,}16 \, RR_{AVERAGE2}
$$

$$
RR_{MISSED} = 1{,}66 \, RR_{AVERAGE2}
$$

Dalam aritmetika pecahan tepat ketiganya adalah bilangan rasional sederhana:

$$
0{,}92 = \frac{23}{25}, \qquad 1{,}16 = \frac{29}{25}, \qquad 1{,}66 = \frac{83}{50}
$$

Tidak satu pun dari ketiganya pangkat dua, jadi tidak satu pun menjadi geser bit tunggal. Untuk membandingkan $RR$ dengan batas, bentuk perangkat keras yang dipakai adalah perkalian silang:

$$
RR \ge \frac{23}{25} RR_{AVERAGE2} \iff 25 \, RR \ge 23 \, RR_{AVERAGE2}
$$

$$
RR \le \frac{29}{25} RR_{AVERAGE2} \iff 25 \, RR \le 29 \, RR_{AVERAGE2}
$$

$$
RR > \frac{83}{50} RR_{AVERAGE2} \iff 50 \, RR > 83 \, RR_{AVERAGE2}
$$

Bentuk itu tidak punya pembagian, jadi tidak ada galat pembulatan sama sekali, tetapi ia memerlukan pengali dengan konstanta 25 dan 50. Aproksimasi berpenyebut pangkat dua menggantikan pengali itu dengan geser dan tambah, dengan harga pergeseran letak batas.

### 4.1 Tiga kandidat aproksimasi

Penyebut diseragamkan menjadi 32 supaya satu jalur data dapat melayani ketiganya:

$$
\frac{30}{32} = 1 - \frac{1}{16} = 0{,}9375, \qquad \frac{37}{32} = 1 + \frac{5}{32} = 1{,}15625, \qquad \frac{53}{32} = 1 + \frac{21}{32} = 1{,}65625
$$

Kandidat kedua yang lebih halus memakai penyebut 64:

$$
\frac{59}{64} = 0{,}921875, \qquad \frac{74}{64} = 1{,}15625, \qquad \frac{106}{64} = 1{,}65625
$$

Bentuk geser dan tambahnya, dengan $x$ adalah $RR_{AVERAGE2}$:

| Aproksimasi | Nilai | Bentuk geser dan tambah | Geser | Tambah | Kurang |
|---|---|---|---|---|---|
| Bawah penyebut 32 | 0,9375 | $(x \ll 4) - x$ lalu $\gg 4$ | 2 | 0 | 1 |
| Bawah penyebut 64 | 0,921875 | $(x \ll 6) - (x \ll 2) - x$ lalu $\gg 6$ | 3 | 0 | 2 |
| Atas penyebut 32 dan 64 | 1,15625 | $(x \ll 5) + (x \ll 2) + x$ lalu $\gg 5$ | 3 | 2 | 0 |
| Missed penyebut 32 | 1,65625 | $(x \ll 5) + (x \ll 4) + (x \ll 2) + x$ lalu $\gg 5$ | 4 | 3 | 0 |
| Missed penyebut 64 | 1,65625 | $(x \ll 6) + (x \ll 5) + (x \ll 3) + (x \ll 1)$ lalu $\gg 6$ | 5 | 3 | 0 |

Seluruh bentuk geser itu diperiksa terhadap pembagian bulat pada setiap nilai bulat $x$ dari 250 sampai 1999, dan seluruhnya cocok. Perlu dicatat bahwa bentuk penyebut 32 untuk batas bawah dan bentuk penyebut 64 untuk batas atas serta batas missed adalah dua pengali yang sama nilainya dengan kandidat terdahulu, jadi yang benar benar bertambah halus hanya batas bawah.

### 4.2 Pergeseran letak batas

| Batas | $RR_{AVERAGE2}$ | Nilai tepat | Aproksimasi 32 | Pergeseran 32 | Aproksimasi 64 | Pergeseran 64 |
|---|---|---|---|---|---|---|
| Bawah | 500 ms | 460,000 ms | 468,750 ms | +8,750 ms | 460,9375 ms | +0,9375 ms |
| Bawah | 600 ms | 552,000 ms | 562,500 ms | +10,500 ms | 553,1250 ms | +1,1250 ms |
| Bawah | 800 ms | 736,000 ms | 750,000 ms | +14,000 ms | 737,5000 ms | +1,5000 ms |
| Bawah | 1000 ms | 920,000 ms | 937,500 ms | +17,500 ms | 921,8750 ms | +1,8750 ms |
| Atas | 800 ms | 928,000 ms | 925,000 ms | $-3{,}000$ ms | 925,0000 ms | $-3{,}0000$ ms |
| Missed | 800 ms | 1328,000 ms | 1325,000 ms | $-3{,}000$ ms | 1325,0000 ms | $-3{,}0000$ ms |

Galat relatifnya terhadap nilai persis: batas bawah naik 1,9022 persen pada penyebut 32 dan 0,2038 persen pada penyebut 64, batas atas turun 0,3233 persen, dan batas missed turun 0,2259 persen. Arah pergeserannya perlu diperhatikan karena tidak seluruhnya sama: batas bawah naik sehingga penyaringan menjadi lebih ketat, sedangkan batas atas dan batas missed turun sehingga keduanya menjadi lebih longgar.

### 4.3 Biaya keputusan aproksimasi

Rekaman AFDB 04015 hanya membawa anotasi ritme, yaitu lima belas penanda perubahan irama, dan tidak membawa anotasi denyut. Karena itu sensitivitas dan spesifisitas di sini didefinisikan pada tingkat keputusan, dengan aritmetika pecahan tepat sebagai acuan: sensitivitas adalah bagian keputusan benar yang tetap diakui aproksimasi, dan spesifisitas adalah bagian keputusan salah yang tetap ditolak aproksimasi. Ini bukan unjuk kerja deteksi terhadap rujukan denyut, dan tidak boleh dibaca sebagai itu.

Mode pertama, yaitu arus $RR_{AVERAGE2}$ dibekukan supaya pergeseran batas terukur sendirian:

| Keputusan | TP | FN | FP | TN | Sensitivitas | Spesifisitas |
|---|---|---|---|---|---|---|
| Penanda irama teratur | 849 | 51 | 0 | 1615 | 0,943333 | 1,000000 |
| Interval masuk $RR_{AVERAGE2}$ | 1145 | 14 | 0 | 1356 | 0,987921 | 1,000000 |
| Lewat batas missed | 86 | 0 | 0 | 2429 | 1,000000 | 1,000000 |

Bacaan tabelnya begini. Aproksimasi tidak pernah membuat keputusan baru yang seharusnya tidak dibuat, karena kolom FP nol seluruhnya dan spesifisitasnya satu. Yang hilang adalah pengakuan: 51 dari 900 penyalaan penanda irama teratur hilang, dan 14 dari 1159 pengakuan interval hilang. Batas missed tidak terpengaruh sama sekali pada arus yang sama, karena aproksimasinya hanya berbeda 3 ms pada 800 ms.

Mode kedua, yaitu lingkar tertutup penuh, dan di sinilah biaya sesungguhnya terlihat:

| Kombinasi | Penanda langsung | Penanda antrean | Beda $RR_{AVERAGE2}$ rata-rata | Beda maksimum | Lewat batas missed |
|---|---|---|---|---|---|
| Tepat, 23/25 dan 29/25 dan 83/50 | 898 | 902 | 0,000 ms | 0,000 ms | 87 |
| Hanya batas bawah kasar, 30/32 | 9 | 12 | 113,428 ms | 458,667 ms | 77 |
| Hanya batas atas kasar, 37/32 | 889 | 902 | 8,651 ms | 300,000 ms | 89 |
| Hanya batas missed kasar, 53/32 | 898 | 902 | 0,000 ms | 0,000 ms | 87 |
| Ketiganya kasar | 9 | 12 | 113,378 ms | 458,667 ms | 77 |
| Batas bawah halus, 59/64 | 890 | 893 | 0,871 ms | 160,000 ms | 87 |
| Ketiganya halus, penyebut 64 | 881 | 893 | 9,427 ms | 300,000 ms | 89 |

Inilah temuan yang paling mengejutkan di seluruh fase ini, dan letaknya di baris kedua. **Catatan koreksi 19 Oktober 2026.** Keruntuhan penanda dari 898 menjadi 9 itu hanya berlaku pada deret interval acuan. Pada rantai penuh dengan deret denyut detektor kita sendiri, keruntuhan itu tidak muncul, dan dengan pemotongan separuh ambang hidup, bentuk 30 per 32 justru menaikkan penanda dari 1.005 menjadi 1.034, jadi kedua risiko itu saling meniadakan sebagian. Larangan memakai 30 per 32 sekarang berdiri di atas dua dasar yang tetap sah, yaitu pergeseran batas bawah 15,2 milidetik pada rata-rata 800 milidetik dan biaya bentuk eksak 23 per 25 yang ternyata sama murahnya. Rinciannya di [[07 - combined-risk-measurements|combined-risk-measurements]]. Mengganti batas bawah dari 0,92 menjadi 0,9375, yaitu pergeseran relatif hanya 1,9022 persen, menurunkan penyalaan penanda irama teratur dari 898 kali menjadi 9 kali, sedangkan mengganti batas atas atau batas missed hampir tidak mengubah apa pun. Penyebabnya adalah umpan balik pada persamaan (25) sampai (29): batas bawah yang lebih tinggi membuang interval yang lebih pendek dari rata-rata, rata-rata yang dibuang itu menjadi lebih kecil, batasnya ikut mengecil, dan seterusnya sampai rata-rata terkunci pada satu nilai. Pada bacaan langsung, fraksi langkah yang kedua rata-ratanya berbeda naik dari 0,6425 menjadi 0,9960 pada versi kasar.

Baris keenam menunjukkan bahwa keruntuhan itu bukan sifat yang melekat pada penanda, melainkan akibat langsung dari pergeseran 1,9022 persen itu, dan sesudah pengukuran ulang di [[07 - combined-risk-measurements|combined-risk-measurements]] syaratnya dipersempit menjadi hanya pada deret interval acuan. Dengan batas bawah 59/64, yaitu galat relatif 0,2038 persen, penyalaan penandanya kembali menjadi 890 kali, hanya 8 kali lebih sedikit daripada aritmetika tepat. Dua jejak $RR_{AVERAGE2}$ bercabang lebih dari 1 ms pertama kali pada langkah ke-20, yaitu denyut ke-27 atau detik ke-18,9, dan beda maksimumnya kemudian mencapai 458,667 ms.

Kesimpulan yang dapat dipakai tim: batas atas dan batas missed aman diaproksimasi dengan penyebut 32, sedangkan batas bawah tidak. Kalau batas bawah harus dihindari dari pengali, aproksimasi terdekat yang masih aman adalah 59/64, yang harganya satu pengurangan tambahan.

## 5. Prosedur search back langkah demi langkah

Kalimat makalah persisnya di halaman 234: "If a QRS complex is not found during the interval specified by the RR MISSED LIMIT, the maximal peak reserved between the two established thresholds is considered to be a QRS candidate." Kalimat itu memuat seluruh prosedurnya, dan langkahnya dapat ditulis berurutan.

1. Sebelum pemeriksaan, ada dua ambang pada tiap jalur, ambang pertama $I1$ dan ambang kedua $I2$ yang nilainya separuh $I1$, ditetapkan dari $SPKI$ dan $NPKI$ menurut persamaan (14) dan (15).
2. Selama sinyal berjalan, setiap puncak lokal yang nilainya di atas ambang kedua tetapi di bawah ambang pertama tidak diangkat menjadi denyut, melainkan disimpan sebagai puncak cadangan. Inilah arti "between the two established thresholds", dan puncak itu harus disimpan bersama posisinya supaya penanda waktunya benar bila nanti diangkat.
3. Bersamaan dengan itu, jarak antara waktu sekarang dan waktu denyut terakhir yang sudah diangkat terus dibandingkan dengan $RR_{MISSED}$ pada persamaan (28).
4. Bila jarak itu melampaui $RR_{MISSED}$ padahal tidak ada denyut yang ditemukan, puncak cadangan dengan nilai terbesar di dalam selang itu diangkat menjadi calon kompleks QRS. Yang diambil adalah yang terbesar, bukan yang pertama, sesuai kata "maximal peak".
5. Penanda waktu hasil pengangkatan adalah posisi puncak cadangan itu, bukan waktu pemeriksaannya. Karena itu interval RR sesudah pengangkatan tetap benar, dan ini penting bagi persamaan (24).
6. Bila puncak itu diangkat, $SPKI$ dan $SPKF$ diperbarui dengan bobot seperempat, yaitu persamaan (21), bukan dengan bobot seperdelapan seperti pendeteksian biasa. Bobot yang lebih besar itu yang membuat ambang bergerak lebih cepat setelah pengangkatan.
7. Kalau tidak ada puncak cadangan di dalam selang itu, tidak ada yang diangkat, dan pemeriksaan diulang pada selang berikutnya.

### 5.1 Angka terukur pada deret buatan

Deret buatan berisi 60 denyut dengan interval tetap 800 ms, dua ambang $I1$ sama dengan 1,5 dan $I2$ sama dengan 0,75, dan satu atau dua denyut yang amplitudonya dikecilkan sampai 1,0 sehingga jatuh tepat di antara kedua ambang.

| Keadaan | Denyut terdeteksi | Puncak diangkat | Pemeriksaan lewat batas | Tunda pengangkatan | Tunda dalam denyut |
|---|---|---|---|---|---|
| Satu denyut hilang | 60 dari 60 | 1 | 1 | 532,0 ms | 0,6650 |
| Dua denyut hilang | 60 dari 60 | 2 | 1 | 532,0 ms dan 532,0 ms | 0,6650 dan 0,6650 |

Tunda itu dapat dihitung lebih dulu tanpa pengukuran. Batas missed 166 persen berarti selang pemeriksaan 1,66 kali interval RR yang berlaku, dan interval RR yang berlaku adalah satu kali periode denyut. Selisih keduanya adalah

$$
\text{tunda} = 1{,}66 \, RR - RR = 0,66 \, RR
$$

Pada 800 ms hasilnya 528,0 ms, sedangkan yang terukur 532,0 ms. Selisih 4,0 ms itu tepat satu sampel pada 250 Hz, dan muncul karena pemeriksaan pada implementasi dilakukan per sampel, bukan per waktu yang kontinu. Jadi tunda tambahan search back adalah 0,66 interval RR atau 66 persen satu periode denyut: pada 60 denyut per menit menjadi 660 ms, pada 120 denyut per menit menjadi 330 ms.

Dua akibat rancangan yang perlu dicatat dari tabel itu. Pertama, pengangkatan selalu satu puncak per denyut yang hilang, tidak lebih, bahkan ketika dua denyut berturut-turut hilang, karena denyut yang diangkat pertama menetapkan ulang titik hitung sehingga pemeriksaan kedua jatuh tepat di selang yang baru. Kedua, seluruh interval RR pada deret buatan itu kembali menjadi tepat 800 ms sesudah pengangkatan, dengan simpangan terbesar 0,000 ms. Jadi prosedur search back memulihkan deret RR seolah tidak ada denyut yang hilang, dan seluruh isi dokumen ini bergantung pada pemulihan itu. Tanpa prosedur itu, tiap denyut yang hilang menyumbang satu interval palsu sebesar dua kali periode, dan pada rekaman uji itu kejadian lewat batas terukur 87 kali tanpa topeng mutu dan 11 kali dengan topeng mutu.

Satu syarat yang harus dipenuhi supaya prosedur ini dapat berjalan: pada konvensi terkunci dipakai penampan melingkar, dan prosedur ini memerlukan penampan serupa untuk puncak cadangan, yaitu satu register nilai dan satu register posisi per puncak di dalam selang $RR_{MISSED}$. Tanpa penampan itu tidak ada yang dapat diangkat.

## 6. Penanda irama teratur, persamaan (29)

Persamaan (29) memberi penanda satu bit. Kalimat lengkapnya di halaman 234: "If each of the eight most-recent sequential RR intervals that are calculated from RR AVERAGE1 is between the RR LOW LIMIT and the RR HIGH LIMIT, we interpret the heart rate to be regular for these eight heart beats and", lalu persamaan (29), yaitu

$$
RR_{AVERAGE2} \leftarrow RR_{AVERAGE1}
$$

dan penutupnya "This is the case for normal sinus rhythm." Jadi arti penanda itu ada dua lapis. Lapis pertama adalah pernyataannya sendiri, yaitu bahwa delapan denyut terakhir berirama teratur, dan makalah menyebutnya sebagai irama sinus normal. Lapis kedua adalah tindakannya, yaitu menugasi $RR_{AVERAGE2}$ sama dengan $RR_{AVERAGE1}$, dan itulah satu-satunya jalan bagi rata-rata yang disaring untuk kembali ke rata-rata yang tidak disaring.

Ada satu kalimat lain di halaman yang sama yang membuat penanda ini bukan sekadar keluaran laporan. Kalimat itu berbunyi: "For irregular heart rates, the first threshold of each set is reduced by half so as to increase the detection sensitivity and to avoid missing beats", yaitu persamaan (22) dan (23). Jadi hasil penanda irama teratur dipakai tahap ambang: saat irama tidak teratur, ambang pertama dibelah dua supaya denyut tidak terlewat. Akibatnya kedua tahap itu saling bergantung, dan penanda ini bukan hiasan.

### 6.1 Penghitungan penyalaan pada rekaman

| Lingkup | Langkah | Menyala | Fraksi |
|---|---|---|---|
| Seluruh rekaman, bacaan langsung | 2515 | 898 | 0,3571 |
| Seluruh rekaman, bacaan antrean | 2515 | 902 | 0,3586 |
| Kelas N | 2151 | 898 | 0,4175 |
| Kelas AFIB | 364 | 0 | 0,0000 |
| Kelas N dengan topeng mutu | 1975 | 1210 | 0,6127 |
| Kelas AFIB dengan topeng mutu | 287 | 0 | 0,0000 |

Tabel per jendela kelas irama, memakai anotasi ritme rekaman:

| Kelas | Durasi | Denyut | Menyala | Fraksi menyala | Laju denyut |
|---|---|---|---|---|---|
| N | 410,216 s | 556 | 9 | 0,0162 | 90,36 bpm |
| AFIB | 68,080 s | 123 | 0 | 0,0000 | 119,05 bpm |
| N | 8,676 s | 12 | 0 | 0,0000 | 81,08 bpm |
| AFIB | 1,684 s | 3 | 0 | 0,0000 | 108,70 bpm |
| N | 44,616 s | 71 | 0 | 0,0000 | 105,63 bpm |
| AFIB | 134,036 s | 238 | 0 | 0,0000 | 119,05 bpm |
| N | 1132,572 s | 1512 | 889 | 0,5880 | 80,65 bpm |

### 6.2 Apakah penanda itu layak dipakai sebagai gerbang

Angka di atas memberi jawaban berlapis, dan seluruh lapisnya perlu dilihat.

Pertama, sisi sensitifnya kuat. Penanda itu tidak menyala satu kali pun pada ketiga jendela beranotasi AFIB, 0 dari 364 langkah, dan itu juga berlaku setelah topeng mutu diterapkan, 0 dari 287 langkah. Jadi penanda itu memang memisahkan irama fibrilasi dari irama teratur pada arah yang benar.

Kedua, sisi spesifiknya lemah pada rekaman ini. Dari empat jendela beranotasi N, hanya jendela terpanjang yang penandanya menyala sering, yaitu 0,5880. Tiga jendela N yang lain menyala 0,0162, 0,0000, dan 0,0000. Dengan gerbang sederhana "fraksi menyala di bawah 0,10 berarti tidak teratur, dan tidak teratur berarti AFIB", penilaian pada tingkat jendela menghasilkan 4 jendela benar dan 3 jendela salah dari 7 jendela. Tiga kesalahan itu seluruhnya jendela beranotasi N yang penandanya tidak menyala.

Ketiga, sebagian kesalahan itu soal panjang jendela, bukan soal irama. Penanda memerlukan delapan interval sebagai riwayat, dan jendela N yang panjangnya 8,676 s hanya berisi 12 denyut serta jendela 44,616 s hanya berisi 71 denyut, jadi keduanya memang tidak punya cukup banyak kesempatan untuk menyala. Yang tersisa dan tidak dapat dibela adalah jendela N pertama, 410,216 s dengan 556 denyut, yang penandanya hanya menyala 0,0162. Jendela itu beranotasi N tetapi simpangan baku RR relatifnya 0,5977, jadi memang tidak teratur meskipun bukan fibrilasi atrium. Label N di basis data itu berarti bukan AFIB, bukan berarti teratur.

Kesimpulan untuk tim: penanda irama teratur layak dipakai sebagai satu fitur tambahan, dan tidak layak dipakai sebagai gerbang tunggal. Penanda itu punya sensitivitas yang baik terhadap fibrilasi atrium, tetapi juga menyala jarang pada irama yang tidak teratur karena sebab lain, dan angka penyalaannya sangat peka terhadap nilai batas bawah seperti terukur di bagian 4.3.

Satu angka pendukung yang perlu dicatat: panjang jendela penanda itu bukan tetap dalam detik, melainkan delapan denyut. Pada laju 180 bpm jendelanya 2,666667 s, sedangkan pada 40 bpm jendelanya 12,0 s. Jadi pada takikardia penanda dapat berubah keadaan beberapa kali per detik, sedangkan pada bradikardia ia baru dapat berubah setelah dua belas detik.

## 7. Tabel hitung tangan satu deret interval RR

Contoh ini memakai enam belas interval RR dalam milidetik, seluruhnya kelipatan empat seperti yang terjadi pada laju 250 Hz, dengan dua interval menyimpang: satu panjang 1040 ms dan satu pendek 560 ms. Kolom jumlah delapan interval dihitung dua kali, sekali langsung dan sekali bergeser, dan kedua kolom itu sama pada seluruh langkah.

| $k$ | $RR_k$ | $S_8[k]$ langsung | $S_8[k]$ bergeser | $S_8[k] \gg 3$ | $RR_{AVERAGE1}$ | Selisih geser | Batas bawah | Batas atas | $b$ | $RR_{AVERAGE2}$ | Penanda |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | 800 | 6400 | 6400 | 800 | 800,000 | 0,000 | 736,000 | 928,000 | 8 | 800,000 | menyala |
| 8 | 1040 | 6640 | 6640 | 830 | 830,000 | 0,000 | 736,000 | 928,000 | 7 | 800,000 | tidak |
| 9 | 560 | 6396 | 6396 | 799 | 799,500 | 0,500 | 735,387 | 927,227 | 6 | 799,333 | tidak |
| 10 | 800 | 6400 | 6400 | 800 | 800,000 | 0,000 | 736,000 | 928,000 | 6 | 800,000 | tidak |
| 11 | 800 | 6400 | 6400 | 800 | 800,000 | 0,000 | 736,000 | 928,000 | 6 | 800,000 | tidak |
| 12 | 1200 | 6788 | 6788 | 848 | 848,500 | 0,500 | 733,792 | 925,216 | 5 | 797,600 | tidak |
| 13 | 400 | 6400 | 6400 | 800 | 800,000 | 0,000 | 736,000 | 928,000 | 4 | 800,000 | tidak |
| 14 | 800 | 6400 | 6400 | 800 | 800,000 | 0,000 | 736,000 | 928,000 | 4 | 800,000 | tidak |
| 15 | 800 | 6400 | 6400 | 800 | 800,000 | 0,000 | 736,000 | 928,000 | 4 | 800,000 | tidak |

Empat hal yang bisa dibaca dari tabel itu, dan semuanya adalah mekanika yang sudah dijelaskan di atas.

Pertama, baris $k = 8$ adalah contoh paling jelas bedanya kedua rata-rata. Interval yang masuk panjangnya 1040 ms, jadi $RR_{AVERAGE1}$ naik menjadi 830,000 ms, sedangkan $RR_{AVERAGE2}$ tetap 800,000 ms karena 1040 ms berada di atas batas atas 928,000 ms dan karena itu tidak ikut dihitung. Beda keduanya 30 ms pada satu langkah.

Kedua, baris $k = 9$ dan $k = 12$ adalah dua baris yang galat geser kanan tiga bitnya tidak nol, yaitu 0,500 ms, karena jumlahnya tidak habis dibagi delapan. Di situ $S_8[k]$ sama dengan 6396 dan 6788, dan pembagian bulatnya memberi 799 dan 848. Galat rata-rata seluruh sembilan langkah adalah 0,1111 ms.

Ketiga, batas bawah dan batas atas bergerak karena $RR_{AVERAGE2}$ bergerak, dan $RR_{AVERAGE2}$ di baris $k = 9$ dan $k = 12$ tidak sama dengan 800,000 ms, yaitu 799,333 ms dan 797,600 ms. Jadi rata-rata yang disaring ikut turun sedikit karena interval pendek 560 ms dan 400 ms yang lolos, dan itulah umpan balik yang di bagian 4.3 terbukti berbahaya saat dikuatkan.

Keempat, penanda irama teratur hanya menyala di baris pertama, 1 dari 9 langkah, karena begitu satu interval jatuh di luar batas, kedelapan interval berikutnya masih memuat interval itu dan penanda tidak dapat menyala sampai interval itu keluar dari jendela. Inilah memori delapan denyut yang dimiliki penanda, dan panjang memorinya sama dengan panjang jendela rata-rata.

## 8. Catatan fixed-point memakai konvensi terkunci

Konvensi di bawah ini dikunci di [[afib-lite/afib-rtl/34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown]] bagian 3.7, dan seluruh angka diukur pada rekaman AFDB `04015`, 30 menit, 450.000 sampel.

1. Masukan rentangnya plus minus 5 mV dengan 12 bit signifikan, dijepit pada plus minus 2047 hitungan, lalu diletakkan di depan kata 16 bit dengan nilai digeser ke kiri 4 bit.
2. Low-pass 22 bit, high-pass 28 bit, turunan 23 bit lalu digeser kanan 8 bit sehingga faktor skala ambangnya 256.
3. Pembagian dengan 38 tidak dilakukan di RTL, dan ambangnya yang dikalikan 38. Ambang dalam satuan milivolt dikalikan 256 lebih dulu.
4. Jendela integrasi bergantian 37 dan 38 sampel, penampan melingkar dipakai, dan tanpa pengali keras bila memungkinkan.

Tahap rata-rata RR di dokumen ini bekerja pada besaran waktu, bukan pada sampel sinyal, jadi lebar bitnya ditentukan satuan waktu yang dipilih. Satu interval RR pada 250 Hz dapat disimpan sebagai jumlah sampel atau sebagai milidetik, dan keduanya 10 bit untuk rentang normal 250 sampai 2500 ms. Yang membedakan keduanya adalah galat geser kanan tiga bit pada bagian 2.1: pada milidetik paling besar 0,5 ms, pada sampel paling besar 0,875 sampel, yaitu 3,5 ms. Jadi milidetik lebih tepat untuk penanda waktu, sedangkan sampel lebih murah bila penanda waktu diambil dari penghitung sampel yang sudah ada.

### 8.1 Lebar bit terukur

| Besaran | Nilai maksimum terukur | Lebar minimum | Catatan |
|---|---|---|---|
| $RR$ | 7088 ms | 14 bit | termasuk satu celah akibat denyut yang tidak terdeteksi |
| $S_8$ jumlah delapan | 13.600 ms | 15 bit | jumlah interval terpanjang di rekaman |
| $S_8 \gg 3$ | 1700 ms | 12 bit | sama dengan $RR_{AVERAGE1}$ terbesar |
| $RR_{AVERAGE1}$ | 1700,0 ms | 12 bit | persamaan (24) |
| $RR_{AVERAGE2}$ | 1032,0 ms | 12 bit | persamaan (25), tidak pernah melebihi $RR_{AVERAGE1}$ di rekaman ini |
| Perkalian silang penyebut 32 | 226.816 | 19 bit | hasil terbesar dari $32 \, RR$ |
| Perkalian silang penyebut 64 | 226.816 | 19 bit | sama, karena faktor pada $RR$ tidak bergantung penyebut |
| Hasil antara $83 \, RR_{AVERAGE2}$ | 85.656 | 18 bit | bentuk tepat batas missed, sedangkan kolom gabungan di notebook mencetak 19 bit karena lebar tertinggi di baris itu ditentukan $32 \, RR$ |

Dua catatan dari tabel itu. Pertama, lebar bit tahap ini ditentukan oleh celah, bukan oleh irama. Tujuh interval pada rekaman lebih panjang dari 2500 ms dengan yang terpanjang 7088 ms, dan seluruhnya akibat denyut yang tidak terdeteksi. Bila $RR$ dijepit pada 4095 ms, yang cukup 13 bit, dan pilihan itu sudah ditetapkan pada 19 Oktober 2026, yaitu lebar 14 bit penuh tanpa penjepitan, seperti tertulis di bagian 9.1 butir P4-4. Kedua, satu jalur data 21 bit sudah cukup untuk seluruh perkalian silang baik pada penyebut 32 maupun 64, sehingga penambahan akumulator 22 bit menampungnya bersama bit tanda. Angka 21 bit itu kecil dibanding akumulator 32 bit yang sudah ada di rantai integrasi, jadi tahap ini bukan tahap yang menentukan lebar jalur data.

### 8.2 Bentuk perbandingan tanpa pembagian

| Batas | Bentuk perkalian silang tepat | Bentuk penyebut 32 | Bentuk penyebut 64 |
|---|---|---|---|
| Bawah | $25 \, RR \ge 23 \, RR_{AVERAGE2}$ | $32 \, RR \ge 30 \, RR_{AVERAGE2}$ | $64 \, RR \ge 59 \, RR_{AVERAGE2}$ |
| Atas | $25 \, RR \le 29 \, RR_{AVERAGE2}$ | $32 \, RR \le 37 \, RR_{AVERAGE2}$ | $64 \, RR \le 74 \, RR_{AVERAGE2}$ |
| Missed | $50 \, RR > 83 \, RR_{AVERAGE2}$ | $32 \, RR > 53 \, RR_{AVERAGE2}$ | $64 \, RR > 106 \, RR_{AVERAGE2}$ |

Karena seluruh kolom di kanan tetap berupa perkalian silang, tidak ada pembagian di jalur data pada ketiga bentuk itu. Yang berbeda hanya letak batas, dan biaya letak itu sudah terukur di bagian 4.2 dan 4.3.

### 8.3 Biaya perhitungan tiap bentuk batas

Tabel berikut dihitung notebook dari ungkapan tiap bentuk, bukan ditulis tetap, dan angkanya adalah jumlah untuk ketiga batas sekaligus.

| Bentuk | Geser | Tambah | Kurang | Pengali konstanta | Penyebut seragam |
|---|---|---|---|---|---|
| Tepat 23/25, 29/25, 83/50 | 0 | 0 | 0 | 3 | tidak |
| Kasar 30/32, 37/32, 53/32 | 9 | 5 | 1 | 0 | ya, 32 |
| Halus 59/64, 74/64, 106/64 | 11 | 5 | 2 | 0 | ya, 64 |

Tabel itu perlu dibaca bersama bagian 4.3, karena bentuk yang paling murah ternyata yang paling berbahaya. Bentuk penyebut 32 menghapus tiga pengali konstanta dengan harga tiga pengurangan tambahan dan penambahan penyebut seragam, tetapi harga sebenarnya adalah keruntuhan penanda irama teratur, dari 898 penyalaan menjadi 9. Bentuk penyebut 64 harganya satu pengurangan tambahan lagi, dan hasilnya 890 penyalaan, yaitu delapan penyalaan dari 898 pada aritmetika tepat. Jadi selisih satu pengurangan itu jauh lebih murah daripada keruntuhan penanda.

Satu hal yang tidak berubah dari fase sebelumnya: tidak ada pengali di tahap ini bila bentuk penyebut dipakai. Yang ada hanya geser, tambah, kurang, dan penampan melingkar delapan kata untuk $S_8$. Pada bentuk tepat, pengalinya ada, tetapi konstanta 25, 29, dan 50 adalah konstanta kecil, jadi pengalinya juga bukan pengali lebar penuh.

## 9. Hubungan ke keputusan AFIB-LITE

Rancangan tim memakai laju terkunci 250 Hz dan ambang yang dikalikan 38, sedangkan tahap ini bekerja pada milidetik. Empat akibat yang langsung terbaca dari pengukuran.

1. Persamaan (24) memang bebas pengali, dan itu benar tanpa syarat. Rata-rata delapan interval adalah satu penjumlah bergeser dan satu geser kanan tiga bit, dengan galat terukur nol pada rekaman ini karena seluruh intervalnya kelipatan delapan milidetik, yaitu akibat paritas jendela bergantian yang dijelaskan di bagian 2.2.
2. Tiga batas persamaan (26) sampai (28) bukan pangkat dua, dan batas bawah adalah yang paling peka. Batas atas dan batas missed aman dengan penyebut 32, sedangkan batas bawah sebaiknya memakai penyebut 64 atau tetap memakai pengali konstanta, dan yang dikunci pada 19 Oktober 2026 adalah pengali konstanta 23 per 25 lewat bentuk silang, seperti tertulis di bagian 9.1 butir P4-2.
3. $RR_{AVERAGE2}$ pada rekaman ini memakai nol sampel pada 34,79 persen langkah dan pernah beku 304,0 detik. Karena batas $RR_{MISSED}$ ditetapkan dari $RR_{AVERAGE2}$, pembekuan itu berarti jendela pemeriksaan search back juga beku. Pilihan yang ditetapkan pada 19 Oktober 2026 adalah bacaan antrean yang selalu punya delapan sampel, sehingga tidak ada lagi langkah bernol sampel, dan penetapan itu tertulis di bagian 9.1 butir P4-1.
4. Prosedur search back memerlukan penampan puncak cadangan di dalam selang $RR_{MISSED}$, dan tunda tambahan yang timbul 0,66 interval RR. Pada laju 120 bpm itu 330 ms, dan pada 60 bpm 660 ms. Tunda itu perlu diperhitungkan bila penanda waktu denyut dipakai untuk menghitung interval RR.

### 9.1 Keputusan yang dikunci 19 Oktober 2026

Lima butir yang sebelumnya masih berupa pertanyaan terbuka sudah diputuskan pada 19 Oktober 2026, dan seluruhnya menyangkut RTL serta kode host. Angka yang dikutip di bawah ini seluruhnya angka terukur dari bagian 2 sampai bagian 8 dokumen ini. Bentuk silang yang dikunci untuk batas bawah adalah

$$
25 \ RR \ge 23 \ RR_{AVERAGE2}
$$

dan keempat keputusannya adalah sebagai berikut.

1. **P4-1. Persamaan (25) dibaca sebagai rata-rata delapan interval lolos TERAKHIR, jadi selalu delapan sampel.** Bacaan lain, yaitu interval lolos di antara delapan terakhir, bisa kosong dan terukur membeku sampai 413 denyut atau 304,0 detik pada 34,79 persen langkah rekaman, dan karena ketiga batas ditetapkan dari $RR_{AVERAGE2}$ maka pembekuan itu ikut membekukan jendela pemeriksaan search back, sehingga bacaan itu ditolak.

2. **P4-2. Konstanta batas bawah memakai bentuk eksak 23 per 25 dalam bentuk silang di atas, dan aproksimasi pangkat dua tidak dipakai untuk batas itu.** Biaya bentuk silang itu terukur hanya 4 geseran dan 3 penjumlahan, jadi tidak ada alasan memakai aproksimasi; aproksimasi 59/64 boleh dipakai sebagai cadangan bila sintesis menuntut bentuk yang lebih ramping, sedangkan aproksimasi 30/32, yang setara dengan 1 dikurangi seperenambelas, DILARANG karena galatnya 1,9022 persen dan terukur meruntuhkan penanda pada deret interval acuan irama dari 898 penyalaan menjadi 9 penyalaan.

3. **P4-3. Satuan waktu RR memakai sampel, bukan milidetik, dan galat 3,5 milidetik ditulis apa adanya sebagai konsekuensinya.** Sampel lebih murah karena penanda waktunya diambil dari penghitung sampel yang sudah ada, dan galat 3,5 ms itu adalah harga yang diterima; sebagai pembanding, jalur milidetik memberi galat 0,5 ms tetapi menuntut penghitung waktu tersendiri.

4. **P4-4. Prosedur search back memakai penampan puncak kandidat, dan lebar RR dipakai 14 bit penuh.** Penampan itu wajib karena tanpa penampan tidak ada puncak yang dapat diangkat, dan lebar 14 bit diambil karena jeda terpanjang pada rekaman ini 7088 ms, sehingga menjepit ke 13 bit akan memotong jeda panjang itu.

5. **P4-5. Antrean delapan interval persamaan (25) disemai ulang bila tidak ada satu pun interval RR yang lolos pita batas selama delapan denyut berturut-turut.** Definisi tepatnya: bila tidak ada interval RR yang lolos pita 0,92 sampai 1,16 kali $RR_{AVERAGE2}$ selama 8 denyut berturut-turut, antrean delapan interval diisi ulang memakai median 32 interval RR terakhir, lalu $RR_{AVERAGE2}$ dihitung ulang dari antrean itu, dan penyemaian ulang dibatasi paling banyak sekali per 8 denyut. Dasarnya pengukuran pada rekaman `04015`: tanpa aturan ini $RR_{AVERAGE2}$ terdampar pada 997 milidetik sedangkan median RR rekaman 736 milidetik, kejadian terdampar terpanjang mencapai 411 denyut atau 302,3 detik, dan penanda irama teratur persamaan (29) hanya menyala 902 kali dari 2.515 langkah. Dengan aturan ini penyalaan penanda pulih menjadi 1.238 kali, kejadian terdampar terpanjang menyusut menjadi 19 denyut atau 12,1 detik, dan bentuk terlarang 30/32 yang tadinya meruntuhkan penanda tidak lagi meruntuhkannya. Nilai 8 dipilih sama dengan panjang antrean, dan nilai 32 dipilih sebagai jendela acuan yang lebih panjang daripada antrean tetapi masih di bawah satu menit pada laju 80 denyut per menit. Kejadian yang ditangani butir ini terukur di [[06 - t-wave-discrimination|t-wave-discrimination]] bagian 7.4.

## 10. Hal yang berbeda dari catatan lama

Catatan lama menyebut dua rata-rata interval RR sebagai satu rata-rata bergerak yang sama, dan tidak menyebut batas bawah yang lebih peka daripada dua batas lainnya. Kedua anggapan itu tidak lengkap, dan yang benar sudah diukur di dokumen ini.

| Klaim catatan lama | Hasil pengukuran | Keterangan |
|---|---|---|
| Kedua rata-rata hampir selalu sama | berbeda pada 64,25 persen langkah seluruh rekaman dan 100,00 persen langkah pada kelas AFIB | beda median pada kelas AFIB 327 ms |
| Ketiga batas sama pekanya terhadap aproksimasi | batas bawah jauh lebih peka | 898 penyalaan menjadi 9 pada batas bawah 0,9375, sedangkan batas atas dan missed hampir tidak berubah |
| Tiga batas cukup diaproksimasi dengan penyebut pangkat dua apa pun | batas bawah perlu penyebut 64 | pergeseran relatif 1,9022 persen meruntuhkan penanda pada deret interval acuan, sedangkan 0,2038 persen tidak |
| Rata-rata yang disaring selalu stabil | pernah beku 304,0 detik | nol sampel lolos pada 34,79 persen langkah |

## 11. Antarmuka ke fase berikutnya, diskriminasi gelombang T

Aturan berikut TIDAK dikerjakan di fase ini, dan hanya disebut sebagai antarmuka, karena ia berada di halaman 234 yang sama tetapi memerlukan besaran lain. Bunyinya: "When an RR interval is less than 360 ms (it must be greater than the 200 ms latency), a judgment is made to determine whether the current QRS complex has been correctly identified or whether it is really a T wave. If the maximal slope that occurs during this waveform is less than half that of the QRS waveform that preceded it, it is identified to be a T wave; otherwise, it is called a QRS complex." Terjemahan bebasnya: bila satu interval RR kurang dari 360 ms dan tentu harus lebih panjang daripada latensi 200 ms, diambil satu keputusan untuk menentukan apakah kompleks yang baru ditemukan itu benar-benar kompleks QRS atau sesungguhnya gelombang T, dan bila kemiringan terbesar di dalam bentuk gelombang itu kurang dari separuh kemiringan kompleks QRS yang mendahuluinya, ia dinyatakan gelombang T, sedangkan bila tidak, ia disebut kompleks QRS. Antarmukanya dengan dokumen ini ada di dua tempat: aturan itu memakai besaran kemiringan terbesar, yaitu keluaran tahap turunan lima titik di [[02 - five-point-derivative-equation|five-point-derivative-equation]], bukan besaran waktu seperti tiga batas di sini, dan aturan itu hanya dapat berjalan setelah ada kompleks QRS sebelumnya yang sudah disahkan, jadi ia memerlukan urutan denyut yang sudah ada, dan urutan itulah yang dihasilkan tahap pada dokumen ini. Karena itu seluruh pemeriksaan kemiringan, termasuk pemilihan besaran kemiringan yang dipakai, masuk fase berikutnya.

## 12. Rujukan

1. Pan J, Tompkins WJ. *A Real-Time QRS Detection Algorithm.* IEEE Transactions on Biomedical Engineering, 1985, BME-32(3):230-236. DOI 10.1109/TBME.1985.325532. Persamaan (24) sampai (29), bagian *Adjusting the Average RR Interval and Rate Limits*, bagian *T-Wave Identification*, dan bagian *Evaluation* ada di halaman 234, dan dibaca langsung dari gambar halaman 600 dpi salinan PDF di `~/.hermes/cache/scratch/explore/pan-tompkins-1985.pdf` karena lapisan teksnya rusak. Kalimat tentang pengurangan ambang untuk irama tidak teratur, yaitu persamaan (22) dan (23), ada di halaman yang sama.
2. Salinan penuh naskah: https://www.robots.ox.ac.uk/~gari/teaching/cdt/A3/readings/ECG/Pan+Tompkins.pdf
3. Cermin cadangan: https://people.ece.cornell.edu/land/courses/ece5030/labs/s2014/Pan_Tompkins.pdf
4. Dokumen pendamping: [[02 - five-point-derivative-equation|five-point-derivative-equation]] dan [[03 - squaring-and-moving-window-integrator-equation|squaring-and-moving-window-integrator-equation]]
5. Dokumen konvensi dan breakdown: 34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown, bagian 3.7
6. Notebook pendamping: `nabdha-afib-lite/model/math-equation-afib/05 - rr-interval-averaging-equations.ipynb`
7. Data uji: PhysioNet MIT-BIH Atrial Fibrillation Database, rekaman `04015`, 250 Hz, 450000 sampel pertama. https://physionet.org/content/afdb/
