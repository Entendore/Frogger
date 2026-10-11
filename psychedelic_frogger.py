#!/usr/bin/env python3
"""
PSYCHEDELIC FROGGER - A retro 8-bit acid trip through classic Frogger gameplay.
Features shifting rainbow colors, trippy visual effects, and chiptune sounds.
Modes: CLASSIC (standard lives) and INFINITE (endless escalating challenge).
Controls: Arrow keys or WASD to move. ESC to quit.
"""

import pygame
import numpy as np
import random
import math
import sys
import os

# ---------------------------------------------------------------------------
# INIT
# ---------------------------------------------------------------------------
os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

CELL = 48
COLS = 13
ROWS = 14
HUD_H = 50
W = CELL * COLS       # 624
H = CELL * ROWS + HUD_H  # 722
FPS = 60
GOAL_SLOTS = 5

screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("🐸 PSYCHEDELIC FROGGER 🐸")
clock = pygame.time.Clock()

font_big = pygame.font.SysFont("consolas", 28, bold=True)
font_title = pygame.font.SysFont("consolas", 42, bold=True)
font_med = pygame.font.SysFont("consolas", 18, bold=True)
font_sm  = pygame.font.SysFont("consolas", 14)

# Game states
STATE_TITLE = 0
STATE_PLAYING = 1
STATE_GAME_OVER = 2

# ---------------------------------------------------------------------------
# COLOR UTILITIES
# ---------------------------------------------------------------------------
def hsv_to_rgb(h, s, v):
    """Convert HSV (0-1 range) to RGB (0-255 range)."""
    h = h % 1.0
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = [(v,t,p),(q,v,p),(p,v,t),(p,q,v),(t,p,v),(v,p,q)][i % 6]
    return (int(r * 255), int(g * 255), int(b * 255))

def shift_hue(color, offset):
    """Shift the hue of an RGB color by offset (0-1)."""
    r, g, b = [c / 255.0 for c in color]
    mx = max(r, g, b)
    mn = min(r, g, b)
    d = mx - mn
    if d == 0:
        h, s = 0, 0
    elif mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h /= 6.0
    s = d / mx if mx else 0
    v = mx
    return hsv_to_rgb(h + offset, s, v)

def psychedelic_cycle(t, speed=0.5):
    """Get a cycling psychedelic color based on time."""
    return hsv_to_rgb(t * speed, 0.8, 1.0)

def neon_glow(surface, rect, color, intensity=2):
    """Draw a neon glow effect around a rect."""
    for i in range(intensity, 0, -1):
        alpha = 60 // i
        glow_color = tuple(min(255, c + 50) for c in color)
        glow_rect = rect.inflate(i * 4, i * 4)
        glow_surf = pygame.Surface((glow_rect.w, glow_rect.h))
        glow_surf.fill(glow_color)
        glow_surf.set_alpha(alpha)
        surface.blit(glow_surf, glow_rect.topleft)

# ---------------------------------------------------------------------------
# 8-BIT SOUND GENERATOR
# ---------------------------------------------------------------------------
SAMPLE_RATE = 44100

