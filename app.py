import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pandas.io.formats.style import Styler
from pathlib import Path
import base64
from datetime import datetime

def get_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# ── Colour palette (defined once, used throughout) ───────────────────────────
COLOR_COMPLETE    = "#D4EDDA"
COLOR_IN_PROGRESS = "#FFF3CD"
COLOR_BLOCKED     = "#F8D7DA"
COLOR_NOT_STARTED = "#E9ECEF"
COLOR_ESCALATED   = "#C0392B"
COLOR_PRIMARY     = "#1B3A6B"
COLOR_SECONDARY   = "#4ECDC4"
COLOR_ACCENT      = "#E8F8F7"

STATUS_COLORS = {
    "Complete":    COLOR_COMPLETE,
    "In Progress": COLOR_IN_PROGRESS,
    "Blocked":     COLOR_BLOCKED,
    "Not Started": COLOR_NOT_STARTED,
}

BAR_COLORS = {
    "Not Started": "#ADB5BD",
    "In Progress": "#F0A500",
    "Blocked":     "#C0392B",
    "Escalated":   "#922B21",
    "Complete":    "#27AE60",
}

TIMELINE_COLORS = {
    "On Time": "#27AE60",
    "At Risk":  "#F0A500",
    "Late":     "#C0392B",
}

PHASE_ORDER = ["Pre-Close", "Close", "Close-to-Post-Close", "Post-Close"]

ENTITY_DISPLAY = {
    "BU001":  "BU001 Switzerland",
    "BU002":  "BU002 Germany",
    "BU003":  "BU003 Austria",
    "DACH":   "DACH Region",
    "EMEA":   "EMEA Area",
    "Global": "Global",
}

BU_ENTITY_KEYS = ["BU001", "BU002", "BU003"]

# Original column list (kept for reference)
BU_DISPLAY_COLS = [
    "Working Day", "Task ID", "Task Description", "Organization Level",
    "Country", "Status", "Completion %", "Priority", "Escalated", "Comments",
]

# Table columns - BU tables (Timeline Status inserted after Status)
BU_TABLE_COLS = [
    "Working Day", "Task ID", "Task Description", "Organization Level",
    "Country", "Status", "Timeline Status", "Completion %", "Priority", "Escalated", "Comments",
]

# Table columns - Consolidated table
CONSOLIDATED_TABLE_COLS = [
    "Working Day", "Task ID", "Task Description", "Organization Level",
    "Org Level Name", "Status", "Timeline Status", "Completion %", "Priority", "Escalated", "Comments",
]

TIMELINE_STATUS_OPTIONS = ["On Time", "At Risk", "Late"]

PAST_WD = {"WD-5", "WD-4", "WD-3", "WD-1", "WD+0"}

st.set_page_config(
    page_title="Helvetia Advisory AG - Month-End Close Manager",
    layout="wide",
)


# ── Timeline Status helper (module-level for @st.cache_data pickling) ─────────

def _timeline_status(row) -> str:
    status = row["Status"]
    wd = row["Working Day"]
    if status == "Complete":
        return "On Time"
    if wd in PAST_WD:
        return "Late"
    if wd == "WD+1":
        if status == "In Progress":
            return "At Risk"
        return "Late"           # Not Started or Blocked on due date
    # WD+2 or WD+3 (future)
    if status == "Blocked":
        return "At Risk"        # future task already blocked
    return "On Time"            # Not Started or In Progress, not yet due


# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data
def load_task_master() -> pd.DataFrame:
    df = pd.read_excel(
        "data/FPnAMonth-EndCloseWorkflow.xlsx",
        sheet_name="Task Master",
    )
    df = df.rename(columns={"Completon %": "Completion %"})
    for col in ["Comments", "Escalated", "Status", "Phase", "Lowest Org Level Name", "Owner Function", "Escalation Role"]:
        if col in df.columns:
            df[col] = df[col].fillna("")
    df["Timeline Status"] = df.apply(_timeline_status, axis=1)
    return df


# ── Helpers ───────────────────────────────────────────────────────────────────

def wd_to_int(wd) -> int:
    """Convert Working Day string (e.g. 'WD-5', 'WD+1', 'WD+0') to integer for sort."""
    try:
        return int(str(wd).replace("WD", "").replace("+", ""))
    except (ValueError, AttributeError):
        return 999


def style_status_rows(display_df: pd.DataFrame) -> Styler:
    """Apply row background colour based on Status column."""
    def row_style(row):
        color = STATUS_COLORS.get(row["Status"], COLOR_NOT_STARTED)
        return [f"background-color: {color}"] * len(row)

    return display_df.style.apply(row_style, axis=1)


