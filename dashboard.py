#!/usr/bin/env python3
"""
Streamlit dashboard for the Multi-Agent Supply Chain Simulator.

Run:   streamlit run dashboard.py
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))

import streamlit as st
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
service_days = st.sidebar.slider(
    "Service-Level (max. Wartezeit, Tage)", 1, 14, 3, 1,
    help="Erst wenn eine Bestellung LÄNGER als diese Frist auf Erfüllung "
         "wartet, zählt sie als Stockout. Die normale Pipeline "
         "(Produktion 1 Tag + Versand 2 Tage) ist KEIN Stockout."
)

st.sidebar.divider()
show_log = st.sidebar.checkbox("Agenten-Log anzeigen", value=True)

# ── Run Simulation ───────────────────────────────────────────────
if "run" not in st.session_state:
    st.info("👉 Klicke links auf **'Simulation starten'**")
    st.stop()

if st.session_state.get("run"):
    # Build simulation with user parameters.
    # Wichtig: sim_env.py / agents.py lesen cfg.X zur Laufzeit — deshalb
    # wirken diese Overrides tatsächlich (vorher wurden die Werte beim
    # Import gebunden und die Slider waren wirkungslos).
    from src import config as cfg

    cfg.TICKS_PER_RUN = ticks
    cfg.DEMAND_BASE = demand_base
    cfg.DEMAND_VOLATILITY = demand_vol
    cfg.PRODUCTION_CAPACITY = prod_cap
    cfg.ORDER_LEAD_TIME = lead_time
    cfg.SAFETY_STOCK_DAYS = safety_days
    cfg.SERVICE_LEVEL_DAYS = service_days

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

total_demand = sum(history["demand"])
total_served = sum(history["served"])
total_shipped = sum(history["shipments"])
total_stockouts = sum(history["stockouts"])
service_level = (1 - total_stockouts / total_demand) * 100 if total_demand else 100.0

# ── KPI Cards ────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    fr = history["fill_rate_30"][-1] if history["fill_rate_30"] else 0
    delta = fr - 95  # target
    st.metric("🎯 Fill Rate (30d)", f"{fr:.1f}%", f"{delta:+.1f}%",
              delta_color="normal" if delta >= 0 else "inverse")
with col2:
    st.metric("📊 Gesamtnachfrage", f"{total_demand:,}")
with col3:
    st.metric("📦 Bedient (aus Lager)", f"{total_served:,}",
              f"{total_served / total_demand * 100:.1f}% der Nachfrage" if total_demand else "—")
with col4:
    pct = total_stockouts / total_demand * 100 if total_demand else 0
    st.metric("⚠️ Stockouts (Einheiten)", f"{total_stockouts:,}", f"{pct:.1f}% der Nachfrage",
              delta_color="inverse")
with col5:
    revenue_w = history["revenue_window"][-1] if history["revenue_window"] else 0.0
    cost_w = history["cost_window"][-1] if history["cost_window"] else 0.0
    profit = revenue_w - cost_w
    st.metric("💰 Gewinn/Verlust", f"CHF {profit:,.0f}", f"{profit:+,.0f}",
              delta_color="normal" if profit >= 0 else "inverse")

st.caption(
    f"Service-Level {service_days} Tage → **{service_level:.1f}%** der Nachfrage innerhalb "
    f"der Frist erfüllt · Geliefert (zugestellt): {total_shipped:,} Einheiten · "
    f"Offener Auftragsbestand: {state['backlog']:,}"
)
st.caption(
    f"⏱️ Auswertungsfenster: **Tag {sim.warmup + 1}–{sim.warmup + len(history['tick'])}** "
    f"(nach Warmup) — Nachfrage, Bedient, Stockouts, Umsatz und Kosten beziehen sich alle "
    f"auf dieselben {len(history['tick'])} Tage.  \n"
    f"Abstimmung: Umsatz CHF {revenue_w:,.0f} (= {revenue_w / 100.0:,.0f} zugestellte "
    f"Einheiten × CHF 100) − Kosten CHF {cost_w:,.0f} = **CHF {profit:,.0f}** · "
    f"Kasse inkl. Warmup: CHF {state['cash']:,.0f}"
)

# ── Charts ───────────────────────────────────────────────────────

# Inventory levels
fig_inv = go.Figure()
fig_inv.add_trace(go.Scatter(x=history["tick"], y=history["raw_a_stock"],
                             name="Rohstoff A", line=dict(color="#1f77b4")))
fig_inv.add_trace(go.Scatter(x=history["tick"], y=history["raw_b_stock"],
                             name="Rohstoff B", line=dict(color="#ff7f0e")))
fig_inv.add_trace(go.Scatter(x=history["tick"], y=history["finished_stock"],
                             name="Fertigwaren (verfügbar)", line=dict(color="#2ca02c")))
fig_inv.update_layout(title="📦 Lagerbestände", hovermode="x unified",
                      height=350, margin=dict(l=0, r=0, t=40, b=0))
fig_inv.update_yaxes(title_text="Einheiten")

# Demand vs Served vs Production vs Shipments
fig_flow = go.Figure()
fig_flow.add_trace(go.Scatter(x=history["tick"], y=history["demand"],
                              name="Nachfrage", line=dict(color="#d62728", width=1, dash="dot")))
fig_flow.add_trace(go.Scatter(x=history["tick"], y=history["served"],
                              name="Bedient", line=dict(color="#1f77b4", width=1.5)))
fig_flow.add_trace(go.Scatter(x=history["tick"], y=history["production"],
                              name="Produktion", line=dict(color="#2ca02c", width=1.5)))
fig_flow.add_trace(go.Scatter(x=history["tick"], y=history["shipments"],
                              name="Auslieferungen", line=dict(color="#17becf", width=1.5)))
fig_flow.update_layout(title="📈 Nachfrage ↔ Bedient ↔ Produktion ↔ Lieferungen",
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
fig_cash = go.Figure()
fig_cash.add_trace(go.Scatter(x=history["tick"], y=history["revenue_window"],
                              name="Umsatz (kum., ab Warmup)", line=dict(color="#2ca02c")))
fig_cash.add_trace(go.Scatter(x=history["tick"], y=history["cost_window"],
                              name="Kosten (kum., ab Warmup)", line=dict(color="#d62728")))
fig_cash.update_layout(title="💰 Umsatz vs. Kosten (Auswertungsfenster)", hovermode="x unified",
                       height=300, margin=dict(l=0, r=0, t=40, b=0))
fig_cash.update_yaxes(title_text="CHF")

# Cost breakdown
cost_parts = {
    "Material": state["cost_material"],
    "Bestellungen (fix)": state["cost_orders"],
    "Produktion (fix)": state["cost_production"],
    "Lagerhaltung": state["cost_holding"],
    "Stockout-Penalty": state["cost_stockout"],
}
fig_cost = go.Figure(go.Bar(
    x=list(cost_parts.values()), y=list(cost_parts.keys()), orientation="h",
    marker_color=["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd", "#d62728"],
    text=[f"CHF {v:,.0f}" for v in cost_parts.values()], textposition="auto",
))
fig_cost.update_layout(title="💸 Kostenaufschlüsselung", height=300,
                       margin=dict(l=0, r=0, t=40, b=0))

# Layout
tab1, tab2, tab3 = st.tabs(["📊 Kennzahlen", "📋 Agenten-Log", "⚙️ Konfiguration"])

with tab1:
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(fig_inv, use_container_width=True)
    with col_b:
        st.plotly_chart(fig_flow, use_container_width=True)

    st.plotly_chart(fig_fr, use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.plotly_chart(fig_cash, use_container_width=True)
    with col_d:
        st.plotly_chart(fig_cost, use_container_width=True)

with tab2:
    if show_log:
        st.code("\n".join(sim.log[-100:]), language="text")
    else:
        st.info("Agenten-Log ist in der Seitenleiste deaktiviert.")

with tab3:
    st.json({
        "Simulations-Tage": ticks,
        "Basis-Nachfrage": demand_base,
        "Volatilität": demand_vol,
        "Produktionskapazität": prod_cap,
        "Lieferzeit (Tage)": lead_time,
        "Sicherheitsbestand (Tage)": safety_days,
        "Service-Level (Tage)": service_days,
        "Läufe gesamt": len(history["tick"]),
        "Aufgezeichnete Tage": len(history["tick"]),
        "Warmup (Tage)": sim.warmup,
        "Agenten": ["📊 Nachfrage", "🛒 Beschaffung", "🔧 Produktion",
                    "📦 Lager", "🚚 Logistik"],
    })
