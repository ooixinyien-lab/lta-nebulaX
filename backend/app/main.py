from fastapi import FastAPI
from app.ps1.ps1_routes import router as ps1_router

app = FastAPI(title="NEBULA X Rail Scheduling Engine")

# Include the PS1 CSV Ingestion endpoints
app.include_router(ps1_router)

@app.get("/")
def root():
    return {"status": "online", "system": "NEBULA X Ingestion Engine"}