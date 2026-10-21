# S7 open correction note

Step S7 of the phase 6 plan of AFIB-LITE. Goal, as written in the design document section 13:
remove the 51064 ms pause that the phase 2 and phase 3 threshold chain produces, by diagnosing the
root cause first, then making exactly one change, then measuring before and after. The gate is that
the longest pause drops to a value that can be defended, with no regression in sensitivity and
specificity.

Everything below is either measured in this session or explicitly marked as a hypothesis. Nothing
is marked as a fact without a run behind it.

## 1. Diagnosis, made before anything was changed

### 1.1 The defect, measured

A fresh streaming run of the locked `rantai.py` over recording 04015, 450000 samples, channel 0,
250 Hz gives 2596 beats and 2595 RR intervals. The largest interval is 51064 ms, index 439 of the
raw series, between the beats at sample 71399 and sample 84165, that is 285.60 s to 336.66 s. That
is the interval the plan names. Two more intervals are above 3000 ms, 7824 ms at sample 84165 and
4856 ms at sample 175577. Six intervals are below 250 ms.

### 1.2 What the signal contains in that range

Three independent readings of the raw lead agree that the beat activity is not there in the lead
the chain consumes.

1. Per second maximum of the absolute signal of ECG1, the lead this chain consumes, over the 51
   seconds: 2.775, 2.33, 1.445, then 0.415, 0.635, 0.255, 0.52, and so on down to a floor of 0.10,
   and it only returns to 3.375 in the last second. Against this, the same statistic over the whole
   record has a median of 1.730 mV and a 5th percentile of 1.315 mV, so about 45 consecutive
   seconds sit below the 5th percentile of the record.
2. The other lead of the same record, ECG2, keeps 1.0 to 4.4 mV per second over exactly that
   stretch, at or above its own record median of 2.330 mV. The heart is beating; ECG1 is not
   carrying it. This is the signature of a contact loss, not of a cardiac pause.
3. The frozen reference detector, NeuroKit2 with the same Pan-Tompkins method the fixture's
   reference peak series came from, reports exactly one beat strictly inside those 51 seconds, at
   sample 84145, which is the beat that ends the gap.

### 1.3 What the threshold chain decided there, and why

The envelope peak picker passed 127 peaks to the threshold stage inside the gap. For every one of
them the verdict was "not signal", no second candidate was raised and the search back never armed.
The numbers, read from the real state of the stage:

| quantity inside the gap | measured | first threshold I1 there | second threshold I2 there |
|---|---|---|---|
| largest envelope value, at sample 81841 | 1795779 | 57524223 | 28762111 |
| median envelope over the 127 peaks | 260454 | record wide median envelope 145902581 | |

So the largest envelope excursion inside the gap is more than thirty times below even the second
threshold, and the median is about 560 times below the record wide median envelope. No decision sat
near a boundary. The rejection is not a threshold or a search back failure; there is no QRS scale
energy in that lead to reject or to accept.

### 1.4 Conclusion of the diagnosis, and a conflict with the plan that must be recorded

Fact. The 51064 ms defect is not caused by the phase 2 and phase 3 threshold chain. The chain is
faithful and silent because the lead it consumes has no beats in that stretch. The plan text says
the defect originates in the phase 2 and phase 3 threshold chain; for this interval that statement
is contradicted by the measurement above.

Fact. In the same run, a second interval has a different cause. The 4856 ms interval at samples
175577 to 176791 sits where ECG1 per second peaks are 4.005, 4.040, 3.845 and 2.495 mV, above the
record median, and NeuroKit reports two real beats strictly inside it, at samples 176582 and
176759, 177 samples apart, which is a plausible 708 ms interval. There the largest envelope value
inside is 68460041 against a first threshold of 142581193 and a second threshold of 71290596. That
is 4.0 percent below the second threshold, so the second candidate test `pv > i2` failed and the
search back never armed, and a beat that is present in the lead was lost by the detection path.
This is a genuine phase 3 threshold miss and it is reported here as a finding. It is NOT fixed in
S7, for two reasons: the plan allows exactly one change, and the change must follow the diagnosis
of the defect S7 targets, which is the 51064 ms interval, not this one.

