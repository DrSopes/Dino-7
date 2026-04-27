![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)
# Dino-7

Dino-7 is a Tiny Tapeout game implemented in Verilog.  
It renders a simplified one-digit Dino runner on a 7-segment display, with gameplay, hit detection, score display, high-score retention, and reset behavior.

## Overview

The design is built for the Tiny Tapeout flow and includes:

- Idle screen with high-score display.
- Start on jump input.
- Gameplay state with obstacle movement.
- Hit state and score screen.
- Game reset behavior.
- Difficulty input handling.
- Cocotb-based RTL and gate-level verification.

The verification flow is split into three modes:

1. **RTL full regression** — strict functional verification.
2. **GL functional smoke** — robust gate-level sanity checks for CI.
3. **GL extended** — optional longer gate-level checks with scaled timeouts.

## Repository Structure

```text
.
├── src/                  # RTL source files
├── test/                 # Cocotb testbench, Makefile, test wrapper
├── tt_submission/        # Gate-level netlist artifact used in GL simulation
└── README.md
```

## Inputs and Outputs

### Inputs

- `clk` — system clock
- `rst_n` — active-low reset
- `ena` — design enable
- `ui_in[0]` — jump
- `ui_in[1]` — game reset
- `ui_in[3:2]` — difficulty select
- `ui_in[7:4]` — seed bits

### Outputs

- `uo_out[7:0]` — 7-segment display output including decimal point

## Verification Strategy

### 1. RTL Full Regression

RTL simulation runs the **full 10/10 strict regression**.

This mode checks:

- boot idle behavior
- game start
- gameplay motion
- hit and score transitions
- reset from gameplay
- reset from score
- difficulty mode effect
- score increment
- high-score persistence
- jump cooldown
- output sanity

This is the main correctness target for design development.

### 2. GL Functional Smoke

Gate-level simulation runs a **robust smoke suite** intended for CI stability.

This mode verifies only behavior that is practical and observable in gate-level netlists:

- boot idle
- start from idle
- reset from gameplay
- basic output sanity
- safe execution with no dependency on internal RTL-only nets

Long, timing-sensitive, or internal-state-heavy tests are converted into **skip-lite passes** in this mode so the CI result stays meaningful and deterministic.

### 3. GL Extended

GL extended mode is optional.

It is meant for developers who want to push gate-level verification further and are willing to accept:

- much longer runtimes
- scaled timeouts
- less deterministic runtime behavior than RTL

This mode re-enables longer behavioral checks in gate-level simulation using configurable timeout scaling.

## Running the Tests

### RTL Full Regression

Run from the `test/` directory:

```bash
make
```

Or explicitly:

```bash
make -f Makefile results.xml
```

This should run the full strict cocotb regression.

### Gate-Level Functional Smoke

Copy the submitted gate-level Verilog into the expected location and run the gate-level target:

```bash
cp tt_submission/*.v test/gate_level_netlist.v
cd test
GATES=yes make -f Makefile results.xml
```

This runs the smoke-oriented gate-level suite.

### Gate-Level Extended

To run the extended gate-level checks, enable `GL_EXTENDED` and optionally increase the timeout scale:

```bash
cp tt_submission/*.v test/gate_level_netlist.v
cd test
GATES=yes GL_EXTENDED=1 GL_TIMEOUT_SCALE=20 make -f Makefile results.xml
```

If the design is still too slow in gate-level simulation, increase the scale:

```bash
GATES=yes GL_EXTENDED=1 GL_TIMEOUT_SCALE=100 make -f Makefile results.xml
```

## Environment Variables

The cocotb testbench uses these environment variables:

- `GATES=yes` — run gate-level simulation instead of RTL.
- `GL_EXTENDED=1` — enable long gate-level tests.
- `GL_TIMEOUT_SCALE=<N>` — multiply timeout windows in gate-level mode.

Examples:

```bash
GATES=yes make -f Makefile results.xml
```

```bash
GATES=yes GL_EXTENDED=1 GL_TIMEOUT_SCALE=50 make -f Makefile results.xml
```

## Why the Test Modes Are Split

RTL and gate-level simulation do not behave the same way.

RTL is faster and exposes internal signals directly, so it is the right place for strict functional regression. Gate-level simulation is slower, often hides internal RTL state, and is more sensitive to timing and netlist structure. For that reason, this repository uses:

- **RTL full regression** for correctness,
- **GL smoke** for stable CI confidence,
- **GL extended** for optional deeper post-synthesis exploration.

This split keeps automated verification fast, useful, and realistic.

## CI Expectation

Recommended CI policy:

- **RTL full regression**: required
- **GL functional smoke**: required
- **GL extended**: optional or manual

That gives good coverage without making every gate-level run too slow.

## Notes

- The gate-level flow uses the submitted netlist copied into `test/gate_level_netlist.v`.
- Some RTL-only internal signals are not available in gate-level simulation.
- Gate-level timing-sensitive tests may require larger timeout scaling.
- Smoke-mode gate-level success does not replace full RTL functional verification.

## License

See the repository license file if present.
