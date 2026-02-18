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
    "component": None,           # currently executing component (set during activation)
    "msg": None,                 # message being processed (set during activation)
    "selected_component": None,  # currently selected component (component creation console)
}


# =============================================================================
# RUNTIME STATE
# =============================================================================

components = {}   # id -> component dict
routes = []       # list of route dicts


# =============================================================================
# RESET
# =============================================================================

def reset():
    """Reset all IntraFlow state to zero. Safe to call between test cases or system restarts."""
    g["component"] = None
    g["msg"] = None
    g["selected_component"] = None
    components.clear()
    routes.clear()
    wire["src"] = None
    wire["dest"] = None
    wire["persist"] = False
    wire["channel-links"] = []


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

def _make_component_dict():
    """Create a canonical IntraFlow component dict."""
    return {
        "type": "INTRAFLOW-COMPONENT",
        "inbox": [],
        "outbox": [],
        "activation": None,
        "state": {},
        "channels": {"in": {}, "out": {}},
        "always_active": False,
    }


def declare_component(component_id):
    """Create a new component with a stable identifier, register it, and select it."""
    if component_id in components:
        raise ValueError(f"Component already registered: {component_id!r}")
    comp = _make_component_dict()
    comp["id"] = component_id
    components[component_id] = comp
    g["selected_component"] = comp
    return comp


def make_component():
    """Create an anonymous (unregistered) component and select it."""
    comp = _make_component_dict()
    g["selected_component"] = comp
    return comp


def get_component():
    """Return the currently selected component."""
    return g["selected_component"]


def register_component(component_id, activation):
    """Convenience: declare a component and assign its activation function."""
    comp = declare_component(component_id)
    comp["activation"] = activation
    return comp


def delist_component(comp):
    """Remove all routes that reference comp as source or destination."""
    to_remove = [
        r for r in routes
        if r["src"] is comp or r["dest"] is comp
    ]
    for r in to_remove:
        routes.remove(r)


def unregister_component(component_id):
    """Remove a component from the registry and delist its routes."""
    comp = components.pop(component_id, None)
    if comp is not None:
        delist_component(comp)


# =============================================================================
# COMPONENT POPULATION ADAPTERS
# =============================================================================

