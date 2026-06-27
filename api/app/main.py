from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    exc_yard,
    financials,
    billing,
    freight_audit,
    freight_audit,
    execution,
    allocation,
    carrier_invoices,
    carrier_management,
    core_platform,
    e2e,
    master_data,
    documents,
    rating,
    auth, shipments, carriers, dispatches,
    oms_events, purchase_orders, order_releases,
    organizations, workflows, status_models, numbering, global_settings
)

app = FastAPI(title="Flow Ops TMS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(exc_yard.router,        prefix="/api/v1/ops",               tags=["exc-yard"])
app.include_router(financials.router,       prefix="/api/v1/financials",         tags=["financials"])
app.include_router(billing.router,          prefix="/api/v1/billing",            tags=["billing"])
app.include_router(freight_audit.router,   prefix="/api/v1/audit",             tags=["freight-audit"])
app.include_router(exc_yard.router,        prefix="/api/v1/ops",               tags=["exc-yard"])
app.include_router(financials.router,       prefix="/api/v1/financials",         tags=["financials"])
app.include_router(billing.router,          prefix="/api/v1/billing",            tags=["billing"])
app.include_router(freight_audit.router,   prefix="/api/v1/audit",             tags=["freight-audit"])
app.include_router(execution.router,       prefix="/api/v1/execution",         tags=["execution"])
app.include_router(allocation.router,       prefix="/api/v1/allocation",         tags=["allocation"])
app.include_router(carrier_invoices.router,    prefix="/api/v1/carrier-invoices",  tags=["carrier-invoices"])
app.include_router(carrier_management.router, prefix="/api/v1/carrier-mgmt",    tags=["carrier-management"])
app.include_router(core_platform.router,  prefix="/api/v1/core",              tags=["core"])
app.include_router(e2e.router,            prefix="/api/v1/e2e",               tags=["e2e"])
app.include_router(master_data.router,     prefix="/api/v1/master-data",      tags=["master-data"])
app.include_router(documents.router,       prefix="/api/v1/documents",        tags=["documents"])
app.include_router(rating.router,           prefix="/api/v1/rating",            tags=["rating"])
app.include_router(auth.router,            prefix="/api/v1/auth",            tags=["auth"])
app.include_router(shipments.router,       prefix="/api/v1/shipments",       tags=["shipments"])
app.include_router(purchase_orders.router, prefix="/api/v1/purchase-orders", tags=["purchase-orders"])
app.include_router(order_releases.router,  prefix="/api/v1/order-releases",  tags=["order-releases"])
app.include_router(organizations.router,   prefix="/api/v1/organizations",   tags=["organizations"])
app.include_router(workflows.router,       prefix="/api/v1/workflows",       tags=["workflows"])
app.include_router(status_models.router,   prefix="/api/v1/status-models",   tags=["status-models"])
app.include_router(numbering.router,       prefix="/api/v1/numbering",       tags=["numbering"])
app.include_router(global_settings.router, prefix="/api/v1/global",          tags=["global-settings"])
app.include_router(carriers.router,        prefix="/api/v1/carriers",        tags=["carriers"])
app.include_router(dispatches.router,      prefix="/api/v1/dispatches",      tags=["dispatches"])
app.include_router(oms_events.router,      prefix="/api/v1/oms-events",      tags=["oms-events"])

@app.get("/health")
async def health():
    return {"status": "ok", "service": "flow-ops-tms"}
