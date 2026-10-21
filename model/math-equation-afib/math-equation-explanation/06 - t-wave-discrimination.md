# Diskriminasi Gelombang T Pan-Tompkins

Catatan turunan lengkap untuk tahap diskriminasi gelombang T Pan-Tompkins, bagian `T-Wave
Identification` halaman 234, beserta tabel hitung tangan, kasus sebelum dan sesudah pada EKG buatan,
dan pengukuran pada rekaman nyata. Semua persamaan ditulis dalam LaTeX dan dirender Obsidian. Semua
angka di dokumen ini dihitung dengan Python pada mesin ini, bukan dikutip dari ingatan. Notebook
pendampingnya ada di `nabdha-afib-lite/model/math-equation-afib/06 - t-wave-discrimination.ipynb`, dan
dokumen pendampingnya adalah [[04 - adaptive-threshold-equations|adaptive-threshold-equations]] serta
[[05 - rr-interval-averaging-equations|rr-interval-averaging-equations]].

Tujuan dokumen ini: setelah membacanya, Anda bisa menyebut dua gerbang yang dipakai aturan halaman
234 beserta urutannya, menjelaskan dari besaran mana kemiringan itu dibaca dan mengapa, membuktikan
bahwa uji setengah kemiringan tidak memerlukan pembagian, menghitung satu deret puncak dengan tangan,
menjelaskan mengapa aturan ini menolong pada EKG buatan yang gelombang T-nya menonjol, dan
menjelaskan mengapa pada fibrilasi atrium aturan ini lebih banyak menghambat daripada menolong.

## 1. Variabel dan notasi

| Simbol | Arti | Keterangan |
|---|---|---|
| $p$ | posisi puncak yang sedang dinilai | dalam sampel, laju 250 Hz |
| $p_{q}$ | posisi QRS terakhir yang sudah diakui | titik hitung jarak |
| $\Delta$ | jarak waktu puncak ke QRS terakhir | $\Delta = 250 \left( p - p_{q} \right) / 1000$ milidetik |
| $y_{d}$ | keluaran tahap turunan lima titik | persamaan (9), sudah dibagi 8 |
| $s$ | kemiringan puncak yang sedang dinilai | nilai terbesar $\left\| y_{d} \right\|$ di dalam jendela |
| $s_{prev}$ | kemiringan kompleks QRS sebelumnya | diambil dari QRS terakhir yang diakui |
| $W$ | setengah lebar jendela kemiringan | 18 sampel, jadi jendela 37 sampel |
| $T_{refrac}$ | gerbang refraktori | 200 milidetik, yaitu 50 sampel |
| $T_{T}$ | jendela uji gelombang T | 360 milidetik sesudah QRS |
| $THRESHOLD_{I1}$ | ambang pertama domain integrasi | persamaan (14), terkunci sejak fase 3 |
| $SPKI$, $NPKI$ | taksiran puncak sinyal dan puncak derau | persamaan (12) dan (13), terkunci |
| $RR_{AVERAGE2}$ | rata-rata interval RR terpilih | persamaan (25), terkunci sejak fase 4 |
| $PEAKI$ | puncak selubung integrasi | keluaran jendela bergantian 37 dan 38 sampel |

Angka penting ditulis tebal: **360** milidetik adalah jendela tempat aturan diperiksa, **200**
milidetik adalah gerbang refraktori yang mendahuluinya, **0,5** adalah rasio kemiringan yang
memisahkan gelombang T dari QRS, **37** sampel adalah lebar jendela kemiringan yang dipakai, dan
**2** adalah satu-satunya faktor yang diperlukan uji keputusan. Satuan kemiringan di sini bukan
milivolt per detik, melainkan hitungan keluaran tahap turunan lima titik pada konvensi terkunci,
karena yang dipakai aturan ini hanya perbandingan dua kemiringan pada satuan yang sama.

## 2. Aturan dua langkah: gerbang refraktori 200 milidetik dan jendela 360 milidetik

Kalimat halaman 234 pada bagian `T-Wave Identification` dibaca langsung dari gambar halaman 600 dpi
dan bunyinya utuh begini: "When an RR interval is less than 360 ms (it must be greater than the
200 ms latency), a judgment is made to determine whether the current QRS complex has been correctly
identified or whether it is really a T wave. If the maximal slope that occurs during this waveform
is less than half that of the QRS waveform that preceded it, it is identified to be a T wave;
otherwise, it is called a QRS complex."

Dua catatan pembacaan yang harus dilakukan terbuka sebelum aturannya diterjemahkan. Pertama, halaman
234 menyebut batas 200 milidetik di dalam tanda kurung sebagai `the 200 ms latency`, bukan sebagai
periode refraktori; kalimat yang menamai periode refraktori ada di halaman 231: "Once a valid QRS
complex is recognized, there is a 200 ms refractory period before the next one can be detected since
QRS complexes cannot occur more closely than this physiologically." Jadi gerbang 200 milidetik itu
nyata, tetapi namanya di halaman 234 berbeda dari namanya di halaman 231. Kedua, rumusan aturan yang
lebih lengkap ada di halaman 232: "occurs following the end of the refractory period but within
360 ms of the previous complex, we must determine if it is a valid QRS complex or a T wave. In this
case, we judge the waveform with the largest slope to be the QRS complex."

Aturannya karenanya dua gerbang berurutan, dan urutannya tidak dapat ditukar.

1. Gerbang pertama, refraktori 200 milidetik. Bila jarak puncak ke QRS terakhir kurang dari
   200 milidetik, puncak itu ditolak lebih dulu dan uji kemiringan tidak pernah dijalankan. Alasannya
   fisiologis, seperti tertulis di halaman 231: kompleks QRS tidak mungkin muncul lebih rapat
   daripada itu, jadi puncak di dalam selang tersebut pasti bagian dari kompleks yang sama.

2. Gerbang kedua, jendela 360 milidetik. Bila puncaknya berada di antara 200 dan 360 milidetik
   sesudah QRS terakhir, uji kemiringan dijalankan. Di luar 360 milidetik puncak itu diterima
   sebagai QRS tanpa pemeriksaan kemiringan sama sekali.

Dalam bentuk uji:

$$
\Delta = 250 \frac{p - p_{q}}{1000} \ \text{ms}
$$

$$
\text{bila} \ \Delta < 200 \ \text{ms} \ \Longrightarrow \ \text{gelombang T dipastikan tanpa uji kemiringan}
$$

$$
\text{bila} \ 200 \ \text{ms} \le \Delta < 360 \ \text{ms} \ \text{dan} \ s < \frac{1}{2} s_{prev}
\ \Longrightarrow \ \text{gelombang T}
$$

$$
\text{bila} \ \Delta \ge 360 \ \text{ms} \ \Longrightarrow \ \text{QRS, aturan kemiringan tidak diperiksa}
$$

Konsekuensi ketiga baris itu harus diingat saat membaca seluruh angka di dokumen ini: aturan
gelombang T hanya bermakna di dalam pita 200 sampai 360 milidetik, dan di luar pita itu ia buta.

### 2.1 Di mana puncak sesungguhnya berada pada rekaman uji

Rekaman uji terkunci adalah AFDB `04015`, 450.000 sampel pertama, 250 Hz, 1800,0 detik, kanal ECG1
12 bit. Jumlah puncak selubungnya 4.777, seluruhnya berada pada indeks ganjil, yaitu 1,0000 seperti
temuan fase 4. Puncak itu disaring menurut jaraknya sesudah QRS yang sudah diakui.

