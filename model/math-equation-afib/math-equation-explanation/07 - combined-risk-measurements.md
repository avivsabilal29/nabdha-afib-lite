# Pengukuran Risiko Gabungan Rantai Pan-Tompkins

Dokumen ini melaporkan tiga pengukuran risiko gabungan yang belum pernah dijalankan pada rantai AFIB-LITE. Ketiganya memakai satu rantai penuh yang dibangun dari persamaan makalah Pan dan Tompkins: low-pass persamaan (3) halaman 232, high-pass persamaan (6) halaman 232, turunan lima titik persamaan (9) halaman 233, pengkuadratan persamaan (10) halaman 233, integrasi jendela bergerak persamaan (11) halaman 233, ambang adaptif persamaan (12) sampai (23) halaman 233 dan 234, dan rata-rata interval RR beserta penanda irama persamaan (24) sampai (29) halaman 234. Seluruh angka di dokumen ini berasal dari eksekusi nyata di mesin ini, bukan dari ingatan dan bukan dari kutipan. Skrip kerjanya ada di `~/.hermes/cache/scratch/afib/risiko/` yaitu `rantai.py`, `intisari.py`, `ukur1.py`, `ukur2.py`, dan `ukur3.py`.

Rekaman uji terkunci adalah AFDB `04015`, potongan 450.000 sampel pertama, 250 Hz, 1800,0 detik, kanal ECG1 12 bit, format 212. Rekaman itu hanya membawa anotasi irama, yaitu lima belas penanda perubahan irama, dan tidak membawa anotasi denyut. Karena itu seluruh pengukuran di dokumen ini bekerja pada tingkat keputusan dan pada tingkat fitur jendela, dan tidak satu pun boleh dibaca sebagai unjuk kerja deteksi terhadap rujukan denyut per denyut.

Konvensi bilangan bulat yang dipakai adalah konvensi terkunci: masukan dijepit pada plus minus 2047 hitungan lalu digeser kiri empat bit, keluaran turunan digeser kanan delapan bit, pembagian dengan 38 tidak dilakukan sehingga ambang yang dikalikan 38, dan jendela integrasi bergantian 37 dan 38 sampel. Rantai yang dibangun di sini memenuhi seluruh lebar bit konvensi itu: selubung integrasi mencapai 3.105.281.786 hitungan dan menempati 32 bit, tepat seperti anggaran yang sudah dikunci.

## 1. Ringkasan tiga temuan

| Nomor | Pengukuran | Keadaan terukur sebelum penggabungan | Hasil pengukuran gabungan pada rantai penuh | Sifat terhadap keputusan terkunci |
|---|---|---|---|---|
| 1 | Calon palsu jalur ambang kedua bersama batas bawah RR | calon jalur kedua 21, penanda irama menyala 898, 890, dan 9 pada tiga bentuk batas bawah | calon jalur kedua 22 dengan pemotongan mati dan 272 dengan pemotongan hidup, penanda menyala 1129, 1136, dan 1005 | mengubah, keruntuhan penanda dari 9 menjadi 1005 tidak terjadi saat digabung |
| 2 | Kisi 8 milidetik terhadap fitur entropi dan gerbang AND | AUC entropi 0,904 dan kepekaan gerbang 92,63 persen pada deret acuan | kisi 8 milidetik sendiri menurunkan kepekaan 1,05 poin, sedangkan deret detektor sendiri menurunkan 15,54 poin lagi | mengubah, penyebab utama kehilangan kepekaan bukan kisi waktu melainkan deret denyut detektor sendiri |
| 3 | Mode pembulatan ambang pada keputusan | bias terukur 3,49 hitungan ke arah bawah dan sisa tetap 7 hitungan | nol denyut berbeda, nol penanda berbeda, nol poin kepekaan berbeda, beda jejak ambang paling besar 7 hitungan | menguatkan, geser kanan aritmetika tetap pilihan yang benar |

