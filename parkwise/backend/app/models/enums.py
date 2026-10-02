from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    ATTENDANT = "ATTENDANT"
    STUDENT = "STUDENT"
    STAFF = "STAFF"
    VISITOR = "VISITOR"


class VehicleType(StrEnum):
    CAR = "CAR"
    MOTORCYCLE = "MOTORCYCLE"
    BICYCLE = "BICYCLE"
    VAN = "VAN"
    EV = "EV"
    ACCESSIBLE = "ACCESSIBLE"


class SlotStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class ParkingSessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class EntryMethod(StrEnum):
    QR = "QR"
    MANUAL = "MANUAL"
    SELF_SERVICE = "SELF_SERVICE"


class GateType(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    BOTH = "BOTH"


class GateDirection(StrEnum):
    IN = "IN"
    OUT = "OUT"


class ScanType(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"


class ScanResult(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class FeedbackCategory(StrEnum):
    AVAILABILITY = "AVAILABILITY"
    SAFETY = "SAFETY"
    CLEANLINESS = "CLEANLINESS"
    ACCESSIBILITY = "ACCESSIBILITY"
    OTHER = "OTHER"


class FeedbackStatus(StrEnum):
    OPEN = "OPEN"
    REVIEWED = "REVIEWED"
    RESOLVED = "RESOLVED"
