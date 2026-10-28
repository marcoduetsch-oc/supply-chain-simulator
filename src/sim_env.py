"""
Simulation environment — tick loop, event bus, metrics collector.

Alle Parameter werden zur Laufzeit über `cfg.X` gelesen, damit Änderungen
aus dem Dashboard (Slider) tatsächlich greifen.
"""

from src import config as cfg
from src.base_agent import BaseAgent, Event


class Simulation:
    """Runs the multi-agent supply chain simulation."""

    def __init__(self, agents: list[BaseAgent]):
        self.agents = {a.name: a for a in agents}
        self.log: list[str] = []
        self.state: dict = self._init_state()
        self.warmup: int = cfg.WARMUP_TICKS
        self.history: dict[str, list] = {
            "tick": [],
            "demand": [],
            "served": [],          # am Bestelltag aus Lager erfüllt
            "backlog": [],
            "raw_a_stock": [],
            "raw_b_stock": [],
            "finished_stock": [],  # Fertigwaren, die am Tag verfügbar waren
            "production": [],
            "shipments": [],
            "stockouts": [],       # Einheiten, die das Service-Level gerissen haben
            "stockout_cost": [],
            "total_cost": [],
            "revenue": [],
            "fill_rate_30": [],    # rolling 30-day fill rate
        }

    def _init_state(self) -> dict:
        return {
            "tick": 0,
            # Inventory
            "raw_a": 1000,
            "raw_b": 500,
            "finished": 200,
            # Demand pipeline
            "pending_orders": [],      # list of {qty, placed_at, counted}
            "backlog": 0,
            # Procurement pipeline
            "incoming_material": [],   # list of {raw_a, raw_b, arrives_at}
            # Production pipeline
            "production_queue": 0,
            "production_in_progress": None,  # {qty, finishes_at}
            # Shipping pipeline
            "shipping_queue": [],
            "in_transit": [],          # list of {qty, arrives_at}
            # Cash
            "cash": 100_000.0,
            "total_cost": 0.0,
            "total_revenue": 0.0,
            "total_stockout_cost": 0.0,
            # Kostenaufschlüsselung
            "cost_material": 0.0,
            "cost_orders": 0.0,
            "cost_production": 0.0,
            "cost_holding": 0.0,
            "cost_stockout": 0.0,
            # Daily stats
            "today_orders": 0,
            "today_served": 0,
            "today_produced": 0,
            "today_shipped": 0,
            "today_stockouts": 0,
            "finished_available": 0,   # Fertigwaren vor der Erfüllung
        }

    def run(self) -> dict:
        """Run the full simulation and return history."""
        for agent in self.agents.values():
            agent.reset()
            agent.log = self.log

        # Bei kurzen Läufen den Warmup mitziehen, sonst bleiben die
        # Kennzahlen leer (z.B. 30-Tage-Lauf bei 30 Tagen Warmup).
        self.warmup = min(cfg.WARMUP_TICKS, max(0, cfg.TICKS_PER_RUN // 5))

        # Event bus: queue of events that arrive this tick
        inbox: list[Event] = []

        for tick in range(cfg.TICKS_PER_RUN):
            self.state["tick"] = tick
            self.state["today_orders"] = 0
            self.state["today_served"] = 0
            self.state["today_produced"] = 0
            self.state["today_shipped"] = 0
            self.state["today_stockouts"] = 0

            # 1. Deliveries arriving this tick
            self._process_deliveries(tick)

            # 2. Production finishing this tick
            self._process_production(tick)

            # 3. Shipments arriving this tick
            self._process_shipments(tick)

            # 4. Let each agent act
            new_events: list[Event] = []
            for agent in self.agents.values():
                agent_events = agent.step(tick, self.state, inbox)
                new_events.extend(agent_events)

            # 5. Carry costs
            self._accrue_costs(tick)

            # 6. Store history snapshots
            if tick >= self.warmup:
                self._record_snapshot(tick)

            # Event bus: replace inbox with events produced this tick
            inbox = new_events

        return self.history

    # ── protected helpers ──────────────────────────────────────

    def _process_deliveries(self, tick: int):
        """Materials from procurement arriving today."""
        still_incoming = []
        for mat in self.state["incoming_material"]:
            if mat["arrives_at"] <= tick:
                self.state["raw_a"] += mat["raw_a"]
                self.state["raw_b"] += mat["raw_b"]
                self._log(tick, f"📦 Material delivery: A+{mat['raw_a']}, B+{mat['raw_b']}")
            else:
                still_incoming.append(mat)
        self.state["incoming_material"] = still_incoming

    def _process_production(self, tick: int):
        """Finished goods completing production."""
        pip = self.state["production_in_progress"]
        if pip and pip["finishes_at"] <= tick:
            qty = pip["qty"]
            self.state["finished"] += qty
            self.state["today_produced"] = qty
            self._log(tick, f"🏭 Production finished: +{qty} units")
            self.state["production_in_progress"] = None

    def _process_shipments(self, tick: int):
        """Customer shipments arriving / delivered."""
        still_transit = []
        for shipment in self.state["in_transit"]:
            if shipment["arrives_at"] <= tick:
                qty = shipment["qty"]
                revenue = qty * cfg.FINISHED_GOOD_PRICE
                self.state["total_revenue"] += revenue
                self.state["cash"] += revenue
                self.state["today_shipped"] += qty
                self._log(tick, f"🚚 Shipment delivered: {qty} units → CHF {revenue:.0f}")
            else:
                still_transit.append(shipment)
        self.state["in_transit"] = still_transit

    def _accrue_costs(self, tick: int):
        """Daily holding cost on inventory."""
        total_units = self.state["raw_a"] + self.state["raw_b"] + self.state["finished"]
        holding = total_units * cfg.HOLDING_COST_PER_UNIT_PER_DAY
        self.state["total_cost"] += holding
        self.state["cost_holding"] += holding
        self.state["cash"] -= holding

    def _record_snapshot(self, tick: int):
        s = self.state
        self.history["tick"].append(tick)
        self.history["demand"].append(s["today_orders"])
        self.history["served"].append(s["today_served"])
        self.history["backlog"].append(s["backlog"])
        self.history["raw_a_stock"].append(s["raw_a"])
        self.history["raw_b_stock"].append(s["raw_b"])
        self.history["finished_stock"].append(s["finished_available"])
        self.history["production"].append(s["today_produced"])
        self.history["shipments"].append(s["today_shipped"])
        self.history["stockouts"].append(s["today_stockouts"])
        self.history["stockout_cost"].append(s["total_stockout_cost"])
        self.history["total_cost"].append(s["total_cost"])
        self.history["revenue"].append(s["total_revenue"])

        # Fill rate: am Bestelltag erfüllte Nachfrage vs. Nachfrage.
        # NICHT die zugestellten Sendungen — die hinken um die Versandzeit
        # nach und können die Nachfrage rechnerisch übersteigen (>100%).
        recent_served = self.history["served"][-30:]
        recent_demand = self.history["demand"][-30:]
        total_demand = sum(recent_demand)
        fr = (sum(recent_served) / total_demand * 100) if total_demand > 0 else 100.0
        self.history["fill_rate_30"].append(round(min(fr, 100.0), 1))

    def _log(self, tick: int, msg: str):
        self.log.append(f"[T{tick:03d}] {msg}")
