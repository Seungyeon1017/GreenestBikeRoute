// Named ways in Heilbronn for data/custom/named_roads_heilbronn.geojson (routing.named_roads): the roads an unnamed
// sidewalk or bike path can be named after, including those bikes may not ride, which the bike graph leaves out, and
// each way's own name for lines merged from several ways.
// Run with: python -m routing.named_roads (or on https://overpass-turbo.eu, Export -> GeoJSON)
[out:json][timeout:120];
area["name"="Heilbronn"]["boundary"="administrative"]["admin_level"="6"]->.hn;
way["highway"]["name"](area.hn);
out geom;
