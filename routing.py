from urllib.parse import quote

import requests


VEHICLE_TOLL_RATE_PER_PLAZA = {
    "car_jeep_van": 90,
    "lcv": 145,
    "bus_truck": 300,
    "multi_axle": 470,
    "bike": 0,
    "cycle": 0,
}

VEHICLE_CLASS_LABELS = {
    "car_jeep_van": "Car/Jeep/Van",
    "lcv": "LCV",
    "bus_truck": "Bus/Truck",
    "multi_axle": "Multi-axle",
    "bike": "Bike (Motorbike)",
    "cycle": "Cycle (Bicycle)",
}


def format_duration(minutes):
    total_minutes = int(round(minutes))
    hours = total_minutes // 60
    mins = total_minutes % 60
    return f"{hours} hr {mins} min"


def estimate_toll_count(distance_km):
    # Heuristic estimate for intercity India driving: about one toll plaza every ~45 km.
    if distance_km < 30:
        return 0
    return max(1, int(round(distance_km / 45)))


def estimate_toll_fare(toll_count, vehicle_class):
    if vehicle_class not in VEHICLE_TOLL_RATE_PER_PLAZA:
        raise ValueError(
            "Invalid vehicle_class. Use one of: "
            + ", ".join(VEHICLE_TOLL_RATE_PER_PLAZA.keys())
        )

    return toll_count * VEHICLE_TOLL_RATE_PER_PLAZA[vehicle_class]


def apply_traffic_multiplier(duration_min, traffic_factor=1.55):
    # Apply traffic factor to account for delays (default 1.55 = 55% delay)
    return duration_min * traffic_factor


def geocode_place(api_key, place):
    encoded_place = quote(place)
    url = f"https://api.maptiler.com/geocoding/{encoded_place}.json?key={api_key}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    features = data.get("features", [])
    if not features:
        return None

    # MapTiler returns coordinates as [longitude, latitude].
    lon, lat = features[0]["center"]
    return {"name": features[0].get("place_name", place), "lat": lat, "lon": lon}


def get_route_alternatives(origin_point, destination_point, mode="driving"):
    # OSRM provides multiple alternatives for different travel modes.
    url = (
        f"https://router.project-osrm.org/route/v1/{mode}/"
        f"{origin_point['lon']},{origin_point['lat']};"
        f"{destination_point['lon']},{destination_point['lat']}"
        "?alternatives=true&steps=true&overview=full&geometries=geojson"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok":
        return []

    return data.get("routes", [])


def find_shortest_path(api_key, origin, destination, vehicle_class="car_jeep_van"):
    if vehicle_class not in VEHICLE_TOLL_RATE_PER_PLAZA:
        raise ValueError(
            "Invalid vehicle_class. Use one of: "
            + ", ".join(VEHICLE_TOLL_RATE_PER_PLAZA.keys())
        )

    origin_point = geocode_place(api_key, origin)
    destination_point = geocode_place(api_key, destination)

    if not origin_point or not destination_point:
        return None

    modes = {
        "driving": {"traffic_factor": 1.55, "avg_speed_kmh": 75},
        "cycling": {"traffic_factor": 1.0, "avg_speed_kmh": 20},
        "foot": {"traffic_factor": 1.0, "avg_speed_kmh": 5},
    }

    result_data = {
        "origin": origin_point,
        "destination": destination_point,
        "selected_vehicle_class": vehicle_class,
        "modes": {},
    }

    for mode, config in modes.items():
        routes = get_route_alternatives(origin_point, destination_point, mode)
        if not routes:
            result_data["modes"][mode] = None
            continue

        shortest_route = min(routes, key=lambda r: r["distance"])
        shortest_route_distance = shortest_route["distance"] / 1000

        alternatives = []
        if mode == "driving":
            for route in routes:
                alternatives.append(
                    {
                        "distance_km": route.get("distance", 0) / 1000,
                        "duration_min": route.get("duration", 0) / 60,
                        "geometry": route.get("geometry", {}).get("coordinates", []),
                        "is_shortest": route is shortest_route,
                    }
                )

        # Calculate approximate duration based on mode's typical speed.
        base_duration = (shortest_route_distance / config["avg_speed_kmh"]) * 60
        traffic_duration = apply_traffic_multiplier(base_duration, config["traffic_factor"])

        # Only calculate tolls for driving mode with motor vehicles (not bikes/cycles)
        if mode == "driving" and vehicle_class in ["car_jeep_van", "lcv", "bus_truck", "multi_axle"]:
            toll_count = estimate_toll_count(shortest_route_distance)
            toll_fare = estimate_toll_fare(toll_count, vehicle_class)
        else:
            toll_count = 0
            toll_fare = 0

        steps = []
        step_path_coordinates = []
        for leg in shortest_route.get("legs", []):
            for step in leg.get("steps", []):
                maneuver = step.get("maneuver", {})
                instruction = maneuver.get("instruction")
                if not instruction:
                    direction = maneuver.get("modifier", "")
                    step_name = step.get("name", "")
                    instruction = f"{maneuver.get('type', 'continue')} {direction} {step_name}".strip()

                maneuver_location = maneuver.get("location")
                if isinstance(maneuver_location, list) and len(maneuver_location) == 2:
                    step_path_coordinates.append(maneuver_location)

                steps.append(
                    {
                        "instruction": instruction,
                        "distance_km": step.get("distance", 0) / 1000,
                        "geometry": step.get("geometry", {}).get("coordinates", []),
                        "maneuver_location": maneuver_location,
                    }
                )

        # Ensure the destination is included in the connected step line.
        destination_coord = [destination_point["lon"], destination_point["lat"]]
        if not step_path_coordinates or step_path_coordinates[-1] != destination_coord:
            step_path_coordinates.append(destination_coord)

        result_data["modes"][mode] = {
            "distance_km": shortest_route_distance,
            "base_duration_min": base_duration,
            "traffic_duration_min": traffic_duration,
            "estimated_toll_count": toll_count,
            "toll_fare_inr": toll_fare,
            "toll": {"count": toll_count, "fare_inr": toll_fare},
            "route_geometry": shortest_route.get("geometry", {}).get("coordinates", []),
            "step_path_coordinates": step_path_coordinates,
            "steps": steps,
            "alternatives": alternatives,
        }

    return result_data
