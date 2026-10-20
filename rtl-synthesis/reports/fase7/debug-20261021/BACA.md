# Harness debug Fase 7 (bukti investigasi, BUKAN bagian gerbang)

t_rule_dbg.sv  salinan rtl/t_rule.sv dengan $display pada kata awal scan dan kata fire,
               dipakai untuk membuktikan jeda kata yang diterima (start = puncak+19, fire = puncak+29).
tb_dbg.sv      dua puncak pada derajat tetap 1000, satu puncak, untuk mengukur latensi dan
               membuktikan jendela dibaca pada [pos-18, pos+18].
tb_dbg2.sv     garis tanjakan + dua spike negatif besar; smoke ini membuktikan indeks i=0
               adalah tap tertua dan kem = maks|turunan| atas jendela penuh.
