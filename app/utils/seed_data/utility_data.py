from app.models.enums import StatusEnum, Tags


STATUSES = [
    StatusEnum.ACTIVE,
    StatusEnum.INACTIVE,
    StatusEnum.PENDING,
    StatusEnum.BOOKED,
    StatusEnum.DELIVERED,
    StatusEnum.RETURNING,
    StatusEnum.PAID,
    StatusEnum.RETURNED,
    StatusEnum.COMPLETED,
    StatusEnum.CANCELLED,
    StatusEnum.REJECTED,
    StatusEnum.REFUNDING,
    StatusEnum.REFUNDED,
    StatusEnum.CHARGED,
    StatusEnum.INITIATED,
    StatusEnum.SETTLED,
    StatusEnum.READ,
    StatusEnum.UNREAD,
    StatusEnum.RESPONDED,
]

TAGS = [Tags.ROOKIE, Tags.TRAVELER, Tags.PRO]
CATEGORIES = ["SUV", "Sedan", "Hatchback", "Electric"]
FUEL_TYPES = ["Petrol", "Diesel", "Electric"]
CAPACITIES = [2, 4, 5, 6, 7, 8]

COLORS = [
    "White",
    "Black",
    "Silver",
    "Red",
    "Blue",
    "Gray",
    "Brown",
    "Green",
    "Yellow",
    "Orange",
]

FEATURES = [
    "Air Conditioning",
    "Power Steering",
    "Airbags",
    "Sunroof",
    "GPS Navigation",
    "Bluetooth",
    "Rear Camera",
    "Leather Seats",
    "Keyless Entry",
    "Parking Sensors",
    "Cruise Control",
    "Alloy Wheels",
    "360 Camera",
    "Fast Charging",
    "Bose Speakers",
    "Touchscreen",
]

__all__ = ["STATUSES", "TAGS", "CATEGORIES", "FUEL_TYPES", "CAPACITIES", "COLORS", "FEATURES"]