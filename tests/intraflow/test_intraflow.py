"""
Tests for the IntraFlow runtime.
"""

import sys
from pathlib import Path

import pytest

# Import intraflow module
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "intraflow.intraflow",
    Path(__file__).parent.parent.parent / "src" / "intraflow" / "intraflow.py"
)
ifl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ifl)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def reset_runtime():
    """Reset all runtime state before each test."""
    ifl.components.clear()
    ifl.routes.clear()
    ifl.g["component"] = None
    ifl.g["msg"] = None
    ifl.wire["src"] = None
    ifl.wire["dest"] = None
    ifl.wire["persist"] = False
    ifl.wire["channel-links"] = []
    yield
    ifl.components.clear()
    ifl.routes.clear()
    ifl.g["component"] = None
    ifl.g["msg"] = None


# =============================================================================
# MESSAGE MODEL
# =============================================================================

def test_make_message_has_required_fields():
    msg = ifl.make_message("ch1", {"data": 42})
    assert msg["channel"] == "ch1"
    assert msg["signal"] == {"data": 42}
    assert "timestamp" in msg


def test_make_message_timestamp_is_string():
    msg = ifl.make_message("x", {})
    assert isinstance(msg["timestamp"], str)
    # Should parse as a float
    float(msg["timestamp"])


# =============================================================================
# COMPONENT MODEL
# =============================================================================

def test_make_component_canonical_form():
    comp = ifl.make_component("foo", lambda: None)
    assert comp["type"] == "INTRAFLOW-COMPONENT"
    assert comp["id"] == "foo"
    assert comp["inbox"] == []
    assert comp["outbox"] == []
    assert comp["state"] == {}
    assert comp["channels"] == {"in": {}, "out": {}}
    assert callable(comp["activation"])


def test_register_component_adds_to_registry():
    comp = ifl.register_component("alpha", lambda: None)
    assert "alpha" in ifl.components
    assert ifl.components["alpha"] is comp


def test_unregister_component_removes_from_registry():
    ifl.register_component("beta", lambda: None)
    assert "beta" in ifl.components
    ifl.unregister_component("beta")
    assert "beta" not in ifl.components


def test_unregister_nonexistent_component_is_safe():
    ifl.unregister_component("does_not_exist")


# =============================================================================
# NORMALIZE ENDPOINT SPEC
# =============================================================================

def test_normalize_component_tuple():
    result = ifl.normalize_endpoint_spec(("component", "foo"))
    assert result == {"type": "component", "id": "foo"}


def test_normalize_filetalk_tuple():
    result = ifl.normalize_endpoint_spec(("filetalk", "/tmp/inbox"))
    assert result == {"type": "filetalk", "path": "/tmp/inbox"}


def test_normalize_list_tuple():
    lst = []
    result = ifl.normalize_endpoint_spec(("list", lst))
    assert result == {"type": "list", "ref": lst}
    assert result["ref"] is lst


def test_normalize_queue_tuple():
    q = []
    result = ifl.normalize_endpoint_spec(("queue", q))
    assert result == {"type": "queue", "ref": q}
    assert result["ref"] is q


def test_normalize_canonical_dict_passthrough():
    ep = {"type": "component", "id": "bar"}
    result = ifl.normalize_endpoint_spec(ep)
    assert result is ep


def test_normalize_bare_component_dict():
    comp = ifl.make_component("x", lambda: None)
    result = ifl.normalize_endpoint_spec(comp)
    assert result["type"] == "component"
    assert result["ref"] is comp


def test_normalize_unknown_tuple_raises():
    with pytest.raises(ValueError, match="Unknown endpoint tuple type"):
        ifl.normalize_endpoint_spec(("bogus", "value"))


def test_normalize_unsupported_type_raises():
    with pytest.raises(ValueError, match="Unsupported endpoint spec"):
        ifl.normalize_endpoint_spec(42)


