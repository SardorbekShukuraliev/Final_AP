from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional
from .state_machine import TableState
from uuid import uuid4

class OrderStatus(Enum):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    READY_TO_SERVE = "READY_TO_SERVE"

class PaymentMethod(Enum):
    ONLINE = "ONLINE"
    CASH = "CASH"

class Allergen(Enum):
    GLUTEN = "gluten"
    LACTOSE = "lactose"
    NUTS = "nuts"
    EGGS = "eggs"

@dataclass
class MenuItem:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    base_price: float = 0.0
    category: str = ""

@dataclass
class Table:
    id: str
    capacity: int
    state: TableState = TableState.FREE
    reservation_time: Optional[str] = None  # слот, например "19:00-21:00"
    lock_holder: Optional[str] = None       # id бронирующего

@dataclass
class Order:
    id: str = field(default_factory=lambda: str(uuid4()))
    table_id: str = ""
    items: List[dict] = field(default_factory=list)   # [{"item_id":..., "customizations":[...]}]
    status: OrderStatus = OrderStatus.PENDING
    payment_method: Optional[PaymentMethod] = None

@dataclass
class KitchenCommand:
    """Команда для кухни (Command pattern)."""
    def execute(self): raise NotImplementedError
    def undo(self): raise NotImplementedError

@dataclass
class AcceptOrder(KitchenCommand):
    order: Order
    def execute(self):
        if self.order.status == OrderStatus.PENDING:
            self.order.status = OrderStatus.PREPARING
    def undo(self):
        if self.order.status == OrderStatus.PREPARING:
            self.order.status = OrderStatus.PENDING

@dataclass
class MarkReady(KitchenCommand):
    order: Order
    def execute(self):
        if self.order.status == OrderStatus.PREPARING:
            self.order.status = OrderStatus.READY_TO_SERVE
    def undo(self):
        if self.order.status == OrderStatus.READY_TO_SERVE:
            self.order.status = OrderStatus.PREPARING