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
COLOR_COMPLETE    = "#E2EFDA"
COLOR_IN_PROGRESS = "#FFF2CC"
COLOR_BLOCKED     = "#FFCCCC"
COLOR_NOT_STARTED = "#F2F2F2"
COLOR_ESCALATED   = "#FF0000"
COLOR_PRIMARY     = "#1F4E79"
COLOR_SECONDARY   = "#2E75B6"
COLOR_ACCENT      = "#D6E4F0"

STATUS_COLORS = {
    "Complete":    COLOR_COMPLETE,
    "In Progress": COLOR_IN_PROGRESS,
    "Blocked":     COLOR_BLOCKED,
    "Not Started": COLOR_NOT_STARTED,
}

BAR_COLORS = {
    "Not Started": "#C8C8C8",
    "In Progress": "#F5C842",
    "Blocked":     "#E06060",
    "Escalated":   COLOR_ESCALATED,
    "Complete":    "#6DB87A",
}

TIMELINE_COLORS = {
    "On Time": "#4CAF50",
    "At Risk":  "#F6AE2D",
    "Late":     "#E84855",
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
    for col in ["Comments", "Escalated", "Status", "Phase", "Lowest Org Level Name", "Owner Function"]:
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


# ── Dashboard calculations ────────────────────────────────────────────────────

def compute_metrics(df: pd.DataFrame) -> dict:
    total = len(df)
    complete = int((df["Status"] == "Complete").sum())
    in_progress = int((df["Status"] == "In Progress").sum())
    not_started = int((df["Status"] == "Not Started").sum())
    blocked_escalated = int(((df["Status"] == "Blocked") | (df["Escalated"] == "Yes")).sum())
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
        "pct_complete": pct_complete,
        "pct_in_progress": pct_in_progress,
        "pct_not_started": pct_not_started,
        "pct_blocked_escalated": pct_blocked_escalated,
    }


# ── Metric cards ──────────────────────────────────────────────────────────────

