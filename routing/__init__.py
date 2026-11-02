"""Routing on the Heilbronn bike graph. The modules fall into three groups (each says its own in its docstring):

- Building the graph (data -> edge attributes): graph, rideable_ways, footways, named_roads, surface, lighting,
  mapillary_lights, shade, shadow, elevation, bridge_profile, air_hotspots.
- Route search: route, search, turns, naming, edges, snap, costs.
- Features on top: score, highlights, tours, grade, sharing_trip, calories.
"""
