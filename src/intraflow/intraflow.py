"""
IntraFlow - In-process, deterministic, message-driven dataflow runtime.

Built on the Patchboard routing model. Unlike the file-based patchboard_router,
IntraFlow operates entirely in memory within a single Python process. Components
are dict-based machines activated by messages; a patchboard routing fabric
connects them via channel-rewriting rules.
"""

import time


# =============================================================================
# GLOBAL EXECUTION CONTEXT
# =============================================================================

g = {
    "component": None,   # currently executing component (set during activation)
    "msg": None,          # message being processed (set during activation)
}


# =============================================================================
# RUNTIME STATE
# =============================================================================

components = {}   # id -> component dict
routes = []       # list of route dicts


# =============================================================================
# MESSAGE MODEL
# =============================================================================

def make_message(channel, signal):
    """Create a Patchboard message envelope with timestamp."""
    return {
        "channel": channel,
        "signal": signal,
        "timestamp": f"{time.time():.6f}",
    }


def emit_signal(channel, signal):
    """Create message and append to current component's outbox.

    Called from within an activation function. Uses g["component"] to find
    the outbox. The message is not routed until the next cycle's Phase 1.
    """
    msg = make_message(channel, signal)
    g["component"]["outbox"].append(msg)


# =============================================================================
# COMPONENT MODEL
# =============================================================================

def make_component(component_id, activation):
    """Create a canonical IntraFlow component dict.

    The component is a machine-like unit with inbox/outbox message queues,
    an activation callable, mutable local state, and reflection-only channel
    declarations.
    """
    return {
        "type": "INTRAFLOW-COMPONENT",
        "id": component_id,
        "inbox": [],
        "outbox": [],
        "activation": activation,
        "state": {},
        "channels": {"in": {}, "out": {}},
    }


def register_component(component_id, activation):
    """Create a component and add it to the registry."""
    comp = make_component(component_id, activation)
    components[component_id] = comp
    return comp


def unregister_component(component_id):
    """Remove a component from the registry."""
    components.pop(component_id, None)


# =============================================================================
# ENDPOINT MODEL & RESOLUTION
# =============================================================================

def resolve_endpoint(endpoint):
    """Resolve an endpoint spec to a runtime object.

    Endpoint types:
      - Has "ref" key: return the ref directly (runtime-only endpoint).
      - {type: "component", id: X}: lookup in components registry.
      - {type: "queue" or "list", ref: obj}: return the ref object.
      - Unresolvable: return None.
    """
    if "ref" in endpoint:
        return endpoint["ref"]

    ep_type = endpoint.get("type")

    if ep_type == "component":
        return components.get(endpoint.get("id"))

    if ep_type in ("queue", "list"):
        return endpoint.get("ref")

    return None


# =============================================================================
# ENDPOINT BEHAVIOR TABLE
# =============================================================================

endpoint_behavior = {
    "INTRAFLOW-COMPONENT": {
        "get_outbox": lambda ep: ep["outbox"],
        "deliver": lambda ep, msg: ep["inbox"].append(msg),
    },
    "queue": {
        "get_outbox": lambda ep: ep,
        "deliver": lambda ep, msg: ep.append(msg),
    },
    "list": {
        "get_outbox": lambda ep: ep,
        "deliver": lambda ep, msg: ep.append(msg),
    },
}


# =============================================================================
# ROUTE MANAGEMENT
# =============================================================================

def add_route(src, src_channel, dest, dest_channel):
    """Append a route dict to the routing table.

    Each argument is an endpoint spec (dict with type/id/ref) or a channel
    name string. Routes should only be added at quiescence.
    """
    route = {
        "src": src,
        "src-channel": src_channel,
        "dest": dest,
        "dest-channel": dest_channel,
    }
    routes.append(route)


def remove_route(src, src_channel, dest, dest_channel):
    """Remove first matching route from the routing table."""
    for i, route in enumerate(routes):
        if (route["src"] is src
                and route["src-channel"] == src_channel
                and route["dest"] is dest
                and route["dest-channel"] == dest_channel):
            routes.pop(i)
            return True
    return False


def clear_routes():
    routes.clear()


# =============================================================================
# ROUTING ALGORITHM — RouteEverything (Phase 1)
# =============================================================================

def _endpoint_type(endpoint_spec):
    """Derive the behavior-table type key for a resolved endpoint.

    Components are dicts with a "type" key ("INTRAFLOW-COMPONENT").
    Queue and list endpoints resolve to plain Python lists; the type
    comes from the endpoint spec that produced them.
    """
    if isinstance(endpoint_spec, dict):
        ep_type = endpoint_spec.get("type")
        if ep_type == "component":
            return "INTRAFLOW-COMPONENT"
        return ep_type  # "queue", "list", etc.
    return None


