import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

@cocotb.test()
async def test_dino7_full_game_logic(dut):
    dut._log.info("Starting Dino-7 Full Coverage Test for TTGF26")

    # Inicialitzem a zero
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0

    # Rellotge 25Mhz (40ns period) - usant 'unit' (no 'units') per evitar warning
    clock = Clock(dut.clk, 40, unit="ns")
    cocotb.start_soon(clock.start())

    # 1. HARD RESET
    dut._log.info("1. Applying hard reset...")
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # 2. CHECK IDLE & HIGH SCORE (0)
    dut._log.info("2. Checking IDLE state (High Score should be 0 = 0xBF)...")
    assert dut.uo_out.value == 0xBF, f"Expected 0xBF, got {hex(dut.uo_out.value)}"

    # 3. START GAME
    dut._log.info("3. Simulating jump to start game...")
    dut.ui_in.value = 1  # ui_in[0] high (Jump button)
    await ClockCycles(dut.clk, 2)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 5)

    # 4. GAMEPLAY CHECK
    dut._log.info("4. Running frames, waiting for Ground Segment...")
    await ClockCycles(dut.clk, 25) 
    
    # Utilitzem to_unsigned() en lloc de l'antic .integer()
    ground_on = (dut.uo_out.value.to_unsigned() & (1 << 3)) != 0
    assert ground_on, "Ground segment (d) should be ON during S_RUN"

    # 5. AVALUA EL SALT
    dut._log.info("5. Waiting for obstacle generation...")
    obstacle_detected = False
    # Augmentem el marge de cerca fins a 3000 cicles perquè li doni temps a l'LFSR d'escollir aparèixer
    for _ in range(3000): 
        await ClockCycles(dut.clk, 1)
        if (dut.uo_out.value.to_unsigned() & (1 << 6)) != 0: # Obstacle a 'g'
            obstacle_detected = True
            break
            
    if obstacle_detected:
        dut._log.info("Obstacle detected at mid-position! JUMPING!")
        dut.ui_in.value = 1  # Jump
        await ClockCycles(dut.clk, 5)
        dut.ui_in.value = 0
        
        await ClockCycles(dut.clk, 2)
        in_air = (dut.uo_out.value.to_unsigned() & (1 << 1)) != 0
        on_ground = (dut.uo_out.value.to_unsigned() & (1 << 4)) != 0
        assert in_air and not on_ground, "Player did not jump correctly!"
        dut._log.info("Player successfully jumped the obstacle.")
    else:
        dut._log.info("No obstacle spawned in time (randomness variation). Proceeding.")

    # 6. FORCE A COLLISION (HIT STATE)
    dut._log.info("6. Forcing a collision...")
    hit_detected = False
    
    # Com que perdem estona saltant, deixem avançar el joc MOLT de temps fins que topem
    # Amb un límit de 10000 cicles de rellotge estem assegurant que l'LFSR genera obstacles segur
    for _ in range(10000):
        await ClockCycles(dut.clk, 1)
        if dut.uo_out.value == 0xFF: # 8'b11111111 is the HIT flash state
            hit_detected = True
            break
            
    assert hit_detected, "Collision (HIT state 0xFF) was never detected!"
    dut._log.info("Collision registered. Screen flashed 0xFF.")

    # 7. SCORE SCREEN & HIGH SCORE MEMORY
    dut._log.info("7. Waiting for Game Over Score Screen...")
    await ClockCycles(dut.clk, 50)
    
    dut._log.info("8. Simulating game reset...")
    dut.ui_in.value = 2  # ui_in[1] high (Reset game)
    await ClockCycles(dut.clk, 5)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 5)

    # 9. VERIFICA LA MEMÒRIA (EL DP HA DE SEGUIR ENCES)
    dut._log.info("9. Checking if memory preserved High Score in IDLE...")
    score_display = dut.uo_out.value.to_unsigned()
    assert (score_display & 0x80) != 0, "Decimal Point should be ON for High Score in IDLE"
    
    dut._log.info(f"Test completely passed! Final High Score segment readout: {hex(score_display)}")
