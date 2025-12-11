from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from PIL import Image

from ufc_fight.followers import get_followers
from ufc_fight.settings import get_settings
from ufc_fight.storage import load_json, save_json

settings = get_settings()

PROFILE_DIR = settings.profile_dir
STRIPE_SECRET_KEY = settings.stripe_secret_key
PAYMENT_MODE = settings.payment_mode
SCOREBOARD_PATH = settings.scoreboard_path
STATS_PATH = settings.stats_path
CUSTOM_PATH = settings.custom_path
FOLLOWER_CACHE_PATH = settings.follower_cache_path
# Map item name -> Stripe Price ID (fill in real values)
STRIPE_PRICE_IDS = {
    # "Red Steel": "price_xxx",
    # "Neon Pulse": "price_xxx",
    # "Spartan Helm": "price_xxx",
    # "Cowboy": "price_xxx",
    # "Arc Zap": "price_xxx",
    # "Wave Pulse": "price_xxx",
    # "Healer (+20% HP)": "price_xxx",
    # "Soldier (+20% dmg)": "price_xxx",
    # "Tank (5s shield)": "price_xxx",
    # "Agile (+15% speed)": "price_xxx",
}


@st.cache_data(show_spinner=False)
def load_followers_cache() -> List[str]:
    if FOLLOWER_CACHE_PATH.exists():
        cached = load_json(FOLLOWER_CACHE_PATH, [])
        if isinstance(cached, list):
            return [str(x) for x in cached]
    try:
        followers = get_followers(max_followers=5000)
        names = sorted({f.username for f in followers if getattr(f, "username", None)})
        save_json(FOLLOWER_CACHE_PATH, names)
        return names
    except Exception:
        board = load_json(SCOREBOARD_PATH, {})
        return sorted(board.keys())


def get_profile_pic(username: str) -> Optional[str]:
    path = PROFILE_DIR / f"{username}.jpg"
    if path.exists():
        return str(path)
    return None


def encode_image(path: Path | str, width: int = 220) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    try:
        with open(p, "rb") as handle:
            b64 = base64.b64encode(handle.read()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return ""


def set_applied(user: str, category: str, item: str) -> None:
    data = load_json(CUSTOM_PATH, {})
    user_store = ensure_custom(user)
    user_store["applied"][category] = item
    data[user] = user_store
    save_json(CUSTOM_PATH, data)


def acquire_item(user: str, category: str, item: str) -> None:
    data = load_json(CUSTOM_PATH, {})
    user_store = ensure_custom(user)
    owned_list = user_store.setdefault(category, [])
    if item not in owned_list:
        owned_list.append(item)
    data[user] = user_store
    save_json(CUSTOM_PATH, data)


def create_checkout_session(item_name: str) -> Optional[str]:
    """Create a Stripe Checkout session; returns URL or None on failure."""
    if PAYMENT_MODE != "prod":
        return None
    price_id = STRIPE_PRICE_IDS.get(item_name)
    if not STRIPE_SECRET_KEY or not price_id:
        return None
    try:
        import stripe  # type: ignore
    except ImportError:
        return None
    stripe.api_key = STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="payment",
            success_url="https://yourdomain.com/checkout/success",  # TODO: replace with real URL
            cancel_url="https://yourdomain.com/checkout/cancel",  # TODO: replace with real URL
        )
        return session.get("url")
    except Exception:
        return None


def prompt_purchase(item_name: str) -> None:
    st.warning("Payments are coming soon. Configure Stripe to enable purchasing.")


def ensure_custom(user: str) -> Dict[str, List[str]]:
    data = load_json(CUSTOM_PATH, {})
    user_store = data.get(
        user,
        {"borders": [], "hats": [], "effects": [], "powerups": [], "applied": {"borders": "", "hats": "", "effects": ""}},
    )
    applied = user_store.get("applied", {})
    for cat in ["borders", "hats", "effects"]:
        applied.setdefault(cat, "")
    user_store["applied"] = applied
    data[user] = user_store
    save_json(CUSTOM_PATH, data)
    return user_store