Cara ukur baris pertama adalah enam putaran rantai penuh pada `ukur1.py`. Cara ukur baris kedua adalah tiga deret RR dan satu gerbang AND tetap pada `ukur2.py`. Cara ukur baris ketiga adalah dua putaran rantai penuh ditambah satu deret puncak konstan buatan pada `ukur3.py`.

## 2. Pengukuran 1, risiko gabungan calon palsu jalur kedua dan batas bawah RR

### 2.1 Cara pengukuran

Rantai penuh dijalankan satu kali penuh sampai selubung integrasi. Pemetik puncak selubung memakai aturan puncak dominan dengan penopang 27 sampel pada tiap sisi, yang menghasilkan 4.777 puncak. Angka itu dipakai supaya sebanding dengan pengukuran terpisah yang melaporkan 4.805 puncak, dan selisihnya 0,58 persen.

Tahap ambang menjalankan persamaan (12) sampai (23) dengan dua pilihan. Pertama, pemotongan separuh dimatikan. Kedua, pemotongan separuh dinyalakan terus, yaitu persamaan (22) dan (23) dipakai pada setiap puncak tanpa syarat pemicu:

$$
I1 \leftarrow 0{,}5 \, I1, \qquad F1 \leftarrow 0{,}5 \, F1
$$

Ambang pertama sebelum pemotongan adalah persamaan (14) dalam bentuk bilangan bulat:

$$
I1 = NPKI + \left( \left( SPKI - NPKI \right) \gg 2 \right)
$$

Sebagai tambahan yang tidak ada di pengukuran terpisah, rantai di sini memakai masa tahan 200 milidetik, yaitu 50 sampel, sesuai kalimat halaman 231 bahwa kompleks QRS tidak dapat muncul lebih rapat daripada itu. Masa tahan itu yang mencegah satu denyut dihitung berkali-kali.

Tahap RR menjalankan persamaan (24) sampai (29) pada deret denyut yang dihasilkan tahap ambang, dengan tiga bentuk batas bawah yang dibandingkan lewat perkalian silang tanpa pembagian:

$$
25 \, RR \ge 23 \, RR_{AVERAGE2}, \qquad 64 \, RR \ge 59 \, RR_{AVERAGE2}, \qquad 32 \, RR \ge 30 \, RR_{AVERAGE2}
$$

Batas atas dan batas kelewatan mengikuti bentuk yang setara, yaitu 29 per 25 dan 83 per 50 pada bentuk eksak, 74 per 64 dan 106 per 64 pada bentuk penyebut 64, serta 37 per 32 dan 53 per 32 pada bentuk penyebut 32. Jadi yang berubah antar baris tabel hanyalah batas bawah beserta batas atas yang sepasang dengannya. Bacaan persamaan (25) yang dipakai adalah bacaan harfiah, yaitu rata-rata delapan interval lolos terakhir, karena itulah bacaan yang bertahan pada deret denyut nyata tanpa membeku. Penanda irama menyala bila kedelapan interval terakhir berada di dalam batas, yaitu persamaan (29).

### 2.2 Tabel hasil

| Pemotongan separuh | Batas bawah | Denyut | Calon jalur kedua | Aktivasi cari mundur | Penanda menyala | Langkah penanda | Ambang I1 median |
|---|---|---|---|---|---|---|---|
| dimatikan | tepat 23 per 25 | 2.605 | 22 | 7 | 1.129 | 2.594 | 57.321.458 |
| dimatikan | 59 per 64 | 2.605 | 22 | 7 | 1.136 | 2.594 | 57.321.458 |
| dimatikan | 30 per 32 | 2.605 | 21 | 7 | 1.005 | 2.594 | 57.321.458 |
| dinyalakan terus | tepat 23 per 25 | 2.625 | 272 | 1 | 1.132 | 2.609 | 28.156.835 |
| dinyalakan terus | 59 per 64 | 2.625 | 272 | 1 | 1.130 | 2.609 | 28.156.835 |
| dinyalakan terus | 30 per 32 | 2.625 | 272 | 1 | 1.034 | 2.609 | 28.156.835 |