def route_everything():
    """Consume messages from source outboxes and deliver to destination inboxes.

    Follows the spec pseudocode exactly:
      1. Resolve all routes to runtime endpoints.
      2. Build route_index grouped by (src_id, src_channel).
      3. Iterate sources in stable order, drain outbox messages.
      4. For each message, fanout to matching destinations with channel rewrite.
      5. Clear objid mapping.

    Routing is destructive: source outbox messages are consumed. Signal and
    timestamp are preserved; only channel is rewritten per the route.
    """
    objid = {}
    objtype = {}     # id(obj) -> behavior-table type key
    route_index = {}

    for route in routes:
        src_obj = resolve_endpoint(route["src"])
        dest_obj = resolve_endpoint(route["dest"])

        if src_obj is None or dest_obj is None:
            continue

        src_id = id(src_obj)
        dest_id = id(dest_obj)

        objid[src_id] = src_obj
        objid[dest_id] = dest_obj
        objtype[src_id] = _endpoint_type(route["src"])
        objtype[dest_id] = _endpoint_type(route["dest"])

        route_index.setdefault(src_id, {})
        route_index[src_id].setdefault(route["src-channel"], [])
        route_index[src_id][route["src-channel"]].append(
            (dest_id, route["dest-channel"])
        )

    for src_id, channel_map in route_index.items():
        src_endpoint = objid[src_id]
        src_beh = endpoint_behavior.get(objtype.get(src_id))
        if src_beh is None:
            continue

        outbox = src_beh["get_outbox"](src_endpoint)

        while outbox:
            msg = outbox.pop(0)
            fanout = channel_map.get(msg["channel"], [])

            for (dest_id, dest_channel) in fanout:
                dest_endpoint = objid[dest_id]
                dest_beh = endpoint_behavior.get(objtype.get(dest_id))
                if dest_beh is None:
                    continue

                new_msg = {
                    "channel": dest_channel,
                    "signal": msg["signal"],
                    "timestamp": msg["timestamp"],
                }
                dest_beh["deliver"](dest_endpoint, new_msg)

    objid.clear()
    objtype.clear()


# =============================================================================
# ACTIVATION — ActivateOneTurnPerComponent (Phase 2)
# =============================================================================

def activate_one_turn_per_component():
    """Round-robin activation: each component consumes at most one inbox message.

    Iterates components in stable (insertion) order. If a component's inbox
    is non-empty, pops one message, sets g["component"] and g["msg"], and
    invokes the component's activation function.
    """
    for comp in components.values():
        if not comp["inbox"]:
            continue

        msg = comp["inbox"].pop(0)
        g["component"] = comp
        g["msg"] = msg

        comp["activation"]()

        g["component"] = None
        g["msg"] = None


# =============================================================================
# MAIN LOOP
# =============================================================================

def run_cycle():
    """Execute one cycle: route_everything() then activate_one_turn_per_component()."""
    route_everything()
    activate_one_turn_per_component()


def is_quiescent():
    """True when all inboxes and outboxes are empty."""
    for comp in components.values():
        if comp["inbox"] or comp["outbox"]:
            return False
    return True


def run(cycles=0):
    """Run the main loop.

    If cycles > 0, run exactly that many cycles.
    If cycles == 0, run until quiescent (no messages anywhere).
    """
    if cycles > 0:
        for _ in range(cycles):
            run_cycle()
    else:
        # Run until quiescent — but always run at least one cycle
        run_cycle()
        while not is_quiescent():
            run_cycle()


# =============================================================================
# SMOKE TEST
# =============================================================================

if __name__ == "__main__":
    # Producer: on any activation, emits a "hello" signal on channel "out"
    def producer_activation():
        emit_signal("out", {"text": "hello from producer"})

    # Consumer: on activation, stores received message in state
    def consumer_activation():
        g["component"]["state"]["received"] = g["msg"]["signal"]

    # Register components
    producer = register_component("producer", producer_activation)
    consumer = register_component("consumer", consumer_activation)

    # Wire: producer "out" -> consumer "in"
    add_route(
        {"type": "component", "id": "producer"},
        "out",
        {"type": "component", "id": "consumer"},
        "in",
    )

    # Inject a seed message into producer's inbox to trigger it
    producer["inbox"].append(make_message("kick", {"reason": "seed"}))

    # Run until quiescent
    run()

    # Verify
    received = consumer["state"].get("received")
    if received and received["text"] == "hello from producer":
        print("PASS: consumer received the routed message.")
        print(f"  signal: {received}")
    else:
        print("FAIL: consumer did not receive the expected message.")
        print(f"  consumer state: {consumer['state']}")
