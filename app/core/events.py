"""
VaidyaMD HMS — Asynchronous In-Process Event Bus
Enables decoupled, pub-sub communication between core domains and plugins.
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Callable, Coroutine, Any, Type, Dict, List
from pydantic import BaseModel, Field

logger = logging.getLogger("vaidyamd.events")


class BaseEvent(BaseModel):
    """Base class for all domain events across the HMS system."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tenant_id: str | None = None


# ==============================================================================
# Domain Events
# ==============================================================================

class AppointmentStatusChangedEvent(BaseEvent):
    appointment_id: str
    patient_id: str
    doctor_id: str | None = None
    department: str | None = None
    old_status: str | None = None
    new_status: str


class InvoiceCreatedEvent(BaseEvent):
    invoice_id: str
    invoice_number: str
    patient_id: str
    amount: float
    status: str
    appointment_source: str | None = None


class PatientAdmittedEvent(BaseEvent):
    admission_id: str
    patient_id: str
    ward_id: str
    bed_id: str


class LabReportAuthorizedEvent(BaseEvent):
    record_id: str
    patient_id: str
    authorized_by: str


# ==============================================================================
# Event Bus Implementation
# ==============================================================================

class EventBus:
    """
    Lightweight, thread-safe asynchronous Event Bus.
    Allows services to publish events and handlers to react without direct coupling.
    """

    def __init__(self):
        self._handlers: Dict[Type[BaseEvent], List[Callable[[Any], Coroutine]]] = {}

    def subscribe(self, event_type: Type[BaseEvent], handler: Callable[[Any], Coroutine]):
        """Register an async handler function for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"Registered subscriber for event: {event_type.__name__} -> {handler.__name__}")

    async def publish(self, event: BaseEvent):
        """
        Publish an event to all registered subscribers.
        Executes all handlers concurrently with isolated exception safety.
        """
        event_cls = type(event)
        handlers = self._handlers.get(event_cls, [])
        if not handlers:
            return

        logger.debug(f"Publishing event {event_cls.__name__} (ID: {event.event_id}) to {len(handlers)} handler(s)")

        async def _safe_execute(handler: Callable[[Any], Coroutine]):
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Error in event handler {handler.__name__} for event {event_cls.__name__} (ID: {event.event_id}): {e}",
                    exc_info=True,
                )

        # Run handlers concurrently without blocking primary transaction
        await asyncio.gather(*[_safe_execute(h) for h in handlers], return_exceptions=True)

    def publish_background(self, event: BaseEvent):
        """Dispatches event publication to the background asyncio event loop."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event))
        except RuntimeError:
            # If no running event loop, create task or pass
            asyncio.run(self.publish(event))


# Global Singleton Event Bus Instance
event_bus = EventBus()