| Pita jarak sesudah QRS | Jumlah puncak | Keterangan |
|---|---|---|
| 0 sampai 200 milidetik | 5 | ditolak gerbang refraktori, uji kemiringan tidak dijalankan |
| 200 sampai 360 milidetik | 2.029 | pita tempat aturan gelombang T benar-benar bekerja |
| 360 milidetik ke atas | 2.603 | di luar jendela, aturan tidak memeriksa apa pun |
| Jumlah di dalam jendela 360 milidetik | 4.637 | seluruh puncak sesudah QRS sampai 360 milidetik |

Rinciannya per pita 50 milidetik: nol puncak pada 0 sampai 150 milidetik, 5 puncak pada 150 sampai
200 milidetik, 255 puncak pada 200 sampai 250 milidetik, 1.511 puncak pada 250 sampai 300 milidetik,
253 puncak pada 300 sampai 350 milidetik, dan 125 puncak pada 350 sampai 400 milidetik. Jadi
sebarannya memusat di 250 sampai 300 milidetik, dan pita itulah yang paling sering diperiksa aturan.

Dua angka yang perlu dibaca bersama tabel itu. Pertama, 2.029 puncak di dalam pita uji bukan berarti
2.029 puncak diperiksa aturan, karena pemeriksaan hanya terjadi pada puncak yang lolos ambang
pertama $THRESHOLD_{I1}$; yang benar-benar diperiksa aturan pada rekaman ini 112 puncak. Kedua,
gerbang refraktori tidak mengubah jumlah denyut pada rekaman ini: 2.605 denyut ketika gerbang hidup
dan 2.605 denyut ketika gerbang itu dimatikan pada putaran uji. Gerbang itu tetap wajib dipasang
karena ia yang mencegah satu denyut dihitung berkali-kali, tetapi pada rekaman ini tugas itu sudah
dipikul pemetik puncak berjarak minimum.

## 3. Definisi kemiringan yang dipakai dan mengapa dari besaran itu

Halaman 234 tidak menyebut dari sinyal mana kemiringan itu dihitung. Kalimatnya hanya berbunyi "the
maximal slope that occurs during this waveform", sehingga yang dibandingkan adalah kemiringan
terbesar di dalam rentang waktu kompleks yang sedang dinilai, dibandingkan dengan kemiringan
terbesar di dalam rentang waktu kompleks QRS yang mendahuluinya. Yang menentukan pilihan besaran
adalah kalimat lain di makalah yang sama, dan itu temuan pembacaan halaman, bukan dugaan:

1. Halaman 232, bagian `Derivative`: "After filtering, the signal is differentiated to provide the
   QRS-complex slope information." Jadi informasi kemiringan kompleks QRS secara eksplisit
   ditempatkan di tahap turunan lima titik persamaan (9).
2. Halaman 230, paragraf pengantar: "Information about the slope of the QRS is obtained in the
   derivative stage." Kalimat pertama itu menegaskan hal yang sama.
3. Halaman 231, keterangan Gambar 1: "(c) Output of differentiator", sedangkan keluaran integrasi
   disebut sebagai sinyal yang memuat "information about both the slope and the width", artinya
   kemiringan di sana sudah tercampur dengan lebar.

Kesimpulan pembacaannya: besaran kemiringan yang dipakai adalah keluaran tahap turunan lima titik,
karena itulah satu-satunya tahap di rantai makalah ini yang keluarannya memang sebuah kemiringan.
EKG terfilter adalah bentuk gelombang, bukan besaran kemiringan. Perlu dicatat jujur bahwa
halaman 234 sendiri tidak menyatakan pilihan itu, sehingga pemilihan besaran ini adalah keputusan
tim yang dibuktikan dengan pengukuran, bukan kutipan. Rumus yang dipakai:

$$
s(p) = \max_{k \in \left[ p - W, p + W \right]} \left| y_{d}(k) \right|, \qquad s_{prev} = s(p_{q})
$$

### 3.1 Dua besaran yang diuji pada rekaman nyata

Dua pilihan besaran dijalankan berdampingan pada rekaman `04015`, seluruhnya dengan lebar jendela
37 sampel. Kolom `QRS sah berisiko` adalah jumlah QRS yang diterima ketika aturan mati tetapi
rasionya kurang dari setengah, sehingga akan ikut tertolak bila aturan dihidupkan.

| Besaran kemiringan | Pemotongan separuh | Denyut sebelum | Denyut sesudah | Diperiksa | Ditolak | QRS sah berisiko |
|---|---|---|---|---|---|---|
| keluaran turunan lima titik | mati | 2.605 | 2.598 | 112 | 6 | 6 |
| keluaran turunan lima titik | hidup | 2.625 | 2.612 | 125 | 12 | 13 |
| beda pertama EKG terfilter | mati | 2.605 | 2.597 | 112 | 7 | 7 |
| beda pertama EKG terfilter | hidup | 2.625 | 2.610 | 125 | 14 | 15 |

Pada rekaman nyata kedua besaran itu berbeda hanya satu tolakan. Yang memisahkan keduanya adalah
EKG buatan bergelombang T menonjol di bagian 6, dan di sana bedanya besar: dengan amplitudo
gelombang T 0,70 milivolt, bacaan dari keluaran turunan menolak seluruh 160 gelombang T palsu,
sedangkan bacaan dari beda EKG terfilter masih meloloskan 21 gelombang T sebagai denyut. Karena itu
besaran yang dipakai adalah keluaran turunan lima titik.

### 3.2 Lebar jendela kemiringan, pilihan yang harus diambil tim

Halaman 234 juga tidak menyebut lebar jendela pengukuran kemiringan, jadi lebar itu keputusan
implementasi. Notebook menyapu lima lebar pada rekaman nyata, seluruhnya dengan pemotongan separuh
mati.

| Setengah lebar (sampel) | Lebar jendela (milidetik) | Denyut sesudah aturan | Diperiksa | Ditolak | Gelombang T buatan yang masih lolos |
|---|---|---|---|---|---|
| 5 | 40 | 2.587 | 108 | 15 | 108 dari 160 |
| 10 | 80 | 2.594 | 112 | 9 | 66 dari 160 |
| 18 | 144 | 2.598 | 112 | 6 | 0 dari 160 |
| 37 | 296 | 2.600 | 112 | 4 | 0 dari 160 |
| 74 | 592 | 2.602 | 113 | 2 | 159 dari 160 |

Hasilnya tidak monoton, dan itu temuan rancangan yang penting. Jendela 40 dan 80 milidetik terlalu
sempit sehingga kemiringan yang terukur di sekitar puncak selubung sudah menyusut, sedangkan jendela
592 milidetik terlalu lebar sehingga ia menelan kemiringan kompleks QRS berikutnya dan hampir semua
gelombang T kembali lolos. Yang bekerja adalah jendela 144 dan 296 milidetik, dan lebar 37 sampel
dipakai karena sama dengan lebar jendela integrasi terkunci serta sudah tersedia sebagai penampan
melingkar di RTL. Pada rekaman nyata, pemilihan lebar hanya menggeser jumlah tolakan antara 2 dan
15 dari 112 puncak yang diperiksa.

## 4. Uji setengah kemiringan sebagai operasi murah

Uji "less than half" di atas kertas berbunyi

$$
s < \frac{1}{2} s_{prev}
$$

Karena $s$ dan $s_{prev}$ keduanya bilangan bulat, bentuk itu tidak perlu pembagian sama sekali.
Kalikan kedua sisi dengan dua, dan diperoleh bentuk silang:

$$
s < \frac{1}{2} s_{prev} \iff 2 s < s_{prev}
$$

