from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """Apply the PARKWISE visual system in one place."""
    st.markdown(
        """
        <style>
        :root {
          --pw-bg: #05080d;
          --pw-surface: #0b1320;
          --pw-soft: #101b2b;
          --pw-border: rgba(140,170,200,.18);
          --pw-text: #f5f7fb;
          --pw-muted: #8fa1b8;
          --pw-cyan: #22d3ee;
          --pw-blue: #3b82f6;
          --pw-green: #34d399;
          --pw-purple: #c084fc;
          --pw-yellow: #facc15;
        }
        [data-testid="stAppViewContainer"] { background: var(--pw-bg); }
        [data-testid="stHeader"] { background: rgba(5,8,13,.86); }
        [data-testid="stSidebar"] { background: #070c14; border-right: 1px solid var(--pw-border); }
        [data-testid="stSidebar"] hr { border-color: var(--pw-border); }
        .block-container { max-width: 1480px; padding-top: 2rem; padding-bottom: 3rem; }
        h1, h2, h3 { letter-spacing: -.035em; }
        h1 { font-weight: 800; }
        [data-testid="stMetric"] {
          background: linear-gradient(145deg, rgba(16,27,43,.95), rgba(11,19,32,.95));
          border: 1px solid var(--pw-border); border-radius: 18px; padding: 1rem 1.1rem;
          box-shadow: 0 16px 40px rgba(0,0,0,.18);
        }
        [data-testid="stMetricLabel"] { color: var(--pw-muted); text-transform: uppercase; letter-spacing: .1em; font-size: .68rem; }
        [data-testid="stMetricValue"] { color: var(--pw-text); }
        [data-testid="stMetricDelta"] { color: var(--pw-green); }
        [data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--pw-border); border-radius: 18px; background: rgba(11,19,32,.64); }
        .pw-eyebrow { color: var(--pw-cyan); font-size: .72rem; font-weight: 750; letter-spacing: .16em; text-transform: uppercase; margin-bottom: .35rem; }
        .pw-hero { font-size: clamp(2rem, 4vw, 3.6rem); line-height: 1.02; font-weight: 850; margin: 0 0 .7rem; color: var(--pw-text); }
        .pw-hero span { color: var(--pw-cyan); }
        .pw-subtitle { color: var(--pw-muted); font-size: 1rem; max-width: 760px; line-height: 1.65; }
        .pw-card-title { color: var(--pw-text); font-weight: 750; font-size: 1.1rem; }
        .pw-muted { color: var(--pw-muted); }
        .pw-status { display: inline-block; border: 1px solid rgba(52,211,153,.32); color: var(--pw-green); background: rgba(52,211,153,.1); border-radius: 999px; padding: .22rem .55rem; font-size: .7rem; font-weight: 750; letter-spacing: .08em; }
        .pw-demo { border: 1px solid rgba(250,204,21,.25); background: rgba(250,204,21,.08); color: #fde68a; border-radius: 16px; padding: .8rem 1rem; }
        .pw-divider { height: 1px; background: var(--pw-border); margin: 1.2rem 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def brand_header(user: dict | None = None) -> None:
    user = user or {}
    name = user.get("full_name", "Guest")
    role = user.get("role", "PUBLIC")
    st.markdown(
        f"""
        <div style="display:flex;justify-content:space-between;align-items:center;gap:1rem;margin-bottom:1.8rem">
          <div>
            <div style="font-weight:850;letter-spacing:.18em;font-size:1.05rem;color:#f5f7fb">◉ PARKWISE</div>
            <div style="font-size:.68rem;letter-spacing:.18em;color:#6f8198;margin-top:.25rem">PREDICTIVE PARKING INTELLIGENCE</div>
          </div>
          <div style="text-align:right;color:#8fa1b8;font-size:.8rem">{name}<br><span style="color:#22d3ee;letter-spacing:.1em;font-size:.68rem">{role}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_label(text: str, color: str = "#22d3ee") -> None:
    st.markdown(f'<div class="pw-eyebrow" style="color:{color}">{text}</div>', unsafe_allow_html=True)
