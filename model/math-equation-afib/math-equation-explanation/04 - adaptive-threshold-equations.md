# Adaptive Threshold Equations

Catatan turunan lengkap untuk tahap ambang adaptif Pan-Tompkins, persamaan (12) sampai (23) halaman 233 dan 234, beserta teladan hitung tangan dan pengukuran pada rekaman nyata. Semua persamaan ditulis dalam LaTeX dan dirender Obsidian. Semua angka di dokumen ini dihitung dengan Python, bukan dikutip dari ingatan. Notebook pendampingnya ada di `nabdha-afib-lite/model/math-equation-afib/04 - adaptive-threshold-equations.ipynb`, dan dokumen pendampingnya adalah [[02 - five-point-derivative-equation|five-point-derivative-equation]] serta [[03 - squaring-and-moving-window-integrator-equation|squaring-and-moving-window-integrator-equation]].

Tujuan dokumen ini: setelah membacanya, Anda bisa menyebut peran masing-masing dari empat ambang, menjelaskan mengapa rantai ini memakai dua domain sinyal, membuktikan bahwa seluruh bobotnya bebas pengali, menghitung konstanta waktu pembaruan dalam jumlah denyut, menghitung jejak ambang dengan tangan, dan menjelaskan mengapa pemotongan separuh ambang persamaan (22) dan (23) harus dikendalikan pada irama fibrilasi atrium.

## 1. Variabel dan notasi

| Simbol | Arti | Keterangan |
|---|---|---|
| $n$ | indeks puncak | satu puncak per pembaruan, $n \ge 1$ |
| $PEAKI$ | puncak yang sedang diklasifikasikan | nilai maksimum lokal pada selubung integrasi |
| $SPKI$ | taksiran berjalan puncak sinyal | diperbarui hanya bila puncaknya puncak sinyal |
| $NPKI$ | taksiran berjalan puncak derau | diperbarui hanya bila puncaknya puncak derau |
| $THRESHOLD_{I1}$ | ambang pertama domain integrasi | dipakai pada analisis pertama sinyal |
| $THRESHOLD_{I2}$ | ambang kedua domain integrasi | dipakai pada pencarian mundur atau search back |
| $PEAKF$ | puncak domain EKG terfilter | kualifikasi sama seperti $PEAKI$ |
| $SPKF$ | taksiran berjalan puncak sinyal domain terfilter | persamaan (17) |
| $NPKF$ | taksiran berjalan puncak derau domain terfilter | persamaan (18) |
| $THRESHOLD_{F1}$ | ambang pertama domain EKG terfilter | persamaan (19) |
| $THRESHOLD_{F2}$ | ambang kedua domain EKG terfilter | persamaan (20) |
| $\alpha$ | bobot pembaruan puncak baru | $\alpha = 0{,}125$ pada persamaan (12) dan (17) |
| $\beta$ | bobot pembaruan lewat ambang kedua | $\beta = 0{,}25$ pada persamaan (16) dan (21) |
| $\gamma$ | bobot selisih pada ambang pertama | $\gamma = 0{,}25$ pada persamaan (14) dan (19) |
| $\tau$ | konstanta waktu pembaruan | dalam jumlah pemutakhiran, yaitu denyut |
| $RR$ | jarak antara dua QRS berurutan | satuan detik |
| $RR\ AVERAGE2$ | rata-rata delapan RR terpilih | dipakai untuk $RR\ MISSED\ LIMIT$ |

Angka-angka penting ditulis tebal: **0,125** adalah bobot puncak baru, **0,875** adalah bobot nilai lama, **0,5** adalah rasio ambang kedua terhadap ambang pertama, dan **0,25** memikul dua peran berbeda yang harus dibedakan, yaitu bobot selisih pada persamaan (14) dan (19) serta bobot puncak baru pada persamaan (16) dan (21). Indeks $I$ adalah singkatan dari integration, yaitu selubung energi keluaran jendela bergerak, dan indeks $F$ adalah singkatan dari filtered, yaitu EKG sesudah bandpass.

## 2. Peran tiap ambang dan mengapa ada dua domain

Tahap ini memakai empat ambang, dua di tiap domain. Perannya berbeda dan tidak boleh tertukar.

Ambang pertama, $THRESHOLD_{I1}$ dan $THRESHOLD_{F1}$, adalah ambang kerja utama. Isi persamaan (14) dapat ditulis ulang menjadi rata-rata berbobot:

$$
THRESHOLD_{I1} = NPKI + 0{,}25 \left( SPKI - NPKI \right) = 0{,}75 \ NPKI + 0{,}25 \ SPKI
$$

Bentuk kedua itu menunjukkan sifat sebenarnya. Ambang pertama adalah rata-rata berbobot taksiran derau dan taksiran sinyal dengan bobot tiga banding satu, sehingga ia selalu berada di antara keduanya, tidak pernah menyentuh keduanya, dan karena itu selalu di atas puncak derau serta selalu di bawah puncak sinyal sesudah kedua taksiran itu berpisah. Angka 0,25 pada persamaan (14) adalah bobot selisih, bukan bobot puncak baru, dan menukarnya dengan peran pada persamaan (16) adalah kekeliruan yang paling mudah terjadi saat menerjemahkan makalah ke kode.

Ambang kedua, $THRESHOLD_{I2}$ dan $THRESHOLD_{F2}$, adalah ambang cadangan dengan rasio tetap:

$$
THRESHOLD_{I2} = 0{,}5 \ THRESHOLD_{I1}, \qquad THRESHOLD_{F2} = 0{,}5 \ THRESHOLD_{F1}
$$