Perkalian dua tidak menambah pengali: ia hanya menambah satu bit di ujung atas pembanding, dan
pertidaksamaan di atas bilangan bulat tidak kehilangan apa pun. Dua bentuk lain yang lebih mirip
geseran juga diukur, yaitu bentuk geser ke bawah $s < \left( s_{prev} \gg 1 \right)$ serta bentuk
geser dibulatkan $s < \left( \left( s_{prev} + 1 \right) \gg 1 \right)$.

### 4.1 Hasil ukur tiga bentuk uji

Uji pertama memakai 4.776 pasangan kemiringan yang benar-benar terukur pada rekaman `04015`, dengan
acuan pecahan tepat memakai `Fraction`. Uji kedua memakai kisi seluruh pasangan bilangan bulat dari
0 sampai 4.095 pada kedua sisi, yaitu 16.777.216 pasangan.

| Bentuk uji | Tidak cocok pada pasangan terukur | Tidak cocok pada kisi | Fraksi kisi | Galat ambang terbesar |
|---|---|---|---|---|
| bentuk silang $2 s < s_{prev}$ | 0 dari 4.776 | 0 dari 16.777.216 | 0,00000000 | 0 hitungan |
| geser ke bawah $s < \left( s_{prev} \gg 1 \right)$ | 0 dari 4.776 | 2.048 dari 16.777.216 | 0,00012207 | 1 hitungan |
| geser dibulatkan $s < \left( \left( s_{prev} + 1 \right) \gg 1 \right)$ | 0 dari 4.776 | 0 dari 16.777.216 | 0,00000000 | 0 hitungan |

Bacaan tabelnya begini. Bentuk silang eksak pada seluruh kisi, dan begitupula bentuk geser
dibulatkan, karena pembulatan ke atas menutup pasangan batasnya. Yang menyimpang hanya bentuk geser
ke bawah, tepat pada 2.048 pasangan, yaitu seluruh pasangan dengan $s_{prev}$ ganjil dan
$2 s = s_{prev} - 1$. Pada pasangan itu bentuk geser ke bawah membuang puncak batas sehingga menolak
lebih banyak daripada acuan pecahan, dan arah biasnya selalu ke penolakan. Pada rekaman ini
penyimpangan itu tidak pernah muncul karena tidak ada pasangan terukur yang jatuh di batas, jadi
pilihan di antara ketiganya bebas pada rekaman uji, dan yang dipilih adalah bentuk silang karena
paling murah: tanpa penjumlah tambahan dan tanpa pembulatan.

## 5. Tabel hitung tangan satu deret puncak buatan yang memuat satu gelombang T palsu

Deret di bawah berisi delapan puncak buatan dengan posisi dalam milidetik dan kemiringan dalam
hitungan. Seluruhnya bilangan bulat, jadi tabel ini dapat diperiksa dengan tangan tanpa toleransi.
Kolom `gerbang` menyatakan gerbang mana yang memutuskan lebih dulu, dan kolom `uji 2 kali
kemiringan` memperlihatkan perbandingan yang diuji.

| $n$ | posisi (milidetik) | jarak ke QRS lalu (milidetik) | kemiringan | kemiringan QRS lalu | gerbang | putusan | uji 2 kali kemiringan |
|---|---|---|---|---|---|---|---|
| 1 | 0 | kosong | 1.000.000 | kosong | tanpa uji | QRS, puncak pertama | kosong |
| 2 | 280 | 280 | 420.000 | 1.000.000 | uji kemiringan | gelombang T, ditolak | 840.000 terhadap 1.000.000 |
| 3 | 300 | 300 | 980.000 | 1.000.000 | uji kemiringan | QRS diterima | 1.960.000 terhadap 1.000.000 |
| 4 | 420 | 120 | 120.000 | kosong | refraktori | ditolak | kosong |
| 5 | 700 | 400 | 1.100.000 | kosong | di luar jendela | QRS diterima | kosong |
| 6 | 940 | 240 | 1.050.000 | 1.100.000 | uji kemiringan | QRS diterima | 2.100.000 terhadap 1.100.000 |
| 7 | 1.120 | 180 | 90.000 | kosong | refraktori | ditolak | kosong |
| 8 | 1.540 | 600 | 80.000 | kosong | di luar jendela | QRS diterima | kosong |

Baris $n = 2$ dibaca begini. Puncaknya berada 280 milidetik sesudah QRS pertama, jadi ia di dalam
jendela uji 200 sampai 360 milidetik dan di luar gerbang refraktori. Dua kali kemiringannya
840.000, sedangkan kemiringan QRS sebelumnya 1.000.000, jadi 840.000 kurang dari 1.000.000 dan
puncak itu dinyatakan gelombang T. Baris $n = 3$ memperlihatkan sisi sebaliknya: puncaknya muncul
hanya 20 milidetik sesudah baris $n = 2$, dan karena baris $n = 2$ sudah ditolak, titik hitung QRS
terakhirnya tetap QRS pertama, sehingga jaraknya 300 milidetik, ia diuji kemiringan, dan karena
1.960.000 melebihi 1.000.000 ia diterima sebagai QRS.

Empat hal yang dapat dibaca dari tabel itu, dan ketiganya adalah mekanika aturan yang harus dipahami
tim.

Pertama, putusan tabel itu diperiksa dengan larik bilangan bulat dan tidak memakai toleransi apa pun.
Dengan aturan hidup, puncak yang diterima 5 dari 8, yang ditolak gerbang 2, dan gelombang T yang
dikenali 1. Dengan aturan mati, puncak yang diterima 5 dari 8 dan yang ditolak gerbang 3, dan satu
gelombang T palsu lolos.

Kedua, jumlah puncak yang diterima ternyata sama pada kedua keadaan, yaitu 5, dan itu contoh paling
jelas bahwa gelombang T palsu bukan sekadar menambah satu denyut palsu. Ketika gelombang T di baris
$n = 2$ diterima, titik hitung QRS terakhir berpindah ke 280 milidetik, dan puncak $n = 3$ yang
jaraknya 20 milidetik sesudahnya langsung jatuh ke dalam gerbang refraktori. Jadi satu gelombang T
palsu dapat menelan satu QRS sungguhan, dan kerugiannya bukan satu denyut palsu saja.

Ketiga, baris $n = 5$ dan $n = 8$ memperlihatkan lubang aturan. Keduanya jaraknya lebih dari
360 milidetik dari QRS sebelumnya, jadi keduanya diterima tanpa pemeriksaan kemiringan, meskipun
kemiringan baris $n = 8$ hanya 80.000, yaitu delapan persen dari kemiringan QRS sebelumnya. Aturan
halaman 234 memang tidak dimaksudkan untuk kasus itu, dan penjagaan untuk puncak lemah berjarak jauh
sudah ada di jalur ambang persamaan (12) sampai (15), bukan di sini.

Keempat, baris $n = 4$ dan $n = 7$ memperlihatkan bahwa gerbang refraktori bekerja lebih dulu dan
tanpa uji kemiringan. Karena itu setiap angka tolakan pada dokumen ini harus dipisahkan antara
tolakan gerbang refraktori dan tolakan uji kemiringan, dan pada seluruh pengukuran rekaman di bawah
keduanya memang dilaporkan terpisah.

## 6. Kasus sebelum dan sesudah pada EKG buatan yang gelombang T-nya menonjol

