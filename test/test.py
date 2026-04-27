import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

@cocotb.test()
async def test_dino7(dut):
    dut._log.info("Starting Dino-7 Test")

    # Set initial states
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0

    # Create a 25Mhz clock (40ns period)
    clock = Clock(dut.clk, 40, units="ns")
    cocotb.start_soon(clock.start())

    dut._log.info("Applying hard reset...")
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Checking IDLE state (Score should be 0 = 0x3F)...")
    # Score 0 on 7-seg is 0111111 in binary -> 0x3F
    assert dut.uo_out.value == 0x3F, f"Expected 0x3F, got {hex(dut.uo_out.value)}"

    dut._log.info("Simulating jump to start game...")
    dut.ui_in.value = 1  # ui_in[0] high (Jump button)
    await ClockCycles(dut.clk, 2)
    dut.ui_in.value = 0

    dut._log.info("Waiting for some frames (fast sim)...")
    await ClockCycles(dut.clk, 100) 

    # In RUN state (or JUMP), at least ground (d=bit 3) should be on
    # Check if bit 3 (ground) is 1. We use integer masking
    ground_on = (dut.uo_out.value.integer & (1 << 3)) != 0
    assert ground_on, "Ground segment (d) should be on during gameplay"

    dut._log.info("Simulating game reset...")
    dut.ui_in.value = 2  # ui_in[1] high (Reset game)
    await ClockCycles(dut.clk, 2)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 15)

    assert dut.uo_out.value == 0x3F, "Score should reset back to 0"
    
    dut._log.info("Test passed successfully!")
