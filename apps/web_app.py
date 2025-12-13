from __future__ import annotations

import base64
import io
import argparse
import mimetypes
import os
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from PIL import Image

from ufc_fight.cosmetics import mask_data_uri
from ufc_fight.followers import get_followers
from ufc_fight.settings import get_settings
from ufc_fight.storage import load_json, save_json


def _apply_env_override() -> None:
    """Allow `--env dev|prod` or trailing `dev|prod` (e.g., `-- dev`)."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--env", dest="env_override", choices=["dev", "prod"])
    args, extras = parser.parse_known_args()

    env_override = args.env_override
    if not env_override:
        for token in extras:
            if token in {"dev", "prod"}:
                env_override = token
                break

    if env_override:
        os.environ["UFC_ENV"] = env_override
        get_settings.cache_clear()


_apply_env_override()
settings = get_settings()

LOGO_PATH = settings.assets_dir / "ufc_logo.png"
PAGE_ICON = str(LOGO_PATH) if LOGO_PATH.exists() else "[UFC]"
PROFILE_DIR = settings.profile_dir
STRIPE_SECRET_KEY = settings.stripe_secret_key
PAYMENT_MODE = settings.payment_mode
SCOREBOARD_PATH = settings.scoreboard_path
STATS_PATH = settings.stats_path
CUSTOM_PATH = settings.custom_path
FOLLOWER_CACHE_PATH = settings.follower_cache_path
NAV_MAIN = ["Leaderboard", "My Stats", "Character", "Power Ups"]
NAV_BOTTOM = ["Support", "Logout"]
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
        mime, _ = mimetypes.guess_type(p.name)
        mime = mime or "image/jpeg"
        with open(p, "rb") as handle:
            b64 = base64.b64encode(handle.read()).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


def load_customizations_data() -> Dict[str, Dict[str, object]]:
    data = load_json(CUSTOM_PATH, {})
    return data if isinstance(data, dict) else {}


def get_active_mask(user: str, custom_data: Optional[Dict[str, object]] = None) -> str:
    data = custom_data if isinstance(custom_data, dict) else load_customizations_data()
    user_store = data.get(user, {}) if isinstance(data, dict) else {}
    applied = user_store.get("applied", {}) if isinstance(user_store.get("applied"), dict) else {}
    # Backward compatibility: copy legacy headgear key to masks
    if "masks" not in applied and "hats" in applied:
        applied["masks"] = applied.get("hats", "")
    mask = applied.get("masks") if isinstance(applied, dict) else ""
    if not mask:
        masks = user_store.get("masks", []) or user_store.get("hats", [])
        if isinstance(masks, list) and masks:
            mask = masks[0]
    return mask or ""


def avatar_with_mask_html(pic_src: str, mask_name: str, size: int = 36, margin_right: int = 0, initial: str = "") -> str:
    fallback = (initial or "").strip()[:1].upper()
    avatar_html = (
        f"<div style='width:{size}px;height:{size}px;border-radius:50%;background:linear-gradient(135deg,#1f1f1f,#0d0d0d);"
        f"border:1px solid #ff3b3b55;color:#ffdedb;display:flex;align-items:center;justify-content:center;font-weight:700;'>"
        f"{fallback}</div>"
        if not pic_src
        else f"<img src='{pic_src}' style='width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;object-position:center;border:1px solid #ff3b3b55;' />"
    )
    mask_html = ""
    if mask_name:
        # Render mask inside the circle
        mask_width = int(size * 0.7)
        mask_uri = mask_data_uri(mask_name, size=mask_width)
        mask_offset = 0
        mask_html = (
            f"<img src='{mask_uri}' class='avatar-mask' alt='{mask_name}' "
            f"style='position:absolute; left:50%; transform:translateX(-50%); width:{mask_width}px; top:{-mask_offset}px;' />"
        )
    style = f"position:relative;width:{size}px;height:{size}px;overflow:visible;"
    if margin_right:
        style += f"margin-right:{margin_right}px;"
    return f"<div class='avatar-with-mask' style='{style}'>{avatar_html}{mask_html}</div>"


def crown_svg() -> str:
    return (
        "<span style='display:inline-flex;align-items:center;margin-left:6px;' title='Match winner'>"
        "<svg width='18' height='16' viewBox='0 0 24 16' fill='none' xmlns='http://www.w3.org/2000/svg'>"
        "<path d='M3 13.5L3.8 5.7L7.6 9.8L12 3L16.4 9.8L20.2 5.7L21 13.5C21 13.8 20.8 14 20.5 14H3.5C3.2 14 3 13.8 3 13.5Z' fill='#F6C343'/>"
        "<path d='M3 13.5C3 13.8 3.2 14 3.5 14H20.5C20.8 14 21 13.8 21 13.5V15C21 15.3 20.8 15.5 20.5 15.5H3.5C3.2 15.5 3 15.3 3 15V13.5Z' fill='#C38900'/>"
        "<circle cx='12' cy='3' r='1.4' fill='#FFD76A'/>"
        "<circle cx='7.5' cy='9.5' r='1.2' fill='#FFD76A'/>"
        "<circle cx='16.5' cy='9.5' r='1.2' fill='#FFD76A'/>"
        "</svg>"
        "</span>"
    )


def set_applied(user: str, category: str, item: str) -> None:
    data = load_json(CUSTOM_PATH, {})
    user_store = ensure_custom(user)
    # Only one cosmetic can be active at a time across all categories
    applied = {c: "" for c in ["borders", "masks", "effects"]}
    if category in applied:
        applied[category] = item
    user_store["applied"] = applied
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
        {"borders": [], "masks": [], "effects": [], "powerups": [], "applied": {"borders": "", "masks": "", "effects": ""}},
    )
    if "masks" not in user_store and "hats" in user_store:
        user_store["masks"] = user_store.get("hats", [])
        user_store.pop("hats", None)
    applied = user_store.get("applied", {})
    if not isinstance(applied, dict):
        applied = {}
    if "masks" not in applied and "hats" in applied:
        applied["masks"] = applied.get("hats", "")
        applied.pop("hats", None)
    for cat in ["borders", "masks", "effects"]:
        applied.setdefault(cat, "")
    # Enforce a single active cosmetic; keep the first non-empty entry
    non_empty = [(cat, val) for cat, val in applied.items() if val]
    if len(non_empty) > 1:
        keep_cat, keep_val = non_empty[0]
        applied = {cat: (keep_val if cat == keep_cat else "") for cat in ["borders", "masks", "effects"]}
    user_store["applied"] = applied
    data[user] = user_store
    save_json(CUSTOM_PATH, data)
    return user_store


def inject_css() -> None:
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;600;700&family=Bebas+Neue&display=swap');
    :root {
        --ufc-red: #BE1A17;
        --font-body: 'Barlow', 'Segoe UI', sans-serif;
        --font-heading: 'Bebas Neue', 'Barlow', sans-serif;
        --login-field-width: 320px;
    }
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], .main {background:#0E0C0B !important; font-family:var(--font-body);}
    body {background:#0E0C0B;}
    .block-container {padding-top: 0rem;}
    .ufc-hero {background: linear-gradient(135deg, #0a0a0a, #1a0000); border:1px solid #ff3b3b33; padding:18px; border-radius:18px; box-shadow:0 12px 32px rgba(0,0,0,.45);}
    .metric-card {padding:14px; border-radius:12px; border:1px solid #ffffff22; background:rgba(255,255,255,0.03);}
    .stat-badge {background:#ff3b3b22; color:#f7f7f7; padding:6px 12px; border-radius:999px; border:1px solid #ff3b3b55;}
    .store-card {border:1px solid #ffffff22; border-radius:12px; padding:12px; background:rgba(255,255,255,0.03);}
    .owned {opacity:0.65;}
    .login-card {background:#000; padding:28px; border-radius:16px; border:none; box-shadow:0 20px 50px rgba(0,0,0,0.75);}
    .login-input input {background:#fff !important; color:#f5f5f5 !important; border:1px solid var(--ufc-red) !important; border-radius:10px !important;}
    .login-button button {background:var(--ufc-red) !important; color:#BE1A17 !important; border:none !important; border-radius:12px !important; height:52px; font-weight:700; letter-spacing:1px; font-family:var(--font-heading); text-transform:uppercase;}
    .suggestion-box {border:none; background:transparent; padding:0; max-height:220px; overflow-y:auto;}
    .suggestion-item {padding:10px; border-radius:8px; color:#f5f5f5;}
    .suggestion-item:hover {background:#ff3b3b33; cursor:pointer;}
    .suggestions-title {text-align:center; color:var(--ufc-red); font-weight:800; font-size:18px; margin:2px 0 6px 0; letter-spacing:0.3px;}
    [data-testid="stSidebar"] > div {display:flex; flex-direction:column; height:100vh;}
    [data-testid="stSidebar"] .stButton>button {background:linear-gradient(90deg,#1b1b1b,#2b0a0a); border:1px solid #ff3b3b55; color:#f5f5f5; border-radius:12px; width:100%; height:46px; font-weight:600; letter-spacing:0.5px;}
    [data-testid="stSidebar"] .stButton>button:hover {border-color:#ff5555; color:#fff;}
    [data-testid="stSidebar"] .nav-tab {padding:12px 14px; border-radius:12px; border:1px solid #ff3b3b55; background:#1a0a0a; color:#f5f5f5; font-weight:700; letter-spacing:0.5px; text-align:center; margin-bottom:8px;}
    [data-testid="stSidebar"] .nav-tab.active {background:linear-gradient(90deg,#ff3b3b,#b10000); border-color:#ff3b3b; color:#fff;}
    .preview-frame {width:128px; height:128px; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:auto; background:linear-gradient(135deg,#1c1c1c,#0a0a0a); position:relative; overflow:visible; box-shadow:0 8px 28px rgba(0,0,0,0.45);}
    .preview-avatar-img {width:116px; height:116px; border-radius:50%; object-fit:cover; object-position:center;}
    .preview-mask {position:absolute; top:-6px; left:50%; transform:translateX(-50%); width:60px; pointer-events:none; filter:drop-shadow(0 4px 12px rgba(0,0,0,0.45));}
    .avatar-with-mask {overflow:visible;}
    .avatar-mask {position:absolute; left:50%; transform:translateX(-50%); top:-4px; width:34px; pointer-events:none; filter:drop-shadow(0 3px 10px rgba(0,0,0,0.5));}
    .preview-effect {position:absolute; inset:-6px; border-radius:50%; box-shadow:0 0 18px 6px rgba(255,59,59,0.35);}
    .leaderboard-list {display:flex; flex-direction:column; gap:12px;}
    .leaderboard-card {border:1px solid #ffffff18; border-radius:14px; padding:12px 14px; background:#0f0c0c; color:#f5f5f5; box-shadow:0 10px 26px rgba(0,0,0,0.35);}
    .leaderboard-card .top {display:flex; align-items:center; justify-content:space-between; gap:12px;}
    .leaderboard-card .user {display:flex; align-items:center; gap:10px; font-weight:700;}
    .leaderboard-card .rank {font-weight:800; color:#ffdedb; letter-spacing:0.6px;}
    .leaderboard-card .stats {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:10px;}
    .leaderboard-card .stat-label {color:#999; font-size:12px; letter-spacing:0.4px;}
    .leaderboard-card .stat-value {font-size:18px; font-weight:700;}
    .stats-grid {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px;}
    .damage-list {display:flex; flex-direction:column; gap:10px;}
    .damage-card {border:1px solid #ffffff18; border-radius:14px; padding:12px 14px; background:#0f0c0c; color:#f5f5f5;}
    .damage-card .row {display:flex; align-items:center; justify-content:space-between; gap:10px;}
    .damage-card .label {color:#999; font-size:12px; letter-spacing:0.4px;}
    .damage-card .value {font-size:16px; font-weight:700;}
    .login-title {text-align:center; margin:4px 0 6px 0; color:var(--ufc-red) !important; text-transform:uppercase; letter-spacing:2px; font-family:var(--font-heading); font-size:32px;}
    .login-subtext {text-align:center; margin:-2px 0 10px 0; color:#cccccc;}
    .login-form {display:flex; flex-direction:column; align-items:center; text-align:center; gap:10px;}
    .login-form .stTextInput>div>div {width:var(--login-field-width); max-width:92vw; margin:0 auto;}
    .login-form .stTextInput>div>div input {text-align:center; font-family:var(--font-body);}
    .login-form .stButton {display:flex; justify-content:center; width:var(--login-field-width); max-width:92vw; margin:0 auto;}
    .login-form .stButton>button {display:block; width:100%; max-width:100%; margin:4px auto 0 auto; background:var(--ufc-red) !important; color:#fff !important; border:1px solid var(--ufc-red) !important; border-radius:12px; height:52px; font-weight:700; letter-spacing:1.1px; text-transform:uppercase; font-family:var(--font-heading); box-shadow:0 8px 18px rgba(190,26,23,0.35);}
    .login-pane form {display:flex; flex-direction:column; align-items:center; gap:10px; margin-top:4px;}
    .login-pane form input {width:var(--login-field-width) !important; max-width:92vw; margin:0 auto;}
    .login-pane form button {width:var(--login-field-width) !important; max-width:92vw; margin:2px auto 0 auto !important; display:block; background:var(--ufc-red) !important; color:#fff !important; border:1px solid var(--ufc-red) !important; height:52px; border-radius:12px;}
    .login-pane .stButton>button {background:var(--ufc-red) !important; color:#fff !important; width:var(--login-field-width); max-width:92vw; height:52px; border:1px solid var(--ufc-red) !important; border-radius:12px;}
    .login-hero-wrap {display:flex; align-items:center; justify-content:center; text-align:center; padding:0 0 4px 0; margin-top:-140px;}
    .login-hero-img {width:min(78vw, 500px); height:auto; max-height:320px; object-fit:contain;}
    @media (max-width: 1200px){
        .block-container {padding-left:16px !important; padding-right:16px !important;}
        [data-testid="stSidebar"] > div {height:auto;}
    }
    @media (max-width: 900px){
        html, body, .stApp {overflow-x:hidden;}
        [data-testid="stHorizontalBlock"] {flex-direction:column !important;}
        [data-testid="column"] {width:100% !important; padding-left:0 !important; padding-right:0 !important;}
        [data-testid="stSidebar"] {width:100% !important; position:relative;}
        [data-testid="stSidebar"] > div {height:auto;}
        .block-container {padding-left:12px !important; padding-right:12px !important;}
        .leaderboard-card .top {flex-direction:column; align-items:flex-start;}
        .leaderboard-card .stats {grid-template-columns:repeat(2,minmax(0,1fr));}
        .stats-grid {grid-template-columns:1fr;}
        .preview-frame {width:110px; height:110px;}
        .preview-avatar-img {width:98px; height:98px;}
        .damage-card .row {flex-direction:column; align-items:flex-start;}
        .login-hero-img {max-height:220px; width:min(88vw, 420px);}
        .login-pane {padding:16px;}
        .login-form .stTextInput>div>div input {text-align:center;}
        .login-hero-wrap {margin-top:-90px;}
    }
    @media (max-width: 680px){
        .leaderboard-card .stats {grid-template-columns:1fr;}
    }
    @media (max-width: 540px){
        .block-container {padding-left:10px !important; padding-right:10px !important;}
        .leaderboard-card {padding:10px 12px;}
        .preview-frame {width:96px; height:96px;}
        .preview-avatar-img {width:86px; height:86px;}
        .login-card {padding:20px;}
        .login-hero-wrap {margin-top:-50px;}
        .login-hero-img {max-height:180px;}
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def login_screen(followers: List[str]) -> None:
    st.markdown("<div class='login-pane'>", unsafe_allow_html=True)
    img_src = encode_image(settings.login_image_path)
    if img_src:
        st.markdown(
            f"<div class='login-hero-wrap'>"
            f"<img src=\"{img_src}\" class='login-hero-img' alt='UFC login hero'/>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.image(str(settings.login_image_path), use_container_width=True)

    st.markdown("<h3 class='login-title'>Enter the Octagon</h3>", unsafe_allow_html=True)
    st.markdown("<p class='login-subtext'>Enter insta handle to log in</p>", unsafe_allow_html=True)
    st.markdown("<div class='login-form'>", unsafe_allow_html=True)
    def _attempt_login() -> None:
        st.session_state["login_attempt"] = st.session_state.get("login_query", "").strip()
    query = st.text_input("Username", key="login_query", label_visibility="collapsed", placeholder="Type your handle", help=None, on_change=_attempt_login)
    submitted = st.button("Enter", key="login_button", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    attempt_val = st.session_state.pop("login_attempt", None) if "login_attempt" in st.session_state else None
    if submitted and query:
        attempt_val = query.strip()
    if attempt_val:
        if attempt_val in followers:
            st.session_state["user"] = attempt_val
            st.rerun()

    normalized_followers = sorted({str(f).strip() for f in followers if str(f).strip()}, key=str.lower)
    q = query.strip().lstrip("@").lower()
    if q:
        prefix_matches = [f for f in normalized_followers if f.lower().startswith(q)]
        contains_matches = [f for f in normalized_followers if q in f.lower() and f not in prefix_matches]
        filtered = prefix_matches + contains_matches
    else:
        filtered = normalized_followers[:20]
    suggestions = filtered[:50]
    if query and suggestions:
        st.markdown("<div class='suggestions-title'>Suggestions</div>", unsafe_allow_html=True)
        chip_cols = st.columns(2)
        for idx, name in enumerate(suggestions):
            with chip_cols[idx % 2]:
                if st.button(name, key=f"pick-{name}", use_container_width=True):
                    st.session_state["user"] = name
                    st.rerun()
    elif query and not suggestions:
        st.info("No matching followers yet. Try a different handle.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar_nav() -> str:
    active = st.session_state.get("nav", NAV_MAIN[0])

    img_src = encode_image(settings.login_image_path)
    if img_src:
        st.sidebar.markdown(
            f"<div style='padding:10px 6px 18px 6px;'><img src=\"{img_src}\" style='width:100%;border-radius:12px;object-fit:cover;'/></div>",
            unsafe_allow_html=True,
        )

    for item in NAV_MAIN:
        if item == active:
            st.sidebar.markdown(f"<div class='nav-tab active'>{item}</div>", unsafe_allow_html=True)
        else:
            if st.sidebar.button(item, key=f"nav-{item}"):
                st.session_state["nav"] = item
                st.rerun()

    st.sidebar.markdown("<div style='flex:1 1 auto;'></div><div style='height:12px;'></div>", unsafe_allow_html=True)

    for item in NAV_BOTTOM:
        if item == active:
            st.sidebar.markdown(f"<div class='nav-tab active'>{item}</div>", unsafe_allow_html=True)
        else:
            if st.sidebar.button(item, key=f"nav-{item}"):
                st.session_state["nav"] = item
                st.rerun()

    return active


def top_bar(user: str) -> None:
    logo_src = encode_image(LOGO_PATH)
    if logo_src:
        st.markdown(
            f"<div style='text-align:center;padding:8px 0 14px 0;'>"
            f"<img src=\"{logo_src}\" alt=\"UFC\" "
            f"style='width:260px;max-width:40vw;height:auto;object-fit:contain;display:block;margin:0 auto;'/>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
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
        "<h2 style='color:#ff3b3b;text-transform:uppercase;letter-spacing:2px;margin-bottom:16px;text-align:center;'>Leaderboard</h2>",
        unsafe_allow_html=True,
    )
    stats = load_json(STATS_PATH, {})
    board = load_json(SCOREBOARD_PATH, {})
    custom_data = load_customizations_data()
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

    row_html_parts = []
    for row in rows:
        crown = crown_svg() if row["wins"] > 0 else ""
        mask_name = get_active_mask(row["user"], custom_data)
        avatar = avatar_with_mask_html(row["pic"], mask_name, size=36, margin_right=10, initial=row["user"][:1])
        row_html_parts.append(
            f"<div class='leaderboard-card'>"
            f"<div class='top'>"
            f"<div class='user'>{avatar}<div>@{row['user']}</div></div>"
            f"<div class='rank'>#{row['rank']}{crown}</div>"
            f"</div>"
            f"<div class='stats'>"
            f"<div><div class='stat-label'>Points</div><div class='stat-value'>{row['points']}</div></div>"
            f"<div><div class='stat-label'>Games</div><div class='stat-value'>{row['runs']}</div></div>"
            f"<div><div class='stat-label'>Total Damage</div><div class='stat-value'>{row['damage']}</div></div>"
            f"</div>"
            f"</div>"
        )

    leaderboard_html = "<div class='leaderboard-list'>" + "".join(row_html_parts) + "</div>"
    st.markdown(leaderboard_html, unsafe_allow_html=True)


def my_stats_page(user: str) -> None:
    stats = load_json(STATS_PATH, {})
    custom_data = load_customizations_data()
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
        pic_src = encode_image(pic) if pic else ""
        mask_name = get_active_mask(user, custom_data)
        avatar_html = avatar_with_mask_html(pic_src, mask_name, size=220, initial=user)
        st.markdown(avatar_html, unsafe_allow_html=True)
    with col_meta:
        stat_html = f"""
        <div class='stats-grid'>
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
        rows_html = []
        for opponent, data in top_targets:
            rows_html.append(
                f"<div class='damage-card'>"
                f"<div class='row'>"
                f"<div><div class='label'>Opponent</div><div class='value'>@{opponent}</div></div>"
                f"<div><div class='label'>Damage</div><div class='value'>{int(data.get('damage', 0))}</div></div>"
                f"<div><div class='label'>Hits</div><div class='value'>{data.get('hits', 0)}</div></div>"
                f"</div>"
                f"</div>"
            )
        damage_html = "<div class='damage-list'>" + "".join(rows_html) + "</div>"
        st.markdown(damage_html, unsafe_allow_html=True)


