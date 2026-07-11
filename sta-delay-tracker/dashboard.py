"""STA Reliability Sign -- pick your bus, direction, and stop; read its reliability
like a destination sign. Styled after STA's real orange dot-matrix bus signs.

Reads precomputed, echo-corrected summaries from build_summary.py.
"""
import base64
import os
import sqlite3

import pandas as pd
import streamlit as st

SUMMARY_DB = "data/summary.sqlite"
TRACKER_DB = "data/tracker.sqlite"
BG_IMAGE = "assets/bus_bg.jpg"
MIN_N = 500

st.set_page_config(page_title="STA Bus Reliability", page_icon="\U0001F68C", layout="centered")


def _bg_css():
    if not os.path.exists(BG_IMAGE):
        return "background:#050505;"
    with open(BG_IMAGE, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return (
        "background:"
        "linear-gradient(rgba(5,5,5,.72), rgba(5,5,5,.90) 60%, rgba(5,5,5,.97)),"
        f"url('data:image/jpeg;base64,{b64}') center top/cover fixed no-repeat;"
    )


st.markdown(f"<style>.stApp{{ {_bg_css()} }}</style>", unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Silkscreen:wght@400;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root{ --led:#ff7519; --led-dim:#6b3910; --green:#39d07a; --red:#ff4438;
       --amber:#ffb000; --ink:#e8e6dc; --muted:#8a8578; --sign:#0a0806; }
html,body,[class*="css"]{ font-family:'IBM Plex Mono',monospace; }
.block-container{ max-width:720px; padding-top:1.6rem; }
[data-testid="stHeader"],#MainMenu,[data-testid="stToolbarActions"],
[data-testid="stAppDeployButton"],footer{ display:none!important; background:transparent!important; }

.kicker{ font-size:.66rem; letter-spacing:.34em; color:var(--muted); text-transform:uppercase;
  text-align:center; margin-bottom:12px; }

.sign{
  border-radius:12px; padding:32px 30px 28px; margin-bottom:6px;
  background-color:var(--sign);
  background-image:radial-gradient(circle at center, rgba(255,117,25,.07) 1.1px, transparent 1.4px);
  background-size:5px 5px;
  border:1px solid #241608; box-shadow:0 0 0 4px #0d0d0d, inset 0 0 60px rgba(0,0,0,.7);
}
.sign .rt{ font-family:'Silkscreen',monospace; font-weight:700; color:var(--led);
  font-size:4.2rem; line-height:.9; text-shadow:0 0 14px rgba(255,117,25,.5); letter-spacing:.02em; }
.sign .rt .lab{ font-size:.86rem; letter-spacing:.3em; color:var(--led-dim); display:block; margin-bottom:10px;
  text-shadow:none; font-weight:400; }
.sign .dest{ font-family:'Silkscreen',monospace; color:var(--led); font-size:1.1rem; letter-spacing:.06em;
  margin-top:14px; text-shadow:0 0 10px rgba(255,117,25,.35); line-height:1.5; }
.sign .at{ font-family:'IBM Plex Mono'; color:var(--muted); font-size:.72rem; letter-spacing:.12em;
  margin-top:6px; text-transform:uppercase; }
.sign .rule{ height:1px; background:linear-gradient(90deg,transparent,#42260c,transparent); margin:18px 0; }
.sign .verdict{ font-family:'Silkscreen',monospace; color:var(--led); font-size:1.55rem; letter-spacing:.03em;
  text-shadow:0 0 16px rgba(255,117,25,.55); line-height:1.25; }

.facts{ margin:18px 2px 6px; }
.fact{ display:flex; align-items:center; gap:12px; padding:9px 0; border-bottom:1px solid #16160f;
  font-size:1rem; color:var(--ink); letter-spacing:.02em; }
.dot{ width:11px; height:11px; border-radius:50%; flex:none; }
.fact b{ color:#fff; }
.sub{ text-align:center; color:var(--muted); font-size:.72rem; letter-spacing:.05em; margin:6px 0 2px; }

.h2{ font-family:'Silkscreen',monospace; color:var(--ink); font-size:1rem; letter-spacing:.12em;
  text-transform:uppercase; margin:30px 0 12px; text-align:center; }
.lr{ display:flex; align-items:center; gap:14px; padding:11px 14px; border:1px solid rgba(255,255,255,.08);
  border-radius:9px; margin-bottom:7px; background:rgba(10,10,8,.66); backdrop-filter:blur(6px);
  -webkit-backdrop-filter:blur(6px); }
.lr .badge{ width:40px; height:40px; border-radius:8px; background:var(--led); color:#0a0806;
  font-family:'Silkscreen',monospace; font-weight:700; font-size:1rem; display:flex; align-items:center;
  justify-content:center; flex:none; }
.lr .txt{ font-size:.92rem; color:var(--ink); }
.lr .txt b{ color:var(--red); }

label{ color:var(--led-dim)!important; font-family:'Silkscreen',monospace!important;
  font-size:.62rem!important; letter-spacing:.12em!important; }
div[data-baseweb="select"]>div{ background:#0d0d0b!important; border-color:#2a1a0a!important; }
.stRadio [role="radiogroup"]{ gap:8px; }
.foot{ color:var(--muted); font-size:.64rem; letter-spacing:.05em; text-align:center; margin-top:26px;
  border-top:1px solid #16160f; padding-top:14px; line-height:1.7; }
.foot a{ color:var(--muted); }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=120)
def load():
    conn = sqlite3.connect(SUMMARY_DB)
    overall = pd.read_sql("SELECT * FROM overall", conn).iloc[0]
    route_stats = pd.read_sql("SELECT * FROM route_stats", conn)
    route_dir = pd.read_sql("SELECT * FROM route_dir", conn)
    route_dir_hour = pd.read_sql("SELECT * FROM route_dir_hour", conn)
    stop_stats = pd.read_sql("SELECT * FROM stop_stats", conn)
    conn.close()
    for df in (route_stats, route_dir, route_dir_hour, stop_stats):
        df["route"] = df["route"].astype(str)
    route_stats = route_stats[route_stats["n"] >= MIN_N]
    return overall, route_stats, route_dir, route_dir_hour, stop_stats


def ampm(h):
    h = int(h)
    if h == 0:
        return "12 AM"
    if h < 12:
        return f"{h} AM"
    if h == 12:
        return "12 PM"
    return f"{h-12} PM"


def verdict(delay):
    if delay < 1.5:
        return "USUALLY ON TIME"
    if delay < 6:
        return f"USUALLY {round(delay)} MIN LATE"
    return f"OFTEN {round(delay)}+ MIN LATE"


def dot_for(delay, otr):
    if otr >= 0.7 and delay < 1.5:
        return "var(--green)"
    if otr >= 0.5:
        return "var(--amber)"
    return "var(--red)"


try:
    overall, route_stats, route_dir, route_dir_hour, stop_stats = load()
except Exception as e:
    st.error(f"Summary not ready. Run:  python src/build_summary.py\n\n{e}")
    st.stop()

st.markdown('<div class="kicker">Spokane Transit &middot; is your bus on time?</div>', unsafe_allow_html=True)
sign_slot = st.empty()

# ---- 1) pick route ----
def sortkey(r):
    return (0, int(r)) if r.isdigit() else (1, 0, r)
routes_with_dir = sorted(route_dir["route"].unique().tolist(), key=sortkey)
default = route_stats.sort_values("n", ascending=False)["route"].iloc[0]
c1, c2 = st.columns([1, 1.4])
with c1:
    sel = st.selectbox("Pick your bus", routes_with_dir,
                       index=routes_with_dir.index(default) if default in routes_with_dir else 0)

# ---- 2) pick direction ----
dirs = route_dir[route_dir["route"] == sel].sort_values("direction_id")
dir_labels = {int(r["direction_id"]): (r["trip_headsign"] or f"Dir {int(r['direction_id'])}")
              for _, r in dirs.iterrows()}
with c2:
    if len(dir_labels) > 1:
        chosen_head = st.radio("Direction", list(dir_labels.values()), horizontal=True)
        chosen_dir = [d for d, h in dir_labels.items() if h == chosen_head][0]
    else:
        chosen_dir = list(dir_labels.keys())[0] if dir_labels else 0
        chosen_head = dir_labels.get(chosen_dir, "")
        st.markdown(f'<div style="padding-top:26px;color:var(--muted);font-size:.8rem">to {chosen_head}</div>',
                    unsafe_allow_html=True)

drow = dirs[dirs["direction_id"] == chosen_dir]
if drow.empty:
    st.stop()
drow = drow.iloc[0]

# ---- 3) pick stop (optional) ----
stops_here = stop_stats[(stop_stats["route"] == sel) &
                        (stop_stats["direction_id"] == chosen_dir)].sort_values("stop_sequence")
stop_choice = "Whole route (all stops)"
picked_stop = None
if len(stops_here):
    stop_opts = [stop_choice] + [f"{r['stop_name']}" for _, r in stops_here.iterrows()]
    stop_choice = st.selectbox("Where do you catch it?", stop_opts)
    if stop_choice != "Whole route (all stops)":
        picked_stop = stops_here[stops_here["stop_name"] == stop_choice].iloc[0]

# ---- decide what the sign shows: stop-level if chosen, else whole direction ----
if picked_stop is not None:
    delay = picked_stop["mean_delay_min"]
    otr = picked_stop["on_time_rate"]
    n = int(picked_stop["n"])
    at_line = f'<div class="at">at {str(stop_choice).upper()}</div>'
    basis = f"at this stop &middot; {n:,} arrivals"
else:
    delay = drow["mean_delay_min"]
    otr = drow["on_time_rate"]
    n = int(drow["n"])
    at_line = ""
    basis = f"whole route &middot; {n:,} arrivals"

dest = str(chosen_head).upper().strip()
# only prepend "TO" for plain place-name headsigns; leave "EASTBOUND TO SCC" etc. as-is
if dest and not any(w in dest for w in ["BOUND", " TO ", "INBOUND", "OUTBOUND"]) and not dest.startswith("TO "):
    dest = f"TO {dest}"
sign_slot.markdown(f"""
<div class="sign">
  <div class="rt"><span class="lab">ROUTE</span>{sel}</div>
  <div class="dest">{dest}</div>
  {at_line}
  <div class="rule"></div>
  <div class="verdict">{verdict(delay)}</div>
</div>
""", unsafe_allow_html=True)

# ---- plain facts ----
delay_word = "on schedule on average" if delay < 1 else f"about <b>{round(delay)} min late</b> on average"
facts = [
    (dot_for(delay, otr), f'On time <b>{round(otr*10)} out of 10</b> trips ({otr*100:.0f}%)'),
    ("var(--amber)" if delay >= 1 else "var(--green)", f'Runs {delay_word}'),
]
# worst hour for this direction
dh = route_dir_hour[(route_dir_hour["route"] == sel) &
                    (route_dir_hour["direction_id"] == chosen_dir) &
                    (route_dir_hour["hour"] >= 5) & (route_dir_hour["hour"] <= 23) &
                    (route_dir_hour["n"] >= 30)]
if len(dh):
    w = dh.loc[dh["mean_delay_min"].idxmax()]
    if w["mean_delay_min"] >= 2:
        facts.append(("var(--red)", f'Worst around <b>{ampm(w["hour"])}</b> '
                                    f'(about {round(w["mean_delay_min"])} min late)'))
facts_html = "".join(
    f'<div class="fact"><span class="dot" style="background:{c}"></span><span>{t}</span></div>'
    for c, t in facts)
st.markdown(f'<div class="facts">{facts_html}</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub">based on {basis}</div>', unsafe_allow_html=True)

# ---- least reliable (route rollup) ----
st.markdown('<div class="h2">Least reliable buses</div>', unsafe_allow_html=True)
worst5 = route_stats.sort_values("mean_delay_min", ascending=False).head(5)
lr = ""
for _, row in worst5.iterrows():
    d = row["mean_delay_min"]
    late = "on schedule" if d < 1 else f"about <b>{round(d)} min late</b>"
    lr += (f'<div class="lr"><div class="badge">{row["route"]}</div>'
           f'<div class="txt">Route {row["route"]} &mdash; {late}, '
           f'on time {round(row["on_time_rate"]*10)}/10 trips</div></div>')
st.markdown(lr, unsafe_allow_html=True)

st.markdown(
    f'<div class="foot">Based on {int(overall["n_stop_visits"]):,} real arrivals, '
    f'{overall["data_start"][:10]} to {overall["data_end"][:10]}. '
    f'A first look at ~6 days &mdash; finer slices (stop, hour) are noisier and grow more reliable '
    f'as data accumulates.<br>'
    f'Background: Spokane Transit City Line bus by JTRamsey, '
    f'<a href="https://commons.wikimedia.org/wiki/File:Full_Spokane_City_Line_bus_charging_at_SCC_transit_center_October_2023.jpg">'
    f'Wikimedia Commons</a>, CC BY-SA 4.0.</div>',
    unsafe_allow_html=True)
