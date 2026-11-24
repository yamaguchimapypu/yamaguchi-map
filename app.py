import base64
import hashlib
import html
import json
import math
import os
import random
import re
import secrets
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from PIL import Image, ImageOps

st.set_page_config(page_title="やまぐちクチコミ帖", page_icon="🌿", layout="wide")

# ---------- 色と文字（白地に、くすんだ緑。ここを変えるとサイト全体の色が変わります） ----------
ACCENT = "#4b7a62"  # アクセントの緑（NEWの札・順位のリボン・リンク）
DARK = "#223a2d"    # 濃い緑（見出し・アイコン）
INK = "#1c2520"     # 本文の文字
SOFT = "#ffffff"    # ページの背景
TINT = "#e3eae4"    # タグや、写真がないときの薄い緑
LINE = "#dfe3df"    # 細い区切り線
MUTED = "#6f7b73"   # 補足の文字
HOME_NEW_N = 4      # ホームの New に出す枚数（「View more」で全部のページへ）
SERIF = "'Cormorant Garamond','Shippori Mincho','Hiragino Mincho ProN',serif"  # 見出しの明朝体
# 本文。英字は見出し・メニューと同じ Cormorant Garamond（先に書いてあるので英字だけこれになり、日本語は Noto Sans JP）
SANS = "'Cormorant Garamond','Noto Sans JP','Hiragino Sans','Yu Gothic',sans-serif"
HIDE_STREAMLIT_PARTS = True  # 公開用の見た目（Streamlitの標準の部品を隠す）。元に戻したいときは False
CHROME_CSS = ("#MainMenu, footer, .stDeployButton, [data-testid='stMainMenu'], [data-testid='stAppDeployButton'],"
              " [data-testid='stDecoration'], [data-testid='stSidebarCollapsedControl'],"
              " [data-testid='stExpandSidebarButton'] { display:none !important; }") if HIDE_STREAMLIT_PARTS else ""
# メニューの動き（秒）。もっとゆっくりにしたいときは数字を大きくしてください
MENU_SLIDE = 0.7    # メニューが横から出てくる時間
MENU_START = 0.3    # 最初の文字が出はじめるまでの時間
MENU_STEP = 0.07    # 文字が1つずつ遅れて出る間隔（上から順に出ます）
MENU_FONT = 1.3     # メニューの文字の大きさ（rem）。小さくしたいときは 1.0 のように数字を下げてください
MENU_DELAYS = "".join(
    f".st-key-drawer > .stElementContainer:nth-child({i}) {{ animation-delay:{MENU_START + i * MENU_STEP:.2f}s; }}\n"
    for i in range(1, 21))


def _icon(body, fill="none"):
    """バーやカードのマーク（ハート・虫眼鏡・吹き出し）を、細い線の絵として作る"""
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='{fill}' stroke='black' "
           f"stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'>{body}</svg>")
    return 'url("data:image/svg+xml,' + svg.replace("<", "%3C").replace(">", "%3E") + '")'


HEART = ("<path d='M12 20.5C5 15 3 11.5 3 8.6C3 6.1 4.9 4.2 7.3 4.2C9.2 4.2 10.8 5.3 12 7.1C13.2 5.3 14.8 4.2 "
         "16.7 4.2C19.1 4.2 21 6.1 21 8.6C21 11.5 19 15 12 20.5Z'/>")
ICON_HEART = _icon(HEART)                  # 保存がまだ無いとき：線だけのハート
ICON_HEART_ON = _icon(HEART, fill="black")  # 保存があるとき：塗りつぶしのハート
ICON_SEARCH = _icon("<circle cx='10.5' cy='10.5' r='6.5'/><path d='M15.5 15.5L20.5 20.5'/>")
ICON_POST = _icon("<path d='M4 4.5H20V16H10.5L6 20.5V16H4Z'/><path d='M12 7.5V13M9.25 10.25H14.75'/>")
# 地図のピンの色（ACCENT と同じ色）
PIN = [int(ACCENT[i:i + 2], 16) for i in (1, 3, 5)] + [235]
# 画面の上のほうの部品どうしで共通の、マーク用の下ごしらえ（絵を切り抜いて色を塗る）
MASK = ("-webkit-mask-repeat:no-repeat; mask-repeat:no-repeat; -webkit-mask-position:center; mask-position:center; "
        "-webkit-mask-size:contain; mask-size:contain;")
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600&family=Noto+Sans+JP:wght@400;500;700&family=Shippori+Mincho:wght@500;600&display=swap');
{CHROME_CSS}
html, body, .stApp, .stMarkdown, p, label, button, input, textarea {{ font-family:{SANS} !important; }}
h1, h2, h3, h4 {{ font-family:{SERIF} !important; font-weight:500; letter-spacing:.08em; color:{DARK}; }}
.stApp {{ background:{SOFT}; color:{INK}; letter-spacing:.04em; font-variant-numeric:lining-nums; }}
div[data-testid="stMarkdownContainer"] a {{ color:{ACCENT} !important; }}

