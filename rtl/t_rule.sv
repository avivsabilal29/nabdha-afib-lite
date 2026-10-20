// ---------------------------------------------------------------------------
// t_rule.sv -- T-wave discrimination rule. Contract profile: stream stage (I1), with one
// documented stage-local output that the 43 row table has no row for.
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). This file is the recommended addition from plan 3.4 ("add one t_rule.sv
// file for the T-wave rule so its testbench has its own file"), so its ports are the
// stream stage ports plus o_reject described below.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2):
//   in   W_DER = 24   Q17.7, the derivative magnitude line this rule scans
//   out  W_TW  = 23   Q16.7, signed, 22 unsigned; measured range [12926, 3995970]
// Saturation points: the rule compares two magnitudes, so it saturates only at the
//   magnitude rail. PITA_MS_ATAS 360 is the in-band ceiling and SETENGAH_JENDELA 18 is
//   the half window, so the scan is over 2*18+1 = 37 values. Those two model constants
//   are not package items in plan 3.4 and stay as local constants in this file until
//   Fase 7 owns them.
// Rounding rule: RND_FLOOR where the shift appears (delta << 2 is exact because
//   1000/250 = 4). The rejection test is the exact cross form 2*kem < kem_qrs; the
//   algebraically similar kem < (kem_qrs >> 1) is FORBIDDEN because the two differ on
//   2048 of 16777216 grid points (doc 36 2.4), so it must never be rewritten.
// Model lines this file mirrors: rantai.py:313-341, scan at :333, in-band test at :339,
//   cross form at :340, SETENGAH_JENDELA 18 at :59, PITA_MS_ATAS 360 at :58.
//
// o_reject is new and is flagged as such: the 43 row signal table has no row for the
// T-wave rejection flag, while plan 4.10 requires the rule to exist. It is exposed here
// as a stage-local output that peak_detect consumes and STATUS records, and it is sent to
// the owner as a question rather than added to the contract silently.
//
// Fixed latency: 37 cycles per peak for the serial scan. Placeholder uses one cycle.
//
// Fase 1 status: PLACEHOLDER. The body narrows the derivative word into the output
// register with a fixed latency and never rejects. Ports and widths are frozen.
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module t_rule #(
    parameter int unsigned W_DER      = afib_lite_pkg::W_DER,
    parameter int unsigned W_TW       = afib_lite_pkg::W_TW,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned LAT_CYCLES = 1
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // sample stream in
    input  wire [W_DER-1:0]         s_tdata,
    input  wire                     s_tvalid,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,
    input  wire [W_IDX-1:0]         s_sample_idx,

    // configuration: b2 of i_arm_select enables this rule, carried in by the caller
    input  wire                     i_rule_enable,

    // sample stream out
    output reg  [W_TW-1:0]          m_tdata,
    output reg                      m_tvalid,
    output reg                      m_overflow,
    output reg                      m_tlast,
    output reg  [W_TUSER-1:0]       m_tuser,
    output reg  [W_IDX-1:0]         m_sample_idx,

    // stage-local T-wave rejection flag, see the header
    output reg                      o_reject,

    // introspection
    output reg                      d_valid,
    output reg  [W_TW-1:0]          d_tw
);

    // placeholder overflow source, see derivative.sv for why the parity of the word is used
    wire overflow_now = ^s_tdata;

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            m_tdata      <= {W_TW{1'b0}};
            m_tvalid     <= 1'b0;
            m_overflow   <= 1'b0;
            m_tlast      <= 1'b0;
            m_tuser      <= {W_TUSER{1'b0}};
            m_sample_idx <= {W_IDX{1'b0}};
            o_reject     <= 1'b0;
            d_valid      <= 1'b0;
            d_tw         <= {W_TW{1'b0}};
        end else begin
            // placeholder datapath: keep the low W_TW bits of the derivative word
            m_tdata      <= s_tdata[W_TW-1:0];
            m_tvalid     <= s_tvalid & i_rule_enable;
            m_tlast      <= s_tlast;
            m_tuser      <= s_tuser;
            m_sample_idx <= s_sample_idx;
            m_overflow   <= m_overflow | overflow_now;
            o_reject     <= 1'b0;
            d_valid      <= s_tvalid & i_rule_enable;
            d_tw         <= s_tdata[W_TW-1:0];
        end
    end

endmodule

`default_nettype wire
