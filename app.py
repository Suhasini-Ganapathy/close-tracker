import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pandas.io.formats.style import Styler

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

PHASE_ORDER = ["Pre-Close", "Close", "Close-to-Post-Close", "Post-Close"]

ENTITY_ORDER = ["BU001", "BU002", "BU003", "DACH", "EMEA", "Global"]

ENTITY_DISPLAY = {
    "BU001":  "BU001 Switzerland",
    "BU002":  "BU002 Germany",
    "BU003":  "BU003 Austria",
    "DACH":   "DACH Region",
    "EMEA":   "EMEA Area",
    "Global": "Global",
}

BU_ORG_LEVELS            = ["BU"]
CONSOLIDATED_ORG_LEVELS  = ["Region", "Area", "Global"]
BU_ENTITY_KEYS           = ["BU001", "BU002", "BU003"]
CONSOLIDATED_ENTITY_KEYS = ["DACH", "EMEA", "Global"]

BU_DISPLAY_COLS = [
    "Working Day", "Task ID", "Task Description", "Organization Level",
    "Country", "Status", "Completion %", "Priority", "Escalated", "Comments",
]

CONSOLIDATED_DISPLAY_COLS = [
    "Working Day", "Task ID", "Task Description", "Organization Level",
    "Lowest Org Level Name", "Status", "Completion %", "Priority", "Escalated", "Comments",
]

st.set_page_config(
    page_title="Helvetia Advisory AG - Month-End Close Manager",
    layout="wide",
)


# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data
def load_task_master() -> pd.DataFrame:
    df = pd.read_excel(
        "data/FPnAMonth-EndCloseWorkflow.xlsx",
        sheet_name="Task Master",
    )
    # Fix typo in source data so the rest of the app uses the correct name
    df = df.rename(columns={"Completon %": "Completion %"})
    # Normalise text columns to avoid NaN display issues
    for col in ["Comments", "Escalated", "Status", "Phase", "Lowest Org Level Name"]:
        if col in df.columns:
            df[col] = df[col].fillna("")
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


# ── Dashboard calculations ────────────────────────────────────────────────────

def compute_metrics(df: pd.DataFrame) -> dict:
    total = len(df)
    complete = int((df["Status"] == "Complete").sum())
    in_progress = int((df["Status"] == "In Progress").sum())
    blocked     = int((df["Status"] == "Blocked").sum())
    not_started = int((df["Status"] == "Not Started").sum())
    escalated   = int((df["Escalated"] == "Yes").sum())
    pct_complete    = round(complete    / total * 100, 1) if total > 0 else 0.0
    pct_in_progress = round(in_progress / total * 100)   if total > 0 else 0
    pct_blocked     = round(blocked     / total * 100)   if total > 0 else 0
    pct_not_started = round(not_started / total * 100)   if total > 0 else 0
    pct_escalated   = round(escalated   / total * 100)   if total > 0 else 0
    return {
        "total": total,
        "complete": complete,
        "in_progress": in_progress,
        "blocked": blocked,
        "not_started": not_started,
        "escalated": escalated,
        "pct_complete": pct_complete,
        "pct_in_progress": pct_in_progress,
        "pct_blocked": pct_blocked,
        "pct_not_started": pct_not_started,
        "pct_escalated": pct_escalated,
    }


def build_entity_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key in ENTITY_ORDER:
        subset = df[df["Lowest Org Level Name"] == key]
        total = len(subset)
        complete = int((subset["Status"] == "Complete").sum())
        in_progress = int((subset["Status"] == "In Progress").sum())
        blocked = int((subset["Status"] == "Blocked").sum())
        not_started = int((subset["Status"] == "Not Started").sum())
        pct = round(complete / total * 100, 1) if total > 0 else 0.0
        rows.append({
            "Entity": ENTITY_DISPLAY[key],
            "Total": total,
            "Complete": complete,
            "In Progress": in_progress,
            "Blocked": blocked,
            "Not Started": not_started,
            "Completion %": pct,
        })
    return pd.DataFrame(rows)


def style_entity_table(entity_df: pd.DataFrame) -> Styler:
    def color_pct(val):
        if val > 70:
            return f"background-color: {COLOR_COMPLETE}"
        elif val >= 30:
            return f"background-color: {COLOR_IN_PROGRESS}"
        else:
            return f"background-color: {COLOR_BLOCKED}"

    return entity_df.style.map(color_pct, subset=["Completion %"])


