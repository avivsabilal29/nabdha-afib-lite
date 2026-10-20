# Laporan Audit Testbench A1 sampai A5

Tanggal: 20 Oktober 2026. Repo: `nabdha-afib-lite`, branch `aviv/rtl-fpga-simulation`.
Lingkup: A1 sampai A6, usulan audit yang Aviv setujui untuk mengukur apakah testbench
Fase 2 sampai 4 benar-benar **sanggup gagal**, bukan hanya lulus.

Alat: Icarus Verilog 12.0, Verilator 5.020, Yosys 0.33 dan 0.70, mcy dan sby dari
`~/eda/oss-cad-suite/bin`, pustaka sel `sky130_fd_sc_hd__tt_025C_1v80.lib`.

## A1, batas putaran pada uji aliran

Uji paritas aliran menelusuri 450.000 kata per larian. Untuk pekerjaan harian itu
terlalu lama, dan untuk mutasi hampir mustahil.

- `tb_kuantisasi.sv` sekarang menerima `+LIMIT=n` pada dua loop uji aliran. **Jalur
  bawaan tidak berubah**: tetap 27 pemeriksaan, nol gagal.
- `+LIMIT=2000`: 23 pemeriksaan, nol gagal, selesai dalam beberapa detik. Jumlah
  pemeriksaan berkurang empat karena empat pemeriksaan memang hanya bermakna pada
  seluruh rekaman.
- `tb_lowpass.sv` dan `tb_highpass.sv` sudah memiliki `+LIMIT` sejak Fase 3.

Batas yang mengikat: untuk gerbang lebar jendela 37.000 dan 38.000, `+LIMIT` harus
**paling sedikit 40.000**. Batas kecil tidak boleh dipakai untuk gerbang itu.

## A2, suntikan cacat untuk membuktikan testbench sanggup gagal

Dua cacat disuntikkan ke **salinan** RTL, bukan ke berkas aslinya.

| Cacat | Akibat yang terukur |
|---|---|
| Tap garis tunda low-pass `x[i-6]` digeser menjadi `x[i-5]` | **19.995 beda**, putusan FAIL |
| Pembagi pulih kuantisasi meleset satu LSB | **1.516 cacah beda** dan **3.608 beda pada nodus `pre`** |

Keduanya tertangkap pada jendela yang pendek, jadi testbench sanggup gagal tanpa harus
menunggu seluruh rekaman. Nodus `pre` penting: aturan pembulatan setengah ke genap
hanya terbukti pada nodus itu, bukan pada kata keluaran.

## A3, cakupan mutasi tahap kuantisasi

Kampanye mcy penuh: 1.000 mutan atas `acq_frontend.sv`, satu putusan per mutan.

| Ukuran | Nilai |
|---|---|
| Mutan diuji | 1.000 |
| Tertangkap testbench | 590 |
| Lolos, testbench buta | 410 |
| Cakupan mutasi | **59,00 persen** |
| Mutan yang berakhir timeout | 8 |

Dua jebakan alat yang memakan waktu dan layak dicatat. Pertama, berkas `output.txt`
harus berisi **baris putusan saja** dalam bentuk `<jumlah> <TAG>`, karena mcy
memparse setiap baris; satu baris kalimat penjelasan membatalkan seluruh kampanye
dengan pesan `Invalid line format`. Kedua, loop penantian awal di `tb_kuantisasi.sv`
menunggu `sample_en` dan indeks sampel tanpa batas putaran, sehingga mutan yang merusak
dua sinyal itu menggantung selamanya pada 99,9 persen CPU. Empat proses sempat
menggantung hampir dua jam. Setiap simulasi sekarang dibatasi 120 detik dan timeout
dihitung sebagai mutan tertangkap, karena rancangan yang tidak pernah mengeluarkan
sampel valid memang rusak.

### Cakupan 59 persen itu belum angka yang jujur

Mode mutasi cepat `+MUT` yang saya buat **melewati uji waktu dan uji celah**, karena dua
uji itu menelusuri dua juta siklus. Akibatnya mutan yang kerusakannya hanya terlihat
pada dua uji itu pasti lolos, dan itu artefak dari jalan pintas saya sendiri, bukan
kelemahan testbench.

Bukti dari klasifikasi mutan:

| | Mutan lolos | Mutan tertangkap |
|---|---|---|
| Sinyal yang disentuh | `rate_cnt_q`, `m_ev_val`, `m_ev_kind`, `s_tuser`, `o_clamp_count` | `quo_q`, `g_langkah`, `prod_mag`, `quo_rnd` |
| Garis sumber 150 sampai 215 | 26 | 68 |
| Garis sumber di atas 270 | 26 | 3 |

Mutan yang tertangkap menumpuk di aritmetika pembagi dan jepit, yang memang selalu
dilalui uji paritas aliran. Mutan yang lolos menumpuk di **sideband peristiwa, penghitung
laju, dan penghitung jepit**, yaitu tepat bagian yang hanya diuji uji waktu dan uji
celah. Perbandingan di wilayah akhir sekitar sembilan banding satu.

