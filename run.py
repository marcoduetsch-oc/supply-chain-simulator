#!/usr/bin/env python3
"""
Headless simulation runner — test the simulation without Streamlit.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))

from sim_env import Simulation
from agents import DemandAgent, ProcurementAgent, ProductionAgent, InventoryAgent, LogisticsAgent

sim = Simulation(agents=[
    DemandAgent("demand"),
    ProcurementAgent("procurement"),
    ProductionAgent("production"),
    InventoryAgent("inventory"),
    LogisticsAgent("logistics"),
])

history = sim.run()

total_demand = sum(history["demand"])
total_served = sum(history["served"])
total_stockouts = sum(history["stockouts"])

print("=== Simulation Complete ===")
print(f"Ticks:            {len(history['tick'])} (Warmup {sim.warmup} Tage)")
print(f"Total Demand:     {total_demand}")
print(f"Total Served:     {total_served}")
print(f"Total Produced:   {sum(history['production'])}")
print(f"Total Shipped:    {sum(history['shipments'])}")
print(f"Total Stockouts:  {total_stockouts}")
if total_demand:
    print(f"Service Level:    {(1 - total_stockouts / total_demand) * 100:.1f}%  "
          f"(Stockouts = {total_stockouts / total_demand * 100:.1f}% der Nachfrage)")
rev_w = history["revenue_window"][-1]
cost_w = history["cost_window"][-1]
print(f"\n--- Auswertungsfenster (Tag {sim.warmup + 1}-{sim.warmup + len(history['tick'])}, "
      f"wie Dashboard) ---")
print(f"Umsatz:           CHF {rev_w:>14,.0f}  (= {rev_w / 100.0:,.0f} zugestellte Einheiten)")
print(f"Kosten:           CHF {cost_w:>14,.0f}")
print(f"Gewinn:           CHF {rev_w - cost_w:>14,.0f}")
print(f"\n--- Gesamtlauf (inkl. Warmup) ---")
print(f"Final Cash:       CHF {sim.state['cash']:>14,.2f}")
print(f"Total Cost:       CHF {sim.state['total_cost']:>14,.2f}")
print(f"Total Revenue:    CHF {sim.state['total_revenue']:>14,.2f}")
print(f"Avg Fill Rate (30d): {history['fill_rate_30'][-1]}%")

s = sim.state
print("\n=== Kostenaufschlüsselung ===")
for label, key in [("Material", "cost_material"), ("Bestellungen (fix)", "cost_orders"),
                   ("Produktion (fix)", "cost_production"), ("Lagerhaltung", "cost_holding"),
                   ("Stockout-Penalty", "cost_stockout")]:
    print(f"  {label:20s} CHF {s[key]:>14,.0f}")
print(f"  {'SUMME':20s} CHF {s['total_cost']:>14,.0f}")

print("\n=== Last 20 Logs ===")
for entry in sim.log[-20:]:
    print(entry)
