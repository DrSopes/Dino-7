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

S_IDLE  = 0
S_RUN   = 1
S_JUMP  = 2
S_HIT   = 3
S_SCORE = 4


def dut_i(dut):
    return dut.user_project


def uo(dut):
    return dut.uo_out.value.to_unsigned()


def ui(dut):
    return dut.ui_in.value.to_unsigned()


def state(dut):
    return dut_i(dut).state.value.to_unsigned()


def score(dut):
    return dut_i(dut).score.value.to_unsigned()


def max_score(dut):
    return dut_i(dut).max_score.value.to_unsigned()


def cooldown(dut):
    return dut_i(dut).cooldown_timer.value.to_unsigned()


def frame_max(dut):
    return dut_i(dut).frame_max.value.to_unsigned()


def obs_c(dut):
    return dut_i(dut).obs_c.value.to_unsigned()


def obs_g(dut):
    return dut_i(dut).obs_g.value.to_unsigned()


def obs_f(dut):
    return dut_i(dut).obs_f.value.to_unsigned()


def has_bit(value, bitmask):
    return (value & bitmask) != 0


def log_state(dut, tag="STATE"):
    value = uo(dut)
    dut._log.info(
        f"[{tag}] "
        f"uo_out=0x{value:02X} "
        f"state={state(dut)} "
        f"score={score(dut)} "
        f"max_score={max_score(dut)} "
        f"cooldown={cooldown(dut)} "
        f"frame_max={frame_max(dut)} "
        f"obs(c/g/f)=({obs_c(dut)}/{obs_g(dut)}/{obs_f(dut)})"
    )


async def init_test(dut, difficulty_bits=0b00, seed_bits=0b1111):
    if not hasattr(init_test, "_clock_started"):
        clock = Clock(dut.clk, 40, unit="ns")
        cocotb.start_soon(clock.start())
        init_test._clock_started = True

    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = ((seed_bits & 0xF) << 4) | ((difficulty_bits & 0x3) << 2)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)
    log_state(dut, "AFTER_RESET")


async def pulse_jump(dut, cycles=1):
    dut.ui_in.value = ui(dut) | 0x01
    await ClockCycles(dut.clk, cycles)
    dut.ui_in.value = ui(dut) & ~0x01


async def hold_jump_until_start(dut, timeout_cycles=80):
    dut._log.info("[STEP] Holding jump until game leaves IDLE")
    dut.ui_in.value = ui(dut) | 0x01

    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)
        if state(dut) != S_IDLE:
            dut._log.info(f"[PASS] Left IDLE after {i+1} cycles")
            dut.ui_in.value = ui(dut) & ~0x01
            await ClockCycles(dut.clk, 1)
            log_state(dut, "AFTER_START")
            return

    dut.ui_in.value = ui(dut) & ~0x01
    raise AssertionError("[FAIL] Game never left IDLE")


async def pulse_game_reset(dut, cycles=2):
    dut.ui_in.value = ui(dut) | 0x02
    await ClockCycles(dut.clk, cycles)
    dut.ui_in.value = ui(dut) & ~0x02


async def wait_for_state(dut, target_state, timeout_cycles=400, label="state"):
    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)
        if state(dut) == target_state:
            dut._log.info(f"[PASS] Reached {label} after {i+1} cycles")
            log_state(dut, f"AT_{label.upper()}")
            return
    raise AssertionError(f"[FAIL] Did not reach {label} within {timeout_cycles} cycles")


async def wait_for_output_change(dut, timeout_cycles=120, label="output change"):
    start = uo(dut)
    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)
        if uo(dut) != start:
            dut._log.info(
                f"[PASS] {label} after {i+1} cycles: 0x{start:02X} -> 0x{uo(dut):02X}"
            )
            return
    raise AssertionError(f"[FAIL] No {label} within {timeout_cycles} cycles")


async def wait_for_hit_and_score(dut):
    await wait_for_state(dut, S_HIT, timeout_cycles=400, label="hit")
    assert uo(dut) == ALL_ON, f"[FAIL] HIT output should be 0xFF, got 0x{uo(dut):02X}"

    await wait_for_state(dut, S_SCORE, timeout_cycles=250, label="score")
    assert uo(dut) != ALL_ON, "[FAIL] SCORE screen should not remain 0xFF"