def _sort_by_phase_wd(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by PHASE_ORDER index then by Working Day numerically."""
    df = df.copy()
    df["_ps"] = df["Phase"].apply(lambda p: PHASE_ORDER.index(p) if p in PHASE_ORDER else 999)
    df["_ws"] = df["Working Day"].apply(wd_to_int)
    return df.sort_values(["_ps", "_ws"]).drop(columns=["_ps", "_ws"])


def _make_display(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Select available columns and replace Escalated Yes/No with badge text."""
    display = df[[c for c in cols if c in df.columns]].copy()
    if "Escalated" in display.columns:
        display["Escalated"] = display["Escalated"].apply(
            lambda v: "ESCALATED" if str(v).strip() == "Yes" else ""
        )
    return display


# ── Demo disclaimer ───────────────────────────────────────────────────────────

def render_disclaimer():
    st.markdown(
        """
        <div style='background:#EEF2F7; border-left:3px solid #4ECDC4; color:#6B7280;
                    font-size:0.8rem; padding:8px 16px; border-radius:4px; margin-bottom:16px;'>
            Demo Dataset - Helvetia Advisory AG | Fiscal Period 2026 P05 | For illustration purposes only
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── RAG close health indicator ────────────────────────────────────────────────

def render_rag_indicator(df: pd.DataFrame):
    total = len(df)
    if total == 0:
        return
    problem_count = int(((df["Status"] == "Blocked") | (df["Timeline Status"] == "Late")).sum())
    pct_problem = problem_count / total * 100
    if pct_problem > 10:
        color, label = "#C0392B", "Close at Risk"
    elif pct_problem > 5:
        color, label = "#F0A500", "Close Needs Attention"
    else:
        color, label = "#27AE60", "Close On Track"
    st.markdown(
        f"""
        <div style='background:white; border-left:4px solid {color}; border-radius:8px;
                    padding:12px 20px; box-shadow:0 2px 8px rgba(27,58,107,0.08); margin-bottom:16px;'>
            <span style='color:{color}; font-size:1.4rem;'>&#9679;</span>
            <strong style='color:{color}; font-size:1rem; margin-left:8px;'>{label}</strong>
            <span style='color:#6B7280; font-size:0.85rem; margin-left:12px;'>
                {pct_problem:.0f}% of tasks blocked or late ({problem_count} of {total} tasks)
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Dashboard calculations ────────────────────────────────────────────────────

def compute_metrics(df: pd.DataFrame) -> dict:
    total = len(df)
    complete = int((df["Status"] == "Complete").sum())
    in_progress = int((df["Status"] == "In Progress").sum())
    not_started = int((df["Status"] == "Not Started").sum())
    blocked_escalated = int(((df["Status"] == "Blocked") | (df["Escalated"] == "Yes")).sum())
    sla_breaches          = int(((df["Timeline Status"] == "Late") & (df["Status"] != "Complete")).sum())
    pct_complete          = round(complete          / total * 100) if total > 0 else 0
    pct_in_progress       = round(in_progress       / total * 100) if total > 0 else 0
    pct_not_started       = round(not_started       / total * 100) if total > 0 else 0
    pct_blocked_escalated = round(blocked_escalated / total * 100) if total > 0 else 0
    return {
        "total": total,
        "complete": complete,
        "in_progress": in_progress,
        "not_started": not_started,
        "blocked_escalated": blocked_escalated,
        "sla_breaches": sla_breaches,
        "pct_complete": pct_complete,
        "pct_in_progress": pct_in_progress,
        "pct_not_started": pct_not_started,
        "pct_blocked_escalated": pct_blocked_escalated,
    }


# ── Metric cards ──────────────────────────────────────────────────────────────

def render_metrics(df: pd.DataFrame, total_task_count: int = 0, bu_task_count: int = 0):
    m = compute_metrics(df)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Total Tasks", m["total"])
    with col2:
        st.metric("Complete", f"{m['complete']} ({m['pct_complete']}%)")
    with col3:
        st.metric("In Progress", f"{m['in_progress']} ({m['pct_in_progress']}%)")
    with col4:
        st.metric("Not Started", f"{m['not_started']} ({m['pct_not_started']}%)")
    with col5:
        st.metric("Blocked/Escalated", f"{m['blocked_escalated']} ({m['pct_blocked_escalated']}%)")
        st.markdown(
            f"<p style='color:{COLOR_ESCALATED}; font-size:12px; margin-top:-12px;"
            f"font-weight:600'>requires attention</p>",
            unsafe_allow_html=True,
        )
    with col6:
        st.metric("SLA Breaches", m["sla_breaches"])
        st.markdown(
            "<p style='color:#F0A500; font-size:12px; margin-top:-12px;"
            "font-weight:600'>past due window</p>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div style='margin: 8px 0 4px 0;'>
            <p style='color:#1B3A6B; font-size:0.875rem; margin-bottom:6px;'>
                Overall close progress: {m['pct_complete']}% complete
            </p>
            <div style='
                background-color: #D6E4F0;
                border-radius: 8px;
                height: 14px;
                width: 100%;
                overflow: hidden;
            '>
                <div style='
                    background-color: #1B3A6B;
                    border-radius: 8px;
                    height: 14px;
                    width: {m['pct_complete']}%;
                '></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Blocked/Escalated count may overlap with status counts above")
    if total_task_count > 0:
        st.caption(
            f"Showing BU-level tasks only ({bu_task_count} of {total_task_count} total tasks)"
        )


# ── BU status bar charts ──────────────────────────────────────────────────────

def build_bu_status_bar(entity_df: pd.DataFrame, entity_name: str):
    """Return a vertical bar chart of task counts by status category, or None if empty."""
    if entity_df.empty:
        return None

    categories = ["Not Started", "In Progress", "Blocked", "Escalated", "Complete"]
    counts = []
    for cat in categories:
        if cat == "Escalated":
            counts.append(int((entity_df["Escalated"] == "Yes").sum()))
        else:
            counts.append(int((entity_df["Status"] == cat).sum()))

    colors = [BAR_COLORS[cat] for cat in categories]

    fig = go.Figure(go.Bar(
        x=categories,
        y=counts,
        marker_color=colors,
        marker_line_width=0,
        text=counts,
        textposition="outside",
        textfont=dict(color=COLOR_PRIMARY, size=12),
        cliponaxis=False,
    ))

    fig.update_layout(
        title=dict(text=entity_name, font=dict(color=COLOR_PRIMARY, size=13), x=0),
        height=280,
        margin=dict(l=4, r=4, t=40, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(
            tickfont=dict(color=COLOR_PRIMARY, size=11),
            tickangle=-20,
            gridcolor="#E8E8E8",
        ),
        yaxis=dict(
            rangemode="tozero",
            tickfont=dict(color=COLOR_PRIMARY, size=11),
            gridcolor="#E8E8E8",
            zeroline=False,
            title=dict(text="Tasks", font=dict(color=COLOR_PRIMARY, size=11)),
        ),
    )
    return fig


def render_bu_charts(df: pd.DataFrame):
    st.markdown(
        f"<h4 style='color:{COLOR_PRIMARY}; margin-top:16px; margin-bottom:4px'>"
        f"Progress Status</h4>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    panels = [
        (col1, "BU001", "BU001 Switzerland"),
        (col2, "BU002", "BU002 Germany"),
        (col3, "BU003", "BU003 Austria"),
        (col4, None,    "DACH Total"),
    ]

    for col, entity_key, label in panels:
        with col:
            subset = df[df["Lowest Org Level Name"] == entity_key] if entity_key else df
            fig = build_bu_status_bar(subset, label)
            if fig is None:
                st.markdown(
                    f"<p style='color:{COLOR_PRIMARY}; font-size:13px; font-weight:600'>{label}</p>",
                    unsafe_allow_html=True,
                )
                st.info("No data for active filters")
            else:
                st.plotly_chart(fig, use_container_width=True)


# ── BU timeline doughnut charts ───────────────────────────────────────────────

def build_bu_timeline_donut(entity_df: pd.DataFrame, entity_name: str):
    """Return a doughnut chart of task counts by Timeline Status, or None if empty."""
    if entity_df.empty:
        return None

    labels = ["On Time", "At Risk", "Late"]
    colors = [TIMELINE_COLORS[l] for l in labels]
    values = [int((entity_df["Timeline Status"] == l).sum()) for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.65,
        marker=dict(colors=colors, line=dict(width=0)),
        textinfo="value",
        textposition="auto",
        insidetextorientation="horizontal",
        textfont=dict(color=COLOR_PRIMARY, size=12),
        showlegend=True,
    ))

    fig.update_layout(
        title=dict(text=entity_name, font=dict(color=COLOR_PRIMARY, size=13), x=0),
        height=250,
        margin=dict(l=4, r=4, t=40, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.15,
            yanchor="top",
            font=dict(color=COLOR_PRIMARY, size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    return fig


def render_bu_donut_charts(df: pd.DataFrame):
    st.markdown(
        f"<h4 style='color:{COLOR_PRIMARY}; margin-top:16px; margin-bottom:4px'>"
        f"Schedule Status</h4>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    panels = [
        (col1, "BU001", "BU001 Switzerland"),
        (col2, "BU002", "BU002 Germany"),
        (col3, "BU003", "BU003 Austria"),
        (col4, None,    "DACH Total"),
    ]

    for col, entity_key, label in panels:
        with col:
            subset = df[df["Lowest Org Level Name"] == entity_key] if entity_key else df
            fig = build_bu_timeline_donut(subset, label)
            if fig is None:
                st.markdown(
                    f"<p style='color:{COLOR_PRIMARY}; font-size:13px; font-weight:600'>{label}</p>",
                    unsafe_allow_html=True,
                )
                st.info("No data for active filters")
            else:
                st.plotly_chart(fig, use_container_width=True)


# ── Owner function bar charts ─────────────────────────────────────────────────

def build_owner_function_bar(entity_df: pd.DataFrame, entity_name: str):
    """Return a bar chart of incomplete task counts by Owner Function, or None if no data."""
    incomplete = entity_df[entity_df["Status"].isin(["In Progress", "Not Started"])]
    if incomplete.empty:
        return None

    counts = (
        incomplete.groupby("Owner Function")
        .size()
        .reset_index(name="count")
        .query("count > 0 and `Owner Function` != ''")
        .sort_values("count", ascending=False)
        .head(3)
    )
    if counts.empty:
        return None

    fig = go.Figure(go.Bar(
        x=counts["Owner Function"],
        y=counts["count"],
        marker_color=COLOR_PRIMARY,
        marker_line_width=0,
        text=counts["count"],
        textposition="outside",
        textfont=dict(color=COLOR_PRIMARY, size=12),
        cliponaxis=False,
    ))

    fig.update_layout(
        title=dict(text=entity_name, font=dict(color=COLOR_PRIMARY, size=13), x=0),
        height=280,
        margin=dict(l=4, r=4, t=40, b=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(
            tickangle=0,
            tickfont=dict(color=COLOR_PRIMARY, size=12),
            gridcolor="#E8E8E8",
            automargin=True,
        ),
        yaxis=dict(
            rangemode="tozero",
            tickfont=dict(color=COLOR_PRIMARY, size=11),
            gridcolor="#E8E8E8",
            zeroline=False,
            title=dict(text="Tasks", font=dict(color=COLOR_PRIMARY, size=11)),
        ),
    )
    return fig


def render_owner_function_charts(df: pd.DataFrame):
    st.markdown(
        f"<h4 style='color:{COLOR_PRIMARY}; margin-top:16px; margin-bottom:4px'>"
        f"Top 3 Owner Functions with Incomplete Tasks</h4>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    panels = [
        (col1, "BU001", "BU001 Switzerland"),
        (col2, "BU002", "BU002 Germany"),
        (col3, "BU003", "BU003 Austria"),
        (col4, None,    "DACH Total"),
    ]

    for col, entity_key, label in panels:
        with col:
            subset = df[df["Lowest Org Level Name"] == entity_key] if entity_key else df
            fig = build_owner_function_bar(subset, label)
            if fig is None:
                st.markdown(
                    f"<p style='color:{COLOR_PRIMARY}; font-size:13px; font-weight:600'>{label}</p>",
                    unsafe_allow_html=True,
                )
                st.info("No incomplete tasks for active filters")
            else:
                st.plotly_chart(fig, use_container_width=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(df: pd.DataFrame):
    st.sidebar.markdown(
        f"<h2 style='color:{COLOR_PRIMARY}; margin-bottom:0'>Helvetia Advisory AG</h2>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        "<p style='color:#666; margin-top:2px'>Month-End Close Manager</p>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()
    active_page = st.sidebar.radio(
        "Navigation",
        options=["Summary", "AI Assistant", "Details"],
        label_visibility="collapsed",
    )
    st.sidebar.divider()
    st.sidebar.markdown(
        f"<p style='color:{COLOR_PRIMARY}; font-weight:700; margin-bottom:4px;'>Filters</p>",
        unsafe_allow_html=True,
    )
    entities = st.sidebar.multiselect(
        "Entity",
        options=BU_ENTITY_KEYS,
        default=[],
        placeholder="All BUs",
    )
    all_phases = [p for p in PHASE_ORDER if p in df["Phase"].unique()]
    phases = st.sidebar.multiselect(
        "Phase",
        options=all_phases,
        default=[],
        placeholder="All phases",
    )
    statuses = st.sidebar.multiselect(
        "Status",
        options=["Not Started", "In Progress", "Complete", "Blocked"],
        default=[],
        placeholder="All statuses",
    )
    timeline_statuses = st.sidebar.multiselect(
        "Timeline Status",
        options=TIMELINE_STATUS_OPTIONS,
        default=[],
        placeholder="All",
    )
    owner_functions = st.sidebar.multiselect(
        "Owner Function",
        options=sorted(df["Owner Function"].replace("", pd.NA).dropna().unique()),
        default=[],
        placeholder="All functions",
    )
    st.sidebar.divider()
    with st.sidebar.expander("About this app"):
        st.write(
            "AI-assisted month-end close manager for Helvetia Advisory AG. "
            "Displays close progress across DACH business units at WD+1, "
            "with exception flagging and AI-powered FP&A analysis."
        )
    return active_page, entities, phases, statuses, timeline_statuses, owner_functions


# ── Filter logic ──────────────────────────────────────────────────────────────

def apply_filters(
    df: pd.DataFrame,
    entities,
    phases,
    statuses,
    timeline_statuses=None,
    owner_functions=None,
) -> pd.DataFrame:
    if entities:
        df = df[df["Lowest Org Level Name"].isin(entities)]
    if phases:
        df = df[df["Phase"].isin(phases)]
    if statuses:
        df = df[df["Status"].isin(statuses)]
    if timeline_statuses:
        df = df[df["Timeline Status"].isin(timeline_statuses)]
    if owner_functions:
        df = df[df["Owner Function"].isin(owner_functions)]
    return df


# ── Three-table section ───────────────────────────────────────────────────────

def render_tables(
    filtered_df: pd.DataFrame,
    full_df: pd.DataFrame,
    phases: list,
    timeline_statuses: list,
):
    # ── Table 1: Blocked and Escalated ────────────────────────────────────────
    st.markdown(
        f"<h3 style='color:{COLOR_ESCALATED}; border-bottom: 2px solid {COLOR_ACCENT}; "
        f"padding-bottom: 4px; margin-top: 24px'>Entity-Level Blocked and Escalated Tasks</h3>",
        unsafe_allow_html=True,
    )

    t1_mask = (filtered_df["Status"] == "Blocked") | (filtered_df["Escalated"] == "Yes")
    t1_df = _sort_by_phase_wd(filtered_df[t1_mask])

    if t1_df.empty:
        st.success("No blocked or escalated tasks")
    else:
        t1_cols = [
            "Working Day", "Task ID", "Task Description", "Organization Level",
            "Country", "Timeline Status", "Completion %", "Priority", "Escalation Role", "Comments",
        ]
        display = _make_display(t1_df, t1_cols)
        display = display.rename(columns={"Escalation Role": "Escalated to"})
        status_values = t1_df["Status"].reset_index(drop=True)
        def style_row_by_index(row):
            status = status_values.iloc[row.name] if row.name < len(status_values) else "Not Started"
            color = STATUS_COLORS.get(status, COLOR_NOT_STARTED)
            return [f"background-color: {color}"] * len(row)
        styled = display.reset_index(drop=True).style.apply(style_row_by_index, axis=1)
        styled = styled.set_table_styles([
            {"selector": "th", "props": [("text-align", "center"), ("background-color", "#1B3A6B"), ("color", "white"), ("font-weight", "600")]}
        ])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Table 2: Close Task Detail ────────────────────────────────────────────
    st.markdown(
        f"<h3 style='color:{COLOR_PRIMARY}; border-bottom: 2px solid {COLOR_ACCENT}; "
        f"padding-bottom: 4px; margin-top: 24px'>Entity-Level Non-Blocked/Escalated Tasks</h3>",
        unsafe_allow_html=True,
    )

    t2_df = _sort_by_phase_wd(filtered_df[~t1_mask])

    if t2_df.empty:
        st.info("No tasks match the current filters.")
    else:
        t2_cols = [c for c in BU_TABLE_COLS if c != "Escalated"]
        display = _make_display(t2_df, t2_cols)
        styled = style_status_rows(display).set_table_styles([
            {"selector": "th", "props": [("text-align", "center"), ("background-color", "#1B3A6B"), ("color", "white"), ("font-weight", "600")]}
        ])
        st.dataframe(styled, use_container_width=True, hide_index=True, height=400)

    # ── Tables 3A/3B/3C: Consolidated View split by level ────────────────────
    consol_df = full_df[full_df["Organization Level"].isin(["Region", "Area", "Global"])].copy()
    if phases:
        consol_df = consol_df[consol_df["Phase"].isin(phases)]
    if timeline_statuses:
        consol_df = consol_df[consol_df["Timeline Status"].isin(timeline_statuses)]
    consol_df = _sort_by_phase_wd(consol_df)
    consol_df = consol_df.rename(columns={"Lowest Org Level Name": "Org Level Name"})

    t3_cols = [
        "Working Day", "Task ID", "Task Description", "Organization Level",
        "Org Level Name", "Status", "Timeline Status", "Completion %", "Priority", "Escalation Role", "Comments",
    ]
    th_styles = [
        {"selector": "th", "props": [("text-align", "center"), ("background-color", "#1B3A6B"), ("color", "white"), ("font-weight", "600")]}
    ]

    for level, header in [
        ("Region", "Consolidation Tasks - Region Level"),
        ("Area",   "Consolidation Tasks - Area Level"),
        ("Global", "Consolidation Tasks - Global Level"),
    ]:
        st.markdown(
            f"<h3 style='color:{COLOR_PRIMARY}; border-bottom: 2px solid {COLOR_ACCENT}; "
            f"padding-bottom: 4px; margin-top: 24px'>{header}</h3>",
            unsafe_allow_html=True,
        )
        sub_df = consol_df[consol_df["Organization Level"] == level].copy()
        if sub_df.empty:
            st.info("No tasks at this level match the active filters.")
        else:
            display = _make_display(sub_df, t3_cols)
            display = display.rename(columns={"Escalation Role": "Escalated to"})
            display["Escalated to"] = display["Escalated to"].where(
                sub_df["Escalated"].reset_index(drop=True) == "Yes", ""
            )
            styled = style_status_rows(display).set_table_styles(th_styles)
            st.dataframe(styled, use_container_width=True, hide_index=True, height=300)


# ── CFO email generation ──────────────────────────────────────────────────────

def generate_cfo_email(bu_df: pd.DataFrame, full_df: pd.DataFrame) -> str:
    # TO ACTIVATE LIVE API: replace string construction below with anthropic client call
    # client = anthropic.Anthropic()
    # response = client.messages.create(model="claude-sonnet-4-20250514", ...)

    today = datetime.now().strftime("%d-%B-%Y")

    total = len(bu_df)
    complete = int((bu_df["Status"] == "Complete").sum())
    blocked_count = int((bu_df["Status"] == "Blocked").sum())
    escalated_count = int((bu_df["Escalated"] == "Yes").sum())
    blocked_escalated_count = int(((bu_df["Status"] == "Blocked") | (bu_df["Escalated"] == "Yes")).sum())
    pct = round(complete / total * 100) if total > 0 else 0

    bu_entities = [
        ("BU001", "Switzerland"),
        ("BU002", "Germany"),
        ("BU003", "Austria"),
    ]
    bu_lines = []
    for key, country in bu_entities:
        sub = bu_df[bu_df["Lowest Org Level Name"] == key]
        sub_total = len(sub)
        sub_complete = int((sub["Status"] == "Complete").sum())
        sub_blocked = int((sub["Status"] == "Blocked").sum())
        sub_escalated = int((sub["Escalated"] == "Yes").sum())
        sub_pct = round(sub_complete / sub_total * 100) if sub_total > 0 else 0
        if sub_blocked == 0 and sub_escalated == 0:
            note = "all tasks on track"
        else:
            parts = []
            if sub_blocked > 0:
                parts.append(f"{sub_blocked} task(s) blocked")
            if sub_escalated > 0:
                parts.append(f"{sub_escalated} task(s) escalated")
            note = ", ".join(parts) + " - requires attention"
        bu_lines.append(f"  - {key} {country}: {sub_pct}% complete - {note}")

    attention_mask = (bu_df["Status"] == "Blocked") | (bu_df["Escalated"] == "Yes")
    attention_df = bu_df[attention_mask].drop_duplicates(subset=["Task ID"])

    attention_lines = []
    for key, country in bu_entities:
        bu_attention = attention_df[attention_df["Lowest Org Level Name"] == key]
        if bu_attention.empty:
            continue
        attention_lines.append(f"  {key} {country}:")
        for _, row in bu_attention.iterrows():
            task_id = str(row.get("Task ID", ""))
            desc = str(row.get("Task Description", ""))
            owner = str(row.get("Task Owner", ""))
            status = str(row.get("Status", ""))
            comment = str(row.get("Comments", "")).strip()[:80]
            line = f"  - {task_id} {desc} (Owner: {owner}) - {status}"
            if comment:
                line += f" - {comment}"
            attention_lines.append(line)

    attention_block = (
        "\n".join(attention_lines) if attention_lines
        else "  No items currently flagged for attention."
    )

    dach_rows = full_df[full_df["Task ID"] == "CL008-REG"]
    if dach_rows.empty:
        dach_status = "Not found"
        dach_comment = ""
    else:
        dach_status = str(dach_rows.iloc[0].get("Status", "Unknown"))
        dach_comment = str(dach_rows.iloc[0].get("Comments", "")).strip()

    dach_line = f"Status: {dach_status}."
    if dach_comment:
        dach_line += f" {dach_comment}"

    if blocked_count > 0 or escalated_count > 0:
        overall = (
            f"The close is currently at risk due to {blocked_escalated_count} task(s) that are blocked or escalated, "
            f"requiring immediate resolution."
        )
        resolution = (
            "Blocked items are under active investigation by the respective task owners. "
            "Resolution is targeted within 4 hours. A further update will be provided "
            "if items remain unresolved by WD+1 12:00."
        )
    else:
        overall = "The close is progressing on schedule with no critical issues outstanding."
        resolution = "No critical blockers outstanding. Close expected to complete on schedule."

    bu_summary = "\n".join(bu_lines)

    return f"""Subject: Month-End Close Status Update | Fiscal Period 2026 P05 | WD+1

To: CFO, Helvetia Advisory AG
From: DACH FP&A Lead
Date: {today}

Dear CFO,

Please find below the WD+1 close status update for Helvetia Advisory AG, Fiscal Period 2026 P05. \
As of this morning, {complete} of {total} BU-level tasks are complete ({pct}%). {overall}

BU STATUS SUMMARY
{bu_summary}

ITEMS REQUIRING ATTENTION
{attention_block}

DACH CONSOLIDATION
Task CL008-REG - {dach_line}

EXPECTED RESOLUTION
{resolution}

Regards,
DACH FP&A Lead
Helvetia Advisory AG"""


# ── Accruals analysis generation ──────────────────────────────────────────────

def generate_accruals_analysis(df: pd.DataFrame) -> str:
    # TO ACTIVATE LIVE API: replace string construction below with anthropic client call
    # client = anthropic.Anthropic()
    # response = client.messages.create(model="claude-sonnet-4-20250514", ...)

    summary_labels = {
        "SUMMARY", "Total Missing Accruals (count)",
        "Estimated Missing Amount (CHF)", "AI Recommendation",
    }
    flagged = df[
        pd.notna(df["AI Flag"])
        & (df["AI Flag"].astype(str).str.strip() != "")
        & (~df["Account Code"].astype(str).isin(summary_labels))
    ].copy()

    lines = ["Suggested Accruals Review - BU001 Switzerland - Period P05", ""]
    for _, row in flagged.iterrows():
        code = str(row.get("Account Code", ""))
        name = str(row.get("Account Name", ""))
        submission = row.get("P05 Submission (CHF)", 0)
        avg = row.get("3M Avg (CHF)", 0)
        variance = row.get("Variance vs Avg (CHF)", 0)
        flag = str(row.get("AI Flag", ""))
        sub_fmt = f"CHF {int(submission):,}" if pd.notna(submission) else "n/a"
        avg_fmt = f"CHF {int(avg):,}" if pd.notna(avg) else "n/a"
        var_fmt = f"CHF {int(variance):,}" if pd.notna(variance) else "n/a"
        lines.append(f"Account {code} - {name}")
        lines.append(f"  P05 Submission: {sub_fmt} | 3M Avg: {avg_fmt} | Variance vs Avg: {var_fmt}")
        lines.append(f"  AI Flag: {flag}")
        lines.append("")

    est_row = df[df["Account Code"].astype(str) == "Estimated Missing Amount (CHF)"]
    rec_row = df[df["Account Code"].astype(str) == "AI Recommendation"]

    if not est_row.empty:
        est_val = est_row.iloc[0]["Account Name"]
        try:
            lines.append(f"TOTAL ESTIMATED MISSING ACCRUALS: CHF {int(float(est_val)):,}")
        except (ValueError, TypeError):
            lines.append(f"TOTAL ESTIMATED MISSING ACCRUALS: {est_val}")

    if not rec_row.empty:
        rec_text = str(rec_row.iloc[0]["Account Name"])
        lines.append(f"\nAI RECOMMENDATION\n{rec_text}")

    return "\n".join(lines)


# ── Variance root cause generation ────────────────────────────────────────────

def generate_variance_analysis(df: pd.DataFrame) -> str:
    # TO ACTIVATE LIVE API: replace string construction below with anthropic client call
    # client = anthropic.Anthropic()
    # response = client.messages.create(model="claude-sonnet-4-20250514", ...)

    breaching = df[df["Threshold Breach"].astype(str).str.contains("YES", na=False)].copy()
    ebit_rows = df[df["P&L Line"].astype(str).str.strip() == "EBIT"]

    lines = ["Variance Root Cause Analysis - DACH Region Consolidated - Period P05", ""]
    lines.append("THRESHOLD BREACH ITEMS")
    lines.append("")

    for _, row in breaching.iterrows():
        pl_line = str(row.get("P&L Line", ""))
        budget = row.get("Budget (CHF)", 0)
        actuals = row.get("Actuals (CHF)", 0)
        variance = row.get("Variance (CHF)", 0)
        var_pct = row.get("Variance %", 0)
        driver = str(row.get("Driver Category", ""))
        breach = str(row.get("Threshold Breach", ""))
        note = str(row.get("AI Root Cause Note", ""))[:120]
        budget_fmt = f"CHF {int(budget):,}" if pd.notna(budget) else "n/a"
        actuals_fmt = f"CHF {int(actuals):,}" if pd.notna(actuals) else "n/a"
        var_fmt = f"CHF {int(variance):,}" if pd.notna(variance) else "n/a"
        try:
            pct_fmt = f"{float(var_pct) * 100:.1f}%"
        except (ValueError, TypeError):
            pct_fmt = "n/a"
        lines.append(f"{pl_line} [{breach}]")
        lines.append(f"  Budget: {budget_fmt} | Actuals: {actuals_fmt} | Variance: {var_fmt} ({pct_fmt})")
        lines.append(f"  Driver: {driver}")
        lines.append(f"  Root Cause: {note}")
        lines.append("")

    if not ebit_rows.empty:
        erow = ebit_rows.iloc[0]
        ebit_var = erow.get("Variance (CHF)", 0)
        ebit_note = str(erow.get("AI Root Cause Note", ""))
        ebit_fmt = f"CHF {int(ebit_var):,}" if pd.notna(ebit_var) else "n/a"
        lines.append("EBIT SUMMARY")
        lines.append(f"  EBIT Variance: {ebit_fmt}")
        lines.append(f"  {ebit_note}")

    return "\n".join(lines)


# ── Missing account checks generation ─────────────────────────────────────────

def generate_missing_accounts(df: pd.DataFrame) -> str:
    # TO ACTIVATE LIVE API: replace string construction below with anthropic client call
    # client = anthropic.Anthropic()
    # response = client.messages.create(model="claude-sonnet-4-20250514", ...)

    flagged = df[df["Zero Balance Flag"].astype(str).str.strip() == "YES"].copy()

    lines = ["Missing Account Checks - BU001 Switzerland - Period P05", ""]
    lines.append(f"FLAGGED ACCOUNTS ({len(flagged)} with unexpected zero balance)")
    lines.append("")

    for _, row in flagged.iterrows():
        code = str(row.get("Account Code", ""))
        name = str(row.get("Account Name", ""))
        p04 = row.get("P04 Balance (CHF)", 0)
        p05 = row.get("P05 Balance (CHF)", 0)
        inv_status = str(row.get("Investigation Status", "")).strip()
        note = str(row.get("AI Note", ""))
        p04_fmt = f"CHF {int(p04):,}" if pd.notna(p04) else "n/a"
        p05_fmt = f"CHF {int(p05):,}" if pd.notna(p05) else "n/a"
        lines.append(f"Account {code} - {name}")
        lines.append(f"  P04 Balance: {p04_fmt} | P05 Balance: {p05_fmt}")
        if inv_status and inv_status != "nan":
            lines.append(f"  Status: {inv_status}")
        lines.append(f"  AI Note: {note}")
        lines.append("")

    summary_labels = {
        "SUMMARY", "Total accounts reviewed", "Accounts with zero balance flag",
        "Accounts expected to post with zero balance", "AI Recommendation",
    }
    summary_rows = df[df["Account Code"].astype(str).isin(summary_labels)]

    if not summary_rows.empty:
        lines.append("SUMMARY")
        for _, row in summary_rows.iterrows():
            label = str(row.get("Account Code", ""))
            val = row.get("Account Name", "")
            if label == "AI Recommendation":
                lines.append(f"\nAI RECOMMENDATION\n{val}")
            elif label != "SUMMARY":
                lines.append(f"  {label}: {val}")

    return "\n".join(lines)


# ── Narrative consistency check generation ────────────────────────────────────

def generate_narrative_check(df: pd.DataFrame) -> str:
    # TO ACTIVATE LIVE API: replace string construction below with anthropic client call
    # client = anthropic.Anthropic()
    # response = client.messages.create(model="claude-sonnet-4-20250514", ...)

    # Section B header at row index 12, data at rows 13-18
    sec_b = df.iloc[13:19].copy()
    sec_b.columns = df.iloc[12].tolist()
    sec_b = sec_b.reset_index(drop=True)

    total = len(sec_b)
    flagged_count = int(
        sec_b["Consistency Status"].astype(str).str.contains("INCONSISTENT", na=False).sum()
    )
    material_count = int(
        sec_b["Consistency Status"].astype(str).str.contains("MATERIAL", na=False).sum()
    )

    lines = ["Narrative Consistency Check - BU001 Switzerland - Period P05", ""]
    lines.append(
        f"REVIEW SUMMARY: {flagged_count} of {total} paragraphs flagged "
        f"({material_count} MATERIAL)"
    )
    lines.append("")

    for _, row in sec_b.iterrows():
        ref = str(row.get("Commentary Ref", ""))
        topic = str(row.get("Topic", ""))
        reported = str(row.get("Reported Figure", ""))[:80]
        stated = str(row.get("Commentary States", ""))
        variance = str(row.get("Variance (CHF)", ""))
        status = str(row.get("Consistency Status", ""))
        flag = str(row.get("AI Flag & Recommendation", ""))[:120]
        lines.append(f"{ref} - {topic}: {status}")
        lines.append(f"  Reported: {reported}")
        lines.append(f"  Commentary states: {stated}")
        if "INCONSISTENT" in status:
            lines.append(f"  Variance: {variance}")
            lines.append(f"  Recommendation: {flag}")
        lines.append("")

    return "\n".join(lines)


# ── Headcount exception detection generation ──────────────────────────────────

def generate_headcount_exceptions(df: pd.DataFrame) -> str:
    # TO ACTIVATE LIVE API: replace string construction below with anthropic client call
    # client = anthropic.Anthropic()
    # response = client.messages.create(model="claude-sonnet-4-20250514", ...)

    exception_rows = df[
        df["AI Exception Flag"].astype(str).str.contains("EXCEPTION|EXIT", na=False)
    ].copy()

    dach_labels = {
        "DACH SUMMARY", "Total DACH headcount plan", "Total DACH actual headcount P0",
        "Net variance vs plan", "Departments with exceptions", "AI Recommendation",
    }
    dach_summary = df[df["Entity"].astype(str).str.contains("DACH SUMMARY|Total DACH|Net variance|Departments with|AI Recommendation", na=False)]

    lines = ["Headcount Exception Detection - DACH Region - Period P05", ""]
    lines.append(f"EXCEPTION ITEMS ({len(exception_rows)} departments with exceptions or exits)")
    lines.append("")

    for _, row in exception_rows.iterrows():
        entity = str(row.get("Entity", ""))
        dept = str(row.get("Department", ""))
        approved = row.get("Approved HC Plan", 0)
        actual = row.get("Actual HC P05", 0)
        variance = row.get("Variance (HC)", 0)
        cost = row.get("Monthly Cost Impact", 0)
        curr = str(row.get("Currency", ""))
        flag = str(row.get("AI Exception Flag", ""))[:100]
        approved_fmt = int(approved) if pd.notna(approved) else "n/a"
        actual_fmt = int(actual) if pd.notna(actual) else "n/a"
        var_fmt = f"{int(variance):+}" if pd.notna(variance) else "n/a"
        cost_fmt = f"{curr} {int(cost):,}" if pd.notna(cost) and cost != 0 else "nil"
        lines.append(f"{entity} - {dept}")
        lines.append(f"  Approved Plan: {approved_fmt} | Actual P05: {actual_fmt} | Variance: {var_fmt}")
        lines.append(f"  Monthly Cost Impact: {cost_fmt}")
        lines.append(f"  Flag: {flag}")
        lines.append("")

    if not dach_summary.empty:
        lines.append("DACH CONSOLIDATED SUMMARY")
        for _, row in dach_summary.iterrows():
            label = str(row.get("Entity", ""))
            val = row.get("Department", "")
            if label == "AI Recommendation":
                lines.append(f"\nAI RECOMMENDATION\n{val}")
            elif label != "DACH SUMMARY":
                lines.append(f"  {label}: {val}")

    return "\n".join(lines) + (
        "\n\nNote: Monthly cost impacts are shown in local functional currency - "
        "CHF for BU001 Switzerland, EUR for BU002 Germany and BU003 Austria. "
        "Values have not been converted to a common reporting currency. "
        "Total DACH cost impact requires FX conversion before aggregation."
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.markdown(
        """
        <!-- Google tag (gtag.js) -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y659LJ7T0D"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){window.dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', 'G-Y659LJ7T0D');
        </script>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
    <style>
    .block-container {
        padding-top: 0 !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    .stApp {
        background-color: #F4F6F8 !important;
    }
    .stButton > button {
        background-color: #8B1A2E !important;
        color: white !important;
        border: none !important;
        border-radius: 4px !important;
    }
    .stButton > button:hover {
        background-color: #6B1422 !important;
        color: white !important;
    }
    textarea[disabled] {
        color: #1a1a1a !important;
        -webkit-text-fill-color: #1a1a1a !important;
        opacity: 1 !important;
    }
    div[data-testid="stMetric"] {
        background-color: white !important;
        border-left: 4px solid #1B3A6B !important;
        border-top: 1px solid #DEE2E6 !important;
        border-right: 1px solid #DEE2E6 !important;
        border-bottom: 1px solid #DEE2E6 !important;
        border-radius: 0 8px 8px 0 !important;
        padding: 16px !important;
        box-shadow: 0 2px 8px rgba(27, 58, 107, 0.08) !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #6B7280 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    div[data-testid="stMetricValue"] {
        color: #1B3A6B !important;
        font-weight: 700 !important;
    }
    div[data-testid="stDataFrame"] {
        border-radius: 12px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 8px rgba(27, 58, 107, 0.08) !important;
    }
    div[data-testid="stPlotlyChart"] {
        background-color: white !important;
        border-radius: 12px !important;
        padding: 8px !important;
        box-shadow: 0 2px 8px rgba(27, 58, 107, 0.08) !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #EBF0F7 !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    img_b64 = get_image_base64("Banner.jpg")
    st.markdown(
        f"""
    <div style='
        position: relative;
        margin: -1rem -1rem 24px -1rem;
        overflow: hidden;
    '>
        <img src='data:image/jpeg;base64,{img_b64}'
             style='width:100%; display:block; max-height:200px; object-fit:cover; object-position:center;'/>
        <div style='
            position:absolute;
            bottom:0;
            left:0;
            right:0;
            padding:16px 28px 14px 28px;
            background:rgba(0,0,0,0.6);
        '>
            <h1 style='
                color:white;
                margin:0;
                font-size:1.6rem;
                font-weight:700;
                letter-spacing:-0.3px;
            '>Helvetia Advisory AG - Month-End Close Manager</h1>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    df = load_task_master()

    active_page, entities, phases, statuses, timeline_statuses, owner_functions = render_sidebar(df)

    bu_df = df[df["Organization Level"] == "BU"].copy()
    now = datetime.now()
    filtered = apply_filters(bu_df, entities, phases, statuses, timeline_statuses, owner_functions)

    if active_page == "AI Assistant":
        subtitle = "AI-Powered FP&A Analysis | Fiscal Period 2026 P05 | As of WD+1"
        st.markdown(
            f"<p style='color:{COLOR_PRIMARY}; margin:0 0 20px 0; font-size:1rem; "
            f"font-weight:500; letter-spacing:0.3px;'>{subtitle}</p>",
            unsafe_allow_html=True,
        )
        render_disclaimer()
        st.markdown(
            """
            <div style='background:#EEF2F7; border-left:3px solid #4ECDC4; color:#6B7280;
                        font-size:0.8rem; padding:8px 16px; border-radius:4px; margin-bottom:16px;'>
                Analysis scope: BU001 Switzerland and DACH Region | Fiscal Period 2026 P05 | Snapshot WD+1
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <style>
            .streamlit-expanderHeader {
                border: 1px solid #DEE2E6 !important;
                border-radius: 8px !important;
                background-color: white !important;
            }
            .streamlit-expanderContent {
                border: 1px solid #DEE2E6 !important;
                border-top: none !important;
                border-radius: 0 0 8px 8px !important;
                background-color: white !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        row1_col1, row1_col2, row1_col3 = st.columns(3)
        row2_col1, row2_col2, row2_col3 = st.columns(3)

        with row1_col1:
            st.markdown(
                f"<p style='color:{COLOR_PRIMARY}; font-weight:700; margin-bottom:2px'>"
                f"CFO Status Email</p>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Generates a structured close status email to the CFO covering "
                "BU progress, blocked items, and escalation risk."
            )
            if st.button("Generate CFO Status Email", use_container_width=True):
                st.session_state["cfo_email"] = generate_cfo_email(bu_df, df)
            with st.expander(
                "CFO Email Draft",
                expanded=bool(st.session_state.get("cfo_email")),
            ):
                st.code(st.session_state.get("cfo_email", ""), language=None)
                st.caption("Review and copy to your email client")

        with row1_col2:
            st.markdown(
                f"<p style='color:{COLOR_PRIMARY}; font-weight:700; margin-bottom:2px'>"
                f"Suggested Accruals</p>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Compares prior 3-month posting averages against current submissions "
                "to flag missing or anomalous accrual entries."
            )
            if st.button("Suggested Accruals", use_container_width=True):
                df_acc = pd.read_excel(
                    "data/Helvetia_AG_AI_Synthetic_Datasets.xlsx",
                    sheet_name="Suggested Accruals",
                    header=2,
                )
                st.session_state["accruals_output"] = generate_accruals_analysis(df_acc)
            with st.expander(
                "Suggested Accruals Analysis",
                expanded=bool(st.session_state.get("accruals_output")),
            ):
                st.code(st.session_state.get("accruals_output", ""), language=None)

        with row1_col3:
            st.markdown(
                f"<p style='color:{COLOR_PRIMARY}; font-weight:700; margin-bottom:2px'>"
                f"Variance Root Cause</p>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Identifies P&L lines exceeding variance thresholds and suggests "
                "probable root causes by driver category."
            )
            if st.button("Variance Root Cause", use_container_width=True):
                df_var = pd.read_excel(
                    "data/Helvetia_AG_AI_Synthetic_Datasets.xlsx",
                    sheet_name="Variance Root Cause",
                    header=2,
                )
                st.session_state["variance_output"] = generate_variance_analysis(df_var)
            with st.expander(
                "Variance Root Cause Analysis",
                expanded=bool(st.session_state.get("variance_output")),
            ):
                st.code(st.session_state.get("variance_output", ""), language=None)

        with row2_col1:
            st.markdown(
                f"<p style='color:{COLOR_PRIMARY}; font-weight:700; margin-bottom:2px'>"
                f"Missing Account Checks</p>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Flags accounts expected to post each period that carry an unexpected "
                "zero balance in the current period."
            )
            if st.button("Missing Account Checks", use_container_width=True):
                df_mac = pd.read_excel(
                    "data/Helvetia_AG_AI_Synthetic_Datasets.xlsx",
                    sheet_name="Missing Account Checks",
                    header=2,
                )
                st.session_state["missing_accounts_output"] = generate_missing_accounts(df_mac)
            with st.expander(
                "Missing Account Checks",
                expanded=bool(st.session_state.get("missing_accounts_output")),
            ):
                st.code(st.session_state.get("missing_accounts_output", ""), language=None)

        with row2_col2:
            st.markdown(
                f"<p style='color:{COLOR_PRIMARY}; font-weight:700; margin-bottom:2px'>"
                f"Narrative Consistency</p>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Compares draft commentary against reported variance data and flags "
                "paragraphs where the narrative understates or misattributes variance."
            )
            if st.button("Narrative Consistency", use_container_width=True):
                df_narr = pd.read_excel(
                    "data/Helvetia_AG_AI_Synthetic_Datasets.xlsx",
                    sheet_name="Narrative Consistency Check",
                    header=None,
                )
                st.session_state["narrative_output"] = generate_narrative_check(df_narr)
            with st.expander(
                "Narrative Consistency Check",
                expanded=bool(st.session_state.get("narrative_output")),
            ):
                st.code(st.session_state.get("narrative_output", ""), language=None)

        with row2_col3:
            st.markdown(
                f"<p style='color:{COLOR_PRIMARY}; font-weight:700; margin-bottom:2px'>"
                f"Headcount Exceptions</p>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Compares approved headcount plan against actuals by department and "
                "flags movements outside plan with monthly cost impact."
            )
            if st.button("Headcount Exceptions", use_container_width=True):
                df_hc = pd.read_excel(
                    "data/Helvetia_AG_AI_Synthetic_Datasets.xlsx",
                    sheet_name="Headcount Exception Detection",
                    header=2,
                )
                st.session_state["headcount_output"] = generate_headcount_exceptions(df_hc)
            with st.expander(
                "Headcount Exception Detection",
                expanded=bool(st.session_state.get("headcount_output")),
            ):
                st.code(st.session_state.get("headcount_output", ""), language=None)

    else:
        subtitle = (
            f"Month-End Close Snapshot | Fiscal Period 2026 P05 | "
            f"As of WD+1, {now.strftime('%d-%B-%Y %H:%M')}"
        )
        st.markdown(
            f"<p style='color:{COLOR_PRIMARY}; margin:0 0 20px 0; font-size:1rem; "
            f"font-weight:500; letter-spacing:0.3px;'>{subtitle}</p>",
            unsafe_allow_html=True,
        )
        render_disclaimer()

        if active_page == "Summary":
            render_rag_indicator(filtered)
            render_metrics(filtered, total_task_count=len(df), bu_task_count=len(bu_df))
            render_bu_charts(filtered)
            render_bu_donut_charts(filtered)
            render_owner_function_charts(filtered)

        else:
            render_tables(filtered, df, phases, timeline_statuses)


if __name__ == "__main__":
    main()
else:
    main()