def generate_tone(freq, duration, volume=0.3, wave_type="square", 
                   vibrato=0, sweep=0, noise_mix=0.0):
    """Generate an 8-bit style tone as a numpy array."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples, dtype=np.float64)
    
    if sweep != 0:
        freq = freq + sweep * t
    
    if vibrato > 0:
        freq = freq + vibrato * np.sin(2 * np.pi * 6 * t)
    
    if wave_type == "square":
        wave = np.sign(np.sin(2 * np.pi * freq * t))
    elif wave_type == "saw":
        wave = 2.0 * (freq * t - np.floor(0.5 + freq * t))
    elif wave_type == "triangle":
        wave = 2.0 * np.abs(2.0 * (freq * t - np.floor(freq * t + 0.5))) - 1.0
    elif wave_type == "sine":
        wave = np.sin(2 * np.pi * freq * t)
    elif wave_type == "noise":
        wave = np.random.uniform(-1, 1, n_samples)
    else:
        wave = np.sign(np.sin(2 * np.pi * freq * t))
    
    if noise_mix > 0:
        noise = np.random.uniform(-1, 1, n_samples) * noise_mix
        wave = wave * (1 - noise_mix) + noise
    
    # Apply envelope (quick attack, short decay, sustain, release)
    attack = int(0.01 * SAMPLE_RATE)
    release = int(0.05 * SAMPLE_RATE)
    env = np.ones(n_samples)
    if attack > 0 and attack < n_samples:
        env[:attack] = np.linspace(0, 1, attack)
    if release > 0 and release < n_samples:
        env[-release:] = np.linspace(1, 0, release)
    
    wave = wave * env * volume
    wave = np.clip(wave, -1, 1)
    return (wave * 32767).astype(np.int16)

def make_sound(freq, duration, **kwargs):
    """Create a pygame Sound from generated tone."""
    arr = generate_tone(freq, duration, **kwargs)
    return pygame.sndarray.make_sound(arr)

# Sound effects
def create_sounds():
    sounds = {}
    # Jump sound - quick ascending chirp
    hop = generate_tone(300, 0.08, 0.25, "square", sweep=800, vibrato=20)
    sounds["hop"] = pygame.sndarray.make_sound(np.column_stack((hop, hop)))
    
    # Splash (death in water) - descending noise
    splash = generate_tone(800, 0.3, 0.3, "noise", sweep=-600, noise_mix=0.7)
    sounds["splash"] = pygame.sndarray.make_sound(np.column_stack((splash, splash)))
    
    # Squish (hit by car) - crunchy
    squish = generate_tone(150, 0.25, 0.3, "saw", sweep=-100, noise_mix=0.5)
    sounds["squish"] = pygame.sndarray.make_sound(np.column_stack((squish, squish)))
    
    # Score (reach home) - happy arpeggio
    score_arr = np.concatenate([
        generate_tone(523, 0.1, 0.25, "square"),
        generate_tone(659, 0.1, 0.25, "square"),
        generate_tone(784, 0.1, 0.25, "square"),
        generate_tone(1047, 0.2, 0.3, "square"),
    ])
    sounds["score"] = pygame.sndarray.make_sound(np.column_stack((score_arr, score_arr)))
    
    # Level up - trippy ascending sweep
    lvl = generate_tone(200, 0.6, 0.25, "saw", sweep=1200, vibrato=30, noise_mix=0.1)
    sounds["level_up"] = pygame.sndarray.make_sound(np.column_stack((lvl, lvl)))
    
    # Death - dissonant falling
    death_arr = np.concatenate([
        generate_tone(400, 0.15, 0.3, "square", sweep=-200, vibrato=50),
        generate_tone(200, 0.15, 0.3, "square", sweep=-100, vibrato=40),
        generate_tone(100, 0.3, 0.3, "saw", sweep=-50, noise_mix=0.3),
    ])
    sounds["death"] = pygame.sndarray.make_sound(np.column_stack((death_arr, death_arr)))
    
    # Game over - sad descending
    go_arr = np.concatenate([
        generate_tone(392, 0.2, 0.3, "square"),
        generate_tone(349, 0.2, 0.3, "square"),
        generate_tone(330, 0.2, 0.3, "square"),
        generate_tone(262, 0.4, 0.35, "triangle"),
    ])
    sounds["game_over"] = pygame.sndarray.make_sound(np.column_stack((go_arr, go_arr)))
    
    # Background music loop - trippy bass line
    bpm = 140
    beat = 60.0 / bpm
    notes = [110, 130.81, 146.83, 164.81, 174.61, 146.83, 130.81, 110]
    music_arr = np.array([], dtype=np.int16)
    for note in notes:
        seg = generate_tone(note, beat * 0.8, 0.12, "square", vibrato=5, noise_mix=0.05)
        rest = np.zeros(int(SAMPLE_RATE * beat * 0.2), dtype=np.int16)
        music_arr = np.concatenate([music_arr, seg, rest])
    sounds["music"] = pygame.sndarray.make_sound(np.column_stack((music_arr, music_arr)))
    
    # Trippy melody overlay
    melody_notes = [523, 0, 659, 0, 784, 659, 523, 0, 440, 0, 523, 440, 392, 0, 349, 0]
    mel_arr = np.array([], dtype=np.int16)
    for note in melody_notes:
        if note == 0:
            mel_arr = np.concatenate([mel_arr, np.zeros(int(SAMPLE_RATE * beat * 0.5), dtype=np.int16)])
        else:
            seg = generate_tone(note, beat * 0.4, 0.08, "triangle", vibrato=10)
            mel_arr = np.concatenate([mel_arr, seg])
    sounds["melody"] = pygame.sndarray.make_sound(np.column_stack((mel_arr, mel_arr)))
    
    return sounds

# ---------------------------------------------------------------------------
# GAME OBJECTS
# ---------------------------------------------------------------------------
class Frog:
    def __init__(self):
        self.reset()
        self.anim_t = 0
    
    def reset(self):
        self.x = COLS // 2
        self.y = ROWS - 1
        self.highest_y = ROWS - 1
        self.alive = True
        self.death_timer = 0
        self.death_type = None
        self.riding = None
        self.hop_anim = 0
    
    def move(self, dx, dy):
        if not self.alive:
            return
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < COLS and 0 <= ny < ROWS:
            self.x = nx
            self.y = ny
            if ny < self.highest_y:
                self.highest_y = ny
            self.hop_anim = 8
            return True
        return False
    
    def pixel_pos(self):
        px = self.x * CELL + CELL // 2
        py = self.y * CELL + CELL // 2 + HUD_H
        # Hop animation - slight bounce
        if self.hop_anim > 0:
            py -= int(math.sin(self.hop_anim / 8.0 * math.pi) * 6)
        return px, py
    
    def draw(self, surface, t):
        px, py = self.pixel_pos()
        # Psychedelic frog body - shifts colors
        body_hue = (t * 0.8) % 1.0
        body_color = hsv_to_rgb(body_hue, 0.9, 1.0)
        eye_color = hsv_to_rgb((body_hue + 0.3) % 1.0, 1.0, 1.0)
        belly_color = hsv_to_rgb((body_hue + 0.5) % 1.0, 0.6, 1.0)
        
        # Pulsing glow
        pulse = 0.5 + 0.5 * math.sin(t * 6)
        glow_size = int(4 + pulse * 6)
        neon_glow(surface, pygame.Rect(px - CELL//3, py - CELL//3, CELL*2//3, CELL*2//3), body_color, glow_size // 2)
        
        # Body (pixelated frog shape)
        s = CELL // 8  # pixel size
        # Back legs
        pygame.draw.rect(surface, body_color, (px - 3*s, py + s, 2*s, 3*s))
        pygame.draw.rect(surface, body_color, (px + s, py + s, 2*s, 3*s))
        # Feet
        pygame.draw.rect(surface, eye_color, (px - 4*s, py + 3*s, 2*s, s))
        pygame.draw.rect(surface, eye_color, (px + 2*s, py + 3*s, 2*s, s))
        # Body
        pygame.draw.rect(surface, body_color, (px - 2*s, py - 2*s, 4*s, 4*s))
        # Belly
        pygame.draw.rect(surface, belly_color, (px - s, py - s, 2*s, 2*s))
        # Front legs
        pygame.draw.rect(surface, body_color, (px - 3*s, py - 2*s, s, 2*s))
        pygame.draw.rect(surface, body_color, (px + 2*s, py - 2*s, s, 2*s))
        # Eyes (bulging)
        pygame.draw.rect(surface, eye_color, (px - 2*s, py - 4*s, 2*s, 2*s))
        pygame.draw.rect(surface, eye_color, (px + s, py - 4*s, 2*s, 2*s))
        # Pupils (trippy spinning)
        pupil_offset = int(math.sin(t * 8) * s * 0.3)
        pygame.draw.rect(surface, (0, 0, 0), (px - 2*s + pupil_offset, py - 4*s, s, 2*s))
        pygame.draw.rect(surface, (0, 0, 0), (px + s + pupil_offset, py - 4*s, s, 2*s))
        
        # Hop animation decay
        if self.hop_anim > 0:
            self.hop_anim -= 1
    
    def draw_death(self, surface, t):
        px = self.x * CELL + CELL // 2
        py = self.y * CELL + CELL // 2 + HUD_H
        progress = self.death_timer / 40.0
        
        if self.death_type == "water":
            # Expanding ripple rings
            for i in range(4):
                r = int(progress * CELL * (i + 1) * 0.6)
                alpha = max(0, 255 - int(progress * 300))
                color = hsv_to_rgb((t * 2 + i * 0.15) % 1.0, 0.8, 1.0)
                if r > 0 and alpha > 0:
                    ring_surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                    pygame.draw.circle(ring_surf, color, (r, r), r, 2)
                    ring_surf.set_alpha(alpha)
                    surface.blit(ring_surf, (px - r, py - r))
        else:
            # Squish animation - flatten and flash
            w = int(CELL * 0.6 * (1 + progress * 2))
            h = int(CELL * 0.6 * max(0.1, 1 - progress))
            color = hsv_to_rgb((t * 10) % 1.0, 1.0, 1.0)
            pygame.draw.ellipse(surface, color, (px - w//2, py - h//2, w, h))
            # X eyes
            if progress > 0.3:
                s = 4
                for ox in [-8, 8]:
                    cx, cy = px + ox, py - 2
                    pygame.draw.line(surface, (255, 255, 255), (cx-s, cy-s), (cx+s, cy+s), 2)
                    pygame.draw.line(surface, (255, 255, 255), (cx-s, cy+s), (cx+s, cy-s), 2)


class Vehicle:
    def __init__(self, x, y, width, speed, color_hue, direction, vehicle_type="car"):
        self.x = x
        self.y = y
        self.width = width
        self.speed = speed
        self.color_hue = color_hue
        self.direction = direction  # 1 = right, -1 = left
        self.vehicle_type = vehicle_type
        self.trail_particles = []
    
    def update(self, dt):
        self.x += self.speed * self.direction * dt * 60
        # Wrap around
        if self.direction == 1 and self.x > COLS + 2:
            self.x = -self.width / CELL - 1
        elif self.direction == -1 and self.x < -self.width / CELL - 1:
            self.x = COLS + 2
        
        # Trail particles for trippy effect
        if random.random() < 0.3:
            px = (self.x * CELL) + (self.width if self.direction == -1 else 0)
            py = self.y * CELL + CELL // 2 + HUD_H
            self.trail_particles.append([px, py, 1.0])
        
        self.trail_particles = [[p[0], p[1], p[2] - 0.03] 
                                 for p in self.trail_particles if p[2] > 0]
    
    def get_rect(self):
        px = self.x * CELL
        py = self.y * CELL + HUD_H
        return pygame.Rect(px, py, self.width, CELL - 2)
    
    def draw(self, surface, t):
        rect = self.get_rect()
        # Shift hue over time for psychedelic effect
        hue = (self.color_hue + t * 0.3) % 1.0
        color = hsv_to_rgb(hue, 0.9, 1.0)
        dark = hsv_to_rgb((hue + 0.05) % 1.0, 1.0, 0.6)
        light = hsv_to_rgb((hue - 0.05) % 1.0, 0.7, 1.0)
        
        # Draw trail particles
        for p in self.trail_particles:
            alpha = max(0, int(p[2] * 150))
            pcolor = hsv_to_rgb((hue + p[2]) % 1.0, 0.8, 1.0)
            ps = pygame.Surface((6, 6))
            ps.fill(pcolor)
            ps.set_alpha(alpha)
            surface.blit(ps, (int(p[0]) - 3, int(p[1]) - 3))
        
        # Neon glow
        neon_glow(surface, rect, color, 2)
        
        # Vehicle body
        pygame.draw.rect(surface, color, rect, border_radius=4)
        # Shading
        highlight = pygame.Rect(rect.x + 3, rect.y + 3, rect.w - 6, rect.h // 3)
        pygame.draw.rect(surface, light, highlight, border_radius=2)
        # Bottom shade
        shade = pygame.Rect(rect.x + 3, rect.y + rect.h * 2 // 3, rect.w - 6, rect.h // 3 - 2)
        pygame.draw.rect(surface, dark, shade, border_radius=2)
        
        # Windows for trucks
        if self.vehicle_type == "truck":
            wx = rect.x + (rect.w - 20) // 2 if self.direction == 1 else rect.x + 8
            pygame.draw.rect(surface, dark, (wx, rect.y + 6, 16, rect.h - 12), border_radius=2)
        elif self.vehicle_type == "car":
            # Headlights
            lx = rect.right - 6 if self.direction == 1 else rect.x + 2
            pygame.draw.rect(surface, (255, 255, 200), (lx, rect.y + 8, 4, 6))
            pygame.draw.rect(surface, (255, 255, 200), (lx, rect.y + rect.h - 14, 4, 6))
        
        # Psychedlic stripe pattern
        stripe_color = hsv_to_rgb((hue + 0.5) % 1.0, 1.0, 1.0)
        for i in range(0, rect.w, 12):
            sx = rect.x + i + int(math.sin(t * 4 + i * 0.5) * 2)
            if rect.x <= sx < rect.right - 2:
                pygame.draw.line(surface, stripe_color, (sx, rect.y + 2), (sx, rect.bottom - 2), 1)


class Log:
    def __init__(self, x, y, width, speed, direction):
        self.x = x
        self.y = y
        self.width = width
        self.speed = speed
        self.direction = direction
    
    def update(self, dt):
        self.x += self.speed * self.direction * dt * 60
        if self.direction == 1 and self.x > COLS + 2:
            self.x = -self.width / CELL - 1
        elif self.direction == -1 and self.x < -self.width / CELL - 1:
            self.x = COLS + 2
    
    def get_rect(self):
        px = self.x * CELL
        py = self.y * CELL + HUD_H
        return pygame.Rect(px, py, self.width, CELL - 2)
    
    def draw(self, surface, t):
        rect = self.get_rect()
        hue = (0.08 + t * 0.15) % 1.0  # Brownish shifting
        base = hsv_to_rgb(hue, 0.6, 0.7)
        dark = hsv_to_rgb((hue + 0.02) % 1.0, 0.8, 0.4)
        light = hsv_to_rgb((hue - 0.02) % 1.0, 0.4, 0.9)
        ring_color = hsv_to_rgb((hue + 0.05) % 1.0, 0.5, 0.5)
        
        # Log body
        pygame.draw.rect(surface, base, rect, border_radius=8)
        # Top highlight
        pygame.draw.rect(surface, light, (rect.x + 4, rect.y + 2, rect.w - 8, rect.h // 3), border_radius=4)
        # Bottom shade
        pygame.draw.rect(surface, dark, (rect.x + 4, rect.y + rect.h * 2 // 3, rect.w - 8, rect.h // 3 - 2), border_radius=4)
        
        # Wood grain rings (psychedelic swirls)
        for i in range(int(rect.w // 20)):
            cx = rect.x + 10 + i * 20 + int(math.sin(t * 2 + i) * 3)
            cy = rect.centery
            r = 4 + int(math.sin(t * 3 + i * 0.7) * 2)
            pygame.draw.circle(surface, ring_color, (cx, cy), r, 1)


class TurtleGroup:
    def __init__(self, x, y, count, speed, direction):
        self.x = x
        self.y = y
        self.count = count
        self.speed = speed
        self.direction = direction
        self.dive_timer = random.uniform(5, 15)
        self.diving = False
        self.dive_phase = 0
        self.width = count * CELL * 0.8
    
    def update(self, dt):
        self.x += self.speed * self.direction * dt * 60
        if self.direction == 1 and self.x > COLS + 2:
            self.x = -self.width / CELL - 1
        elif self.direction == -1 and self.x < -self.width / CELL - 1:
            self.x = COLS + 2
        
        self.dive_timer -= dt
        if self.dive_timer <= 0 and not self.diving:
            self.diving = True
            self.dive_phase = 0
        if self.diving:
            self.dive_phase += dt * 2
            if self.dive_phase > 2.0:
                self.diving = False
                self.dive_timer = random.uniform(6, 12)
    
    def is_submerged(self):
        return self.diving and 0.5 < self.dive_phase < 1.5
    
    def get_rect(self):
        px = self.x * CELL
        py = self.y * CELL + HUD_H
        return pygame.Rect(px, py, self.width, CELL - 2)
    
    def draw(self, surface, t):
        rect = self.get_rect()
        
        if self.is_submerged():
            # Draw bubbles when submerged
            alpha = int(100 * (1 - abs(self.dive_phase - 1.0)))
            for i in range(self.count):
                bx = rect.x + i * CELL * 0.8 + CELL * 0.4
                by = rect.centery + int(math.sin(t * 4 + i * 2) * 5)
                bubble_surf = pygame.Surface((16, 16), pygame.SRCALPHA)
                bcolor = hsv_to_rgb((t + i * 0.2) % 1.0, 0.5, 1.0)
                pygame.draw.circle(bubble_surf, bcolor, (8, 8), 6, 1)
                bubble_surf.set_alpha(alpha)
                surface.blit(bubble_surf, (bx - 8, by - 8))
            return
        
        # Normal turtle drawing
        alpha_mult = 1.0
        if self.diving:
            if self.dive_phase < 0.5:
                alpha_mult = 1.0 - self.dive_phase * 2
            else:
                alpha_mult = (self.dive_phase - 1.5) * 2
            alpha_mult = max(0, min(1, alpha_mult))
        
        for i in range(self.count):
            tx = rect.x + i * CELL * 0.8 + CELL * 0.1
            ty = rect.y + 4
            tw = int(CELL * 0.7)
            th = CELL - 10
            
            hue = (0.3 + t * 0.2 + i * 0.1) % 1.0
            shell_color = hsv_to_rgb(hue, 0.7, 0.8 * alpha_mult)
            skin_color = hsv_to_rgb((hue + 0.15) % 1.0, 0.6, 0.9 * alpha_mult)
            pattern_color = hsv_to_rgb((hue + 0.3) % 1.0, 0.9, 1.0 * alpha_mult)
            
            # Shell
            pygame.draw.ellipse(surface, shell_color, (tx, ty, tw, th))
            # Shell pattern (trippy hexagonal-ish)
            cx, cy = tx + tw // 2, ty + th // 2
            for angle_offset in range(6):
                a = math.radians(angle_offset * 60 + t * 30)
                ex = cx + int(math.cos(a) * tw * 0.25)
                ey = cy + int(math.sin(a) * th * 0.25)
                pygame.draw.line(surface, pattern_color, (cx, cy), (ex, ey), 1)
            # Head
            hx = tx + tw - 2 if self.direction == 1 else tx
            pygame.draw.circle(surface, skin_color, (hx, cy), 5)


# ---------------------------------------------------------------------------
# LANE DEFINITIONS
# ---------------------------------------------------------------------------
# Row 0: Goal area
# Rows 1-5: Water (logs/turtles)
# Row 6: Safe median
# Rows 7-12: Road (vehicles)
# Row 13: Start

def create_vehicles(level, infinite=False):
    vehicles = []
    if infinite:
        # Aggressive scaling for infinite mode
        speed_mult = 1 + (level - 1) * 0.22
        extra_vehicles = min(level - 1, 8)  # More cars at higher levels
    else:
        speed_mult = 1 + (level - 1) * 0.15
        extra_vehicles = 0
    
    # Row 12 (bottom road) - slow cars right
    for i in range(3):
        v = Vehicle(i * 4.5, 12, CELL * 1.2, 0.8 * speed_mult, 0.0, 1, "car")
        vehicles.append(v)
    
    # Row 11 - race cars left (fast!)
    for i in range(3):
        v = Vehicle(i * 5, 11, CELL * 0.9, 1.5 * speed_mult, 0.65, -1, "car")
        vehicles.append(v)
    
    # Row 10 - trucks right
    for i in range(2):
        v = Vehicle(i * 7, 10, CELL * 2.2, 0.6 * speed_mult, 0.15, 1, "truck")
        vehicles.append(v)
    
    # Row 9 - cars left
    for i in range(4):
        v = Vehicle(i * 3.5, 9, CELL * 1.0, 1.0 * speed_mult, 0.45, -1, "car")
        vehicles.append(v)
    
    # Row 8 - fast cars right
    for i in range(3):
        v = Vehicle(i * 4.5, 8, CELL * 1.1, 1.3 * speed_mult, 0.8, 1, "car")
        vehicles.append(v)
    
    # Row 7 - trucks left (wide)
    for i in range(2):
        v = Vehicle(i * 8, 7, CELL * 2.5, 0.5 * speed_mult, 0.3, -1, "truck")
        vehicles.append(v)
    
    # Infinite mode: add extra vehicles on random lanes at higher levels
    if infinite and extra_vehicles > 0:
        for _ in range(extra_vehicles):
            row = random.choice([7, 8, 9, 10, 11, 12])
            direction = random.choice([-1, 1])
            vtype = random.choice(["car", "car", "car", "truck"])
            w = CELL * 1.0 if vtype == "car" else CELL * random.uniform(1.5, 2.5)
            spd = random.uniform(0.5, 1.8) * speed_mult
            hue = random.random()
            x = random.uniform(-2, COLS)
            vehicles.append(Vehicle(x, row, w, spd, hue, direction, vtype))
    
    return vehicles

def create_water_objects(level, infinite=False):
    logs = []
    turtles = []
    if infinite:
        speed_mult = 1 + (level - 1) * 0.18
        # Logs shrink at higher levels in infinite mode
        log_shrink = max(0.5, 1.0 - (level - 1) * 0.04)
        # Turtles dive more frequently
        dive_speedup = max(0.3, 1.0 - (level - 1) * 0.06)
    else:
        speed_mult = 1 + (level - 1) * 0.12
        log_shrink = 1.0
        dive_speedup = 1.0
    
    # Row 5 - short logs right
    for i in range(3):
        logs.append(Log(i * 5, 5, CELL * 2.5 * log_shrink, 0.7 * speed_mult, 1))
    
    # Row 4 - turtles left
    for i in range(3):
        tg = TurtleGroup(i * 5, 4, 3, 0.8 * speed_mult, -1)
        if infinite:
            tg.dive_timer *= dive_speedup  # Dive sooner
        turtles.append(tg)
    
    # Row 3 - long logs right
    for i in range(2):
        logs.append(Log(i * 7, 3, CELL * 3.5 * log_shrink, 0.5 * speed_mult, 1))
    
    # Row 2 - turtles right (short groups)
    for i in range(4):
        tg = TurtleGroup(i * 3.5, 2, 2, 1.0 * speed_mult, 1)
        if infinite:
            tg.dive_timer *= dive_speedup
        turtles.append(tg)
    
    # Row 1 - medium logs left
    for i in range(3):
        logs.append(Log(i * 5, 1, CELL * 2.0 * log_shrink, 0.9 * speed_mult, -1))
    
    # Infinite mode: at very high levels, remove one log/turtle group to make gaps
    if infinite and level > 5 and random.random() < 0.3:
        if logs:
            logs.pop(random.randint(0, len(logs) - 1))
    
    return logs, turtles

# ---------------------------------------------------------------------------
# GAME CLASS
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.sounds = create_sounds()
        self.high_score_classic = 0
        self.high_score_infinite = 0
        self.state = STATE_TITLE
        self.infinite_mode = False
        self.title_selection = 0  # 0 = classic, 1 = infinite
        self.title_blink = 0
        self.reset_game()
        self.time = 0
        self.stars = [(random.randint(0, W), random.randint(0, H), random.random()) 
                      for _ in range(50)]
        self.bg_stars = [(random.randint(0, W), random.randint(HUD_H, H), random.random())
                         for _ in range(80)]
        
        # Start music
        self.music_channel = pygame.mixer.Channel(0)
        self.melody_channel = pygame.mixer.Channel(1)
        self.music_channel.play(self.sounds["music"], loops=-1)
        self.melody_channel.play(self.sounds["melody"], loops=-1)
    
    def reset_game(self):
        self.level = 1
        self.infinite_mode = getattr(self, 'infinite_mode', False)
        self.lives = 3 if self.infinite_mode else 4
        self.score = 0
        self.homes_filled = [False] * GOAL_SLOTS
        self.total_homes = 0
        self.frog = Frog()
        self.vehicles = create_vehicles(self.level, self.infinite_mode)
        self.logs, self.turtles = create_water_objects(self.level, self.infinite_mode)
        self.game_over = False
        self.game_over_timer = 0
        self.level_complete_timer = 0
        self.timer_bar = 1.0
        # Infinite mode timer gets shorter each level
        self.base_timer_duration = 30.0 if not self.infinite_mode else 28.0
        self._timer_duration = self.base_timer_duration
        self.screen_shake = 0
        self.flash_timer = 0
        self.particles = []
        # Infinite mode specific
        self.combo = 0           # Consecutive successful crossings
        self.combo_mult = 1.0    # Score multiplier
        self.max_combo = 0
        self.bonus_life_threshold = 5000 if self.infinite_mode else 10000
        self.next_bonus_life = self.bonus_life_threshold
        self.intensity = 1.0     # Visual/audio intensity ramp
        self.wave_number = 0     # How many full clears in infinite
        self.infinite_streak = 0 # Levels cleared without dying
    
    def add_particles(self, x, y, count, colors):
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(50, 200)
            self.particles.append({
                'x': x, 'y': y,
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': 1.0,
                'color': random.choice(colors)
            })
    
    def update_particles(self, dt):
        for p in self.particles:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vy'] += 200 * dt  # gravity
            p['life'] -= dt * 1.5
        self.particles = [p for p in self.particles if p['life'] > 0]
    
    def draw_particles(self, surface):
        for p in self.particles:
            alpha = int(p['life'] * 255)
            size = max(1, int(p['life'] * 5))
            color = p['color']
            ps = pygame.Surface((size*2, size*2))
            ps.fill(color)
            ps.set_alpha(alpha)
            surface.blit(ps, (p['x'] - size, p['y'] - size))
    
    def goal_slot_positions(self):
        """Get x positions (in cell coords) for the 5 goal slots."""
        slots = []
        spacing = COLS / (GOAL_SLOTS + 1)
        for i in range(GOAL_SLOTS):
            slots.append(int(spacing * (i + 1)))
        return slots
    
    def kill_frog(self, death_type):
        if not self.frog.alive:
            return
        self.frog.alive = False
        self.frog.death_type = death_type
        self.frog.death_timer = 0
        self.screen_shake = 12 if self.infinite_mode else 10
        self.flash_timer = 10 if self.infinite_mode else 8
        
        # Reset combo on death
        if self.infinite_mode:
            self.combo = 0
            self.combo_mult = 1.0
            self.infinite_streak = 0
        
        px = self.frog.x * CELL + CELL // 2
        py = self.frog.y * CELL + CELL // 2 + HUD_H
        
        if death_type == "water":
            self.sounds["splash"].play()
            colors = [hsv_to_rgb(h, 1, 1) for h in [0.55, 0.6, 0.65, 0.5]]
        else:
            self.sounds["squish"].play()
            colors = [hsv_to_rgb(h, 1, 1) for h in [0.0, 0.1, 0.95, 0.85]]
        
        # More particles in infinite mode at higher intensity
        count = int(20 * self.intensity) if self.infinite_mode else 20
        self.add_particles(px, py, count, colors)
    
    def check_goal(self):
        slots = self.goal_slot_positions()
        for i, sx in enumerate(slots):
            if self.frog.x == sx and not self.homes_filled[i]:
                self.homes_filled[i] = True
                self.sounds["score"].play()
                
                # Score: base + time bonus + height bonus
                time_bonus = int(self.timer_bar * 200)
                height_bonus = (ROWS - 1 - self.frog.highest_y) * 10
                base_points = 200 + time_bonus + height_bonus
                
                # Infinite mode: combo multiplier
                if self.infinite_mode:
                    self.combo += 1
                    self.combo_mult = 1.0 + (self.combo - 1) * 0.25
                    if self.combo > self.max_combo:
                        self.max_combo = self.combo
                    base_points = int(base_points * self.combo_mult)
                
                self.score += base_points
                self.total_homes += 1
                
                # Check bonus life
                if self.score >= self.next_bonus_life:
                    self.lives += 1
                    self.next_bonus_life += self.bonus_life_threshold
                    self.sounds["level_up"].play()  # Reuse sound for extra life
                
                px = self.frog.x * CELL + CELL // 2
                py = self.frog.y * CELL + CELL // 2 + HUD_H
                colors = [hsv_to_rgb(h, 1, 1) for h in [0.15, 0.2, 0.3, 0.1]]
                pcount = int(30 * self.intensity) if self.infinite_mode else 30
                self.add_particles(px, py, pcount, colors)
                
                self.frog.reset()
                # Infinite mode: timer gets shorter each level
                if self.infinite_mode:
                    timer_dur = max(12, self.base_timer_duration - (self.level - 1) * 0.8)
                    self.timer_bar = 1.0
                    self._timer_duration = timer_dur
                else:
                    self.timer_bar = 1.0
                
                # Check level complete
                if all(self.homes_filled):
                    self.level += 1
                    level_bonus = 1000 * self.level if self.infinite_mode else 1000
                    self.score += level_bonus
                    self.homes_filled = [False] * GOAL_SLOTS
                    self.vehicles = create_vehicles(self.level, self.infinite_mode)
                    self.logs, self.turtles = create_water_objects(self.level, self.infinite_mode)
                    self.level_complete_timer = 90
                    self.sounds["level_up"].play()
                    
                    if self.infinite_mode:
                        self.wave_number += 1
                        self.infinite_streak += 1
                        # Ramp up intensity
                        self.intensity = min(3.0, 1.0 + self.level * 0.08)
                        # Extra particle burst for wave clear
                        for _ in range(5):
                            bx = random.randint(50, W - 50)
                            by = random.randint(HUD_H + 50, H - 50)
                            burst_colors = [hsv_to_rgb(h, 1, 1) for h in [random.random() for _ in range(3)]]
                            self.add_particles(bx, by, 15, burst_colors)
                return
        # If frog is in row 0 but not in a slot, or slot already filled
        if self.frog.y == 0:
            self.kill_frog("squish")
    
    def update(self, dt):
        self.time += dt
        self.title_blink += dt
        
        if self.state == STATE_TITLE:
            return
        
        if self.game_over:
            self.game_over_timer += 1
            self.update_particles(dt)
            return
        
        if self.level_complete_timer > 0:
            self.level_complete_timer -= 1
            self.update_particles(dt)
            for v in self.vehicles:
                v.update(dt)
            for l in self.logs:
                l.update(dt)
            for t in self.turtles:
                t.update(dt)
            return
        
        # Update screen shake
        if self.screen_shake > 0:
            self.screen_shake -= 1
        if self.flash_timer > 0:
            self.flash_timer -= 1
        
        self.update_particles(dt)
        
        # Update frog death
        if not self.frog.alive:
            self.frog.death_timer += 1
            if self.frog.death_timer > 40:
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True
                    self.sounds["game_over"].play()
                    if self.infinite_mode:
                        if self.score > self.high_score_infinite:
                            self.high_score_infinite = self.score
                    else:
                        if self.score > self.high_score_classic:
                            self.high_score_classic = self.score
                else:
                    self.frog.reset()
                    self.timer_bar = 1.0
            return
        
        # Timer countdown (use variable duration for infinite mode)
        timer_dur = getattr(self, '_timer_duration', 30.0)
        self.timer_bar -= dt / timer_dur
        if self.timer_bar <= 0:
            self.kill_frog("squish")
            return
        
        # Update moving objects
        for v in self.vehicles:
            v.update(dt)
        for l in self.logs:
            l.update(dt)
        for t in self.turtles:
            t.update(dt)
        
        frog_px = self.frog.pixel_pos()
        frog_rect = pygame.Rect(frog_px[0] - CELL//3, frog_px[1] - CELL//3, CELL*2//3, CELL*2//3)
        
        # Check road collisions (rows 7-12)
        if 7 <= self.frog.y <= 12:
            for v in self.vehicles:
                if frog_rect.colliderect(v.get_rect()):
                    self.kill_frog("squish")
                    return
        
        # Check water (rows 1-5)
        if 1 <= self.frog.y <= 5:
            on_platform = False
            
            # Check logs
            for l in self.logs:
                if frog_rect.colliderect(l.get_rect()):
                    on_platform = True
                    self.frog.x += l.speed * l.direction * dt * 60 / CELL * 0.7
                    break
            
            # Check turtles
            if not on_platform:
                for tg in self.turtles:
                    if tg.y == self.frog.y and not tg.is_submerged():
                        if frog_rect.colliderect(tg.get_rect()):
                            on_platform = True
                            self.frog.x += tg.speed * tg.direction * dt * 60 / CELL * 0.7
                            break
            
            if not on_platform:
                self.kill_frog("water")
                return
            
            # Check if frog went off screen while riding
            if self.frog.x < -0.5 or self.frog.x >= COLS + 0.5:
                self.kill_frog("water")
                return
        
        # Check goal row
        if self.frog.y == 0:
            self.check_goal()
    
    def draw_background(self, surface):
        t = self.time
        
        # Road rows (7-12)
        for row in range(7, 13):
            y = row * CELL + HUD_H
            hue = (0.0 + t * 0.05 + row * 0.02) % 1.0
            road_color = hsv_to_rgb(hue, 0.15, 0.15)
            surface.fill(road_color, (0, y, W, CELL))
            
            # Road markings (dashed line)
            mark_hue = (0.15 + t * 0.1) % 1.0
            mark_color = hsv_to_rgb(mark_hue, 0.8, 0.6)
            for mx in range(0, W, 30):
                offset = int(t * 20) % 30 if row % 2 == 0 else 0
                pygame.draw.rect(surface, mark_color, (mx + offset, y + CELL//2 - 1, 15, 2))
        
        # Water rows (1-5)
        for row in range(1, 6):
            y = row * CELL + HUD_H
            hue = (0.55 + t * 0.08 + row * 0.03) % 1.0
            water_color = hsv_to_rgb(hue, 0.6, 0.3)
            surface.fill(water_color, (0, y, W, CELL))
            
            # Animated water ripples
            for wx in range(0, W, 20):
                wave_y = y + CELL // 2 + int(math.sin(t * 3 + wx * 0.05 + row) * 4)
                ripple_hue = (hue + 0.05) % 1.0
                ripple_color = hsv_to_rgb(ripple_hue, 0.5, 0.5)
                pygame.draw.circle(surface, ripple_color, (wx, wave_y), 2)
        
        # Safe median (row 6)
        y = 6 * CELL + HUD_H
        median_hue = (0.25 + t * 0.1) % 1.0
        median_color = hsv_to_rgb(median_hue, 0.5, 0.2)
        surface.fill(median_color, (0, y, W, CELL))
        
        # Draw some trippy flowers/bushes on median
        for i in range(6):
            fx = i * (W // 6) + W // 12
            fy = y + CELL // 2
            flower_hue = (t * 0.5 + i * 0.2) % 1.0
            fc = hsv_to_rgb(flower_hue, 0.9, 1.0)
            petal_r = 5 + int(math.sin(t * 3 + i) * 2)
            for pa in range(5):
                a = math.radians(pa * 72 + t * 20)
                px = fx + int(math.cos(a) * petal_r)
                py = fy + int(math.sin(a) * petal_r)
                pygame.draw.circle(surface, fc, (px, py), 3)
            pygame.draw.circle(surface, hsv_to_rgb((flower_hue + 0.3) % 1, 1, 1), (fx, fy), 2)
        
        # Start area (row 13)
        y = 13 * CELL + HUD_H
        start_hue = (0.25 + t * 0.07) % 1.0
        start_color = hsv_to_rgb(start_hue, 0.4, 0.2)
        surface.fill(start_color, (0, y, W, CELL))
        
        # Goal area (row 0)
        y = HUD_H
        goal_hue = (0.3 + t * 0.12) % 1.0
        goal_color = hsv_to_rgb(goal_hue, 0.5, 0.15)
        surface.fill(goal_color, (0, y, W, CELL))
        
        # Draw goal slots
        slots = self.goal_slot_positions()
        for i, sx in enumerate(slots):
            gx = sx * CELL
            if self.homes_filled[i]:
                # Filled - show a frog
                filled_hue = (t * 1.5 + i * 0.3) % 1.0
                fc = hsv_to_rgb(filled_hue, 0.9, 1.0)
                pygame.draw.rect(surface, fc, (gx + 4, y + 4, CELL - 8, CELL - 8), border_radius=6)
                # Little frog face
                pygame.draw.circle(surface, (255, 255, 255), (gx + CELL//2 - 6, y + CELL//3), 4)
                pygame.draw.circle(surface, (255, 255, 255), (gx + CELL//2 + 6, y + CELL//3), 4)
                pygame.draw.circle(surface, (0, 0, 0), (gx + CELL//2 - 6, y + CELL//3), 2)
                pygame.draw.circle(surface, (0, 0, 0), (gx + CELL//2 + 6, y + CELL//3), 2)
            else:
                # Empty slot - glowing opening
                slot_hue = (t * 0.8 + i * 0.2) % 1.0
                sc = hsv_to_rgb(slot_hue, 0.8, 0.6)
                neon_glow(surface, pygame.Rect(gx + 2, y + 2, CELL - 4, CELL - 4), sc, 1)
                pygame.draw.rect(surface, sc, (gx + 6, y + 6, CELL - 12, CELL - 12), border_radius=4)
        
        # Draw psychedelic stars/sparkles in background
        for sx, sy, phase in self.stars:
            brightness = (math.sin(t * 2 + phase * 10) + 1) / 2
            if brightness > 0.7:
                star_hue = (t * 0.3 + phase) % 1.0
                sc = hsv_to_rgb(star_hue, 0.5, brightness)
                size = 1 + int(brightness * 2)
                pygame.draw.rect(surface, sc, (sx, sy, size, size))
    
    def draw_hud(self, surface):
        # HUD background
        hud_hue = (self.time * 0.1) % 1.0
        hud_bg = hsv_to_rgb(hud_hue, 0.3, 0.08)
        surface.fill(hud_bg, (0, 0, W, HUD_H))
        
        # Score
        score_color = hsv_to_rgb((self.time * 0.5) % 1.0, 0.7, 1.0)
        score_text = font_med.render(f"SCORE: {self.score}", True, score_color)
        surface.blit(score_text, (10, 5))
        
        # High score
        hi = self.high_score_infinite if self.infinite_mode else self.high_score_classic
        hi_color = hsv_to_rgb((self.time * 0.5 + 0.3) % 1.0, 0.7, 1.0)
        hi_text = font_sm.render(f"HI: {hi}", True, hi_color)
        surface.blit(hi_text, (10, 28))
        
        # Level
        lvl_color = hsv_to_rgb((self.time * 0.5 + 0.6) % 1.0, 0.7, 1.0)
        lvl_text = font_med.render(f"LV:{self.level}", True, lvl_color)
        surface.blit(lvl_text, (W // 2 - 30, 5))
        
        # Infinite mode: combo multiplier display
        if self.infinite_mode and self.combo > 1:
            combo_hue = (self.time * 3) % 1.0
            combo_color = hsv_to_rgb(combo_hue, 0.9, 1.0)
            pulse = 1.0 + 0.2 * math.sin(self.time * 8)
            combo_text = font_med.render(f"x{self.combo_mult:.2f}", True, combo_color)
            # Draw with slight size pulse via position wiggle
            cx = W // 2 - combo_text.get_width() // 2
            cy = int(28 + math.sin(self.time * 6) * 2)
            surface.blit(combo_text, (cx, cy))
        
        # Mode indicator
        if self.infinite_mode:
            mode_color = hsv_to_rgb((self.time * 2) % 1.0, 0.8, 1.0)
            mode_text = font_sm.render("INFINITE", True, mode_color)
            surface.blit(mode_text, (W // 2 + 25, 28))
        
        # Lives (as frog icons)
        for i in range(min(self.lives, 10)):  # Cap display at 10
            lx = W - 30 - i * 28
            frog_hue = (self.time + i * 0.2) % 1.0
            fc = hsv_to_rgb(frog_hue, 0.9, 1.0)
            pygame.draw.rect(surface, fc, (lx, 10, 16, 16), border_radius=3)
            pygame.draw.circle(surface, (255, 255, 255), (lx + 5, 8), 3)
            pygame.draw.circle(surface, (255, 255, 255), (lx + 12, 8), 3)
        if self.lives > 10:
            extra_color = hsv_to_rgb((self.time * 0.5) % 1.0, 0.7, 1.0)
            extra_text = font_sm.render(f"+{self.lives - 10}", True, extra_color)
            surface.blit(extra_text, (W - 30 - 10 * 28 - 15, 10))
        
        # Timer bar
        bar_x, bar_y = W // 2 - 50, 30
        bar_w, bar_h = 100, 12
        pygame.draw.rect(surface, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        
        if self.timer_bar > 0.3:
            bar_hue = (0.3 + self.timer_bar * 0.3) % 1.0
        else:
            bar_hue = 0.0  # Red when low
        bar_color = hsv_to_rgb(bar_hue, 0.9, 1.0)
        fill_w = int(bar_w * max(0, self.timer_bar))
        if fill_w > 0:
            pygame.draw.rect(surface, bar_color, (bar_x, bar_y, fill_w, bar_h), border_radius=3)
        
        # Pulsing border on timer when low
        if self.timer_bar < 0.3 and int(self.time * 6) % 2:
            pygame.draw.rect(surface, (255, 0, 0), (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2), 1, border_radius=3)
    
    def draw_game_over(self, surface):
        # Dark overlay
        overlay = pygame.Surface((W, H))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(150)
        surface.blit(overlay, (0, 0))
        
        t = self.time
        hi = self.high_score_infinite if self.infinite_mode else self.high_score_classic
        is_new_hs = self.score >= hi and self.score > 0
        
        # Game over text
        for i, ch in enumerate("GAME OVER"):
            hue = (t * 2 + i * 0.1) % 1.0
            color = hsv_to_rgb(hue, 0.9, 1.0)
            y_off = int(math.sin(t * 4 + i * 0.5) * 8)
            ch_surf = font_big.render(ch, True, color)
            x = W // 2 - 100 + i * 22
            surface.blit(ch_surf, (x, H // 2 - 80 + y_off))
        
        # Mode label
        mode_label = "INFINITE MODE" if self.infinite_mode else "CLASSIC MODE"
        mode_color = hsv_to_rgb((t * 0.5 + 0.5) % 1, 0.7, 1.0)
        mode_surf = font_sm.render(mode_label, True, mode_color)
        surface.blit(mode_surf, (W // 2 - mode_surf.get_width() // 2, H // 2 - 50))
        
        # Score
        score_text = font_med.render(f"FINAL SCORE: {self.score}", True, 
                                      hsv_to_rgb((t * 0.5) % 1, 0.8, 1.0))
        surface.blit(score_text, (W // 2 - score_text.get_width() // 2, H // 2 - 25))
        
        if is_new_hs:
            hs_text = font_med.render("NEW HIGH SCORE!", True,
                                       hsv_to_rgb((t * 3) % 1, 0.9, 1.0))
            surface.blit(hs_text, (W // 2 - hs_text.get_width() // 2, H // 2 + 5))
        
        # Infinite mode stats
        if self.infinite_mode:
            stats_y = H // 2 + 35
            stat_color = hsv_to_rgb((t * 0.4) % 1, 0.6, 0.9)
            
            stats = [
                f"LEVEL REACHED: {self.level}",
                f"WAVES CLEARED: {self.wave_number}",
                f"HOMES FILLED: {self.total_homes}",
                f"MAX COMBO: {self.max_combo}x",
                f"BEST STREAK: {self.infinite_streak}",
            ]
            for i, stat in enumerate(stats):
                st = font_sm.render(stat, True, stat_color)
                surface.blit(st, (W // 2 - st.get_width() // 2, stats_y + i * 20))
        
        if self.game_over_timer > 60:
            restart_text = font_med.render("PRESS ENTER FOR TITLE", True,
                                            hsv_to_rgb((t * 0.7) % 1, 0.7, 1.0))
            if int(t * 2) % 2:
                surface.blit(restart_text, (W // 2 - restart_text.get_width() // 2, H // 2 + 150))
    
    def draw_title(self, surface):
        t = self.time
        
        # Trippy animated background
        for y in range(0, H, 4):
            hue = (t * 0.15 + y * 0.003) % 1.0
            color = hsv_to_rgb(hue, 0.4, 0.08)
            surface.fill(color, (0, y, W, 4))
        
        # Animated stars
        for sx, sy, phase in self.bg_stars:
            brightness = (math.sin(t * 2 + phase * 10) + 1) / 2
            if brightness > 0.6:
                star_hue = (t * 0.3 + phase) % 1.0
                sc = hsv_to_rgb(star_hue, 0.5, brightness)
                size = 1 + int(brightness * 2)
                pygame.draw.rect(surface, sc, (sx, sy, size, size))
        
        # Title - "PSYCHEDELIC FROGGER" with wave effect
        title = "PSYCHEDELIC"
        for i, ch in enumerate(title):
            hue = (t * 1.5 + i * 0.06) % 1.0
            color = hsv_to_rgb(hue, 0.9, 1.0)
            y_off = int(math.sin(t * 3 + i * 0.4) * 10)
            ch_surf = font_title.render(ch, True, color)
            x = W // 2 - len(title) * 12 + i * 24
            surface.blit(ch_surf, (x, 80 + y_off))
        
        # Subtitle
        sub = "FROGGER"
        for i, ch in enumerate(sub):
            hue = (t * 2 + i * 0.1 + 0.5) % 1.0
            color = hsv_to_rgb(hue, 0.85, 1.0)
            y_off = int(math.sin(t * 4 + i * 0.5 + 1) * 6)
            ch_surf = font_title.render(ch, True, color)
            x = W // 2 - len(sub) * 13 + i * 26
            surface.blit(ch_surf, (x, 130 + y_off))
        
        # Decorative frog
        frog_y = 210 + int(math.sin(t * 2) * 5)
        frog_hue = (t * 0.8) % 1.0
        fc = hsv_to_rgb(frog_hue, 0.9, 1.0)
        ecx = hsv_to_rgb((frog_hue + 0.3) % 1, 1, 1)
        # Pixelated frog
        pygame.draw.rect(surface, fc, (W//2 - 16, frog_y, 32, 24), border_radius=6)
        pygame.draw.rect(surface, fc, (W//2 - 24, frog_y + 6, 12, 12), border_radius=3)
        pygame.draw.rect(surface, fc, (W//2 + 12, frog_y + 6, 12, 12), border_radius=3)
        pygame.draw.circle(surface, ecx, (W//2 - 8, frog_y - 4), 6)
        pygame.draw.circle(surface, ecx, (W//2 + 8, frog_y - 4), 6)
        pygame.draw.circle(surface, (0, 0, 0), (W//2 - 8, frog_y - 4), 3)
        pygame.draw.circle(surface, (0, 0, 0), (W//2 + 8, frog_y - 4), 3)
        # Glow
        neon_glow(surface, pygame.Rect(W//2 - 24, frog_y - 10, 48, 44), fc, 2)
        
        # Mode selection
        sel_y = 300
        modes = [
            ("CLASSIC", "Standard lives & scoring", "HI: " + str(self.high_score_classic)),
            ("INFINITE", "Endless escalation & combos", "HI: " + str(self.high_score_infinite)),
        ]
        
        header_color = hsv_to_rgb((t * 0.3) % 1, 0.6, 0.9)
        header = font_med.render("SELECT MODE", True, header_color)
        surface.blit(header, (W // 2 - header.get_width() // 2, sel_y - 30))
        
        for i, (name, desc, hi) in enumerate(modes):
            y = sel_y + i * 80
            selected = self.title_selection == i
            
            if selected:
                # Selected highlight
                sel_hue = (t * 2) % 1.0
                sel_color = hsv_to_rgb(sel_hue, 0.8, 0.3)
                pygame.draw.rect(surface, sel_color, (W//2 - 180, y - 5, 360, 65), border_radius=8)
                neon_glow(surface, pygame.Rect(W//2 - 178, y - 3, 356, 61), 
                         hsv_to_rgb(sel_hue, 0.9, 1.0), 2)
                # Arrow indicator
                if int(t * 4) % 2:
                    arrow_color = hsv_to_rgb((t * 3) % 1, 0.9, 1.0)
                    arrow = font_med.render(">", True, arrow_color)
                    surface.blit(arrow, (W//2 - 200, y + 10))
                    arrow2 = font_med.render("<", True, arrow_color)
                    surface.blit(arrow2, (W//2 + 175, y + 10))
            
            # Mode name
            name_hue = (t * 1.5 + i * 0.4) % 1.0 if selected else 0.0
            name_color = hsv_to_rgb(name_hue, 0.9 if selected else 0.3, 1.0 if selected else 0.5)
            name_surf = font_big.render(name, True, name_color)
            surface.blit(name_surf, (W // 2 - name_surf.get_width() // 2, y))
            
            # Description
            desc_color = hsv_to_rgb((t * 0.3 + i * 0.2) % 1, 0.5, 0.7 if selected else 0.4)
            desc_surf = font_sm.render(desc, True, desc_color)
            surface.blit(desc_surf, (W // 2 - desc_surf.get_width() // 2, y + 30))
            
            # High score
            hi_color = hsv_to_rgb((t * 0.4 + i * 0.3) % 1, 0.6, 0.8 if selected else 0.5)
            hi_surf = font_sm.render(hi, True, hi_color)
            surface.blit(hi_surf, (W // 2 - hi_surf.get_width() // 2, y + 47))
        
        # Controls
        ctrl_y = H - 70
        if int(t * 1.5) % 2:
            ctrl_color = hsv_to_rgb((t * 0.5) % 1, 0.5, 0.7)
            ctrl1 = font_sm.render("UP/DOWN to select  |  ENTER to start", True, ctrl_color)
            surface.blit(ctrl1, (W // 2 - ctrl1.get_width() // 2, ctrl_y))
        ctrl2_color = hsv_to_rgb((t * 0.3) % 1, 0.4, 0.5)
        ctrl2 = font_sm.render("WASD or Arrows to move  |  ESC to quit", True, ctrl2_color)
        surface.blit(ctrl2, (W // 2 - ctrl2.get_width() // 2, ctrl_y + 22))
    
    def draw_level_complete(self, surface):
        if self.level_complete_timer <= 0:
            return
        overlay = pygame.Surface((W, H))
        alpha = min(150, self.level_complete_timer * 5)
        overlay.fill((0, 0, 0))
        overlay.set_alpha(alpha)
        surface.blit(overlay, (0, 0))
        
        t = self.time
        if self.infinite_mode:
            text = f"WAVE {self.wave_number + 1} INCOMING!"
        else:
            text = f"LEVEL {self.level - 1} COMPLETE!"
        for i, ch in enumerate(text):
            hue = (t * 3 + i * 0.08) % 1.0
            color = hsv_to_rgb(hue, 0.9, 1.0)
            y_off = int(math.sin(t * 5 + i * 0.4) * 6)
            ch_surf = font_big.render(ch, True, color)
            x = W // 2 - len(text) * 11 + i * 22
            surface.blit(ch_surf, (x, H // 2 - 20 + y_off))
        
        # Infinite mode: show combo bonus
        if self.infinite_mode and self.combo > 1:
            combo_text = font_med.render(f"COMBO x{self.combo_mult:.1f} ACTIVE!", True,
                                          hsv_to_rgb((t * 4) % 1, 0.9, 1.0))
            surface.blit(combo_text, (W // 2 - combo_text.get_width() // 2, H // 2 + 25))
    
    def draw(self, surface):
        if self.state == STATE_TITLE:
            self.draw_title(surface)
            return
        
        # Create a buffer for potential screen shake
        buffer = pygame.Surface((W, H))
        
        # Background
        self.draw_background(buffer)
        
        # Water objects (logs and turtles)
        for l in self.logs:
            l.draw(buffer, self.time)
        for tg in self.turtles:
            tg.draw(buffer, self.time)
        
        # Vehicles
        for v in self.vehicles:
            v.draw(buffer, self.time)
        
        # Frog
        if self.frog.alive:
            self.frog.draw(buffer, self.time)
        else:
            self.frog.draw_death(buffer, self.time)
        
        # Particles
        self.draw_particles(buffer)
        
        # Flash effect on death
        if self.flash_timer > 0:
            flash = pygame.Surface((W, H))
            flash_alpha = int(self.flash_timer / 8 * 100)
            flash.fill((255, 255, 255))
            flash.set_alpha(flash_alpha)
            buffer.blit(flash, (0, 0))
        
        # Screen shake (stronger in infinite mode at high intensity)
        shake_amount = self.screen_shake
        if self.infinite_mode:
            shake_amount = int(shake_amount * self.intensity)
        shake_x = random.randint(-shake_amount, shake_amount) if shake_amount else 0
        shake_y = random.randint(-shake_amount, shake_amount) if shake_amount else 0
        surface.fill((0, 0, 0))
        surface.blit(buffer, (shake_x, shake_y))
        
        # HUD (no shake)
        self.draw_hud(surface)
        
        # Overlays
        if self.game_over:
            self.draw_game_over(surface)
        self.draw_level_complete(surface)
    
    def handle_input(self, event):
        if event.type != pygame.KEYDOWN:
            return
        
        # Title screen
        if self.state == STATE_TITLE:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.title_selection = (self.title_selection - 1) % 2
                self.sounds["hop"].play()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.title_selection = (self.title_selection + 1) % 2
                self.sounds["hop"].play()
            elif event.key == pygame.K_RETURN:
                self.infinite_mode = (self.title_selection == 1)
                self.state = STATE_PLAYING
                self.reset_game()
                self.sounds["level_up"].play()
            return
        
        if self.game_over:
            if event.key == pygame.K_RETURN:
                self.state = STATE_TITLE
                self.game_over = False
                self.game_over_timer = 0
                self.title_selection = 0
            return
        
        if not self.frog.alive or self.level_complete_timer > 0:
            return
        
        moved = False
        if event.key in (pygame.K_UP, pygame.K_w):
            moved = self.frog.move(0, -1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            moved = self.frog.move(0, 1)
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            moved = self.frog.move(-1, 0)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            moved = self.frog.move(1, 0)
        
        if moved:
            self.sounds["hop"].play()

# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------
def main():
    game = Game()
    running = True
    
    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)  # Cap delta time
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if game.state == STATE_TITLE:
                    running = False
                else:
                    game.state = STATE_TITLE
                    game.game_over = False
                    game.title_selection = 0
            else:
                game.handle_input(event)
        
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()