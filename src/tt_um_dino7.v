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

    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    // Nous inputs
    wire jump_btn = ui_in[0];
    wire game_rst = ui_in[1];
    wire [1:0] difficulty = ui_in[3:2]; // Selector de dificultat
    wire [3:0] seed = ui_in[7:4];       // Llavors reduïdes per fer espai

    // 32-bit LFSR
    reg [31:0] lfsr;

    // Nous estats de la FSM
    localparam S_IDLE  = 3'd0;
    localparam S_RUN   = 3'd1;
    localparam S_JUMP  = 3'd2;
    localparam S_HIT   = 3'd3;
    localparam S_SCORE = 3'd4;

    reg [2:0] state;
    reg [3:0] score;
    reg [3:0] max_score; // Registre de High Score

    reg [23:0] clk_div;
    reg [23:0] frame_max;
    reg [23:0] speed_step;
    wire frame_tick = (clk_div >= frame_max);

    // Obstacles i Timers
    reg obs_c, obs_g, obs_f;
    reg [2:0] jump_timer;
    reg [2:0] cooldown_timer;
    reg [4:0] blink_timer;

    // Descodificador de dificultat per Hardware
    reg [23:0] init_base_speed;
    reg [23:0] init_speed_step;

    always @(*) begin
        `ifdef COCOTB_SIM
            init_base_speed = 24'd10;
            init_speed_step = 24'd2;
        `else
            case(difficulty)
                2'b00: begin init_base_speed = 24'd6_250_000; init_speed_step = 24'd1_000_000; end // Normal
                2'b01: begin init_base_speed = 24'd5_000_000; init_speed_step = 24'd1_000_000; end // Fast
                2'b10: begin init_base_speed = 24'd3_750_000; init_speed_step = 24'd800_000;   end // Hard
                2'b11: begin init_base_speed = 24'd2_500_000; init_speed_step = 24'd500_000;   end // Insane
            endcase
        `endif
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE;
            clk_div <= 0;
            score <= 0;
            max_score <= 0;
            obs_c <= 0; obs_g <= 0; obs_f <= 0;
            jump_timer <= 0;
            cooldown_timer <= 0;
            lfsr <= {28'hA5A5A5A, seed};
            frame_max <= init_base_speed;
            speed_step <= init_speed_step;
            blink_timer <= 0;
        end else if (game_rst) begin
            state <= S_IDLE;
            clk_div <= 0;
            score <= 0;
            obs_c <= 0; obs_g <= 0; obs_f <= 0;
            jump_timer <= 0;
            cooldown_timer <= 0;
            lfsr <= {lfsr[27:0], seed}; // Mantenim entropia entre partides
            frame_max <= init_base_speed;
            speed_step <= init_speed_step;
            blink_timer <= 0;
        end else begin
            clk_div <= clk_div + 1;

            // Capturem el salt fora del tick de frame per màxima resposta
            if (state == S_RUN && jump_btn && cooldown_timer == 0) begin
                state <= S_JUMP;
                jump_timer <= 3;
            end

            if (frame_tick) begin
                clk_div <= 0;
                // LFSR 32 bits (Taps: 32, 22, 2, 1)
                lfsr <= {lfsr[30:0], lfsr[31] ^ lfsr[21] ^ lfsr[1] ^ lfsr[0]};

                case (state)
                    S_IDLE: begin
                        if (jump_btn) state <= S_RUN;
                    end

                    S_RUN, S_JUMP: begin
                        obs_f <= obs_g;
                        obs_g <= obs_c;
                        // Impedeix spawn si hi ha obstacle a 'g' per evitar salts impossibles
                        obs_c <= (lfsr[0] & lfsr[1] & lfsr[2]) & !obs_c & !obs_g; 

                        if (obs_g && state == S_RUN) begin
                            state <= S_HIT;
                            blink_timer <= 5; // Temps de flaix de xoc
                            if (score > max_score) max_score <= score; // Actualitza High Score
                        end else begin
                            if (obs_f && state == S_JUMP) begin
                                if (score < 9) score <= score + 1;
                                if (score[1:0] == 2'b11 && frame_max > speed_step) begin
                                    frame_max <= frame_max - speed_step;
                                end
                            end
                        end

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
                        if (blink_timer > 0) blink_timer <= blink_timer - 1;
                        else state <= S_SCORE;
                    end
                    
                    S_SCORE: begin
                        blink_timer <= blink_timer + 1; // S'usa per alternar puntuacions a la pantalla
                    end
                endcase
            end
        end
    end

    // Descodificador 7 segments
    function [6:0] seg7;
        input [3:0] val;
        case(val)
            0: seg7 = 7'b0111111; 1: seg7 = 7'b0000110; 2: seg7 = 7'b1011011;
            3: seg7 = 7'b1001111; 4: seg7 = 7'b1100110; 5: seg7 = 7'b1101101;
            6: seg7 = 7'b1111101; 7: seg7 = 7'b0000111; 8: seg7 = 7'b1111111;
            9: seg7 = 7'b1101111; default: seg7 = 7'b0000000;
        endcase
    endfunction

    reg [7:0] out;
    always @(*) begin
        if (state == S_IDLE) begin
            out = {1'b1, seg7(max_score)}; // IDLE: Mostra High Score amb el Punt Decimal ON
        end else if (state == S_HIT) begin
            out = 8'b11111111; // HIT: Tot encès
        end else if (state == S_SCORE) begin
            if (blink_timer[3]) out = {1'b1, seg7(max_score)}; // Alterna High Score (DP On)
            else                out = {1'b0, seg7(score)};     // Alterna Puntuació Final (DP Off)
        end else begin
            // In Game display mapping
            out[0] = 1'b0;                 
            out[1] = (state == S_JUMP);    
            out[2] = obs_c;                
            out[3] = 1'b1;                 
            out[4] = (state == S_RUN);     
            out[5] = obs_f;                
            out[6] = obs_g;                
            out[7] = (cooldown_timer > 0); 
        end
    end

    assign uo_out = out;

endmodule