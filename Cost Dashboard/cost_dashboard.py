"""
Snowflake Cost Dashboard

Requires the app owner role to hold IMPORTED PRIVILEGES on database SNOWFLAKE.
Uses only packages bundled with Streamlit in Snowflake - no environment.yml needed.
"""

import json
import decimal

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from snowflake.snowpark.context import get_active_session

# -------------------------------------------------
# Session
# -------------------------------------------------

try:
    session = get_active_session()
except Exception:
    conn = st.connection("snowflake")
    session = conn.session()
else:
    class _SessConn:
        def query(self, sql, ttl=300):
            return session.sql(sql).to_pandas()
    conn = _SessConn()

# -------------------------------------------------
# Page config
# -------------------------------------------------

st.set_page_config(
    page_title="Cost Dashboard",
    page_icon="📊",
    layout="wide",
)

# ----------------------------------------------------------------------
# Page settings
# Cache Snowflake queries for 1h; cast NUMBER/Decimal to float for charts.
# ----------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Querying ACCOUNT_USAGE...")

def _query(sql: str, start: str, end: str) -> pd.DataFrame:
    df = session.sql(sql, params=[start, end]).to_pandas()
    # Snowflake NUMBER(p,s) arrives as decimal.Decimal -> object dtype.
    # Cast to float so .round(), .clip() and the charts work.
    for c in df.columns:
        if df[c].map(lambda v: isinstance(v, decimal.Decimal)).any():
            df[c] = df[c].astype(float)
    return df


def run(sql: str, start: str, end: str) -> pd.DataFrame:
    """A missing view or column degrades one section, not the whole app."""
    try:
        return _query(sql, start, end)
    except Exception as e:
        st.warning(f"Query failed, section will be empty: {e}")
        return pd.DataFrame()


def run_optional(sql: str, start: str, end: str) -> pd.DataFrame:
    """Silent variant: these views are legitimately absent on many accounts."""
    try:
        return _query(sql, start, end)
    except Exception:
        return pd.DataFrame()

# ----------------------------------------------------------------------
# Config from config.json (same folder as this app)
# ----------------------------------------------------------------------

def _load_config():
    candidates = []
    try:
        candidates.append(Path(__file__).resolve().parent / "config.json")
    except Exception:
        pass
    candidates.append(Path("config.json"))
    for path in candidates:
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("config.json must contain a JSON object")
            return data, path
    raise FileNotFoundError(
        "config.json not found next to cost_dashboard.py. "
        "Add config.json with contract_start, annual_capacity, credit_rate, credit_rate_label."
    )

_cfg, _cfg_path = _load_config()
credit_price = float(_cfg["credit_rate"])
rate_choice = str(_cfg.get("credit_rate_label", "") or "Configured rate")
if credit_price <= 0:
    rate_choice = "Credits only"
    
# ----------------------------------------------------------------------
# Colors
# ----------------------------------------------------------------------

NAVY = "#16324F"
NAVY_LIGHT = "#2A5F8F"
NAVY_DEEP = "#0F2438"
SNOW_BLUE = "#29B5E8"
BLUE_MID = "#5FC5EC"
BLUE_LIGHT = "#A7D8EF"
BLUE_PALE = "#CFE8F5"
PANEL = "#E9EEF2"
CARD_BG = "#EEF2F6"
INK = "#0F2438"
MUTED = "#6B7F92"
GREEN = "#1F9D6B"
RED = "#C23B3B"
WHITE = "#FFFFFF"

# ----------------------------------------------------------------------
# Style
# ----------------------------------------------------------------------

