import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from routing import VEHICLE_CLASS_LABELS, find_shortest_path, format_duration

# Load environment variables from .env file
load_dotenv()

MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")
if not MAPTILER_API_KEY:
    raise ValueError("MAPTILER_API_KEY environment variable is not set. Please create a .env file with your API key.")

app = FastAPI(title="Route Planner API")
templates = Jinja2Templates(directory="templates")


class RouteRequest(BaseModel):
    origin: str
    destination: str
    vehicle_class: str = "car_jeep_van"


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

    # Add a human-readable vehicle class label for the UI
    result["selected_vehicle_class_label"] = VEHICLE_CLASS_LABELS.get(payload.vehicle_class, payload.vehicle_class)

    # Add pre-formatted durations for easier UI rendering.
    for mode_data in result["modes"].values():
        if mode_data:
            mode_data["base_duration_hm"] = format_duration(mode_data["base_duration_min"])
            mode_data["traffic_duration_hm"] = format_duration(mode_data["traffic_duration_min"])

    return result