def build_entity_chart(entity_df: pd.DataFrame) -> go.Figure:
    # Reverse so BU001 appears at top (Plotly draws first row at bottom)
    chart_df = entity_df.iloc[::-1].reset_index(drop=True)

    colors = []
    for val in chart_df["Completion %"]:
        if val > 70:
            colors.append(COLOR_COMPLETE)
        elif val >= 30:
            colors.append(COLOR_IN_PROGRESS)
        else:
            colors.append(COLOR_BLOCKED)

    fig = go.Figure(go.Bar(
        orientation="h",
        y=chart_df["Entity"],
        x=chart_df["Completion %"],
        marker_color=colors,
        marker_line_width=0,
        text=[f"{v:.1f}%" for v in chart_df["Completion %"]],
        textposition="outside",
        textfont=dict(color=COLOR_PRIMARY, size=12),
        cliponaxis=False,
        showlegend=False,
    ))

    for label, color in [
        ("Above 70% - On Track",        COLOR_COMPLETE),
        ("30-70% - At Risk",            COLOR_IN_PROGRESS),
        ("Below 30% - Behind Schedule", COLOR_BLOCKED),
    ]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(color=color, size=10, symbol="square"),
            name=label,
            showlegend=True,
        ))

    fig.update_layout(
        title=dict(text=""),
        height=320,
        margin=dict(l=0, r=60, t=8, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(
            orientation="h",
            x=0,
            y=-0.18,
            xanchor="left",
            yanchor="top",
            font=dict(color=COLOR_PRIMARY, size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            range=[0, 100],
            tickvals=[0, 25, 50, 75, 100],
            ticksuffix="%",
            tickfont=dict(color=COLOR_PRIMARY),
            gridcolor="#E8E8E8",
            zeroline=False,
        ),
        yaxis=dict(
            tickfont=dict(color=COLOR_PRIMARY, size=12),
            automargin=True,
        ),
    )
    return fig


def build_bu_stacked_chart(df: pd.DataFrame) -> go.Figure:
    # Reverse so BU001 appears at top
    bu_labels = [ENTITY_DISPLAY[k] for k in reversed(BU_ENTITY_KEYS)]

    status_segments = [
        ("Complete",    COLOR_COMPLETE),
        ("In Progress", COLOR_IN_PROGRESS),
        ("Blocked",     COLOR_BLOCKED),
        ("Not Started", COLOR_NOT_STARTED),
    ]

    traces = []
    for status_name, color in status_segments:
        counts = []
        texts = []
        for key in reversed(BU_ENTITY_KEYS):
            subset = df[df["Lowest Org Level Name"] == key]
            count = int((subset["Status"] == status_name).sum())
            counts.append(count)
            texts.append(str(count) if count > 0 else "")
        traces.append(go.Bar(
            name=status_name,
            orientation="h",
            y=bu_labels,
            x=counts,
            marker_color=color,
            marker_line_width=0,
            text=texts,
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color=COLOR_PRIMARY, size=11),
        ))

    bu_totals = [len(df[df["Lowest Org Level Name"] == k]) for k in BU_ENTITY_KEYS]
    max_total = max(bu_totals) if any(t > 0 for t in bu_totals) else 29

    fig = go.Figure(data=traces)
    fig.update_layout(
        barmode="stack",
        height=240,
        margin=dict(l=0, r=20, t=8, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(
            orientation="h",
            x=0,
            y=-0.18,
            xanchor="left",
            yanchor="top",
            font=dict(color=COLOR_PRIMARY, size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            range=[0, max_total],
            tickfont=dict(color=COLOR_PRIMARY),
            gridcolor="#E8E8E8",
            zeroline=False,
            title=dict(text="Tasks", font=dict(color=COLOR_PRIMARY, size=11)),
        ),
        yaxis=dict(
            tickfont=dict(color=COLOR_PRIMARY, size=12),
            automargin=True,
        ),
    )
    return fig


# ── Dashboard rendering ───────────────────────────────────────────────────────

def render_dashboard(df: pd.DataFrame, view: str = "BU View"):
    m = compute_metrics(df)

    # Metric cards
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Total Tasks", m["total"])
    with col2:
        st.metric("Complete", f"{m['complete']} ({m['pct_complete']:.0f}%)")
    with col3:
        st.metric("In Progress", f"{m['in_progress']} ({m['pct_in_progress']}%)")
    with col4:
        st.metric("Not Started", f"{m['not_started']} ({m['pct_not_started']}%)")
    with col5:
        st.metric("Blocked", f"{m['blocked']} ({m['pct_blocked']}%)")
        st.markdown(
            f"<p style='color:{COLOR_ESCALATED}; font-size:12px; margin-top:-12px;"
            f"font-weight:600'>requires attention</p>",
            unsafe_allow_html=True,
        )
    with col6:
        st.metric("Escalated", f"{m['escalated']} ({m['pct_escalated']}%)")
        st.markdown(
            "<p style='color:#F0A500; font-size:12px; margin-top:-12px;"
            "font-weight:600'>active alerts</p>",
            unsafe_allow_html=True,
        )

    # Progress bar
    st.progress(
        m["pct_complete"] / 100,
        text=f"Overall close progress: {m['pct_complete']:.1f}% complete",
    )

    # Per-entity completion table
    st.markdown(
        f"<h4 style='color:{COLOR_PRIMARY}; margin-top:16px; margin-bottom:4px'>"
        f"Completion by Entity</h4>",
        unsafe_allow_html=True,
    )
    if view == "BU View":
        st.plotly_chart(build_bu_stacked_chart(df), use_container_width=True)
    else:
        entity_df = build_entity_table(df)
        visible = entity_df[entity_df["Total"] > 0]
        st.plotly_chart(build_entity_chart(visible), use_container_width=True)

    st.markdown("---")


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

    view = st.sidebar.radio("View", ["BU View", "Consolidated View"], index=0)

    st.sidebar.divider()
    st.sidebar.subheader("Filters")

    entity_options = BU_ENTITY_KEYS if view == "BU View" else CONSOLIDATED_ENTITY_KEYS
    entities = st.sidebar.multiselect(
        "Entity",
        options=entity_options,
        default=[],
        placeholder="All entities",
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

    st.sidebar.divider()
    with st.sidebar.expander("About this app"):
        st.write(
            "AI-assisted month-end close manager for Helvetia Advisory AG. "
            "Displays close progress across DACH business units at WD+1, "
            "with exception flagging and AI-powered FP&A analysis."
        )

    return view, entities, phases, statuses


# ── Filter logic ──────────────────────────────────────────────────────────────

def apply_filters(df: pd.DataFrame, entities, phases, statuses) -> pd.DataFrame:
    if entities:
        df = df[df["Lowest Org Level Name"].isin(entities)]
    if phases:
        df = df[df["Phase"].isin(phases)]
    if statuses:
        df = df[df["Status"].isin(statuses)]
    return df


# ── Task list ─────────────────────────────────────────────────────────────────

def render_task_list(df: pd.DataFrame, view: str = "BU View"):
    if df.empty:
        st.info("No tasks match the current filters.")
        return

    cols = BU_DISPLAY_COLS if view == "BU View" else CONSOLIDATED_DISPLAY_COLS

    for phase in PHASE_ORDER:
        group = df[df["Phase"] == phase].copy()
        if group.empty:
            continue

        # Sort by Working Day numerically within the phase
        group["_wd_sort"] = group["Working Day"].apply(wd_to_int)
        group = group.sort_values("_wd_sort").drop(columns=["_wd_sort"])

        # Build display slice with only the required columns
        display = group[[c for c in cols if c in group.columns]].copy()

        if view == "Consolidated View":
            display = display.rename(columns={"Lowest Org Level Name": "Org Level Name"})

        # Replace Escalated Yes/No with badge text
        display["Escalated"] = display["Escalated"].apply(
            lambda v: "ESCALATED" if str(v).strip() == "Yes" else ""
        )

        st.markdown(
            f"<h3 style='color:{COLOR_PRIMARY}; border-bottom: 2px solid {COLOR_ACCENT}; "
            f"padding-bottom: 4px; margin-top: 24px'>{phase}</h3>",
            unsafe_allow_html=True,
        )

        styled = style_status_rows(display)
        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.markdown(
        f"<h1 style='color:{COLOR_PRIMARY}'>Helvetia Advisory AG - Month-End Close Manager</h1>",
        unsafe_allow_html=True,
    )
    st.caption("FP&A Close Tracker | Fiscal Period 2026 P05 | Snapshot: WD+1")

    df = load_task_master()

    view, entities, phases, statuses = render_sidebar(df)

    org_levels = BU_ORG_LEVELS if view == "BU View" else CONSOLIDATED_ORG_LEVELS
    view_df = df[df["Organization Level"].fillna("").isin(org_levels)].copy()

    filtered = apply_filters(view_df, entities, phases, statuses)

    render_dashboard(filtered, view)
    render_task_list(filtered, view)


if __name__ == "__main__":
    main()
else:
    main()