Ambang ini tidak dipakai pada analisis awal, melainkan hanya bila jarak sejak QRS terakhir melampaui $RR\ MISSED\ LIMIT$ dan pencarian mundur menjadi perlu. Rasio tetap 0,5 itu terukur persis di notebook pada 240 puncak buatan, dengan nilai 0,500000.

Persamaan (16) dan (21) menaikkan bobot puncak baru dari 0,125 menjadi 0,25, yaitu meluruhkan bobot nilai lama dari 0,875 menjadi 0,75, tetapi hanya bila QRS ditemukan lewat ambang kedua. Alasannya aritmetika: $THRESHOLD_{I2}$ jauh lebih rendah daripada $THRESHOLD_{I1}$, sehingga puncak yang lolos lewat jalur itu lebih lemah dan taksirannya perlu mengejar lebih cepat. Perbandingan kedua laju itu terukur di notebook, dan pada konstanta waktu keduanya berselisih 2,0909 kali.

Mengapa ada dua domain. Halaman 234 menutup bagian ini dengan syarat ganda: sebuah puncak hanya diakui sebagai QRS bila dikenali di kedua bentuk gelombang, selubung integrasi dan EKG terfilter. Satu domain saja tidak cukup. Selubung integrasi kehilangan morfologi karena jendela 38 sampel meratakannya, jadi ia kuat untuk menyatakan bahwa ada energi tetapi lemah untuk menyatakan bahwa energi itu berbentuk QRS. EKG terfilter masih memuat morfologi, jadi ia kuat untuk menolak gelombang T yang lebar. Dua syarat yang harus dilampaui bersama menurunkan peluang puncak derau diterima, dengan harga satu jalur pembaruan tambahan. Itulah sebabnya persamaan (17) sampai (21) menduplikasi persamaan (12) sampai (16) dengan mengganti lambang $I$ menjadi $F$, dan bukan memakai satu himpunan ambang untuk kedua sinyal.

## 3. Lima bentuk tetap dan bukti bebas pengali

Persamaan (12) sampai (23) dapat direduksi menjadi lima bentuk tetap, yaitu lima bobot yang seluruhnya pangkat dua atau komplemen pangkat dua dari satu:

| Nomor persamaan | Bentuk tetap | Nilai | Padanan tanpa pengali |
|---|---|---|---|
| (12), (13), (17), (18) | bobot puncak baru | $0{,}125$ | geser kanan 3 |
| (12), (13), (17), (18) | bobot nilai lama | $0{,}875$ | satu dikurangi geser kanan 3 |
| (14), (19) | bobot selisih puncak | $0{,}25$ | geser kanan 2 |
| (16), (21) | bobot puncak baru lewat ambang kedua | $0{,}25$ | geser kanan 2 |
| (16), (21) | bobot nilai lama lewat ambang kedua | $0{,}75$ | satu dikurangi geser kanan 2 |
| (15), (20) | rasio ambang kedua | $0{,}5$ | geser kanan 1 |

Lima boolean hasil ukur di notebook, seluruhnya diuji sebagai bilangan rasional eksak memakai `Fraction` sehingga tidak ada toleransi sama sekali:

| Uji | Hasil ukur | Nilai rasional |
|---|---|---|
| $0{,}125$ sama dengan geser kanan 3 | benar | $1/8$ |
| $0{,}875$ sama dengan satu dikurangi geser kanan 3 | benar | $7/8$ |
| $0{,}25$ sama dengan geser kanan 2 | benar | $1/4$ |
| $0{,}75$ sama dengan satu dikurangi geser kanan 2 | benar | $3/4$ |
| $0{,}5$ sama dengan geser kanan 1 | benar | $1/2$ |

Uji pendukungnya, geser kanan aritmetika sama dengan pembulatan ke bawah pada 200.001 bilangan bulat dari minus 100.000 sampai 100.000, dan ketiga geseran itu lolos: $x \gg 3$ sama dengan bulat ke bawah $x/8$, $x \gg 2$ sama dengan bulat ke bawah $x/4$, dan $x \gg 1$ sama dengan bulat ke bawah $x/2$.

Kunci bebas pengali terletak pada penulisan ulang persamaan (12). Pindahkan $SPKI$ sebagai satu kesatuan:

$$
SPKI = 0{,}125 \ PEAKI + 0{,}875 \ SPKI = SPKI + 0{,}125 \left( PEAKI - SPKI \right)
$$

Suku $0{,}125\left(PEAKI - SPKI\right)$ adalah selisih antara puncak baru dan taksiran lama dibagi delapan, dan pada aritmetika bilangan bulat pembagian delapan itu adalah geser kanan tiga bit:

$$
SPKI \mathrel{+}= \left( PEAKI - SPKI \right) \gg 3
$$

Bentuk itu disebut bentuk selisih, dan bentuk itulah yang bebas pengali. Ada temuan penting di sini yang perlu dicatat tim. Bentuk yang secara aljabar setara, yaitu bentuk dua suku yang memakai penggeseran terpisah pada masing-masing suku, tidak selalu sama dengan bentuk selisih pada aritmetika bilangan bulat:

$$
SPKI = \left( PEAKI \gg 3 \right) + SPKI - \left( SPKI \gg 3 \right)
$$

Hasil ukur pada 60.000 pasangan bilangan bulat acak dalam rentang minus 4.000 sampai 4.000: bentuk selisih sama persis dengan pembulatan ke bawah dari jumlah berbobot, dengan selisih terbesar nol, sedangkan bentuk dua suku menyimpang dengan selisih terbesar satu hitungan. Sebabnya, geser kanan membulatkan ke bawah dan pembulatan ke bawah tidak komutatif terhadap pengurangan. Jadi bentuk selisih bukan sekadar bentuk yang lebih hemat perangkat keras, melainkan satu-satunya bentuk yang eksak terhadap acuan pecahan. RTL harus memakai bentuk selisih.

