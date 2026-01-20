"""
Shared module for canvas skills integration.

This module provides common infrastructure for agent-eyes, agent-canvas, and canvas-edit.
"""

from .canvas_bus import (
    SCHEMA_VERSION,
    CANVAS_BUS_JS,
    get_timestamp,
    generate_session_id,
    create_event,
    get_canvas_bus_js,
    inject_canvas_bus,
    drain_bus_events,
    get_bus_change_log,
    reset_bus_change_log,
    set_capture_mode,
    get_bus_state,
)

__all__ = [
    "SCHEMA_VERSION",
    "CANVAS_BUS_JS",
    "get_timestamp",
    "generate_session_id",
    "create_event",
    "get_canvas_bus_js",
    "inject_canvas_bus",
    "drain_bus_events",
    "get_bus_change_log",
    "reset_bus_change_log",
    "set_capture_mode",
    "get_bus_state",
]