STORE_ITEMS = {
    "borders": [{"name": "Red Steel", "price": 0}, {"name": "Neon Pulse", "price": 0}],
    "masks": [{"name": "Spartan Helm", "price": 0}, {"name": "Cowboy", "price": 0}],
    "effects": [{"name": "Arc Zap", "price": 0}, {"name": "Wave Pulse", "price": 0}],
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
        mask_icon = ""
        effect_glow = ""
        if category == "borders":
            border_color = "#ff3b3b" if "Red" in item_name else "#00e0ff"
        if category == "masks":
            mask_icon = mask_data_uri(item_name, size=72)
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
        mask_html = f"<img class='preview-mask' src='{mask_icon}' alt='{item_name} mask' />" if mask_icon else ""
        effect_html = f"<div class='preview-effect' style='{effect_glow}'></div>" if effect_glow else ""
        return f"<div class='preview-frame' style='border:3px solid {border_color};'>{avatar_img}{mask_html}{effect_html}</div>"

    for category in ["borders", "masks", "effects"]:
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
                            st.rerun()
                else:
                    if price == 0:
                        if st.button("Claim (Free)", key=f"claim-{category}-{item['name']}"):
                            acquire_item(user, category, item["name"])
                            set_applied(user, category, item["name"])
                            st.success(f"Claimed {item['name']}")
                            st.rerun()
                    else:
                        if st.button(f"Buy {item['name']}", key=f"buy-{category}-{item['name']}"):
                            if PAYMENT_MODE != "prod":
                                acquire_item(user, category, item["name"])
                                set_applied(user, category, item["name"])
                                st.success(f"Purchased {item['name']} (dev mode)")
                                st.rerun()
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
                        st.rerun()
                else:
                    if st.button(f"Buy {item['name']}", key=f"buy-power-{item['name']}"):
                        if PAYMENT_MODE != "prod":
                            acquire_item(user, "powerups", item["name"])
                            st.success(f"Purchased {item['name']} (dev mode)")
                            st.rerun()
                        else:
                            prompt_purchase(item["name"])


def powerups_placeholder() -> None:
    st.markdown("### Power Ups")
    st.info("Comming soon")


def support_page() -> None:
    st.markdown("### Support")
    st.info("Coming soon")


def app():
    st.set_page_config(page_title="Ultimate Followers Championship", layout="wide", page_icon=PAGE_ICON)
    st.markdown(
        """
        <style>
        html,body,#root,[data-testid="stAppViewContainer"],[data-testid="stApp"],.main,.block-container{
          margin:0 !important;
          padding:0 !important;
          background:#0E0C0B !important;
          width:100%;
          height:100%;
          overflow-x:hidden;
        }
        [data-testid="stAppViewContainer"] > header,
        [data-testid="stHeader"],
        header {display:none !important; height:0 !important; padding:0 !important; margin:0 !important;}
        [data-testid="stToolbar"],
        [data-testid="stActionMenu"],
        [data-testid="baseButton-toolbar"] {display:none !important;}
        .main {padding:0 !important;}
        .block-container{padding-top:0 !important;padding-left:0 !important;padding-right:0 !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )
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
        # powerups_page(user)  # Temporarily disabled; keep logic for future use
        powerups_placeholder()
    else:
        support_page()


if __name__ == "__main__":
    app()
