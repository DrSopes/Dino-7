import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

SEG_A  = 1 << 0
SEG_B  = 1 << 1
SEG_C  = 1 << 2
SEG_D  = 1 << 3
SEG_E  = 1 << 4
SEG_F  = 1 << 5
SEG_G  = 1 << 6
SEG_DP = 1 << 7

IDLE_ZERO_WITH_DP = 0xBF
ALL_ON = 0xFF


def uo(dut):
    return dut.uo_out.value.to_unsigned()


def ui(dut):
    return dut.ui_in.value.to_unsigned()


def has_bit(value, bitmask):
    return (value & bitmask) != 0


def log_state(dut, tag="STATE"):
    value = uo(dut)
    dut._log.info(
        f"[{tag}] uo_out=0x{value:02X} "
        f"(dp={int(has_bit(value, SEG_DP))} "
        f"a={int(has_bit(value, SEG_A))} "
        f"b={int(has_bit(value, SEG_B))} "
        f"c={int(has_bit(value, SEG_C))} "
        f"d={int(has_bit(value, SEG_D))} "
        f"e={int(has_bit(value, SEG_E))} "
        f"f={int(has_bit(value, SEG_F))} "
        f"g={int(has_bit(value, SEG_G))})"
    )


async def hard_reset(dut):
    dut._log.info("[SETUP] Applying hard reset")
    dut.rst_n.value = 0
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)
    log_state(dut, "AFTER_HARD_RESET")


async def pulse_game_reset(dut, cycles=2):
    dut.ui_in.value = ui(dut) | 0x02
    await ClockCycles(dut.clk, cycles)
    dut.ui_in.value = ui(dut) & ~0x02


async def start_game(dut, timeout_cycles=80):
    dut._log.info("[STEP] Starting game and holding jump until gameplay begins")
    dut.ui_in.value = ui(dut) | 0x01

    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)
        val = uo(dut)
        if val != IDLE_ZERO_WITH_DP:
            dut._log.info(
                f"[PASS] Game left IDLE after {i+1} cycles (uo_out=0x{val:02X})"
            )
            dut.ui_in.value = ui(dut) & ~0x01
            await ClockCycles(dut.clk, 1)
            log_state(dut, "AFTER_START")
            return

    dut.ui_in.value = ui(dut) & ~0x01
    raise AssertionError("[FAIL] Game never left IDLE while jump was held")


async def wait_for_any_change(dut, max_cycles, label):
    start = uo(dut)
    for i in range(max_cycles):
        await RisingEdge(dut.clk)
        now = uo(dut)
        if now != start:
            dut._log.info(
                f"[PASS] {label}: output changed after {i+1} cycles "
                f"(0x{start:02X} -> 0x{now:02X})"
            )
            return i + 1
    raise AssertionError(
        f"[FAIL] {label}: no output change observed within {max_cycles} cycles"
    )


async def wait_for_hit(dut, timeout_cycles=400):
    dut._log.info(f"[STEP] Waiting for collision / HIT state (timeout {timeout_cycles} cycles)")
    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)
        if uo(dut) == ALL_ON:
            dut._log.info(f"[PASS] HIT detected after {i+1} cycles")
            log_state(dut, "AT_HIT")
            return
    raise AssertionError("[FAIL] No HIT state detected within timeout")


async def wait_for_score_screen(dut, timeout_cycles=300):
    dut._log.info(f"[STEP] Waiting for SCORE screen (timeout {timeout_cycles} cycles)")
    seen_hit = False

    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)
        val = uo(dut)

        if val == ALL_ON:
            seen_hit = True
            continue

        if seen_hit and val != ALL_ON:
            dut._log.info(
                f"[PASS] SCORE screen detected after {i+1} cycles "
                f"(uo_out=0x{val:02X})"
            )
            log_state(dut, "AT_SCORE")
            return

    raise AssertionError("[FAIL] Score screen not reached after HIT")


async def wait_for_dp_toggle_on_score(dut, timeout_cycles=300):
    dut._log.info("[STEP] Checking score/max-score alternation using decimal point")
    seen_dp_0 = False
    seen_dp_1 = False

    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)
        val = uo(dut)

        if val == ALL_ON:
            continue

        if has_bit(val, SEG_DP):
            seen_dp_1 = True
        else:
            seen_dp_0 = True

        if seen_dp_0 and seen_dp_1:
            dut._log.info(
                f"[PASS] Score/max-score alternation observed within {i+1} cycles"
            )
            return

    raise AssertionError("[FAIL] No DP alternation observed on score screen")


@cocotb.test()
async def test_dino7_full(dut):
    dut._log.info("========== DINO-7 FULL TEST START ==========")

    clock = Clock(dut.clk, 40, unit="ns")
    cocotb.start_soon(clock.start())

    await hard_reset(dut)

    dut._log.info("[CHECK] Verifying idle screen after power-up")
    assert uo(dut) == IDLE_ZERO_WITH_DP, (
        f"[FAIL] Idle screen mismatch: expected 0x{IDLE_ZERO_WITH_DP:02X}, "
        f"got 0x{uo(dut):02X}"
    )
    dut._log.info("[PASS] Idle screen is correct")

    await start_game(dut, timeout_cycles=80)

    dut._log.info("[CHECK] Waiting for gameplay motion")
    await wait_for_any_change(dut, 80, "gameplay motion")

    await wait_for_hit(dut, timeout_cycles=400)
    await wait_for_score_screen(dut, timeout_cycles=300)
    await wait_for_dp_toggle_on_score(dut, timeout_cycles=300)

    dut._log.info("[CHECK] Testing in-game reset")
    await pulse_game_reset(dut, cycles=2)
    await ClockCycles(dut.clk, 20)
    log_state(dut, "AFTER_GAME_RESET")

    assert uo(dut) == IDLE_ZERO_WITH_DP, (
        f"[FAIL] Game reset did not return to idle: got 0x{uo(dut):02X}"
    )
    dut._log.info("[PASS] Game reset returns to idle")

    dut._log.info("========== DINO-7 FULL TEST PASS ==========")
