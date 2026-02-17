"""
IntraFlow - In-process, deterministic, message-driven dataflow runtime.

Built on the Patchboard routing model. Unlike the file-based patchboard_router,
IntraFlow operates entirely in memory within a single Python process. Components
are dict-based machines activated by messages; a patchboard routing fabric
connects them via channel-rewriting rules.
"""

import json
import os
import time
import uuid


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
# NORMALIZE ENDPOINT SPEC
# =============================================================================

endpoint_spec_types = {"component", "filetalk", "queue", "list"}


def normalize_endpoint_spec(x):
    """Convert user-provided endpoint identifier into canonical endpoint spec.

    Accepts:
      - ("component", id_string)   -> {"type": "component", "id": id_string}
      - ("filetalk", path_string)  -> {"type": "filetalk", "path": path_string}
      - ("list", list_object)      -> {"type": "list", "ref": list_object}
      - ("queue", queue_object)    -> {"type": "queue", "ref": queue_object}
      - A dict with "type" key     -> validated and returned (idempotent)
      - A dict without "type" (runtime component dict) -> {"type": "component", "ref": dict}

    Idempotent: canonical dicts pass through unchanged.
    """
    # Tuple form: (type_tag, value)
    if isinstance(x, (tuple, list)) and len(x) == 2:
        tag, value = x
        if tag == "component":
            return {"type": "component", "id": value}
        if tag == "filetalk":
            return {"type": "filetalk", "path": value}
        if tag == "list":
            return {"type": "list", "ref": value}
        if tag == "queue":
            return {"type": "queue", "ref": value}
        raise ValueError(f"Unknown endpoint tuple type: {tag!r}")

    # Dict form
    if isinstance(x, dict):
        ep_type = x.get("type")
        if ep_type in endpoint_spec_types:
            # Already canonical endpoint spec — return as-is
            return x
        # Bare component dict (runtime reference)
        return {"type": "component", "ref": x}

    raise ValueError(f"Unsupported endpoint spec: {type(x).__name__}")


# =============================================================================
# ENDPOINT BEHAVIOR TABLE
# =============================================================================

def _component_drain(ep):
    msgs = list(ep["ref"]["outbox"])
    ep["ref"]["outbox"].clear()
    return msgs

def _component_deliver(ep, msg):
    ep["ref"]["inbox"].append(msg)

def _component_resolve_ref(ep):
    return components.get(ep.get("id"))

def _list_drain(ep):
    msgs = list(ep["ref"])
    ep["ref"].clear()
    return msgs