## 4. Pembaruan sebagai integrator bocor dan konstanta waktunya

Persamaan (12) adalah tapis lintas rendah orde satu tanpa pengali. Untuk puncak konstan $P$, dengan $SPKI_n$ sebagai nilai sesudah pembaruan ke-$n$:

$$
SPKI_n = 0{,}125 \ P + 0{,}875 \ SPKI_{n-1}
$$

Kurangkan $P$ dari kedua sisi, dan diperoleh bentuk integrator bocor:

$$
SPKI_n - P = 0{,}875 \left( SPKI_{n-1} - P \right) \quad \Longrightarrow \quad SPKI_n - P = 0{,}875^{n} \left( SPKI_0 - P \right)
$$

Faktor boconjya adalah 0,875, dan konstanta waktunya diperoleh dari $e^{-1/\tau} = 0{,}875$:

$$
\tau = \frac{1}{\ln \left( 1 / 0{,}875 \right)} = 7{,}4889 \ \text{denyut}
$$

Karena satu pemutakhiran sama dengan satu denyut, konstanta waktunya sekitar 7,5 denyut pada persamaan (12), (13), (17), dan (18). Jumlah pembaruan sampai galat menyusut ke lima persen nilai tunaknya:

$$
n_{95} = \frac{\ln 0{,}05}{\ln 0{,}875} = 22{,}4347 \ \text{pemutakhiran}
$$

yang dibulatkan menjadi 23 pemutakhiran, dan angka itu terukur persis di notebook pada puncak konstan 1.000. Persamaan (16) dan (21) memakai bobot 0,25 sehingga faktornya 0,75 dan konstanta waktunya lebih pendek:

$$
\tau_{16} = \frac{1}{\ln \left( 1 / 0{,}75 \right)} = 3{,}4761 \ \text{denyut}
$$

Jalur ambang kedua karenanya menyentuh 95 persen nilai tunaknya pada denyut ke-11, yaitu 2,0909 kali lebih cepat daripada jalur normal.

| Besaran terukur | Bobot 0,125 dan 0,875 | Bobot 0,25 dan 0,75 |
|---|---|---|
| Konstanta waktu $\tau$ | 7,4889 denyut | 3,4761 denyut |
| $n_{95}$ analitik | 22,4347 | 10,4133 |
| $n_{95}$ terukur | 23 denyut | 11 denyut |
| Nilai pada $n_{95}$, puncak 1.000 | 953,635539 | 957,764864 |
| Percepatan pada $n_{95}$ terhadap jalur normal | 1,0000 kali | 2,0909 kali |

Pada bobot normal, konstanta waktu 7,4889 denyut itu setara kira-kira 7,5 detik pada 60 denyut per menit dan kira-kira 4,5 detik pada 100 denyut per menit. Artinya ambang baru mantap sesudah belasan denyut pertama, dan pada rekaman pendek bagian awal itu harus diperlakukan sebagai masa pemanasan.

## 5. Galat pembulatan dan dua mode pembulatan

Pembaruan bulat membuang pecahan pada setiap langkah. Notebook mengukur seberapa besar pembuangan itu pada deret puncak acak panjang 2.500 pemutakhiran, dengan jalur bulat dan jalur pecahan berjalan berdampingan dari nilai awal yang sama.

| Besaran terukur | Nilai |
|---|---|
| Galat per langkah, paling negatif | $-5{,}266012$ hitungan |
| Galat per langkah, paling positif | $-0{,}375000$ hitungan |
| Galat per langkah, nilai mutlak maksimum | 5,266012 hitungan |
| Galat per langkah, rata-rata | $-3{,}487322$ hitungan |
| Galat kumulatif bertanda | $-8\,718{,}304241$ |
| Galat kumulatif nilai mutlak | 8.718,304241 |
| Nilai akhir $SPKI$ bulat | 1.274 |
| Nilai akhir $SPKI$ pecahan | 1.278,609778 |
| Selisih nilai akhir | $-4{,}609778$ hitungan |

Bacaan tabel itu jujur dan penting. Galat per langkahnya selalu negatif dan berkisar tiga setengah hitungan, jadi pembulatan ke bawah memang menekan taksiran ke arah bawah. Namun galat kumulatifnya tidak menumpuk secara linear seperti pada akumulator biasa. Pada 2.500 langkah, penjumlahan linear akan memberi galat ribuan hitungan, sedangkan yang terukur hanya 8.718 dibagi 2.500, yaitu tiga setengah hitungan per langkah. Sebabnya integrator bocor ini melupakan galat lama dengan faktor 0,875 tiap langkah, sehingga galatnya berhenti pada tingkat tetap dan tidak tumbuh. Nilai akhir bulat berbeda 4,609778 hitungan dari nilai akhir pecahan, yaitu sekitar 0,36 persen dari nilai taksirannya.

Pada deret puncak konstan, sifat tetap itu terukur lebih tajam. Untuk puncak konstan 1.000, jalur bulat dengan mode ke bawah berhenti pada 993 hitungan, sedangkan jalur pecahannya berhenti pada 1.000,000000. Jadi ada sisa tetap 7 hitungan, dan sisa itu tidak pernah hilang karena pada langkah berikutnya selisihnya tinggal 7, dibagi delapan menjadi 0,875, dan pembulatan ke bawah mengubahnya menjadi nol.

Perbandingan dua mode pembulatan pada deret 2.500 pemutakhiran yang sama:

| Besaran terukur | Bulat ke bawah | Bulat ke arah nol |
|---|---|---|
| Galat rata-rata $SPKI$ | $-3{,}487322$ hitungan | $-0{,}092721$ hitungan |
| Galat per langkah nilai mutlak maksimum | 5,266012 hitungan | 3,495528 hitungan |
| Nilai akhir $SPKI$ | 1.274 | 1.279 |
| Bias ambang rata-rata | $-8{,}205600$ hitungan | acuan |
| Bias ambang akhir | $-2{,}750000$ hitungan | acuan |
| Bias ambang paling besar | 132,500000 hitungan | acuan |

Dua mode itu berbeda hanya untuk selisih negatif, karena bulat ke bawah dan pemotongan ke arah nol berimpit pada selisih positif. Mode ke arah nol memangkas bias rata-rata dari tiga setengah hitungan menjadi sepersepuluh hitungan, tetapi galat sesaatnya tidak lebih kecil, dan pada selubung berorde miliaran hitungan keduanya sama saja. Karena taksiran ini hanya dipakai sebagai ambang, bukan sebagai luaran, geser kanan aritmetika tetap pilihan yang benar di RTL. Yang perlu dicatat hanyalah bahwa bias beberapa hitungan ke arah bawah itu nyata dan terukur, bukan nol.

## 6. Tabel hitung tangan jejak ambang

Deret puncak buatan di bawah berisi empat belas puncak yang bergantian sinyal dan derau. Seluruhnya bilangan bulat, dan kedua taksiran mulai dari nol. Kolomnya satu kolom per suku, sesuai bentuk dua suku persamaan (12) dan (13). Kolom yang tidak terisi ditandai kosong, dan itulah bukti tabel bahwa satu puncak hanya memutakhirkan salah satu variabel.

| $n$ | $PEAKI$ | jenis | $0{,}125 \ PEAKI$ | $0{,}875 \ SPKI$ lama | $0{,}875 \ NPKI$ lama | $SPKI$ baru | $NPKI$ baru | $THRESHOLD_{I1}$ | $THRESHOLD_{I2}$ |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 4.000 | sinyal | 500,000000 | 0,000000 |  | 500,000000 | 0,000000 | 125,000000 | 62,500000 |
| 2 | 120 | derau | 15,000000 |  | 0,000000 | 500,000000 | 15,000000 | 136,250000 | 68,125000 |
| 3 | 3.200 | sinyal | 400,000000 | 437,500000 |  | 837,500000 | 15,000000 | 220,625000 | 110,312500 |
| 4 | 160 | derau | 20,000000 |  | 13,125000 | 837,500000 | 33,125000 | 234,218750 | 117,109375 |
| 5 | 4.800 | sinyal | 600,000000 | 732,812500 |  | 1.332,812500 | 33,125000 | 358,046875 | 179,023438 |
| 6 | 200 | derau | 25,000000 |  | 28,984375 | 1.332,812500 | 53,984375 | 373,691406 | 186,845703 |
| 7 | 2.400 | sinyal | 300,000000 | 1.166,210938 |  | 1.466,210938 | 53,984375 | 407,041016 | 203,520508 |
| 8 | 240 | derau | 30,000000 |  | 47,236328 | 1.466,210938 | 77,236328 | 424,479980 | 212,239990 |
| 9 | 4.000 | sinyal | 500,000000 | 1.282,934570 |  | 1.782,934570 | 77,236328 | 503,660889 | 251,830444 |
| 10 | 280 | derau | 35,000000 |  | 67,581787 | 1.782,934570 | 102,581787 | 522,669983 | 261,334991 |
| 11 | 3.600 | sinyal | 450,000000 | 1.560,067749 |  | 2.010,067749 | 102,581787 | 579,453278 | 289,726639 |
| 12 | 320 | derau | 40,000000 |  | 89,759064 | 2.010,067749 | 129,759064 | 599,836235 | 299,918118 |
| 13 | 4.400 | sinyal | 550,000000 | 1.758,809280 |  | 2.308,809280 | 129,759064 | 674,521618 | 337,260809 |
| 14 | 360 | derau | 45,000000 |  | 113,539181 | 2.308,809280 | 158,539181 | 696,106706 | 348,053353 |

Baris $n = 5$ dibaca begini. Puncaknya $4\,800$ dan berjenis sinyal karena $4\,800$ melebihi ambang pertama baris sebelumnya, yaitu 234,218750. Suku puncaknya $0{,}125 \times 4\,800 = 600$, suku lamanya $0{,}875 \times 837{,}5 = 732{,}8125$, jumlahnya 1.332,8125, jadi $SPKI$ naik dari 837,5 ke 1.332,8125 sedangkan $NPKI$ tertinggal di 33,125. Sesudah itu ambang pertamanya menjadi 358,046875 dan ambang keduanya 179,023438.

Tiga hal yang dapat dibaca dari tabel itu. Pertama, dari empat belas baris, tujuh baris mengisi kolom $0{,}875 \ SPKI$ lama dan tujuh baris mengisi kolom $0{,}875 \ NPKI$ lama, tidak pernah keduanya, dan itulah wujud nyata kalimat halaman 234 bahwa puncak baru harus diklasifikasikan lebih dulu. Kedua, $SPKI$ dan $NPKI$ berpisah dengan cepat: sesudah lima baris $SPKI$ sudah 1.332,8125 sedangkan $NPKI$ baru 33,125, sehingga rasio keduanya 40,2 kali. Ketiga, ambang pertama selalu berada di antara keduanya, dan pada baris terakhir nilainya 696,106706, yaitu $0{,}75 \times 158{,}539181 + 0{,}25 \times 2\,308{,}809280$, persis bentuk rata-rata berbobot tiga banding satu.