async def wait_for_dp_toggle_in_score(dut, timeout_cycles=300):
    seen0 = False
    seen1 = False
    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)
        if state(dut) != S_SCORE:
            continue
        if has_bit(uo(dut), SEG_DP):
            seen1 = True
        else:
            seen0 = True
        if seen0 and seen1:
            dut._log.info(f"[PASS] DP toggled in SCORE after {i+1} cycles")
            return
    raise AssertionError("[FAIL] DP did not toggle in SCORE")


async def autoplay_until_score_increase(dut, timeout_cycles=1500):
    last_score = score(dut)
    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)

        if state(dut) == S_RUN and obs_g(dut) == 1 and cooldown(dut) == 0:
            dut.ui_in.value = ui(dut) | 0x01
            await ClockCycles(dut.clk, 1)
            dut.ui_in.value = ui(dut) & ~0x01

        if score(dut) > last_score:
            dut._log.info(f"[PASS] Score increased from {last_score} to {score(dut)} after {i+1} cycles")
            return

    raise AssertionError("[FAIL] Could not increase score with autoplay")


async def autoplay_until_score_at_least(dut, target, timeout_cycles=5000):
    for i in range(timeout_cycles):
        await RisingEdge(dut.clk)

        if state(dut) == S_RUN and obs_g(dut) == 1 and cooldown(dut) == 0:
            dut.ui_in.value = ui(dut) | 0x01
            await ClockCycles(dut.clk, 1)
            dut.ui_in.value = ui(dut) & ~0x01

        if score(dut) >= target:
            dut._log.info(f"[PASS] Reached score {score(dut)} after {i+1} cycles")
            return

        if state(dut) == S_SCORE and score(dut) < target:
            raise AssertionError(f"[FAIL] Died before reaching score {target}, final score={score(dut)}")

    raise AssertionError(f"[FAIL] Timeout before reaching score {target}")


@cocotb.test()
async def test_boot_idle(dut):
    await init_test(dut, difficulty_bits=0b00, seed_bits=0b1111)
    assert state(dut) == S_IDLE, f"[FAIL] Expected IDLE after reset, got {state(dut)}"
    assert uo(dut) == IDLE_ZERO_WITH_DP, f"[FAIL] Expected 0xBF in idle, got 0x{uo(dut):02X}"
    assert score(dut) == 0, f"[FAIL] Score should reset to 0, got {score(dut)}"
    assert max_score(dut) == 0, f"[FAIL] Max score should reset to 0, got {max_score(dut)}"
    dut._log.info("[PASS] Boot idle test passed")


@cocotb.test()
async def test_start_and_motion(dut):
    await init_test(dut, difficulty_bits=0b00, seed_bits=0b1111)
    await hold_jump_until_start(dut)
    assert state(dut) in (S_RUN, S_JUMP), f"[FAIL] Expected RUN/JUMP, got {state(dut)}"
    await wait_for_output_change(dut, timeout_cycles=120, label="gameplay motion")
    dut._log.info("[PASS] Start and motion test passed")


@cocotb.test()
async def test_hit_and_score_screen(dut):
    await init_test(dut, difficulty_bits=0b00, seed_bits=0b1111)
    await hold_jump_until_start(dut)
    await wait_for_hit_and_score(dut)
    await wait_for_dp_toggle_in_score(dut)
    dut._log.info("[PASS] Hit and score screen test passed")


@cocotb.test()
async def test_reset_from_gameplay(dut):
    await init_test(dut, difficulty_bits=0b00, seed_bits=0b1111)
    await hold_jump_until_start(dut)
    await wait_for_output_change(dut, timeout_cycles=120, label="pre-reset gameplay activity")
    await pulse_game_reset(dut, cycles=2)
    await ClockCycles(dut.clk, 10)
    assert state(dut) == S_IDLE, f"[FAIL] Reset from gameplay should go to IDLE, got {state(dut)}"
    assert uo(dut) == IDLE_ZERO_WITH_DP, f"[FAIL] Reset from gameplay should show 0xBF, got 0x{uo(dut):02X}"
    dut._log.info("[PASS] Reset from gameplay test passed")


@cocotb.test()
async def test_reset_from_score(dut):
    await init_test(dut, difficulty_bits=0b00, seed_bits=0b1111)
    await hold_jump_until_start(dut)
    await wait_for_hit_and_score(dut)
    await pulse_game_reset(dut, cycles=2)
    await ClockCycles(dut.clk, 10)
    assert state(dut) == S_IDLE, f"[FAIL] Reset from score should go to IDLE, got {state(dut)}"
    assert uo(dut) == IDLE_ZERO_WITH_DP, f"[FAIL] Reset from score should show 0xBF, got 0x{uo(dut):02X}"
    dut._log.info("[PASS] Reset from score test passed")