def inject_css() -> None:
    css = """
    <style>
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], .main {background:#0E0C0B !important;}
    body {background:#0E0C0B;}
    .block-container {padding-top: 0rem;}
    .ufc-hero {background: linear-gradient(135deg, #0a0a0a, #1a0000); border:1px solid #ff3b3b33; padding:18px; border-radius:18px; box-shadow:0 12px 32px rgba(0,0,0,.45);}
    .metric-card {padding:14px; border-radius:12px; border:1px solid #ffffff22; background:rgba(255,255,255,0.03);}
    .stat-badge {background:#ff3b3b22; color:#f7f7f7; padding:6px 12px; border-radius:999px; border:1px solid #ff3b3b55;}
    .store-card {border:1px solid #ffffff22; border-radius:12px; padding:12px; background:rgba(255,255,255,0.03);}
    .owned {opacity:0.65;}
    .login-card {background:#000; padding:28px; border-radius:16px; border:none; box-shadow:0 20px 50px rgba(0,0,0,0.75);}
    .login-input input {background:#050505 !important; color:#f5f5f5 !important; border:1px solid #ff3b3b55 !important; border-radius:10px !important;}
    .login-button button {background:linear-gradient(90deg,#ff3b3b,#b10000) !important; color:#fff !important; border:none !important; border-radius:12px !important; height:52px; font-weight:700; letter-spacing:1px;}
    .suggestion-box {border:none; background:transparent; padding:0; max-height:220px; overflow-y:auto;}
    .suggestion-item {padding:10px; border-radius:8px; color:#f5f5f5;}
    .suggestion-item:hover {background:#ff3b3b33; cursor:pointer;}
    [data-testid="stSidebar"] > div {display:flex; flex-direction:column; height:100vh;}
    [data-testid="stSidebar"] .stButton>button {background:linear-gradient(90deg,#1b1b1b,#2b0a0a); border:1px solid #ff3b3b55; color:#f5f5f5; border-radius:12px; width:100%; height:46px; font-weight:600; letter-spacing:0.5px;}
    [data-testid="stSidebar"] .stButton>button:hover {border-color:#ff5555; color:#fff;}
    [data-testid="stSidebar"] .nav-tab {padding:12px 14px; border-radius:12px; border:1px solid #ff3b3b55; background:#1a0a0a; color:#f5f5f5; font-weight:700; letter-spacing:0.5px; text-align:center; margin-bottom:8px;}
    [data-testid="stSidebar"] .nav-tab.active {background:linear-gradient(90deg,#ff3b3b,#b10000); border-color:#ff3b3b; color:#fff;}
    .preview-frame {width:128px; height:128px; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:auto; background:linear-gradient(135deg,#1c1c1c,#0a0a0a); position:relative; box-shadow:0 8px 28px rgba(0,0,0,0.45);}
    .preview-avatar-img {width:116px; height:116px; border-radius:50%; object-fit:cover; object-position:center;}
    .preview-hat {position:absolute; top:-8px; font-size:28px;}
    .preview-effect {position:absolute; inset:-6px; border-radius:50%; box-shadow:0 0 18px 6px rgba(255,59,59,0.35);}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def login_screen(followers: List[str]) -> None:
    col_left, col_right = st.columns([6, 6], gap="large")
    with col_left:
        img_src = encode_image(settings.login_image_path)
        if img_src:
            st.markdown(
                f"<div style='height:90vh;display:flex;align-items:center;justify-content:center;'>"
                f"<img src=\"{img_src}\" style='width:100%;object-fit:contain;'/>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.image(str(settings.login_image_path), use_container_width=True)
    with col_right:
        st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
        st.markdown("<h3 style='color:#ff3b3b;text-transform:uppercase;letter-spacing:2px;margin:0;'>Enter the Octagon</h3>", unsafe_allow_html=True)
        query = st.text_input("Username", key="login_query", label_visibility="collapsed", placeholder="Type your handle", help=None)
        filtered = [f for f in followers if query.lower() in f.lower()] if query else followers[:10]
        suggestions = filtered[:8]
        if query and suggestions:
            st.markdown("**Suggestions**", unsafe_allow_html=True)
            chip_cols = st.columns(4)
            for idx, name in enumerate(suggestions):
                with chip_cols[idx % 4]:
                    if st.button(name, key=f"pick-{name}", use_container_width=True):
                        st.session_state["user"] = name
                        st.rerun()


def render_sidebar_nav() -> str:
    nav_main = ["Leaderboard", "My Stats", "Character", "Power Ups"]
    nav_bottom = ["Support", "Logout"]
    active = st.session_state.get("nav", nav_main[0])

    img_src = encode_image(settings.login_image_path)
    if img_src:
        st.sidebar.markdown(
            f"<div style='padding:10px 6px 18px 6px;'><img src=\"{img_src}\" style='width:100%;border-radius:12px;object-fit:cover;'/></div>",
            unsafe_allow_html=True,
        )

    for item in nav_main:
        if item == active:
            st.sidebar.markdown(f"<div class='nav-tab active'>{item}</div>", unsafe_allow_html=True)
        else:
            if st.sidebar.button(item, key=f"nav-{item}"):
                st.session_state["nav"] = item
                st.rerun()

    st.sidebar.markdown("<div style='flex:1 1 auto;'></div><div style='height:12px;'></div>", unsafe_allow_html=True)

    for item in nav_bottom:
        if item == active:
            st.sidebar.markdown(f"<div class='nav-tab active'>{item}</div>", unsafe_allow_html=True)
        else:
            if st.sidebar.button(item, key=f"nav-{item}"):
                st.session_state["nav"] = item
                st.rerun()

    return active


def top_bar(user: str) -> None:
    st.markdown(
        "<div style='text-align:center;font-size:36px;font-weight:700;letter-spacing:4px;color:#ff3b3b;'>UFC</div>",
        unsafe_allow_html=True,
    )


def load_scoreboard_df() -> pd.DataFrame:
    board = load_json(SCOREBOARD_PATH, {})
    rows = []
    for user, data in board.items():
        rows.append({"Username": user, "Points": data.get("points", 0), "Runs": data.get("runs", 0)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=["Points", "Runs"], ascending=[False, False]).reset_index(drop=True)
        df["Rank"] = df.index + 1
    return df


def leaderboard_page() -> None:
    st.markdown(
        "<h2 style='color:#ff3b3b;text-transform:uppercase;letter-spacing:2px;margin-bottom:16px;'>Leaderboard</h2>",
        unsafe_allow_html=True,
    )
    stats = load_json(STATS_PATH, {})
    board = load_json(SCOREBOARD_PATH, {})
    if not board:
        st.info("No fights recorded yet.")
        return

    rows = []
    for user, data in board.items():
        pts = data.get("points", 0)
        runs = data.get("runs", 0)
        entry = stats.get(user, {})
        dmg = int(entry.get("total_damage_dealt", 0))
        wins = entry.get("wins", 0)
        pic_path = get_profile_pic(user)
        pic_src = encode_image(pic_path) if pic_path else ""
        rows.append({"user": user, "points": pts, "runs": runs, "damage": dmg, "wins": wins, "pic": pic_src})

    rows = sorted(rows, key=lambda r: (r["points"], r["wins"], r["runs"], r["damage"]), reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx

    header_html = """
    <div style="display:grid;grid-template-columns:90px 1.6fr 1fr 1fr 1fr;gap:12px;
                padding:14px 16px;border-radius:12px;border:1px solid #ff3b3b55;
                background:linear-gradient(90deg,#1a0a0a,#120808);color:#f5f5f5;
                font-weight:700;letter-spacing:0.5px;">
        <div>Rank</div>
        <div>Username</div>
        <div style="text-align:right;">Points</div>
        <div style="text-align:right;">Games</div>
        <div style="text-align:right;">Total Damage</div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    row_html_parts = []
    for row in rows:
        crown = " *" if row["wins"] > 0 else ""
        avatar = ""
        if row["pic"]:
            avatar = (
                f"<img src='{row['pic']}' style='width:36px;height:36px;border-radius:50%;object-fit:cover;"
                "margin-right:10px;border:1px solid #ff3b3b55;'/>"
            )
        row_html_parts.append(
            f"""
            <div style="display:grid;grid-template-columns:90px 1.6fr 1fr 1fr 1fr;gap:12px;
                        padding:12px 16px;margin-top:10px;border-radius:12px;
                        border:1px solid #ffffff18;background:#0f0c0c;color:#f5f5f5;
                        align-items:center;">
                <div style="font-weight:700;color:#ffdedb;">#{row['rank']}{crown}</div>
                <div style="display:flex;align-items:center;font-weight:600;">{avatar}<span>@{row['user']}</span></div>
                <div style="text-align:right;">{row['points']}</div>
                <div style="text-align:right;">{row['runs']}</div>
                <div style="text-align:right;">{row['damage']}</div>
            </div>
            """
        )

    st.markdown("".join(row_html_parts), unsafe_allow_html=True)


def my_stats_page(user: str) -> None:
    stats = load_json(STATS_PATH, {})
    entry = stats.get(user, {})
    matches = entry.get("matches", 0)
    wins = entry.get("wins", 0)
    dmg = entry.get("total_damage_dealt", 0)
    hits = entry.get("total_hits", 0)
    rival = entry.get("biggest_rival", "") or "N/A"
    st.markdown(
        "<h2 style='color:#ff3b3b;text-transform:uppercase;letter-spacing:2px;margin-bottom:16px;'>My Stats</h2>",
        unsafe_allow_html=True,
    )
    col_pic, col_meta = st.columns([2, 3])
    with col_pic:
        pic = get_profile_pic(user)
        if pic:
            st.image(pic, width=220)
    with col_meta:
        stat_html = f"""
        <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;">
            <div class='metric-card'><div style='color:#999;font-size:12px;'>Matches</div><div style='font-size:24px;font-weight:700;color:#fff;'>{matches}</div></div>
            <div class='metric-card'><div style='color:#999;font-size:12px;'>Wins</div><div style='font-size:24px;font-weight:700;color:#fff;'>{wins}</div></div>
            <div class='metric-card'><div style='color:#999;font-size:12px;'>Total Damage</div><div style='font-size:24px;font-weight:700;color:#fff;'>{int(dmg)}</div></div>
            <div class='metric-card'><div style='color:#999;font-size:12px;'>Total Hits</div><div style='font-size:24px;font-weight:700;color:#fff;'>{hits}</div></div>
            <div class='metric-card'><div style='color:#999;font-size:12px;'>Biggest Rival</div><div style='font-size:20px;font-weight:700;color:#ffdedb;'>{rival}</div></div>
            <div class='metric-card'><div style='color:#999;font-size:12px;'>Handle</div><div style='font-size:20px;font-weight:700;color:#fff;'>@{user}</div></div>
        </div>
        """
        st.markdown(stat_html, unsafe_allow_html=True)

    st.divider()
    damage_to = entry.get("damage_to", {})
    search_name = st.text_input("Search damage dealt to follower", key="search_damage")
    if search_name:
        info = damage_to.get(search_name, {"damage": 0, "hits": 0})
        st.markdown(
            f"<div class='metric-card' style='margin-bottom:12px;'>"
            f"<div style='color:#999;font-size:12px;'>Damage to {search_name}</div>"
            f"<div style='font-size:20px;font-weight:700;color:#fff;'>{int(info.get('damage', 0))} dmg over {info.get('hits', 0)} hits</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    if damage_to:
        top_targets = sorted(damage_to.items(), key=lambda kv: kv[1].get("damage", 0), reverse=True)[:10]
        st.markdown(
            "<h4 style='color:#ff3b3b;letter-spacing:1px;margin:12px 0;'>Top damage dealt</h4>",
            unsafe_allow_html=True,
        )
        header_html = """
        <div style="display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:12px;
                    padding:12px 16px;border-radius:12px;border:1px solid #ff3b3b55;
                    background:linear-gradient(90deg,#1a0a0a,#120808);color:#f5f5f5;
                    font-weight:700;letter-spacing:0.5px;">
            <div>Opponent</div>
            <div style="text-align:right;">Damage</div>
            <div style="text-align:right;">Hits</div>
        </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)
        rows_html = []
        for opponent, data in top_targets:
            rows_html.append(
                f"""
                <div style="display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:12px;
                            padding:10px 16px;margin-top:8px;border-radius:12px;
                            border:1px solid #ffffff18;background:#0f0c0c;color:#f5f5f5;
                            align-items:center;">
                    <div style="font-weight:600;">@{opponent}</div>
                    <div style="text-align:right;">{int(data.get('damage', 0))}</div>
                    <div style="text-align:right;">{data.get('hits', 0)}</div>
                </div>
                """
            )
        st.markdown("".join(rows_html), unsafe_allow_html=True)


STORE_ITEMS = {
    "borders": [{"name": "Red Steel", "price": 0}, {"name": "Neon Pulse", "price": 0}],
    "hats": [{"name": "Spartan Helm", "price": 10}, {"name": "Cowboy", "price": 10}],
    "effects": [{"name": "Arc Zap", "price": 15}, {"name": "Wave Pulse", "price": 15}],
    "powerups": [
        {"name": "Healer (+20% HP)", "price": 50},
        {"name": "Soldier (+20% dmg)", "price": 50},
        {"name": "Tank (5s shield)", "price": 50},
        {"name": "Agile (+15% speed)", "price": 50},
    ],
}


def character_page(user: str) -> None:
    st.markdown(
        "<h2 style='color:#ff3b3b;text-transform:uppercase;letter-spacing:2px;margin-bottom:16px;'>Character</h2>",
        unsafe_allow_html=True,
    )
    owned = ensure_custom(user)
    avatar_path = get_profile_pic(user)
    avatar_src = encode_image(avatar_path) if avatar_path else ""
    if not avatar_src:
        fallback = Image.new("RGB", (200, 200), (30, 30, 30))
        buf = io.BytesIO()
        fallback.save(buf, format="PNG")
        avatar_src = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    def preview_html(category: str, item_name: str) -> str:
        border_color = "#ff3b3b"
        hat_icon = ""
        effect_glow = ""
        if category == "borders":
            border_color = "#ff3b3b" if "Red" in item_name else "#00e0ff"
        if category == "hats":
            hat_icon = "^" if "Spartan" in item_name else "~"
            border_color = "#111"
        if category == "effects":
            border_color = "#222"
            effect_glow = (
                "box-shadow:0 0 24px 10px rgba(0,224,255,0.35);"
                if "Wave" in item_name
                else "box-shadow:0 0 24px 10px rgba(255,160,30,0.35);"
            )

        avatar_img = (
            f"<img class='preview-avatar-img' src='{avatar_src}' />"
            if avatar_src
            else "<div class='preview-avatar-img' style='background:linear-gradient(135deg,#222,#111);'></div>"
        )
        hat_html = f"<div class='preview-hat'>{hat_icon}</div>" if hat_icon else ""
        effect_html = f"<div class='preview-effect' style='{effect_glow}'></div>" if effect_glow else ""
        return f"<div class='preview-frame' style='border:3px solid {border_color};'>{avatar_img}{hat_html}{effect_html}</div>"

    for category in ["borders", "hats", "effects"]:
        st.markdown(
            f"<h4 style='color:#ffdedb;letter-spacing:1px;margin:16px 0 8px 0;'>{category.title()}</h4>",
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        for idx, item in enumerate(STORE_ITEMS[category]):
            with cols[idx % 2]:
                owned_flag = item["name"] in owned.get(category, [])
                applied_item = owned.get("applied", {}).get(category, "")
                is_applied = owned_flag and applied_item == item["name"]
                bg = "linear-gradient(135deg,#1a0a0a,#120808)" if is_applied else "#0f0c0c"
                card_html = (
                    "<div style=\"border:1px solid #ff3b3b55; border-radius:14px; padding:14px; margin-bottom:14px;"
                    f"background:{bg}; color:#f5f5f5;\">"
                    "<div style='display:flex; align-items:center; gap:12px;'>"
                    f"{preview_html(category, item['name'])}"
                    "<div>"
                    f"<div style='font-weight:700; letter-spacing:0.5px;'>{item['name']}</div>"
                    f"<div style='color:#ffdedb;font-weight:600;'>${item['price']}</div>"
                    "</div>"
                    "</div>"
                    "</div>"
                )
                st.markdown(card_html, unsafe_allow_html=True)
                price = item.get("price", 0)
                if owned_flag:
                    if is_applied:
                        st.button("Applied", disabled=True, key=f"applied-{category}-{item['name']}")
                    else:
                        if st.button("Apply", key=f"apply-{category}-{item['name']}"):
                            set_applied(user, category, item["name"])
                            st.success(f"Applied {item['name']}")
                            st.experimental_rerun()
                else:
                    if price == 0:
                        if st.button("Claim (Free)", key=f"claim-{category}-{item['name']}"):
                            acquire_item(user, category, item["name"])
                            set_applied(user, category, item["name"])
                            st.success(f"Claimed {item['name']}")
                            st.experimental_rerun()
                    else:
                        if st.button(f"Buy {item['name']}", key=f"buy-{category}-{item['name']}"):
                            if PAYMENT_MODE != "prod":
                                acquire_item(user, category, item["name"])
                                set_applied(user, category, item["name"])
                                st.success(f"Purchased {item['name']} (dev mode)")
                                st.experimental_rerun()
                            else:
                                prompt_purchase(item["name"])


def powerups_page(user: str) -> None:
    st.markdown(
        "<h2 style='color:#ff3b3b;text-transform:uppercase;letter-spacing:2px;margin-bottom:16px;'>Power Ups</h2>",
        unsafe_allow_html=True,
    )
    owned = ensure_custom(user)
    if "powerups" not in owned:
        owned["powerups"] = []
    cols = st.columns(2)
    for idx, item in enumerate(STORE_ITEMS["powerups"]):
        with cols[idx % 2]:
            owned_flag = item["name"] in owned["powerups"]
            bg = "linear-gradient(135deg,#1a0a0a,#120808)" if owned_flag else "#0f0c0c"
            st.markdown(
                f"""
                <div style="border:1px solid #ff3b3b55; border-radius:14px; padding:14px; margin-bottom:12px;
                            background:{bg}; color:#f5f5f5;">
                    <div style="font-weight:700; letter-spacing:0.5px;">{item['name']}</div>
                    <div style="color:#ffdedb;font-weight:600;">${item['price']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if owned_flag:
                st.button("Owned", disabled=True, key=f"power-{item['name']}")
            else:
                price = item.get("price", 0)
                if price == 0:
                    if st.button("Claim (Free)", key=f"claim-power-{item['name']}"):
                        acquire_item(user, "powerups", item["name"])
                        st.success(f"Claimed {item['name']}")
                        st.experimental_rerun()
                else:
                    if st.button(f"Buy {item['name']}", key=f"buy-power-{item['name']}"):
                        if PAYMENT_MODE != "prod":
                            acquire_item(user, "powerups", item["name"])
                            st.success(f"Purchased {item['name']} (dev mode)")
                            st.experimental_rerun()
                        else:
                            prompt_purchase(item["name"])


def support_page() -> None:
    st.markdown("### Support")
    st.info("Coming soon")


def app():
    st.set_page_config(page_title="UFC Follower Fight", layout="wide", page_icon="[UFC]")
    inject_css()
    followers = load_followers_cache()
    user = st.session_state.get("user")
    if not user:
        login_screen(followers)
        return

    nav = render_sidebar_nav()

    if nav == "Logout":
        st.session_state.clear()
        st.rerun()

    top_bar(user)

    if nav == "Leaderboard":
        leaderboard_page()
    elif nav == "My Stats":
        my_stats_page(user)
    elif nav == "Character":
        character_page(user)
    elif nav == "Power Ups":
        powerups_page(user)
    else:
        support_page()


if __name__ == "__main__":
    app()