Seluruh angka tabel itu diukur pada rekaman `04015` oleh `ukur1.py`. Kolom denyut adalah jumlah kompleks QRS yang terbentuk, kolom calon jalur kedua adalah jumlah puncak derau yang nilainya di antara ambang kedua dan ambang pertama sehingga menjadi calon pengangkatan pencarian mundur, dan kolom ambang I1 median adalah median ambang pertama domain integrasi sepanjang seluruh puncak.

Sebagai kendali, tahap RR yang sama dijalankan pada deret denyut acuan yang berlabel anotasi irama, supaya terlihat apakah keruntuhan penanda yang terukur terpisah tetap muncul di luar rantai ini.

| Batas bawah | Penanda menyala pada deret acuan | Langkah | RR rata-rata kedua median | RR rata-rata kedua maksimum |
|---|---|---|---|---|
| tepat 23 per 25 | 807 | 2.590 | 790,5 ms | 986,0 ms |
| 59 per 64 | 744 | 2.590 | 783,5 ms | 986,0 ms |
| 30 per 32 | 11 | 2.590 | 982,5 ms | 1.001,5 ms |

### 2.3 Tafsir

Temuan pertama, pemotongan separuh melipatgandakan calon jalur kedua persis seperti yang dilaporkan pengukuran terpisah. Angkanya 22 menjadi 272, yaitu 12,3636 kali, dengan ambang pertama median turun dari 57.321.458 menjadi 28.156.835 hitungan, yaitu 0,4912 kali. Jumlah denyut yang terbentuk hanya naik dari 2.605 menjadi 2.625, yaitu 0,7678 persen, dan aktivasi cari mundur justru turun dari 7 menjadi 1. Jadi harga pemotongan separuh dibayar seluruhnya di jalur ambang kedua, dan itu menguatkan keputusan terkunci bahwa angka kepekaan harus selalu dilaporkan berpasangan dengan angka salah positifnya.

Temuan kedua, dan inilah mekanisme yang hanya muncul saat digabung. Keruntuhan penanda irama yang terukur terpisah, dari 898 menjadi 9 pada bentuk 30 per 32, tidak terjadi pada rantai penuh. Pada rantai penuh bentuk 30 per 32 menyala 1.005 kali dari 2.594 langkah, yaitu 0,3874, sedangkan bentuk eksak menyala 1.129 kali, yaitu 0,4352. Keruntuhan itu turun menjadi selisih 124 penyalaan atau 10,9832 persen pada keadaan pemotongan mati, dan menjadi selisih 98 penyalaan atau 8,6572 persen pada keadaan pemotongan hidup. Sebabnya terlihat pada kolom ketiga tabel kendali: pada deret acuan batas bawah kasar menaikkan RR rata-rata kedua median dari 790,5 milidetik ke 982,5 milidetik sehingga batasnya meninggalkan irama yang harus diloloskannya, sedangkan pada deret detektor sendiri RR rata-rata kedua bertahan di sekitar 724 milidetik sehingga batas kasarnya tetap memuat irama. Dengan kata lain, rantai penuh melemahkan umpan balik yang meruntuhkan penanda, karena deret denyutnya sendiri sudah membawa cukup banyak interval pendek pada segmen fibrilasi atrium.