@cocotb.test()
async def test_difficulty_modes(dut):
    await init_test(dut, difficulty_bits=0b00, seed_bits=0b1111)
    normal_frame = frame_max(dut)
    dut._log.info(f"[INFO] NORMAL frame_max={normal_frame}")

    await init_test(dut, difficulty_bits=0b11, seed_bits=0b1111)
    insane_frame = frame_max(dut)
    dut._log.info(f"[INFO] INSANE frame_max={insane_frame}")

    assert insane_frame < normal_frame, (
        f"[FAIL] Difficulty not applied: INSANE={insane_frame}, NORMAL={normal_frame}"
    )
    dut._log.info("[PASS] Difficulty mode test passed")


@cocotb.test()
async def test_score_increment(dut):
    await init_test(dut, difficulty_bits=0b00, seed_bits=0b1111)
    await hold_jump_until_start(dut)
    await autoplay_until_score_increase(dut, timeout_cycles=1500)
    assert score(dut) >= 1, f"[FAIL] Score did not increment, got {score(dut)}"
    dut._log.info("[PASS] Score increment test passed")


@cocotb.test()
async def test_high_score_persistence(dut):
    await init_test(dut, difficulty_bits=0b00, seed_bits=0b1111)
    await hold_jump_until_start(dut)
    await autoplay_until_score_at_least(dut, target=1, timeout_cycles=5000)

    while state(dut) != S_SCORE:
        await RisingEdge(dut.clk)

    log_state(dut, "AFTER_DEATH_WITH_SCORE")
    assert max_score(dut) >= 1 or score(dut) >= 1, (
        f"[FAIL] Expected score or max_score >=1, got score={score(dut)} max_score={max_score(dut)}"
    )

    await pulse_game_reset(dut, cycles=2)
    await ClockCycles(dut.clk, 10)

    assert state(dut) == S_IDLE, f"[FAIL] Expected IDLE after reset, got {state(dut)}"
    assert has_bit(uo(dut), SEG_DP), f"[FAIL] Idle high-score display should have DP on, got 0x{uo(dut):02X}"
    assert max_score(dut) >= 1, f"[FAIL] High score did not persist, got {max_score(dut)}"
    dut._log.info("[PASS] High score persistence test passed")


@cocotb.test()
async def test_jump_cooldown(dut):
    await init_test(dut, difficulty_bits=0b00, seed_bits=0b1111)
    await hold_jump_until_start(dut)

    while state(dut) != S_RUN:
        await RisingEdge(dut.clk)

    await pulse_jump(dut, cycles=1)

    jumped = False
    for _ in range(50):
        await RisingEdge(dut.clk)
        if state(dut) == S_JUMP:
            jumped = True
            break

    assert jumped, "[FAIL] First jump did not enter S_JUMP"

    while state(dut) == S_JUMP:
        await RisingEdge(dut.clk)

    cd = cooldown(dut)
    assert cd > 0, f"[FAIL] Cooldown should be >0 after jump, got {cd}"

    await pulse_jump(dut, cycles=1)
    await ClockCycles(dut.clk, 2)

    assert state(dut) != S_JUMP, "[FAIL] Jump should be blocked during cooldown"

    while cooldown(dut) != 0:
        await RisingEdge(dut.clk)

    await pulse_jump(dut, cycles=1)
    await ClockCycles(dut.clk, 2)

    valid_second_jump = state(dut) == S_JUMP or has_bit(uo(dut), SEG_B)
    assert valid_second_jump, "[FAIL] Jump should work again after cooldown"
    dut._log.info("[PASS] Jump cooldown test passed")


@cocotb.test()
async def test_output_sanity(dut):
    await init_test(dut, difficulty_bits=0b00, seed_bits=0b1111)

    assert uo(dut) == IDLE_ZERO_WITH_DP, f"[FAIL] Idle output wrong: 0x{uo(dut):02X}"

    await hold_jump_until_start(dut)
    await ClockCycles(dut.clk, 5)
    gameplay_val = uo(dut)
    assert has_bit(gameplay_val, SEG_D), f"[FAIL] Ground segment should be on during gameplay, got 0x{gameplay_val:02X}"

    await wait_for_hit_and_score(dut)
    assert uo(dut) != ALL_ON, "[FAIL] Score output should not remain all-on"

    dut._log.info("[PASS] Output sanity test passed")
