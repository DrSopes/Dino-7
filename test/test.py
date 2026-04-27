import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

@cocotb.test()
async def test_dino7_full_game_logic(dut):
    dut._log.info("Starting Dino-7 Full Coverage Test for TTGF26")

    dut.ena.value = 1
    dut.ui_in.value = 0
    # ACTIVA EL BACKDOOR HARDWARE DE FAST SIM (uio_in[7] = 1)
    dut.uio_in.value = 0x80

    clock = Clock(dut.clk, 40, unit="ns")
    cocotb.start_soon(clock.start())

    dut._log.info("1. Applying hard reset...")
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("2. Checking IDLE state (High Score should be 0 = 0xBF)...")
    assert dut.uo_out.value == 0xBF, f"Expected 0xBF, got {hex(dut.uo_out.value)}"

    dut._log.info("3. Simulating jump to start game...")
    dut.ui_in.value = 1  
    await ClockCycles(dut.clk, 2)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 5)

    dut._log.info("4. Running frames, waiting for Ground Segment...")
    await ClockCycles(dut.clk, 30) 
    
    ground_on = (dut.uo_out.value.to_unsigned() & (1 << 3)) != 0
    assert ground_on, "Ground segment (d) should be ON during S_RUN"

    dut._log.info("5. Waiting for obstacle to spawn and reach close zone...")
    
    timeout_cycles = 50000
    cycles_waited = 0
    obstacle_reached_close = False
    
    while cycles_waited < timeout_cycles:
        await RisingEdge(dut.clk)
        cycles_waited += 1
        
        val = dut.uo_out.value.to_unsigned()
        
        if val == 0xFF:
            obstacle_reached_close = True
            dut._log.info(f"Collision detected after {cycles_waited} cycles!")
            break
            
        if (val & (1 << 5)) != 0:
            pass 

    assert obstacle_reached_close, f"Timeout! No collision occurred even after {timeout_cycles} cycles."

    dut._log.info("6. Game Over flash detected successfully.")
    
    dut._log.info("7. Waiting for Score Screen...")
    await ClockCycles(dut.clk, 200)
    
    dut._log.info("8. Simulating game reset...")
    dut.ui_in.value = 2 
    await ClockCycles(dut.clk, 5)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 10)

    dut._log.info("9. Checking if IDLE memory works (DP should be ON)...")
    score_display = dut.uo_out.value.to_unsigned()
    assert (score_display & 0x80) != 0, "Decimal Point should be ON for High Score in IDLE"
    
    dut._log.info("Test completely passed!")