Padanan aritmetika geser pada deret yang sama memperlihatkan jarak yang kecil tetapi nyata:

| $n$ | $PEAKI$ | jenis | $SPKI$ bulat | $NPKI$ bulat | $SPKI$ pecahan | $NPKI$ pecahan |
|---|---|---|---|---|---|---|
| 1 | 4.000 | sinyal | 500 | 0 | 500,0000 | 0,0000 |
| 2 | 120 | derau | 500 | 15 | 500,0000 | 15,0000 |
| 3 | 3.200 | sinyal | 837 | 15 | 837,5000 | 15,0000 |
| 4 | 160 | derau | 837 | 33 | 837,5000 | 33,1250 |
| 5 | 4.800 | sinyal | 1.332 | 33 | 1.332,8125 | 33,1250 |
| 6 | 200 | derau | 1.332 | 53 | 1.332,8125 | 53,9844 |
| 7 | 2.400 | sinyal | 1.465 | 53 | 1.466,2109 | 53,9844 |
| 8 | 240 | derau | 1.465 | 76 | 1.466,2109 | 77,2363 |
| 9 | 4.000 | sinyal | 1.781 | 76 | 1.782,9346 | 77,2363 |
| 10 | 280 | derau | 1.781 | 101 | 1.782,9346 | 102,5818 |
| 11 | 3.600 | sinyal | 2.008 | 101 | 2.010,0677 | 102,5818 |
| 12 | 320 | derau | 2.008 | 128 | 2.010,0677 | 129,7591 |
| 13 | 4.400 | sinyal | 2.307 | 128 | 2.308,8093 | 129,7591 |
| 14 | 360 | derau | 2.307 | 157 | 2.308,8093 | 158,5392 |

Selisihnya berhenti pada satu sampai dua hitungan dan tidak tumbuh, konsisten dengan pengukuran galat di bagian 5. Pada deret ini nilainya tidak melebihi 1,81 hitungan.

## 7. Pemotongan separuh ambang pada irama tidak teratur

Persamaan (22) dan (23) memotong separuh ambang pertama kedua domain bila irama dinilai tidak teratur:

$$
THRESHOLD_{I1} \leftarrow 0{,}5 \ THRESHOLD_{I1}, \qquad THRESHOLD_{F1} \leftarrow 0{,}5 \ THRESHOLD_{F1}
$$

Motifnya benar, yaitu menaikkan kepekaan supaya denyut tidak terlewat. Namun konsekuensinya perlu dihitung, karena ambang kedua mengikuti ambang pertama sebagai separuhnya, sehingga memotong ambang pertama separuh berarti memotong ambang kedua menjadi seperempat nilai asalnya:

$$
THRESHOLD_{I2} = 0{,}5 \ THRESHOLD_{I1} \quad \longrightarrow \quad THRESHOLD_{I2} = 0{,}5 \left( 0{,}5 \ THRESHOLD_{I1} \right) = 0{,}25 \ THRESHOLD_{I1}
$$

Notebook mengukurnya pada deret puncak teratur buatan, 60 denyut pada 250 Hz, dengan puncak QRS 4.000 tiap 250 sampel dan dua puncak derau acak berdistribusi eksponensial di antaranya. Yang dihitung adalah puncak derau yang lolos ambang kedua, yaitu puncak yang berada di antara ambang kedua dan ambang pertama sehingga menjadi calon QRS pada pencarian mundur.

| Besaran terukur | Tanpa pemotongan separuh | Dengan pemotongan separuh |
|---|---|---|
| Puncak terdeteksi | 177 | 177 |
| Puncak lolos ambang pertama | 61 | 65 |
| Puncak derau lolos ambang kedua | 3 | 22 |
| Ambang pertama minimum | 118,687500 | 53,675781 |
| Ambang kedua minimum | 59,343750 | 26,837891 |
| Ambang pertama akhir | 1.121,578817 | 560,789408 |
| Ambang kedua akhir | 560,789408 | 280,394704 |
| Lebar pita tambahan, rata-rata | acuan | 247,214956 |

Bacaan tabelnya begini. Tanpa pemotongan, hanya 3 puncak derau yang menyusup ke pita antara ambang kedua dan ambang pertama. Dengan pemotongan, jumlahnya menjadi 22, yaitu 7,3333 kali lebih banyak, sementara jumlah puncak yang lolos ambang pertama hanya naik dari 61 menjadi 65, yaitu 1,0656 kali. Jadi pemotongan separuh menambah kepekaan terhadap QRS dengan tambahan sekitar enam persen, tetapi menambah pita salah positif pada ambang kedua lebih dari tujuh kali lipat. Ambang pertama minimumnya juga turun menjadi 0,452245 kali semula, dan itu memperlihatkan bahwa pemotongan yang berjalan terus akan menekan ambang ke bawah secara sistematis.

Pada irama fibrilasi atrium, kondisi tidak teratur itu hampir selalu benar, sehingga pemotongan berjalan nyaris sepanjang waktu. Inilah alasan bagian 8 mengukur akibatnya pada rekaman nyata.

## 8. Pengukuran jalur search back pada rekaman AFDB 04015

