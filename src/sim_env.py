"""
Simulation environment — tick loop, event bus, metrics collector.
"""

from src.base_agent import BaseAgent, Event
from src.config import TICKS_PER_RUN, WARMUP_TICKS


class Simulation:
    """Runs the multi-agent supply chain simulation."""

    def __init__(self, agents: list[BaseAgent]):
        self.agents = {a.name: a for a in agents}
        self.log: list[str] = []
        self.state: dict = self._init_state()
        self.history: dict[str, list] = {
            "tick": [],
            "demand": [],
            "backlog": [],
            "raw_a_stock": [],
            "raw_b_stock": [],
            "finished_stock": [],
            "production": [],
            "shipments": [],
            "stockouts": [],
            "total_cost": [],
            "revenue": [],
            "fill_rate_30": [],  # rolling 30-day fill rate
        }

    def _init_state(self) -> dict:
        return {
            "tick": 0,
            # Inventory
            "raw_a": 1000,
            "raw_b": 500,
            "finished": 200,
            # Demand pipeline
            "pending_orders": [],      # list of {qty, placed_at}
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
            # Daily stats
            "today_orders": 0,
            "today_produced": 0,
            "today_shipped": 0,
            "today_stockouts": 0,
        }

    def run(self) -> dict:
        """Run the full simulation and return history."""
        for agent in self.agents.values():
            agent.reset()
            agent.log = self.log

        # Event bus: queue of events that arrive this tick
        inbox: list[Event] = []

        for tick in range(TICKS_PER_RUN):
            self.state["tick"] = tick
            self.state["today_orders"] = 0
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
            if tick >= WARMUP_TICKS:
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
                revenue = qty * 100.0  # FINISHED_GOOD_PRICE
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
        holding = total_units * 0.10  # HOLDING_COST
        self.state["total_cost"] += holding
        self.state["cash"] -= holding

    def _record_snapshot(self, tick: int):
        s = self.state
        # rolling 30-day fill rate
        self.history["tick"].append(tick)
        self.history["demand"].append(s["today_orders"])
        self.history["backlog"].append(s["backlog"])
        self.history["raw_a_stock"].append(s["raw_a"])
        self.history["raw_b_stock"].append(s["raw_b"])
        self.history["finished_stock"].append(s["finished"])
        self.history["production"].append(s["today_produced"])
        self.history["shipments"].append(s["today_shipped"])
        self.history["stockouts"].append(s["today_stockouts"])
        self.history["total_cost"].append(s["total_cost"])
        self.history["revenue"].append(s["total_revenue"])

        # fill rate: shipments vs demand over last 30 ticks
        recent_shipped = self.history["shipments"][-30:]
        recent_demand = self.history["demand"][-30:]
        total_demand = sum(recent_demand)
        fr = (sum(recent_shipped) / total_demand * 100) if total_demand > 0 else 100.0
        self.history["fill_rate_30"].append(round(fr, 1))

    def _log(self, tick: int, msg: str):
        self.log.append(f"[T{tick:03d}] {msg}")