# =============================================================================
# ROUTE MANAGEMENT
# =============================================================================

def test_add_route_appends():
    ifl.register_component("a", lambda: None)
    ifl.register_component("b", lambda: None)
    ifl.add_route({
        "src": ("component", "a"), "src-channel": "out",
        "dest": ("component", "b"), "dest-channel": "in",
    })
    assert len(ifl.routes) == 1
    assert ifl.routes[0]["src"]["type"] == "component"
    assert ifl.routes[0]["src"]["id"] == "a"
    assert ifl.routes[0]["src-channel"] == "out"
    assert ifl.routes[0]["dest"]["id"] == "b"
    assert ifl.routes[0]["dest-channel"] == "in"
    assert ifl.routes[0]["persistent"] is False


def test_add_route_resolves_refs():
    comp = ifl.register_component("x", lambda: None)
    ifl.add_route({
        "src": ("component", "x"), "src-channel": "out",
        "dest": ("component", "x"), "dest-channel": "in",
    })
    assert ifl.routes[0]["src"]["ref"] is comp
    assert ifl.routes[0]["dest"]["ref"] is comp


def test_add_route_unresolvable_raises():
    with pytest.raises(ValueError, match="Cannot resolve"):
        ifl.add_route({
            "src": ("component", "ghost"), "src-channel": "out",
            "dest": ("component", "ghost"), "dest-channel": "in",
        })


def test_add_route_persistent_validation():
    ifl.register_component("a", lambda: None)
    output = []
    with pytest.raises(ValueError, match="not persistable"):
        ifl.add_route({
            "src": ("component", "a"), "src-channel": "out",
            "dest": ("list", output), "dest-channel": "in",
            "persistent": True,
        })


def test_add_route_persistent_allowed():
    ifl.register_component("a", lambda: None)
    ifl.register_component("b", lambda: None)
    ifl.add_route({
        "src": ("component", "a"), "src-channel": "out",
        "dest": ("component", "b"), "dest-channel": "in",
        "persistent": True,
    })
    assert ifl.routes[0]["persistent"] is True


def test_clear_routes():
    ifl.register_component("a", lambda: None)
    ifl.register_component("b", lambda: None)
    ifl.add_route({
        "src": ("component", "a"), "src-channel": "x",
        "dest": ("component", "b"), "dest-channel": "y",
    })
    assert len(ifl.routes) == 1
    ifl.clear_routes()
    assert len(ifl.routes) == 0


def test_remove_route():
    ifl.register_component("a", lambda: None)
    ifl.register_component("b", lambda: None)
    ifl.add_route({
        "src": ("component", "a"), "src-channel": "out",
        "dest": ("component", "b"), "dest-channel": "in",
    })
    assert len(ifl.routes) == 1
    src_ep = ifl.routes[0]["src"]
    dest_ep = ifl.routes[0]["dest"]
    result = ifl.remove_route(src_ep, "out", dest_ep, "in")
    assert result is True
    assert len(ifl.routes) == 0


def test_remove_route_not_found():
    src = {"type": "component", "id": "a"}
    dest = {"type": "component", "id": "b"}
    result = ifl.remove_route(src, "out", dest, "in")
    assert result is False


# =============================================================================
# EMIT SIGNAL
# =============================================================================

def test_emit_signal_appends_to_outbox():
    comp = ifl.register_component("emitter", lambda: None)
    ifl.g["component"] = comp
    ifl.emit_signal("data", {"value": 99})
    ifl.g["component"] = None

    assert len(comp["outbox"]) == 1
    msg = comp["outbox"][0]
    assert msg["channel"] == "data"
    assert msg["signal"] == {"value": 99}
    assert "timestamp" in msg


# =============================================================================
# ROUTING — route_everything()
# =============================================================================

def _add_route(src, src_channel, dest, dest_channel):
    """Test helper: build a route dict and call add_route."""
    ifl.add_route({
        "src": src, "src-channel": src_channel,
        "dest": dest, "dest-channel": dest_channel,
    })


