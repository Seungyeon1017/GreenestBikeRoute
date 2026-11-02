"""Cheapest-path search over states, for routing.route: Dijkstra, or A* with an estimate of the cost still to go."""
import heapq
import math

import networkx as nx


def cheapest_path(start, goal, steps, estimate=None):
    """The nodes of the cheapest path from node `start` to node `goal`.

    The search runs over states: hashable, the node first (a turn's cost can depend on the node the rider came from,
    so that can be part of the state), from (start, None). steps(state, info) yields (next state, cost, its info) for
    each step on; `info` is what the step leaves the next one (the heading on arrival, say) and must follow from the
    state alone. estimate(node), A*: at most the cost still to go from node to goal, falling by no more than a step's
    cost along it (consistent); without one, 0 (Dijkstra). An estimate that breaks this can miss the cheapest path.
    Raises nx.NetworkXNoPath.
    """
    estimate = estimate or (lambda node: 0.0)
    best, came_from, done = {(start, None): 0.0}, {}, set()
    queue, tie = [(estimate(start), 0, 0.0, (start, None), None)], 1
    while queue:
        _, _, cost, state, info = heapq.heappop(queue)
        if state in done:
            continue
        done.add(state)
        if state[0] == goal:
            path = [goal]
            while state in came_from:
                state = came_from[state]
                path.append(state[0])
            return path[::-1]
        for nxt, step, nxt_info in steps(state, info):
            c = cost + step
            if c < best.get(nxt, math.inf):
                best[nxt], came_from[nxt] = c, state
                heapq.heappush(queue, (c + estimate(nxt[0]), tie, c, nxt, nxt_info))
                tie += 1
    raise nx.NetworkXNoPath