**Tindak lanjut yang sudah ditetapkan:** 410 mutan lolos diuji ulang memakai
testbench **penuh**, tanpa mode cepat, sehingga uji waktu dan uji celah ikut menilai.
Angka cakupan final akan dilaporkan setelah itu, dan angka 59,00 persen di atas harus
dibaca sebagai batas bawah, bukan hasil akhir.

### Uji ulang: dugaan terbukti, dan ukurannya terukur

Dugaan di atas diuji dengan menjalankan mutan yang sama memakai testbench penuh di
direktori terpisah. Dua ukuran yang mengikat:

| Ukuran | Nilai |
|---|---|
| Biaya satu mutan dengan testbench penuh | **39 detik** (23 pemeriksaan, nol gagal pada rancangan asli) |
| Dari 52 mutan lolos pertama yang diuji ulang | **32 tertangkap**, 20 tetap lolos |

Jadi **32 dari 52 mutan yang tadi disebut lolos ternyata memang lubang mode cepat**,
bukan kelemahan testbench. Cakupan pada 52 itu naik dari 59,00 menjadi 61,54 persen
terhadap seluruh seribu. Sisa 358 mutan sedang diuji ulang, dan angka akhirnya masuk ke
tabel di atas setelah selesai.

Catatan alat yang layak diingat: mcy membersihkan direktori tugas begitu putusannya
dibaca, sehingga jumlah berkas di `tasks/` bukan tanda kemajuan. Dua kali saya salah
membaca itu dan menyimpulkan percobaan yang sehat sedang gagal. Ukuran kemajuan yang
sah hanya `mcy status`.

## A4, cakupan mutasi kedua tapis

Kampanye mcy atas `bandpass.sv` disusun sebagai **satu proyek dengan dua uji**, low-pass
dan high-pass, dan satu mutan dianggap tertangkap bila salah satu uji menangkapnya. Cara
ini lebih jujur daripada dua angka cakupan yang saling menutupi. Hasil lengkap:

| Ukuran | Nilai |
|---|---|
| Mutan diuji | 1.000 |
| Tidak tertangkap uji mana pun | **0** |
| Tertangkap paling sedikit satu uji | 1.000 |
| Cakupan mutasi | **100,00 persen** |

Seratus persen, dan sebabnya masuk akal: kedua tapis murni aritmetika atas garis tunda
dan riwayat, jadi hampir setiap mutasi mengubah aliran kata yang diperiksa uji paritas
kata demi kata. Bandingkan dengan kuantisasi yang hanya 59 persen pada mode cepat, dan
bedanya terletak pada banyaknya logika waktu dan sideband peristiwa yang tidak muncul di
aliran kata.

## A5, pembuktian latensi

**Status: belum selesai, dan tidak saya samarkan.** Harness ada di
`rtl-synthesis/sby/derivative_latency.sv` dengan konfigurasi `derivative_latency.sby`,
dan pada saat laporan ini ditulis sby masih menemukan counterexample pada siklus 18.

### Temuan yang sudah pasti, dan ini yang berharga

Harness pertama saya memegang `s_tvalid` tinggi setiap siklus lalu menuntut `m_tvalid`
tinggi terus. Itu gagal pada siklus 18, dan **kegagalan itu perilaku RTL yang benar,
bukan bug**. Tahap turunan **bukan** saluran satu sampel per siklus: ia menerima satu
sampel lalu sibuk selama enam belas siklus, jadi disiplin masukannya adalah **strobe**
dan keluarannya adalah **pulsa**. RTL-nya sendiri menyatakannya di baris 256: kata yang
datang saat tahap sedang sibuk akan hilang, karena tidak ada `tready` di dalam.

Artinya kalimat "latensi tetap dan tidak pernah menahan" pada rencana baru sahih
**dengan syarat jarak strobe**. Kalimat itu perlu dipertegas untuk seluruh tahap
multisiklus, bukan hanya tahap ini.

### Yang belum terbukti dan mengapa

Pembuktian formal "strobe menghasilkan satu pulsa keluaran tepat LAT siklus kemudian"
belum berhasil. Tiga percobaan terakhir saya gagal karena harness-nya sendiri:
BMC di sby mulai dari keadaan awal yang bebas, sehingga penghitung siklus harness bisa
mulai dari nilai besar dan pernyataan latensi menyala terlalu dini. Atribut `init`
saya pasang, dan counterexample-nya memang berpindah dari siklus 2 ke siklus 18, tetapi
belum hilang.

Yang menjadi bukti latensi saat ini, dan saya sebut apa adanya: paritas kata demi kata
atas seluruh 450.000 sampel pada bench Fase 4, dan pengukuran 17 siklus per sampel yang
dilaporkan bench itu. Keduanya bukti kuat, tetapi keduanya bukti **simulasi**, bukan
bukti formal. Menutup celah itu adalah pekerjaan tersendiri.

## A6, kesimpulan

Testbench Fase 2 sampai 4 **sudah terbukti sanggup gagal**, bukan hanya sanggup lulus:
satu cacat aritmetika dan satu cacat tapis keduanya tertangkap pada jendela pendek, dan
kampanye mutasi menangkap 590 dari 1.000 mutan. Yang belum selesai adalah memisahkan
mutan yang benar-benar setara secara fungsional dari mutan yang memang belum teruji,
dan itulah pekerjaan uji ulang yang sudah ditetapkan di atas.
