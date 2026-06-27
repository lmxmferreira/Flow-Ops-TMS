from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
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
