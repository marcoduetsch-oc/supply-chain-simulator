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


def run_case(label, **over) -> dict:
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
    print(f"  Fenster (ab Warmup): Umsatz CHF {h['revenue_window'][-1]:,.0f} | "
          f"Kosten CHF {h['cost_window'][-1]:,.0f} | "
          f"Gewinn CHF {h['revenue_window'][-1] - h['cost_window'][-1]:,.0f}")
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

# Abstimmung der Geldkennzahlen (Fenster ab Warmup vs. Gesamtlauf)
print("\n=== Abstimmung Geldkennzahlen ===")
for label, r in [("A", a), ("B", b), ("C", c), ("D1", d1), ("D2", d2), ("D3", d3)]:
    st, h = r["sim"].state, r["h"]
    if abs(st["cash"] - (100_000 + st["total_revenue"] - st["total_cost"])) > 1e-6:
        print(f"  FEHLER {label}: Kassen-Identität verletzt "
              f"(cash={st['cash']:.2f} vs {100_000 + st['total_revenue'] - st['total_cost']:.2f})")
        ok = False
    blocks = sum(st[k] for k in ("cost_material", "cost_orders", "cost_production",
                                "cost_holding", "cost_stockout"))
    if abs(blocks - st["total_cost"]) > 1e-6:
        print(f"  FEHLER {label}: Kostensumme ({blocks:.2f}) != total_cost ({st['total_cost']:.2f})")
        ok = False
    rev_w, cost_w = h["revenue_window"][-1], h["cost_window"][-1]
    delivered = rev_w / 100.0
    tol = 3 * (r["demand"] / len(h["demand"]))  # Ankunfts-Verzug an der Fenstergrenze
    if delivered > r["demand"] + tol:
        print(f"  FEHLER {label}: zugestellte Einheiten ({delivered:,.0f}) > "
              f"Nachfrage ({r['demand']}) + Toleranz ({tol:,.0f})")
        ok = False
    if delivered > sum(h["shipments"]) + tol:
        print(f"  FEHLER {label}: zugestellte Einheiten ({delivered:,.0f}) > "
              f"versandte Einheiten ({sum(h['shipments']):,}) + Toleranz")
        ok = False
print("  Kassen-Identität (cash = 100'000 + Umsatz − Kosten):", ok)
print("  Kostensumme == total_cost:", ok)
print("  Zugestellt <= Nachfrage/Versand (Fenstertoleranz 3 Tage):", ok)
