from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

from fetch_followers import get_followers, download_profile_pics
from fight_simulation import update_scoreboard


WIDTH = 1080
HEIGHT = 1920
FPS = 30
SPRITE_SIZE = 128
PROFILE_DIR = Path("follower_pp")
BATTLES_DIR = Path("battles")
MAX_FIGHTERS = 50


@dataclass
class Sprite:
    username: str
    image: Image.Image
    x: float
    y: float
    vx: float
    vy: float
    health: float = 100.0
    alive: bool = True
    death_frame: int | None = None


def load_avatar(username: str) -> Image.Image:
    path = PROFILE_DIR / f"{username}.jpg"
    if path.exists():
        img = Image.open(path).convert("RGBA")
    else:
        img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (200, 200, 200, 255))
    return img.resize((SPRITE_SIZE, SPRITE_SIZE), Image.LANCZOS)


def create_sprites(followers) -> List[Sprite]:
    selected = followers[:MAX_FIGHTERS]
    sprites: List[Sprite] = []
    margin = 80
    for f in selected:
        username = getattr(f, "username", None)
        img = load_avatar(username or "unknown")
        x = random.uniform(margin, WIDTH - margin - SPRITE_SIZE)
        y = random.uniform(margin, HEIGHT - margin - SPRITE_SIZE - 200)
        vx = float(random.choice([-8, -7, -6, -5, 5, 6, 7, 8]))
        vy = float(random.choice([-8, -7, -6, -5, 5, 6, 7, 8]))
        sprites.append(Sprite(username or "", img, x, y, vx, vy))
    return sprites


def move_sprites(sprites: List[Sprite]) -> None:
    for s in sprites:
        if not s.alive:
            continue
        s.x += s.vx
        s.y += s.vy
        if s.x < 0:
            s.x = 0
            s.vx = -s.vx
        if s.x + SPRITE_SIZE > WIDTH:
            s.x = WIDTH - SPRITE_SIZE
            s.vx = -s.vx
        if s.y < 0:
            s.y = 0
            s.vy = -s.vy
        if s.y + SPRITE_SIZE > HEIGHT - 200:
            s.y = HEIGHT - 200 - SPRITE_SIZE
            s.vy = -s.vy


def collides(a: Sprite, b: Sprite) -> bool:
    ax1, ay1 = a.x, a.y
    ax2, ay2 = a.x + SPRITE_SIZE, a.y + SPRITE_SIZE
    bx1, by1 = b.x, b.y
    bx2, by2 = b.x + SPRITE_SIZE, b.y + SPRITE_SIZE
    overlap_x = ax1 < bx2 and ax2 > bx1
    overlap_y = ay1 < by2 and ay2 > by1
    return overlap_x and overlap_y


def apply_collisions(sprites: List[Sprite], frame_idx: int) -> None:
    alive_indices = [i for i, s in enumerate(sprites) if s.alive]
    n = len(alive_indices)
    for i in range(n):
        for j in range(i + 1, n):
            a = sprites[alive_indices[i]]
            b = sprites[alive_indices[j]]
            if not a.alive or not b.alive:
                continue
            if collides(a, b):
                damage_a = random.randint(5, 30)
                damage_b = random.randint(5, 30)
                a.health -= damage_b
                b.health -= damage_a
                if a.health <= 0 and a.alive:
                    a.alive = False
                    a.death_frame = frame_idx
                if b.health <= 0 and b.alive:
                    b.alive = False
                    b.death_frame = frame_idx


def draw_frame(sprites: List[Sprite], winner: str | None) -> np.ndarray:
    img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    for s in sprites:
        if not s.alive:
            continue
        img.paste(s.image, (int(s.x), int(s.y)), s.image)
        bar_w, bar_h = SPRITE_SIZE, 12
        bar_x, bar_y = int(s.x), int(s.y + SPRITE_SIZE + 5)
        hp_ratio = max(0.0, min(1.0, s.health / 100.0))
        hp_w = int(bar_w * hp_ratio)
        draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(60, 60, 60))
        draw.rectangle([bar_x, bar_y, bar_x + hp_w, bar_y + bar_h], fill=(0, 200, 0))

    if winner is not None:
        text = f"WINNER: {winner}"
        font = ImageFont.load_default()
        # compute bounding box instead of using textsize (removed in Pillow 10+)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = right - left, bottom - top
        tx = (WIDTH - text_w) // 2
        ty = HEIGHT // 2 - text_h // 2
        draw.rectangle([tx - 20, ty - 20, tx + text_w + 20, ty + text_h + 20], fill=(0, 0, 0))
        draw.text((tx, ty), text, font=font, fill=(255, 215, 0))

    return np.array(img)

def build_ranking(sprites: List[Sprite], total_frames: int) -> List[Dict[str, object]]:
    alive = [s for s in sprites if s.alive]
    if len(alive) > 1:
        alive_sorted = sorted(alive, key=lambda s: s.health)
        for i, s in enumerate(alive_sorted):
            s.death_frame = total_frames + i
    for s in sprites:
        if s.death_frame is None:
            s.death_frame = -1
    sorted_sprites = sorted(sprites, key=lambda s: s.death_frame, reverse=True)
    ranking: List[Dict[str, object]] = []
    for order, s in enumerate(sorted_sprites, start=1):
        ranking.append({"username": s.username, "profile_pic": str(PROFILE_DIR / f"{s.username}.jpg"), "order": order, "final_health": s.health})
    return ranking


def simulate_and_record(followers) -> List[Dict[str, object]]:
    sprites = create_sprites(followers)
    frames: List[np.ndarray] = []
    winner_name: str | None = None
    frame_idx = 0
    max_frames = FPS * 60
    while frame_idx < max_frames:
        move_sprites(sprites)
        apply_collisions(sprites, frame_idx)
        alive = [s for s in sprites if s.alive]
        if len(alive) <= 1:
            if alive:
                winner_name = alive[0].username
            frame = draw_frame(sprites, winner_name)
            for _ in range(FPS * 3):
                frames.append(frame.copy())
            break
        frame = draw_frame(sprites, None)
        frames.append(frame)
        frame_idx += 1
    if not frames:
        frames.append(draw_frame(sprites, None))
    clip = ImageSequenceClip(frames, fps=FPS)
    BATTLES_DIR.mkdir(exist_ok=True)
    existing = sorted([p for p in BATTLES_DIR.iterdir() if p.name.startswith("battle_") and p.suffix == ".mp4"])
    next_index = len(existing) + 1
    file_path = BATTLES_DIR / f"battle_{next_index}.mp4"
    clip.write_videofile(str(file_path), codec="libx264", audio=False, fps=FPS)
    ranking = build_ranking(sprites, len(frames))
    update_scoreboard(ranking, "scoreboard.json")
    return ranking


def run_battle() -> None:
    followers = get_followers()
    PROFILE_DIR.mkdir(exist_ok=True)
    download_profile_pics(followers, PROFILE_DIR, skip_existing=True)
    simulate_and_record(followers)


if __name__ == "__main__":
    run_battle()