def populate_filetalk(intraflow_to_filesystem_path, filesystem_to_intraflow_path):
    """Populate the selected component with FileTalk adapter behavior.

    Either path may be None; behavior adjusts accordingly.
    The component is marked always_active and polls on a 250ms interval.
    """
    component = g["selected_component"]
    component["component_type"] = "adapter"
    component["adapter_kind"] = "filetalk"
    component["always_active"] = True
    component["state"] = {
        "intraflow_to_filesystem_path": intraflow_to_filesystem_path,
        "filesystem_to_intraflow_path": filesystem_to_intraflow_path,
        "check_after_n_ms": 250,
        "last_checked_timestamp": 0,
    }

    def _activation():
        comp = g["component"]
        state = comp["state"]
        now_ms = time.time() * 1000
        if (now_ms - state["last_checked_timestamp"]) < state["check_after_n_ms"]:
            return
        state["last_checked_timestamp"] = now_ms

        # Outgoing: inbox -> filesystem
        out_path = state["intraflow_to_filesystem_path"]
        while comp["inbox"]:
            if out_path is None:
                raise ValueError(
                    "FileTalk adapter cannot emit: intraflow_to_filesystem_path not defined"
                )
            msg = comp["inbox"].pop(0)
            os.makedirs(out_path, exist_ok=True)
            filepath = os.path.join(out_path, f"{uuid.uuid4().hex}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(msg, f)

        # Incoming: filesystem -> outbox
        in_path = state["filesystem_to_intraflow_path"]
        if in_path and os.path.isdir(in_path):
            for filename in os.listdir(in_path):
                if not filename.endswith(".json"):
                    continue
                filepath = os.path.join(in_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        msg = json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue
                os.remove(filepath)
                comp["outbox"].append(msg)

    component["activation"] = _activation


def populate_queue(queue):
    """Populate the selected component with queue adapter behavior."""
    component = g["selected_component"]
    component["component_type"] = "adapter"
    component["adapter_kind"] = "queue"
    component["always_active"] = True
    component["state"] = {"queue": queue}

    def _activation():
        comp = g["component"]
        q = comp["state"]["queue"]
        # Incoming: queue -> outbox (drain before adding new items)
        while not q.empty():
            comp["outbox"].append(q.get_nowait())
        # Outgoing: inbox -> queue
        while comp["inbox"]:
            q.put(comp["inbox"].pop(0))

    component["activation"] = _activation


def populate_list(L):
    """Populate the selected component with list adapter behavior.

    The list acts as a FIFO buffer; index 0 is the next message to consume.
    """
    component = g["selected_component"]
    component["component_type"] = "adapter"
    component["adapter_kind"] = "list"
    component["always_active"] = True
    component["state"] = {"list": L}

    def _activation():
        comp = g["component"]
        lst = comp["state"]["list"]
        # Incoming: list -> outbox (drain before adding new items)
        while lst:
            comp["outbox"].append(lst.pop(0))
        # Outgoing: inbox -> list
        while comp["inbox"]:
            lst.append(comp["inbox"].pop(0))

    component["activation"] = _activation


# =============================================================================
# ROUTE MANAGEMENT
# =============================================================================

_ROUTE_FIELD_ORDER = [
    "src_id", "src", "src-channel",
    "dest_id", "dest", "dest-channel",
    "persistent",
]


def order_route(route):
    """Reorder route keys in-place to canonical field order."""
    ordered = {k: route[k] for k in _ROUTE_FIELD_ORDER if k in route}
    for k in route:
        if k not in ordered:
            ordered[k] = route[k]
    route.clear()
    route.update(ordered)


def add_route(route):
    """Bind a canonical route into executable topology.

    Resolves component identifiers to runtime refs, validates persistence
    eligibility, enforces canonical field ordering, and inserts into routing table.
    """
    # Resolve src
    src = route.get("src")
    src_id = route.get("src_id")
    if src is None:
        if not src_id:
            raise ValueError("Route must provide 'src' or 'src_id'")
        src = components.get(src_id)
        if src is None:
            raise ValueError(f"Source component not found: {src_id!r}")
        route["src"] = src
    else:
        if src_id and components.get(src_id) is not src:
            raise ValueError(f"src_id {src_id!r} does not match provided src ref")

    # Resolve dest
    dest = route.get("dest")
    dest_id = route.get("dest_id")
    if dest is None:
        if not dest_id:
            raise ValueError("Route must provide 'dest' or 'dest_id'")
        dest = components.get(dest_id)
        if dest is None:
            raise ValueError(f"Destination component not found: {dest_id!r}")
        route["dest"] = dest
    else:
        if dest_id and components.get(dest_id) is not dest:
            raise ValueError(f"dest_id {dest_id!r} does not match provided dest ref")

    # Validate persistence
    persistent = route.get("persistent", False)
    if persistent:
        if not src_id:
            raise ValueError("Persistent route requires src_id")
        if not dest_id:
            raise ValueError("Persistent route requires dest_id")

    route.setdefault("src_id", None)
    route.setdefault("dest_id", None)
    route.setdefault("persistent", False)

    order_route(route)
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
# PATCHBOARD WIRING CONSOLE
# =============================================================================

wire = {
    "src": None,
    "dest": None,
    "persist": False,
    "channel-links": [],
}


def address_source(x):
    """Assign source component (id string or component dict) and reset wiring state."""
    wire["src"] = x
    wire["persist"] = False
    wire["channel-links"] = []


def address_dest(x):
    """Assign destination component (id string or component dict)."""
    wire["dest"] = x


def address_components(src, dest):
    """Convenience: address_source(src) then address_dest(dest)."""
    address_source(src)
    address_dest(dest)


def persist_links():
    """Mark subsequent committed routes as persistent."""
    wire["persist"] = True


def link_channels(src_channel, dest_channel):
    """Stage a channel mapping between current source and destination."""
    if wire["src"] is None:
        raise ValueError("No source component addressed")
    if wire["dest"] is None:
        raise ValueError("No destination component addressed")
    wire["channel-links"].append((src_channel, dest_channel))


def commit_links():
    """Finalize staged channel mappings by creating routes via add_route().

    Resolves string ids to component refs. Clears channel-links and persist
    flag afterward. Preserves current src and dest addressing context.
    """
    if wire["src"] is None:
        raise ValueError("No source component addressed")
    if wire["dest"] is None:
        raise ValueError("No destination component addressed")
    if not wire["channel-links"]:
        raise ValueError("No channel links staged")

    # Resolve source
    if isinstance(wire["src"], str):
        src_id = wire["src"]
        src = components.get(src_id)
        if src is None:
            raise ValueError(f"Source component not found: {src_id!r}")
    else:
        src = wire["src"]
        src_id = src.get("id")

    # Resolve destination
    if isinstance(wire["dest"], str):
        dest_id = wire["dest"]
        dest = components.get(dest_id)
        if dest is None:
            raise ValueError(f"Destination component not found: {dest_id!r}")
    else:
        dest = wire["dest"]
        dest_id = dest.get("id")

    for (src_channel, dest_channel) in wire["channel-links"]:
        route = {
            "src_id": src_id,
            "src": src,
            "src-channel": src_channel,
            "dest_id": dest_id,
            "dest": dest,
            "dest-channel": dest_channel,
            "persistent": wire["persist"],
        }
        order_route(route)
        add_route(route)

    wire["channel-links"] = []
    wire["persist"] = False


# =============================================================================
# ROUTING ALGORITHM — RouteEverything (Phase 1)
# =============================================================================

def route_everything():
    """Drain messages from source components and deliver routed copies to destinations.

    Routes are fully compiled: src and dest are component refs with inbox/outbox.
    No resolution occurs here.

    Steps:
      1. Build route_index grouped by source component identity and channel.
      2. Iterate sources, drain all messages from outbox.
      3. For each message, fanout to matching destinations with channel rewrite.
    """
    objid = {}
    route_index = {}

    # Compile routing index
    for route in routes:
        src = route["src"]
        src_key = id(src)
        objid[src_key] = src
        route_index.setdefault(src_key, {})
        route_index[src_key].setdefault(route["src-channel"], [])
        route_index[src_key][route["src-channel"]].append(
            (route["dest"], route["dest-channel"])
        )

    # Execute routing
    for src_key, channel_map in route_index.items():
        src = objid[src_key]
        msgs = src["outbox"]
        src["outbox"] = []

        for msg in msgs:
            fanout = channel_map.get(msg["channel"], [])
            for (dest, dest_channel) in fanout:
                new_msg = {
                    "channel": dest_channel,
                    "signal": msg["signal"],
                    "timestamp": msg["timestamp"],
                }
                dest["inbox"].append(new_msg)

    objid.clear()


# =============================================================================
# ACTIVATION — ActivateOneTurnPerComponent (Phase 2)
# =============================================================================

def activate_one_turn_per_component():
    """Round-robin activation: each component runs at most one turn per cycle.

    Components with always_active=True are activated even with an empty inbox
    (msg will be None in that case).
    """
    for comp in components.values():
        has_message = bool(comp["inbox"])
        always = comp.get("always_active", False)
        if not has_message and not always:
            continue

        msg = comp["inbox"].pop(0) if has_message else None
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
    address_components("producer", "consumer")
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
