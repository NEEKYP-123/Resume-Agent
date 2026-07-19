from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth_routes, resumes, settings_routes, job_routes, user_routes, usage_routes

app = FastAPI(title="Resume Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(resumes.router)
app.include_router(settings_routes.router)
app.include_router(job_routes.router)
app.include_router(user_routes.router)
app.include_router(usage_routes.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