def test_route_everything_basic_delivery():
    """Message in src outbox is delivered to dest inbox with channel rewrite."""
    src = ifl.register_component("src", lambda: None)
    dest = ifl.register_component("dest", lambda: None)

    _add_route(("component", "src"), "out", ("component", "dest"), "in")

    src["outbox"].append(ifl.make_message("out", {"x": 1}))
    ifl.route_everything()

    # src outbox should be drained
    assert len(src["outbox"]) == 0
    # dest inbox should have the message with rewritten channel
    assert len(dest["inbox"]) == 1
    assert dest["inbox"][0]["channel"] == "in"
    assert dest["inbox"][0]["signal"] == {"x": 1}


def test_route_everything_preserves_timestamp():
    src = ifl.register_component("src", lambda: None)
    dest = ifl.register_component("dest", lambda: None)

    _add_route(("component", "src"), "out", ("component", "dest"), "in")

    original_msg = ifl.make_message("out", {})
    original_ts = original_msg["timestamp"]
    src["outbox"].append(original_msg)
    ifl.route_everything()

    assert dest["inbox"][0]["timestamp"] == original_ts


def test_route_everything_no_match_consumes_message():
    """Messages with no matching channel are still consumed from outbox."""
    src = ifl.register_component("src", lambda: None)
    ifl.register_component("dest", lambda: None)

    _add_route(("component", "src"), "out", ("component", "dest"), "in")

    # Message on wrong channel
    src["outbox"].append(ifl.make_message("wrong_channel", {}))
    ifl.route_everything()

    assert len(src["outbox"]) == 0
    assert len(ifl.components["dest"]["inbox"]) == 0


def test_route_everything_fanout():
    """One message delivered to multiple destinations matching the same channel."""
    src = ifl.register_component("src", lambda: None)
    d1 = ifl.register_component("d1", lambda: None)
    d2 = ifl.register_component("d2", lambda: None)

    _add_route(("component", "src"), "out", ("component", "d1"), "in_a")
    _add_route(("component", "src"), "out", ("component", "d2"), "in_b")

    src["outbox"].append(ifl.make_message("out", {"fanout": True}))
    ifl.route_everything()

    assert len(d1["inbox"]) == 1
    assert d1["inbox"][0]["channel"] == "in_a"
    assert len(d2["inbox"]) == 1
    assert d2["inbox"][0]["channel"] == "in_b"
    assert d1["inbox"][0]["signal"] == {"fanout": True}
    assert d2["inbox"][0]["signal"] == {"fanout": True}


def test_route_everything_multiple_messages_fifo():
    """Multiple outbox messages are routed in FIFO order."""
    src = ifl.register_component("src", lambda: None)
    dest = ifl.register_component("dest", lambda: None)

    _add_route(("component", "src"), "out", ("component", "dest"), "in")

    src["outbox"].append(ifl.make_message("out", {"seq": 1}))
    src["outbox"].append(ifl.make_message("out", {"seq": 2}))
    src["outbox"].append(ifl.make_message("out", {"seq": 3}))
    ifl.route_everything()

    assert len(dest["inbox"]) == 3
    assert dest["inbox"][0]["signal"]["seq"] == 1
    assert dest["inbox"][1]["signal"]["seq"] == 2
    assert dest["inbox"][2]["signal"]["seq"] == 3


def test_route_everything_unresolvable_rejected_at_add():
    """Routes with unresolvable endpoints are rejected at add_route time."""
    ifl.register_component("src", lambda: None)
    with pytest.raises(ValueError, match="Cannot resolve"):
        _add_route(("component", "src"), "out", ("component", "ghost"), "in")