Temuan ketiga, ada satu interaksi dua arah yang terukur dan tidak muncul di pengukuran terpisah mana pun. Dengan pemotongan separuh hidup, bentuk batas bawah kasar 30 per 32 justru menaikkan penyalaan penanda dari 1.005 menjadi 1.034, yaitu 29 penyalaan atau 2,8856 persen. Sebabnya, pemotongan separuh menerima lebih banyak denyut sehingga rata-rata intervalnya turun dan batas kasarnya menjadi lebih cocok dengan irama yang sesungguhnya. Jadi pemotongan separuh dan batas bawah kasar tidak saling menumpuk menjadi keruntuhan berlipat, melainkan sebagian saling menghapus. Yang tetap benar dan menguatkan keputusan terkunci adalah urutan pilihan: bentuk 59 per 64 menyala 1.136 kali dan bentuk eksak 1.129 kali pada keadaan pemotongan mati, jadi keduanya sebanding, sedangkan bentuk 30 per 32 tetap yang paling rendah pada kedua keadaan. Namun angka 1.005 sebagai ganti 9 berarti alasan penolakan 30 per 32 tidak lagi dapat bersandar pada keruntuhan penanda, dan harus bersandar pada pergeseran letak batas sebesar 1,9022 persen beserta tambahan calon jalur kedua.

Satu catatan kejujuran tentang pengukuran terpisah. Tahap RR di sini tidak dijalankan pada deret denyut yang sama dengan pengukuran terpisah, karena pengukuran terpisah memakai deret yang sudah tersaring topeng mutu dan berhenti di 2.515 langkah, sedangkan di sini deretnya 2.594 langkah. Karena itu perbandingan angka 898 dengan 1.129 dan angka 9 dengan 1.005 adalah perbandingan tingkat penyalaan, yaitu 0,3571 melawan 0,4352 dan 0,0036 melawan 0,3874, dan bukan perbandingan bilangan yang sama-sama sejenis.

## 3. Pengukuran 2, dampak kisi 8 milidetik terhadap fitur entropi dan gerbang AND

### 3.1 Cara pengukuran

Jendela integrasi bergantian 37 dan 38 sampel panjangnya tepat 150,0 milidetik, dan pada rantai ini jendela 38 sampel selalu jatuh pada indeks ganjil. Akibatnya puncak selubung yang dipilih pemetik selalu berada pada indeks ganjil, terukur 1,0000 dari seluruh puncak, sehingga seluruh interval RR yang berasal dari detektor sendiri menjadi kelipatan delapan milidetik:

$$
RR = 8k \ \text{ms}, \qquad k = 1, 2, 3, \ldots
$$

Fitur dihitung persis seperti rantai fitur yang sudah ada, pada jendela 32 denyut berlangkah 4 denyut, dengan label kelas diambil dari anotasi irama resmi dan hanya jendela yang seluruh 32 denyutnya satu kelas yang dipakai. Rumusnya adalah RMSSD, RMSSD dibagi rata-rata RR, pNN50 yaitu bagian selisih interval berurutan yang melebihi 50 milidetik, dan entropi ternormalisasi

$$
H = -\sum_{i} p_i \log_2 p_i, \qquad H_{norm} = \frac{H}{4}
$$

dengan 16 bin yang batasnya diambil dari sebaran setelah 8 interval terpanjang dan 8 interval terpendek dibuang. Gerbang AND yang sudah ada adalah RMSSD dibagi rata-rata RR lebih besar dari 0,21 DAN entropi ternormalisasi lebih besar dari 0,70. AUC dihitung dengan rumus peringkat Mann dan Whitney.

Tiga deret RR dibandingkan. Deret A adalah keluaran detektor rantai penuh kita sendiri, terkunci pada kisi 8 milidetik. Deret B adalah deret acuan yang berasal dari saluran anotasi irama, yaitu pemetik pantompkins1985 pada sinyal yang sama, dengan kisi 4 milidetik. Deret C adalah kendali kisi, yaitu deret B yang waktunya dibulatkan ke kisi 8 milidetik, supaya dampak kisi terpisah dari dampak deret denyut.

### 3.2 Tabel hasil

