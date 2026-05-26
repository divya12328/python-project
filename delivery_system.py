"""
FastBox Delivery System Simulator
==================================
Simulates one day of logistics operations:
  - Reads warehouse, agent, and package data from a JSON file
  - Assigns each package to the nearest available agent
  - Simulates pick-up + delivery, tracking total distance
  - Generates a performance report (saved to report.json)
  - Bonus: ASCII route map, random delays, mid-day new agent, CSV export

Usage:
    python delivery_system.py [data.json]          # default: data.json
    python delivery_system.py base_case.json
    python delivery_system.py test_case_1.json
"""

import json
import math
import sys
import csv
import random
import os



# 1. HELPERS


def euclidean(point_a, point_b):
    """Return the straight-line distance between two [x, y] coordinates."""
    return math.sqrt((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2)



# 2. JSON PARSING  (handles both input formats)

def load_data(filepath):
    """
    Read and normalise the JSON input file.

    Two formats are supported:
      • Dict format  (test cases):  warehouses / agents are plain dicts  {id: [x,y]}
                                    packages use key "warehouse"
      • List format  (base_case):   warehouses / agents are lists of objects {id, location}
                                    packages use key "warehouse_id"

    Returns three plain dicts:
        warehouses  : { "W1": [x, y], ... }
        agents      : { "A1": [x, y], ... }
        packages    : [ {"id": "P1", "warehouse": "W1", "destination": [x, y]}, ... ]
    """
    with open(filepath, "r") as f:
        raw = json.load(f)

    # --- warehouses ---
    wh_raw = raw["warehouses"]
    if isinstance(wh_raw, dict):
        warehouses = {k: v for k, v in wh_raw.items()}          # dict format
    else:
        warehouses = {w["id"]: w["location"] for w in wh_raw}   # list format

    # --- agents ---
    ag_raw = raw["agents"]
    if isinstance(ag_raw, dict):
        agents = {k: v for k, v in ag_raw.items()}
    else:
        agents = {a["id"]: a["location"] for a in ag_raw}

    # --- packages ---
    packages = []
    for p in raw["packages"]:
        packages.append({
            "id":          p["id"],
            "warehouse":   p.get("warehouse") or p.get("warehouse_id"),  # both keys
            "destination": p["destination"],
        })

    return warehouses, agents, packages



# 3. PACKAGE ASSIGNMENT


def assign_packages(packages, warehouses, agents):
    """
    Assign each package to the nearest agent.

    'Nearest' is measured as Euclidean distance from the agent's starting
    position to the package's warehouse location.

    Returns a dict:  { agent_id: [package, ...] }
    """
    assignment = {aid: [] for aid in agents}

    for pkg in packages:
        wh_loc = warehouses[pkg["warehouse"]]

        # Find the agent closest to this package's warehouse
        nearest_agent = min(
            agents.keys(),
            key=lambda aid: euclidean(agents[aid], wh_loc)
        )
        assignment[nearest_agent].append(pkg)

    return assignment



# 4. DELIVERY SIMULATION


def simulate_deliveries(assignment, warehouses, agents, use_delays=False):
    """
    Simulate each agent picking up and delivering their packages.

    Route per agent (per package):
        current_position  →  warehouse  →  destination

    The agent's position is updated after each delivery so multi-package
    routes accumulate correctly.

    If use_delays=True (bonus), a small random delay (0–5 min) is added
    per delivery; this is reported but does not affect distance.

    Returns a dict:
        { agent_id: {"packages_delivered": N,
                     "total_distance": float,
                     "efficiency": float,          # distance per package
                     "delay_minutes": int} }        # bonus field
    """
    results = {}

    for agent_id, pkgs in assignment.items():
        current_pos = list(agents[agent_id])   # mutable copy of starting pos
        total_dist  = 0.0
        total_delay = 0

        for pkg in pkgs:
            wh_loc   = warehouses[pkg["warehouse"]]
            dest_loc = pkg["destination"]

            # Leg 1: current position → warehouse
            total_dist += euclidean(current_pos, wh_loc)

            # Leg 2: warehouse → destination
            total_dist += euclidean(wh_loc, dest_loc)

            # Bonus: random delivery delay
            if use_delays:
                delay = random.randint(0, 5)
                total_delay += delay
                print(f"    [delay] {agent_id} delivering {pkg['id']}: +{delay} min")

            # Agent ends at the destination
            current_pos = dest_loc

        n = len(pkgs)
        efficiency = round(total_dist / n, 2) if n > 0 else 0.0

        results[agent_id] = {
            "packages_delivered": n,
            "total_distance":     round(total_dist, 2),
            "efficiency":         efficiency,
            "delay_minutes":      total_delay,
        }

    return results



# 5. REPORT GENERATION


def build_report(results):
    """
    Build the final report dict and determine the best (most efficient) agent.

    'Best agent' = lowest efficiency score (least distance per package).
    Agents with zero deliveries are excluded from best-agent consideration.
    """
    # Only agents who actually delivered something
    active = {aid: v for aid, v in results.items() if v["packages_delivered"] > 0}

    best_agent = min(active, key=lambda aid: active[aid]["efficiency"]) if active else None

    report = {aid: {
        "packages_delivered": v["packages_delivered"],
        "total_distance":     v["total_distance"],
        "efficiency":         v["efficiency"],
    } for aid, v in results.items()}

    report["best_agent"] = best_agent
    return report


def save_report(report, output_path="report.json"):
    """Write the report dict to a JSON file."""
    with open(output_path, "w") as f:
        json.dump(report, f, indent=4)
    print(f"\n✅  Report saved → {output_path}")


# BONUS A: ASCII ROUTE MAP


def ascii_map(warehouses, agents, packages, assignment, grid_size=20):
    """
    Draw a rough ASCII bird's-eye view of the logistics landscape.

    Symbols:
        W  = warehouse     A  = agent start
        *  = destination   .  = empty cell
    """
    # Find coordinate bounds
    all_pts = list(warehouses.values()) + list(agents.values()) + \
              [p["destination"] for p in packages]
    max_x = max(p[0] for p in all_pts) or 1
    max_y = max(p[1] for p in all_pts) or 1

    # Scale everything to grid_size × grid_size
    def scale(pt):
        gx = round(pt[0] / max_x * (grid_size - 1))
        gy = round(pt[1] / max_y * (grid_size - 1))
        return gx, gy

    grid = [["." for _ in range(grid_size)] for _ in range(grid_size)]

    for wid, loc in warehouses.items():
        gx, gy = scale(loc)
        grid[grid_size - 1 - gy][gx] = "W"

    for aid, loc in agents.items():
        gx, gy = scale(loc)
        grid[grid_size - 1 - gy][gx] = "A"

    for pkg in packages:
        gx, gy = scale(pkg["destination"])
        grid[grid_size - 1 - gy][gx] = "*"

    print("\n── ASCII Route Map ──────────────────────────────")
    print("  " + "".join(str(i % 10) for i in range(grid_size)))
    for row in grid:
        print("  " + "".join(row))
    print("  Legend:  W=Warehouse  A=Agent  *=Destination")
    print("─────────────────────────────────────────────────\n")


# BONUS B: MID-DAY NEW AGENT


def add_midday_agent(agents, packages, warehouses, assignment, results):
    """
    Bonus: a new agent 'A_NEW' joins mid-day and takes over any unassigned
    (zero-package) agents' undelivered tasks — or simply gets the last package.

    For demo purposes we reassign the final package to the new agent.
    """
    if not packages:
        return assignment, results

    new_id = "A_NEW"
    # Place the new agent near the centroid of all warehouses
    cx = sum(w[0] for w in warehouses.values()) / len(warehouses)
    cy = sum(w[1] for w in warehouses.values()) / len(warehouses)
    agents[new_id] = [round(cx), round(cy)]

    # Give the new agent the last package
    last_pkg = packages[-1]
    for aid in list(assignment.keys()):
        if last_pkg in assignment[aid]:
            assignment[aid].remove(last_pkg)
            break
    assignment[new_id] = [last_pkg]

    print(f"\n  Mid-day agent {new_id} joined at {agents[new_id]}, "
          f"assigned package {last_pkg['id']}")

    # Re-simulate only the new agent
    new_results = simulate_deliveries(
        {new_id: assignment[new_id]}, warehouses, agents
    )
    results.update(new_results)
    return assignment, results



# BONUS C: EXPORT TOP PERFORMER TO CSV


def export_top_performer_csv(report, assignment, output_path="top_performer.csv"):
    """Export the best agent's package list and stats to a CSV file."""
    best = report.get("best_agent")
    if not best:
        print("No best agent to export.")
        return

    rows = []
    for pkg in assignment.get(best, []):
        rows.append({
            "agent_id":    best,
            "package_id":  pkg["id"],
            "warehouse":   pkg["warehouse"],
            "dest_x":      pkg["destination"][0],
            "dest_y":      pkg["destination"][1],
            "total_distance": report[best]["total_distance"],
            "efficiency":     report[best]["efficiency"],
        })

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Top performer ({best}) exported → {output_path}")



# 6. MAIN

def main():
    # Accept optional input file as command-line argument
    input_file = sys.argv[1] if len(sys.argv) > 1 else "data.json"

    if not os.path.exists(input_file):
        print(f"  File not found: {input_file}")
        sys.exit(1)

    print(f"\ FastBox Delivery Simulator")
    print(f"    Input: {input_file}\n")

    # ── Step 1: Parse input ───────────────────
    warehouses, agents, packages = load_data(input_file)
    print(f"  Warehouses : {list(warehouses.keys())}")
    print(f"  Agents     : {list(agents.keys())}")
    print(f"  Packages   : {[p['id'] for p in packages]}")

    # ── Step 2: Assign packages to agents ────
    assignment = assign_packages(packages, warehouses, agents)
    print("\n  Package Assignments:")
    for aid, pkgs in assignment.items():
        ids = [p["id"] for p in pkgs]
        print(f"    {aid}: {ids if ids else '(none)'}")

    # ── BONUS B: Mid-day agent ────────────────
    # Uncomment the next two lines to enable the mid-day agent bonus:
    # assignment, _ = add_midday_agent(agents, packages, warehouses, assignment, {})
    # (results will be recomputed below)

    # ── Step 3: Simulate deliveries ───────────
    # Set use_delays=True to enable random delay bonus
    results = simulate_deliveries(assignment, warehouses, agents, use_delays=False)

    # ── Step 4: Build + display report ────────
    report = build_report(results)

    print("\n  ── Delivery Report ─────────────────────────")
    for aid, stats in report.items():
        if aid == "best_agent":
            continue
        print(f"    {aid}: delivered={stats['packages_delivered']}, "
              f"distance={stats['total_distance']:.2f}, "
              f"efficiency={stats['efficiency']:.2f}")
    print(f"\n  🏆  Best Agent: {report['best_agent']}")

    # ── Step 5: Save report ───────────────────
    output_dir = os.path.dirname(input_file) or "."
    report_path = os.path.join(output_dir, "report.json")
    save_report(report, report_path)

    # ── BONUS A: ASCII map ────────────────────
    ascii_map(warehouses, agents, packages, assignment)

    # ── BONUS C: CSV export ───────────────────
    csv_path = os.path.join(output_dir, "top_performer.csv")
    export_top_performer_csv(report, assignment, csv_path)

    # ── Sanity check ─────────────────────────
    total_assigned = sum(v["packages_delivered"] for v in results.values())
    total_packages = len(packages)
    if total_assigned == total_packages:
        print(f"\n✔   All {total_packages} packages delivered successfully.")
    else:
        print(f"\n⚠   Mismatch: {total_assigned} delivered vs {total_packages} total.")


if __name__ == "__main__":
    main()