Rekaman uji terkunci adalah AFDB `04015`, 450.000 sampel, 250 Hz, 30 menit, kanal ECG1 12 bit. Selubung energinya dibentuk rantai bilangan bulat terkunci, lalu dijalankan tata cara ambang persamaan (12) sampai (15) ditambah aturan pencarian mundur: bila jarak sejak QRS terakhir melampaui $RR\ MISSED\ LIMIT = 1{,}66 \ RR\ AVERAGE2$, puncak maksimum di atas ambang kedua dianggap calon QRS dan taksirannya diperbarui lewat persamaan (16). Selubungnya mencapai puncak 2.053.318.817 hitungan dengan median 4.512.293,5 hitungan, dan terdeteksi 4.805 puncak. Kedua taksiran mulai dari nol, sehingga ambang minimum dilaporkan dua kali, sekali untuk seluruh rekaman dan sekali lagi sesudah pemanasan 200 puncak.

| Besaran terukur | Tanpa pemotongan separuh | Pemotongan separuh berjalan terus |
|---|---|---|
| Jumlah QRS terbentuk | 2.603 | 2.627 |
| Aktivasi jalur search back | 4 | 2 |
| Puncak derau lolos ambang kedua | 21 | 216 |
| Ambang pertama minimum, seluruh rekaman | 3.866.872,597656 | 1.933.436,298828 |
| Ambang pertama minimum sesudah pemanasan 200 puncak | 26.005.441,785769 | 12.443.913,436036 |
| Ambang kedua minimum sesudah pemanasan | 13.002.720,892885 | 6.221.956,718018 |
| Ambang pertama median | 38.074.454,036147 | 18.754.506,803865 |
| Ambang pertama maksimum | 125.243.994,189577 | 62.591.949,804218 |
| Ambang pertama akhir | 33.538.254,953241 | 16.769.127,476620 |

Jawaban atas dua pertanyaan yang diminta. Pertama, jalur search back aktif **2 kali** ketika pemotongan separuh berjalan terus, dibanding **4 kali** ketika pemotongan tidak berjalan. Kedua, nilai ambang minimum yang tercapai sesudah pemanasan adalah **12.443.913,436036 hitungan** dengan pemotongan, dibanding 26.005.441,785769 hitungan tanpa pemotongan, yaitu 0,478512 kali semula. Bila seluruh rekaman dihitung termasuk masa pemanasan, angka minimumnya 1.933.436,298828 hitungan dengan pemotongan, tepat separuh dari 3.866.872,597656 hitungan tanpa pemotongan; angka seluruh rekaman itu adalah jejak masa pemanasan, dan tidak boleh dipakai sebagai ukuran perilaku tunak.

Temuan yang perlu dicatat tim dari tabel itu ada tiga. Pertama, pemotongan separuh justru menurunkan jumlah aktivasi search back, dari 4 menjadi 2. Alasannya masuk akal: karena ambangnya lebih rendah, lebih banyak puncak diterima sebagai QRS, jarak antar QRS menjadi lebih rapat, dan peluang melampaui $RR\ MISSED\ LIMIT$ pun menurun. Jadi pemotongan itu memang menaikkan kepekaan, dan tujuannya tercapai. Kedua, harganya terlihat di kolom puncak derau yang lolos ambang kedua, yaitu 21 menjadi 216, atau 10,2857 kali lebih banyak. Ketiga, ambang mediannya turun menjadi 0,492575 kali, dan ambang maksimumnya turun dari 125.243.994,189577 menjadi 62.591.949,804218. Jadi seluruh jalur ambangnya turun sekitar separuh, bukan hanya pada sesaat.

Kesimpulan untuk laporan evaluasi: kepekaan yang naik pada irama fibrilasi atrium bukan bukti deteksi yang baik dengan sendirinya. Pemotongan separuh persamaan (22) dan (23) memang membantu menemukan denyut yang lemah, tetapi ia juga melipatgandakan calon QRS dari jalur ambang kedua. Setiap angka kepekaan pada rekaman AF harus dibaca bersama angka salah positifnya, dan keduanya harus dilaporkan berpasangan.

## 9. Catatan fixed-point memakai konvensi terkunci

Konvensi di bawah ini dikunci di [[afib-lite/afib-rtl/34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown]], bagian 3.7, dan dipakai seluruh fase. Ambang adaptif berada di ujung rantai, sesudah turunan, sehingga seluruh skalanya ditentukan dua keputusan sebelumnya.

1. Masukan rentangnya plus minus 5 mV dengan 12 bit signifikan, dijepit pada plus minus 2047 hitungan, lalu diletakkan di depan kata 16 bit dengan nilai digeser ke kiri 4 bit.
2. Sesudah turunan lima titik, hasilnya digeser kanan 8 bit, sehingga faktor skala ambangnya 256.
3. Sesudah geser 8 itu, pengkuadratan muat di 32 bit dan jendela 38 sampel muat tepat di 32 bit.
4. Pembagian dengan 38 tidak dilakukan di RTL, sehingga ambangnya dikalikan 38.
5. Ambang apa pun yang ditulis dalam satuan milivolt dikalikan 256 lebih dulu, sesuai butir 2.
6. Konvensi gabungan kedua butir terakhir adalah faktor 9.728 hitungan per milivolt pada ambang.

| Besaran | Nilai |
|---|---|
| Faktor skala ambang, geser 8 | 256 |
| Pengali lebar jendela, pembagian tidak dilakukan | 38 |
| Faktor gabungan ambang, hitungan per mV | 9.728 |
| Rasio ambang kedua terhadap ambang pertama | 0,5 |
| Lebar bit $SPKI$ maksimum yang mungkin | 32 bit |
| Lebar bit $NPKI$ maksimum yang mungkin | 30 bit |
| Lebar bit ambang pertama maksimum yang mungkin | 31 bit |

