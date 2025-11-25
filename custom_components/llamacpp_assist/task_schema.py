"""Task schema definitions for the multi-agent architecture."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


TaskType = Literal[
    "device_control",
    "shopping_add",
    "shopping_query",
    "shopping_remove",
    "calendar_query",
    "calendar_create",
    "memory_read",
    "memory_write",
]

TaskStatus = Literal[
    "pending",
    "awaiting_selection",
    "ready_for_execution",
    "executed",
    "failed",
]


@dataclass
class Task:
    """Base task structure."""
    
    id: str
    type: TaskType
    status: TaskStatus = "pending"


@dataclass
class DeviceControlTask(Task):
    """Task for controlling Home Assistant devices."""
    
    type: TaskType = "device_control"
    action: Literal["turn_on", "turn_off", "toggle", "set"] = "turn_on"
    raw_targets: list[str] = field(default_factory=list)
    domain: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    
    # After Resolver
    available_entities: list[dict[str, Any]] = field(default_factory=list)
    service_schema: dict[str, Any] = field(default_factory=dict)
    
    # After Selection Agent
    selected_entities: list[str] = field(default_factory=list)
    service_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ShoppingAddTask(Task):
    """Task for adding items to shopping list."""
    
    type: TaskType = "shopping_add"
    raw_items: str = ""
    
    # After Resolver (always split)
    items: list[str] = field(default_factory=list)


@dataclass
class ShoppingQueryTask(Task):
    """Task for querying shopping list."""
    
    type: TaskType = "shopping_query"


@dataclass
class ShoppingRemoveTask(Task):
    """Task for removing item from shopping list."""
    
    type: TaskType = "shopping_remove"
    item: str = ""


@dataclass
class CalendarQueryTask(Task):
    """Task for querying calendar events."""
    
    type: TaskType = "calendar_query"
    start: str | None = None
    end: str | None = None
    query: str | None = None
    
    # After Resolver
    start_iso: str | None = None
    end_iso: str | None = None


@dataclass
class CalendarCreateTask(Task):
    """Task for creating calendar event."""
    
    type: TaskType = "calendar_create"
    calendar_entity: str | None = None
    summary: str = ""
    start: str = ""
    end: str = ""
    description: str | None = None
    location: str | None = None
    
    # After Resolver
    available_calendars: list[dict[str, str]] = field(default_factory=list)
    start_iso: str | None = None
    end_iso: str | None = None
    
    # After Selection Agent
    selected_calendar: str | None = None


@dataclass
class MemoryReadTask(Task):
    """Task for reading from memory."""
    
    type: TaskType = "memory_read"
    key: str = ""


@dataclass
class MemoryWriteTask(Task):
    """Task for writing to memory."""
    
    type: TaskType = "memory_write"
    key: str = ""
    value: str = ""


def task_from_dict(data: dict[str, Any]) -> Task:
    """Create a Task instance from a dictionary."""
    task_type = data.get("type")
    
    if task_type == "device_control":
        return DeviceControlTask(**data)
    elif task_type == "shopping_add":
        return ShoppingAddTask(**data)
    elif task_type == "shopping_query":
        return ShoppingQueryTask(**data)
    elif task_type == "shopping_remove":
        return ShoppingRemoveTask(**data)
    elif task_type == "calendar_query":
        return CalendarQueryTask(**data)
    elif task_type == "calendar_create":
        return CalendarCreateTask(**data)
    elif task_type == "memory_read":
        return MemoryReadTask(**data)
    elif task_type == "memory_write":
        return MemoryWriteTask(**data)
    else:
        # Fallback for unknown types
        return Task(**data)
