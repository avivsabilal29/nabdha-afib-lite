// ---------------------------------------------------------------------------
// afib_lite_pkg.sv -- the single place where a number lives.
//
// Plan of record: vault doc 38 "Rencana Implementasi RTL End to End", section 3.4
// (package SystemVerilog and file layout) plus section 13.3 (owner decisions of
// 20 October 2026). Cross checked against vault doc 36 "Rencana Port Model ke RTL",
// section 2.2 (measured node widths, frozen fixture 04015), 2.2.1 (binding widths
// over three records) and 5.5 (binding feature widths over three source arms).
//
// House rules that bind this file (rtl/README.md, rtl/TASK_BRIEF.md, plan 2.6):
//   - English identifiers and comments, ASCII only, no em dash, no en dash.
//   - One clock, synchronous active low reset, no vendor primitives, no latches,
//     no initial blocks outside testbenches.
//   - No module may state a width, a threshold, a shift or a buffer length that is
//     not declared here. Every module parameter default is written as
//     afib_lite_pkg::NAME, never as a bare number (plan 3.4, contract I1 rule 2).
//
// Model term translation, once, here (plan 2.6 rule): the model says "kelas" for the
// triage class, so the enum keeps the plan's own type name kelas_e and its members
// carry the English names KELAS_UNDECIDED, KELAS_NORMAL, KELAS_REVIEW.
//
// Frozen owner decisions applied in this file:
//   D1  no tready inside the datapath, fixed latency per stage, one overflow flag
//       per stage feeding STATUS, s_ready at the top level only.
//   D2  class encoding 0 undecided, 1 normal, 2 review, reset value 0.
//       rtl-synthesis/template/design_template.sv:31 writes class 1 as atrial
//       fibrillation and CONTRADICTS D2. It is flagged, not silently changed.
//   D2b confidence is a 0 to 1000 scale, not a standard deviation.
//   D10 wire and reg in synthesised files, logic inside testbenches only.
//   D12 rate divider field is 20 bit.
//   D8  register reset values carry the locked triage operating point P1.
//
// Group index of this file, in the order plan 3.4 lists it:
//   1 bit widths          2 saturation points        3 rounding rules
//   4 types and enums     5 reset operating point values
//   6 interface bit map, transcribed from the 43 row signal table (see below)
//   7 width cross check against doc 36 section 2.2 and 5.5
// ---------------------------------------------------------------------------
`ifndef AFIB_LITE_PKG_SV
`define AFIB_LITE_PKG_SV

