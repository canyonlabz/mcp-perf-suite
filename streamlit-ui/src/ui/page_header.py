"""
Shared page header component rendered at the top of every page.

Layout: [Logo] [Tab Navigation Links] [Session Controls]
Follows the llm-perf-studio pattern with st.page_link() for tab-style nav.
"""

import os
import streamlit as st

from src.ui.page_styles import inject_page_header_styles


def render_page_header():
    """Render the shared header with logo, navigation tabs, and session controls."""
    inject_page_header_styles()

    col_logo, col_nav, col_controls = st.columns([0.12, 0.68, 0.20])

    with col_logo:
        st.markdown(
            "<div style='font-size: 1.4rem; font-weight: 700; color: #5a9bc7; "
            "padding-top: 6px;'>MCP Suite</div>",
            unsafe_allow_html=True,
        )

    with col_nav:
        tab_cols = st.columns([0.18, 0.22, 0.25, 0.22, 0.13], border=False)

        with tab_cols[0]:
            st.page_link("nav_pages/page_homepage.py", label="Home", icon=":material/home:")

        with tab_cols[1]:
            st.page_link("nav_pages/page_config_editor.py", label="Config Editor", icon=":material/settings:")

        with tab_cols[2]:
            st.page_link("nav_pages/page_config_migrate.py", label="Config Migration", icon=":material/sync:")

        with tab_cols[3]:
            st.page_link("nav_pages/page_kpi_dashboard.py", label="KPI Dashboard", icon=":material/monitoring:")

    with col_controls:
        ctrl_col1, ctrl_col2 = st.columns([0.5, 0.5], border=False)

        with ctrl_col1:
            if st.button("Clear Session", key="clear_session"):
                st.session_state.clear()
                st.rerun()

        with ctrl_col2:
            if st.button("Exit App", key="exit_app"):
                st.write("Goodbye!")
                os._exit(0)

    st.divider()
