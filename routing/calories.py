"""Rough energy use of a bike ride, in kcal, for display next to a route.

    kcal = MET * weight_kg * riding hours                      (riding on the flat)
         + (weight_kg + BIKE_KG) * g * metres climbed / EFFICIENCY / 4184   (extra for climbing)

- MET 6.8: "bicycling for transportation, moderate effort" (Compendium of Physical Activities
  2024, code 16002, https://pacompendium.com/transportation/). 1 MET ~ 1 kcal per kg per hour.
- Climbing: lifting rider and bike costs m * g * h joules of work; muscles turn about a quarter
  of food energy into work (EFFICIENCY). Only uphill metres count; rolling downhill is not refunded.
- Riding time comes from the route (routing.route: speed per street from speed_map).

E-bike (pedelec, e_bike=True), a rough estimate:
- riding * EBIKE_RIDING_FACTOR (0.9): in a small study the heart-rate rise on an e-bike was 89%
  of a conventional bike on the same route (Hoj et al. 2018, JMIR Public Health Surveill 4(4):e10461).
  The Compendium even gives the same 6.8 MET (code 16005), so 0.9 is if anything low on savings.
- climbing * EBIKE_CLIMB_FACTOR (0.5): an ASSUMPTION that the motor does about half the lifting;
  real assist levels range from little (eco) to most of it (turbo).
- the riding time is the same as for a normal bike (speed_map mixes both kinds of bikes), although
  e-bike riders are usually faster.

An estimate, not a measurement: it ignores wind, stops, tyre pressure and fitness, and the MET
value is an average across people. Show it rounded ("about 80 kcal"), and mark e-bike values as rough.
"""
G_MS2 = 9.81
J_PER_KCAL = 4184.0
MET_CYCLING = 6.8
EFFICIENCY = 0.25
BIKE_KG = 15.0
EBIKE_KG = 25.0
DEFAULT_WEIGHT_KG = 70.0
EBIKE_RIDING_FACTOR = 0.9
EBIKE_CLIMB_FACTOR = 0.5


def ride_kcal(duration_s, climb_m, weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """kcal for riding `duration_s` seconds with `climb_m` metres of total ascent."""
    bike_kg = EBIKE_KG if e_bike else BIKE_KG
    riding = MET_CYCLING * weight_kg * duration_s / 3600
    climbing = (weight_kg + bike_kg) * G_MS2 * max(climb_m, 0.0) / EFFICIENCY / J_PER_KCAL
    if e_bike:
        riding *= EBIKE_RIDING_FACTOR
        climbing *= EBIKE_CLIMB_FACTOR
    return riding + climbing


def total_climb(rises_m):
    """Total ascent in m from the height change of each edge (negative = downhill, ignored)."""
    return sum(r for r in rises_m if r > 0)


def route_climb(G, edges):
    """Total ascent in m of a route given as (u, v, data) edges (routing.route.route_edges), the humps of bridges
    included: the climb_m of /route/grade. None when the graph has no elevation data."""
    from routing.grade import NoElevationError, edge_parts  # needs the graph stack (osmnx)
    try:
        return total_climb(rise for u, v, d in edges for _, rise, _ in edge_parts(G, u, v, d))
    except NoElevationError:
        return None


def route_kcal(G, edges, duration_s, weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """kcal for a route given as (u, v, data) edges (routing.route.route_edges) and its duration_s.

    Without elevation data in the graph the climb counts as 0, so the value is a lower bound.
    """
    return ride_kcal(duration_s, route_climb(G, edges) or 0.0, weight_kg, e_bike)
