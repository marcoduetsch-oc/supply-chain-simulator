#!/usr/bin/env python3
"""
Streamlit dashboard for the Multi-Agent Supply Chain Simulator.

Run:   streamlit run dashboard.py
"""

import sys
sys.path.insert(0, "src")

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from sim_env import Simulation
from agents import (
    DemandAgent, ProcurementAgent, ProductionAgent,
    InventoryAgent, LogisticsAgent,
)

st.set_page_config(page_title="Supply Chain Simulator", layout="wide")
st.title("🏭 Multi-Agent Supply Chain Simulator")

# ── Sidebar Controls ─────────────────────────────────────────────
st.sidebar.header("⚙️ Steuerung")

if st.sidebar.button("🔄 Simulation starten", type="primary", use_container_width=True):
    st.session_state["run"] = True

if st.sidebar.button("Dashboard reset", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Parameter")
ticks = st.sidebar.slider("Simulations-Tage", 30, 365, 180, 10)
demand_base = st.sidebar.slider("Basis-Nachfrage (Einheiten/Tag)", 10, 500, 100, 10)
demand_vol = st.sidebar.slider("Nachfrage-Volatilität", 0, 100, 20, 5)
prod_cap = st.sidebar.slider("Produktionskapazität", 10, 300, 120, 10)
lead_time = st.sidebar.slider("Lieferzeit (Tage)", 1, 14, 5, 1)
safety_days = st.sidebar.slider("Sicherheitsbestand (Tage)", 0, 30, 7, 1)

st.sidebar.divider()
auto_refresh = st.sidebar.checkbox("Auto-Refresh", value=True)

# ── Run Simulation ───────────────────────────────────────────────
if "run" not in st.session_state:
    st.info("👉 Klicke links auf **'Simulation starten'**")
    st.stop()

if st.session_state.get("run"):
    # Build simulation with user parameters
    from src import config as cfg

    # Override config with user selections
    cfg.TICKS_PER_RUN = ticks
    cfg.DEMAND_BASE = demand_base
    cfg.DEMAND_VOLATILITY = demand_vol
    cfg.PRODUCTION_CAPACITY = prod_cap
    cfg.ORDER_LEAD_TIME = lead_time
    cfg.SAFETY_STOCK_DAYS = safety_days

    sim = Simulation(agents=[
        DemandAgent("📊 Nachfrage"),
        ProcurementAgent("🛒 Beschaffung"),
        ProductionAgent("🔧 Produktion"),
        InventoryAgent("📦 Lager"),
        LogisticsAgent("🚚 Logistik"),
    ])

    with st.spinner("Simulation läuft…"):
        history = sim.run()

    st.session_state["history"] = history
    st.session_state["sim"] = sim
    st.session_state["run"] = False
    st.session_state["done"] = True
    st.rerun()

if not st.session_state.get("done"):
    st.stop()

history = st.session_state["history"]
sim = st.session_state["sim"]
state = sim.state

# ── KPI Cards ────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    fr = history["fill_rate_30"][-1] if history["fill_rate_30"] else 0
    delta = fr - 85  # target
    st.metric("🎯 Fill Rate (30d)", f"{fr:.1f}%", f"{delta:+.1f}%", delta_color="inverse" if delta < 0 else "normal")
with col2:
    total_demand = sum(history["demand"])
    st.metric("📊 Gesamtnachfrage", f"{total_demand:,}")
with col3:
    total_shipped = sum(history["shipments"])
    st.metric("🚚 Geliefert", f"{total_shipped:,}")
with col4:
    total_stockouts = sum(history["stockouts"])
    st.metric("⚠️ Stockouts", f"{total_stockouts:,}", delta_color="inverse")
with col5:
    profit = state["total_revenue"] - state["total_cost"]
    profit_str = f"CHF {profit:,.0f}" if profit >= 0 else f"CHF {profit:,.0f}"
    profit_delta = f"{profit:+.0f}"
    st.metric("💰 Gewinn/Verlust", profit_str, profit_delta,
              delta_color="normal" if profit >= 0 else "inverse")

# ── Charts ───────────────────────────────────────────────────────

# Inventory levels
fig_inv = make_subplots(specs=[[{"secondary_y": True}]])
fig_inv.add_trace(go.Scatter(x=history["tick"], y=history["raw_a_stock"],
                             name="Rohstoff A", line=dict(color="#1f77b4")), secondary_y=False)
fig_inv.add_trace(go.Scatter(x=history["tick"], y=history["raw_b_stock"],
                             name="Rohstoff B", line=dict(color="#ff7f0e")), secondary_y=False)
fig_inv.add_trace(go.Scatter(x=history["tick"], y=history["finished_stock"],
                             name="Fertigwaren", line=dict(color="#2ca02c")), secondary_y=False)
fig_inv.update_layout(title="📦 Lagerbestände", hovermode="x unified",
                      height=350, margin=dict(l=0, r=0, t=40, b=0))
fig_inv.update_yaxes(title_text="Einheiten", secondary_y=False)

# Demand vs Production vs Shipments
fig_flow = go.Figure()
fig_flow.add_trace(go.Scatter(x=history["tick"], y=history["demand"],
                              name="Nachfrage", line=dict(color="#d62728", width=1, dash="dot")))
fig_flow.add_trace(go.Scatter(x=history["tick"], y=history["production"],
                              name="Produktion", line=dict(color="#2ca02c", width=1.5)))
fig_flow.add_trace(go.Scatter(x=history["tick"], y=history["shipments"],
                              name="Auslieferungen", line=dict(color="#17becf", width=1.5)))
fig_flow.update_layout(title="📈 Nachfrage ↔ Produktion ↔ Lieferungen",
                       hovermode="x unified", height=350, margin=dict(l=0, r=0, t=40, b=0))
fig_flow.update_yaxes(title_text="Einheiten pro Tag")

# Fill rate
fig_fr = go.Figure()
fig_fr.add_trace(go.Scatter(x=history["tick"], y=history["fill_rate_30"],
                            name="Fill Rate (30d)", fill="tozeroy",
                            line=dict(color="#9467bd")))
fig_fr.add_hline(y=95, line_dash="dash", line_color="green",
                 annotation_text="Ziel 95%")
fig_fr.update_layout(title="🎯 Fill Rate (Rollierend 30 Tage)",
                     hovermode="x unified", height=250,
                     margin=dict(l=0, r=0, t=40, b=0))
fig_fr.update_yaxes(range=[0, 105], title_text="%")

# Cash & Cost
fig_cash = make_subplots(specs=[[{"secondary_y": True}]])
fig_cash.add_trace(go.Scatter(x=history["tick"], y=history["revenue"],
                              name="Umsatz (kum.)", line=dict(color="#2ca02c")), secondary_y=False)
fig_cash.add_trace(go.Scatter(x=history["tick"], y=history["total_cost"],
                              name="Kosten (kum.)", line=dict(color="#d62728")), secondary_y=False)
fig_cash.update_layout(title="💰 Umsatz vs. Kosten", hovermode="x unified",
                       height=300, margin=dict(l=0, r=0, t=40, b=0))
fig_cash.update_yaxes(title_text="CHF", secondary_y=False)

# Layout
tab1, tab2, tab3 = st.tabs(["📊 Kennzahlen", "📋 Agenten-Log", "⚙️ Konfiguration"])

with tab1:
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(fig_inv, use_container_width=True)
    with col_b:
        st.plotly_chart(fig_flow, use_container_width=True)

    st.plotly_chart(fig_fr, use_container_width=True)
    st.plotly_chart(fig_cash, use_container_width=True)

with tab2:
    if auto_refresh:
        st.info("🔄 Auto-Refresh aktiv — Log wird live aktualisiert")
    st.code("\n".join(sim.log[-100:]), language="text")

with tab3:
    st.json({
        "Simulations-Tage": ticks,
        "Basis-Nachfrage": demand_base,
        "Volatilität": demand_vol,
        "Produktionskapazität": prod_cap,
        "Lieferzeit": lead_time,
        "Sicherheitsbestand (Tage)": safety_days,
        "Läufe gesamt": len(history["tick"]),
        "Agenten": ["📊 Nachfrage", "🛒 Beschaffung", "🔧 Produktion", "📦 Lager", "🚚 Logistik"],
    })
