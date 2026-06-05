
from typing import List
from domain.models import Order, OrderStatus, AcceptOrder, MarkReady, KitchenCommand

class KitchenQueue:
    def __init__(self):
        self.pending: List[Order] = []
        self.history: List[KitchenCommand] = []   # стек команд для undo
        self.redo_stack: List[KitchenCommand] = []

    def add_order(self, order: Order):
        if order.status == OrderStatus.PENDING:
            self.pending.append(order)

    def accept_order(self, order_id: str) -> bool:
        order = next((o for o in self.pending if o.id == order_id), None)
        if not order:
            return False
        cmd = AcceptOrder(order)
        cmd.execute()
        self.history.append(cmd)
        self.redo_stack.clear()
        return True

    def mark_ready(self, order_id: str) -> bool:
        order = next((o for o in self.pending if o.id == order_id and o.status == OrderStatus.PREPARING), None)
        if not order:
            return False
        cmd = MarkReady(order)
        cmd.execute()
        self.history.append(cmd)
        self.redo_stack.clear()
        return True

    def undo(self) -> bool:
        if not self.history:
            return False
        cmd = self.history.pop()
        cmd.undo()
        self.redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        cmd = self.redo_stack.pop()
        cmd.execute()
        self.history.append(cmd)
        return True

    def get_pending_orders(self):
        return self.pending

kitchen_queue = KitchenQueue()