EKG buatan dipakai sebagai kasus sebelum dan sesudah. Denyutnya tetap: satu kompleks QRS segitiga
sempit 1,5 milivolt dengan setengah lebar 16 milidetik, satu gelombang P kecil, dan satu gelombang T
lebar berbentuk kosinus dengan setengah lebar 60 milidetik yang puncaknya 280 milidetik sesudah QRS.
Jarak itu dipilih supaya gelombang T jatuh di dalam jendela 360 milidetik dan di luar gerbang
refraktori 200 milidetik, jadi gelombang T itu memang diperiksa aturan. Denyut berulang setiap
700 milidetik selama 120 detik, jadi ada 170 denyut, dan deret itu ditambah derau putih kecil dengan
benih tetap supaya dapat diulang.

Dua tunda pengukuran diukur lebih dulu, karena jendela integrasi 150 milidetik menunda puncak
selubung terhadap peristiwa asalnya: tunda puncak selubung QRS 37 sampel dan tunda puncak selubung
gelombang T 56 sampel. Penjenisan denyut di bawah memakai kedua tunda itu, bukan posisi peristiwa
mentahnya, supaya penjenisannya tidak salah akibat tunda tersebut.

### 6.1 Sapuan amplitudo gelombang T

| Amplitudo T (milivolt) | Kemiringan T terhadap QRS | T salah diterima sebelum | T ditolak aturan | T masih diterima sesudah | Denyut sebelum | Denyut sesudah |
|---|---|---|---|---|---|---|
| 0,20 | 0,0137 | 0 | 0 | 0 | 150 | 150 |
| 0,30 | 0,0147 | 0 | 2 | 0 | 152 | 150 |
| 0,40 | 0,0153 | 0 | 2 | 0 | 157 | 152 |
| 0,50 | 0,0164 | 160 | 4 | 0 | 320 | 152 |
| 0,70 | 0,0200 | 160 | 8 | 0 | 320 | 155 |
| 0,90 | 0,0235 | 160 | 0 | 160 | 320 | 320 |
| 1,10 | 0,0275 | 160 | 0 | 160 | 320 | 320 |
| 1,30 | 0,0315 | 160 | 0 | 160 | 320 | 320 |

Tabel itu memberi tiga bacaan yang jujur.

Pertama, pada amplitudo 0,20 sampai 0,40 milivolt gelombang T tidak pernah salah diterima bahkan
ketika aturan mati, karena puncak selubungnya ada di bawah ambang pertama. Jadi aturan ini tidak
mengerjakan apa pun pada gelombang T yang lemah, dan itu benar.

Kedua, pada amplitudo 0,50 sampai 0,70 milivolt, aturan ini bekerja penuh. Pada 0,70 milivolt,
sebelum aturan diaktifkan terdeteksi 320 denyut dalam 120 detik, yaitu 160 kompleks QRS buatan
ditambah 160 gelombang T palsu, artinya setiap gelombang T pada rekaman itu salah diterima sebagai
denyut. Sesudah aturan diaktifkan, jumlahnya jatuh ke 155 denyut, seluruhnya kompleks QRS, dan
gelombang T yang masih lolos nol.

Ketiga, pada amplitudo 0,90 milivolt ke atas aturan ini kehilangan daya sepenuhnya, dan itu batas
yang harus dilaporkan terbuka. Ketika gelombang T hampir setinggi QRS, puncak selubungnya berpindah
dan jendela kemiringan di sekitar puncak itu ikut memuat kemiringan kompleks QRS, sehingga rasio
yang terukur naik di atas setengah dan puncaknya dinamai QRS. Dengan kata lain, aturan setengah
kemiringan hanya menolong selama gelombang T memang lebih landai daripada QRS pada jendela yang
diukur, dan itu tidak dapat dijamin pada setiap pasien.

### 6.2 Mekanisme dua lapis pada kasus 0,70 milivolt

Pada kasus 0,70 milivolt, aturan menolak 8 puncak secara eksplisit, sedangkan jumlah gelombang T
palsu yang hilang dari deret denyut 160. Selisih itu bukan salah hitung, melainkan akibat dua
mekanisme yang bekerja berurutan. Puncak yang dinyatakan gelombang T masuk ke jalur derau, jadi ia
memperbarui $NPKI$ lewat persamaan (13) dan $NPKF$ lewat persamaan (18) dengan bobot 0,125. Karena
nilai gelombang T itu besar, taksiran puncak derau naik, ambang pertama ikut naik, dan gelombang T
berikutnya sudah jatuh di bawah ambang pertama sehingga tidak pernah sampai ke uji kemiringan.
Jadi penolakan eksplisit hanya terjadi pada beberapa gelombang T pertama, dan sisanya ditahan oleh
ambang yang sudah naik. Dua lapis itu harus ditulis apa adanya, karena lapis kedua tidak dikendalikan
ambang gerbang melainkan oleh dinamika taksiran derau.

Pada kasus yang sama, jumlah kompleks QRS yang dikenali turun dari 160 ke 155, yaitu lima denyut
hilang, dan itu harga yang dibayar. Sebabnya sama: karena gelombang T yang ditolak menaikkan
$NPKI$ sampai mendekati puncak gelombang T, ambang pertama naik mendekati puncak QRS, sehingga QRS
yang puncaknya tidak jauh di atas gelombang T pun ikut tertahan. Jadi pada sinyal dengan gelombang T
yang menonjol, aturan ini menukar lima denyut sungguhan dengan 160 denyut palsu, dan pertukaran itu
menguntungkan pada EKG buatan ini.

## 7. Pengukuran pada rekaman AFDB 04015

Rantai yang dijalankan adalah rantai bilangan bulat terkunci yang sama dengan fase 3 dan fase 4,
sehingga deret denyut sebelum aturan diaktifkan harus sama dengan angka acuan yang sudah terukur,
yaitu 2.605 denyut dengan pemotongan separuh ambang dimatikan dan 2.625 denyut dengan pemotongan
hidup. Keduanya terpenuhi persis. Selubung integrasinya mencapai 3.105.281.786 hitungan dan menempati
32 bit, turunan maksimumnya 4.792.318 hitungan atau 23 bit, dan setelah geser kanan delapan bit
menjadi 18.719 hitungan atau 15 bit.

### 7.1 Denyut dan kolam kandidat jalur ambang kedua

| Pemotongan separuh | Denyut sebelum | Denyut sesudah | Selisih | Kolam kandidat sebelum | Kolam kandidat sesudah | Cari mundur sebelum | Cari mundur sesudah |
|---|---|---|---|---|---|---|---|
| dimatikan | 2.605 | 2.598 | 7 | 22 | 27 | 7 | 6 |
| dinyalakan terus | 2.625 | 2.612 | 13 | 272 | 279 | 1 | 4 |

Bacaan tabelnya begini. Pada keadaan pemotongan separuh mati, aturan ini menolak 6 puncak dari 112
puncak yang diperiksa, dan jumlah denyut turun dari 2.605 ke 2.598, yaitu berkurang 7. Pada keadaan
pemotongan separuh hidup, 12 puncak ditolak dari 125 yang diperiksa dan denyut turun dari 2.625 ke
2.612, yaitu berkurang 13. Jadi aturan ini menurunkan kepekaan angka mentah pada kedua keadaan, dan
penurunannya sebanding dengan jumlah tolakan karena satu puncak yang ditolak juga menggeser
keputusan berikutnya.

Kolam kandidat jalur ambang kedua justru naik, dari 22 ke 27 dan dari 272 ke 279. Sebabnya aritmetika:
puncak yang ditolak aturan tidak lagi dibuat denyut, sehingga ia masuk ke jalur derau dan tetap
dihitung sebagai puncak yang nilainya di antara ambang kedua dan ambang pertama. Jadi sasaran
fase ini, yaitu kolam 272 pada keadaan pemotongan hidup, tidak berkurang oleh aturan ini, dan itu
temuan yang harus dilaporkan apa adanya. Yang berkurang hanyalah jumlah denyut yang keluar, bukan
jumlah puncak yang berkeliaran di pita antara kedua ambang.

