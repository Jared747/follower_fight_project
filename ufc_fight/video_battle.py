from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from moviepy.editor import AudioFileClip
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

from .cosmetics import apply_mask_to_avatar
from .followers import Follower, download_profile_pics, get_followers
from .scoreboard import update_scoreboard
from .settings import Settings, get_settings
from .stats import update_stats_with_battle
from .storage import load_json, save_json


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
    last_hit_frame: int = -999
    base_image: Image.Image | None = None
    effect_name: str = ""


@dataclass
class BattleOutcome:
    ranking: List[Dict[str, object]]
    video_path: Path
    frames: int


@dataclass
class BattleConfig:
    width: int = 1080
    height: int = 1920
    arena_vertical_scale: float = 0.82
    fps: int = 30
    max_fighters: int = 50
    restitution: float = 0.85
    collision_cooldown_frames: int = 6
    min_damage: int = 5
    max_damage: int = 14
    win_hold_seconds: int = 5
    min_size_factor: float = 0.78
    max_size_factor: float = 1.35
    early_damage_scale: float = 0.5
    late_damage_scale: float = 1.0


class VideoFightSimulator:
    """Visual, physics-driven fight simulator that renders a video."""

    def __init__(self, settings: Settings | None = None, config: BattleConfig | None = None) -> None:
        self.settings = settings or get_settings()
        self.config = config or BattleConfig()
        self.octagon_center_y = (self.config.height - 120) / 2
        arena_height = self.config.width * self.config.arena_vertical_scale
        max_arena_height = max(400.0, self.config.height - 240.0)
        self.arena_height = max(320.0, min(arena_height, max_arena_height))
        self.arena_top = self.octagon_center_y - self.arena_height / 2
        self.arena_bottom = self.octagon_center_y + self.arena_height / 2
        self.sprite_size = 128
        self.sprite_radius = self.sprite_size / 2
        self.sprite_min_size = self.sprite_size
        self.sprite_max_size = self.sprite_size
        self.starting_fighters = 0
        self.background: Image.Image | None = None
        self.circle_mask: Image.Image | None = None
        self.damage_log: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.custom_cache: Dict[str, Dict[str, List[str]]] = {}
        self.battle_number: int | None = None
        self.fighter_count: int = 0

    def run(self, followers: List[Follower]) -> BattleOutcome:
        if not followers:
            raise ValueError("No followers provided for the fight.")

        self.damage_log.clear()
        self.custom_cache.clear()
        self.background = None
        self.circle_mask = None
        self.battle_number = self._next_battle_number()

        self._set_sprite_geometry(len(followers))
        sprites = self._create_sprites(followers)
        frames, winner = self._simulate_frames(sprites)
        video_path = self._write_video(frames)
        ranking = self._build_ranking(sprites, len(frames))

        self._backup_run_state()
        update_scoreboard(ranking, self.settings.scoreboard_path)
        update_stats_with_battle(ranking, self.damage_log, self.settings.stats_path)
        save_json(self.settings.last_run_damage_path, self.damage_log)
        save_json(self.settings.last_run_path, ranking)

        return BattleOutcome(ranking=ranking, video_path=video_path, frames=len(frames))

    # Simulation lifecycle -------------------------------------------------

    def _simulate_frames(self, sprites: List[Sprite]) -> Tuple[List[np.ndarray], Sprite | None]:
        frames: List[np.ndarray] = []
        winner_sprite: Sprite | None = None
        frame_idx = 0
        collision_memory: Dict[tuple, int] = {}

        while True:
            alive_count = sum(1 for sprite in sprites if sprite.alive)
            self._update_sprite_size(alive_count, sprites)
            self._move_sprites(sprites, alive_count)
            self._apply_collisions(sprites, frame_idx, collision_memory)
            alive = [sprite for sprite in sprites if sprite.alive]

            if len(alive) <= 1:
                self._update_sprite_size(len(alive), sprites)
                if alive:
                    winner_sprite = alive[0]
                    winner_sprite.alive = False  # hide in-world sprite, only show champion card
                hold_frames = self.config.fps * self.config.win_hold_seconds
                for hold_idx in range(hold_frames):
                    frame = self._draw_frame(sprites, winner_sprite, frame_idx + hold_idx)
                    frames.append(frame)
                break

            frame = self._draw_frame(sprites, None, frame_idx)
            frames.append(frame)
            frame_idx += 1

        if not frames:
            frames.append(self._draw_frame(sprites, None, frame_idx))

        return frames, winner_sprite

    def _create_sprites(self, followers: List[Follower]) -> List[Sprite]:
        selected = followers[: self.config.max_fighters]
        self.fighter_count = len(selected)
        sprites: List[Sprite] = []
        margin = 80
        for follower in selected:
            username = getattr(follower, "username", None) or "unknown"
            base_avatar = self._load_avatar(username, size=self.sprite_max_size)
            avatar = self._scale_avatar(base_avatar, self.sprite_size)
            x = random.uniform(margin, self.config.width - margin - self.sprite_size)
            y = random.uniform(self.arena_top + margin, self.arena_bottom - margin - self.sprite_size)
            speed_mag = max(3, min(12, int(0.06 * self.sprite_size)))
            speeds = list(range(-speed_mag, -5)) + list(range(6, speed_mag + 1))
            vx = float(random.choice(speeds))
            vy = float(random.choice(speeds))
            effect_name = self._active_effect(username)
            sprites.append(
                Sprite(
                    username=username,
                    image=avatar,
                    x=x,
                    y=y,
                    vx=vx,
                    vy=vy,
                    base_image=base_avatar,
                    effect_name=effect_name,
                )
            )
        return sprites

    def _move_sprites(self, sprites: List[Sprite], alive_count: int) -> None:
        min_speed, max_speed = self._speed_bounds(alive_count)
        for sprite in sprites:
            if not sprite.alive:
                continue
            self._enforce_speed_bounds(sprite, min_speed, max_speed)
            sprite.x += sprite.vx
            sprite.y += sprite.vy
            self._clamp_sprite(sprite)

    def _apply_collisions(self, sprites: List[Sprite], frame_idx: int, collision_memory: Dict[tuple, int]) -> None:
        alive_indices = [i for i, sprite in enumerate(sprites) if sprite.alive]
        total_alive = len(alive_indices)
        for i in range(total_alive):
            for j in range(i + 1, total_alive):
                a = sprites[alive_indices[i]]
                b = sprites[alive_indices[j]]
                if not a.alive or not b.alive:
                    continue
                key = tuple(sorted((id(a), id(b))))
                if not self._collides(a, b):
                    collision_memory.pop(key, None)
                    continue

                self._resolve_collision(a, b)
                last_frame = collision_memory.get(key, -999)
                if frame_idx - last_frame >= self.config.collision_cooldown_frames:
                    self._apply_damage(a, b, frame_idx, total_alive)
                    collision_memory[key] = frame_idx

    # Physics utilities ----------------------------------------------------

    def _speed_bounds(self, alive_count: int) -> Tuple[float, float]:
        base_floor = max(3.0, 0.05 * self.sprite_size)
        if alive_count <= 2:
            boost = 4.5
        elif alive_count <= 3:
            boost = 3.5
        elif alive_count <= 5:
            boost = 2.0
        else:
            boost = 0.0
        min_speed = base_floor + boost
        max_speed = max(min_speed + 3.0, min_speed * 1.4)
        return min_speed, max_speed

    def _enforce_speed_bounds(self, sprite: Sprite, min_speed: float, max_speed: float) -> None:
        speed = math.hypot(sprite.vx, sprite.vy)
        if speed < 1e-5:
            angle = random.uniform(0, 2 * math.pi)
            sprite.vx = math.cos(angle) * min_speed
            sprite.vy = math.sin(angle) * min_speed
            return
        if speed < min_speed:
            scale = min_speed / speed
            sprite.vx *= scale
            sprite.vy *= scale
        elif speed > max_speed:
            scale = max_speed / speed
            sprite.vx *= scale
            sprite.vy *= scale

    def _clamp_sprite(self, sprite: Sprite) -> None:
        if sprite.x < 0:
            sprite.x = 0
            sprite.vx = abs(sprite.vx)
        if sprite.x + self.sprite_size > self.config.width:
            sprite.x = self.config.width - self.sprite_size
            sprite.vx = -abs(sprite.vx)
        if sprite.y < self.arena_top:
            sprite.y = self.arena_top
            sprite.vy = abs(sprite.vy)
        if sprite.y + self.sprite_size > self.arena_bottom:
            sprite.y = self.arena_bottom - self.sprite_size
            sprite.vy = -abs(sprite.vy)

    def _collides(self, a: Sprite, b: Sprite) -> bool:
        ax, ay = a.x + self.sprite_radius, a.y + self.sprite_radius
        bx, by = b.x + self.sprite_radius, b.y + self.sprite_radius
        dx = ax - bx
        dy = ay - by
        distance_sq = dx * dx + dy * dy
        min_dist = self.sprite_size
        return distance_sq < (min_dist * min_dist)

    def _resolve_collision(self, a: Sprite, b: Sprite) -> None:
        ax, ay = a.x + self.sprite_radius, a.y + self.sprite_radius
        bx, by = b.x + self.sprite_radius, b.y + self.sprite_radius
        dx = ax - bx
        dy = ay - by
        dist = math.hypot(dx, dy) or 1e-6
        min_dist = self.sprite_size
        if dist >= min_dist:
            return

        overlap = (min_dist - dist) / 2
        nx, ny = dx / dist, dy / dist
        a.x += nx * overlap
        a.y += ny * overlap
        b.x -= nx * overlap
        b.y -= ny * overlap

        rel_vx = a.vx - b.vx
        rel_vy = a.vy - b.vy
        closing_speed = rel_vx * nx + rel_vy * ny
        if closing_speed >= 0:
            return

        impulse = -(1 + self.config.restitution) * closing_speed / 2
        a.vx += impulse * nx
        a.vy += impulse * ny
        b.vx -= impulse * nx
        b.vy -= impulse * ny

        self._clamp_sprite(a)
        self._clamp_sprite(b)

    def _damage_scale(self, alive_count: int) -> float:
        ratio = max(0.0, min(1.0, alive_count / max(1, self.starting_fighters)))
        return self.config.early_damage_scale + (1 - ratio) * (
            self.config.late_damage_scale - self.config.early_damage_scale
        )

    def _apply_damage(self, a: Sprite, b: Sprite, frame_idx: int, alive_count: int) -> None:
        scale = self._damage_scale(alive_count)
        damage_a_base = random.randint(self.config.min_damage, self.config.max_damage)
        damage_b_base = random.randint(self.config.min_damage, self.config.max_damage)
        damage_a = max(1, int(round(damage_a_base * scale)))
        damage_b = max(1, int(round(damage_b_base * scale)))

        a.health = max(0.0, a.health - damage_b)
        b.health = max(0.0, b.health - damage_a)
        a.last_hit_frame = frame_idx
        b.last_hit_frame = frame_idx

        self._record_damage(b.username, a.username, damage_b)
        self._record_damage(a.username, b.username, damage_a)

        if a.health <= 0 and a.alive:
            a.alive = False
            a.death_frame = frame_idx
        if b.health <= 0 and b.alive:
            b.alive = False
            b.death_frame = frame_idx

    # Rendering ------------------------------------------------------------

    def _draw_frame(self, sprites: List[Sprite], winner: Sprite | None, frame_idx: int) -> np.ndarray:
        if self.background is None:
            self.background = self._generate_background(self.config.width, self.config.height)
        frame = self.background.copy()
        draw = ImageDraw.Draw(frame)
        bar_height = 14
        alive_count = 0
        for sprite in sprites:
            if not sprite.alive:
                continue
            alive_count += 1
            pos = (int(sprite.x), int(sprite.y))
            sprite_img = sprite.image
            effect_name = sprite.effect_name
            if effect_name:
                self._draw_effect_glow(frame, pos, sprite_img.size, effect_name, frame_idx)
            frame.paste(sprite_img, pos, sprite_img)

            bar_width = self.sprite_size
            bar_x, bar_y = pos[0], pos[1] + self.sprite_size + 6
            hp_ratio = max(0.0, min(1.0, sprite.health / 100.0))
            hp_width = int(bar_width * hp_ratio)
            draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill=(35, 35, 35))
            if hp_width > 0:
                color = (0, 200, 0) if sprite.alive else (170, 30, 30)
                if hp_ratio < 0.35 and sprite.alive:
                    color = (240, 150, 20)
                draw.rectangle([bar_x, bar_y, bar_x + hp_width, bar_y + bar_height], fill=color)
            draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], outline=(15, 15, 15), width=2)

        if winner is not None:
            alive_count = max(alive_count, 1)

        counter_font = self._get_header_font(40)
        label = f"Alive: {alive_count}"
        lx1, ly1, lx2, ly2 = draw.textbbox((0, 0), label, font=counter_font)
        lw, lh = lx2 - lx1, ly2 - ly1
        pad = 10
        draw.rectangle([10, 10, 10 + lw + pad * 2, 10 + lh + pad * 2], fill=(0, 0, 0, 140))
        draw.text((10 + pad, 10 + pad), label, font=counter_font, fill=(255, 255, 255, 230))

        if winner is not None:
            center_x = self.config.width // 2
            center_y = int((self.arena_top + self.arena_bottom) // 2)

            header_font = self._get_header_font(72)
            header_text = "CHAMPION"
            left, top, right, bottom = draw.textbbox((0, 0), header_text, font=header_font)
            header_w, header_h = right - left, bottom - top
            hx = center_x - header_w // 2
            hy = center_y - self.sprite_size - 140
            draw.text((hx, hy), header_text, font=header_font, fill=(255, 215, 0, 255))

            champ_size = max(220, int(self.sprite_size * 1.6))
            champ_img = winner.image.resize((champ_size, champ_size), Image.LANCZOS)
            champ_mask = Image.new("L", (champ_size, champ_size), 0)
            champ_draw = ImageDraw.Draw(champ_mask)
            champ_draw.ellipse([0, 0, champ_size - 1, champ_size - 1], fill=255)
            champ_img.putalpha(champ_mask)
            frame.paste(champ_img, (center_x - champ_size // 2, center_y - champ_size // 2), champ_img)

            handle_font = self._get_header_font(42)
            handle = f"@{winner.username}"
            hl, ht, hr, hb = draw.textbbox((0, 0), handle, font=handle_font)
            hw, hh = hr - hl, hb - ht
            hx2 = center_x - hw // 2
            hy2 = center_y + champ_size // 2 + 20
            draw.text((hx2, hy2), handle, font=handle_font, fill=(255, 255, 255, 230))

        return np.array(frame.convert("RGB"))

    def _generate_background(self, width: int, height: int) -> Image.Image:
        bg = Image.new("RGBA", (width, height), (10, 10, 14, 255))
        painter = ImageDraw.Draw(bg)

        for y_coord in range(height):
            t = y_coord / max(1, height - 1)
            r_val = int(18 + 90 * t)
            green = int(8 + 25 * t)
            b_val = int(12 + 30 * (1 - t))
            painter.line([(0, y_coord), (width, y_coord)], fill=(r_val, green, b_val, 255))

        vignette = Image.new("L", (width, height), 0)
        vd = ImageDraw.Draw(vignette)
        margin = 80
        vd.ellipse([margin, margin, width - margin, height - margin], fill=180)
        bg.putalpha(vignette)
        bg = bg.convert("RGBA")

        cx, cy = width / 2, self.octagon_center_y
        radius = min(width, height) * 0.35
        oct_pts = []
        for i in range(8):
            angle = math.pi / 8 + i * (math.pi / 4)
            ox = cx + radius * math.cos(angle)
            oy = cy + radius * math.sin(angle)
            oct_pts.append((ox, oy))
        painter = ImageDraw.Draw(bg)
        painter.polygon(oct_pts, outline=(220, 50, 50, 200), width=6)
        inner_pts = []
        for i in range(8):
            angle = math.pi / 8 + i * (math.pi / 4)
            ox = cx + (radius * 0.72) * math.cos(angle)
            oy = cy + (radius * 0.72) * math.sin(angle)
            inner_pts.append((ox, oy))
        painter.polygon(inner_pts, outline=(255, 255, 255, 80), width=2)

        stripe_color = (40, 5, 5, 90)
        for x_coord in range(-width, width * 2, 140):
            painter.line([(x_coord, height), (x_coord + width // 2, 0)], fill=stripe_color, width=6)

        self._draw_overlay_texts(painter, width, height)

        return bg

    def _draw_centered_label(
        self,
        painter: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        center_x: float,
        y: float,
        fill: tuple[int, int, int, int],
        shadow: tuple[int, int, int, int] | None = None,
    ) -> None:
        left, top, right, bottom = painter.textbbox((0, 0), text, font=font)
        text_width = right - left
        x = center_x - text_width / 2
        if shadow is not None:
            painter.text((x + 2, y + 2), text, font=font, fill=shadow)
        painter.text((x, y), text, font=font, fill=fill)

    def _draw_overlay_texts(self, painter: ImageDraw.ImageDraw, width: int, height: int) -> None:
        top_font = self._get_header_font(64)
        bottom_font = self._get_header_font(64)
        top_lines = ["Making my followers fight until", "only one is left"]
        battle_num = self.battle_number if self.battle_number is not None else 1
        fighters = self.fighter_count if self.fighter_count else self.starting_fighters
        bottom_text = f"Day {battle_num}: {fighters} followers"

        center_x = width / 2
        line_gap = 10
        top_heights = []
        for line in top_lines:
            bbox = painter.textbbox((0, 0), line, font=top_font)
            top_heights.append(bbox[3] - bbox[1])
        top_total_height = sum(top_heights) + line_gap * (len(top_lines) - 1)
        top_y = max(32, (self.arena_top - top_total_height) * 0.82)

        current_y = top_y
        for idx, line in enumerate(top_lines):
            self._draw_centered_label(
                painter,
                line,
                top_font,
                center_x,
                current_y,
                fill=(255, 255, 255, 200),
                shadow=(0, 0, 0, 120),
            )
            current_y += top_heights[idx] + line_gap

        bottom_bbox = painter.textbbox((0, 0), bottom_text, font=bottom_font)
        bottom_height = bottom_bbox[3] - bottom_bbox[1]
        bottom_margin_space = max(12, height - self.arena_bottom - bottom_height)
        bottom_y = self.arena_bottom + bottom_margin_space * 0.3

        self._draw_centered_label(
            painter,
            bottom_text,
            bottom_font,
            center_x,
            bottom_y,
            fill=(255, 255, 255, 230),
            shadow=(0, 0, 0, 130),
        )

    # Avatar rendering -----------------------------------------------------

    def _load_avatar(self, username: str, size: int | None = None) -> Image.Image:
        target_size = size or self.sprite_size
        path = self.settings.profile_dir / f"{username}.jpg"
        if path.exists():
            img = Image.open(path).convert("RGBA")
        else:
            img = Image.new("RGBA", (target_size, target_size), (200, 200, 200, 255))
        img = img.resize((target_size, target_size), Image.LANCZOS)

        self.circle_mask = Image.new("L", (target_size, target_size), 0)
        mask_draw = ImageDraw.Draw(self.circle_mask)
        mask_draw.ellipse([0, 0, target_size - 1, target_size - 1], fill=255)

        img.putalpha(self.circle_mask)
        return self._decorate_avatar(username, img)

    def _scale_avatar(self, avatar: Image.Image, size: int) -> Image.Image:
        if avatar.size == (size, size):
            return avatar.copy()
        return avatar.resize((size, size), Image.LANCZOS)

    def _load_customizations(self) -> Dict[str, Dict[str, List[str]]]:
        if self.custom_cache:
            return self.custom_cache
        data = load_json(self.settings.custom_path, {})
        if isinstance(data, dict):
            self.custom_cache.update(data)
        return self.custom_cache

    def _active_lookup(self, username: str) -> Dict[str, str]:
        customs = self._load_customizations()
        user_custom = customs.get(username, {}) if isinstance(customs, dict) else {}
        if "masks" not in user_custom and "hats" in user_custom:
            user_custom["masks"] = user_custom.get("hats", [])
        applied = user_custom.get("applied", {}) if isinstance(user_custom.get("applied"), dict) else {}
        # Backward compatibility: migrate legacy headgear key to masks
        if "masks" not in applied and "hats" in applied:
            applied["masks"] = applied.get("hats", "")
        choices = {k: v for k, v in applied.items() if v}
        if len(choices) > 1:
            # enforce a single visible cosmetic: priority effects > masks > borders
            priority = ("effects", "masks", "borders")
            keep_cat = next((p for p in priority if p in choices), "")
            keep_val = choices.get(keep_cat, "")
            choices = {cat: (keep_val if cat == keep_cat else "") for cat in priority}
        return {
            "borders": choices.get("borders", ""),
            "masks": choices.get("masks", ""),
            "effects": choices.get("effects", ""),
        }

    def _active_border(self, username: str) -> str:
        return self._active_lookup(username).get("borders", "")

    def _active_mask(self, username: str) -> str:
        return self._active_lookup(username).get("masks", "")

    def _active_effect(self, username: str) -> str:
        return self._active_lookup(username).get("effects", "")

    def _decorate_avatar(self, username: str, img: Image.Image) -> Image.Image:
        effect_name = self._active_effect(username)
        mask_name = "" if effect_name else self._active_mask(username)
        border_name = "" if effect_name or mask_name else self._active_border(username)

        base = img.copy()
        draw = ImageDraw.Draw(base)

        if border_name:
            border_color = (255, 59, 59, 220) if "Red" in border_name else (0, 200, 255, 220)
            draw.ellipse(
                [1, 1, base.size[0] - 2, base.size[1] - 2],
                outline=border_color,
                width=4,
            )

        if mask_name:
            base = apply_mask_to_avatar(base, mask_name)

        return base

    def _draw_effect_glow(
        self, frame: Image.Image, pos: Tuple[int, int], size: Tuple[int, int], effect_name: str, frame_idx: int
    ) -> None:
        """Overlay a pulsing glow effect around the sprite at the given position."""
        glow_pad = max(12, int(size[0] * 0.22))
        ring_size = (size[0] + glow_pad * 2, size[1] + glow_pad * 2)
        layer = Image.new("RGBA", ring_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        t = (frame_idx % 40) / 40.0
        pulse = 0.6 + 0.4 * math.sin(2 * math.pi * t)
        outer_color = (0, 210, 255, int(180 * pulse)) if "Wave" in effect_name else (255, 150, 40, int(180 * pulse))
        inner_color = (0, 160, 230, int(140 * pulse)) if "Wave" in effect_name else (255, 110, 20, int(140 * pulse))
        fill_color = (255, 255, 255, int(60 * pulse))

        outer_width = max(8, int(size[0] * 0.12))
        inner_width = max(5, int(size[0] * 0.08))
        inset_outer = max(2, int(size[0] * 0.02))
        inset_inner = inset_outer + max(6, int(size[0] * 0.05))

        draw.ellipse(
            [inset_outer, inset_outer, ring_size[0] - inset_outer, ring_size[1] - inset_outer],
            outline=outer_color,
            width=outer_width,
        )
        draw.ellipse(
            [inset_inner, inset_inner, ring_size[0] - inset_inner, ring_size[1] - inset_inner],
            outline=inner_color,
            width=inner_width,
        )
        draw.ellipse(
            [
                inset_inner + 4,
                inset_inner + 4,
                ring_size[0] - inset_inner - 4,
                ring_size[1] - inset_inner - 4,
            ],
            fill=fill_color,
        )

        blur_radius = max(6, int(size[0] * 0.08))
        layer = layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        frame.paste(layer, (pos[0] - glow_pad, pos[1] - glow_pad), layer)

    # Ranking & persistence ------------------------------------------------

    def _build_ranking(self, sprites: List[Sprite], total_frames: int) -> List[Dict[str, object]]:
        alive = [sprite for sprite in sprites if sprite.alive]
        if len(alive) > 1:
            alive_sorted = sorted(alive, key=lambda sprite: sprite.health)
            for idx, sprite in enumerate(alive_sorted):
                sprite.death_frame = total_frames + idx

        # Ensure any survivors (the winner) get the highest death_frame so they rank first.
        max_frame = max((sprite.death_frame if sprite.death_frame is not None else -1) for sprite in sprites)
        for sprite in sprites:
            if sprite.death_frame is None:
                max_frame += 1
                sprite.death_frame = max_frame

        sorted_sprites = sorted(sprites, key=lambda sprite: sprite.death_frame, reverse=True)
        ranking: List[Dict[str, object]] = []
        for order, sprite in enumerate(sorted_sprites, start=1):
            ranking.append(
                {
                    "username": sprite.username,
                    "profile_pic": str(self.settings.profile_dir / f"{sprite.username}.jpg"),
                    "order": order,
                    "final_health": max(0.0, sprite.health),
                }
            )
        return ranking

    def _write_video(self, frames: List[np.ndarray]) -> Path:
        clip = ImageSequenceClip(frames, fps=self.config.fps)
        self.settings.base_battles.mkdir(parents=True, exist_ok=True)
        battle_index = self.battle_number or self._next_battle_number()
        file_path = self.settings.base_battles / f"battle_{battle_index}.mp4"
        audio = None
        video_duration = len(frames) / self.config.fps
        if self.settings.sound_path.exists():
            try:
                raw_audio = AudioFileClip(str(self.settings.sound_path))
                audio = raw_audio.set_duration(video_duration)
            except Exception:
                audio = None

        clip = clip.set_audio(audio) if audio is not None else clip
        clip.write_videofile(str(file_path), codec="libx264", audio=audio is not None, fps=self.config.fps)
        return file_path

    # Helpers --------------------------------------------------------------

    def _next_battle_number(self) -> int:
        numbers = []
        for path in self.settings.base_battles.iterdir():
            if not (path.name.startswith("battle_") and path.suffix == ".mp4"):
                continue
            try:
                numbers.append(int(path.stem.split("_")[-1]))
            except (IndexError, ValueError):
                continue
        return max(numbers, default=0) + 1

    def _compute_sprite_size(self, fighter_count: int) -> int:
        fighter_count = max(1, fighter_count)
        min_px, max_px = 36, 180
        frac = (math.log10(fighter_count) - 1) / (5 - 1)
        frac = max(0.0, min(1.0, frac))
        size = int(max_px - frac * (max_px - min_px))
        return max(min_px, min(max_px, size))

    def _current_size_for_alive(self, alive_count: int) -> int:
        ratio = max(0.0, min(1.0, alive_count / max(1, self.starting_fighters)))
        span = max(0, self.sprite_max_size - self.sprite_min_size)
        return int(self.sprite_min_size + (1 - ratio) * span)

    def _apply_sprite_size(self, size: int) -> None:
        self.sprite_size = size
        self.sprite_radius = self.sprite_size / 2

    def _backup_run_state(self) -> None:
        """Persist current scoreboard/stats so revert can restore exactly."""
        try:
            self.settings.last_run_scoreboard_backup_path.parent.mkdir(parents=True, exist_ok=True)
            current_board = load_json(self.settings.scoreboard_path, {})
            save_json(self.settings.last_run_scoreboard_backup_path, current_board)
            current_stats = load_json(self.settings.stats_path, {})
            save_json(self.settings.last_run_stats_backup_path, current_stats)
        except Exception:
            # If backup fails, we continue so the battle can still run; revert will warn.
            pass

    def _set_sprite_geometry(self, fighter_count: int) -> None:
        self.starting_fighters = max(1, fighter_count)
        base_size = self._compute_sprite_size(self.starting_fighters)
        self.sprite_min_size = max(48, int(base_size * self.config.min_size_factor))
        scaled_max = int(base_size * self.config.max_size_factor)
        arena_cap = int(self.config.width * 0.45)
        self.sprite_max_size = max(self.sprite_min_size, min(scaled_max, arena_cap))
        starting_size = self._current_size_for_alive(self.starting_fighters)
        self._apply_sprite_size(starting_size)
        self.circle_mask = None

    def _update_sprite_size(self, alive_count: int, sprites: List[Sprite]) -> None:
        target_size = self._current_size_for_alive(alive_count)
        if target_size == self.sprite_size:
            return
        self._apply_sprite_size(target_size)
        for sprite in sprites:
            base = sprite.base_image if sprite.base_image is not None else sprite.image
            sprite.image = self._scale_avatar(base, target_size)

    def _record_damage(self, attacker: str, defender: str, amount: float) -> None:
        if not attacker or not defender:
            return
        info = self.damage_log.setdefault(attacker, {}).setdefault(defender, {"damage": 0.0, "hits": 0})
        info["damage"] += float(amount)
        info["hits"] += 1

    def _get_header_font(self, size: int) -> ImageFont.FreeTypeFont:
        for name in ("Impact.ttf", "impact.ttf", "arialbd.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()


def run_battle(
    settings: Settings | None = None,
    followers: List[Follower] | None = None,
) -> BattleOutcome:
    """Fetch followers, download avatars, run a video fight, and persist results."""
    settings = settings or get_settings()
    refresh = os.getenv("UFC_REFRESH_FOLLOWERS", "").lower() in {"1", "true", "yes", "y"}
    follower_list = followers or get_followers(settings=settings, use_cache=True, refresh=refresh)
    settings.profile_dir.mkdir(exist_ok=True)

    missing = [f for f in follower_list if not (settings.profile_dir / f"{f.username}.jpg").exists()]
    if missing:
        cached = len(follower_list) - len(missing)
        if cached:
            print(f"[cache] skipping download for {cached} cached avatars", flush=True)
        download_profile_pics(missing, settings.profile_dir, skip_existing=False)
    elif follower_list:
        print(f"[cache] all {len(follower_list)} avatars already downloaded", flush=True)

    simulator = VideoFightSimulator(settings=settings)
    return simulator.run(follower_list)