Fact. The 7824 ms interval at samples 84165 to 86121 is the same lead loss event as the 51 second
one: ECG1 per second peaks fall from 3.38 to 0.44, 0.43, 0.55 mV, while NeuroKit reports no beat
inside it at all.

Hypothesis, not measured here. A repair of the detection path that would catch the two beats of the
4856 ms interval would have to move the arming rule of the second threshold or the search back
window. Either move changes the beat series `qrs` of the locked chain, which would make the frozen
fixture an oracle of a behaviour that no longer exists. That is a decision for Aviv, not for this
step, and it is left open.

## 2. The one change

Because the diagnosis says there is no beat to catch in the target range, no beat may be invented
and the detection path must not be loosened. The change is therefore in stage 7 only, as an integer
rhythm check over the raw interval series, written beside the locked series and not inside it.

Location. `model/rantai-afib-lite/rantai.py`, one block added after the locked `rr()` function
(stage 7b), one key added to `rr_awal()`, one call added in `_catat()` where every raw interval is
already appended, and four arrays added to `hasil()`. Nothing else in the file is touched.

The rules, in exact integer arithmetic, every ratio a cross multiplication:

1. An interval above 83/50 of the running average is a missed beat. The comparison is the cross
   form `50 * x > 83 * reference`, which is the form the phase 4 notebook already writes for the
   missed boundary in `lewat_missed`. The interval becomes two exact halves, `first = x >> 1` and
   `second = x - first`, so the two halves sum to the raw interval exactly.
2. An interval below 1/2 of the running average is a false detection. The exact cross form
   `2 * x < reference` removes it and it enters no average.
3. An interval that rule 1 catches and that is also above the absolute ceiling of 3000 ms is a
   recording gap, not a missed beat. It is marked as a gap, it stays in the corrected series as one
   entry instead of being split, and it is kept out of the running average.

The running average is the integer median of the last eight corrected intervals, computed with
`median_bulat`, the helper the file already carries. Choice, and why: a mean is dragged by exactly
the outlier this block exists to repair, and the file already holds an exact integer median; the
window length is `DELAPAN`, the length the locked stage already uses for its own average.

The marker, so a downstream window can tell a corrected interval from a raw one:

| mark | meaning |
|---|---|
| 0 | the raw interval was kept as it came |
| 1 | the raw interval was a missed beat and became two exact halves |
| 2 | the raw interval was a false detection and produced no entry |
| 3 | the raw interval was a recording gap, marked and kept out of the running average |

Exposed by `hasil()` as `rr_mark_raw` (one entry per raw interval, same length as `rr`),
`rr_corrected` and `rr_mark_corrected` (the corrected series and its own marks, same length as each
other), and `rr_rhythm_state` (the counters raw, kept, split, dropped, gap). The raw series `rr`
and every other locked array are not edited, so the frozen fixture keeps its meaning as the oracle
of the old behaviour and the change is provably additive.

## 3. Measured before and after on recording 04015

| quantity | before | after |
|---|---|---|
| raw intervals `rr` | 2595, longest 51064 ms, mean 693.2 ms | unchanged, byte for byte |
| corrected intervals `rr_corrected` | did not exist | 2983 entries, longest 51064 ms |
| longest interval not marked as a gap | 51064 ms was a physiological interval | 1112 ms |
| intervals marked as a recording gap | none | 3, namely 51064, 7824 and 4856 ms |
| intervals marked as a false detection | none | 9, between 200 and 304 ms, summing 2304 ms |
| intervals marked as a missed beat and split | none | 397 |
| rate implied by the series | 86.6 beats per minute | 99.6 beats per minute for the corrected series |
| beats `qrs` | 2596 | unchanged, byte for byte |
| every locked array | matches the fixture | matches the fixture, all 21 arrays the chain produces |
| keys added by this change | none | `rr_corrected`, `rr_mark_corrected`, `rr_mark_raw`, `rr_rhythm_state` |

Fact, and a limitation that must not be hidden. The missed beat rule fires on 397 of 2595 intervals
of this record, which is 15.3 percent, and it lifts the implied rate from 86.6 to 99.6 beats per
minute. The gate asks for no regression in sensitivity and specificity; those are measured on the
window layer, which is built from `qrs`, and `qrs` is unchanged, so the regression is zero by
construction and this is verified by rerunning the gates below.

