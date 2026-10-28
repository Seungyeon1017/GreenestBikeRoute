// Bike-friendly streets in Heilbronn for data/custom/bike_friendly_streets_heilbronn.geojson
// Run on https://overpass-turbo.eu, then Export -> GeoJSON -> download (saves as export.geojson)
[out:json][timeout:120];
area["name"="Heilbronn"]["boundary"="administrative"]["admin_level"="6"]->.hn;
(
  way["highway"="cycleway"](area.hn);
  way["bicycle_road"="yes"](area.hn);
  way["highway"~"path|footway|track|pedestrian"]["bicycle"~"designated|yes"](area.hn);
  way["cycleway"~"lane|track|shared_lane"](area.hn);
  way["cycleway:both"~"lane|track|shared_lane"](area.hn);
  way["cycleway:left"~"lane|track|shared_lane"](area.hn);
  way["cycleway:right"~"lane|track|shared_lane"](area.hn);
)->.infra;
relation["route"="bicycle"](area.hn);
way(r)(area.hn)->.routes;
(.infra; .routes;);
out geom;