| Deret RR | Denyut | Jendela (AFIB dan N) | Interval kelipatan 8 ms | AUC RMSSD | AUC RMSSD/MeanRR | AUC pNN50 | AUC entropi |
|---|---|---|---|---|---|---|---|
| A, detektor sendiri kisi 8 ms | 2.605 | 592 (96 dan 496) | 1,0000 | 0,6547 | 0,7760 | 0,8561 | 0,9460 |
| B, acuan anotasi irama kisi 4 ms | 2.601 | 590 (95 dan 495) | 0,5181 | 0,6337 | 0,7699 | 0,8278 | 0,9045 |
| C, acuan dikisi 8 ms | 2.601 | 590 (95 dan 495) | 1,0000 | 0,6337 | 0,7701 | 0,8077 | 0,9437 |

| Deret RR | Median RMSSD AFIB | Median RMSSD N | Median entropi AFIB | Median entropi N | Kepekaan gerbang AND | Spesifisitas | Akurasi | Jendela N lolos gerbang |
|---|---|---|---|---|---|---|---|---|
| A, detektor sendiri kisi 8 ms | 132,00 ms | 36,50 ms | 0,7695 | 0,3119 | 76,04 persen | 89,11 persen | 86,99 persen | 10,89 persen |
| B, acuan anotasi irama kisi 4 ms | 131,10 ms | 70,41 ms | 0,8007 | 0,6506 | 92,63 persen | 79,60 persen | 81,69 persen | 20,40 persen |
| C, acuan dikisi 8 ms | 131,51 ms | 70,62 ms | 0,8007 | 0,5313 | 91,58 persen | 81,62 persen | 83,22 persen | 18,38 persen |

Seluruh angka diukur oleh `ukur2.py` pada rekaman `04015`. Baris B mereproduksi pengukuran acuan yang sudah terkunci sampai tiga angka di belakang koma, yaitu median RMSSD 131,104 dan 70,413 milidetik, median entropi 0,8007 dan 0,6506, keempat AUC 0,634, 0,770, 0,828, dan 0,904, serta gerbang 92,6 persen, 79,6 persen, dan 81,7 persen pada 590 jendela. Kesesuaian itu memastikan bahwa perangkat ukur di dokumen ini menerapkan rantai fitur dengan benar.

### 3.3 Tafsir

Temuan pertama, dampak kisi waktu terukur kecil dan arahnya bukan seperti yang diduga. Membandingkan baris C dengan baris B memisahkan kisi 8 milidetik dari deret denyutnya, dan hasilnya kepekaan gerbang turun dari 92,63 persen menjadi 91,58 persen, yaitu 1,05 poin saja, sementara spesifisitasnya justru naik dari 79,60 persen menjadi 81,62 persen dan akurasinya naik dari 81,69 persen menjadi 83,22 persen. Yang menarik, kisi itu menaikkan AUC entropi ternormalisasi dari 0,9045 menjadi 0,9437, sedangkan AUC pNN50 turun dari 0,8278 menjadi 0,8077. Sebabnya terlihat pada median entropi kelas N, yang turun dari 0,6506 menjadi 0,5313 ketika intervalnya dipaksa ke kisi 8 milidetik, sehingga histogramnya memampat dan entropinya menurun; pemampatan itu justru memperlebar jarak kelas N terhadap kelas AFIB yang mediannya tidak bergerak.

Temuan kedua, penyebab utama kehilangan kepekaan bukan kisi, melainkan deret denyut detektor sendiri. Membandingkan baris A dengan baris C memberi selisih 91,58 persen menjadi 76,04 persen, yaitu 15,54 poin, atau sepuluh kali lebih besar daripada harga kisinya. Selisih total dari baris B ke baris A adalah 16,59 poin. Ini mengubah keputusan terkunci yang sebelumnya menyebut kuantisasi waktu puncak R sebagai mekanisme kehilangan kepekaan, karena pada rantai penuh kisi 8 milidetik hanya memikul 1,05 poin dari 16,59 poin. Yang memikul 15,54 poin sisanya adalah deret denyut detektor sendiri, yaitu puncak tambahan dan denyut yang terlewat, dan itu terlihat pada median kelas N yang jatuh dari 70,62 milidetik menjadi 36,50 milidetik dan median pNN50 kelas N yang jatuh dari 0,4194 menjadi 0,1290. Kelas N pada deret detektor sendiri jadi jauh lebih teratur daripada kelas N pada deret acuan, sehingga sebagian jendela N menyerupai kelas AFIB dan sebagian jendela AFIB gagal melewati gerbang.

