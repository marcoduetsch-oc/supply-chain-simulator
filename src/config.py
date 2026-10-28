"""
Simulation configuration & parameters.
Tweak these to experiment with different supply chain dynamics.

WICHTIG: Diese Werte werden zur LAUFZEIT gelesen (agents.py / sim_env.py
greifen über `cfg.X` zu). Nur deshalb wirken die Dashboard-Slider.
"""

# ── Product Definition ────────────────────────────────────────────
# A simple product: 1 finished good = 2 units raw material A + 1 unit raw material B
BILL_OF_MATERIALS = {
    "raw_a": 2,  # units of raw material A per finished good
    "raw_b": 1,  # units of raw material B per finished good
}

RAW_MATERIAL_COST = {
    "raw_a": 10.0,   # cost per unit
    "raw_b": 5.0,
}

FINISHED_GOOD_PRICE = 100.0  # selling price per unit

# ── Simulation Timing ─────────────────────────────────────────────
TICKS_PER_RUN = 180       # days
WARMUP_TICKS = 30         # ticks before recording metrics (wird bei kurzen
                          # Läufen automatisch auf ticks/5 reduziert)

# ── Service Level ─────────────────────────────────────────────────
# Maximal tolerierte Wartezeit einer Bestellung. Erst wenn eine Bestellung
# LÄNGER als SERVICE_LEVEL_DAYS auf Erfüllung wartet, gilt sie als Stockout.
# Die normale Pipeline (Produktion 1 Tag + Versand 2 Tage) ist KEIN Stockout.
SERVICE_LEVEL_DAYS = 3

# ── Agent Parameters ──────────────────────────────────────────────
# Demand
DEMAND_BASE = 100          # average daily demand (units)
DEMAND_VOLATILITY = 20     # std dev of daily demand
DEMAND_TREND = 0.05        # daily demand growth (units/tick)
SEASONAL_AMPLITUDE = 15    # seasonal variation amplitude
SEASONAL_PERIOD = 30       # days for one full sine-wave cycle

# Procurement
ORDER_LEAD_TIME = 5        # days from order to delivery
SAFETY_STOCK_DAYS = 7      # days of demand held as safety stock
REORDER_POINT_MULTIPLIER = 2.0  # how many days of demand before reordering
ORDER_QTY_MULTIPLIER = 3.0      # how many days of demand per order
MIN_ORDER_QTY = 100             # Mindestbestellmenge pro Bestellung
DEMAND_SMOOTHING = 0.2          # EWMA-Faktor für die Nachfrageschätzung

# Production
PRODUCTION_CAPACITY = 120  # max units per tick (day)
PRODUCTION_LEAD_TIME = 1   # days to produce a batch

# Logistics
SHIPPING_LEAD_TIME = 2     # days to ship to customer
TRUCK_CAPACITY = 50        # max units per shipment

# Inventory
HOLDING_COST_PER_UNIT_PER_DAY = 0.10  # CHF per unit per day
STOCKOUT_COST_PER_UNIT = 50.0         # Penalty pro Einheit, die das
                                      # Service-Level reisst (verlorener Umsatz)

# ── Cost Tracking ─────────────────────────────────────────────────
# Materialkosten fallen EINMALIG beim Einkauf an (ProcurementAgent).
# Der ProductionAgent berechnet nur noch die Rüstkosten.
ORDER_FIXED_COST = 150.0   # fixed cost per procurement order
PRODUCTION_FIXED_COST = 200.0  # fixed cost per production run