/* ボタンは細い線のふちだけ（押すと濃くなる） */
div.stButton > button, div[data-testid="stFormSubmitButton"] > button, [data-testid="stFileUploaderDropzone"] button {{
    border-radius:999px; border:1px solid #c3cdc5; background:#fff; color:{INK}; letter-spacing:.1em; }}
div.stButton > button {{ width:100%; }}
div.stButton > button:hover, div.stButton > button:focus:not(:active),
div[data-testid="stFormSubmitButton"] > button:hover, div[data-testid="stFormSubmitButton"] > button:focus:not(:active),
[data-testid="stFileUploaderDropzone"] button:hover, [data-testid="stFileUploaderDropzone"] button:focus:not(:active) {{
    background:#f5f8f5; border-color:{DARK}; color:{DARK}; }}
div.stButton > button:active, div[data-testid="stFormSubmitButton"] > button:active,
[data-testid="stFileUploaderDropzone"] button:active {{ background:{TINT}; border-color:{DARK}; color:{DARK}; }}
div.stButton > button:focus-visible, div[data-testid="stFormSubmitButton"] > button:focus-visible,
[data-testid="stFileUploaderDropzone"] button:focus-visible {{ box-shadow:0 0 0 .2rem rgba(34,58,45,.25); }}
div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div {{
    border-radius:0 !important; background:#fff !important; border:1px solid {LINE} !important; }}
div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within,
div[data-baseweb="select"] > div:focus-within {{ border-color:{DARK} !important; }}

/* カード：枠も影もなく、写真が主役 */
.card {{ position:relative; }}
.ph {{ position:relative; aspect-ratio:4/5; overflow:hidden; background:{TINT}; }}
.ph img {{ width:100%; height:100%; object-fit:cover; display:block; transition:transform .5s ease; }}
.ph.none {{ display:flex; align-items:center; justify-content:center; color:{MUTED}; font-family:{SERIF};
    letter-spacing:.3em; font-size:.8rem; }}
.pcount {{ position:absolute; left:.5rem; bottom:.5rem; background:rgba(28,37,32,.62); color:#fff; font-size:.78rem;
    letter-spacing:.14em; padding:.15rem .5rem; }}
[class*="st-key-cardwrap-"] {{ position:relative; gap:0 !important; }}
[class*="st-key-cardwrap-"]:hover .ph img {{ transform:scale(1.04); }}
.ribbon {{ position:absolute; top:0; left:0; z-index:1; width:92px; height:92px; color:#fff;
    background:linear-gradient(135deg,{ACCENT} 50%,transparent 50%); font-family:{SERIF};
    font-variant-numeric:lining-nums; }}
.ribbon i {{ position:absolute; top:8px; left:10px; font-style:normal; font-size:.72rem; letter-spacing:.08em; }}
.ribbon b {{ position:absolute; top:17px; left:23px; font-size:1.9rem; font-weight:500; line-height:1; }}
.ribbon.two b {{ top:22px; left:13px; font-size:1.35rem; }}
.tags {{ margin:.75rem 0 .1rem; display:flex; flex-wrap:wrap; gap:.3rem; }}
.tag {{ background:{TINT}; color:#3e5a4a; padding:1px 7px; font-size:.84rem; letter-spacing:.06em; }}
.tag.new {{ background:{ACCENT}; color:#fff; }}
.nm {{ font-weight:500; font-size:1rem; line-height:1.5; margin:.25rem 0 0; }}
.price {{ font-size:1.05rem; margin:.1rem 0 .4rem; display:flex; flex-wrap:wrap; align-items:baseline; column-gap:.9rem; }}
.price .saves {{ color:{ACCENT}; font-size:.88rem; white-space:nowrap; }}
/* ホームのランキング：横にスライド（スクロール）する。下に細いバーが出る */
.st-key-rankhead {{ margin-top:2.6rem; }}
.st-key-rankhead [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap !important; align-items:flex-end;
    gap:1.8rem !important; }}
/* Streamlit は文章の下に -16px の余白を付けるため、大きな見出しの下が切れて見えた。ここでは付けない */
.st-key-rankhead [data-testid="stMarkdownContainer"] {{ margin-bottom:0 !important; }}
.st-key-rankhead [data-testid="stColumn"], .st-key-rankhead [data-testid="column"] {{ flex:0 0 auto !important;
    width:auto !important; min-width:0 !important; }}
.st-key-rankhead [data-testid="stColumn"]:first-child, .st-key-rankhead [data-testid="column"]:first-child {{
    flex:1 0 auto !important; }}
.st-key-rankhead .stButton > button {{ width:auto; border:none; border-radius:0; background:transparent; color:{MUTED};
    padding:.5rem 0; min-height:0; position:relative; }}
.st-key-rankhead .stButton > button, .st-key-rankhead .stButton > button p {{ font-size:.95rem; font-weight:500;
    letter-spacing:.2em; text-transform:uppercase; }}
.st-key-rankhead .stButton > button::after {{ content:""; position:absolute; left:0; right:.2em; bottom:2px; height:1px;
    background:{DARK}; transform:scaleX(0); transform-origin:left; transition:transform .25s; }}
.st-key-rankhead .stButton > button:hover::after, [class*="st-key-rt-on-"] .stButton > button::after {{
    transform:scaleX(1); }}
.st-key-rankhead .stButton > button:hover, .st-key-rankhead .stButton > button:focus:not(:active),
.st-key-rankhead .stButton > button:active, [class*="st-key-rt-on-"] .stButton > button {{
    background:transparent; color:{INK}; }}
[class*="st-key-slide-"] [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap !important; gap:1rem !important;
    overflow-x:auto; padding-bottom:1.1rem; scroll-snap-type:x proximity;
    scrollbar-width:auto; scrollbar-color:auto; }}  /* Streamlit は標準でバーを透明にしているので、ここでは元に戻す */
[class*="st-key-slide-"] [data-testid="stHorizontalBlock"]::-webkit-scrollbar {{ height:5px; }}
[class*="st-key-slide-"] [data-testid="stHorizontalBlock"]::-webkit-scrollbar-track {{ background:{TINT}; }}
[class*="st-key-slide-"] [data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb {{ background:{ACCENT}; }}
@supports not selector(::-webkit-scrollbar) {{
    [class*="st-key-slide-"] [data-testid="stHorizontalBlock"] {{ scrollbar-width:thin; scrollbar-color:{ACCENT} {TINT}; }} }}
[class*="st-key-slide-"] [data-testid="stColumn"], [class*="st-key-slide-"] [data-testid="column"] {{
    flex:0 0 clamp(210px, 23vw, 290px) !important; width:auto !important; min-width:0 !important;
    scroll-snap-align:start; }}
@media (max-width:640px) {{
    .st-key-rankhead [data-testid="stHorizontalBlock"] {{ flex-wrap:wrap !important; gap:.2rem .7rem !important; }}
    .st-key-rankhead [data-testid="stColumn"]:first-child, .st-key-rankhead [data-testid="column"]:first-child {{
        flex:1 0 100% !important; }}
    .st-key-rankhead .stButton > button, .st-key-rankhead .stButton > button p {{ font-size:.8rem; letter-spacing:.08em; }}
    [class*="st-key-slide-"] [data-testid="stColumn"], [class*="st-key-slide-"] [data-testid="column"] {{
        flex:0 0 72vw !important; }} }}
.saves {{ color:{ACCENT}; }}
.meta {{ color:{MUTED}; font-size:.78rem; margin-top:.25rem; line-height:1.6; }}
.maplink {{ color:{ACCENT} !important; text-decoration:none; border-bottom:1px solid currentColor; }}
.rv {{ color:#46524b; font-size:.84rem; line-height:1.7; display:-webkit-box; -webkit-line-clamp:3;
    -webkit-box-orient:vertical; overflow:hidden; margin:.2rem 0 .4rem; }}
/* カード全体を押せるようにする、見えないボタン */
[class*="st-key-cd-"] {{ position:absolute; inset:0; z-index:2; margin:0; width:100% !important; height:100% !important; }}
[class*="st-key-cd-"] .stButton {{ width:100%; height:100%; }}
[class*="st-key-cd-"] .stButton > button {{ width:100%; height:100%; opacity:0; cursor:pointer; border-radius:0; }}
/* 写真の右上のハート（保存するとハートが塗られる） */
[class*="st-key-cs-"], [class*="st-key-cson-"] {{ position:absolute; top:.6rem; right:.6rem; z-index:3; margin:0;
    width:auto !important; height:auto !important; }}
[class*="st-key-cs-"] .stButton button, [class*="st-key-cson-"] .stButton button {{ position:relative; width:38px;
    height:38px; min-height:0; padding:0; border:none; border-radius:50%; background:rgba(255,255,255,.92); }}
[class*="st-key-cs-"] .stButton button:hover, [class*="st-key-cson-"] .stButton button:hover {{ background:#fff; }}
[class*="st-key-cs-"] .stButton button p, [class*="st-key-cson-"] .stButton button p {{ position:absolute; width:1px;
    height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; margin:0; }}
[class*="st-key-cs-"] .stButton button::before, [class*="st-key-cson-"] .stButton button::before {{ content:"";
    position:absolute; left:9px; top:9px; width:20px; height:20px; background:{DARK}; transition:background .2s; {MASK} }}
[class*="st-key-cs-"] .stButton button::before {{ -webkit-mask-image:{ICON_HEART}; mask-image:{ICON_HEART}; }}
[class*="st-key-cson-"] .stButton button::before {{ background:{ACCENT};
    -webkit-mask-image:{ICON_HEART_ON}; mask-image:{ICON_HEART_ON}; }}
[class*="st-key-cs-"] .stButton button:hover::before {{ background:{ACCENT}; }}

/* ホームの上の紹介・見出し・いちばん下のINFO */
.hero {{ background:#f3f6f3; padding:3.4rem 1.5rem; text-align:center; margin:.5rem 0 2rem; }}
.hero-en {{ font-family:{SERIF}; letter-spacing:.4em; font-size:.85rem; color:{ACCENT}; }}
.hero-title {{ font-family:'Shippori Mincho','Hiragino Mincho ProN',serif; margin:.6rem 0; font-size:2.4rem;
    font-weight:500; letter-spacing:.18em; color:{DARK}; }}
.hero-sub {{ color:{INK}; margin:.4rem 0 1.4rem; letter-spacing:.12em; font-size:.92rem; }}
.hero-n {{ display:inline-block; border:1px solid {DARK}; border-radius:999px; padding:.25rem 1.2rem;
    font-size:.84rem; letter-spacing:.24em; color:{DARK}; }}
.sec {{ margin:2.6rem 0 1rem; }}
.sec-en {{ font-family:{SERIF}; font-size:2.2rem; font-weight:500; letter-spacing:.06em; color:{INK}; line-height:1.2; }}
.sec-ja {{ font-size:.78rem; color:{MUTED}; letter-spacing:.2em; margin-top:.2rem; }}
/* ホームの New の下の「View more」：まん中に置いた、細い線の丸いボタン（押すと濃くなる） */
.st-key-new-more {{ margin-top:1.6rem; }}
.st-key-new-more .stButton {{ display:flex; justify-content:center; }}
.st-key-new-more .stButton > button {{ width:auto; min-height:0; padding:.7rem 3.4rem; border:1px solid {DARK};
    background:transparent; color:{DARK}; transition:background .25s, color .25s; }}
.st-key-new-more .stButton > button p {{ font-family:{SERIF} !important; font-size:1.05rem; font-weight:500;
    letter-spacing:.24em; margin:0; }}
.st-key-new-more .stButton > button:hover, .st-key-new-more .stButton > button:focus:not(:active),
.st-key-new-more .stButton > button:active {{ background:{DARK}; border-color:{DARK}; color:#fff; }}
.st-key-drawer .stButton > button:active {{ background:transparent; color:{ACCENT}; }}
.foot {{ border-top:1px solid {INK}; margin-top:4.5rem; padding:2.6rem 0 1.5rem; color:{INK}; font-size:.85rem;
    line-height:2; }}
.foot-sec {{ margin-bottom:2rem; }}
.foot-h {{ font-family:{SERIF}; font-size:1.5rem; letter-spacing:.2em; text-transform:uppercase; margin:0 0 .6rem; }}
.copy {{ font-size:.82rem; color:{MUTED}; margin-top:1.5rem; }}

/* いちばん上のバー：左に三本線、まん中にサイト名、右にマーク */
header[data-testid="stHeader"] {{ background:rgba(255,255,255,.96) !important; backdrop-filter:blur(8px);
    border-bottom:1px solid {LINE}; height:3.6rem !important; min-height:0 !important; }}
.st-key-hamburger, .st-key-brand {{ position:fixed; z-index:999991; width:auto !important; }}
.st-key-hamburger {{ top:.55rem; left:.9rem; }}
.st-key-brand {{ top:.55rem; left:50%; transform:translateX(-50%); }}
.st-key-brand .stButton > button {{ width:auto; height:40px; border:none; border-radius:0; background:transparent;
    color:{DARK}; padding:0 .4rem; }}
.st-key-brand .stButton > button, .st-key-brand .stButton > button p {{ font-family:{SERIF} !important;
    font-size:1.2rem; font-weight:600; letter-spacing:.2em; }}
.st-key-brand .stButton > button:hover, .st-key-brand .stButton > button:active {{ background:transparent;
    color:{ACCENT}; }}
.st-key-hamburger .stButton > button, .st-key-menu-close .stButton > button {{
    position:relative; width:44px; height:40px; min-height:0; padding:0; border:none; border-radius:50%;
    background:transparent; }}
.st-key-hamburger .stButton > button:hover, .st-key-menu-close .stButton > button:hover {{ background:{TINT}; }}
.st-key-hamburger button p, .st-key-menu-close button p, .st-key-backdrop button p {{
    position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }}
.st-key-hamburger button::before {{ content:""; position:absolute; left:11px; top:12px; width:22px; height:2px;
    border-radius:2px; background:{DARK}; box-shadow:0 7px 0 {DARK}, 0 14px 0 {DARK}; }}
.st-key-menu-close button::before, .st-key-menu-close button::after {{ content:""; position:absolute; left:10px;
    top:19px; width:24px; height:2px; border-radius:2px; background:{DARK}; transform:rotate(45deg); }}
.st-key-menu-close button::after {{ transform:rotate(-45deg); }}
@media (max-width:520px) {{
    .st-key-brand {{ left:4.3rem; transform:none; }}
    .st-key-brand .stButton > button, .st-key-brand .stButton > button p {{ font-size:1rem; letter-spacing:.1em; }} }}

/* 右端のマーク：お気に入り・検索・クチコミ（いつも表示。マークだけで、保存があるとハートに数字が付く） */
.st-key-actions {{ position:fixed; top:.55rem; right:.9rem; z-index:999991; width:auto !important;
    display:flex !important; flex-direction:row !important; align-items:center; gap:.1rem !important; }}
.st-key-actions > .stElementContainer {{ width:auto !important; }}
.st-key-actions .stButton button {{ position:relative; width:42px; height:40px; min-height:0; padding:0; border:none;
    border-radius:50%; background:transparent; }}
.st-key-actions .stButton button:hover {{ background:{TINT}; }}
.st-key-actions .stButton button p {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0);
    white-space:nowrap; margin:0; }}
.st-key-actions .stButton button::before {{ content:""; position:absolute; left:9px; top:8px; width:24px; height:24px;
    background:{DARK}; transition:background .2s; {MASK} }}
.st-key-actions .st-key-hd-fav button::before {{ -webkit-mask-image:{ICON_HEART}; mask-image:{ICON_HEART}; }}
.st-key-actions .st-key-hd-fav-n button::before {{ background:{ACCENT};
    -webkit-mask-image:{ICON_HEART_ON}; mask-image:{ICON_HEART_ON}; }}
.st-key-actions .st-key-hd-search button::before {{ -webkit-mask-image:{ICON_SEARCH}; mask-image:{ICON_SEARCH}; }}
.st-key-actions .st-key-hd-post button::before {{ -webkit-mask-image:{ICON_POST}; mask-image:{ICON_POST}; }}
.st-key-actions .stButton button:hover::before {{ background:{ACCENT}; }}
.st-key-actions .st-key-hd-fav-n .stButton button p {{ top:2px; right:0; width:auto; height:16px; min-width:16px;
    padding:0 4px; clip:auto; overflow:visible; background:{ACCENT}; color:white; border-radius:8px;
    font-size:.65rem; font-weight:700; line-height:16px; text-align:center; box-shadow:0 0 0 2px {SOFT}; }}

/* メニュー：開くと左から出てきて、ほかの画面は暗くなる */
.st-key-backdrop {{ position:fixed; inset:0; z-index:1000001; width:auto !important; height:auto !important;
    background:rgba(20,28,23,.55); animation:menuFade {MENU_SLIDE * 0.8:.2f}s ease both; }}
.st-key-backdrop .stButton, .st-key-backdrop .stButton > button {{ width:100%; height:100%; }}
.st-key-backdrop .stButton > button {{ border:none; border-radius:0; opacity:0; cursor:pointer; }}
.st-key-drawer {{ position:fixed; top:0; left:0; bottom:0; z-index:1000002; width:min(380px,88vw) !important;
    height:auto !important; background:white; padding:.45rem 1.4rem 2rem; gap:0 !important; align-items:stretch !important; overflow-y:auto;
    box-shadow:8px 0 32px rgba(0,0,0,.22);
    animation:menuDrawer {MENU_SLIDE}s cubic-bezier(.22,.8,.24,1) both; }}
.st-key-drawer > .stElementContainer {{ width:auto !important; animation:menuItem .7s ease both; }}
{MENU_DELAYS}
/* 文字は全て大文字。字と字の間をゆったり空ける */
.st-key-drawer .stButton > button, .st-key-drawer .stButton > button p {{
    font-size:{MENU_FONT}rem; font-weight:600; line-height:1.3; letter-spacing:.15em; text-transform:uppercase; }}
.st-key-drawer .stButton > button {{ width:100%; border:none; border-radius:0; background:transparent;
    color:{INK}; padding:.6rem 0; min-height:0; transition:color .2s, padding-left .2s; }}
.st-key-drawer .stButton > button, .st-key-drawer .stButton > button * {{
    text-align:left !important; justify-content:flex-start !important; }}
.st-key-drawer .stButton > button > div {{ width:100%; }}
.st-key-drawer .stButton > button p {{ margin:0; }}
.st-key-drawer .stButton > button:hover, .st-key-drawer .stButton > button:focus:not(:active) {{
    background:transparent; color:{ACCENT}; padding-left:.35rem; }}
.st-key-drawer .st-key-menu-close .stButton > button {{ width:44px; padding:0; border-radius:50%; }}
.st-key-drawer .st-key-menu-close .stButton > button:hover {{ background:{TINT}; padding:0; }}
[class*="st-key-menu-sub-"] .stButton > button, [class*="st-key-menu-sub-"] .stButton > button p {{
    font-size:{MENU_FONT * 0.88:.2f}rem; font-weight:500; letter-spacing:.14em; }}
[class*="st-key-menu-sub-"] .stButton > button {{ padding:.45rem 0 .45rem 1rem; }}
[class*="st-key-menu-sub-"] .stButton > button:hover {{ padding-left:1.3rem; }}
.mgroup {{ display:flex; align-items:center; gap:.8rem; color:{MUTED}; font-family:{SERIF}; font-size:.95rem;
    letter-spacing:.24em; text-transform:uppercase; margin:1.5rem 0 .5rem; }}
.mgroup::before, .mgroup::after {{ content:""; flex:1; height:1px; background:{LINE}; }}
.mgroup:empty {{ margin:.8rem 0 .1rem; }}
.mgroup:empty::after {{ display:none; }}
@keyframes menuFade {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
@keyframes menuDrawer {{ from {{ transform:translateX(-100%); }} to {{ transform:none; }} }}
@keyframes menuItem {{ from {{ opacity:0; transform:translateX(-22px); }} to {{ opacity:1; transform:none; }} }}
@media (prefers-reduced-motion: reduce) {{
    .st-key-backdrop, .st-key-drawer, .st-key-drawer > .stElementContainer {{ animation:none !important; }}
    .ph img {{ transition:none; }} }}
</style>""", unsafe_allow_html=True)

# ---------- データ（まずはサンプル。spots.csv ができたらそちらが本体になります） ----------
AREAS = {"山口市": (34.186, 131.471)}  # 増やすときは「"宇部市": (緯度, 経度),」のように足す
CATS = ["カフェ", "自然", "グルメ", "海", "温泉"]
ICONS = {"カフェ": "☕", "自然": "🌿", "グルメ": "🍽️", "海": "🌊", "温泉": "♨️"}
CAT_EN = {"カフェ": "Cafe", "自然": "Nature", "グルメ": "Gourmet", "海": "Sea", "温泉": "Onsen"}  # メニューの英語名
AREA_EN = {"山口市": "Yamaguchi City"}  # 場所を増やしたら、ここに英語名も足す（なくても日本語のまま出ます）
RANK_N = 10                       # ホームのランキングに出す件数（横にスライドします）
RANK_TABS = ["すべて", *CATS]      # ランキングの切り替え（すべて ＋ カテゴリごと）
AGES = ["回答しない", "10代", "20代", "30代", "40代", "50代以上"]
GENDERS = ["回答しない", "女性", "男性", "その他"]
MAX_PHOTOS = 5
MIN_CODE = 6   # 合言葉の最低文字数
MAX_FAILS = 5  # 合言葉を間違えられる回数（1回の利用中）
SAMPLE = [
    ("サンプルカフェA", "山口市", "カフェ", 800, 4.9),
    ("サンプルの森B", "山口市", "自然", 500, 4.8),
    ("サンプル食堂C", "山口市", "グルメ", 1200, 4.7),
    ("サンプル温泉D", "山口市", "温泉", 700, 4.6),
    ("サンプルカフェE", "山口市", "カフェ", 900, 4.4),
    ("サンプル公園F", "山口市", "自然", 0, 4.3),
    ("サンプルの海辺G", "山口市", "海", 0, 4.2),
]


def make_spot(i, name, area, cat, budget, score, review="ここにクチコミが入ります（サンプル）。",
              address="", photo="", age="", gender="", edit_hash=""):
    lat, lon = AREAS[area]
    return dict(id=i, name=name, area=area, category=cat, budget=budget, score=score,
                review=review, address=address, photo=photo, age=age, gender=gender,
                edit_hash=edit_hash, lat=lat + random.uniform(-.02, .02), lon=lon + random.uniform(-.02, .02))


# ---------- CSVと写真の保存（app.py と同じフォルダの spots.csv / photos/） ----------
CSV = Path(__file__).parent / "spots.csv"
PHOTO_DIR = Path(__file__).parent / "photos"
COLS = ["id", "name", "area", "category", "budget", "score", "review",
        "address", "photo", "age", "gender", "lat", "lon", "edit_hash"]


def save_spots(spots):
    pd.DataFrame(spots, columns=COLS).to_csv(CSV, index=False, encoding="utf-8-sig")


def load_spots():
    if not CSV.exists():  # 初回だけサンプルからCSVを作る
        save_spots([make_spot(i, *row) for i, row in enumerate(SAMPLE)])
    df = pd.read_csv(CSV, encoding="utf-8-sig")
    for c in COLS:  # 古いCSVに無い列（住所・写真など）は空で補う
        if c not in df.columns:
            df[c] = ""
    return df[COLS].fillna("").to_dict("records")


# 「何人が保存したか」の数だけを saves.json に残す。誰が保存したかは記録しない（匿名のまま）
SAVES = Path(__file__).parent / "saves.json"


def load_saves():
    try:
        data = json.loads(SAVES.read_text(encoding="utf-8"))
        return {str(k): int(v) for k, v in data.items() if int(v) > 0}
    except (OSError, ValueError, AttributeError):  # まだ無い・壊れているときは、0件として扱う
        return {}


def write_saves(counts):
    tmp = SAVES.with_suffix(".tmp")  # 書き込み途中で止まっても壊れないよう、いったん別ファイルに書く
    tmp.write_text(json.dumps(counts, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, SAVES)


def change_saves(spot_id, delta):
    counts = load_saves()
    n = max(0, counts.get(str(spot_id), 0) + delta)
    if n:
        counts[str(spot_id)] = n
    else:
        counts.pop(str(spot_id), None)
    write_saves(counts)


def clear_saves(spot_id):  # 投稿を消したとき、その数も消す（あとで同じ番号の投稿に引き継がれないように）
    counts = load_saves()
    if counts.pop(str(spot_id), None) is not None:
        write_saves(counts)


def save_photo(file):
    # 向きを直し、4:3に切り抜いて縮小。撮影場所などのEXIF情報は保存しない
    img = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
    img = ImageOps.fit(img, (800, 600))
    name = f"{uuid.uuid4().hex[:12]}.jpg"
    PHOTO_DIR.mkdir(exist_ok=True)
    img.save(PHOTO_DIR / name, "JPEG", quality=80)
    return name


@st.cache_data
def photo_b64(name):
    f = PHOTO_DIR / name
    return base64.b64encode(f.read_bytes()).decode() if f.exists() else ""


def photo_html(names, overlay=""):
    # photo列には「a.jpg,b.jpg」のように、写真のファイル名がカンマ区切りで入っています
    # overlay：写真の上に重ねるもの（順位のリボンなど）
    files = [n.strip() for n in str(names).split(",") if n.strip()]
    first = next((b for b in map(photo_b64, files) if b), "")
    if not first:
        return f'<div class="ph none">{overlay}NO PHOTO</div>'
    count = f'<span class="pcount">{len(files)} PHOTOS</span>' if len(files) > 1 else ""
    return f'<div class="ph">{overlay}<img src="data:image/jpeg;base64,{first}" alt="">{count}</div>'


# ---------- 場所の名前から、住所と位置を探す ----------
# 住所の作り方
#  ① 場所は OpenStreetMap と 国土地理院 の両方から探す（カフェなどは OSM、役所や名所は国土地理院が得意）
#  ② 住所の「市＋町名」は、国土地理院の公式データ（緯度・経度から調べる）で作る。道路名などは入れない
#  ③ 番地は自動では分からないので、住所のあとに書き足してもらう。足すとピンも番地の位置に合う
UA = {"User-Agent": "yamaguchi-kuchikomi-cho/0.1"}
GSI_SEARCH = "https://msearch.gsi.go.jp/address-search/AddressSearch"
GSI_REVERSE = "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress"
MUNI = {  # 国土地理院が返す市町村コード → 市町村名（山口県）
    "35201": "下関市", "35202": "宇部市", "35203": "山口市", "35204": "萩市", "35206": "防府市",
    "35207": "下松市", "35208": "岩国市", "35210": "光市", "35211": "長門市", "35212": "柳井市",
    "35213": "美祢市", "35215": "周南市", "35216": "山陽小野田市", "35305": "周防大島町", "35321": "和木町",
    "35341": "上関町", "35343": "田布施町", "35344": "平生町", "35502": "阿武町"}
KINDS = {  # OpenStreetMap の種類 → 候補に出す日本語
    "cafe": "カフェ", "restaurant": "レストラン", "fast_food": "軽食", "bar": "バー", "pub": "バー",
    "ice_cream": "アイス", "bakery": "パン屋", "place_of_worship": "寺社・教会", "station": "駅",
    "university": "大学", "school": "学校", "townhall": "役所", "museum": "博物館", "library": "図書館",
    "park": "公園", "garden": "庭園", "public_bath": "温浴施設", "onsen": "温泉", "hot_spring": "温泉",
    "attraction": "観光地", "viewpoint": "展望", "beach": "ビーチ", "hotel": "宿泊", "guest_house": "宿泊",
    "castle": "城", "monument": "記念碑", "memorial": "記念碑", "theatre": "劇場", "zoo": "動物園"}


def meters(lat1, lon1, lat2, lon2):
    """2つの場所のあいだの距離（メートル）"""
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742000 * math.asin(math.sqrt(a))


@st.cache_data(ttl=86400, show_spinner=False)
def gsi_town(lat, lon):
    """緯度・経度から、国土地理院の公式の「市町村」と「町丁目」を調べる。例：('山口市', '湯田温泉二丁目')"""
    r = requests.get(GSI_REVERSE, params={"lat": round(lat, 6), "lon": round(lon, 6)}, headers=UA, timeout=8)
    r.raise_for_status()
    res = r.json().get("results") or {}
    return MUNI.get(str(res.get("muniCd", "")), ""), str(res.get("lv01Nm", ""))


def town_address(city, town, postcode=""):
    zip_ = f"〒{postcode} " if re.fullmatch(r"\d{3}-\d{4}", postcode or "") else ""  # 郵便番号は形が正しいときだけ
    return f"{zip_}山口県{city}{town}"


def kind_of(it):
    if it.get("category") == "historic":
        return "史跡"
    return KINDS.get(it.get("type", ""), "")


def clean_name(nm):
    """「山口県庁 (Yamaguchi Prefecture Hall)」→「山口県庁」"""
    return re.sub(r"\s*[(（][A-Za-z0-9 .,'&-]+[)）]\s*$", "", nm).strip() or nm


@st.cache_data(ttl=3600, show_spinner="場所を探しています…")
def geocode(name):
    found = []
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": name, "format": "jsonv2", "addressdetails": 1, "limit": 10,
                "countrycodes": "jp", "accept-language": "ja",
                "viewbox": "131.2,34.6,131.85,33.95", "bounded": 1},  # 山口市まわりに限定
        headers=UA, timeout=8)
    r.raise_for_status()
    for it in r.json():
        if it.get("category") == "boundary" or it.get("type") == "administrative":
            continue  # 市や町の境界線は「場所」ではない
        city = next((a for a in AREAS if a in it.get("display_name", "")), "")
        if not city:
            continue
        ad = it.get("address", {})
        found.append(dict(name=clean_name(it.get("name") or it["display_name"].split(",")[0]), kind=kind_of(it),
                          lat=float(it["lat"]), lon=float(it["lon"]), zip=ad.get("postcode", ""),
                          city=city, town=ad.get("quarter") or ad.get("suburb") or ""))
    try:  # 国土地理院の名前検索（役所・名所・施設に強い）。つながらなくても OSM の結果だけで続ける
        g = requests.get(GSI_SEARCH, params={"q": name}, headers=UA, timeout=8)
        g.raise_for_status()
        for it in g.json()[:8]:
            title = it.get("properties", {}).get("title", "")
            lon, lat = it["geometry"]["coordinates"]
            if not title or title == "山口県" or re.match(r"山口県[^市町村郡]*[市町村郡]", title):
                continue  # 「山口県山口市…」のような住所そのものは、場所の名前ではない
            if not (33.95 <= lat <= 34.6 and 131.2 <= lon <= 131.85):
                continue
            if any(meters(lat, lon, f["lat"], f["lon"]) < 150 for f in found):
                continue  # OSM にも出ている同じ場所
            found.append(dict(name=title, kind="", lat=float(lat), lon=float(lon), zip="",
                              city=list(AREAS)[0], town=""))
    except Exception:
        pass
    result = []
    for f in found[:8]:
        city, town = f["city"], f["town"]
        try:  # 町名は、国土地理院の公式データで確かめる（OSM の町名や道路名より正確）
            city, town = gsi_town(f["lat"], f["lon"])
        except Exception:
            pass
        if city not in AREAS:
            continue
        addr = town_address(city, town, f["zip"])
        result.append(dict(name=f["name"], address=addr, lat=f["lat"], lon=f["lon"],
                           label=f"{f['name']}（{f['kind'] + '・' if f['kind'] else ''}{addr}）"))
    return result[:6]


@st.cache_data(ttl=3600, show_spinner="位置を探しています…")
def geocode_gsi(address):
    """住所から位置を探す（国土地理院・キー不要）。山口県内の結果だけを使う。
    番地まで特定できたときは exact=True、町名までしか分からないときは exact=False"""
    a = unicodedata.normalize("NFKC", address)
    a = re.sub(r"[‐‑–—―−]", "-", a)
    a = re.sub(r"〒?\s*\d{3}-\d{4}", "", a).replace("日本、", "").strip()
    toks = a.split()  # 建物名などが後ろに付いていたら捨てる。ただし「滝町 1-1」のように番地が離れていたらつなぐ
    a = toks[0] if toks else ""
    for t in toks[1:]:
        if re.match(r"\d", t) and not re.search(r"\d$", a):
            a += t
    if not a:
        return None
    if not a.startswith("山口県"):
        a = "山口県" + a
    h = re.sub(r"(\d)丁目\s*(\d)", r"\1-\2", a)  # 「2丁目6-8」→「2-6-8」の書き方も試す
    h = re.sub(r"(\d)番地?\s*(\d)", r"\1-\2", h)
    h = re.sub(r"(\d)号$", r"\1", h)
    tries = []
    for q in (a, h, re.sub(r"[\d丁目番地号-]+$", "", a)):  # 最後は番地を削って、町の位置
        if q and q not in tries:
            tries.append(q)
    best = None
    for q in tries:
        r = requests.get(GSI_SEARCH, params={"q": q}, headers=UA, timeout=8)
        r.raise_for_status()
        for it in r.json():
            title = it.get("properties", {}).get("title", "")
            if title.startswith("山口県"):
                lon, lat = it["geometry"]["coordinates"]
                hit = dict(lat=float(lat), lon=float(lon), title=title,
                           exact=bool(re.search(r"[0-9０-９]", title)))  # 数字（番・号）が付いていれば番地まで
                if hit["exact"]:
                    return hit
                best = best or hit  # 町名までの結果はとっておき、番地まで出るほかの書き方を先に試す
                break
    return best


COORD = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,，\s]\s*(-?\d+(?:\.\d+)?)\s*$")


def relocate(spot, text):
    """住所、または「緯度, 経度」からピンを置き直す。(成功したか, メッセージ) を返す"""
    t = unicodedata.normalize("NFKC", text).strip()
    m = COORD.match(t)
    addr = None
    if m:
        lat, lon = float(m[1]), float(m[2])
        note = "緯度・経度でピンを置き直しました。"
    else:
        try:
            hit = geocode_gsi(t)
        except Exception:
            return False, "位置の検索ができませんでした。ネットの接続を確認してください。"
        if not hit:
            return False, "この住所からは場所が見つかりませんでした。「緯度, 経度」で入れてみてください。"
        lat, lon = hit["lat"], hit["lon"]
        if hit["exact"]:
            note = f"「{hit['title']}」の位置にピンを置き直しました。"
        else:
            note = f"「{hit['title']}」あたりにピンを置き直しました（番地までは特定できませんでした）。"
    if not (33.5 <= lat <= 34.9 and 130.7 <= lon <= 132.2):
        return False, "山口県の外か、緯度と経度が逆になっているようです。もう一度確かめてください。"
    if m:  # 緯度・経度で動かしたときは、住所もそこの町名に合わせる
        try:
            city, town = gsi_town(lat, lon)
            if city and town:
                addr = town_address(city, town)
                note += f"住所も「{addr}」に直しました（番地は、必要なら編集で書き足してください）。"
        except Exception:
            pass
    spot.update(lat=lat, lon=lon, address=addr or (spot["address"] if m else text.strip()))
    save_spots(S.spots)
    return True, note


def hash_code(code, salt=None):
    # 合言葉そのものは保存せず、投稿ごとのランダムな値(salt)を混ぜた「ハッシュ」だけを保存する
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", code.encode(), bytes.fromhex(salt), 10_000).hex()
    return f"{salt}${h}"


def code_ok(code, stored):
    stored = str(stored)
    if "$" not in stored or not code:
        return False
    return secrets.compare_digest(hash_code(code, stored.split("$", 1)[0]), stored)


S = st.session_state
if "spots" not in S:
    S.spots = load_spots()
S.setdefault("favs", set())
for k, v in dict(page="home", area="すべて", cat="すべて", sort="score", q="", post_n=0, flash="",
                  detail_id=None, back="home", saved={}, unlocked=set(), fails=0, menu=False,
                  rank_tab="すべて").items():
    S.setdefault(k, v)
SAVE_COUNTS = load_saves()  # 画面を開くたびに読み直す（ほかの人の保存も反映される）


def saves_of(spot):
    return SAVE_COUNTS.get(str(spot["id"]), 0)


def score_of(spot):  # 星の評価（1〜5）。数字になっていないときは 0 として扱う
    try:
        return max(0.0, min(5.0, float(spot["score"])))
    except (TypeError, ValueError):
        return 0.0


def rank_key(spot):  # 評価が高い順。同じ評価なら保存された数が多い順、それも同じなら新しい順
    return (score_of(spot), saves_of(spot), spot["id"])


def ranking(spots, cat="すべて", n=RANK_N):
    rows = [s for s in spots if cat in ("すべて", s["category"])]
    return sorted(rows, key=rank_key, reverse=True)[:n]


# ---------- 動き ----------
def go(page, area="すべて", cat="すべて", sort="score"):
    S.update(page=page, area=area, cat=cat, sort=sort, menu=False,  # ページを移るときはメニューも閉じる
             scroll_top=True)  # 前のページの下のほうを見ていても、新しいページは一番上から見せる


def toggle_menu():
    S.menu = not S.menu


def close_menu():
    S.menu = False


def open_detail(spot_id):
    if S.page != "detail":  # もどるときのために、今のページと絞り込みを覚えておく
        S.back = S.page
        S.saved = dict(area=S.area, cat=S.cat, sort=S.sort)
    S.update(detail_id=spot_id, page="detail", scroll_top=True)


def back():
    S.update(page=S.back, scroll_top=True, **S.saved)


def try_unlock(spot, code):
    """合言葉が合えば編集できる状態にして ""、だめならメッセージを返す"""
    if S.fails >= MAX_FAILS:
        return "合言葉を何度も間違えました。いったんブラウザを閉じて、もう一度開いてください。"
    if code_ok(code, spot["edit_hash"]):
        S.unlocked.add(spot["id"])
        return ""
    S.fails += 1
    return "合言葉が違います。"


def toggle_fav(spot_id):
    if spot_id in S.favs:
        S.favs.discard(spot_id)
        change_saves(spot_id, -1)
    else:
        S.favs.add(spot_id)
        change_saves(spot_id, 1)


def filtered():
    rows = [s for s in S.spots
            if S.area in ("すべて", s["area"]) and S.cat in ("すべて", s["category"])]
    return sorted(rows, key=rank_key if S.sort == "score" else (lambda s: s["id"]), reverse=True)


def esc(text):
    return html.escape(str(text)).replace("\n", "<br>")


def maps_url(name, address=""):
    # Googleマップをキーワード検索で開くだけのリンク（キーも料金も不要）
    place = re.sub(r"〒[\d-]+\s*", "", address)
    return "https://www.google.com/maps/search/?api=1&query=" + quote(f"{name} {place}".strip() if place else f"{name} 山口市")


def card_html(s, badge=""):
    addr = f'<div class="meta">📍 {esc(s["address"])}</div>' if s["address"] else ""
    link = (f'<div class="meta"><a href="{html.escape(maps_url(str(s["name"]), str(s["address"])))}" '
            'target="_blank" rel="noopener" class="maplink">🗺 Googleマップで開く</a></div>')
    who = " ".join(x for x in (s["age"], s["gender"]) if x)
    who = f'<div class="meta">投稿者：{esc(who)}</div>' if who else ""
    budget = int(s["budget"] or 0)
    ribbon = ""  # ランキングは、写真の左上に「No.1」のリボン
    new = ""     # NEW は、名前の上の札
    if badge.startswith("No."):
        num = badge[3:]
        ribbon = f'<div class="ribbon{" two" if len(num) > 1 else ""}"><i>No.</i><b>{esc(num)}</b></div>'
    elif badge:
        new = f'<span class="tag new">{esc(badge)}</span>'
    return ('<div class="card">' + photo_html(str(s["photo"]), ribbon)
            + f'<div class="tags">{new}<span class="tag">{esc(s["area"])}</span><span class="tag">{esc(s["category"])}</span></div>'
            f'<div class="nm">{esc(s["name"])}</div>'
            f'<div class="price">¥{budget:,}<span class="saves" title="保存された数">♥ {saves_of(s)}</span></div>'
            f'<div class="rv">{esc(s["review"])}</div>{addr}{link}{who}</div>')


def card_box(key):
    try:
        return st.container(key=key)
    except TypeError:  # 古いStreamlitではカード全体は押せず、「詳細を見る」ボタンが出る
        return st.container()


def one_card(s, key, mark=""):
    with card_box(f"cardwrap-{key}-{s['id']}"):
        st.markdown(card_html(s, mark), unsafe_allow_html=True)
        # 見えないボタンをカードの上に重ねて、カード全体を押せるようにしている
        st.button("詳細を見る", key=f"cd-{key}-{s['id']}", on_click=open_detail, args=(s["id"],))
        # 写真の右上のハート。保存すると塗りつぶされる（見た目は keyの名前 cs / cson で切り替え）
        saved = s["id"] in S.favs
        st.button("保存済み" if saved else "保存", key=f"{'cson' if saved else 'cs'}-{key}-{s['id']}",
                  on_click=toggle_fav, args=(s["id"],))


def cards(spots, key, per_row=5, badge=""):
    if not spots:
        st.info("該当するスポットがまだありません。")
    for r in range(0, len(spots), per_row):
        for j, (col, s) in enumerate(zip(st.columns(per_row), spots[r:r + per_row])):
            with col:
                one_card(s, key, f"No.{r + j + 1}" if badge == "rank" else badge)  # ランキングは「No.1」、Newは「NEW」


def slide_cards(spots, key):
    """ランキングを横一列に並べる。横にスワイプ（パソコンは下のバーをドラッグ、Shift＋ホイール）で次の順位が見える"""
    if not spots:
        st.caption("このカテゴリのクチコミは、まだありません。")
        return
    with card_box(f"slide-{key}"):
        for j, (col, s) in enumerate(zip(st.columns(len(spots)), spots)):
            with col:
                one_card(s, key, f"No.{j + 1}")


def set_rank_tab(tab):
    S.rank_tab = tab


def show_map(spots, key):
    df = pd.DataFrame(spots)
    if df.empty:
        return
    df = df[["id", "name", "lat", "lon"]].copy()
    df[["lat", "lon"]] = df[["lat", "lon"]].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    if df.empty:
        return
    layer = pdk.Layer(
        "ScatterplotLayer", id="spots", data=df, get_position="[lon, lat]",
        get_fill_color=PIN, get_radius=60, radius_min_pixels=9,
        stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=2,
        pickable=True, auto_highlight=True)
    deck = pdk.Deck(
        layers=[layer], map_style=None, tooltip={"text": "{name}"},
        initial_view_state=pdk.ViewState(latitude=df["lat"].mean(), longitude=df["lon"].mean(), zoom=11.5))
    try:
        ev = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key=key, height=420)
    except TypeError:  # 古いStreamlitでは、ピンを押せない地図になる
        st.pydeck_chart(deck)
        return
    try:
        picked = ev.selection.objects.get("spots", [])
    except (AttributeError, KeyError):
        picked = []
    if picked:  # ピンが押されたら、そのスポットの詳細へ
        open_detail(int(picked[0]["id"]))
        st.rerun()


def idx_of(options, value):
    return options.index(value) if value in options else 0


def star_input(label, key):
    """星の評価（1〜5）を選ぶ。まだ選んでいないときは None を返す"""
    st.caption(label)
    if hasattr(st, "feedback"):
        try:
            v = st.feedback("stars", key=key)  # 星を押すと 0〜4 が返る（押すまでは None）
            return None if v is None else int(v) + 1
        except Exception:  # フォームの中で使えない古い版など
            pass
    return st.radio(label, [1, 2, 3, 4, 5], index=None, horizontal=True, key=f"{key}-radio",
                    format_func=lambda n: "★" * n, label_visibility="collapsed")


def owner_panel(spot):
    sid = spot["id"]
    if not spot["edit_hash"]:  # 合言葉のない古い投稿：最初に決めた人が持ち主になる
        with st.expander("✏️ 投稿者の方へ（編集・削除）"):
            st.caption("この投稿には、まだ合言葉がありません。投稿した本人なら、合言葉を決めると編集・削除できます。")
            code = st.text_input(f"新しい合言葉（{MIN_CODE}文字以上）", type="password", key=f"claim-{sid}")
            if st.button("この投稿の合言葉を決める", key=f"claimbtn-{sid}"):
                if len(code) < MIN_CODE:
                    st.warning(f"合言葉は{MIN_CODE}文字以上にしてください。")
                else:
                    spot["edit_hash"] = hash_code(code)
                    save_spots(S.spots)
                    S.unlocked.add(sid)
                    S.flash = "合言葉を決めました。これで編集・削除できます。"
                    st.rerun()
        return
    if sid not in S.unlocked:
        with st.expander("✏️ 投稿者の方はこちら（編集・削除）"):
            code = st.text_input("合言葉", type="password", key=f"unlock-{sid}")
            if st.button("編集できるようにする", key=f"unlockbtn-{sid}"):
                msg = try_unlock(spot, code)
                if msg:
                    st.warning(msg)
                else:
                    st.rerun()
        return

    files = [f for f in (n.strip() for n in str(spot["photo"]).split(",")) if f and (PHOTO_DIR / f).exists()]
    with st.expander("✏️ この投稿を編集する", expanded=True):
        with st.form(f"edit-{sid}"):
            name = st.text_input("スポット名", value=str(spot["name"]), key=f"e-name-{sid}")
            address = st.text_input("住所", value=str(spot["address"]), key=f"e-addr-{sid}")
            cat = st.selectbox("スポット", CATS, index=idx_of(CATS, spot["category"]), key=f"e-cat-{sid}")
            budget = st.number_input("かかった予算（円）", 0, 100000, min(int(spot["budget"] or 0), 100000), 100,
                                     key=f"e-budget-{sid}")
            review = st.text_area("クチコミ", value=str(spot["review"]), key=f"e-review-{sid}")
            new_stars = star_input(f"星の評価（今は {score_of(spot):.1f}。変えるときだけ星を押してください）", f"e-stars-{sid}")
            drop = []
            if files:
                st.caption("今の写真（消したい写真にチェック）")
                for f, col in zip(files, st.columns(len(files))):
                    col.image(str(PHOTO_DIR / f))
                    if col.checkbox("消す", key=f"e-drop-{sid}-{f}"):
                        drop.append(f)
            up = st.file_uploader(f"写真を足す（全部で{MAX_PHOTOS}枚まで）", type=["jpg", "jpeg", "png"],
                                  accept_multiple_files=True, key=f"e-up-{sid}")
            c1, c2 = st.columns(2)
            age = c1.selectbox("あなたの年代（任意）", AGES, index=idx_of(AGES, spot["age"] or "回答しない"),
                               key=f"e-age-{sid}")
            gender = c2.selectbox("性別（任意）", GENDERS, index=idx_of(GENDERS, spot["gender"] or "回答しない"),
                                  key=f"e-gender-{sid}")
            saved = st.form_submit_button("変更を保存する")
        if saved:
            keep = [f for f in files if f not in drop]
            if len(keep) + len(up) > MAX_PHOTOS:
                st.warning(f"写真は全部で{MAX_PHOTOS}枚までです。")
            elif not (name.strip() and review.strip()):
                st.warning("スポット名とクチコミは空にできません。")
            else:
                added = [save_photo(f) for f in up]
                for f in drop:
                    (PHOTO_DIR / f).unlink(missing_ok=True)
                moved = False
                if address.strip() and address.strip() != str(spot["address"]).strip():
                    try:  # 住所を直したときは、番地まで特定できれば、ピンも住所の位置に合わせる
                        hit = geocode_gsi(address)
                    except Exception:
                        hit = None
                    if hit and hit["exact"]:
                        spot.update(lat=hit["lat"], lon=hit["lon"])
                        moved = True
                spot.update(name=name.strip(), address=address.strip(), category=cat, budget=int(budget),
                            review=review, photo=",".join(keep + added),
                            age="" if age == "回答しない" else age,
                            gender="" if gender == "回答しない" else gender)
                if new_stars:
                    spot["score"] = float(new_stars)
                save_spots(S.spots)
                S.flash = "変更を保存しました。" + ("住所に合わせて、ピンの位置も直しました。" if moved else "")
                st.rerun()

    with st.expander("📍 ピンの位置を直す"):
        st.caption("住所、または「緯度, 経度」を入れてください。Googleマップで場所を右クリックすると、緯度・経度が出ます。")
        fix = st.text_input("住所 / 緯度, 経度", value=str(spot["address"]), key=f"fix-{sid}")
        if st.button("この場所にピンを置く", key=f"fixbtn-{sid}"):
            ok, msg = relocate(spot, fix)
            if ok:
                S.flash = msg
                st.rerun()
            else:
                st.warning(msg)
        st.caption("位置の検索：国土地理院")

    with st.expander("🗑 この投稿を削除する"):
        sure = st.checkbox("本当に削除する（元に戻せません）", key=f"delchk-{sid}")
        if st.button("削除する", key=f"delbtn-{sid}", disabled=not sure):
            for f in files:
                (PHOTO_DIR / f).unlink(missing_ok=True)
            S.spots = [x for x in S.spots if x["id"] != sid]
            S.favs.discard(sid)
            clear_saves(sid)
            S.unlocked.discard(sid)
            save_spots(S.spots)
            S.flash = "投稿を削除しました。"
            S.update(page=S.back, scroll_top=True, **S.saved)
            st.rerun()


def hero():
    st.markdown('<div class="hero"><div class="hero-en">YAMAGUCHI KUCHIKOMI-CHO</div>'
                '<div class="hero-title">やまぐちクチコミ帖</div>'
                '<div class="hero-sub">山口の大学生が、ほんとうに行ってよかった場所だけ。</div>'
                f'<div class="hero-n">{len(S.spots)} REVIEWS</div></div>', unsafe_allow_html=True)


def section(en, ja):  # 英語の大きな見出し（明朝体）と、その下に小さく日本語
    st.markdown(f'<div class="sec"><div class="sec-en">{en.title()}</div><div class="sec-ja">{ja}</div></div>',
                unsafe_allow_html=True)


def title_en(en):  # 英語だけの見出し（Ranking・New のページ用）
    st.markdown(f'<div class="sec en"><div class="sec-en">{en.title()}</div></div>', unsafe_allow_html=True)


# ---------- メニュー（左上の三本線から開く。文字だけの英語メニュー） ----------
st.button("Open menu", key="hamburger", on_click=toggle_menu)  # 三本線
if S.menu:
    st.button("Close menu", key="backdrop", on_click=close_menu)  # 暗くなった背景。どこを押しても閉じる
    with card_box("drawer"):
        st.button("Close menu", key="menu-close", on_click=close_menu)  # ×
        if AREAS:
            st.markdown('<div class="mgroup">Area</div>', unsafe_allow_html=True)
            for a in AREAS:
                st.button(AREA_EN.get(a, a), key=f"menu-sub-{a}", on_click=go, args=("browse",), kwargs={"area": a})
        st.markdown('<div class="mgroup">Category</div>', unsafe_allow_html=True)
        for c in CATS:
            st.button(CAT_EN.get(c, c), key=f"menu-sub-{c}", on_click=go, args=("browse",), kwargs={"cat": c})
        st.markdown('<div class="mgroup"></div>', unsafe_allow_html=True)
        st.button("Ranking", key="menu-rank", on_click=go, args=("home",))  # ランキングはホームにある
        st.button("New", key="menu-new", on_click=go, args=("new",))
        st.button("My posts", key="menu-mine", on_click=go, args=("mine",))

# ---------- 上のバー ----------
with card_box("brand"):  # サイト名（押すとホームへ）
    st.button("やまぐちクチコミ帖", key="t-home", on_click=go, args=("home",))
with card_box("actions"):  # 右端に、お気に入り・検索・クチコミのマークを常に表示（マークだけ）
    n_fav = len(S.favs)  # 保存があるとハートが塗りつぶされ、数字が付く
    st.button(str(n_fav) if n_fav else "Favorites", key="hd-fav-n" if n_fav else "hd-fav",
              on_click=go, args=("favs",))
    st.button("Search", key="hd-search", on_click=go, args=("search",))
    st.button("Write a review", key="hd-post", on_click=go, args=("post",))

# ---------- ページ ----------
if S.flash:
    st.success(S.flash)
    S.flash = ""
    S.scroll_top = True  # お知らせは上に出るので、下のほうにいても上まで戻す
page = S.page

if page == "home":
    hero()
    show_map(S.spots, "map-home")
    # ランキング：左に見出し、右に「すべて／カテゴリ」の切り替え。その下に、横にスライドする10位まで
    with card_box("rankhead"):
        for col, t in zip(st.columns(len(RANK_TABS) + 1), [None, *RANK_TABS]):
            if t is None:
                col.markdown('<div class="sec-en">Ranking</div>', unsafe_allow_html=True)
            else:
                on = S.rank_tab == t
                col.button("All" if t == "すべて" else CAT_EN.get(t, t), key=f"rt-on-{t}" if on else f"rt-{t}",
                           on_click=set_rank_tab, args=(t,))
    slide_cards(ranking(S.spots, S.rank_tab), f"rk-{S.rank_tab}")
    # New：新しい順に数枚だけ見せて、「View more」で New のページ（全部）へ
    title_en("New")
    cards(sorted(S.spots, key=lambda s: s["id"], reverse=True)[:HOME_NEW_N], "new", per_row=HOME_NEW_N, badge="NEW")
    with card_box("new-more"):
        st.button("View more", key="new-more-btn", on_click=go, args=("new",))

elif page == "new":
    title_en("NEW")
    cards(sorted(S.spots, key=lambda s: s["id"], reverse=True), "newall")

elif page == "browse":
    section("EXPLORE", "さがす")
    c1, c2, c3 = st.columns([1, 3, 1.5])
    c1.selectbox("場所", ["すべて", *AREAS], key="area")
    c2.radio("スポット", ["すべて", *CATS], key="cat", horizontal=True)
    c3.radio("並び順", ["score", "new"], key="sort", horizontal=True,
             format_func={"score": "人気順", "new": "新着順"}.get)
    rows = filtered()
    show_map(rows, "map-browse")
    cards(rows, "browse")

elif page == "search":
    section("SEARCH", "検索")
    st.text_input("スポット名・住所・キーワード", key="q")
    q = S.q.strip()
    rows = [s for s in S.spots
            if q and q in f"{s['name']}{s['area']}{s['address']}{s['category']}{s['review']}"]
    if q:
        cards(rows, "search")
    else:
        st.caption("キーワードを入力すると結果が出ます。")

elif page == "favs":
    section("FAVORITES", "お気に入り")
    rows = [s for s in S.spots if s["id"] in S.favs]
    if rows:
        show_map(rows, "map-favs")
        cards(rows, "fav")
    else:
        st.info("まだ保存したスポットがありません。気になる場所の「♡ 保存」を押してみてください。")

elif page == "detail":
    spot = next((x for x in S.spots if x["id"] == S.detail_id), None)
    st.button("← もどる", key="d-back", on_click=back)
    if spot is None:
        st.info("スポットが見つかりませんでした。")
    else:
        st.subheader(spot["name"])
        left, right = st.columns([3, 2])
        with left:
            shown = [f for f in (PHOTO_DIR / n.strip() for n in str(spot["photo"]).split(",") if n.strip())
                     if f.exists()]
            for i, f in enumerate(shown, 1):
                st.image(str(f), caption=f"{i} / {len(shown)}")
            if not shown:
                st.info("写真はまだありません。")
        with right:
            who = " ".join(x for x in (spot["age"], spot["gender"]) if x)
            link = html.escape(maps_url(str(spot["name"]), str(spot["address"])))
            st.markdown(
                '<div>'
                f'<span class="tag">{esc(spot["area"])}</span><span class="tag">{esc(spot["category"])}</span>'
                + (f'<div class="meta">📍 {esc(spot["address"])}</div>' if spot["address"] else "")
                + f'<div class="meta"><a href="{link}" target="_blank" rel="noopener" class="maplink">'
                  '🗺 Googleマップで開く</a></div>'
                f'<p>予算 {int(spot["budget"] or 0):,}円'
                f'　<span class="saves">♥ {saves_of(spot)}人が保存</span></p>'
                f'<div>{esc(spot["review"])}</div>'
                + (f'<div class="meta">投稿者：{esc(who)}</div>' if who else "")
                + '</div>', unsafe_allow_html=True)
            saved = spot["id"] in S.favs
            st.button("♥ 保存済み" if saved else "♡ 保存", key="d-fav", on_click=toggle_fav, args=(spot["id"],))
            pt = pd.DataFrame([{"lat": spot["lat"], "lon": spot["lon"]}]).apply(pd.to_numeric, errors="coerce").dropna()
            if not pt.empty:
                try:
                    st.map(pt, color=ACCENT)
                except TypeError:  # 古いStreamlitでは色の指定ができない
                    st.map(pt)
        st.divider()
        owner_panel(spot)

elif page == "mine":
    section("MY POSTS", "自分の投稿")
    st.caption("投稿するときに決めた合言葉を入れて Enter を押してください。名前やログインは使いません。")
    code = st.text_input("合言葉", type="password", key="mine_code")
    if code:
        if S.fails >= MAX_FAILS:
            st.warning("合言葉を何度も間違えました。いったんブラウザを閉じて、もう一度開いてください。")
        else:
            mine = [x for x in S.spots if code_ok(code, x["edit_hash"])]
            if mine:
                S.unlocked.update(x["id"] for x in mine)
                st.success(f"{len(mine)}件の投稿が見つかりました。カードを押すと、編集・削除できます。")
                cards(mine, "mine")
            else:
                S.fails += 1
                st.warning("この合言葉の投稿は見つかりませんでした。")

elif page == "post":
    section("WRITE A REVIEW", "クチコミをする")
    n = S.post_n
    name = st.text_input("スポット名（入力して Enter を押すと、住所が自動で入ります）", key=f"p_name{n}").strip()
    cands, idx = [], 0
    if name:
        try:
            cands = geocode(name)
            if not cands:
                st.info("自動では見つかりませんでした。下の「Googleマップで探す」で住所を調べて、住所欄に貼り付けてください。")
        except Exception:
            st.warning("住所の自動検索ができませんでした。ネットの接続を確認するか、住所を手で入力してください。")
    if cands:
        idx = st.selectbox("この場所ですか？", range(len(cands)), key=f"p_idx{n}-{name}",
                           format_func=lambda i: cands[i]["label"])
    if name:
        st.markdown(f"[🗺 Googleマップで探す]({maps_url(name)})　別のタブで開きます。"
                    "住所をコピーして、下の住所欄に貼り付けてください。")
    pick = cands[idx] if cands else None
    with st.form(f"post{n}"):
        address = st.text_input("住所（市・町名までは自動で入ります。番地がわかるときは、うしろに足してください　例：1-1）",
                                value=pick["address"] if pick else "", key=f"p_addr{n}-{name}-{idx}")
        cat = st.selectbox("スポット", CATS, key=f"p_cat{n}")
        budget = st.number_input("かかった予算（円）", 0, 100000, 1000, 100, key=f"p_budget{n}")
        rating = star_input("星の評価（必ず選んでください）", f"p_stars{n}")
        review = st.text_area("クチコミ", key=f"p_review{n}")
        up = st.file_uploader(f"写真（{MAX_PHOTOS}枚まで・jpg/png）", type=["jpg", "jpeg", "png"],
                              accept_multiple_files=True, key=f"p_up{n}")
        st.caption("人の顔やナンバープレートが写っていない写真を選んでください。")
        c1, c2 = st.columns(2)
        age = c1.selectbox("あなたの年代（任意）", AGES, key=f"p_age{n}")
        gender = c2.selectbox("性別（任意）", GENDERS, key=f"p_gender{n}")
        st.caption("名前は聞きません。年代と性別だけが、投稿の下に表示されます。　住所の自動入力：© OpenStreetMap contributors　位置の検索：国土地理院")
        code = st.text_input(f"編集用の合言葉（{MIN_CODE}文字以上）", type="password", key=f"p_code{n}")
        code2 = st.text_input("もう一度入れてください", type="password", key=f"p_code2{n}")
        st.caption("あとで自分の投稿を見直したり、直したり消したりするときに使います。忘れると編集できないので、メモしてください。")
        sent = st.form_submit_button("投稿する")
    if sent:
        if len(up) > MAX_PHOTOS:
            st.warning(f"写真は{MAX_PHOTOS}枚までです。選び直してください。")
        elif not (name and review.strip()):
            st.warning("スポット名とクチコミを入力してください。")
        elif not rating:
            st.warning("星の評価を選んでください。")
        elif len(code) < MIN_CODE or code != code2:
            st.warning(f"合言葉は{MIN_CODE}文字以上で、同じものを2回入れてください。")
        else:
            photo = ",".join(save_photo(f) for f in up)
            new_id = max((s["id"] for s in S.spots), default=-1) + 1
            addr = address.strip()
            spot = make_spot(
                new_id, name, list(AREAS)[0], cat, int(budget), float(rating), review, addr, photo,
                "" if age == "回答しない" else age, "" if gender == "回答しない" else gender, hash_code(code))
            placed = bool(pick)
            warn = ""
            if pick:  # えらんだ場所のピンを置く
                spot.update(lat=pick["lat"], lon=pick["lon"])
            if addr and not (pick and addr == pick["address"]):
                # 住所を自分で書いた・直したときは、その住所の位置も調べる。番地まで特定できたら、そちらが正確
                try:
                    hit = geocode_gsi(addr)
                except Exception:
                    hit = None
                if hit and (hit["exact"] or not pick):
                    if pick and meters(pick["lat"], pick["lon"], hit["lat"], hit["lon"]) > 1500:
                        warn = "住所の位置と、えらんだ場所が1km以上離れています。詳細ページでピンの位置を確かめてください。"
                    spot.update(lat=hit["lat"], lon=hit["lon"])
                    placed = True
            S.spots.append(spot)
            save_spots(S.spots)
            S.unlocked.add(new_id)
            S.flash = ("投稿しました。Newに表示され、spots.csv にも保存されました。"
                       "あとから「自分の投稿」で、合言葉を入れると確認・編集できます。" + warn
                       + ("" if placed else "ピンの位置は山口市のあたりに仮置きしました。詳細ページの「ピンの位置を直す」で直せます。"))
            S.post_n += 1  # 入力欄を空にする
            st.rerun()

# ---------- 下のエリア ----------
st.markdown(
    '<div class="foot"><div class="foot-sec"><div class="foot-h">Info</div>'
    '山口県内の大学生が、実際に行ってよかった場所を紹介するサイトです。</div>'
    '<div class="copy">© 2026 やまぐちクチコミ帖</div></div>', unsafe_allow_html=True)

# ---------- ページを移ったときは、画面を一番上に戻す ----------
# Streamlit は、ページの中身が変わっても「下までスクロールした位置」を覚えたままなので、
# 下のほうが表示されてしまう。ここで一番上までスクロールし直す（見えない小さな部品を使う）
if S.get("scroll_top"):
    S.scroll_top = False
    S.scroll_n = S.get("scroll_n", 0) + 1  # 毎回ちがう中身にして、確実に動かす
    try:
        st.components.v1.html(
            "<script>const up=()=>{const d=window.parent.document;"
            "for(const s of ['[data-testid=\"stMain\"]','section.main','.main']){const e=d.querySelector(s);"
            "if(e)e.scrollTo(0,0);}window.parent.scrollTo(0,0);};"
            f"up();setTimeout(up,150);setTimeout(up,500);/*{S.scroll_n}*/</script>", height=0)
    except Exception:  # 使えない版では、何もしない（下のほうが表示されるだけ）
        pass