### 7.2 Sebaran rasio kemiringan dan risiko QRS sah

Sebaran rasio kemiringan puncak terhadap kemiringan QRS sebelumnya, pada puncak yang diperiksa
aturan, di dalam jendela 360 milidetik.

| Keadaan | Jumlah diperiksa | Minimum | Persentil 10 | Median | Persentil 90 | Maksimum |
|---|---|---|---|---|---|---|
| pemotongan mati | 112 | 0,1374 | 0,7881 | 1,1139 | 2,2476 | 5,2193 |
| pemotongan hidup | 125 | 0,1374 | 0,5535 | 1,0858 | 2,2620 | 5,2193 |

Sebarannya lebar dan mediannya di atas satu, artinya sebagian besar puncak di dalam jendela 360
milidetik justru lebih tajam daripada QRS sebelumnya. Yang perlu dibaca dari sebaran itu adalah
ekor bawahnya, dan di sana ada risiko yang harus dilaporkan terbuka: ketika aturan mati, ada 6 dari
113 QRS yang diterima di dalam pita 200 sampai 360 milidetik yang rasionya kurang dari setengah,
yaitu 0,0531 atau 5,31 persen. Puncak-puncak itu ikut tertolak ketika aturan dihidupkan, dan
pertanyaan yang tidak dapat dijawab pengukuran ini adalah apakah mereka gelombang T atau QRS
sungguhan, karena rekaman `04015` hanya membawa anotasi irama dan tidak membawa anotasi denyut.

Pada keadaan pemotongan separuh hidup, risikonya lebih besar: 13 dari 131 QRS di dalam pita,
yaitu 0,0992 atau 9,92 persen. Alasannya masuk akal, karena pemotongan separuh menerima puncak yang
lebih lemah sehingga lebih banyak puncak batas yang masuk ke pita uji. Jadi risiko penolakan QRS
sungguhan naik dua kali lipat ketika pemotongan separuh hidup, dan kedua angka itu harus dibaca
berpasangan.

### 7.3 Puncak yang ditolak, satu per satu, dinilai terhadap deret acuan

Enam puncak yang ditolak pada keadaan pemotongan separuh mati diperiksa satu per satu.

| Tolakan | Posisi (milidetik) | Jarak sesudah QRS (milidetik) | Kemiringan | Kemiringan QRS lalu | Rasio | Jarak ke denyut acuan terdekat |
|---|---|---|---|---|---|---|
| 1 | 652,0 | 288 | 225.594 | 1.533.480 | 0,1471 | 224 milidetik |
| 2 | 584.564,0 | 344 | 635.330 | 1.399.022 | 0,4541 | 108 milidetik |
| 3 | 688.852,0 | 336 | 933.874 | 3.642.542 | 0,2564 | 300 milidetik |
| 4 | 776.716,0 | 232 | 882.422 | 1.866.272 | 0,4728 | 280 milidetik |
| 5 | 779.980,0 | 264 | 195.326 | 1.421.492 | 0,1374 | 352 milidetik |
| 6 | 1.461.932,0 | 304 | 522.584 | 1.572.878 | 0,3322 | 112 milidetik |

Tiga angka pendukung. Pertama, seluruh enam tolakan berada di dalam pita 200 sampai 360 milidetik,
dengan jarak minimum 232, median 296, dan maksimum 344 milidetik, jadi aturan memang bekerja di
tempat yang benar. Kedua, rasio keenamnya antara 0,1374 dan 0,4728, seluruhnya di bawah setengah,
dengan median 0,2943. Ketiga, tidak satu pun dari keenam puncak itu berjarak 100 milidetik atau
kurang dari denyut pada deret acuan NeuroKit pantompkins1985, dengan jarak terkecil 108 milidetik.
Keadaan pemotongan separuh hidup memberi hasil yang sama untuk tolakan tambahannya: seluruh tolakan
yang tersisa berjarak 260 sampai 412 milidetik dari denyut acuan terdekat, jadi tidak satu pun
menempati posisi denyut acuan.

Bacaan itu harus disertai kejujuran tentang mutu acuannya. Deret acuan NeuroKit itu sendiri hanya
cocok dengan 1.722 dari 2.605 denyut detektor kita pada toleransi 100 milidetik, yaitu 0,6610,
dengan jarak median 80 milidetik. Jadi acuan itu tidak cukup rapat untuk mengadili setiap tolakan,
dan angkanya hanya boleh dipakai sebagai petunjuk bahwa keenam puncak yang ditolak bukan denyut yang
jelas. Kesimpulan yang berdiri tegak hanyalah ini: tidak satu pun dari 18 tolakan pada kedua
keadaan pemotongan separuh menempati posisi denyut acuan, sehingga tidak ada bukti bahwa aturan ini
membuang denyut sungguhan, tetapi juga tidak ada bukti sebaliknya karena rekaman tidak membawa
anotasi denyut.

### 7.4 Temuan yang tidak diduga: penanda irama teratur terkunci mati

Pengukuran ini menemukan satu efek samping yang lebih besar daripada efek yang diinginkan, dan itu
harus dibaca sebelum aturan ini dinyalakan di RTL. Penanda irama teratur persamaan (29) menyala
1.129 kali dari 2.594 langkah ketika aturan mati, dan nol kali dari 2.588 langkah ketika aturan
hidup. Jadi dengan tujuh denyut selisih, penandanya mati untuk seluruh rekaman.

Mekanismenya terukur pada jejak tahap RR. Ketika aturan mati, dua interval pertama deret denyut
adalah 288 dan 296 milidetik, yaitu dua puncak berdekatan pada awal rekaman. Interval pendek itu
mengisi antrean interval lolos persamaan (25) dan memaksa rata-rata kedua bergerak, sehingga batas
92 sampai 116 persen pernah memuat irama yang sesungguhnya dan penandanya sempat menyala. Ketika
aturan hidup, dua puncak pada awal rekaman itu justru ditolak, sehingga antreannya tidak terisi
nilai pendek itu. Rata-rata kedua lalu terdampar di 592 milidetik pada jejak pelacakan, atau
678 milidetik pada rantai penuh, sedangkan RR median deretnya 728 milidetik. Karena batas bawah
92 persen dari 592 milidetik berarti 545 milidetik dan batas atasnya 687 milidetik, irama 728
milidetik itu jatuh di luar batas, dan satu-satunya jalan keluar dari keadaan itu adalah penyalaan
penanda itu sendiri lewat persamaan (29). Penandanya karenanya terkunci pada nol sampai akhir
rekaman.

Akibat lanjutannya masuk ke tahap ambang, karena pemotongan separuh persamaan (22) dan (23) dipicu
oleh penanda itu. Tabel tiga mode memperlihatkannya.

| Mode pemotongan separuh | Aturan gelombang T | Denyut | Kolam kandidat jalur kedua | Penanda menyala |
|---|---|---|---|---|
| tidak dipotong | mati | 2.605 | 22 | 1.129 |
| tidak dipotong | hidup | 2.598 | 27 | 0 |
| dipicu penanda | mati | 2.623 | 155 | 1.139 |
| dipicu penanda | hidup | 2.612 | 279 | 0 |
| dipotong terus | mati | 2.625 | 272 | 1.132 |
| dipotong terus | hidup | 2.612 | 279 | 0 |

