from enum import Enum

class TableState(Enum):
    FREE = "FREE"
    HOLD_15MIN = "HOLD_15MIN"
    RESERVED = "RESERVED"
    OCCUPIED = "OCCUPIED"
    AWAITING_BILL = "AWAITING_BILL"
    CLEARED = "CLEARED"

TRANSITIONS = {
    TableState.FREE: [TableState.HOLD_15MIN],
    TableState.HOLD_15MIN: [TableState.RESERVED, TableState.FREE],
    TableState.RESERVED: [TableState.OCCUPIED, TableState.FREE],
    TableState.OCCUPIED: [TableState.AWAITING_BILL],
    TableState.AWAITING_BILL: [TableState.CLEARED],
    TableState.CLEARED: [TableState.FREE],
}

class InvalidTransitionError(Exception):
    pass

def can_transition(current: TableState, target: TableState) -> bool:
    return target in TRANSITIONS.get(current, [])

def transition(current: TableState, target: TableState) -> TableState:
    if not can_transition(current, target):
        raise InvalidTransitionError(f"{current.value} -> {target.value} forbidden")
    return target