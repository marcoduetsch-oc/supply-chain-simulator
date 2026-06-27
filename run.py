#!/usr/bin/env python3
"""
Headless simulation runner — test the simulation without Streamlit.
"""
import sys
sys.path.insert(0, "src")

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

print(f"=== Simulation Complete ===")
print(f"Ticks:        {len(history['tick'])}")
print(f"Total Demand: {sum(history['demand'])}")
print(f"Total Produced: {sum(history['production'])}")
print(f"Total Shipped: {sum(history['shipments'])}")
print(f"Total Stockouts: {sum(history['stockouts'])}")
print(f"Final Cash:   CHF {sim.state['cash']:.2f}")
print(f"Total Cost:   CHF {sim.state['total_cost']:.2f}")
print(f"Total Revenue: CHF {sim.state['total_revenue']:.2f}")
print(f"Avg Fill Rate (30d): {history['fill_rate_30'][-1]}%")

print(f"\n=== Last 20 Logs ===")
for entry in sim.log[-20:]:
    print(entry)