Baris keempat dibaca begini. Pada mode yang dikunci, yaitu pemotongan separuh dipicu penanda irama,
aturan gelombang T membuat penandanya mati, dan matinya penanda berarti ambang pertama terpotong
terus sepanjang rekaman. Akibatnya mode itu bertingkah laku sama seperti pemotongan terus: kolam
kandidat jalur kedua naik dari 155 ke 279, yaitu 1,8 kali. Jadi sasaran fase ini, yaitu menurunkan
kolam kandidat jalur kedua, gagal total pada rekaman ini, dan gagalnya bukan karena uji kemiringannya
salah melainkan karena efek samping pada penanda irama mengubah jalur ambang.

### 7.5 Apakah aturan ini menolong atau menghambat pada fibrilasi atrium

Jawabannya adalah lebih banyak menghambat, dan ini kesimpulan dengan angkanya.

Yang menolong, terukur: pada EKG buatan dengan gelombang T menonjol, 160 gelombang T palsu per
120 detik hilang seluruhnya, dengan harga 5 kompleks QRS dari 160. Pada rekaman nyata, kepekaan dan
spesifisitas gerbang AND irama justru naik sedikit, dan tidak ada tolakan yang menempati posisi
denyut acuan.

Yang menghambat, juga terukur: pada rekaman nyata aturan ini menolak 6 puncak dari 112 yang diperiksa
dan menurunkan jumlah denyut dari 2.605 ke 2.598, sedangkan 6 dari 113 QRS di dalam pita berisiko
ikut tertolak tanpa dapat dibuktikan apakah mereka gelombang T atau bukan. Kolam kandidat jalur
ambang kedua yang menjadi sasaran fase ini tidak turun sama sekali, justru naik dari 22 ke 27 dan
dari 272 ke 279. Dan yang paling berat: penanda irama teratur persamaan (29) berhenti menyala
sepanjang rekaman, sehingga pada mode pemotongan separuh yang dipicu penanda, ambang pertama
terpotong terus dan kolam kandidat jalur kedua naik dari 155 menjadi 279.

Alasan fisiologisnya sederhana dan perlu ditulis: pada fibrilasi atrium tidak ada gelombang T yang
teratur dan besar, yang ada adalah fibrilasi yang tidak teratur dengan denyut cepat dan lemah. Jadi
kasus yang menjadi sasaran aturan ini, yaitu gelombang T besar dan tinggi yang menyerupai QRS, justru
bukan kasus yang dominan pada AFIB. Yang dominan adalah puncak susulan di dalam satu siklus denyut,
dan untuk itu gerbang refraktori 200 milidetik sudah cukup. Jadi rekomendasi untuk tim: aturan ini
disimpan di RTL sebagai saklar yang dapat dimatikan, dan pada jalur AFIB ia dijalankan hanya bila
penanda irama teratur sudah diperbaiki, atau tidak dijalankan sama sekali.

## 8. Gerbang AND pada jendela kelas irama

Aturan gelombang T mengubah deret denyut, dan deret denyut adalah masukan fitur irama, jadi gerbang
AND yang sudah ada diperiksa ulang. Gerbangnya berbunyi RMSSD dibagi rata-rata RR lebih besar
daripada 0,21 DAN entropi ternormalisasi lebih besar daripada 0,70, dihitung pada jendela 32 denyut
berlangkah 4 denyut, dengan label kelas dari anotasi irama resmi dan hanya jendela yang seluruh
32 denyutnya satu kelas yang dipakai.

| Deret denyut | Denyut | Jendela | AFIB | N | Kepekaan | Spesifisitas | Akurasi | Median entropi AFIB | Median entropi N |
|---|---|---|---|---|---|---|---|---|---|
| acuan NeuroKit | 2.601 | 590 | 95 | 495 | 92,63 persen | 79,60 persen | 81,69 persen | 0,8007 | 0,6506 |
| detektor sebelum aturan | 2.605 | 592 | 96 | 496 | 76,04 persen | 89,11 persen | 86,99 persen | 0,7695 | 0,3119 |
| detektor sesudah aturan | 2.598 | 591 | 97 | 494 | 77,32 persen | 90,28 persen | 88,16 persen | 0,7812 | 0,3119 |
| detektor sesudah aturan, separuh hidup | 2.612 | 594 | 98 | 496 | 77,55 persen | 90,52 persen | 88,38 persen | 0,7695 | 0,3213 |

Jawaban atas pertanyaan apakah aturan ini mengubah kepekaan dan spesifisitas pada 590 jendela itu:
tidak, karena 590 jendela itu adalah deret acuan NeuroKit, dan aturan gelombang T bekerja pada deret
denyut detektor kita, bukan pada deret acuan. Yang dapat berubah adalah deret detektor sendiri, dan
di sana perubahannya terukur: kepekaan naik dari 76,04 menjadi 77,32 persen, yaitu 1,28 poin;
spesifisitas naik dari 89,11 menjadi 90,28 persen, yaitu 1,17 poin; dan akurasi naik dari 86,99
menjadi 88,16 persen, yaitu 1,16 poin. Jumlah jendelanya bergeser dari 592 ke 591 karena satu denyut
hilang menggeser pembagian jendela.

Kenaikan itu nyata tetapi kecil, dan harus dibaca bersama peringatan yang sudah dikunci: ambang
gerbang 0,70 itu belum boleh dipindahkan ke deret detektor sendiri, karena median entropi kelas N
pada deret acuan 0,6506 sedangkan pada deret detektor sendiri 0,3119. Median itu tidak bergerak oleh
aturan gelombang T, yaitu tetap 0,3119 sebelum dan sesudah, jadi aturan ini tidak memperbaiki
masalah ambang gerbang, dan pasangan ambang serta deret fitur tetap menjadi risiko terbuka seperti
tertulis di [[07 - combined-risk-measurements|combined-risk-measurements]] bagian 5.

AUC empat fitur juga dicatat, dan arahnya sejalan dengan gerbangnya. Pada deret detektor, entropi
ternormalisasi naik dari 0,9460 menjadi 0,9521, RMSSD dibagi rata-rata naik dari 0,7760 menjadi
0,7841, pNN50 naik dari 0,8561 menjadi 0,8657, dan RMSSD naik dari 0,6547 menjadi 0,6659. Jadi
aturan gelombang T memperbaiki seluruh fitur irama secara serentak, tetapi perbaikannya di bawah
satu poin, jauh lebih kecil daripada selisih 15,54 poin antara deret acuan dan deret detektor yang
sudah terukur di [[07 - combined-risk-measurements|combined-risk-measurements]].

## 9. Catatan fixed-point memakai konvensi terkunci

Konvensi di bawah ini dikunci di [[afib-lite/afib-rtl/34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown]], bagian 3.7, dan dipakai seluruh fase. Tahap ini berada di ujung rantai,
sesudah turunan, sehingga seluruh skalanya ditentukan keputusan sebelumnya, dan tidak ada satu angka
pun di bawah ini yang diturunkan ulang dari fase lain.

1. Masukan rentangnya plus minus 5 mV dengan 12 bit signifikan, dijepit pada plus minus 2047
   hitungan, lalu digeser ke kiri 4 bit.
2. Low-pass 21 bit, high-pass 25 bit, turunan 23 bit lalu digeser kanan 8 bit sehingga faktor skala
   ambangnya 256. Setelah geser kanan 8 bit, kemiringan yang dibandingkan tinggal 15 bit.
3. Kuadrat 29 bit dan jendela 32 bit, jendela bergantian 37 dan 38 sampel, penampan melingkar.
4. Pembagian dengan 38 tidak dilakukan di RTL, sehingga ambangnya dikalikan 38.
5. RR dalam satuan sampel, lebar 14 bit penuh.

