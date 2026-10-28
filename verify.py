"""Verifikation des Stockout-/Kosten-Fixes über mehrere Stressszenarien (read-only)."""
import os
import random
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))

from sim_env import Simulation
from agents import DemandAgent, ProcurementAgent, ProductionAgent, InventoryAgent, LogisticsAgent
from src import config as cfg


def build():
    return Simulation(agents=[
        DemandAgent("demand"), ProcurementAgent("procurement"),
        ProductionAgent("production"), InventoryAgent("inventory"),
        LogisticsAgent("logistics"),
    ])


def run_case(label, **over):
    random.seed(42)
    for k, v in over.items():
        setattr(cfg, k, v)
    sim = build()
    h = sim.run()
    d = sum(h["demand"])
    s = sum(h["served"])
    so = sum(h["stockouts"])
    so_ticks = sum(1 for x in h["stockouts"] if x > 0)
    print(f"\n--- {label} ---")
    print(f"  demand={d}  served={s}  stockouts={so}  "
          f"({so / d * 100:.1f}% der Nachfrage)  Tage mit Stockout={so_ticks}")
    print(f"  produced={sum(h['production'])}  shipped={sum(h['shipments'])}  "
          f"backlog={sim.state['backlog']}")
    print(f"  cash=CHF {sim.state['cash']:,.0f}  cost=CHF {sim.state['total_cost']:,.0f}  "
          f"revenue=CHF {sim.state['total_revenue']:,.0f}")
    print(f"  Kosten: Material {sim.state['cost_material']:,.0f} | Orders {sim.state['cost_orders']:,.0f} | "
          f"Prod {sim.state['cost_production']:,.0f} | Lager {sim.state['cost_holding']:,.0f} | "
          f"Penalty {sim.state['cost_stockout']:,.0f}")
    print(f"  fill_rate_30 min/avg/max: {min(h['fill_rate_30']):.1f} / "
          f"{sum(h['fill_rate_30']) / len(h['fill_rate_30']):.1f} / {max(h['fill_rate_30']):.1f}")
    return dict(demand=d, served=s, stockouts=so, sim=sim, h=h)


print("=== A: Normalbetrieb (Baseline, config-Defaults) ===")
a = run_case("A Baseline", TICKS_PER_RUN=180, DEMAND_BASE=100, DEMAND_VOLATILITY=20,
             PRODUCTION_CAPACITY=120, ORDER_LEAD_TIME=5, SAFETY_STOCK_DAYS=7,
             SERVICE_LEVEL_DAYS=3)

print("\n=== B: Unterkapazität (Nachfrage 300/Tag, Kapazität 120/Tag) ===")
b = run_case("B Unterkapazität", DEMAND_BASE=300, PRODUCTION_CAPACITY=120)

print("\n=== C: Lieferengpass (Lead Time 14 Tage, Safety 0) ===")
c = run_case("C Lieferengpass", DEMAND_BASE=100, PRODUCTION_CAPACITY=120,
             ORDER_LEAD_TIME=14, SAFETY_STOCK_DAYS=0)

print("\n=== D: Service-Level-Vergleich (gleicher Seed, nur Frist ändert sich) ===")
d1 = run_case("D1 Service-Level 1 Tag", DEMAND_BASE=300, PRODUCTION_CAPACITY=120, SERVICE_LEVEL_DAYS=1)
d2 = run_case("D2 Service-Level 3 Tage", DEMAND_BASE=300, PRODUCTION_CAPACITY=120, SERVICE_LEVEL_DAYS=3)
d3 = run_case("D3 Service-Level 10 Tage", DEMAND_BASE=300, PRODUCTION_CAPACITY=120, SERVICE_LEVEL_DAYS=10)

print("\n=== E: Slider-Wirksamkeit (Bug D) ===")
random.seed(42)
cfg.TICKS_PER_RUN = 30
cfg.DEMAND_BASE = 500
cfg.PRODUCTION_CAPACITY = 300
sim = build()
h = sim.run()
print(f"  30 Tage, DEMAND_BASE=500 -> recorded ticks={len(h['tick'])} "
      f"(erwartet ~{30 - sim.warmup}), avg demand/tick={sum(h['demand']) / len(h['demand']):.0f} "
      f"(erwartet ~500)")

print("\n=== Konsistenz-Checks ===")
ok = True
for label, r in [("A", a), ("B", b), ("C", c), ("D1", d1), ("D2", d2), ("D3", d3)]:
    if r["stockouts"] > r["demand"]:
        print(f"  FEHLER {label}: stockouts ({r['stockouts']}) > demand ({r['demand']})"); ok = False
    if r["served"] > r["demand"]:
        print(f"  FEHLER {label}: served ({r['served']}) > demand ({r['demand']})"); ok = False
print("  stockouts <= demand in allen Szenarien:", ok)
print("  Service-Level monoton (mehr Toleranz = weniger Stockouts):",
      d1["stockouts"] >= d2["stockouts"] >= d3["stockouts"])
