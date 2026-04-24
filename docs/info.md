<!---
This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the first 1024 characters of the combined markdown files are used for metadata extraction.
-->

## How it works

Dino-7 brings the spirit of the classic Chrome Dinosaur endless runner to a single 7-segment display.

The game is driven by a **Finite State Machine (FSM)** with four states:

| State | Description |
|-------|-------------|
| `RUN`   | Player is on the ground, obstacles move left |
| `JUMP`  | Player is in the air for a fixed number of frames |
| `HIT`   | Collision detected — display flashes error pattern |
| `SCORE` | Shows final score (0–9) and waits for reset |

### Display Mapping

The 7-segment display acts as a side-scrolling game world:

| Segment | Position | Meaning |
|---------|----------|---------|
| `d` (bottom) | Ground | Always on |
| `e` (bottom-left) | Left | Player on the ground |
| `b` (top-right) | Upper-right | Player jumping in the air |
| `c` (bottom-right) | Far right | Obstacle spawning |
| `g` (middle) | Mid | Obstacle approaching |
| `f` (top-left) | Left | Obstacle in collision zone |
| `dp` (decimal point) | — | Jump cooldown active |

### Obstacle Generation

An **8-bit Galois LFSR** generates pseudo-random obstacle spawn timing. At reset, bits `ui_in[7:2]` are loaded as an optional seed override to vary the obstacle pattern between games.

### Speed Progression

A **20-bit clock divider** scales the 25 MHz TinyTapeout clock down to a playable frame rate. Every 4 points scored, the divisor decreases, making obstacles move faster and the game harder.

### Collision Detection

A collision occurs when an obstacle reaches segment `f` (the close zone) while the player is in `RUN` state (on the ground). This triggers the `HIT` state.

## How to test

### Controls

| Pin | Function |
|-----|----------|
| `ui_in[0]` | Jump button — press to jump (active high) |
| `ui_in[1]` | Reset — press to restart after game over (active high) |
| `ui_in[7:2]` | Optional LFSR seed — set before reset to change obstacle pattern |

### Step-by-step

1. Power on or assert `ui_in[1]` (reset) briefly to start the game.
2. Watch segment `c` → `g` → `f` for incoming obstacles.
3. Press `ui_in[0]` to jump when an obstacle is at `g` (mid position).
4. The decimal point (`dp`) lights up during jump cooldown — you cannot jump again until it turns off.
5. Score increases every time an obstacle passes without collision. Speed increases every 4 points.
6. On collision, the display flashes an error pattern, then shows your score (0–9) on the display.
7. Press `ui_in[1]` to reset and play again.

### External Hardware

- A **common-cathode 7-segment display** connected to `uo_out[7:0]`.
- A **push button** on `ui_in[0]` with a pull-down resistor.
- A **reset button** on `ui_in[1]` with a pull-down resistor.
- No other external components required.