def test_route_everything_with_list_dest():
    """List endpoint receives routed messages."""
    src = ifl.register_component("src", lambda: None)
    output_list = []

    _add_route(("component", "src"), "out", ("list", output_list), "result")

    src["outbox"].append(ifl.make_message("out", {"val": 7}))
    ifl.route_everything()

    assert len(output_list) == 1
    assert output_list[0]["channel"] == "result"
    assert output_list[0]["signal"] == {"val": 7}


def test_route_everything_with_list_source():
    """List endpoint can serve as a source outbox."""
    source_list = [ifl.make_message("data", {"from": "list"})]
    dest = ifl.register_component("dest", lambda: None)

    _add_route(("list", source_list), "data", ("component", "dest"), "in")

    ifl.route_everything()

    assert len(source_list) == 0  # drained
    assert len(dest["inbox"]) == 1
    assert dest["inbox"][0]["channel"] == "in"


# =============================================================================
# ACTIVATION — activate_one_turn_per_component()
# =============================================================================

def test_activation_pops_one_message():
    """Each component processes at most one inbox message per activation round."""
    log = []

    def act():
        log.append(ifl.g["msg"]["signal"])

    comp = ifl.register_component("worker", act)
    comp["inbox"].append(ifl.make_message("in", {"n": 1}))
    comp["inbox"].append(ifl.make_message("in", {"n": 2}))

    ifl.activate_one_turn_per_component()

    assert len(log) == 1
    assert log[0] == {"n": 1}
    assert len(comp["inbox"]) == 1  # second message still waiting


def test_activation_sets_and_clears_globals():
    """g['component'] and g['msg'] are set during activation, cleared after."""
    captured = {}

    def act():
        captured["component"] = ifl.g["component"]
        captured["msg"] = ifl.g["msg"]

    comp = ifl.register_component("observer", act)
    comp["inbox"].append(ifl.make_message("in", {}))

    ifl.activate_one_turn_per_component()

    assert captured["component"] is comp
    assert captured["msg"]["channel"] == "in"
    # After activation, globals should be cleared
    assert ifl.g["component"] is None
    assert ifl.g["msg"] is None


def test_activation_skips_empty_inbox():
    """Components with empty inboxes are not activated."""
    activated = []

    def act():
        activated.append(True)

    ifl.register_component("idle", act)
    ifl.activate_one_turn_per_component()

    assert len(activated) == 0


def test_activation_round_robin_fairness():
    """Multiple components each process one message per round."""
    log = []

    def make_act(name):
        def act():
            log.append(name)
        return act

    a = ifl.register_component("a", make_act("a"))
    b = ifl.register_component("b", make_act("b"))
    c = ifl.register_component("c", make_act("c"))

    a["inbox"].append(ifl.make_message("in", {}))
    a["inbox"].append(ifl.make_message("in", {}))
    b["inbox"].append(ifl.make_message("in", {}))
    c["inbox"].append(ifl.make_message("in", {}))

    ifl.activate_one_turn_per_component()

    # Each activated once, in insertion order
    assert log == ["a", "b", "c"]
    # "a" still has one message left
    assert len(a["inbox"]) == 1


def test_activation_component_can_emit():
    """A component can emit messages during activation (they go to outbox)."""
    def act():
        ifl.emit_signal("result", {"computed": True})

    comp = ifl.register_component("emitter", act)
    comp["inbox"].append(ifl.make_message("trigger", {}))

    ifl.activate_one_turn_per_component()

    assert len(comp["outbox"]) == 1
    assert comp["outbox"][0]["channel"] == "result"


# =============================================================================
# MAIN LOOP — run_cycle, run, is_quiescent
# =============================================================================

def test_is_quiescent_when_empty():
    ifl.register_component("x", lambda: None)
    assert ifl.is_quiescent() is True


def test_is_quiescent_false_with_inbox():
    comp = ifl.register_component("x", lambda: None)
    comp["inbox"].append(ifl.make_message("in", {}))
    assert ifl.is_quiescent() is False