Temuan ketiga, AUC entropi ternormalisasi tetap fitur terbaik pada ketiga deret, yaitu 0,9460, 0,9045, dan 0,9437, sehingga keputusan terkunci untuk memakai entropi ternormalisasi sebagai fitur unggulan tetap berlaku dan justru menguat. Namun ambang 0,70 yang terkunci tidak dapat dipindahkan begitu saja ke deret detektor sendiri, karena median kelas N turun dari 0,6506 ke 0,3119 sementara median kelas AFIB hampir tidak bergerak dari 0,8007 ke 0,7695. Jadi ambang dan deret fitur harus diputuskan bersama, dan keputusan itu belum dikunci.

## 4. Pengukuran 3, dampak keputusan dari mode pembulatan ambang

### 4.1 Cara pengukuran

Pembaruan taksiran puncak memakai bentuk selisih, yang pada aritmetika bilangan bulat berbentuk geser kanan tiga bit:

$$
SPKI \leftarrow SPKI + \left( \left( PEAKI - SPKI \right) \gg 3 \right)
$$

Pengukuran ini menjalankan rantai penuh dua kali pada rekaman `04015`, sekali dengan mode ke bawah yaitu geser kanan aritmetika, dan sekali dengan mode ke arah nol yaitu pemotongan yang sama untuk selisih positif tetapi berbeda untuk selisih negatif. Yang dibandingkan adalah seluruh keputusan: jumlah denyut, jumlah calon jalur kedua, jumlah aktivasi pencarian mundur, jumlah penanda irama yang menyala, jejak ambang pertama sepanjang 4.777 puncak, dan kepekaan serta spesifisitas gerbang AND pada deret RR yang dihasilkan. Sebagai acuan besaran bias, dijalankan juga deret puncak konstan 1.000 hitungan selama 60 pemutakhiran pada kedua mode.

### 4.2 Tabel hasil

| Mode pembulatan | Denyut | Calon jalur kedua | Cari mundur | Penanda menyala | Langkah | Ambang I1 median | Ambang I1 maksimum | Nilai tunak puncak konstan 1.000 |
|---|---|---|---|---|---|---|---|---|
| ke bawah, geser kanan | 2.605 | 22 | 7 | 1.129 | 2.594 | 57.321.458 | 190.421.069 | 993 |
| ke arah nol | 2.605 | 22 | 7 | 1.129 | 2.594 | 57.321.463 | 190.421.071 | 993 |

| Besaran keputusan | Mode ke bawah | Mode ke arah nol | Selisih |
|---|---|---|---|
| Denyut terbentuk | 2.605 | 2.605 | 0 |
| Denyut yang hanya muncul di satu mode | acuan | acuan | 0 |
| Penanda irama menyala | 1.129 | 1.129 | 0 |
| Kepekaan gerbang AND | 76,04 persen | 76,04 persen | 0,000000 |
| Spesifisitas gerbang AND | 89,11 persen | 89,11 persen | 0,000000 |
| Akurasi gerbang AND | 86,99 persen | 86,99 persen | 0,000000 |
| Beda jejak ambang paling besar | acuan | 7 hitungan | 7 hitungan pada 4.743 dari 4.777 langkah |
| Beda jejak ambang rata-rata | acuan | 3,8166 hitungan | 6,7 kali sepuluh pangkat minus delapan dari median ambang |

Seluruh angka diukur oleh `ukur3.py`. Tabel pertama adalah keadaan rantai penuh dan nilai tunak deret puncak konstan. Tabel kedua adalah perbandingan keputusan antara kedua mode.

