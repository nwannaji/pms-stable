from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import os
import logging
from decouple import config
from dotenv import load_dotenv
from utils.limiter import limiter
load_dotenv()
# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from database import create_tables
from routers import auth, users, roles, organization, initiatives, goals, goal_tags, reviews, performance, notifications, analytics, reports

# Read CORS origins from environment variable, with fallback to .env file
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000").split(",")

# Strip whitespace from each origin
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ALLOWED_ORIGINS]
print(CORS_ALLOWED_ORIGINS)

# Log CORS configuration for debugging
logger.info(f"CORS Allowed Origins: {CORS_ALLOWED_ORIGINS}")

app = FastAPI(
    title="NIGCOMSAT PMS API",
    description="Performance Management System for Nigerian Communications Satellite Limited",
    version="2.0.0",
    redirect_slashes=False
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Forwarded-Proto", "X-Forwarded-Host"],
    expose_headers=["Content-Disposition"],
)

# Trust X-Forwarded-* headers from IIS reverse proxy
PROXY_HOSTS = config("PROXY_TRUSTED_HOSTS", default="localhost,127.0.0.1").split(",")
PROXY_HOSTS = [h.strip() for h in PROXY_HOSTS]

# Conditionally add HTTPS redirect in production behind reverse proxy
ENVIRONMENT = config("ENVIRONMENT", default="development")
if ENVIRONMENT == "production":
    # When behind IIS with SSL termination, we trust X-Forwarded-Proto
    # Do NOT use HTTPSRedirectMiddleware — IIS handles the redirect to HTTPS
    logger.info("Running in production mode behind reverse proxy")

if not os.path.exists("uploads"):
    os.makedirs("uploads")
app.mount("/api/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(roles.router, prefix="/api/roles", tags=["Roles"])
app.include_router(organization.router, prefix="/api/organization", tags=["Organization"])
app.include_router(initiatives.router, prefix="/api", tags=["Initiatives"])
app.include_router(goals.router, prefix="/api/goals", tags=["Goals"])
app.include_router(goal_tags.router, tags=["Goal Tags"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(performance.router, prefix="/api/performance", tags=["Performance"])
app.include_router(notifications.router, tags=["Notifications"])
app.include_router(analytics.router, prefix="/api", tags=["Analytics"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])

@app.on_event("startup")
async def startup_event():
    """Create database tables on startup"""
    create_tables()

@app.get("/")
async def root():
    return {"message": "NIGCOMSAT PMS API v2.0 - Simplified & Efficient"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "NIGCOMSAT PMS API v2.0"}

if __name__ == "__main__":
    import uvicorn
    # Bind to 0.0.0.0 so the backend is reachable at the public IP (160.226.0.67)
    # as well as localhost, since IIS reverse proxy forwards to the public IP
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=(ENVIRONMENT != "production"))