Hypothesis, labelled as such. The canonical Pan-Tompkins missed beat rule presumes a reasonably
regular underlying rhythm, because it reads an interval above 83/50 of the average as a detection
that was missed rather than as a long pause. This record is atrial fibrillation, where the interval
series is irregular by nature and long intervals are real, so the rule over fires. Until Aviv rules
on it, a consumer should read the mark of an interval (mark 1 means a suspected missed beat) rather
than accept the split halves as beats, because the split invents a beat in the interval series even
though it never touches the beat series `qrs`.

## 4. What this step did not do

1. The fixture `fixture/04015_30m.npz` was not touched, was not refrozen, and its SHA-256 is still
   `91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d`.
2. No beat was added to or removed from the beat series. `qrs` is identical to the fixture over all
   450000 samples, so window features, window classes and the sensitivity and specificity numbers
   of the reference gate cannot move.
3. The 4856 ms detection miss of section 1.4 is reported and left open.
4. The corrected series is not yet consumed by the window decision layer. Wiring it in is a further
   change that S7 does not contain, and it would need Aviv's decision first, because the window
   layer builds its interval series from `qrs` and not from the RR stage at all.

## 5. The seven frozen gates, before and after, run unchanged

Every gate was run twice: once against a pristine copy of the whole folder taken before the change
(`rantai.py` at `9b2f6657...`), and once in the repository with the changed `rantai.py`. No gate file
was edited. The two lines that differ in the header of each run are the path of the fixture, which
is a consequence of running the before copy from a different directory, and wall clock times.

| gate | before | after | verdict |
|---|---|---|---|
| `uji_kesetaraan_s1.py` | exit 0, gate S1 PASS, every array identical | exit 0, gate S1 PASS, every array identical | unchanged, still passes |
| `uji_teorema.py` | exit 1, 8 pass 1 fail of 9, gate S3 FAIL | exit 1, 8 pass 1 fail of 9, gate S3 FAIL | unchanged. The single failure is T3, the derivative kernel peak claim at fs/6, which is a documented baseline condition of step S3, already ruled on by Aviv on 20 October 2026 with the kernel orientation kept. It is the same failing item with the same reason before and after, and it is not a regression |
| `uji_ekivalensi.py` | exit 0, 22 of 22 checks pass, gate S4 PASS | exit 0, 22 of 22 checks pass, gate S4 PASS | unchanged verdict. The array count moved from 21 to 25 core arrays because this gate fingerprints every key of `hasil()`, so the four new arrays are inside the digest. See 5.1 |
| `ambang_gerbang.py` | exit 0 | exit 0 | unchanged, pairs, sweep and accuracy identical |
| `uji_ambang_pool.py` | exit 0, 21 checks 21 pass, 1562 windows, 677 AFIB | exit 0, 21 checks 21 pass, 1562 windows, 677 AFIB | unchanged |
| `uji_kebijakan_ambang.py` | exit 0, 29 checks 29 pass, 6 points | exit 0, 29 checks 29 pass, 6 points | unchanged |
| `uji_referensi.py` | exit 0, 36 checks 36 pass | exit 0, 36 checks 36 pass | unchanged |

No gate goes from pass to fail. No gate that failed before passes now.

### 5.1 The only numbers that moved, and why

1. `uji_ekivalensi.py`: "21 core arrays" became "25 core arrays", the per path SHA-256 digests
   changed with it, the combined fingerprint changed from `970186083f826a69b289eacabb0cd5f5...` to
   `4c9554f1be752a257992330294eb2c29...`, and the elementwise comparison went from 144 arrays and
   24511309 elements to 168 arrays and 24562703 elements. This is expected and correct: that gate
   fingerprints every key the chain returns, so adding four arrays changes the digest of the run by
   definition. Its own requirements still hold, including A equal to B across two separate
   processes.
2. `uji_referensi.py` check [22]: "21 core arrays compared, differing 0" became "25 core arrays
   compared, differing 0". The count of arrays compared moved; the number that matters, zero
   differing, did not.
3. Wall clock lines everywhere, which are not gates.