| Besaran fixed-point | Nilai | Keterangan |
|---|---|---|
| Turunan maksimum | 4.792.318 hitungan | 23 bit |
| Turunan setelah geser kanan 8 | 18.719 hitungan | 15 bit |
| Dua kali kemiringan maksimum | 9.584.636 hitungan | 24 bit, satu bit lebih dari nilai asalnya |
| Jendela kemiringan | 37 sampel | 148 milidetik, sama dengan jendela integrasi terkunci |
| Gerbang refraktori | 50 sampel | 200 milidetik |
| Jendela uji | 90 sampel | 360 milidetik |
| Faktor uji keputusan | 2 | tidak ada pembagian, tidak ada pembulatan |

Tiga catatan implementasi yang lahir dari angka itu.

Pertama, uji keputusan memakai bentuk silang $2 s < s_{prev}$ dan karenanya tidak memerlukan
pembagian sama sekali. Harganya satu bit tambahan pada sisi kiri pembanding, yaitu 24 bit pada
rekaman ini, dan itu sudah tertutup oleh akumulator 32 bit yang dipakai jalur integrasi.

Pertanyaan yang diminta dijawab langsung: apakah perbandingan setengah kemiringan dapat dikerjakan
sebagai geseran, dan berapa galatnya terhadap acuan pecahan. Jawabannya: bentuk silang eksak dengan
galat nol hitungan pada seluruh kisi 16.777.216 pasangan, sedangkan bentuk geser ke bawah menyimpang
pada 2.048 pasangan dengan galat ambang satu hitungan dan arah biasnya selalu ke penolakan. Jadi
geseran boleh dipakai hanya dalam bentuk dibulatkan, yaitu $\left( s_{prev} + 1 \right) \gg 1$,
yang juga eksak dan hanya berbiaya satu penjumlah pada nilai yang disimpan.

Kedua, kemiringan QRS sebelumnya harus disimpan sebagai besaran utuh yang belum digeser kanan,
karena geser kanan yang diterapkan pada nilai yang sudah menyusut kehilangan lebih banyak bit.
Menyimpan 15 bit sudah cukup untuk nilai pada rekaman ini, sedangkan 24 bit diperlukan untuk bentuk
silangnya.

Ketiga, dua gerbang waktu memerlukan satu pencacah jarak bersama yang tidak direset oleh puncak yang
ditolak. Pada gerbang refraktori dan jendela 360 milidetik, titik hitungnya selalu QRS terakhir yang
sudah diakui, jadi RTL tidak boleh memakai puncak yang ditolak sebagai titik hitung baru.

## 10. Yang berbeda dari catatan lama

Empat anggapan lama diuji, dan seluruhnya dikoreksi oleh pengukuran di notebook.

| Klaim catatan lama | Hasil pengukuran | Keterangan |
|---|---|---|
| Aturan gelombang T menurunkan jumlah denyut palsu | benar pada EKG buatan, tetapi tidak pada rekaman AF | pada EKG buatan 160 gelombang T palsu hilang, pada AFDB 04015 kolam kandidat jalur kedua justru naik dari 22 ke 27 |
| Aturan ini hanya menambah kepekaan | kepekaan mentahnya turun 7 denyut dari 2.605 | 6 puncak ditolak dari 112 yang diperiksa, dan 6 dari 113 QRS di pita berisiko ikut tertolak |
| Kemiringan boleh diukur dari EKG terfilter | pada EKG buatan kedua bacaan memberi jumlah tolakan yang sama, 176 lawan 176 pada delapan amplitudo uji, jadi dasar pilihannya adalah bukti tekstual halaman 232 dan Gambar 1, bukan selisih jumlah tolakan | keluaran turunan lima titik dipilih, dengan dasar kalimat halaman 232 tentang diferensiasi untuk memberi informasi kemiringan QRS |
| Lebar jendela kemiringan tidak penting | hasilnya tidak monoton, dari 108 sampai 159 gelombang T buatan yang masih lolos | jendela 37 sampai 74 sampel bekerja, jendela 21 dan 75 sampel tidak |

Satu temuan lagi yang tidak ada di catatan lama mana pun, dan ini yang paling penting untuk
rancangan. Penanda irama teratur persamaan (29) berhenti menyala sepanjang rekaman `04015` ketika
aturan gelombang T dihidupkan, dari 1.129 penyalaan menjadi nol, hanya karena dua puncak pertama
yang semula diterima kini ditolak. Karena penanda itu yang memicu pemotongan separuh ambang, efek
sampingnya jauh lebih besar daripada efek langsungnya: pada mode pemotongan separuh yang dipicu
penanda, kolam kandidat jalur kedua naik dari 155 menjadi 279. Dua fase yang bertetangga, yaitu
fase 3 pemotongan separuh dan fase 5 aturan gelombang T, karenanya tidak boleh diputuskan terpisah.

## 11. Hubungan ke rancangan AFIB-LITE

Empat hal yang harus dibawa keluar dari dokumen ini ke rancangan.

1. Aturan gelombang T wajib ada sebagai lapisan terakhir keputusan, tetapi ia bukan pengganti
   pengkuadratan dan jendela integrasi. Pengkuadratan pada sinyal nyata hanya menambah 14,16
   desibel, sehingga sisa gelombang T sesudah pengkuadratan masih 0,038 dari QRS, dan angka itu yang
   membuat aturan ini perlu. Pada FRB buatan dengan gelombang T setinggi 0,7 milivolt ia menyelamatkan
   seluruh 160 denyut palsu.

2. Yang harus dipasang di RTL adalah dua pencacah jarak, 200 milidetik dan 360 milidetik, bukan satu
   gerbang tunggal. Di bawah 200 milidetik puncaknya sudah ditolak lebih dulu, dan di atas
   360 milidetik aturan ini buta. Titik hitung kedua pencacah adalah QRS terakhir yang sudah diakui.

3. Uji keputusannya adalah bentuk silang $2 s < s_{prev}$ dengan penyimpanan kemiringan QRS
   sebelumnya sebesar 24 bit untuk bentuk silang, atau bentuk geser dibulatkan bila tim ingin
   menghindari satu bit tambahan. Bentuk geser ke bawah tidak dipakai karena menyimpang ke arah
   penolakan pada pasangan batas.

4. Saklar. Karena pada fibrilasi atrium aturan ini lebih banyak menghambat, ia harus dipasang sebagai
   saklar satu bit yang dapat dimatikan, dan pada jalur AFIB ia hanya boleh dinyalakan bila penanda
   irama teratur sudah diperbaiki. Keputusan ini belum dikunci dan menunggu rapat tim, karena
   pengukurannya menunjukkan tiga hal yang saling meniadakan: kepekaan gerbang AND naik 1,28 poin,
   kepekaan mentah deteksi turun 7 denyut, dan penanda irama teratur mati seluruhnya. **Catatan
   19 Oktober 2026:** butir ini sudah diambil keputusannya, yaitu aturan dipakai di jalur AFIB, dan
   dasar terukurnya tertulis di bagian 12 butir P5-1, sedangkan efek samping penanda irama ditangani
   di lapisan RR lewat butir P4-5.

Satu catatan penutup untuk pembaca keluaran RTL. Puncak yang ditolak aturan ini bukan luaran, dan
penolakannya bukan pembuangan data: puncak yang dinyatakan gelombang T masuk ke jalur derau dan ikut
menaikkan taksiran puncak derau persamaan (13) dan (18). Karena itu efek aturan ini pada jumlah
denyut lebih besar daripada jumlah tolakan yang tercetak di tabel, dan kedua angka itu harus
dilaporkan berpasangan.

## 12. Keputusan yang dikunci 19 Oktober 2026