def _filetalk_drain(ep):
    """Read and remove all parseable .json message files from ep['path']."""
    path = ep["path"]
    msgs = []
    if not os.path.isdir(path):
        return msgs
    for filename in os.listdir(path):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(path, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                msg = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Presumed incomplete — skip, retry later
            continue
        os.remove(filepath)
        msgs.append(msg)
    return msgs


def _filetalk_deliver(ep, msg):
    """Write a message as a .json file into ep['path']."""
    path = ep["path"]
    os.makedirs(path, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.json"
    filepath = os.path.join(path, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(msg, f)


def _queue_drain(ep):
    msgs = []
    q = ep["ref"]
    while not q.empty():
        msgs.append(q.get_nowait())
    return msgs

endpoint_behavior = {
    "component": {
        "requires_ref": True,
        "resolve_ref": _component_resolve_ref,
        "is_persistable": lambda ep: "id" in ep,
        "drain_messages": _component_drain,
        "deliver": _component_deliver,
    },
    "filetalk": {
        "requires_ref": False,
        "resolve_ref": lambda ep: None,
        "is_persistable": lambda ep: "path" in ep,
        "drain_messages": _filetalk_drain,
        "deliver": _filetalk_deliver,
    },
    "queue": {
        "requires_ref": True,
        "resolve_ref": lambda ep: ep.get("ref"),
        "is_persistable": lambda ep: False,
        "drain_messages": _queue_drain,
        "deliver": lambda ep, msg: ep["ref"].put(msg),
    },
    "list": {
        "requires_ref": True,
        "resolve_ref": lambda ep: ep.get("ref"),
        "is_persistable": lambda ep: False,
        "drain_messages": _list_drain,
        "deliver": lambda ep, msg: ep["ref"].append(msg),
    },
}


# =============================================================================
# ROUTE MANAGEMENT
# =============================================================================

def _find_existing_endpoint(ep):
    """Find an existing bound endpoint spec in routes matching the same logical endpoint.

    Routes sharing the same logical source must share the same endpoint spec
    object so that route_everything() can group them by identity.
    """
    for route in routes:
        for existing in (route["src"], route["dest"]):
            if existing["type"] != ep["type"]:
                continue
            if "id" in ep and existing.get("id") == ep["id"]:
                return existing
            if "path" in ep and existing.get("path") == ep["path"]:
                return existing
            if "ref" in ep and existing.get("ref") is ep["ref"]:
                return existing
    return None


def add_route(route):
    """Bind a declarative route into executable topology.

    Accepts a route dict with keys: src, src-channel, dest, dest-channel,
    and optional persistent (default False).

    Steps:
      1. Normalize src and dest endpoint specifications.
      2. Lookup endpoint behavior contracts for both endpoints.
      3. Resolve runtime refs if endpoint type requires binding.
      4. Validate persistence eligibility.
      5. Append fully-bound route object to routing table.
    """
    src_ep = normalize_endpoint_spec(route["src"])
    dest_ep = normalize_endpoint_spec(route["dest"])
    persistent = route.get("persistent", False)

    # Reuse existing endpoint specs for identity-based grouping in routing
    src_ep = _find_existing_endpoint(src_ep) or src_ep
    dest_ep = _find_existing_endpoint(dest_ep) or dest_ep

    # Lookup behavior contracts
    src_beh = endpoint_behavior.get(src_ep["type"])
    dest_beh = endpoint_behavior.get(dest_ep["type"])
    if src_beh is None:
        raise ValueError(f"Unknown endpoint type: {src_ep['type']!r}")
    if dest_beh is None:
        raise ValueError(f"Unknown endpoint type: {dest_ep['type']!r}")

    # Resolve runtime refs if required
    if src_beh["requires_ref"] and "ref" not in src_ep:
        ref = src_beh["resolve_ref"](src_ep)
        if ref is None:
            raise ValueError(f"Cannot resolve source endpoint: {src_ep}")
        src_ep["ref"] = ref

    if dest_beh["requires_ref"] and "ref" not in dest_ep:
        ref = dest_beh["resolve_ref"](dest_ep)
        if ref is None:
            raise ValueError(f"Cannot resolve destination endpoint: {dest_ep}")
        dest_ep["ref"] = ref

    # Validate persistence
    if persistent:
        if not src_beh["is_persistable"](src_ep):
            raise ValueError(f"Source endpoint not persistable: {src_ep}")
        if not dest_beh["is_persistable"](dest_ep):
            raise ValueError(f"Destination endpoint not persistable: {dest_ep}")

    bound_route = {
        "src": src_ep,
        "src-channel": route["src-channel"],
        "dest": dest_ep,
        "dest-channel": route["dest-channel"],
        "persistent": persistent,
    }
    routes.append(bound_route)


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
# PATCHBOARD WIRING CONSOLE
# =============================================================================

wire = {
    "src": None,
    "dest": None,
    "persist": False,
    "channel-links": [],
}


def address_source(x):
    """Assign source endpoint spec and reset provisional wiring state."""
    wire["src"] = normalize_endpoint_spec(x)
    wire["persist"] = False
    wire["channel-links"] = []


def address_dest(x):
    """Assign destination endpoint spec."""
    wire["dest"] = normalize_endpoint_spec(x)


def address_components(src, dest):
    """Convenience: address_source(src) then address_dest(dest)."""
    address_source(src)
    address_dest(dest)


def persist_links():
    """Mark subsequent committed routes as persistent (subject to add_route validation)."""
    wire["persist"] = True


def link_channels(src_channel, dest_channel):
    """Stage a channel mapping between current source and destination."""
    if wire["src"] is None:
        raise ValueError("No source endpoint addressed")
    if wire["dest"] is None:
        raise ValueError("No destination endpoint addressed")
    wire["channel-links"].append((src_channel, dest_channel))


def commit_links():
    """Finalize all staged channel mappings by creating routes via add_route().

    Clears channel-links and persist flag afterward.
    Preserves current src and dest addressing context.
    """
    if wire["src"] is None:
        raise ValueError("No source endpoint addressed")
    if wire["dest"] is None:
        raise ValueError("No destination endpoint addressed")
    if not wire["channel-links"]:
        raise ValueError("No channel links staged")

    for (src_channel, dest_channel) in wire["channel-links"]:
        route = {
            "src": wire["src"],
            "dest": wire["dest"],
            "src-channel": src_channel,
            "dest-channel": dest_channel,
            "persistent": wire["persist"],
        }
        add_route(route)

    wire["channel-links"] = []
    wire["persist"] = False


# =============================================================================
# ROUTING ALGORITHM — RouteEverything (Phase 1)
# =============================================================================

def route_everything():
    """Drain messages from source endpoints and deliver routed copies to destinations.

    Routes are pre-bound: endpoint specs already contain runtime refs from
    add_route(). No resolution occurs here.

    Steps:
      1. Build route_index grouped by source endpoint identity and channel.
      2. Iterate sources, drain all messages via drain_messages().
      3. For each message, fanout to matching destinations with channel rewrite.
    """
    objid = {}
    route_index = {}

    # Compile routing index
    for route in routes:
        src_ep = route["src"]
        dest_ep = route["dest"]

        src_id = id(src_ep)

        objid[src_id] = src_ep

        route_index.setdefault(src_id, {})
        route_index[src_id].setdefault(route["src-channel"], [])
        route_index[src_id][route["src-channel"]].append(
            (dest_ep, route["dest-channel"])
        )

    # Execute routing
    for src_id, channel_map in route_index.items():
        src_ep = objid[src_id]
        src_beh = endpoint_behavior[src_ep["type"]]
        msgs = src_beh["drain_messages"](src_ep)

        for msg in msgs:
            fanout = channel_map.get(msg["channel"], [])
            for (dest_ep, dest_channel) in fanout:
                dest_beh = endpoint_behavior[dest_ep["type"]]
                new_msg = {
                    "channel": dest_channel,
                    "signal": msg["signal"],
                    "timestamp": msg["timestamp"],
                }
                dest_beh["deliver"](dest_ep, new_msg)

    objid.clear()


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

    # Wire: producer "out" -> consumer "in" using wiring console
    address_components(("component", "producer"), ("component", "consumer"))
    link_channels("out", "in")
    commit_links()

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
