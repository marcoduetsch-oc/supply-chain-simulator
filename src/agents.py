"""
Supply chain agents — each makes independent operational decisions.
"""

import math
import random

from src.base_agent import BaseAgent, Event
from src.config import (
    DEMAND_BASE,
    DEMAND_VOLATILITY,
    DEMAND_TREND,
    SEASONAL_AMPLITUDE,
    SEASONAL_PERIOD,
    ORDER_LEAD_TIME,
    SAFETY_STOCK_DAYS,
    REORDER_POINT_MULTIPLIER,
    ORDER_QTY_MULTIPLIER,
    PRODUCTION_CAPACITY,
    PRODUCTION_LEAD_TIME,
    SHIPPING_LEAD_TIME,
    TRUCK_CAPACITY,
    BILL_OF_MATERIALS,
    RAW_MATERIAL_COST,
    FINISHED_GOOD_PRICE,
    ORDER_FIXED_COST,
    PRODUCTION_FIXED_COST,
)


class DemandAgent(BaseAgent):
    """Generates customer demand with trend + seasonality + noise."""

    def reset(self):
        pass

    def step(self, tick: int, state: dict, events: list[Event]) -> list[Event]:
        # Demand with trend, seasonality, and randomness
        trend = DEMAND_TREND * tick
        seasonal = SEASONAL_AMPLITUDE * math.sin(2 * math.pi * tick / SEASONAL_PERIOD)
        noise = random.gauss(0, DEMAND_VOLATILITY)
        qty = max(0, int(DEMAND_BASE + trend + seasonal + noise))

        if qty > 0:
            state["pending_orders"].append({"qty": qty, "placed_at": tick})
            state["today_orders"] += qty
            state["backlog"] += qty
            self._info(f"📊 New demand: {qty} units (base={DEMAND_BASE}, trend={trend:.0f}, "
                       f"seasonal={seasonal:.0f}, noise={noise:.0f})")

        return []


class ProcurementAgent(BaseAgent):
    """
    Monitors raw material inventory and places orders with suppliers.
    Uses an (s, Q) continuous-review policy:
      s = reorder point (safety stock + lead-time demand)
      Q = order quantity (economic / days-of-supply)
    """

    def reset(self):
        self._last_inventory_levels = {}

    def step(self, tick: int, state: dict, events: list[Event]) -> list[Event]:
        new_events = []

        for mat in ["raw_a", "raw_b"]:
            current = state[mat]
            # Estimate daily demand rate for this material
            # based on BOM and recent finished-goods orders
            bom_qty = BILL_OF_MATERIALS[mat]
            avg_daily_demand = state["today_orders"] * bom_qty if state["today_orders"] > 0 else 0

            reorder_point = avg_daily_demand * REORDER_POINT_MULTIPLIER + \
                            avg_daily_demand * SAFETY_STOCK_DAYS
            order_qty = max(100, int(avg_daily_demand * ORDER_QTY_MULTIPLIER))

            if current < reorder_point and current > 0:
                # Place an order
                state["incoming_material"].append({
                    "raw_a": order_qty if mat == "raw_a" else 0,
                    "raw_b": order_qty if mat == "raw_b" else 0,
                    "arrives_at": tick + ORDER_LEAD_TIME,
                })
                cost = order_qty * RAW_MATERIAL_COST[mat] + ORDER_FIXED_COST
                state["total_cost"] += cost
                state["cash"] -= cost
                self._info(f"🛒 Procurement: +{order_qty} {mat} (cost CHF {cost:.0f}, arrives T+{ORDER_LEAD_TIME})")

                new_events.append(Event(
                    tick=tick, source=self.name, target="inventory",
                    kind="order_placed",
                    data={"material": mat, "qty": order_qty, "arrives_at": tick + ORDER_LEAD_TIME}
                ))

                # Avoid double-ordering the same material this tick
                state[mat] = 99999  # temporarily suppress

        return new_events


class ProductionAgent(BaseAgent):
    """
    Schedules production: converts raw materials into finished goods
    to meet pending customer orders.
    """

    def reset(self):
        pass

    def step(self, tick: int, state: dict, events: list[Event]) -> list[Event]:
        # Don't start new production if one is already running
        if state["production_in_progress"] is not None:
            return []

        # How many units can we produce based on raw materials?
        max_from_a = state["raw_a"] // BILL_OF_MATERIALS["raw_a"] if BILL_OF_MATERIALS["raw_a"] > 0 else 9999
        max_from_b = state["raw_b"] // BILL_OF_MATERIALS["raw_b"] if BILL_OF_MATERIALS["raw_b"] > 0 else 9999
        max_by_material = min(max_from_a, max_from_b)

        # How many do we need? (pending orders - finished stock)
        demand = state["backlog"]
        needed = max(0, demand - state["finished"])

        if needed <= 0 or max_by_material <= 0:
            return []

        qty = min(needed, max_by_material, PRODUCTION_CAPACITY)

        if qty <= 0:
            return []

        # Consume raw materials
        state["raw_a"] -= qty * BILL_OF_MATERIALS["raw_a"]
        state["raw_b"] -= qty * BILL_OF_MATERIALS["raw_b"]

        # Schedule production
        state["production_in_progress"] = {
            "qty": qty,
            "finishes_at": tick + PRODUCTION_LEAD_TIME,
        }

        cost = qty * (BILL_OF_MATERIALS["raw_a"] * RAW_MATERIAL_COST["raw_a"] +
                      BILL_OF_MATERIALS["raw_b"] * RAW_MATERIAL_COST["raw_b"]) + \
               PRODUCTION_FIXED_COST
        state["total_cost"] += cost
        state["cash"] -= cost

        self._info(f"🔧 Production started: {qty} units, finishes T+{PRODUCTION_LEAD_TIME}")

        return [Event(
            tick=tick, source=self.name, target="inventory",
            kind="production_started",
            data={"qty": qty, "finishes_at": tick + PRODUCTION_LEAD_TIME}
        )]


class InventoryAgent(BaseAgent):
    """
    Tracks inventory levels, detects stockouts, manages finished-goods
    fulfilment to pending orders.
    """

    def reset(self):
        pass

    def step(self, tick: int, state: dict, events: list[Event]) -> list[Event]:
        # ── Fulfil pending orders from finished stock ──
        can_ship = state["finished"]
        still_pending = []

        for order in state["pending_orders"]:
            if can_ship <= 0:
                still_pending.append(order)
                continue

            ship_qty = min(order["qty"], can_ship)
            can_ship -= ship_qty
            state["backlog"] -= ship_qty

            # Put into shipping queue
            state["shipping_queue"].append({
                "qty": ship_qty,
                "order_placed": order["placed_at"],
            })

            self._info(f"📦 Fulfilled {ship_qty} units from stock")

            leftover = order["qty"] - ship_qty
            if leftover > 0:
                still_pending.append({"qty": leftover, "placed_at": order["placed_at"]})

        state["pending_orders"] = still_pending

        # ── Stockout detection ──
        if still_pending:
            stockout_qty = sum(o["qty"] for o in still_pending)
            state["today_stockouts"] = stockout_qty
            self._info(f"⚠️ STOCKOUT: {stockout_qty} units of demand unfilled")

        # Update finished stock
        state["finished"] = can_ship

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
            batch = min(total_ready, TRUCK_CAPACITY)
            total_ready -= batch

            state["in_transit"].append({
                "qty": batch,
                "arrives_at": tick + SHIPPING_LEAD_TIME,
            })

            self._info(f"🚛 Shipment dispatched: {batch} units, arrives T+{SHIPPING_LEAD_TIME}")

        return []
