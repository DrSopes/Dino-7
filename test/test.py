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
    return dut.uo_out.value.integer


def has_bit(value, bitmask):
    return (value & bitmask) != 0


def log_state(dut, tag="STATE"):
    value = uo(dut)
    dut._log.info(
        f"[{tag}] uo_out=0x{value:02X} "
        f"(dp={int(has_bit(value, SEG_DP))} "
        f"a={int(has_bit(value, SEG_A))} b={int(has_bit(value, SEG_B))} "
        f"c={int(has_bit(value, SEG_C))} d={int(has_bit(value, SEG_D))} "
        f"e={int(has_bit(value, SEG_E))} f={int(has_bit(value, SEG_F))} "
        f"g={int(has_bit(value, SEG_G))})"
    )


async def pulse_jump(dut, cycles=1):
    current = dut.ui_in.value.integer
    dut.ui_in.value = current | 0x01
    await ClockCycles(dut.clk, cycles)
    dut.ui_in.value = current & ~0x01


async def pulse_game_reset(dut, cycles=2):
    current = dut.ui_in.value.integer
    dut.ui_in.value = current | 0x02
    await ClockCycles(dut.clk, cycles)
    dut.ui_in.value = current & ~0x02


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


async def wait_for_any_change(dut, max_cycles, label):
    start = uo(dut)
    for i in range(max_cycles):
        await RisingEdge(dut.clk)
        if uo(dut) != start:
            dut._log.info(
                f"[PASS] {label}: output changed after {i+1} cycles "
                f"(0x{start:02X} -> 0x{uo(dut):02X})"
            )
            return i + 1
    raise AssertionError(
        f"[FAIL] {label}: no output change observed within {max_cycles} cycles"
    )


async def start_game(dut):
    dut._log.info("[STEP] Starting game with jump pulse")
    await pulse_jump(dut, cycles=2)
    await ClockCycles(dut.clk, 2)
    log_state(dut, "AFTER_START")

    val = uo(dut)
    assert has_bit(val, SEG_D), (
        f"[FAIL] Game did not enter gameplay display. "
        f"Ground segment d is off: uo_out=0x{val:02X}"
    )
    dut._log.info("[PASS] Game started and ground segment is on")


async def wait_for_hit(dut, timeout_cycles=500):
    dut._log.info(f"[STEP] Waiting for collision / HIT state (timeout {timeout_cycles} cycles)")
    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)
        val = uo(dut)
        if val == ALL_ON:
            dut._log.info(f"[PASS] HIT detected after {i+1} cycles (uo_out=0xFF)")
            return
    raise AssertionError("[FAIL] No HIT state detected within timeout")


async def wait_for_score_screen(dut, timeout_cycles=300):
    dut._log.info(f"[STEP] Waiting for SCORE screen after HIT (timeout {timeout_cycles} cycles)")
    seen_non_ff = False
    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)
        val = uo(dut)
        if val != ALL_ON and not has_bit(val, SEG_D):
            dut._log.info(
                f"[PASS] SCORE-like screen detected after {i+1} cycles "
                f"(uo_out=0x{val:02X})"
            )
            seen_non_ff = True
            break
    if not seen_non_ff:
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
                f"[PASS] Decimal point toggles on score screen "
                f"(observed both DP=0 and DP=1 within {i+1} cycles)"
            )
            return

    raise AssertionError("[FAIL] Score/max-score alternation not observed")


async def measure_first_motion_time(dut, difficulty_bits, label):
    dut._log.info(f"[STEP] Measuring first obstacle motion for difficulty {label}")
    dut.ui_in.value = (difficulty_bits << 2)
    await pulse_game_reset(dut, cycles=2)
    await ClockCycles(dut.clk, 10)

    val = uo(dut)
    assert val == IDLE_ZERO_WITH_DP, (
        f"[FAIL] {label}: expected idle screen 0x{IDLE_ZERO_WITH_DP:02X}, got 0x{val:02X}"
    )

    await start_game(dut)
    cycles = await wait_for_any_change(dut, 200, f"{label} first motion")
    log_state(dut, f"{label}_FIRST_MOTION")
    return cycles


@cocotb.test()
async def test_dino7_full(dut):
    dut._log.info("========== DINO-7 FULL TEST START ==========")

    clock = Clock(dut.clk, 40, units="ns")
    cocotb.start_soon(clock.start())

    await hard_reset(dut)

    dut._log.info("[CHECK] Verifying idle screen after power-up")
    val = uo(dut)
    assert val == IDLE_ZERO_WITH_DP, (
        f"[FAIL] Idle screen mismatch after reset: expected 0x{IDLE_ZERO_WITH_DP:02X}, got 0x{val:02X}"
    )
    dut._log.info("[PASS] Idle screen is correct (high score 0 with DP on)")

    await start_game(dut)

    dut._log.info("[CHECK] Waiting for gameplay animation / obstacle motion")
    await wait_for_any_change(dut, 120, "gameplay motion")

    await wait_for_hit(dut, timeout_cycles=500)
    log_state(dut, "AT_HIT")

    await wait_for_score_screen(dut, timeout_cycles=300)
    log_state(dut, "AT_SCORE_SCREEN")

    await wait_for_dp_toggle_on_score(dut, timeout_cycles=300)

    dut._log.info("[CHECK] Testing in-game reset button")
    await pulse_game_reset(dut, cycles=2)
    await ClockCycles(dut.clk, 15)
    val = uo(dut)
    log_state(dut, "AFTER_GAME_RESET")
    assert val == IDLE_ZERO_WITH_DP, (
        f"[FAIL] Game reset did not return to idle screen: got 0x{val:02X}"
    )
    dut._log.info("[PASS] Game reset returns to idle screen correctly")

    dut._log.info("[CHECK] Comparing difficulty modes")
    normal_cycles = await measure_first_motion_time(dut, difficulty_bits=0b00, label="NORMAL")
    insane_cycles = await measure_first_motion_time(dut, difficulty_bits=0b11, label="INSANE")

    dut._log.info(
        f"[INFO] First motion timing: NORMAL={normal_cycles} cycles, INSANE={insane_cycles} cycles"
    )
    assert insane_cycles < normal_cycles, (
        f"[FAIL] Difficulty selector ineffective: INSANE ({insane_cycles}) "
        f"is not faster than NORMAL ({normal_cycles})"
    )
    dut._log.info("[PASS] Difficulty selector changes game speed")

    dut._log.info("========== DINO-7 FULL TEST PASS ==========")