def test_is_quiescent_false_with_outbox():
    comp = ifl.register_component("x", lambda: None)
    comp["outbox"].append(ifl.make_message("out", {}))
    assert ifl.is_quiescent() is False


def test_run_cycle_routes_then_activates():
    """run_cycle does Phase 1 (route) then Phase 2 (activate) in one call."""
    received = []

    def consumer_act():
        received.append(ifl.g["msg"]["signal"])

    src = ifl.register_component("src", lambda: None)
    ifl.register_component("dest", consumer_act)

    _add_route(("component", "src"), "out", ("component", "dest"), "in")

    # Put message in src outbox — Phase 1 routes it, Phase 2 activates dest
    src["outbox"].append(ifl.make_message("out", {"hello": True}))
    ifl.run_cycle()

    assert len(received) == 1
    assert received[0] == {"hello": True}


def test_run_fixed_cycles():
    """run(N) executes exactly N cycles."""
    cycle_count = []

    def act():
        cycle_count.append(1)
        # Re-emit to keep running
        ifl.emit_signal("out", {})

    comp = ifl.register_component("looper", act)
    _add_route(("component", "looper"), "out", ("component", "looper"), "in")

    comp["inbox"].append(ifl.make_message("in", {}))
    ifl.run(5)

    assert len(cycle_count) == 5


def test_run_until_quiescent():
    """run(0) runs until system is quiescent."""
    counter = {"n": 3}

    def countdown_act():
        counter["n"] -= 1
        if counter["n"] > 0:
            ifl.emit_signal("out", {"remaining": counter["n"]})

    comp = ifl.register_component("countdown", countdown_act)
    _add_route(("component", "countdown"), "out", ("component", "countdown"), "in")

    comp["inbox"].append(ifl.make_message("in", {"start": True}))
    ifl.run()

    assert counter["n"] == 0
    assert ifl.is_quiescent() is True


# =============================================================================
# END-TO-END SCENARIOS
# =============================================================================

def test_producer_consumer_pipeline():
    """Classic producer -> consumer: seed triggers producer, output arrives at consumer."""
    def producer_act():
        ifl.emit_signal("out", {"text": "hello from producer"})

    def consumer_act():
        ifl.g["component"]["state"]["received"] = ifl.g["msg"]["signal"]

    producer = ifl.register_component("producer", producer_act)
    ifl.register_component("consumer", consumer_act)

    _add_route(("component", "producer"), "out", ("component", "consumer"), "in")

    producer["inbox"].append(ifl.make_message("kick", {}))
    ifl.run()

    consumer = ifl.components["consumer"]
    assert consumer["state"]["received"] == {"text": "hello from producer"}


def test_three_stage_pipeline():
    """A -> B -> C pipeline: message propagates through all stages."""
    def stage_act():
        incoming = ifl.g["msg"]["signal"]
        stage_name = ifl.g["component"]["id"]
        outgoing = dict(incoming)
        outgoing["path"] = incoming.get("path", []) + [stage_name]
        ifl.emit_signal("out", outgoing)
        ifl.g["component"]["state"]["saw"] = incoming

    ifl.register_component("a", stage_act)
    ifl.register_component("b", stage_act)
    ifl.register_component("c", stage_act)

    _add_route(("component", "a"), "out", ("component", "b"), "in")
    _add_route(("component", "b"), "out", ("component", "c"), "in")

    # Collect c's output in a list endpoint
    output = []
    _add_route(("component", "c"), "out", ("list", output), "final")

    ifl.components["a"]["inbox"].append(ifl.make_message("in", {"origin": "test"}))
    ifl.run()

    assert len(output) == 1
    assert output[0]["signal"]["path"] == ["a", "b", "c"]
    assert output[0]["channel"] == "final"


