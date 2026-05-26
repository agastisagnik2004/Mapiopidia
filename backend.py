import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from database import (
    get_location_by_share_token,
    get_or_create_share_token,
    get_user_by_token,
    init_db,
    login_user,
    logout_user,
    register_user,
    update_device_info,
)
from mailer import send_location_email
from routing import VEHICLE_CLASS_LABELS, find_shortest_path, format_duration

# ── Startup ──────────────────────────────────────────────────────────────────
load_dotenv()

MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
if not MAPTILER_API_KEY:
    raise ValueError(
        "MAPTILER_API_KEY environment variable is not set. "
        "Please create a .env file with your API key."
    )

init_db()  # ensure tables exist

app = FastAPI(title="Mapiopidia API")
templates = Jinja2Templates(directory="templates")


# ── Pydantic models ───────────────────────────────────────────────────────────

class RouteRequest(BaseModel):
    origin: str
    destination: str
    vehicle_class: str = "car_jeep_van"


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class DeviceInfoRequest(BaseModel):
    token: str
    latitude: float
    longitude: float
    battery_level: float          # 0.0 – 1.0
    battery_charging: bool = False


class ShareLocationRequest(BaseModel):
    token: str                    # sender's session token
    recipient_email: str          # email address to send to


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="map.html",
        context={
            "vehicle_classes": VEHICLE_CLASS_LABELS,
            "maptiler_key": MAPTILER_API_KEY,
        },
    )


@app.get("/auth", response_class=HTMLResponse)
def auth_page(request: Request):
    return templates.TemplateResponse(request=request, name="auth.html", context={})


# ── Auth API ──────────────────────────────────────────────────────────────────

@app.post("/api/register")
def api_register(payload: RegisterRequest):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    if not payload.email.strip() or "@" not in payload.email:
        raise HTTPException(status_code=400, detail="A valid email is required.")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    user = register_user(payload.name.strip(), payload.email.strip(), payload.password)
    if user is None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    return {"message": "Account created successfully.", "user_id": user["id"]}


@app.post("/api/login")
def api_login(payload: LoginRequest):
    user_id, token, name = login_user(payload.email, payload.password)
    if not user_id:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return {"user_id": user_id, "token": token, "name": name}


@app.post("/api/logout")
def api_logout(request: Request):
    token = request.headers.get("X-Session-Token", "")
    if token:
        logout_user(token)
    return {"message": "Logged out."}


@app.get("/api/me")
def api_me(request: Request):
    token = request.headers.get("X-Session-Token", "")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    return user


# ── Device tracking API ───────────────────────────────────────────────────────

@app.post("/api/device/update")
def api_device_update(payload: DeviceInfoRequest):
    user = get_user_by_token(payload.token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    ok = update_device_info(
        payload.token,
        payload.latitude,
        payload.longitude,
        payload.battery_level,
        payload.battery_charging,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update device info.")

    return {"message": "Device info updated.", "user_id": user["id"]}


# ── Location sharing ──────────────────────────────────────────────────────────

@app.post("/api/share-location")
def api_share_location(payload: ShareLocationRequest):
    """Generate a shareable link and email it to the recipient."""
    user = get_user_by_token(payload.token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    if user["latitude"] is None or user["longitude"] is None:
        raise HTTPException(
            status_code=400,
            detail="No location data yet. Allow location access on the map page first.",
        )

    if not payload.recipient_email or "@" not in payload.recipient_email:
        raise HTTPException(status_code=400, detail="A valid recipient email is required.")

    # Get (or create) a persistent share token for this user
    share_token = get_or_create_share_token(payload.token)
    if not share_token:
        raise HTTPException(status_code=500, detail="Could not generate share token.")

    share_url = f"{BASE_URL}/track/{share_token}"

    try:
        send_location_email(
            sender_name=user["name"],
            recipient_email=payload.recipient_email,
            latitude=user["latitude"],
            longitude=user["longitude"],
            battery_level=user["battery_level"] or 0.0,
            battery_charging=user["battery_charging"],
            last_seen=user["last_seen"],
            share_url=share_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Email delivery failed: {exc}",
        ) from exc

    return {
        "message": f"Location shared! Email sent to {payload.recipient_email}.",
        "share_url": share_url,
    }


@app.get("/track/{share_token}", response_class=HTMLResponse)
def track_page(request: Request, share_token: str):
    """Public page that shows a user's last known location on a live map."""
    data = get_location_by_share_token(share_token)
    if not data:
        return HTMLResponse(
            "<h2 style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            "Location not found or not yet shared.</h2>",
            status_code=404,
        )
    return templates.TemplateResponse(
        request=request,
        name="track.html",
        context={
            "maptiler_key": MAPTILER_API_KEY,
            "share_token": share_token,
            "user": data,
        },
    )


@app.get("/api/track/{share_token}")
def api_track(share_token: str):
    """JSON endpoint polled by the track page to refresh location data."""
    data = get_location_by_share_token(share_token)
    if not data:
        raise HTTPException(status_code=404, detail="Location not found.")
    return data


# ── Route API ─────────────────────────────────────────────────────────────────

@app.post("/api/route")
def get_route(payload: RouteRequest):
    try:
        result = find_shortest_path(
            MAPTILER_API_KEY,
            payload.origin,
            payload.destination,
            payload.vehicle_class,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not result:
        raise HTTPException(status_code=404, detail="Could not resolve locations or fetch routes")

    result["selected_vehicle_class_label"] = VEHICLE_CLASS_LABELS.get(
        payload.vehicle_class, payload.vehicle_class
    )
    for mode_data in result["modes"].values():
        if mode_data:
            mode_data["base_duration_hm"] = format_duration(mode_data["base_duration_min"])
            mode_data["traffic_duration_hm"] = format_duration(mode_data["traffic_duration_min"])

    return result