Sensitivity and specificity did not move anywhere. The reference gate prints, before and after and
unchanged to the last digit: afdb/04043 767 windows including 192 AFIB, sensitivity 89.58,
specificity 100.00, accuracy 97.39; afdb/04126 795 windows including 485 AFIB, 86.80, 73.55, 81.64;
nsrdb/16265 specificity 100.00 with zero AFIB windows; mitdb/100 not measurable for windows. Beat
counts per record are identical: 2596 on 04015, 3223 on 04043, 3399 on 04126, 2765 on 16265, 2264
on 100.

## 6. The phase 2 and phase 3 notebooks, run once

Both notebooks were executed to a copy in a scratch directory with `jupyter nbconvert --execute`.
Neither file in the repository was written, and neither file's source was touched.

    phase 2  squaring-and-moving-window-integrator-equation.ipynb
    phase 3  adaptive-threshold-equations.ipynb

Result, both notebooks: 0 cells with an error output, 0 cells whose source differs, and every
printed text output of every code cell identical to the text already stored in the repository
notebook, cell for cell. No printed number moved.

Fact about this result, so it is not overread. These two notebooks are the source of truth for the
arithmetic and they do not import `rantai.py`, so this change cannot reach them by construction.
Running them once was done because the plan asks for it, and it confirms that the numbers recorded
in the vault for phase 2 and phase 3 still reproduce on this machine.

## 7. Audit trail

| artifact | value |
|---|---|
| `rantai.py` before | `9b2f66572db524d503013241034443e7b32967b1ad04b348d5514aed46e62c50`, 877 lines |
| `rantai.py` after | `4bd63a1174585712eebda2a50f6f0c9a5784e97ea791adc1152f5b8afddfef9b`, 1014 lines |
| RR series before the rhythm check | `fixture/rr_gap_before_04015.txt`, `8d6fd98a177d17301a10af55575c6884b81bc5975a9b14884790e8bbfa16f768`, 2595 intervals, one line each, with the raw mark per interval |
| RR series after the rhythm check | `fixture/rr_gap_after_04015.txt`, `80cb7f985b3c600ec5956f002d886fcc7da99867987ba8a950c4ee1e0ff0b7c2`, 2983 corrected entries with their own mark |
| the gate of this step | `uji_jeda_rr.py`, `b5f25fa2ffbf8b0bcf851a0645966889f80bfef7cec474377b342faf3950d73b`, 439 lines, 19 of 19 items pass |
| this note | `S7_OPEN_CORRECTION_NOTE.md`, its own SHA-256 is reported in the run log of S7, because a file cannot carry its own hash |

The two RR series files are written from one run of the chain over recording 04015: the raw series
is `hasil()["rr"]`, its marks are `hasil()["rr_mark_raw"]`, the corrected series is
`hasil()["rr_corrected"]` and its marks are `hasil()["rr_mark_corrected"]`. The corrected series is
reproducible from the frozen raw series alone, and `uji_jeda_rr.py` check F2 reconstructs it that
way and compares it element for element.

### 7.1 Frozen files that were not changed

`acuan_fase.py`, `adapter.py`, `simulator_attys.py`, `ambang_gerbang.py`, `s0_bekukan_acuan.py`,
`periksa_verbatim.py`, `uji_adapter.py`, `uji_ambang_pool.py`, `uji_ekivalensi.py`,
`uji_kebijakan_ambang.py`, `uji_kesetaraan_s1.py`, `uji_referensi.py`, `uji_teorema.py`,
`TASK_BRIEF.md`, `fixture/04015_30m.npz` at
`91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d`, every file under
`fixture/attys/`, `fixture/pembanding_inisialisasi_fase3.txt`, `fixture/sidik_jari.txt`, and the
seven notebooks under `model/math-equation-afib/`. Their SHA-256 values are in the run log of this
step. Nothing was committed and nothing was staged.

## 8. What is left open for Aviv

1. Whether the corrected series should be consumed by the window decision layer. It is not
   consumed today, and the window layer builds its intervals from `qrs` and not from the RR stage.
2. What reading of the missed beat mark to keep. Mark 1 with the split halves is the literal
   reading the step asks for, and the measurement in section 3 says it over fires in atrial
   fibrillation. Reading the mark and discarding the split halves is available and auditable from
   the same arrays.
3. The 4856 ms detection miss of section 1.4, which needs a change in the threshold arming rule and
   would move the beat series.
4. Whether to refreeze the fixture. This step did not, so the fixture remains the oracle of the
   behaviour before the change only.