def test_fanout_and_collect():
    """One source fans out to two consumers, both receive the message."""
    results = {"d1": None, "d2": None}

    def make_collector(name):
        def act():
            results[name] = ifl.g["msg"]["signal"]
        return act

    src = ifl.register_component("src", lambda: None)
    ifl.register_component("d1", make_collector("d1"))
    ifl.register_component("d2", make_collector("d2"))

    _add_route(("component", "src"), "broadcast", ("component", "d1"), "in")
    _add_route(("component", "src"), "broadcast", ("component", "d2"), "in")

    src["outbox"].append(ifl.make_message("broadcast", {"data": 42}))
    ifl.run()

    assert results["d1"] == {"data": 42}
    assert results["d2"] == {"data": 42}


def test_component_state_persists_across_cycles():
    """Component state dict persists across multiple activation cycles."""
    def counter_act():
        state = ifl.g["component"]["state"]
        state["count"] = state.get("count", 0) + 1
        if state["count"] < 3:
            ifl.emit_signal("out", {})

    comp = ifl.register_component("counter", counter_act)
    _add_route(("component", "counter"), "out", ("component", "counter"), "in")

    comp["inbox"].append(ifl.make_message("in", {}))
    ifl.run()

    assert comp["state"]["count"] == 3
    assert ifl.is_quiescent()


def test_list_to_component_routing():
    """External list used as a source, component as destination."""
    input_list = [
        ifl.make_message("cmd", {"action": "start"}),
        ifl.make_message("cmd", {"action": "stop"}),
    ]

    log = []

    def act():
        log.append(ifl.g["msg"]["signal"]["action"])

    ifl.register_component("handler", act)

    _add_route(("list", input_list), "cmd", ("component", "handler"), "command")

    # Phase 1 drains the list, Phase 2 activates handler (one msg per cycle)
    ifl.run()

    assert log == ["start", "stop"]
    assert len(input_list) == 0


# =============================================================================
# WIRING CONSOLE
# =============================================================================

def test_wiring_console_basic():
    """Wiring console creates routes via address + link + commit."""
    ifl.register_component("p", lambda: None)
    ifl.register_component("q", lambda: None)

    ifl.address_components(("component", "p"), ("component", "q"))
    ifl.link_channels("out", "in")
    ifl.commit_links()

    assert len(ifl.routes) == 1
    assert ifl.routes[0]["src-channel"] == "out"
    assert ifl.routes[0]["dest-channel"] == "in"


def test_wiring_console_multiple_channels():
    """Multiple link_channels calls stage multiple mappings committed together."""
    ifl.register_component("a", lambda: None)
    ifl.register_component("b", lambda: None)

    ifl.address_components(("component", "a"), ("component", "b"))
    ifl.link_channels("data", "input")
    ifl.link_channels("status", "control")
    ifl.commit_links()

    assert len(ifl.routes) == 2
    assert ifl.routes[0]["src-channel"] == "data"
    assert ifl.routes[1]["src-channel"] == "status"


def test_wiring_console_persist():
    """persist_links() marks committed routes as persistent."""
    ifl.register_component("a", lambda: None)
    ifl.register_component("b", lambda: None)

    ifl.address_components(("component", "a"), ("component", "b"))
    ifl.persist_links()
    ifl.link_channels("out", "in")
    ifl.commit_links()

    assert ifl.routes[0]["persistent"] is True


def test_wiring_console_commit_clears_links():
    """After commit_links(), channel-links and persist are reset."""
    ifl.register_component("a", lambda: None)
    ifl.register_component("b", lambda: None)

    ifl.address_components(("component", "a"), ("component", "b"))
    ifl.persist_links()
    ifl.link_channels("out", "in")
    ifl.commit_links()

    assert ifl.wire["channel-links"] == []
    assert ifl.wire["persist"] is False
    # src and dest remain latched
    assert ifl.wire["src"] is not None
    assert ifl.wire["dest"] is not None


