"""
Supply chain agents — each makes independent operational decisions.

Alle Parameter werden zur Laufzeit über `cfg.X` gelesen (nicht per
`from ... import X` beim Modul-Import), sonst wirken die Dashboard-Slider nicht.
"""

import math
import random

from src import config as cfg
from src.base_agent import BaseAgent, Event


class DemandAgent(BaseAgent):
    """Generates customer demand with trend + seasonality + noise."""

    def reset(self):
        pass

    def step(self, tick: int, state: dict, events: list[Event]) -> list[Event]:
        # Demand with trend, seasonality, and randomness
        trend = cfg.DEMAND_TREND * tick
        seasonal = cfg.SEASONAL_AMPLITUDE * math.sin(2 * math.pi * tick / cfg.SEASONAL_PERIOD)
        noise = random.gauss(0, cfg.DEMAND_VOLATILITY)
        qty = max(0, int(cfg.DEMAND_BASE + trend + seasonal + noise))

        if qty > 0:
            state["pending_orders"].append({"qty": qty, "placed_at": tick, "counted": False})
            state["today_orders"] += qty
            state["backlog"] += qty
            self._info(f"📊 New demand: {qty} units (base={cfg.DEMAND_BASE}, trend={trend:.0f}, "
                       f"seasonal={seasonal:.0f}, noise={noise:.0f})")

        return []


class ProcurementAgent(BaseAgent):
    """
    Monitors raw material inventory and places orders with suppliers.
    Uses an (s, Q) continuous-review policy:
      s = reorder point (lead-time demand + safety stock)
      Q = order quantity (days-of-supply)

    Der Bestellpunkt wird aus einer GEGLÄTTETEN Nachfrageschätzung (EWMA)
    berechnet, nicht aus dem verrauschten Einzeltag. Bestellt wird auf Basis
    des Lagerbestands PLUS bereits unterwegs befindlicher Ware (Inventory
    Position), damit dieselbe Lieferung nicht mehrfach bestellt wird.
    """

    def reset(self):
        self._demand_ewma: float | None = None

    def step(self, tick: int, state: dict, events: list[Event]) -> list[Event]:
        new_events = []

        # Geglättete Tagesnachfrage (EWMA) statt Einzeltag-Rauschen
        today = state["today_orders"]
        if self._demand_ewma is None:
            self._demand_ewma = float(today)
        else:
            a = cfg.DEMAND_SMOOTHING
            self._demand_ewma = a * today + (1 - a) * self._demand_ewma
        demand_est: float = self._demand_ewma if self._demand_ewma is not None else 0.0

        for mat in ["raw_a", "raw_b"]:
            bom_qty = cfg.BILL_OF_MATERIALS[mat]
            # Bedarf pro Tag in Einheiten dieses Rohmaterials
            daily_need = demand_est * bom_qty

            # Inventory Position = Bestand + bereits bestellte (unterwegs) Ware
            on_order = sum(m.get(mat, 0) for m in state["incoming_material"])
            position = state[mat] + on_order

            reorder_point = daily_need * (cfg.ORDER_LEAD_TIME + cfg.SAFETY_STOCK_DAYS)

            if position < reorder_point:
                order_qty = max(
                    cfg.MIN_ORDER_QTY,
                    int(daily_need * cfg.ORDER_QTY_MULTIPLIER),
                    int(reorder_point - position),
                )
                state["incoming_material"].append({
                    "raw_a": order_qty if mat == "raw_a" else 0,
                    "raw_b": order_qty if mat == "raw_b" else 0,
                    "arrives_at": tick + cfg.ORDER_LEAD_TIME,
                })
                cost = order_qty * cfg.RAW_MATERIAL_COST[mat] + cfg.ORDER_FIXED_COST
                state["total_cost"] += cost
                state["cost_material"] += order_qty * cfg.RAW_MATERIAL_COST[mat]
                state["cost_orders"] += cfg.ORDER_FIXED_COST
                state["cash"] -= cost
                self._info(f"🛒 Procurement: +{order_qty} {mat} "
                           f"(cost CHF {cost:.0f}, arrives T+{cfg.ORDER_LEAD_TIME}, "
                           f"position {position:.0f} < s {reorder_point:.0f})")

                new_events.append(Event(
                    tick=tick, source=self.name, target="inventory",
                    kind="order_placed",
                    data={"material": mat, "qty": order_qty,
                          "arrives_at": tick + cfg.ORDER_LEAD_TIME}
                ))

        return new_events