Untuk ambang adaptif, lebar kata tidak ditentukan selubungnya, melainkan taksirannya. Karena $SPKI$ dan $NPKI$ selalu di bawah atau sama dengan puncak tertinggi, dan karena ambang pertama adalah rata-rata berbobot keduanya, seluruh bilangan di tahap ini muat di lebar kata selubungnya. Notebook menguji sifat itu pada 4.000 puncak acak yang seluruhnya di bawah selubung tertinggi, dan jumlah langkah yang melewati selubung tertinggi nol. Jadi akumulator 32 bit yang sudah dikunci menampung seluruh tahap ini dengan margin.

Satu catatan penting tentang faktor 9.728. Angka itu bukan skala fisis, melainkan skala perbandingan. Yang dibandingkan di tahap ini adalah ambang dan selubung pada domain yang sama, jadi yang harus konsisten hanyalah pangkat dua penggeseran dan pengali lebar jendela. Bila tim menulis ambang dalam milivolt, urutannya adalah kalikan 256 lalu kalikan 38, dan pada aritmetika bilangan bulat tidak ada urutan lain yang memberi hasil sama.

## 10. Yang berbeda dari catatan lama

Tiga hal pada tahap ini sering dicatat salah, dan ketiganya sudah diukur di notebook.

| Klaim catatan lama | Hasil pengukuran | Keterangan |
|---|---|---|
| Bobot 0,875 memerlukan pengali | benar tanpa pengali | $0{,}875 = 1 - 2^{-3}$ eksak, dan bentuk selisih menghapus penggeseran pada suku lamanya |
| Bentuk selisih dan bentuk dua suku sama saja | bentuk selisih eksak, bentuk dua suku menyimpang sampai 1 hitungan | pembulatan ke bawah tidak komutatif terhadap pengurangan |
| Pemotongan separuh ambang hanya menaikkan kepekaan | kepekaan naik 6 persen, calon QRS jalur kedua naik 7,3333 kali pada deret buatan dan 10,2857 kali pada AFDB 04015 | akibatnya harus dilaporkan berpasangan |

Satu hal lagi yang berbeda dari dugaan awal, dan ini temuan pengukuran. Pemotongan separuh ambang persamaan (22) dan (23) menurunkan jumlah aktivasi search back, bukan menaikkannya. Pada rekaman AFDB 04015 angkanya 4 menjadi 2. Jadi pemotongan itu bukan sekadar pengaman terhadap denyut yang terlewat, ia juga mengubah cara jalur pencarian mundur terpakai: karena ambang pertama turun, jalur pertama sudah cukup sering menerima puncak, sehingga jalur kedua lebih jarang diperlukan.

## 11. Hubungan ke rancangan AFIB-LITE

Empat hal yang harus dibawa keluar dari dokumen ini ke rancangan.

1. Seluruh bobot persamaan (12) sampai (23) bebas pengali, dan RTL harus memakai bentuk selisih $SPKI \mathrel{+}= \left( PEAKI - SPKI \right) \gg 3$. Bentuk dua suku yang secara aljabar setara tidak boleh dipakai, karena ia menyimpang sampai satu hitungan dari acuan pecahan. Bentuk selisih terbukti eksak dengan selisih terbesar nol pada 60.000 pasangan bilangan bulat uji.

2. Konstanta waktunya diukur dalam denyut. Persamaan (12), (13), (17), dan (18) memakai 7,4889 denyut dan menyentuh 95 persen nilai tunaknya pada denyut ke-23, sedangkan persamaan (16) dan (21) memakai 3,4761 denyut dan menyentuh 95 persen pada denyut ke-11. Kedua angka itu berarti ambang baru mantap sesudah belasan denyut pertama, sehingga bagian awal setiap rekaman adalah masa pemanasan dan harus diperlakukan tersendiri saat menghitung kepekaan.

3. Bias pembulatan boleh dipilih dengan sadar dan tidak perlu dihilangkan. Mode geser kanan aritmetika memberi galat rata-rata 3,487322 hitungan ke arah bawah dan menurunkan ambang pada tingkat yang sama, sedangkan mode ke arah nol memangkasnya menjadi 0,092721 hitungan tetapi memerlukan rangkaian pemotongan tersendiri. Pada selubung berorde miliaran hitungan, selisih beberapa hitungan itu tidak berarti, sehingga geser kanan tetap pilihan yang benar.

4. Pemotongan separuh ambang persamaan (22) dan (23) harus dikendalikan, bukan dibiarkan berjalan. Pada rekaman AFDB 04015 ia menurunkan ambang minimum sesudah pemanasan menjadi 0,478512 kali dan ambang median menjadi 0,492575 kali, sambil menaikkan puncak derau yang lolos ambang kedua dari 21 menjadi 216. Laporan evaluasi harus selalu memasangkan angka kepekaan dengan angka salah positifnya.

Satu catatan penutup untuk pembaca keluaran RTL. Nilai $SPKI$, $NPKI$, dan keempat ambang bukan sinyal EKG dan bukan milivolt. Ketiganya adalah bilangan pada skala perbandingan di dalam rantai, dengan satuan yang ditentukan faktor 9.728. Yang boleh diartikan dari keluaran tahap ini hanyalah tanda keluar dari perbandingan, yaitu QRS atau bukan QRS, dan keputusan itu baru sah bila kedua domain sepakat.

## 12. Keputusan yang dikunci 19 Oktober 2026

Lima butir yang sebelumnya masih berupa pertanyaan terbuka sudah diputuskan pada 19 Oktober 2026, dan setiap keputusan disertai alasan terukurnya. Seluruh angka yang dikutip di bawah ini berasal dari bagian 4, 5, dan 8 dokumen ini, jadi tidak ada angka baru yang ditambahkan. Satu bentuk yang menjadi rujukan keputusan irama adalah batas fase 4