### 4.3 Tafsir

Temuan pertama, pada deret puncak konstan kedua mode memberi nilai tunak yang sama, yaitu 993 hitungan, dengan sisa tetap 7 hitungan dari 1.000. Jadi sisa tetap tujuh hitungan itu bukan akibat mode pembulatan, melainkan akibat bobot 0,125 pada bentuk selisih, karena selisih 7 dibagi delapan menjadi 0,875 dan dibuang oleh mode apa pun. Ini melengkapi pengukuran terpisah yang melaporkan sisa 7 hitungan, dan memperjelas bahwa mode ke arah nol tidak menghapus sisa itu pada deret naik yang seluruh selisihnya positif.

Temuan kedua, kedua mode berbeda hanya pada selisih negatif terjadwal, dan perbedaannya tidak menyentuh satu keputusan pun. Jejak ambangnya berbeda pada 4.743 dari 4.777 langkah, tetapi bedanya paling besar 7 hitungan dan rata-rata 3,8166 hitungan, yaitu 6,7 kali sepuluh pangkat minus delapan dari median ambangnya. Pada skala itu tidak ada puncak yang berpindah sisi ambang: jumlah denyut sama, jumlah calon jalur kedua sama, jumlah aktivasi pencarian mundur sama, jumlah penanda irama yang menyala sama, dan ketiga angka gerbang AND sama sampai enam angka di belakang koma. Jadi kesimpulannya menguatkan keputusan terkunci bahwa geser kanan aritmetika tetap pilihan yang benar, dan bahwa bias beberapa hitungan yang terukur pada deret panjang tidak berharga apa pun bagi keputusan. Yang perlu dicatat hanya satu: karena selisihnya nol pada rekaman ini, pengukuran ini tidak dapat dipakai untuk membenarkan pemilihan mode sebaliknya, dan alasan memilih geser kanan tetap alasan biaya rangkaian, bukan alasan keputusan.

## 5. Risiko yang masih terbuka sesudah tiga pengukuran

1. Bacaan persamaan (25) menentukan seluruh perilaku penanda irama, dan bacaan itu sudah dikunci pada P4-1 memakai bacaan antrean, sehingga yang belum hanyalah penerapannya di RTL. Pada rantai penuh, bacaan langsung yaitu rata-rata interval lolos di antara delapan interval terakhir membekukan RR rata-rata kedua pada 1.112 milidetik dan menghasilkan nol penyalaan penanda pada seluruh konfigurasi, sedangkan bacaan antrean yaitu rata-rata delapan interval lolos terakhir menghasilkan sekitar 1.130 penyalaan. Selisih itu adalah pilihan rancangan, bukan angka salah, dan konsekuensinya jauh lebih besar daripada seluruh risiko kisi waktu.

2. Deret denyut detektor sendiri memikul 15,54 poin dari kehilangan kepekaan gerbang AND, sedangkan kisi waktu hanya memikul 1,05 poin. Risiko ini belum dapat ditutup pada rekaman ini karena rekaman hanya membawa anotasi irama. Untuk menutupnya diperlukan rekaman dengan anotasi denyut, atau pengukuran ulang pada basis data yang membawa anotasi denyut.

3. Puncak susulan di dalam satu selang denyut masih diterima sebagai calon denyut, dengan angka terukur 272 calon pada keadaan pemotongan separuh hidup. Aturan penolakan puncak susulan ada di halaman 234 dan belum dibuka pada fase ini, sehingga angka 272 itu adalah batas atas yang harus diturunkan oleh fase berikutnya, bukan angka akhir.

4. Pembekuan RR rata-rata kedua masih mungkin terjadi. Pada deret acuan yang dipakai kendali, bentuk batas bawah 30 per 32 membekukan RR rata-rata kedua pada 982,5 milidetik dan menyala 11 kali dari 2.590 langkah. Karena batas kelewatan persamaan (28) ditetapkan dari RR rata-rata kedua, pembekuan itu berarti jendela pemeriksaan pencarian mundur juga beku. Batas umur RR rata-rata kedua belum diputuskan.