def test_wiring_console_preserves_addressing():
    """After commit, src/dest remain for further link_channels + commit cycles."""
    ifl.register_component("a", lambda: None)
    ifl.register_component("b", lambda: None)

    ifl.address_components(("component", "a"), ("component", "b"))
    ifl.link_channels("x", "y")
    ifl.commit_links()

    # Second commit using same addressing
    ifl.link_channels("p", "q")
    ifl.commit_links()

    assert len(ifl.routes) == 2


def test_wiring_console_link_without_src_raises():
    with pytest.raises(ValueError, match="No source"):
        ifl.link_channels("out", "in")


def test_wiring_console_link_without_dest_raises():
    ifl.address_source(("component", "a"))
    with pytest.raises(ValueError, match="No destination"):
        ifl.link_channels("out", "in")


def test_wiring_console_commit_empty_raises():
    ifl.register_component("a", lambda: None)
    ifl.register_component("b", lambda: None)
    ifl.address_components(("component", "a"), ("component", "b"))
    with pytest.raises(ValueError, match="No channel links"):
        ifl.commit_links()


def test_wiring_console_end_to_end():
    """Full wiring console flow: wire, commit, seed, run, verify."""
    def producer_act():
        ifl.emit_signal("out", {"msg": "wired"})

    def consumer_act():
        ifl.g["component"]["state"]["got"] = ifl.g["msg"]["signal"]

    producer = ifl.register_component("producer", producer_act)
    ifl.register_component("consumer", consumer_act)

    ifl.address_components(("component", "producer"), ("component", "consumer"))
    ifl.link_channels("out", "in")
    ifl.commit_links()

    producer["inbox"].append(ifl.make_message("kick", {}))
    ifl.run()

    assert ifl.components["consumer"]["state"]["got"] == {"msg": "wired"}


# =============================================================================
# FILETALK TRANSPORT
# =============================================================================

import json
import os
import tempfile


@pytest.fixture
def ftdir(tmp_path):
    """Provide a temporary directory for filetalk tests."""
    return str(tmp_path / "filetalk")


def test_filetalk_deliver_creates_file(ftdir):
    """Delivering to a filetalk endpoint writes a .json file."""
    ep = {"type": "filetalk", "path": ftdir}
    msg = ifl.make_message("out", {"hello": "world"})
    ifl._filetalk_deliver(ep, msg)

    files = os.listdir(ftdir)
    assert len(files) == 1
    assert files[0].endswith(".json")

    with open(os.path.join(ftdir, files[0]), "r", encoding="utf-8") as f:
        written = json.load(f)
    assert written["channel"] == "out"
    assert written["signal"] == {"hello": "world"}
    assert written["timestamp"] == msg["timestamp"]