class ProductionAgent(BaseAgent):
    """
    Schedules production: converts raw materials into finished goods
    to meet pending customer orders.

    Materialkosten werden NICHT hier berechnet — sie fallen einmalig beim
    Einkauf an (ProcurementAgent). Hier entstehen nur die Rüstkosten.
    """

    def reset(self):
        pass

    def step(self, tick: int, state: dict, events: list[Event]) -> list[Event]:
        # Don't start new production if one is already running
        if state["production_in_progress"] is not None:
            return []

        bom_a = cfg.BILL_OF_MATERIALS["raw_a"]
        bom_b = cfg.BILL_OF_MATERIALS["raw_b"]

        # How many units can we produce based on raw materials?
        max_from_a = state["raw_a"] // bom_a if bom_a > 0 else 9999
        max_from_b = state["raw_b"] // bom_b if bom_b > 0 else 9999
        max_by_material = min(max_from_a, max_from_b)

        # How many do we need? (pending orders - finished stock)
        needed = max(0, state["backlog"] - state["finished"])

        if needed <= 0 or max_by_material <= 0:
            return []

        qty = min(needed, max_by_material, cfg.PRODUCTION_CAPACITY)

        if qty <= 0:
            return []

        # Consume raw materials
        state["raw_a"] -= qty * bom_a
        state["raw_b"] -= qty * bom_b

        # Schedule production
        state["production_in_progress"] = {
            "qty": qty,
            "finishes_at": tick + cfg.PRODUCTION_LEAD_TIME,
        }

        cost = cfg.PRODUCTION_FIXED_COST
        state["total_cost"] += cost
        state["cost_production"] += cost
        state["cash"] -= cost

        self._info(f"🔧 Production started: {qty} units, finishes T+{cfg.PRODUCTION_LEAD_TIME}")

        return [Event(
            tick=tick, source=self.name, target="inventory",
            kind="production_started",
            data={"qty": qty, "finishes_at": tick + cfg.PRODUCTION_LEAD_TIME}
        )]


class InventoryAgent(BaseAgent):
    """
    Tracks inventory levels, manages finished-goods fulfilment to pending
    orders, and detects STOCKOUTS against a service level.

    Stockout-Definition: Eine Bestellung gilt erst dann als Stockout, wenn sie
    LÄNGER als SERVICE_LEVEL_DAYS auf Erfüllung gewartet hat. Die normale
    Pipeline (Produktion 1 Tag + Versand) ist KEIN Stockout. Jede Bestellung
    wird höchstens einmal gezählt (Flag `counted`), auch wenn sie als Backlog
    weiter offen bleibt.
    """

    def reset(self):
        pass

    def step(self, tick: int, state: dict, events: list[Event]) -> list[Event]:
        # ── Fulfil pending orders from finished stock ──
        can_ship = state["finished"]
        state["finished_available"] = can_ship  # Bestand VOR der Erfüllung
        still_pending = []
        served = 0

        for order in state["pending_orders"]:
            if can_ship <= 0:
                still_pending.append(order)
                continue

            ship_qty = min(order["qty"], can_ship)
            can_ship -= ship_qty
            served += ship_qty
            state["backlog"] -= ship_qty

            # Put into shipping queue
            state["shipping_queue"].append({
                "qty": ship_qty,
                "order_placed": order["placed_at"],
            })

            leftover = order["qty"] - ship_qty
            if leftover > 0:
                still_pending.append({
                    "qty": leftover,
                    "placed_at": order["placed_at"],
                    "counted": order.get("counted", False),
                })

        state["pending_orders"] = still_pending
        state["today_served"] = served
        state["finished"] = can_ship

        # ── Stockout-Erkennung gegen das Service-Level ──
        # Erst wenn eine Bestellung das Service-Level reisst, zählt sie.
        stockout_qty = 0
        for order in state["pending_orders"]:
            waited = tick - order["placed_at"]
            if waited > cfg.SERVICE_LEVEL_DAYS and not order.get("counted", False):
                order["counted"] = True
                stockout_qty += order["qty"]
                penalty = order["qty"] * cfg.STOCKOUT_COST_PER_UNIT
                state["total_stockout_cost"] += penalty
                state["cost_stockout"] += penalty
                state["total_cost"] += penalty
                state["cash"] -= penalty
                self._info(f"⚠️ STOCKOUT: {order['qty']} units waited {waited} days "
                           f"(> service level {cfg.SERVICE_LEVEL_DAYS}d), "
                           f"penalty CHF {penalty:.0f}")

        state["today_stockouts"] = stockout_qty

        return []


class LogisticsAgent(BaseAgent):
    """
    Manages shipping: dispatches finished goods from the shipping queue
    to customers (with lead time and truck capacity constraints).
    """

    def reset(self):
        pass

    def step(self, tick: int, state: dict, events: list[Event]) -> list[Event]:
        if not state["shipping_queue"]:
            return []

        # Consolidate all queued goods into shipments
        total_ready = sum(s["qty"] for s in state["shipping_queue"])
        state["shipping_queue"] = []

        # Ship in truck-sized batches
        while total_ready > 0:
            batch = min(total_ready, cfg.TRUCK_CAPACITY)
            total_ready -= batch

            state["in_transit"].append({
                "qty": batch,
                "arrives_at": tick + cfg.SHIPPING_LEAD_TIME,
            })

            self._info(f"🚛 Shipment dispatched: {batch} units, arrives T+{cfg.SHIPPING_LEAD_TIME}")

        return []