$$
RR_{LOW} = 0{,}92 \ RR_{AVERAGE2}, \qquad RR_{HIGH} = 1{,}16 \ RR_{AVERAGE2}
$$

dan kelima keputusannya adalah sebagai berikut.

1. **P3-1. $SPKI$ dan $NPKI$ diinisialisasi dari maksimum dua detik pertama rekaman, bukan dari nol.** Inisialisasi nol membuat sekitar 23 denyut pertama terlalu sensitif. Pembacaan literalnya membuat kandidat paling awal ditolak, dan itu disengaja supaya ambang awal tidak berada di zona terlalu sensitif, sebab dengan nol puncak pertama selalu dinilai puncak sinyal dan taksirannya baru menyentuh 95 persen nilai tunak pada pemutakhiran ke-23, sehingga seluruh masa itu dibaca sebagai puncak sinyal; dua detik pertama pada laju 60 sampai 100 denyut per menit memuat dua sampai tiga denyut, jadi maksimum dua detik pertama mengisi kedua taksiran dengan tingkat yang nyata sebelum keputusan pertama diambil. Halaman 234 tidak menentukan pilihan ini, sehingga pilihan ditetapkan di sini dan tidak dibuka lagi.

2. **P3-2. Pembulatan jalur ambang memakai geser kanan, yaitu pembulatan ke bawah, dan bias tetapnya 3,49 hitungan diterima.** Geser kanan aritmetika memberi galat rata-rata terukur 3,487322 hitungan ke arah bawah dan pada deret puncak konstan 1.000 sisanya berhenti pada 7 hitungan, sedangkan pembulatan ke arah nol memang memangkas bias itu menjadi 0,092721 hitungan tetapi menuntut rangkaian pemotongan tersendiri, dan pada selubung berorde miliaran hitungan selisih beberapa hitungan itu tidak sebanding dengan rangkaian tambahannya.

3. **P3-3. Kriteria irama tidak teratur untuk memicu persamaan (22) dan (23) diturunkan dari batas RR fase 4, yaitu interval di luar 0,92 sampai 1,16 kali rata-rata dianggap tidak teratur, dan definisinya harus sama persis di model dan di RTL.** Kedua angka itu adalah persamaan (26) dan (27), jadi pemicunya memakai besaran yang sudah ada dan tidak menambah satu tetapan baru; syaratnya harus dinyatakan eksplisit karena pemotongan separuh yang berjalan terus menaikkan puncak derau yang lolos ambang kedua dari 21 menjadi 216 pada rekaman AFDB 04015, dan karena itu pemicunya tidak boleh diserahkan pada perilaku bawaan implementasi.

4. **P3-4. Kepekaan selalu dilaporkan berpasangan dengan salah positif, tidak pernah sendiri.** Pada rekaman AFDB 04015 pemotongan separuh menaikkan puncak yang lolos ambang pertama dari 61 menjadi 65, yaitu 1,0656 kali atau sekitar enam persen, tetapi sekaligus menaikkan puncak derau yang lolos ambang kedua dari 21 menjadi 216, yaitu 10,2857 kali, jadi satu angka kepekaan tanpa angka salah positifnya adalah laporan yang menyesatkan.

5. **P3-5. Sebuah puncak disebut QRS hanya bila lolos kedua domain, gelombang integrasi dan EKG terfilter, dan prosedur search back hanya membuka ambang domain integrasi.** Halaman 234 menuntut syarat ganda karena selubung integrasi kuat untuk menyatakan ada energi tetapi lemah untuk menyatakan morfologinya, sedangkan EKG terfilter masih memuat morfologi, dan pada pencarian mundur yang diperbarui adalah taksiran domain integrasi lewat persamaan (16), yang pada rekaman AFDB 04015 aktif 4 kali tanpa pemotongan separuh dan 2 kali dengan pemotongan separuh.

## 13. Rujukan

1. Pan J, Tompkins WJ. *A Real-Time QRS Detection Algorithm.* IEEE Transactions on Biomedical Engineering, 1985, BME-32(3):230-236. DOI 10.1109/TBME.1985.325532. Persamaan (12) sampai (15) dan kalimat pengantar tentang dua himpunan ambang ada di halaman 233, sedangkan persamaan (16) sampai (23) beserta aturan irama tidak teratur ada di halaman 234. Kedua halaman itu dibaca langsung dari gambar halaman 600 dpi salinan PDF di `~/.hermes/cache/scratch/explore/pan-tompkins-1985.pdf`, karena lapisan teksnya rusak, dan seluruh kutipan di dokumen ini disalin dari gambar halaman, bukan dari hasil ekstraksi teks.
2. Salinan penuh naskah: https://www.robots.ox.ac.uk/~gari/teaching/cdt/A3/readings/ECG/Pan+Tompkins.pdf
3. Cermin cadangan: https://people.ece.cornell.edu/land/courses/ece5030/labs/s2014/Pan_Tompkins.pdf
4. Dokumen pendamping di vault: [[02 - five-point-derivative-equation|five-point-derivative-equation]] dan [[03 - squaring-and-moving-window-integrator-equation|squaring-and-moving-window-integrator-equation]]
5. Dokumen konvensi dan breakdown: [[afib-lite/afib-rtl/31 - Memahami AFIB-LITE (Masalah, Kondisi Hari Ini, Logika Matematis)]] dan [[afib-lite/afib-rtl/34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown]], bagian 3.7
6. Notebook pendamping: `nabdha-afib-lite/model/math-equation-afib/04 - adaptive-threshold-equations.ipynb`
7. Data uji: PhysioNet MIT-BIH Atrial Fibrillation Database, rekaman 04015, 250 Hz, 450.000 sampel. https://physionet.org/content/afdb/