`default_nettype none

package afib_lite_pkg;

  // ===========================================================================
  // Group 1. Bit widths. Plan doc 38 section 3.4, value list row 1.
  // ===========================================================================
  localparam int unsigned W_IN        = 16;  // Q12.4 locked input word       [36 2.2]
  localparam int unsigned W_LP        = 22;  // Q18.4 low-pass node           [36 2.2]
  localparam int unsigned W_LP_ACC    = 23;  // |2*y1| = 2358144 accumulator, bounds only [38 13.5]
  localparam int unsigned W_HP_ACC    = 27;  // |32*x16| = 37730304 accumulator, bounds only [38 13.5]
  localparam int unsigned W_HP        = 26;  // Q22.4 high-pass node          [36 2.2]
  localparam int unsigned W_DER       = 24;  // Q17.7 derivative node         [36 2.2]
  localparam int unsigned W_DER_WORST = 25;  // signed bound of +-14464656    [38 4.4, TASK_BRIEF 3]
  localparam int unsigned W_SQ        = 30;  // square node, 29 unsigned      [36 2.2]
  localparam int unsigned W_SQ_WORST  = 32;  // SQ_LIMIT^2 = 3192589009 unsigned, bounds only [38 13.4]
  localparam int unsigned W_WIN       = 33;  // window node, 32 unsigned      [36 2.2]
  localparam int unsigned W_WIN_WORST = 37;  // 38 * SQ_LIMIT^2 = 121318382342, magnitude convention [36 2.4]
  localparam int unsigned W_THR       = 30;  // adaptive threshold and search back [36 2.2.1]
  localparam int unsigned W_TW        = 23;  // T-wave slope, 22 unsigned     [36 2.2]
  localparam int unsigned W_RR_MS     = 16;  // milliseconds, worst record    [36 2.2, 2.2.1]
  localparam int unsigned W_RR_SMP    = 15;  // search-back distance in samples [TASK_BRIEF 2.1], design choice not measured
  localparam int unsigned W_CONF      = 16;  // confidence word               [38 3.2, D2b]
  localparam int unsigned W_F_RATIO   = 17;  // Q1.16 ratio feature           [36 5.5]
  localparam int unsigned W_F_ENT     = 15;  // Q1.14 entropy divided by four [36 5.5]
  localparam int unsigned W_F_MEANQ   = 27;  // Q19.8 sum of 31 squares / 31  [36 5.4, 5.5]
  localparam int unsigned W_F_RMSSD   = 18;  // Q10.8 root of the mean square [36 5.5]
  localparam int unsigned W_IDX       = 32;  // absolute sample index         [38 3.2]
  localparam int unsigned W_RATE_DIV  = 20;  // D12: 399999 needs 19 bit      [36 3.1]
  localparam int unsigned W_TUSER     = 8;   // marker vector                 [38 3.2]

  // ===========================================================================
  // Group 2. Saturation points. Plan doc 38 section 3.4, value list row 2.
  // Values that live in a register field are declared at the width of that field,
  // so nothing is truncated silently when they are loaded (a 32 bit constant into a
  // 20 bit divider field is a lint warning, and lint warnings are hard failures here).
  // ===========================================================================
  localparam int signed            CLAMP_COUNT       = 2047;   // count clamp, 12 significant bit [36 2.1]
  localparam int unsigned          SHIFT_IN          = 4;      // locked word is left justified by four
  localparam int signed            CLAMP_WORD        = 32752;  // 2047 << 4, largest legal input word [36 2.1]
  localparam int signed            SQ_LIMIT          = 56503;  // ceil(14464656 / 2**8), |d| bound of the square node
  localparam logic [W_SQ_WORST-1:0] SQ_SAT           = 1073741823; // 2**30-1, square stage saturates here and raises the flag [38 13.4, Aviv 20 Oct]
  localparam int unsigned          SHIFT_DER         = 8;      // right shift between derivative and square
  localparam int unsigned          THRESH_SCALE      = 256;    // 2**SHIFT_DER, threshold scale factor
  localparam int unsigned          N_WIN             = 38;     // running window, 37 and 38 alternating [38 4.6]
  localparam int unsigned          N_WIN_ALT         = 37;     // the short window of the alternating pair
  localparam logic [W_RR_MS-1:0]   RR_LONG_MS        = 3000;   // long interval ceiling, stored whole and marked GAP
  localparam logic [W_RR_MS-1:0]   RR_MAX_MS         = 65535;  // full W_RR_MS width; clamping to 13 bit is forbidden
  localparam int unsigned          GAP_RECOVERY      = 131;    // 12+32+4+38+27+18 samples = 524 ms at 250 Hz [36 3.6]
  localparam logic [W_RATE_DIV-1:0] RATE_DIV_RST     = 399999; // terminal count, 100e6 / 400000 = 250.0 Hz [36 3.1]
  localparam int unsigned          SEARCH_BACK_DEPTH = 128;    // candidate buffer, needs its own overflow flag, design choice not measured
  localparam int unsigned          DECISION_DEPTH    = 8;      // decision output buffer, design choice not measured
  localparam int unsigned          CONF_FULL_SCALE   = 1000;   // confidence full scale, D2b

  // Fase 2 addition, plan doc 38 section 4.1, added by the acquisition phase. The input
  // quantiser needs the divisor 1000 and no other constant in this file can supply it, so
  // it is declared here instead of typed into the module, which is the rule of this file.
  // It is derived and not typed: the model gain is (2**11 - 1) / 5 counts per mV
  // (rantai.py:49) and the frozen fixture header carries the WFDB default gain of 200
  // counts per mV (adapter.py:90, a declared gain of 0 means 200.0), so
  //   pre = rint(c * CLAMP_COUNT / Q_DIVISOR) = rint(mV * GAIN_COUNT)
  // is the same arithmetic in the count domain as the model does in the millivolt domain.
  localparam int unsigned          MV_FULL_SCALE     = 5;      // locked plus minus 5 mV [rantai.py:49]
  localparam int unsigned          REC_GAIN_MV       = 200;    // record gain, counts per mV [adapter.py:90]
  localparam int unsigned          Q_DIVISOR         = MV_FULL_SCALE * REC_GAIN_MV;  // 1000, plan 38 4.1

  // ===========================================================================
  // Group 3. Rounding rules. Plan doc 38 section 3.4, value list row 3.
  // The three rules coexist on purpose and must never be unified (doc 36 2.3).
  // ===========================================================================
  // RND_TIES_EVEN   quantiser only, np.rint, rounds half to even  [rantai.py:163]
  // RND_FLOOR       every other right shift, arithmetic shift      [rantai.py:244, :655, :683]
  // RND_TRUNC_ZERO  derivative stage only, keeps the kernel antisymmetric [rantai.py:228]

  // ===========================================================================
  // Group 4. Types and enumerations. Plan doc 38 section 3.4, value list row 4.
  // ===========================================================================
  typedef logic [W_IN-1:0]        word_in_t;  // locked input word, Q12.4
  typedef logic signed [W_LP-1:0] lp_t;       // Q18.4
  typedef logic signed [W_HP-1:0] hp_t;       // Q22.4
  typedef logic signed [W_DER-1:0] der_t;     // Q17.7
  typedef logic signed [W_SQ-1:0] sq_t;       // count squared after the shift of 8
  typedef logic signed [W_WIN-1:0] win_t;     // running window of 38
  typedef logic signed [W_THR-1:0] thr_t;     // Q29.0 adaptive threshold and search back
  typedef logic [W_RR_MS-1:0]     rr_ms_t;    // RR interval in milliseconds, Q16.0
  typedef logic [W_IDX-1:0]       idx_t;      // absolute sample index
  typedef logic [W_TUSER-1:0]     tuser_t;    // marker vector
  typedef logic [W_CONF-1:0]      conf_t;     // confidence, 0 to CONF_FULL_SCALE

  // Triage class. D2: 0 undecided, 1 normal, 2 review, reset value 0.
  // The frozen fixture stores a label string, not a code, so the mapping used on
  // export is 'N' -> KELAS_NORMAL and 'AFIB' -> KELAS_REVIEW. KELAS_UNDECIDED is
  // the reset value, so a register that was never written can never read as normal.
  typedef enum logic [1:0] {
    KELAS_UNDECIDED = 2'd0,
    KELAS_NORMAL    = 2'd1,
    KELAS_REVIEW    = 2'd2
  } kelas_e;

  // Event sideband kinds, one cycle each. Plan doc 38 section 3.2, row m_ev_kind.
  typedef enum logic [2:0] {
    EV_NONE      = 3'd0,  // no event
    EV_QRS       = 3'd1,  // accepted beat at this index
    EV_PEAK_CAND = 3'd2,  // candidate peak kept for the search-back walk
    EV_RR        = 3'd3,  // interval closed, value in milliseconds
    EV_WINDOW    = 3'd4,  // decision window closed
    EV_GAP       = 3'd5   // lost sample observed
  } ev_kind_e;

  // Rounding selector. Values are the group 3 rules, in the order plan 3.4 lists them.
  typedef enum logic [1:0] {
    RND_TIES_EVEN  = 2'd0,
    RND_FLOOR      = 2'd1,
    RND_TRUNC_ZERO = 2'd2
  } rnd_e;

  // RR interval marks, four values, all four must reach the register map [36 2.7].
  typedef enum logic [1:0] {
    RR_MARK_KEEP  = 2'd0,  // raw interval used as it stands
    RR_MARK_SPLIT = 2'd1,  // missed beat, split into two exact halves
    RR_MARK_DROP  = 2'd2,  // false detection, produces no entry
    RR_MARK_GAP   = 2'd3   // recording gap, marked and kept out of the mean
  } rr_mark_e;

  // ===========================================================================
  // Group 5. Reset operating point values. Plan doc 38 section 3.4, row 5, and
  // section 13.3 D8. These reset values make the part come out of reset equal to
  // the locked triage operating point P1 (0.165 and 0.63) with all four arms lit.
  // ===========================================================================
  localparam logic [15:0] RATIO_THRESH_RST   = 16'd33;   // 1/200 units, 33 is 0.165
  localparam logic [15:0] ENTROPY_THRESH_RST = 16'd63;   // 1/100 units, 63 is 0.63
  localparam logic [4:0]  ARM_SELECT_RST     = 5'h0F;    // ratio, entropy, T-wave rule, marked series
  // CLK_HZ is not one of the four plan 3.4 groups and not part of D8 either. It is kept
  // here because RATE_DIV_RST is meaningless without it: 399999 is a terminal count, and
  // the 250.0 Hz it produces only follows from the 100 MHz PL clock of doc 36 3.1 and
  // doc 39 7.2 (apply_board_preset "1" gives pl_clk0 100 MHz). Declaring it here keeps the
  // testbench free of a bare 100000000, which is the whole point of this file.
  localparam int unsigned CLK_HZ = 100_000_000;  // PL clock, doc 36 3.1

  // ===========================================================================
  // Group 6. Interface bit map, transcribed from the 43 row signal table below.
  // Not part of the plan 3.4 parameter groups; added so no module writes a bare
  // bit position. Sources are the table rows s_tuser, m_ev_kind and the D5 lock.
  // ===========================================================================
  localparam int unsigned W_EVKIND      = 3;  // m_ev_kind width, table row m_ev_kind
  localparam int unsigned TU_CLAMP      = 0;  // s_tuser bit 0, clamp marker, set strictly above CLAMP_COUNT
  localparam int unsigned TU_GAP        = 1;  // s_tuser bit 1, this sample follows a lost sample
  localparam int unsigned TU_WEAK       = 2;  // s_tuser bit 2, weak signal over the last second
  localparam int unsigned TU_UNSURE     = 3;  // s_tuser bit 3, quality undecided
  localparam int unsigned WINDOW_BEATS_RST  = 32;  // D5 lock: decision window length in beats
  localparam int unsigned WINDOW_STEP_RST   = 4;   // D5 lock: window stride in beats
  localparam logic [7:0]  WINDOW_STEP_FIELD = 8'd4;  // the same value at the register field width
  localparam logic [7:0]  WINDOW_BEATS_FIELD= 8'd32; // the same value at the register field width

  // ===========================================================================
  // Signal table, contract I1, 43 rows. Plan doc 38 section 3.2, lines 378 to 420.
  // Every row below carries the marker "// TBL|" and the block ends at "// TBL-END",
  // so the row count is machine checkable inside this file:
  //   grep -c '^  // TBL|' rtl/afib_lite_pkg.sv    ->  must print 43
  // Columns: group | name | direction | width | semantics | when valid
  // Group totals from plan 3.2: 2 clock and reset, 6 sample in, 6 sample out,
  // 4 event, 2 introspection, 6 decision, 8 status, 9 configuration. Sum 43.
  // ===========================================================================
  // TBL| clock   | clk_i           | in         | 1                        | the only clock, 100 MHz on the KV260 | always
  // TBL| clock   | rst_ni          | in         | 1                        | synchronous reset, active low | every register returns to its reset value on the first edge
  // TBL| sample  | s_tdata         | in         | W_IN = 16                | one ECG sample, Q12.4, 12 significant bits shifted left four, so the contract width is 16 | while s_tvalid and s_ready are high
  // TBL| sample  | s_tvalid        | in         | 1                        | one valid word is present this cycle | held high until accepted
  // TBL| sample  | s_ready         | out        | 1                        | the top level can accept a sample | top level only; inner stages have no back pressure (D1)
  // TBL| sample  | s_tlast         | in         | 1                        | end of the evaluation window | only on a valid word cycle
  // TBL| sample  | s_tuser         | in         | W_TUSER = 8              | quality vector, bits 3 to 0 used: clamp, gap, weak, undecided | sticks to the same word
  // TBL| sample  | s_sample_idx    | in         | W_IDX = 32               | absolute sample index since reset, the PL time base | same as the s_tdata it accompanies
  // TBL| sample  | m_tdata         | out        | per stage, see group 7   | one result word of this stage | while m_tvalid is high, fixed latency
  // TBL| sample  | m_tvalid        | out        | 1                        | one valid word is available | only after the word reaches the output register
  // TBL| sample  | m_overflow      | out        | 1                        | overflow of this stage | sticky until read; routed to STATUS at the top level
  // TBL| sample  | m_tlast        | out        | 1                        | window boundary forwarded verbatim | together with m_tdata
  // TBL| sample  | m_tuser         | out        | W_TUSER = 8              | marker vector forwarded verbatim | a stage may not add or drop a bit
  // TBL| sample  | m_sample_idx    | out        | W_IDX = 32               | index of the word being processed | together with m_tdata
  // TBL| event   | m_ev_valid      | out        | 1                        | one event this cycle | high for one cycle
  // TBL| event   | m_ev_kind       | out        | W_EVKIND = 3             | 0 none, 1 QRS beat, 2 peak candidate, 3 RR interval, 4 decision window, 5 lost sample | with m_ev_valid
  // TBL| event   | m_ev_idx        | out        | W_IDX = 32               | sample index at which the event happened | with m_ev_valid
  // TBL| event   | m_ev_val        | out        | 32                       | peak amplitude, RR length in milliseconds, or interval count | with m_ev_valid
  // TBL| intro   | d_valid         | out        | 1                        | introspection data of this stage is valid | follows m_tvalid unless stated otherwise
  // TBL| intro   | d_<node>        | out        | node width, doc 36 2.2   | one port per node per stage; the caller must read it | together with d_valid
  // TBL| decide  | m_dvalid        | out        | 1                        | one decision window is available | one cycle per window
  // TBL| decide  | m_class         | out        | 2                        | 0 undecided, 1 normal, 2 review (D2) | with m_dvalid
  // TBL| decide  | m_conf          | out        | W_CONF = 16              | confidence, 0 to CONF_FULL_SCALE 1000, distance to the binding threshold (D2b) | with m_dvalid
  // TBL| decide  | m_win_idx       | out        | W_IDX = 32               | decision window index | with m_dvalid
  // TBL| decide  | m_rr_last       | out        | W_RR_MS = 16             | last RR interval in milliseconds | after the first two beats
  // TBL| decide  | m_rr_mark       | out        | 2                        | series mark: 0 keep, 1 split, 2 drop, 3 gap | with m_rr_last
  // TBL| status  | o_sample_idx    | out        | 32                       | sample counter since reset | always
  // TBL| status  | o_beat_count    | out        | 32                       | beats accepted since reset | always
  // TBL| status  | o_gap_count     | out        | 32                       | lost sample events since reset, counted from the marker bit | always
  // TBL| status  | o_clamp_count   | out        | 32                       | clamped samples since reset | always
  // TBL| status  | o_window_count  | out        | 32                       | finished decision windows since reset | always
  // TBL| status  | o_rr_long_count | out        | 32                       | intervals above RR_LONG_MS since reset | always
  // TBL| status  | o_irq           | out        | 5                        | interrupt sources: window done, gap, clamp, FIFO overflow, long interval | high while its source is active
  // TBL| status  | o_dbg_val       | out        | 32                       | introspection word selected by i_dbg_sel | with o_dbg_valid
  // TBL| config  | i_rate_div      | in         | W_RATE_DIV = 20          | rate counter terminal count; 399999 gives 250.0 Hz (D12) | always
  // TBL| config  | i_enable        | in         | 1                        | allows the chain to advance | always
  // TBL| config  | i_clear_counters| in         | 1                        | clears the status counters | one cycle pulse
  // TBL| config  | i_ratio_thresh  | in         | 16                       | ratio arm threshold in 1/200 units; 33 is 0.165 | always
  // TBL| config  | i_entropy_thresh| in         | 16                       | entropy arm threshold in 1/100 units; 63 is 0.63 | always
  // TBL| config  | i_arm_select    | in         | 5                        | active arms: b0 ratio, b1 entropy, b2 T-wave rule, b3 marked series, b4 both arms required | always
  // TBL| config  | i_window_step   | in         | 8                        | window stride in beats | always
  // TBL| config  | i_window_beats  | in         | 8                        | decision window length in beats | always
  // TBL| config  | i_dbg_sel       | in         | 8                        | introspection node selector | temporarily a port, becomes a register after D8 lands
  // TBL-END

  // ===========================================================================
  // Group 8. Fase 5 additions. Every entry is a NEW name. No value of group 1 to
  // group 7 is modified, and the frozen ev_kind_e members keep their codes, so
  // tb_pkg_konstanta.sv keeps its 68 checks. The source of every number is the
  // frozen model itself (model/rantai-afib-lite/rantai.py, sha256 90df6e5b457307d3):
  //   :55   RADIUS_PUNCAK 27      envelope peak picker radius
  //   :56   JENDELA_F 25          half window of the filtered peak
  //   :57   PANTUL 50             refractory gate, 200 ms at 250 Hz
  //   :58   PITA_MS_ATAS 360      upper edge of the T wave band, in milliseconds
  //   :59   SETENGAH_JENDELA 18   half window of the slope, 37 samples
  //   :62   DELAPAN 8             RR averaging queue length
  //   :63   SEMAI_PANJANG 32      RR history that feeds the reseed median
  //   :64   SEMAI_JEDA 8          reseeding is allowed once per eight beats
  //   :933  GarisTunda(64)        ring depth of the three streaming rings
  //   :655  i1 = npki + ((spki - npki) >> 2)
  //   :656  f1 = npkf + ((spkf - npkf) >> 2)
  //   :657  i2 = i1 >> 1
  //   :683  spki += (pv - spki) >> 3
  //   :709  spki += (v - spki) >> 2, the search back update
  //   :399  ra1 = sum(deret 8) >> 3
  //   :359  the exact in band test of the RR stage, cross multiplied by 25
  //   :628  250 <= rr_ms <= 2000 selects the intervals the RR stage consumes
  //   :581  the search back gate, 200 * delta * penyebut > 83 * pembilang
  //   :339  (delta << 2) < 360, exact because 1000 / 250 is 4
  // Two peak verdicts of rantai.ambang have no code in the frozen ev_kind_e, so
  // they are declared here as plain localparams at the m_ev_kind width instead of
  // extending the enumeration: EV_REJECTED_T 6 and EV_NOISE 7.
  // The two accumulator widths are not plan numbers either. They are the smallest
  // signed width that holds the measured extremes: spki reaches 717628984, which
  // needs 30 unsigned bits and therefore does not fit the signed W_THR port, and
  // the difference pv - spki spans the 32 unsigned bit window node plus a sign bit.
  // ===========================================================================
  localparam int unsigned PEAK_RADIUS      = 27;   // :55
  localparam int unsigned PEAK_HALF_WIN    = 25;   // :56
  localparam int unsigned PEAK_WIN_WORDS   = 2 * PEAK_RADIUS + 1;  // 55, the max window
  localparam int unsigned PEAK_RING_WORDS  = 64;   // :933, GarisTunda(64)
  localparam int unsigned PEAK_BUF_DEPTH   = SEARCH_BACK_DEPTH;    // 128, group 2
  localparam int unsigned PEAK_LAT_SAMPLE  = 128;  // cycles per accepted word, this stage
  localparam int unsigned PANTUL           = 50;   // :57
  localparam int unsigned PITA_MS_ATAS     = 360;  // :58
  localparam int unsigned SETENGAH_JENDELA = 18;   // :59
  localparam int unsigned DELAPAN          = 8;    // :62
  localparam int unsigned SEMAI_PANJANG    = 32;   // :63
  localparam int unsigned SEMAI_JEDA       = 8;    // :64
  localparam int unsigned SHIFT_I1         = 2;    // :655
  localparam int unsigned SHIFT_I2         = 1;    // :657
  localparam int unsigned SHIFT_SPKI       = 3;    // :683
  localparam int unsigned SHIFT_SB         = 2;    // :709
  localparam int unsigned SHIFT_RA1        = 3;    // :399
  localparam int unsigned SB_BAND_SHIFT    = 2;    // :339
  localparam int unsigned RR_BAND_NUM      = 25;   // :359
  localparam int unsigned RR_BAND_LO       = 23;   // :359
  localparam int unsigned RR_BAND_HI       = 29;   // :359
  localparam int unsigned RR_BAND_MIN_MS   = 250;  // :628
  localparam int unsigned RR_BAND_MAX_MS   = 2000; // :628
  localparam int unsigned SB_GATE_DELTA    = 200;  // :581, 200 * delta * penyebut
  localparam int unsigned SB_GATE_AVERAGE  = 83;   // :581, > 83 * pembilang
  localparam int unsigned W_THR_ACC        = W_THR + 1;  // 31, signed spki/npki accumulator
  localparam int unsigned W_WIN_ACC        = W_WIN + 1;  // 34, signed pv - spki difference
  // W_SB 30 is the item plan 12.0.7 lists as still missing ("Belum ada parameter lebar
  // untuk kata penelusuran balik ... Tambah W_SB 30 ke paket sekarang, sebelum modul
  // peak_detect.sv diisi aritmetika"). Doc 36 2.2.1 is the source of the 30. It equals
  // W_THR, but it is a separate name because it is a separate node: the model's search
  // back word range is (34794360, 145902581) and its accepted candidates satisfy v <= i1,
  // which never reaches 2**28, so narrowing an accepted candidate to 30 bits is exact.
  localparam int unsigned W_SB             = 30;   // search back word, doc 36 2.2.1
  localparam int unsigned W_RR_SUM         = 20;   // 8 * RR_MAX_MS 65535 = 524280
  localparam int unsigned W_RR_PROD        = 32;   // 29 * 524280 = 15204120
  localparam int unsigned W_SB_PROD        = 32;   // 200 * delta * penyebut
  localparam int unsigned SB_DELTA_GUARD   = 20;   // delta above 2**20 makes :581 true for any average
  localparam logic [W_EVKIND-1:0] EV_REJECTED_T = 3'd6;  // a T wave rule verdict, no code in ev_kind_e
  localparam logic [W_EVKIND-1:0] EV_NOISE      = 3'd7;  // neither threshold accepted it

  // ===========================================================================
  // Group 7. Width cross check, plan doc 38 section 3.4 against doc 36.
  // Two columns: the package name used in this file, and the measured value in
  // doc 36 section 2.2 (frozen fixture 04015) with the binding value of 2.2.1 and
  // 5.5 where one exists. Where the two documents differ, the note says so.
  //   node       package name          doc 36 measured        binding      status
  //   input      W_IN    = 16          16                     16           agree
  //   lp         W_LP    = 22          22                     22           agree
  //   hp         W_HP    = 26          26                     26           agree
  //   derivative W_DER   = 24          24                     24           agree
  //   derivative W_DER_WORST = 25      no name in doc 36      TASK_BRIEF 3 "25" agree, signed convention
  //   square     W_SQ    = 30          30 signed, 29 unsigned 30           agree
  //   window     W_WIN   = 33          33 signed, 32 unsigned 33           agree
  //   window     W_WIN_WORST = 37      doc 36 2.4 says "37 bit" for the same 121318382342
  //                                    value, which is the magnitude width. A strict
  //                                    two's-complement reading needs 38. DISAGREEMENT,
  //                                    reported, not resolved silently.
  //   threshold  W_THR   = 30          29 on 04015            30 on nsrdb/16265  agree with the binding value
  //   searchback W_THR   = 30          29 on 04015            30 on nsrdb/16265  agree with the binding value
  //   T-wave     W_TW    = 23          23                     23           agree
  //   rr ms      W_RR_MS = 16          12 on 04015, 16 worst  16           agree
  //   rr samples W_RR_SMP= 15          not in doc 36          TASK_BRIEF 2.1 15  agree
  //   confidence W_CONF  = 16          not in doc 36          38 3.2, D2b 16    agree
  //   feature    W_F_RATIO = 17        doc 36 5.4 says 9      17 in 5.5, pinned agree with the binding value
  //   feature    W_F_ENT   = 15        doc 36 5.4 says 9      15 in 5.5          agree with the binding value
  //   feature    W_F_MEANQ = 27        27                     27                 agree
  //   feature    W_F_RMSSD = 18        doc 36 5.4 says 14      18 in 5.5          agree with the binding value
  //   index      W_IDX   = 32          not in doc 36          38 3.2             agree
  //   rate       W_RATE_DIV = 20       doc 36 3.1 says 20 bit 20, D12            agree
  //   marker     W_TUSER = 8           38 3.2                 8                  agree
  // Only one disagreement exists between plan 3.4 and doc 36: the convention behind
  // W_WIN_WORST. Every other value agrees, and where doc 36 carries two numbers the
  // package follows the binding one (2.2.1 for the threshold, 5.5 for the features).
  // ===========================================================================

endpackage

`default_nettype wire

`endif
