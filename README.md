# Route Planner Web App

A FastAPI-based route planning application using MapTiler for geocoding and OSRM for routing.

## Features

- Multi-mode route planning (Driving, Cycling, Walking)
- Vehicle class support (Car, Bike, Cycle, LCV, Bus, Truck, Multi-axle)
- Toll estimation based on distance and vehicle type
- Dynamic map visualization with route alternatives
- Step-by-step turn-by-turn directions

## Setup

### Prerequisites

- Python 3.7+
- Virtual environment (recommended)

### Installation

1. Clone or download the project
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate  # Windows
   source .venv/bin/activate  # macOS/Linux
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up your MapTiler API key securely:**

   Create a `.env` file in the project root:
   ```bash
   cp .env.example .env
   ```

   Then edit `.env` and add your MapTiler API key:
   ```
   MAPTILER_API_KEY=your_actual_api_key_here
   ```

   **⚠️ Important:** Never commit `.env` to version control. The `.gitignore` file already prevents this.

### Running the Server

Start the development server:
```bash
python -m uvicorn backend:app --reload --host 127.0.0.1 --port 8000
```

Open your browser and navigate to: `http://127.0.0.1:8000/`

## API Endpoints

### GET `/`
Serves the web UI (map.html)

### POST `/api/route`
Calculates the route between two locations.

**Request:**
```json
{
  "origin": "Nandakumar, West Bengal, India",
  "destination": "Delhi, India",
  "vehicle_class": "car_jeep_van"
}
```

**Response:**
```json
{
  "origin": {"name": "...", "lat": 22.xxx, "lon": 87.xxx},
  "destination": {"name": "...", "lat": 28.xxx, "lon": 77.xxx},
  "selected_vehicle_class": "car_jeep_van",
  "selected_vehicle_class_label": "Car/Jeep/Van",
  "modes": {
    "driving": {
      "distance_km": 1492.84,
      "base_duration_min": 1194.72,
      "traffic_duration_min": 1851.81,
      "toll": {"count": 33, "fare_inr": 2970},
      "route_geometry": [...],
      "step_path_coordinates": [...],
      "steps": [...]
    },
    "cycling": {...},
    "foot": {...}
  }
}
```

## Security

- **API Key Protection:** The MapTiler API key is stored in a `.env` file that is **not** committed to version control
- **Environment Variables:** Use `python-dotenv` to load sensitive configuration from environment variables
- **Validation:** The app requires a valid `MAPTILER_API_KEY` to start

## Files

- `main.py` - CLI example (legacy)
- `backend.py` - FastAPI application
- `routing.py` - Core routing and toll calculation logic
- `templates/map.html` - Web UI
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (local, not committed)
- `.env.example` - Template for environment variables
- `.gitignore` - Git ignore rules

## License

MIT