def render_metrics(df: pd.DataFrame, total_task_count: int = 0, bu_task_count: int = 0):
    m = compute_metrics(df)

    col1, col2, col3, col4, col5 = st.columns(5)
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

    st.progress(
        m["pct_complete"] / 100,
        text=f"Overall close progress: {m['pct_complete']}% complete",
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
        f"Task Status by Business Unit</h4>",
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
        f"Completion Status by Business Unit</h4>",
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
        margin=dict(l=4, r=4, t=40, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(
            tickangle=0,
            tickfont=dict(color=COLOR_PRIMARY, size=12),
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

def render_sidebar():
    st.sidebar.markdown(
        f"<h2 style='color:{COLOR_PRIMARY}; margin-bottom:0'>Helvetia Advisory AG</h2>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        "<p style='color:#666; margin-top:2px'>Month-End Close Manager</p>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()
    with st.sidebar.expander("About this app"):
        st.write(
            "AI-assisted month-end close manager for Helvetia Advisory AG. "
            "Displays close progress across DACH business units at WD+1, "
            "with exception flagging and AI-powered FP&A analysis."
        )


# ── Filter panel ──────────────────────────────────────────────────────────────

def render_filters(df: pd.DataFrame):
    st.markdown(
        f"<h4 style='color:{COLOR_PRIMARY}; margin-top:0; margin-bottom:8px'>Filters</h4>",
        unsafe_allow_html=True,
    )

    entities = st.multiselect(
        "Entity",
        options=BU_ENTITY_KEYS,
        default=[],
        placeholder="All BUs",
    )

    all_phases = [p for p in PHASE_ORDER if p in df["Phase"].unique()]
    phases = st.multiselect(
        "Phase",
        options=all_phases,
        default=[],
        placeholder="All phases",
    )

    statuses = st.multiselect(
        "Status",
        options=["Not Started", "In Progress", "Complete", "Blocked"],
        default=[],
        placeholder="All statuses",
    )

    timeline_statuses = st.multiselect(
        "Timeline Status",
        options=TIMELINE_STATUS_OPTIONS,
        default=[],
        placeholder="All",
    )

    owner_functions = st.multiselect(
        "Owner Function",
        options=sorted(df["Owner Function"].replace("", pd.NA).dropna().unique()),
        default=[],
        placeholder="All functions",
    )

    return entities, phases, statuses, timeline_statuses, owner_functions


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
        f"padding-bottom: 4px; margin-top: 24px'>Blocked and Escalated Tasks</h3>",
        unsafe_allow_html=True,
    )

    t1_mask = (filtered_df["Status"] == "Blocked") | (filtered_df["Escalated"] == "Yes")
    t1_df = _sort_by_phase_wd(filtered_df[t1_mask])

    if t1_df.empty:
        st.success("No blocked or escalated tasks")
    else:
        display = _make_display(t1_df, BU_TABLE_COLS)
        st.dataframe(
            style_status_rows(display),
            use_container_width=True,
            hide_index=True,
        )

    # ── Table 2: Close Task Detail ────────────────────────────────────────────
    st.markdown(
        f"<h3 style='color:{COLOR_PRIMARY}; border-bottom: 2px solid {COLOR_ACCENT}; "
        f"padding-bottom: 4px; margin-top: 24px'>BU-Level Non-Blocked/Escalated Tasks</h3>",
        unsafe_allow_html=True,
    )

    t2_df = _sort_by_phase_wd(filtered_df[~t1_mask])

    if t2_df.empty:
        st.info("No tasks match the current filters.")
    else:
        display = _make_display(t2_df, BU_TABLE_COLS)
        st.dataframe(
            style_status_rows(display),
            use_container_width=True,
            hide_index=True,
            height=400,
        )

    # ── Table 3: Consolidated View ────────────────────────────────────────────
    st.markdown(
        f"<h3 style='color:{COLOR_PRIMARY}; border-bottom: 2px solid {COLOR_ACCENT}; "
        f"padding-bottom: 4px; margin-top: 24px'>Consolidated-Level Tasks</h3>",
        unsafe_allow_html=True,
    )

    consol_df = full_df[full_df["Organization Level"].isin(["Region", "Area", "Global"])].copy()
    if phases:
        consol_df = consol_df[consol_df["Phase"].isin(phases)]
    if timeline_statuses:
        consol_df = consol_df[consol_df["Timeline Status"].isin(timeline_statuses)]
    consol_df = _sort_by_phase_wd(consol_df)
    consol_df = consol_df.rename(columns={"Lowest Org Level Name": "Org Level Name"})

    if consol_df.empty:
        st.info("No consolidated tasks match the active filters.")
    else:
        display = _make_display(consol_df, CONSOLIDATED_TABLE_COLS)
        st.dataframe(
            style_status_rows(display),
            use_container_width=True,
            hide_index=True,
            height=400,
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.markdown(
        """
    <style>
    .block-container {
        padding-top: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
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

    render_sidebar()

    content_col, filter_col = st.columns([4, 1])

    with filter_col:
        entities, phases, statuses, timeline_statuses, owner_functions = render_filters(df)

    bu_df = df[df["Organization Level"] == "BU"].copy()
    filtered = apply_filters(bu_df, entities, phases, statuses, timeline_statuses, owner_functions)

    with content_col:
        now = datetime.now()
        subtitle = f"Month-End Close Snapshot | Fiscal Period 2026 P05 | As of WD+1, {now.strftime('%d-%B-%Y %H:%M')}"
        st.markdown(
            f"<p style='color:{COLOR_PRIMARY}; margin:0 0 20px 0; font-size:1rem; "
            f"font-weight:500; letter-spacing:0.3px;'>{subtitle}</p>",
            unsafe_allow_html=True,
        )
        render_metrics(filtered, total_task_count=len(df), bu_task_count=len(bu_df))
        render_bu_charts(filtered)
        render_bu_donut_charts(filtered)
        render_owner_function_charts(filtered)
        st.markdown("---")
        render_tables(filtered, df, phases, timeline_statuses)


if __name__ == "__main__":
    main()
else:
    main()