def test_filetalk_drain_reads_and_removes(ftdir):
    """Draining a filetalk endpoint reads messages and removes files."""
    os.makedirs(ftdir, exist_ok=True)
    msg = ifl.make_message("data", {"val": 42})
    filepath = os.path.join(ftdir, "msg001.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(msg, f)

    ep = {"type": "filetalk", "path": ftdir}
    msgs = ifl._filetalk_drain(ep)

    assert len(msgs) == 1
    assert msgs[0]["channel"] == "data"
    assert msgs[0]["signal"] == {"val": 42}
    # File should be removed after drain
    assert len(os.listdir(ftdir)) == 0


def test_filetalk_drain_skips_unparseable(ftdir):
    """Files that fail JSON parsing are skipped (presumed incomplete)."""
    os.makedirs(ftdir, exist_ok=True)
    # Write a valid message
    good = os.path.join(ftdir, "good.json")
    with open(good, "w", encoding="utf-8") as f:
        json.dump(ifl.make_message("ch", {"ok": True}), f)
    # Write an incomplete/corrupt file
    bad = os.path.join(ftdir, "bad.json")
    with open(bad, "w", encoding="utf-8") as f:
        f.write('{"channel": "ch", "signal": {')

    ep = {"type": "filetalk", "path": ftdir}
    msgs = ifl._filetalk_drain(ep)

    assert len(msgs) == 1
    assert msgs[0]["signal"] == {"ok": True}
    # Bad file remains, good file removed
    remaining = os.listdir(ftdir)
    assert remaining == ["bad.json"]


def test_filetalk_drain_nonexistent_dir(ftdir):
    """Draining a nonexistent directory returns empty list."""
    ep = {"type": "filetalk", "path": ftdir}
    msgs = ifl._filetalk_drain(ep)
    assert msgs == []


def test_filetalk_drain_ignores_non_json(ftdir):
    """Non-.json files in the directory are ignored."""
    os.makedirs(ftdir, exist_ok=True)
    with open(os.path.join(ftdir, "readme.txt"), "w") as f:
        f.write("not a message")
    with open(os.path.join(ftdir, "msg.json"), "w", encoding="utf-8") as f:
        json.dump(ifl.make_message("ch", {}), f)

    ep = {"type": "filetalk", "path": ftdir}
    msgs = ifl._filetalk_drain(ep)

    assert len(msgs) == 1
    # txt file should remain
    assert "readme.txt" in os.listdir(ftdir)


def test_filetalk_as_dest_in_routing(ftdir):
    """Component routes messages to a filetalk directory endpoint."""
    src = ifl.register_component("src", lambda: None)
    _add_route(("component", "src"), "out", ("filetalk", ftdir), "delivered")

    src["outbox"].append(ifl.make_message("out", {"routed": True}))
    ifl.route_everything()

    files = os.listdir(ftdir)
    assert len(files) == 1
    with open(os.path.join(ftdir, files[0]), "r", encoding="utf-8") as f:
        msg = json.load(f)
    assert msg["channel"] == "delivered"
    assert msg["signal"] == {"routed": True}


def test_filetalk_as_src_in_routing(ftdir):
    """Filetalk directory endpoint drains into a component inbox via routing."""
    os.makedirs(ftdir, exist_ok=True)
    msg = ifl.make_message("input", {"from_file": True})
    with open(os.path.join(ftdir, "msg.json"), "w", encoding="utf-8") as f:
        json.dump(msg, f)

    dest = ifl.register_component("dest", lambda: None)
    _add_route(("filetalk", ftdir), "input", ("component", "dest"), "in")

    ifl.route_everything()

    assert len(dest["inbox"]) == 1
    assert dest["inbox"][0]["channel"] == "in"
    assert dest["inbox"][0]["signal"] == {"from_file": True}
    assert len(os.listdir(ftdir)) == 0


def test_filetalk_end_to_end(ftdir):
    """Full cycle: component emits -> filetalk dir -> route back to component."""
    outdir = os.path.join(ftdir, "outbox")
    indir = os.path.join(ftdir, "inbox")

    def producer_act():
        ifl.emit_signal("out", {"step": "produced"})

    def consumer_act():
        ifl.g["component"]["state"]["got"] = ifl.g["msg"]["signal"]

    producer = ifl.register_component("producer", producer_act)
    ifl.register_component("consumer", consumer_act)

    # producer -> outdir (filetalk)
    _add_route(("component", "producer"), "out", ("filetalk", outdir), "relay")

    # Seed and run two cycles:
    #   Cycle 1: route (nothing to route), activate (producer emits to outbox)
    #   Cycle 2: route (outbox -> filetalk dir), activate (nothing)
    producer["inbox"].append(ifl.make_message("kick", {}))
    ifl.run_cycle()
    ifl.run_cycle()

    # Verify file landed
    assert len(os.listdir(outdir)) == 1

    # Now route from outdir -> consumer
    _add_route(("filetalk", outdir), "relay", ("component", "consumer"), "in")
    ifl.run_cycle()

    assert ifl.components["consumer"]["state"]["got"] == {"step": "produced"}
    assert len(os.listdir(outdir)) == 0
