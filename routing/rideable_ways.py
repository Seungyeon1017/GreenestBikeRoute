"""OSM ways we ride although OSM doesn't say bikes may (footways without a bicycle tag).

Checked by hand, one per line with why. Routing treats them like footways tagged bicycle=yes.

Planned: users report streets in the app and, once checked, they are added here (or to a database that
replaces this file).
"""
RIDEABLE_WAYS = {
    286359672: "Allee, Heilbronn: footway beside the bus/tram lane and the car lane, which cyclists use instead; its neighbours 164208993, 262195720 and 286359696 are tagged bicycle=yes, this one only lacks the tag in OSM",
}
