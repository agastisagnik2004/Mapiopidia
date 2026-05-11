from routing import VEHICLE_CLASS_LABELS, find_shortest_path, format_duration


# Example usage
api_key = "4LTxwIKBMtXtHZkO3INT"
origin = "Nandakumar, West Bengal, India"
destination = "Delhi, India"
vehicle_class = "car_jeep_van"  # car_jeep_van | lcv | bus_truck | multi_axle

result = find_shortest_path(api_key, origin, destination, vehicle_class)

if result:
    print(f"Origin: {result['origin']['name']} ({result['origin']['lat']:.5f}, {result['origin']['lon']:.5f})")
    print(
        f"Destination: {result['destination']['name']} "
        f"({result['destination']['lat']:.5f}, {result['destination']['lon']:.5f})"
    )

    mode_names = {"driving": "Driving", "cycling": "Cycling", "foot": "Walking"}

    for mode, display_name in mode_names.items():
        if result["modes"][mode]:
            mode_data = result["modes"][mode]
            print(f"\n{display_name}:")
            print(f"  Distance: {mode_data['distance_km']:.2f} km")
            print(f"  Base time: {format_duration(mode_data['base_duration_min'])}")
            if mode == "driving":
                selected_class = result["selected_vehicle_class"]
                class_label = VEHICLE_CLASS_LABELS[selected_class]
                print(f"  With traffic (55% delay): {format_duration(mode_data['traffic_duration_min'])}")
                print(f"  Approx time: {format_duration(mode_data['traffic_duration_min'])}")
                print(f"  Vehicle class: {class_label} ({selected_class})")
                print(f"  Estimated toll plazas: {mode_data['estimated_toll_count']}")
                print(f"  Estimated toll fare: Rs {mode_data['toll_fare_inr']:.2f}")
            else:
                print(f"  Approx time: {format_duration(mode_data['traffic_duration_min'])}")
        else:
            print(f"\n{display_name}: Route not available")

    print("\nStep-by-step directions for driving:")
    if result["modes"]["driving"]:
        for idx, step in enumerate(result["modes"]["driving"]["steps"], start=1):
            print(f"{idx}. {step['instruction']} ({step['distance_km']:.2f} km)")
else:
    print("Could not resolve locations or fetch route paths.")
