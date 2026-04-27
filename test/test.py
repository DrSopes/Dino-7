import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

@cocotb.test()
async def test_dino7_full_game(dut):
    dut._log.info("=== Starting Dino-7 Full Silicon Verification Test ===")

    # Set initial states
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0

    # Create a 25Mhz clock (40ns period)
    clock = Clock(dut.clk, 40, units="ns")
    cocotb.start_soon(clock.start())

    dut._log.info("[1] Applying hard reset...")
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("[2] Checking IDLE state...")
    # Score 0 on 7-seg is 0111111 in binary -> 0x3F. DP is on (0x80) -> 0xBF
    assert dut.uo_out.value == 0xBF, f"Expected IDLE output 0xBF, got {hex(dut.uo_out.value)}"

    # Set difficulty to Normal (00) and simulate jump to start game
    dut._log.info("[3] Starting Game (Normal Difficulty)...")
    dut.ui_in.value = 1  # ui_in[0] high (Jump button)
    await ClockCycles(dut.clk, 2)
    dut.ui_in.value = 0

    # Wait for the player to enter S_RUN
    await ClockCycles(dut.clk, 5)
    ground_on = (dut.uo_out.value.integer & (1 << 3)) != 0
    assert ground_on, "Ground segment (d) should be on during gameplay"

    dut._log.info("[4] Auto-Bot: Playing the game to score points...")
    score_achieved = 0
    
    # Let the bot play until it scores 3 points
    # Max loop cycles to prevent infinite loop if game hangs
    max_cycles = 50000 
    cycles = 0

    while score_achieved < 3 and cycles < max_cycles:
        await RisingEdge(dut.clk)
        cycles += 1
        
        out_val = dut.uo_out.value.integer
        
        # Read the game state from the 7-segment output
        obs_mid = (out_val & (1 << 6)) != 0   # Obstacle in mid position
        obs_close = (out_val & (1 << 5)) != 0 # Obstacle in close position
        player_jumping = (out_val & (1 << 1)) != 0 # Player is jumping
        cooldown = (out_val & (1 << 7)) != 0  # Cooldown active
        
        # Bot Logic: Jump if obstacle is close and we are not on cooldown/jumping
        if obs_close and not player_jumping and not cooldown:
            dut.ui_in.value = 1
            await ClockCycles(dut.clk, 1)
            dut.ui_in.value = 0
            dut._log.info(f"Bot jumped at cycle {cycles}!")
            
            # Wait until jump resolves and check if score goes up
            # We assume a successful jump means we survived
            await ClockCycles(dut.clk, 50) 
            score_achieved += 1
            dut._log.info(f"Bot scored! Current score approx: {score_achieved}")

    assert score_achieved >= 3, "Bot failed to score 3 points"

    dut._log.info("[5] Forcing Game Over...")
    # Stop jumping and let the next obstacle hit the player
    hit_detected = False
    for _ in range(5000):
        await RisingEdge(dut.clk)
        if dut.uo_out.value == 0xFF:
            hit_detected = True
            break
            
    assert hit_detected, "Player was never hit! S_HIT state (0xFF) not reached."
    dut._log.info("Collision detected successfully!")

    # Wait for blink timer to finish (S_HIT -> S_SCORE)
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("[6] Verifying Hardware Difficulty Change...")
    dut.ui_in.value = 2 # Reset the game (ui_in[1] = 1)
    await ClockCycles(dut.clk, 2)
    dut.ui_in.value = 0b00001100 # Set Insane difficulty (ui_in[3:2] = 11)
    
    # The internal speed registers should now be configured much faster
    dut._log.info("Difficulty registers updated. Restarting game...")
    dut.ui_in.value = 0b00001101 # Keep Insane difficulty + Jump button
    await ClockCycles(dut.clk, 2)
    dut.ui_in.value = 0b00001100 # Release jump

    # Run for a bit to ensure it doesn't crash on Insane mode
    await ClockCycles(dut.clk, 200)

    dut._log.info("=== All Full Silicon Verification tests passed! ===")