st.markdown(
    f"""
    <style>
      .stApp {{ background: #F4F6F8; }}
      .block-container {{ padding-top: 1.4rem; max-width: 1600px; }}
      #MainMenu, footer {{ visibility: hidden; }}
      .masthead {{ display: flex; align-items: baseline; gap: .55rem; margin-bottom: .1rem; }}
      .masthead h1 {{
        font-size: 1.65rem; font-weight: 800; color: {INK};
        margin: 0; letter-spacing: -.02em;
      }}
      .masthead .logo {{
        height: 28px; width: auto; object-fit: contain;
        display: block;
      }}
      .masthead .logo-fallback {{
        width: 28px; height: 28px; border-radius: 6px;
        background: linear-gradient(135deg, {SNOW_BLUE}, {NAVY_LIGHT});
        flex-shrink: 0;
      }}
      .subhead {{ color: {MUTED}; font-size: .75rem; margin: .1rem 0 .8rem 0; }}
      .card {{
        border-radius: 12px; padding: .75rem .9rem 0.85rem .9rem; height: 100%;
        text-align: center; background: {CARD_BG};
        border: 1px solid #E2E8EE;
      }}
      .card.primary {{
        background: {NAVY_LIGHT}; color: #FFFFFF; text-align: left;
        padding: .85rem 1rem; border: none;
      }}
      .card .label {{
        font-size: .62rem; font-weight: 600; letter-spacing: .01em;
        opacity: .85; margin-bottom: .2rem; line-height: 1.2;
      }}
      .card .value {{
        font-size: 1.25rem; font-weight: 800; letter-spacing: -.03em;
        line-height: 1.15; font-variant-numeric: tabular-nums;
        color: {INK};
      }}
      .card.primary .value {{ color: #FFFFFF; font-size: 1.42rem; }}
      .card .delta-pill {{
        display: inline-block; margin-top: .35rem; margin-bottom: .25rem;
        padding: .12rem .5rem; border-radius: 999px;
        font-size: .62rem; font-weight: 600;
      }}
      .card .delta-pill.up {{ background: #D8F3E7; color: {GREEN}; }}
      .card .delta-pill.down {{ background: #FDE8E8; color: {RED}; }}
      .card.primary .delta-pill.up {{ background: rgba(125,255,179,.22); color: #7DFFB3; }}
      .card.primary .delta-pill.down {{ background: rgba(255,180,180,.22); color: #FFB4B4; }}
      .card .foot {{
        font-size: .78rem; color: {MUTED}; margin-top: .15rem;
        line-height: 1.35;
      }}
      .card.primary .foot {{ color: rgba(255,255,255,.78); }}
      .budget-bar {{
        height: 5px; border-radius: 3px; background: rgba(255,255,255,.18);
        margin: .45rem 0 .35rem 0; overflow: hidden;
      }}
      .budget-bar span {{ display: block; height: 100%; background: {SNOW_BLUE}; border-radius: 3px; }}
      .tray {{
        background: {PANEL}; border-radius: 10px;
        padding: .45rem .5rem;
      }}
      .note {{
        text-align: left; color: {MUTED}; font-size: .66rem;
        margin: .55rem 0 1rem 0; line-height: 1.4;
      }}
      .panel-title {{
        font-size: .82rem; font-weight: 700; color: {INK};
        margin: 0 0 .4rem .05rem;
      }}
      div[data-testid="stSelectbox"] label,
      div[data-testid="stDateInput"] label {{
        color: {MUTED}; font-size: .72rem;
      }}
      .range-label {{
        font-size: .78rem; color: {INK}; margin: .35rem 0 .5rem 0;
      }}
      .range-label b {{ color: {RED}; }}
      /* Smaller Warehouse Detail dataframe text */
      div[data-testid="stDataFrame"] {{
        font-size: 0.72rem;
      }}
      div[data-testid="stDataFrame"] table {{
        font-size: 0.72rem;
      }}
      div[data-testid="stDataFrame"] th {{
        font-size: 0.68rem !important;
        padding-top: 0.25rem !important;
        padding-bottom: 0.25rem !important;
      }}
      div[data-testid="stDataFrame"] td {{
        font-size: 0.72rem !important;
        padding-top: 0.2rem !important;
        padding-bottom: 0.2rem !important;
      }}
      /* Denser stacked bars (Vega / native chart) */
      .stVegaLiteChart svg g.mark-rect > path,
      .stVegaLiteChart svg rect {{ }}
      div[data-testid="stVegaLiteChart"] svg .mark-bar rect,
      div[data-testid="stArrowVegaLiteChart"] svg .mark-bar rect {{
        /* browser may ignore; height increase is primary lever */
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Logo
# ----------------------------------------------------------------------

_logo_html = '<div class="logo-fallback" title="Add logo.png or logo.jpg"></div>'
try:
    import base64 as _b64
    _logo_dir = Path(__file__).resolve().parent
    _logo_path = None
    _mime = None
    for _name, _m in (
        ("logo.png", "image/png"),
        ("logo.jpg", "image/jpeg"),
        ("logo.jpeg", "image/jpeg"),
    ):
        _candidate = _logo_dir / _name
        if _candidate.is_file():
            _logo_path, _mime = _candidate, _m
            break
    if _logo_path is not None:
        _b64data = _b64.b64encode(_logo_path.read_bytes()).decode("ascii")
        _logo_html = (
            f'<img class="logo" alt="Logo" '
            f'src="data:{_mime};base64,{_b64data}"/>'
        )
except Exception:
    pass

# ----------------------------------------------------------------------
# Page Header
# ----------------------------------------------------------------------

DATE_PRESET_MAP = {
    "Today": "TODAY",
    "Week to Date": "WTD",
    "Month to Date": "MTD",
    "Quarter to Date": "QTD",
    "Year to Date": "YTD",
}
DATE_PRESETS = list(DATE_PRESET_MAP.keys())

if "last_refreshed" not in st.session_state:
    st.session_state.last_refreshed = datetime.now()

title_col, range_col = st.columns([3.2, 1.3])
with title_col:
    st.markdown(
        f'<div class="masthead">{_logo_html}<h1>Cost Dashboard</h1></div>'
        '<div class="subhead">Warehouse, query, serverless, AI, storage, '
        "and data-transfer detail.</div>"
        f'<div style="color:{MUTED};font-size:.72rem;margin:-0.35rem 0 0.15rem 0;">'
        f"Last refreshed: {st.session_state.last_refreshed.strftime('%Y-%m-%d %H:%M:%S')}</div>",
        unsafe_allow_html=True,
    )
with range_col:
    preset_label = st.selectbox(
        "Date Range",
        DATE_PRESETS,
        index=DATE_PRESETS.index("Year to Date"),
    )
    preset = DATE_PRESET_MAP[preset_label]

today = datetime.now().date()
if preset == "TODAY":
    start_date = today
    end_date = today
elif preset == "WTD":
    start_date = today - timedelta(days=today.weekday())  # Monday
    end_date = today
elif preset == "MTD":
    start_date = today.replace(day=1)
    end_date = today
elif preset == "QTD":
    quarter_start_month = ((today.month - 1) // 3) * 3 + 1
    start_date = today.replace(month=quarter_start_month, day=1)
    end_date = today
else:  # YTD
    start_date = today.replace(month=1, day=1)
    end_date = today

with range_col:
    st.markdown(
        f'<div style="color:{MUTED};font-size:0.72rem;margin-top:-0.35rem;">'
        f'{start_date.strftime("%b %d, %Y")} → {end_date.strftime("%b %d, %Y")}'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

start_ts = start_date.strftime("%Y-%m-%d")
end_ts = end_date.strftime("%Y-%m-%d")

# ACCOUNT_USAGE ranges are half-open; end bound is exclusive.
p_start = start_ts
p_end = (end_date + timedelta(days=1)).isoformat()


# ----------------------------------------------------------------------
# Queries
# ----------------------------------------------------------------------

Q_WAREHOUSE = """
SELECT warehouse_name                                AS "Warehouse"
     , SUM(credits_used_compute)                     AS "Compute"
     , SUM(credits_used_cloud_services)              AS "Cloud Services"
     , SUM(COALESCE(credits_attributed_compute_queries, 0)) AS "Query Attributed"
     , GREATEST(SUM(credits_used_compute)
       - SUM(COALESCE(credits_attributed_compute_queries, 0)), 0) AS "Idle"
     , SUM(credits_used)                             AS "Total Credits"
FROM snowflake.account_usage.warehouse_metering_history
WHERE start_time >= ? AND start_time < ?
GROUP BY 1
ORDER BY "Total Credits" DESC
"""

Q_WAREHOUSE_DAILY = """
SELECT TO_CHAR(start_time, 'YYYY-MM-DD') AS "Date"
     , warehouse_name       AS "Warehouse"
     , SUM(credits_used)    AS "Credits"
FROM snowflake.account_usage.warehouse_metering_history
WHERE start_time >= ? AND start_time < ?
GROUP BY 1, 2
ORDER BY 1
"""

Q_QUERY = """
SELECT warehouse_name                       AS "Warehouse"
     , COUNT(*)                             AS "Queries"
     , SUM(credits_attributed_compute)      AS "Query Credits"
     , SUM(credits_used_query_acceleration) AS "Query Acceleration"
     , AVG(credits_attributed_compute)      AS "Avg Credits / Query"
FROM snowflake.account_usage.query_attribution_history
WHERE start_time >= ? AND start_time < ?
GROUP BY 1
ORDER BY "Query Credits" DESC
"""

# One predicate defines AI. Q_SERVERLESS negates it, so the two sections
# can never overlap or leave a gap. Add new AI service types here only.
AI_PREDICATE = """(
       service_type LIKE 'AI%'
    OR service_type LIKE 'CORTEX%'
    OR service_type LIKE 'SNOWFLAKE_COCO%'
    OR service_type IN ('SNOWFLAKE_COWORK', 'SNOWFLAKE_INTELLIGENCE')
  )"""

Q_SERVERLESS = f"""
SELECT service_type        AS "Service"
     , SUM(credits_used)   AS "Credits"
FROM snowflake.account_usage.metering_daily_history
WHERE usage_date >= ? AND usage_date < ?
  AND service_type NOT IN ('WAREHOUSE_METERING', 'WAREHOUSE_METERING_READER')
  AND NOT {AI_PREDICATE}
GROUP BY 1
HAVING SUM(credits_used) > 0
ORDER BY "Credits" DESC
"""

Q_CLOUD = """
SELECT TO_CHAR(usage_date, 'YYYY-MM-DD')          AS "Date"
     , SUM(credits_used_compute)                  AS "Warehouse Compute"
     , SUM(credits_used_cloud_services)           AS "Cloud Services Used"
     , -SUM(credits_adjustment_cloud_services)    AS "Covered by allowance"
     , SUM(credits_used_cloud_services)
       + SUM(credits_adjustment_cloud_services)   AS "Billed"
FROM snowflake.account_usage.metering_daily_history
WHERE usage_date >= ? AND usage_date < ?
GROUP BY 1
ORDER BY 1
"""

Q_TRANSFER = """
SELECT transfer_type AS "Type"
     , source_cloud || ' ' || source_region || '  ->  '
       || target_cloud || ' ' || target_region      AS "Route"
     , SUM(bytes_transferred) / POWER(1024, 4)      AS "TB"
FROM snowflake.account_usage.data_transfer_history
WHERE start_time >= ? AND start_time < ?
GROUP BY 1, 2
HAVING SUM(bytes_transferred) > 0
ORDER BY "TB" DESC
"""

Q_STORAGE = """
SELECT usage_date                    AS "Date"
     , storage_bytes  / POWER(1024, 4) AS "Database"
     , stage_bytes    / POWER(1024, 4) AS "Stage"
     , failsafe_bytes / POWER(1024, 4) AS "Fail-safe"
FROM snowflake.account_usage.storage_usage
WHERE usage_date >= ? AND usage_date < ?
ORDER BY 1
"""

Q_AI = f"""
SELECT service_type        AS "Service"
     , SUM(credits_used)   AS "Credits"
FROM snowflake.account_usage.metering_daily_history
WHERE usage_date >= ? AND usage_date < ?
  AND {AI_PREDICATE}
GROUP BY 1
HAVING SUM(credits_used) > 0
ORDER BY "Credits" DESC
"""

Q_AI_DETAIL = """
SELECT COALESCE(model_name, '(none)') AS "Model"
     , function_name                  AS "Function"
     , SUM(tokens)                    AS "Tokens"
     , SUM(token_credits)             AS "Credits"
FROM snowflake.account_usage.cortex_functions_usage_history
WHERE start_time >= ? AND start_time < ?
GROUP BY 1, 2
ORDER BY "Credits" DESC
"""


wh = run(Q_WAREHOUSE, p_start, p_end)
wh_daily = run(Q_WAREHOUSE_DAILY, p_start, p_end)
qry = run(Q_QUERY, p_start, p_end)
srv = run(Q_SERVERLESS, p_start, p_end)
cld = run(Q_CLOUD, p_start, p_end)
stg = run(Q_STORAGE, p_start, p_end)
xfer = run(Q_TRANSFER, p_start, p_end)
ai = run_optional(Q_AI, p_start, p_end)
ai_detail = run_optional(Q_AI_DETAIL, p_start, p_end)


def total(df: pd.DataFrame, col: str) -> float:
    return float(df[col].sum()) if not df.empty else 0.0


srv_credits = total(srv, "Credits")
ai_credits = total(ai, "Credits")


# ----------------------------------------------------------------------
# Warehouse credits
# ----------------------------------------------------------------------

st.subheader("Warehouse credits")

if wh.empty:
    st.info("No warehouse metering in this range.")
else:
    c1, c2 = st.columns([3, 2])
    wh_height = max(380, 34 * len(wh) + 120)

    with c1:
        st.markdown("**Credit composition by warehouse**")
        st.bar_chart(
            wh.melt(
                id_vars="Warehouse",
                value_vars=["Query Attributed", "Idle", "Cloud Services"],
                var_name="Component", value_name="Credits",
            ),
            x="Warehouse", y="Credits", color="Component", horizontal=True,
            height=wh_height,
        )

    with c2:
        if not wh_daily.empty:
            st.markdown("**Daily credits by warehouse**")
            st.bar_chart(
                wh_daily, x="Date", y="Credits", color="Warehouse", height=wh_height
            )

    st.markdown(
        f"""
        <div class="note">
        **Query Attributed** - compute credits traced to specific query 
        execution.
        <br>**Idle** - compute credits billed while the warehouse 
        was running with no query attributed to it, including auto-suspend 
        lag, the 60-second minimum on resume, and cluster startup.
        <br>**Cloud Services** - credits that warehouse generated in the 
        cloud services layer for compilation, metadata, and access checks; 
        only the portion above the daily 10% allowance is billed.
        </div>
        """,
        unsafe_allow_html=True,
    )

    disp = wh.copy()
    disp["Idle %"] = (
        disp["Idle"] / disp["Compute"].where(disp["Compute"] != 0) * 100
    ).round(1)
    if credit_price:
        disp["Cost $"] = (disp["Total Credits"] * credit_price).round(0)
    st.markdown("**Warehouse detail**")
    st.dataframe(disp, use_container_width=True, hide_index=True)


# ----------------------------------------------------------------------
# Query-attributed credits
# ----------------------------------------------------------------------

st.subheader("Query-attributed credits by warehouse")

if qry.empty:
    st.info("No query attribution data in this range.")
else:
    c1, c2 = st.columns([3, 2])
    qry_height = max(380, 34 * len(qry) + 120)

    with c1:
        st.bar_chart(
            qry, x="Warehouse", y="Query Credits", horizontal=True, height=qry_height
        )

    with c2:
        recon = qry.merge(
            wh[["Warehouse", "Compute"]], on="Warehouse", how="outer"
        ).fillna(0)
        recon["Unattributed"] = (recon["Compute"] - recon["Query Credits"]).clip(lower=0)
        st.bar_chart(
            recon.melt(
                id_vars="Warehouse",
                value_vars=["Query Credits", "Unattributed"],
                var_name="Component", value_name="Credits",
            ),
            x="Warehouse", y="Credits", color="Component", horizontal=True,
            height=qry_height,
        )
        st.markdown(
            f"""
            <div class="note">
            Attributed vs unattributed share of warehouse compute.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.dataframe(qry.round(4), use_container_width=True, hide_index=True)
    st.markdown(
    f"""
    <div class="note">
        Attribution excludes warehouse idle time and sub-100ms queries, so it will 
        not sum to warehouse compute credits.
    </div>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------
# Serverless
# ----------------------------------------------------------------------

st.divider()

st.subheader("Serverless compute")

if srv.empty:
    st.info("No serverless credit consumption in this range.")
else:
    c1, c2 = st.columns([3, 2])
    srv_height = max(380, 34 * len(srv) + 120)
    with c1:
        st.bar_chart(
            srv, x="Service", y="Credits", horizontal=True, height=srv_height
        )
    with c2:
        pct = srv.copy()
        pct["% of serverless"] = (pct["Credits"] / srv_credits * 100).round(1)
        if credit_price:
            pct["Cost $"] = (pct["Credits"] * credit_price).round(0)
        st.dataframe(pct, use_container_width=True, hide_index=True, height=srv_height)


# ----------------------------------------------------------------------
# AI services
# ----------------------------------------------------------------------

st.divider()

st.subheader("AI services")

if ai.empty:
    st.info("No AI service credits in this range.")
else:
    c1, c2 = st.columns([3, 2])
    ai_height = max(380, 34 * len(ai) + 120)
    with c1:
        st.bar_chart(ai, x="Service", y="Credits", horizontal=True, height=ai_height)
        st.markdown(
            f"""
            <div class="note">
            Cortex AI functions, Analyst, Search, Agents, fine-tuning, CoCo, and 
            CoWork. Snowflake renames these periodically - if an unfamiliar 
            AI-looking service appears under Serverless, add it to AI_PREDICATE.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        svc = ai.copy()
        svc["% of AI"] = (svc["Credits"] / ai_credits * 100).round(1)
        if credit_price:
            svc["Cost $"] = (svc["Credits"] * credit_price).round(0)
        st.dataframe(svc, use_container_width=True, hide_index=True, height=ai_height)

    if not ai_detail.empty:
        st.bar_chart(
            ai_detail, x="Model", y="Credits", color="Function", horizontal=True,
            height=max(380, 34 * len(ai_detail) + 120),
        )
        detail = ai_detail.copy()
        detail["Credits / M tokens"] = (
            detail["Credits"] / detail["Tokens"].where(detail["Tokens"] != 0) * 1e6
        ).round(2)
        st.dataframe(detail, use_container_width=True, hide_index=True)
        st.markdown(
            f"""
            <div class="note">
            Per-function token spend. Credits per million tokens is set by model, so 
            moving high-volume calls to a smaller model is the main lever. Warehouse 
            compute for the calling query is billed separately and appears above.
            </div>
            """,
            unsafe_allow_html=True,
        )


# ----------------------------------------------------------------------
# Cloud services
# ----------------------------------------------------------------------

st.divider()

st.subheader("Cloud services")

if cld.empty:
    st.info("No metering data in this range.")
else:
    cs_ratio = (
        cld["Cloud Services Used"].sum() / cld["Warehouse Compute"].sum() * 100
        if cld["Warehouse Compute"].sum() else 0
    )

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**Daily cloud services credits**")
        st.bar_chart(
            cld, x="Date", y=["Covered by allowance", "Billed"], height=380
        )
        st.markdown(
            f"""
            <div class="note">
            Bar height is total cloud services consumed. The two segments split it 
            into the portion absorbed by the daily 10% allowance and the portion 
            actually charged."
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown("**Allowance check**")
        st.metric("Cloud services as % of warehouse compute", f"{cs_ratio:.1f}%")
        st.markdown(
            f"""
            <div class="note">
            Cloud services are only billed above the daily 10% allowance. 
            Adjustment is the credit-back for the covered portion, so it is negative.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.dataframe(
            cld.tail(14).round(3), use_container_width=True, hide_index=True, height=300
        )


# ----------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------

st.divider()

st.subheader("Storage")

if stg.empty:
    st.info("No storage history in this range.")
else:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.area_chart(stg, x="Date", y=["Database", "Stage", "Fail-safe"], height=380)
        st.markdown(
            f"""
            <div class="note">
                Average daily storage, TB.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        latest = stg.iloc[-1]
        st.metric("Database", f"{latest['Database']:,.2f} TB")
        st.metric("Stage", f"{latest['Stage']:,.2f} TB")
        st.metric("Fail-safe", f"{latest['Fail-safe']:,.2f} TB")
        if latest["Database"]:
            st.metric(
                "Fail-safe as % of database",
                f"{latest['Fail-safe'] / latest['Database'] * 100:.1f}%",
            )
st.markdown(
    f"""
    <div class="note">
        STORAGE_USAGE measures differently than billing and will not tie exactly to 
        the invoice. Storage is billed in $/TB/month, not credits, so it is excluded 
        from credit totals on Cost Summary.
    </div>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------
# Data transfer
# ----------------------------------------------------------------------

st.divider()

st.subheader("Data transfer")

if xfer.empty:
    st.info("No data transfer in this range.")
else:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**Egress by route**")
        st.bar_chart(
            xfer, x="Route", y="TB", color="Type", horizontal=True,
            height=max(320, 34 * len(xfer) + 120),
        )
    with c2:
        st.markdown("**Detail**")
        st.dataframe(
            xfer.round(4), use_container_width=True, hide_index=True,
            height=max(320, 34 * len(xfer) + 120),
        )

st.markdown(
    f"""
    <div class="note">
        Ingress is free; egress is charged per TB at rates that vary by source and 
        target region, so this is reported in terabytes rather than credits or 
        dollars. Transfer within a single region on the same cloud is not billed. 
        REPLICATION covers failover groups, EXTERNAL_FUNCTION covers calls out to 
        external services, and COPY covers unloading to external stages.
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Notes
# ----------------------------------------------------------------------

st.markdown("---")

st.markdown(
    f"""
    <div class="note">
    ACCOUNT_USAGE views are not real time. Metering and storage lag by roughly
    2 to 3 hours, query attribution by up to 8 hours, and Cortex function usage
    by about 5 minutes. Ranges that include today or yesterday will therefore
    understate actual consumption, and the most recent day is always partial.<br><br>
    Storage and data transfer bill in dollars per terabyte, not credits, so
    neither is included in Total credits / Total Spend.
    Figures are drawn from ACCOUNT_USAGE and are for internal analysis only -
    they will not tie exactly to your Snowflake invoice. Use ORGANIZATION_USAGE
    or the billing statement for figures of record.
    </div>
    """,
    unsafe_allow_html=True,
)
