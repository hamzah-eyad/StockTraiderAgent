"""
Autopilot: Real-time autonomous trading loop.
Runs in a background thread, monitors geopolitical risk continuously,
and triggers the Gemini agent to trade when conditions change.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING

from config import (
    AUTOPILOT_POLL_INTERVAL,
    AUTOPILOT_ROUTINE_INTERVAL,
    AUTOPILOT_RISK_CHANGE_THRESHOLD,
    RISK_THRESHOLDS,
)
from agent.prompts import REACTIVE_PROMPT, ANALYSIS_PROMPT

if TYPE_CHECKING:
    from agent.trading_agent import TradingAgent

logger = logging.getLogger(__name__)

MAX_LOG_ENTRIES = 100


def _get_band(score: float) -> str:
    """Map a risk score to its named band."""
    if score < RISK_THRESHOLDS["low"]:
        return "low"
    elif score < RISK_THRESHOLDS["medium"]:
        return "medium"
    else:
        return "high"


class ActivityEntry:
    """A single autopilot activity log entry."""

    def __init__(
        self,
        kind: str,
        message: str,
        risk_score: float | None = None,
        trades_made: int = 0,
    ):
        self.timestamp = datetime.utcnow()
        self.kind = kind          # "monitoring" | "reactive" | "routine" | "error"
        self.message = message
        self.risk_score = risk_score
        self.trades_made = trades_made

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "kind": self.kind,
            "message": self.message,
            "risk_score": self.risk_score,
            "trades_made": self.trades_made,
        }


class Autopilot:
    """
    Background autopilot that continuously monitors geopolitical risk
    and triggers buy/sell decisions in real-time.

    Two trigger modes:
    - Reactive: fires immediately when risk band changes or a large score
                move (>= risk_change_threshold) is detected.
    - Routine:  fires periodically (routine_interval_seconds) even when
                risk is stable, to catch technical opportunities.
    """

    def __init__(
        self,
        agent: TradingAgent,
        poll_interval_seconds: int = AUTOPILOT_POLL_INTERVAL,
        routine_interval_seconds: int = AUTOPILOT_ROUTINE_INTERVAL,
        risk_change_threshold: float = AUTOPILOT_RISK_CHANGE_THRESHOLD,
    ):
        self.agent = agent
        self.poll_interval = poll_interval_seconds
        self.routine_interval = routine_interval_seconds
        self.risk_change_threshold = risk_change_threshold

        self.is_running: bool = False
        self.previous_risk: float = 50.0
        self.current_risk: float = 50.0
        self.last_analysis_time: datetime | None = None
        self.last_action_time: datetime | None = None

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._log_lock = threading.Lock()
        self._activity_log: list[ActivityEntry] = []

    # ------------------------------------------------------------------
    # Public control API
    # ------------------------------------------------------------------

    def start(self):
        """Start the autopilot background thread."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, name="AutopilotThread", daemon=True
        )
        self._thread.start()
        self.is_running = True
        self._log("monitoring", "Autopilot started.")
        logger.info("Autopilot started.")

    def stop(self):
        """Stop the autopilot background thread."""
        if not self.is_running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self.is_running = False
        self._log("monitoring", "Autopilot stopped.")
        logger.info("Autopilot stopped.")

    def get_activity_log(self, limit: int = 50) -> list[dict]:
        with self._log_lock:
            return [e.to_dict() for e in self._activity_log[-limit:]][::-1]

    def update_settings(
        self,
        poll_interval: int | None = None,
        routine_interval: int | None = None,
        risk_threshold: float | None = None,
    ):
        """Hot-update settings without restarting the thread."""
        if poll_interval is not None:
            self.poll_interval = poll_interval
        if routine_interval is not None:
            self.routine_interval = routine_interval
        if risk_threshold is not None:
            self.risk_change_threshold = risk_threshold

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _loop(self):
        """Main loop -- runs in the background thread."""
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Autopilot tick error: {e}", exc_info=True)
                self._log("error", f"Tick error: {e}")

            # Sleep in small increments so stop() is responsive
            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

    def _tick(self):
        """One iteration: fetch risk, decide whether to trade."""
        from mcp_servers.geopolitical_server import get_geopolitical_risk_score

        raw = get_geopolitical_risk_score()
        risk_data = json.loads(raw)

        if "error" in risk_data:
            self._log("error", f"Risk fetch failed: {risk_data['error']}")
            return

        new_score = risk_data.get("composite_score", 50.0)
        self.current_risk = new_score

        prev_band = _get_band(self.previous_risk)
        new_band = _get_band(new_score)
        band_changed = prev_band != new_band
        big_move = abs(new_score - self.previous_risk) >= self.risk_change_threshold

        now = datetime.utcnow()
        time_since_routine = (
            (now - self.last_analysis_time).total_seconds()
            if self.last_analysis_time
            else self.routine_interval + 1
        )

        if band_changed or big_move:
            direction = "INCREASED" if new_score > self.previous_risk else "DECREASED"
            self._log(
                "reactive",
                f"Risk {direction}: {self.previous_risk:.0f} → {new_score:.0f} "
                f"(band: {prev_band} → {new_band}). Triggering reactive trade cycle.",
                risk_score=new_score,
            )
            self._run_reactive_cycle(new_score, prev_band, new_band, risk_data)

        elif time_since_routine >= self.routine_interval:
            self._log(
                "routine",
                f"Routine cycle triggered. Risk stable at {new_score:.0f} ({new_band}).",
                risk_score=new_score,
            )
            self._run_routine_cycle(new_score)

        else:
            next_routine_in = int(self.routine_interval - time_since_routine)
            self._log(
                "monitoring",
                f"Risk stable at {new_score:.0f} ({new_band}). "
                f"Next routine check in {next_routine_in}s.",
                risk_score=new_score,
            )

        self.previous_risk = new_score

    def _run_reactive_cycle(
        self,
        new_score: float,
        prev_band: str,
        new_band: str,
        risk_data: dict,
    ):
        """Trigger an urgent Gemini analysis because risk changed meaningfully."""
        try:
            self.agent._register_tools()

            portfolio = self.agent._execute_tool_call("get_portfolio", {})
            balance = self.agent._execute_tool_call("get_account_balance", {})
            direction = "INCREASED" if new_score > self.previous_risk else "DECREASED"

            prompt = REACTIVE_PROMPT.format(
                prev_score=self.previous_risk,
                new_score=new_score,
                direction=direction,
                prev_band=prev_band.upper(),
                new_band=new_band.upper(),
                portfolio=portfolio,
                balance=balance,
                watchlist=", ".join(self.agent.watchlist),
            )

            result = self.agent.run_analysis(custom_prompt=prompt)
            trades_made = self._count_trades_in_result(result)

            self.last_analysis_time = datetime.utcnow()
            self.last_action_time = datetime.utcnow()

            self._update_last_log_trades(trades_made)
            logger.info(
                f"Reactive cycle complete. Risk: {new_score:.0f}, Trades: {trades_made}"
            )
        except Exception as e:
            logger.error(f"Reactive cycle error: {e}", exc_info=True)
            self._log("error", f"Reactive cycle failed: {e}", risk_score=new_score)

    def _run_routine_cycle(self, current_score: float):
        """Trigger a standard periodic Gemini analysis cycle."""
        try:
            self.agent._register_tools()

            portfolio = self.agent._execute_tool_call("get_portfolio", {})
            balance = self.agent._execute_tool_call("get_account_balance", {})

            prompt = ANALYSIS_PROMPT.format(
                portfolio=portfolio,
                balance=balance,
                watchlist=", ".join(self.agent.watchlist),
            )

            result = self.agent.run_analysis(custom_prompt=prompt)
            trades_made = self._count_trades_in_result(result)

            self.last_analysis_time = datetime.utcnow()
            self.last_action_time = datetime.utcnow()

            self._update_last_log_trades(trades_made)
            logger.info(
                f"Routine cycle complete. Risk: {current_score:.0f}, Trades: {trades_made}"
            )
        except Exception as e:
            logger.error(f"Routine cycle error: {e}", exc_info=True)
            self._log("error", f"Routine cycle failed: {e}", risk_score=current_score)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(
        self,
        kind: str,
        message: str,
        risk_score: float | None = None,
        trades_made: int = 0,
    ):
        entry = ActivityEntry(
            kind=kind,
            message=message,
            risk_score=risk_score,
            trades_made=trades_made,
        )
        with self._log_lock:
            self._activity_log.append(entry)
            if len(self._activity_log) > MAX_LOG_ENTRIES:
                self._activity_log = self._activity_log[-MAX_LOG_ENTRIES:]

    def _update_last_log_trades(self, trades_made: int):
        """Retroactively update trades_made on the last log entry."""
        with self._log_lock:
            if self._activity_log:
                self._activity_log[-1].trades_made = trades_made

    def _count_trades_in_result(self, result: dict) -> int:
        """Count how many trades were executed in the last analysis cycle."""
        try:
            from mcp_servers.trade_server import get_trade_history
            history = json.loads(get_trade_history(5))
            if not history:
                return 0
            last_ts = self.last_analysis_time
            if last_ts is None:
                return 0
            recent = [
                t for t in history
                if datetime.fromisoformat(t["timestamp"]) >= last_ts
            ]
            return len(recent)
        except Exception:
            return 0