5. Ambang gerbang AND belum dapat dipindahkan ke deret detektor sendiri. Median entropi kelas N turun dari 0,6506 pada deret acuan menjadi 0,3119 pada deret detektor sendiri, sedangkan ambangnya terkunci 0,70. Selama deret fitur belum ditetapkan, pasangan ambang dan deret itu adalah risiko terbuka, bukan sekadar soal penyetelan.

6. Angka kepekaan pemotongan separuh tetap harus dilaporkan berpasangan dengan calon jalur keduanya, karena pengukuran gabungan menaikkan calon 12,3636 kali sementara kepekaannya hanya naik 0,7678 persen pada jumlah denyut. Pengukuran gabungan bahkan menurunkan aktivasi pencarian mundur dari 7 menjadi 1, dan itu memperkuat alasan pelaporan berpasangan.

7. Rantai di sini memakai masa tahan 200 milidetik yang diambil dari halaman 231, sedangkan pengukuran terpisah tidak menyebutnya. Masa tahan itu bagian dari algoritma, tetapi peranannya terhadap jumlah denyut belum diukur tersendiri, sehingga selisih 2.605 lawan 2.603 denyut terhadap pengukuran terpisah belum dapat dipisahkan antara masa tahan dan pemetik puncak.

## 6. Rujukan

1. Pan J, Tompkins WJ. *A Real-Time QRS Detection Algorithm.* IEEE Transactions on Biomedical Engineering, 1985, BME-32(3):230-236. DOI 10.1109/TBME.1985.325532. Persamaan (3) dan (6) ada di halaman 232, persamaan (9), (10), dan (11) beserta paragraf lebar jendela ada di halaman 233, dan persamaan (12) sampai (29) beserta aturan masa tahan 200 milidetik dan aturan irama tidak teratur ada di halaman 233 dan 234. Salinan PDF naskahnya ada di `~/.hermes/cache/scratch/explore/pan-tompkins-1985.pdf`.
2. Salinan penuh naskah: https://www.robots.ox.ac.uk/~gari/teaching/cdt/A3/readings/ECG/Pan+Tompkins.pdf
3. Cermin cadangan: https://people.ece.cornell.edu/land/courses/ece5030/labs/s2014/Pan_Tompkins.pdf
4. Dokumen turunan di vault: [[00 - low-pass-filter-equation|low-pass-filter-equation]], [[01 - high-pass-filter-equation|high-pass-filter-equation]], [[02 - five-point-derivative-equation|five-point-derivative-equation]], [[03 - squaring-and-moving-window-integrator-equation|squaring-and-moving-window-integrator-equation]], [[04 - adaptive-threshold-equations|adaptive-threshold-equations]], dan [[05 - rr-interval-averaging-equations|rr-interval-averaging-equations]].
5. Dokumen konvensi dan breakdown: [[afib-lite/afib-rtl/34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown]], bagian 3.7 untuk konvensi fixed-point dan bagian 3.8 untuk anggaran latensi dan luas.
6. Data uji: PhysioNet MIT-BIH Atrial Fibrillation Database, rekaman `04015`, 250 Hz, 450.000 sampel pertama, kanal ECG1 12 bit. https://physionet.org/content/afdb/
7. Perangkat lunak pengukuran: SciPy 1.17.1, NumPy 2.4.6, WFDB 4.3.1, dan NeuroKit2 pada lingkungan `~/.venvs/afib-lite`. Skrip kerja: `~/.hermes/cache/scratch/afib/risiko/rantai.py`, `intisari.py`, `ukur1.py`, `ukur2.py`, `ukur3.py`, dan pemeriksa `~/.hermes/cache/scratch/afib/check_risiko.py`.
