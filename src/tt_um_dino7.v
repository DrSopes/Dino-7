`default_nettype none

module tt_um_dino7 (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high)
    input  wire       ena,      // always 1 when the design is powered
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    // TinyTapeout requires all unused outputs to be assigned
    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    // Inputs mapping
    wire jump_btn = ui_in[0];
    wire game_rst = ui_in[1];
    wire [5:0] seed = ui_in[7:2];

    // Clock divider for frame generation
    reg [23:0] clk_div;
    reg [23:0] frame_max;
    wire frame_tick = (clk_div >= frame_max);

    `ifdef COCOTB_SIM
        localparam BASE_SPEED = 24'd10;        // Extremely fast for simulation
        localparam SPEED_STEP = 24'd2;
    `else
        localparam BASE_SPEED = 24'd6_250_000; // 4 FPS initially at 25MHz
        localparam SPEED_STEP = 24'd1_000_000; // Speed up amount
    `endif

    // FSM States
    localparam S_IDLE = 2'd0;
    localparam S_RUN  = 2'd1;
    localparam S_JUMP = 2'd2;
    localparam S_HIT  = 2'd3;

    reg [1:0] state;
    reg [3:0] score;

    // Obstacle positions
    reg obs_c, obs_g, obs_f;

    reg [2:0] jump_timer;
    reg [2:0] cooldown_timer;
    reg [7:0] lfsr;

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE;
            clk_div <= 0;
            frame_max <= BASE_SPEED;
            score <= 0;
            obs_c <= 0; obs_g <= 0; obs_f <= 0;
            jump_timer <= 0;
            cooldown_timer <= 0;
            lfsr <= {seed, 2'b01}; // Ensure non-zero seed
        end else if (game_rst) begin
            state <= S_IDLE;
            clk_div <= 0;
            frame_max <= BASE_SPEED;
            score <= 0;
            obs_c <= 0; obs_g <= 0; obs_f <= 0;
            jump_timer <= 0;
            cooldown_timer <= 0;
            lfsr <= {seed, 2'b01};
        end else begin
            clk_div <= clk_div + 1;

            // Capture jump asynchronous to frame tick for responsiveness
            if (state == S_RUN && jump_btn && cooldown_timer == 0) begin
                state <= S_JUMP;
                jump_timer <= 3;
            end

            if (frame_tick) begin
                clk_div <= 0;
                // Galois LFSR (taps at 8, 6, 5, 4 for 8-bit)
                lfsr <= {lfsr[6:0], lfsr[7] ^ lfsr[5] ^ lfsr[4] ^ lfsr[3]};

                case (state)
                    S_IDLE: begin
                        if (jump_btn) state <= S_RUN;
                    end

                    S_RUN, S_JUMP: begin
                        // Shift obstacles
                        obs_f <= obs_g;
                        obs_g <= obs_c;
                        obs_c <= lfsr[0] & lfsr[1]; // 25% chance to spawn

                        // Check collisions
                        if (obs_g && state == S_RUN) begin
                            state <= S_HIT;
                        end else begin
                            // Score point if player passed an obstacle
                            if (obs_f && state == S_JUMP) begin
                                if (score < 9) score <= score + 1;
                                // Increase speed every 4 points
                                if (score[1:0] == 2'b11 && frame_max > SPEED_STEP) begin
                                    frame_max <= frame_max - SPEED_STEP;
                                end
                            end
                        end

                        // Handle timers
                        if (state == S_JUMP) begin
                            if (jump_timer > 0) jump_timer <= jump_timer - 1;
                            else begin
                                state <= S_RUN;
                                cooldown_timer <= 2;
                            end
                        end else begin
                            if (cooldown_timer > 0) cooldown_timer <= cooldown_timer - 1;
                        end
                    end

                    S_HIT: begin
                        // Wait one tick on error screen, then go to score screen
                        state <= S_IDLE;
                    end
                endcase
            end
        end
    end

    // 7-segment decoder for SCORE state
    reg [6:0] score_seg;
    always @(*) begin
        case(score)
            0: score_seg = 7'b0111111; // 0
            1: score_seg = 7'b0000110; // 1
            2: score_seg = 7'b1011011; // 2
            3: score_seg = 7'b1001111; // 3
            4: score_seg = 7'b1100110; // 4
            5: score_seg = 7'b1101101; // 5
            6: score_seg = 7'b1111101; // 6
            7: score_seg = 7'b0000111; // 7
            8: score_seg = 7'b1111111; // 8
            9: score_seg = 7'b1101111; // 9
            default: score_seg = 7'b0000000;
        endcase
    end

    // Output Mapping
    reg [7:0] out;
    always @(*) begin
        if (state == S_IDLE) begin
            out = {1'b0, score_seg}; // dp off, show score
        end else if (state == S_HIT) begin
            out = 8'b11111111;       // Flash all segments
        end else begin
            // In Game display mapping
            out[0] = 1'b0;                 // a: Unused
            out[1] = (state == S_JUMP);    // b: Player jumping
            out[2] = obs_c;                // c: Obstacle far
            out[3] = 1'b1;                 // d: Ground
            out[4] = (state == S_RUN);     // e: Player on ground
            out[5] = obs_f;                // f: Obstacle close
            out[6] = obs_g;                // g: Obstacle mid
            out[7] = (cooldown_timer > 0); // dp: Cooldown
        end
    end

    assign uo_out = out;

endmodule