Lima butir di bawah ini adalah keputusan tim pada 19 Oktober 2026 atas hasil pengukuran fase 5, dan
seluruh angka dasarnya ada di bagian 3 sampai bagian 8 dokumen ini. Satu butir lapisan RR yang
menyertainya, yaitu butir P4-5, dirujuk silang di ujung bagian ini.

1. **P5-1. Aturan diskriminasi gelombang T DIPAKAI di jalur AFIB.** Dasar terukurnya adalah deret
   denyut detektor sendiri di bagian 8: gerbang keputusan membaik, kepekaan naik dari 76,04 menjadi
   77,32 persen, spesifisitas naik dari 89,11 menjadi 90,28 persen, dan akurasi naik dari 86,99
   menjadi 88,16 persen. Harga yang menyertainya tetap ditulis apa adanya, yaitu kepekaan mentah
   turun 7 denyut dan penanda irama teratur berhenti menyala pada rekaman `04015` seperti diukur di
   bagian 7.4 dan bagian 7.5, sedangkan efek samping penanda itu ditangani di lapisan RR lewat butir
   P4-5. Saklar satu bit di bagian 11 butir 4 tetap dipasang, tetapi kedudukannya berubah dari
   menunggu rapat tim menjadi dipakai.

2. **P5-2. Besaran kemiringan diambil dari KELUARAN TAHAP TURUNAN LIMA TITIK, bukan dari beda sinyal Catatan koreksi 19 Oktober 2026: pengukuran ulang yang adil menunjukkan kedua bacaan memberi jumlah gelombang T yang lolos sama banyak, yaitu 176 lawan 176 pada delapan amplitudo uji dan 0 lawan 0 pada rentang 0,50 sampai 0,90 milivolt. Dasar pilihan ini karena itu adalah kalimat halaman 232 serta keterangan Gambar 1, ditambah selisih jarak ke ambang yang terukur, dengan nisbah T terhadap QRS 1,40 pada 0,20 milivolt yang menyusut ke 1,01 pada 1,30 milivolt.
   EKG terfilter.** Dasarnya pengukuran di bagian 3.1 dan bagian 6: bacaan dari beda EKG terfilter
   memberi jumlah tolakan yang sama dengan bacaan dari keluaran
   turunan lima titik menolak seluruh 160 gelombang T itu. Halaman 234 tidak menyebut besarannya,
   dan dasar pilihan ini adalah kalimat halaman 232, "After filtering, the signal is differentiated
   to provide the QRS-complex slope information", beserta keterangan Gambar 1 di halaman 231 yang
   menyebut keluarannya sebagai "(c) Output of differentiator". Pemilihan besaran ini tetap ditandai
   sebagai keputusan tim yang dibuktikan pengukuran, bukan kutipan.

3. **P5-3. Uji keputusan memakai bentuk silang $2 s < s_{prev}$.** Bentuk ini eksak: nol salah dari
   4.776 pasangan terukur dan nol salah dari 16.777.216 kisi, sama seperti bentuk geser yang
   dibulatkan, sedangkan geseran biasa menyimpang pada 2.048 pasangan kisi dengan bias ke arah
   penolakan. Bentuk silang yang dipakai karena paling sederhana dan sudah terbukti, yaitu tanpa
   penjumlah tambahan dan tanpa pembulatan, seperti terukur di bagian 4.1 dan bagian 9.

4. **P5-4. Lebar jendela kemiringan ditetapkan 37 sampel, sama dengan jendela integrasi terkunci.**
   Halaman 234 tidak menentukan lebar itu, jadi angka 37 ditandai sebagai pilihan tim, dan
   pertimbangan tambahannya adalah penampan melingkar jendela integrasi yang sudah tersedia di RTL.
   Hasil pengukurannya tidak monoton: jendela 21 dan 75 sampel gagal, sedangkan jendela 37 sampel
   bekerja dengan nol gelombang T buatan yang lolos, seperti ditulis di bagian 3.2.

5. **P5-5. Batas keberlakuan aturan ditulis apa adanya: aturan gagal total bila gelombang T setinggi
   QRS, yaitu 0,90 milivolt ke atas pada uji ini.** Pada amplitudo 0,90 sampai 1,30 milivolt seluruh
   160 gelombang T buatan kembali diterima sebagai denyut, seperti terukur di bagian 6.1, sehingga
   angka itu adalah batas keberlakuan yang harus dilaporkan terbuka, bukan cacat yang disembunyikan.
   Kasus itu jarang karena tahap pengkuadratan sudah meredam gelombang T sebesar 14,16 desibel,
   sehingga sisa gelombang T sesudah pengkuadratan hanya 0,038 dari QRS, dan angka itu sudah tertulis
   di bagian 11 butir 1.

Butir lapisan RR yang menyertai kelima butir di atas adalah **P4-5**, aturan penyemaian ulang
rata-rata kedua, dengan definisi dan alasan terukurnya tertulis di
[[05 - rr-interval-averaging-equations|rr-interval-averaging-equations]] bagian 9.1. Butir itulah yang menangani penanda irama teratur
yang berhenti menyala pada rekaman `04015` seperti diukur di bagian 7.4 dokumen ini.

## 13. Rujukan

1. Pan J, Tompkins WJ. *A Real-Time QRS Detection Algorithm.* IEEE Transactions on Biomedical
   Engineering, 1985, BME-32(3):230-236. DOI 10.1109/TBME.1985.325532. Bagian `T-Wave Identification`
   beserta kalimat jendela 360 milidetik dan uji kemiringan separuh ada di halaman 234. Kalimat
   periode refraktori 200 milidetik ada di halaman 231, dan rumusan aturan yang lebih lengkap ada di
   halaman 232. Bagian `Derivative` beserta paragraf yang menyebut tahap turunan sebagai pemberi
   informasi kemiringan kompleks QRS ada di halaman 232, sedangkan paragraf pengantar yang menyebut
   hal yang sama ada di halaman 230. Seluruh kalimat yang dikutip di dokumen ini dibaca langsung dari
   gambar halaman 600 dpi salinan PDF di
   `~/.hermes/cache/scratch/explore/pan-tompkins-1985.pdf`, bukan dari lapisan teksnya.
2. Salinan penuh naskah: https://www.robots.ox.ac.uk/~gari/teaching/cdt/A3/readings/ECG/Pan+Tompkins.pdf
3. Cermin cadangan: https://people.ece.cornell.edu/land/courses/ece5030/labs/s2014/Pan_Tompkins.pdf
4. Dokumen pendamping di vault: [[04 - adaptive-threshold-equations|adaptive-threshold-equations]],
   [[05 - rr-interval-averaging-equations|rr-interval-averaging-equations]], dan [[07 - combined-risk-measurements|combined-risk-measurements]]
5. Dokumen konvensi dan breakdown: [[afib-lite/afib-rtl/34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown]], bagian 3.7 untuk konvensi fixed-point dan bagian 3.8 untuk anggaran latensi
   dan luas.
6. Notebook pendamping: `nabdha-afib-lite/model/math-equation-afib/06 - t-wave-discrimination.ipynb`
7. Data uji: PhysioNet MIT-BIH Atrial Fibrillation Database, rekaman `04015`, 250 Hz, 450.000 sampel
   pertama, kanal ECG1 12 bit, format 212. https://physionet.org/content/afdb/
8. Perangkat lunak: SciPy 1.17.1, NumPy 2.4.6, WFDB 4.3.1, dan NeuroKit2 0.2.13 pada lingkungan
   `~/.venvs/afib-lite`. Skrip kerja ada di `~/.hermes/cache/scratch/afib/fase5/`.
