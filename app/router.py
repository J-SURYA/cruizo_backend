from fastapi import APIRouter
from app.api.routes import (
    backup_routes,
    content_routes,
    auth_routes,
    rbac_routes,
    user_routes,
    inventory_routes,
    booking_routes,
    payment_routes,
    query_routes,
    notification_routes,
    chat_routes,
)

# Master router that bundles all service routers
router = APIRouter()

router.include_router(auth_routes.router, prefix="/auth", tags=["Authentication"])
router.include_router(user_routes.router, prefix="/users", tags=["Users"])
router.include_router(rbac_routes.router, prefix="/admin", tags=["Authorization"])
router.include_router(
    inventory_routes.router, prefix="/admin", tags=["Car Inventory - Admin"]
)
router.include_router(booking_routes.router, prefix="/bookings", tags=["Bookings"])
router.include_router(payment_routes.router, prefix="/payments", tags=["Payments"])
router.include_router(query_routes.router, prefix="/queries", tags=["Customer Queries"])
router.include_router(
    notification_routes.router, prefix="/notifications", tags=["Notifications"]
)
router.include_router(
    content_routes.router, prefix="/content", tags=["Content Management"]
)
router.include_router(
    backup_routes.router, prefix="/backups", tags=["Backup and Recovery"]
)
router.include_router(chat_routes.router, prefix="/chat", tags=["AI Chat Assistant"])
