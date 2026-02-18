"""Unit tests for IntraFlow - In-process Patchboard runtime."""

import json
import os
import queue
import tempfile
import unittest

from intraflow import (
    g, components, routes, wire,
    make_message, emit_signal,
    _make_component_dict, declare_component, make_component, get_component,
    register_component, unregister_component,
    populate_filetalk, populate_queue, populate_list,
    _ROUTE_FIELD_ORDER, order_route, add_route, remove_route, clear_routes,
    address_source, address_dest, address_components, persist_links,
    link_channels, commit_links,
    route_everything, activate_one_turn_per_component,
    run_cycle, is_quiescent, run,
)


def reset_state():
    """Reset all module-level mutable state between tests."""
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
# make_message
# =============================================================================

class TestMakeMessage(unittest.TestCase):
    def test_returns_required_fields(self):
        msg = make_message("out", {"x": 1})
        self.assertEqual(msg["channel"], "out")
        self.assertEqual(msg["signal"], {"x": 1})
        self.assertIn("timestamp", msg)

    def test_timestamp_is_string(self):
        msg = make_message("chan", 42)
        self.assertIsInstance(msg["timestamp"], str)

    def test_timestamp_is_parseable_float(self):
        msg = make_message("chan", None)
        float(msg["timestamp"])  # should not raise

    def test_signal_preserved_by_identity(self):
        signal = {"nested": [1, 2, 3]}
        msg = make_message("c", signal)
        self.assertIs(msg["signal"], signal)


# =============================================================================
# emit_signal
# =============================================================================

class TestEmitSignal(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_appends_to_current_component_outbox(self):
        comp = _make_component_dict()
        g["component"] = comp
        emit_signal("out", {"text": "hello"})
        self.assertEqual(len(comp["outbox"]), 1)
        self.assertEqual(comp["outbox"][0]["channel"], "out")
        self.assertEqual(comp["outbox"][0]["signal"], {"text": "hello"})

    def test_multiple_emits_accumulate(self):
        comp = _make_component_dict()
        g["component"] = comp
        emit_signal("a", 1)
        emit_signal("b", 2)
        self.assertEqual(len(comp["outbox"]), 2)
        self.assertEqual(comp["outbox"][0]["channel"], "a")
        self.assertEqual(comp["outbox"][1]["channel"], "b")


# =============================================================================
# _make_component_dict
# =============================================================================

class TestMakeComponentDict(unittest.TestCase):
    def test_canonical_structure(self):
        comp = _make_component_dict()
        self.assertEqual(comp["type"], "INTRAFLOW-COMPONENT")
        self.assertEqual(comp["inbox"], [])
        self.assertEqual(comp["outbox"], [])
        self.assertIsNone(comp["activation"])
        self.assertEqual(comp["state"], {})
        self.assertEqual(comp["channels"], {"in": {}, "out": {}})
        self.assertFalse(comp["always_active"])

    def test_independent_lists_across_instances(self):
        a = _make_component_dict()
        b = _make_component_dict()
        a["inbox"].append("x")
        self.assertEqual(b["inbox"], [])


# =============================================================================
# declare_component
# =============================================================================

class TestDeclareComponent(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_registers_in_components(self):
        comp = declare_component("foo")
        self.assertIn("foo", components)
        self.assertIs(components["foo"], comp)

    def test_sets_selected_component(self):
        comp = declare_component("foo")
        self.assertIs(g["selected_component"], comp)

    def test_stores_id_in_component(self):
        comp = declare_component("foo")
        self.assertEqual(comp["id"], "foo")

    def test_canonical_structure(self):
        comp = declare_component("foo")
        self.assertEqual(comp["type"], "INTRAFLOW-COMPONENT")
        self.assertEqual(comp["inbox"], [])

    def test_raises_on_duplicate_id(self):
        declare_component("foo")
        with self.assertRaises(ValueError):
            declare_component("foo")

    def test_last_declared_is_selected(self):
        declare_component("a")
        b = declare_component("b")
        self.assertIs(g["selected_component"], b)


# =============================================================================
# make_component (anonymous)
# =============================================================================

class TestMakeComponentAnon(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_not_added_to_registry(self):
        make_component()
        self.assertEqual(len(components), 0)

    def test_sets_selected_component(self):
        comp = make_component()
        self.assertIs(g["selected_component"], comp)

    def test_canonical_structure(self):
        comp = make_component()
        self.assertEqual(comp["type"], "INTRAFLOW-COMPONENT")


# =============================================================================
# get_component
# =============================================================================

class TestGetComponent(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_returns_selected_component(self):
        comp = declare_component("foo")
        self.assertIs(get_component(), comp)

    def test_returns_none_when_nothing_selected(self):
        self.assertIsNone(get_component())


# =============================================================================
# register_component
# =============================================================================

class TestRegisterComponent(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_registers_and_assigns_activation(self):
        fn = lambda: None
        comp = register_component("foo", fn)
        self.assertIn("foo", components)
        self.assertIs(comp["activation"], fn)

    def test_raises_on_duplicate(self):
        register_component("foo", lambda: None)
        with self.assertRaises(ValueError):
            register_component("foo", lambda: None)


# =============================================================================
# unregister_component
# =============================================================================

class TestUnregisterComponent(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_removes_from_registry(self):
        declare_component("foo")
        unregister_component("foo")
        self.assertNotIn("foo", components)

    def test_no_error_on_unknown_id(self):
        unregister_component("nonexistent")  # must not raise


# =============================================================================
# populate_queue
# =============================================================================

class TestPopulateQueue(unittest.TestCase):
    def setUp(self):
        reset_state()

    def _activate(self, comp):
        g["component"] = comp
        g["msg"] = comp["inbox"][0] if comp["inbox"] else None
        comp["activation"]()
        g["component"] = None
        g["msg"] = None

    def test_sets_adapter_fields(self):
        q = queue.Queue()
        comp = declare_component("qa")
        populate_queue(q)
        self.assertEqual(comp["component_type"], "adapter")
        self.assertEqual(comp["adapter_kind"], "queue")
        self.assertTrue(comp["always_active"])
        self.assertIs(comp["state"]["queue"], q)

    def test_outgoing_inbox_to_queue(self):
        q = queue.Queue()
        comp = declare_component("qa")
        populate_queue(q)
        msg = make_message("x", 42)
        comp["inbox"].append(msg)
        self._activate(comp)
        self.assertEqual(comp["inbox"], [])
        self.assertIs(q.get_nowait(), msg)

    def test_incoming_queue_to_outbox(self):
        q = queue.Queue()
        comp = declare_component("qa")
        populate_queue(q)
        msg = make_message("x", 99)
        q.put(msg)
        self._activate(comp)
        self.assertEqual(comp["outbox"], [msg])

    def test_both_directions_in_one_activation(self):
        q = queue.Queue()
        comp = declare_component("qa")
        populate_queue(q)
        incoming = make_message("in", "from_queue")
        q.put(incoming)
        outgoing = make_message("out", "to_queue")
        comp["inbox"].append(outgoing)
        self._activate(comp)
        self.assertEqual(comp["outbox"], [incoming])
        self.assertEqual(comp["inbox"], [])
        self.assertIs(q.get_nowait(), outgoing)


# =============================================================================
# populate_list
# =============================================================================

class TestPopulateList(unittest.TestCase):
    def setUp(self):
        reset_state()

    def _activate(self, comp):
        g["component"] = comp
        comp["activation"]()
        g["component"] = None

    def test_sets_adapter_fields(self):
        L = []
        comp = declare_component("la")
        populate_list(L)
        self.assertEqual(comp["component_type"], "adapter")
        self.assertEqual(comp["adapter_kind"], "list")
        self.assertTrue(comp["always_active"])
        self.assertIs(comp["state"]["list"], L)

    def test_outgoing_inbox_to_list(self):
        L = []
        comp = declare_component("la")
        populate_list(L)
        msg = make_message("x", 1)
        comp["inbox"].append(msg)
        self._activate(comp)
        self.assertEqual(comp["inbox"], [])
        self.assertEqual(L, [msg])

    def test_incoming_list_to_outbox(self):
        L = []
        comp = declare_component("la")
        populate_list(L)
        msg = make_message("x", 2)
        L.append(msg)
        self._activate(comp)
        self.assertEqual(comp["outbox"], [msg])
        self.assertEqual(L, [])

    def test_outgoing_fifo_order(self):
        L = []
        comp = declare_component("la")
        populate_list(L)
        m1 = make_message("x", 1)
        m2 = make_message("x", 2)
        comp["inbox"].extend([m1, m2])
        self._activate(comp)
        self.assertEqual(L, [m1, m2])

    def test_incoming_fifo_order(self):
        L = []
        comp = declare_component("la")
        populate_list(L)
        m1 = make_message("x", 1)
        m2 = make_message("x", 2)
        L.extend([m1, m2])
        self._activate(comp)
        self.assertEqual(comp["outbox"], [m1, m2])


# =============================================================================
# populate_filetalk
# =============================================================================

class TestPopulateFiletalk(unittest.TestCase):
    def setUp(self):
        reset_state()

    def _activate(self, comp):
        g["component"] = comp
        comp["activation"]()
        g["component"] = None

    def _bypass_timing(self, comp):
        comp["state"]["check_after_n_ms"] = 0
        comp["state"]["last_checked_timestamp"] = 0

    def test_sets_adapter_fields(self):
        comp = declare_component("ft")
        populate_filetalk("/out", "/in")
        self.assertEqual(comp["component_type"], "adapter")
        self.assertEqual(comp["adapter_kind"], "filetalk")
        self.assertTrue(comp["always_active"])

    def test_outgoing_writes_message_to_filesystem(self):
        comp = declare_component("ft")
        with tempfile.TemporaryDirectory() as out_dir:
            populate_filetalk(out_dir, None)
            self._bypass_timing(comp)
            msg = make_message("x", {"data": 42})
            comp["inbox"].append(msg)
            self._activate(comp)
            self.assertEqual(comp["inbox"], [])
            files = [f for f in os.listdir(out_dir) if f.endswith(".json")]
            self.assertEqual(len(files), 1)
            with open(os.path.join(out_dir, files[0])) as f:
                written = json.load(f)
            self.assertEqual(written["signal"], {"data": 42})

    def test_incoming_reads_json_files_from_filesystem(self):
        comp = declare_component("ft")
        with tempfile.TemporaryDirectory() as in_dir:
            populate_filetalk(None, in_dir)
            self._bypass_timing(comp)
            msg = {"channel": "x", "signal": {"hello": "world"}, "timestamp": "1.0"}
            with open(os.path.join(in_dir, "msg.json"), "w") as f:
                json.dump(msg, f)
            self._activate(comp)
            self.assertEqual(len(comp["outbox"]), 1)
            self.assertEqual(comp["outbox"][0]["signal"], {"hello": "world"})
            self.assertEqual(os.listdir(in_dir), [])  # file consumed

    def test_timing_check_skips_activation_within_interval(self):
        import time as _time
        comp = declare_component("ft")
        with tempfile.TemporaryDirectory() as out_dir:
            populate_filetalk(out_dir, None)
            comp["state"]["last_checked_timestamp"] = _time.time() * 1000
            comp["state"]["check_after_n_ms"] = 250
            comp["inbox"].append(make_message("x", 1))
            self._activate(comp)
            self.assertEqual(len(comp["inbox"]), 1)  # not consumed — skipped

    def test_outgoing_raises_when_out_path_is_none(self):
        comp = declare_component("ft")
        populate_filetalk(None, None)
        self._bypass_timing(comp)
        comp["inbox"].append(make_message("x", 1))
        with self.assertRaises(ValueError):
            self._activate(comp)

    def test_skips_non_json_files(self):
        comp = declare_component("ft")
        with tempfile.TemporaryDirectory() as in_dir:
            populate_filetalk(None, in_dir)
            self._bypass_timing(comp)
            with open(os.path.join(in_dir, "ignore.txt"), "w") as f:
                f.write("not json")
            self._activate(comp)
            self.assertEqual(comp["outbox"], [])

    def test_skips_malformed_json_files(self):
        comp = declare_component("ft")
        with tempfile.TemporaryDirectory() as in_dir:
            populate_filetalk(None, in_dir)
            self._bypass_timing(comp)
            with open(os.path.join(in_dir, "bad.json"), "w") as f:
                f.write("{not valid json")
            self._activate(comp)
            self.assertEqual(comp["outbox"], [])


# =============================================================================
# order_route
# =============================================================================

class TestOrderRoute(unittest.TestCase):
    def test_reorders_keys_to_canonical_order(self):
        route = {
            "persistent": False,
            "dest-channel": "in",
            "src": {},
            "dest": {},
            "src-channel": "out",
            "src_id": "a",
            "dest_id": "b",
        }
        order_route(route)
        self.assertEqual(list(route.keys()), _ROUTE_FIELD_ORDER)

    def test_preserves_values(self):
        src = {"id": "s"}
        dest = {"id": "d"}
        route = {"src_id": "a", "src": src, "src-channel": "out",
                 "dest_id": "b", "dest": dest, "dest-channel": "in",
                 "persistent": True}
        order_route(route)
        self.assertIs(route["src"], src)
        self.assertIs(route["dest"], dest)
        self.assertEqual(route["src_id"], "a")
        self.assertTrue(route["persistent"])

    def test_extra_keys_appended_after_canonical(self):
        route = {"extra": "val", "src_id": None, "src": {}, "src-channel": "x",
                 "dest_id": None, "dest": {}, "dest-channel": "y", "persistent": False}
        order_route(route)
        keys = list(route.keys())
        self.assertEqual(keys[:7], _ROUTE_FIELD_ORDER)
        self.assertIn("extra", keys)

    def test_idempotent(self):
        route = {"src_id": "a", "src": {}, "src-channel": "x",
                 "dest_id": "b", "dest": {}, "dest-channel": "y", "persistent": False}
        order_route(route)
        order_route(route)
        self.assertEqual(list(route.keys()), _ROUTE_FIELD_ORDER)


# =============================================================================
# add_route
# =============================================================================

class TestAddRoute(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_resolve_src_by_src_id(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src_id": "src", "src": None, "src-channel": "out",
                   "dest_id": "dest", "dest": None, "dest-channel": "in",
                   "persistent": False})
        self.assertIs(routes[0]["src"], src)

    def test_resolve_dest_by_dest_id(self):
        declare_component("src")
        dest = declare_component("dest")
        add_route({"src_id": "src", "src": None, "src-channel": "out",
                   "dest_id": "dest", "dest": None, "dest-channel": "in",
                   "persistent": False})
        self.assertIs(routes[0]["dest"], dest)

    def test_resolve_by_ref(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        self.assertIs(routes[0]["src"], src)
        self.assertIs(routes[0]["dest"], dest)

    def test_raises_on_unknown_src_id(self):
        declare_component("dest")
        with self.assertRaises(ValueError):
            add_route({"src_id": "missing", "src": None, "src-channel": "out",
                       "dest_id": "dest", "dest": None, "dest-channel": "in",
                       "persistent": False})

    def test_raises_on_unknown_dest_id(self):
        declare_component("src")
        with self.assertRaises(ValueError):
            add_route({"src_id": "src", "src": None, "src-channel": "out",
                       "dest_id": "missing", "dest": None, "dest-channel": "in",
                       "persistent": False})

    def test_raises_when_src_ref_mismatches_src_id(self):
        src = declare_component("src")
        declare_component("other")
        dest = declare_component("dest")
        with self.assertRaises(ValueError):
            add_route({"src_id": "other", "src": src, "src-channel": "out",
                       "dest": dest, "dest-channel": "in"})

    def test_raises_when_dest_ref_mismatches_dest_id(self):
        src = declare_component("src")
        dest = declare_component("dest")
        declare_component("other")
        with self.assertRaises(ValueError):
            add_route({"src": src, "src-channel": "out",
                       "dest_id": "other", "dest": dest, "dest-channel": "in"})

    def test_sets_default_src_id_none(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        self.assertIsNone(routes[0]["src_id"])

    def test_sets_default_dest_id_none(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        self.assertIsNone(routes[0]["dest_id"])

    def test_sets_default_persistent_false(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        self.assertFalse(routes[0]["persistent"])

    def test_persistent_requires_src_id(self):
        src = declare_component("src")
        dest = declare_component("dest")
        with self.assertRaises(ValueError):
            add_route({"src": src, "src-channel": "out",
                       "dest_id": "dest", "dest": dest, "dest-channel": "in",
                       "persistent": True})

    def test_persistent_requires_dest_id(self):
        src = declare_component("src")
        dest = declare_component("dest")
        with self.assertRaises(ValueError):
            add_route({"src_id": "src", "src": src, "src-channel": "out",
                       "dest": dest, "dest-channel": "in",
                       "persistent": True})

    def test_persistent_succeeds_with_both_ids(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src_id": "src", "src": src, "src-channel": "out",
                   "dest_id": "dest", "dest": dest, "dest-channel": "in",
                   "persistent": True})
        self.assertTrue(routes[0]["persistent"])

    def test_appends_to_routes(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "a", "dest": dest, "dest-channel": "b"})
        add_route({"src": src, "src-channel": "c", "dest": dest, "dest-channel": "d"})
        self.assertEqual(len(routes), 2)

    def test_route_keys_are_in_canonical_order(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        self.assertEqual(list(routes[0].keys()), _ROUTE_FIELD_ORDER)


# =============================================================================
# remove_route
# =============================================================================

class TestRemoveRoute(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_removes_matching_route(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        result = remove_route(src, "out", dest, "in")
        self.assertTrue(result)
        self.assertEqual(routes, [])

    def test_returns_false_when_not_found(self):
        src = declare_component("src")
        dest = declare_component("dest")
        result = remove_route(src, "out", dest, "in")
        self.assertFalse(result)

    def test_uses_identity_not_equality_for_src(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        other = _make_component_dict()
        result = remove_route(other, "out", dest, "in")
        self.assertFalse(result)
        self.assertEqual(len(routes), 1)

    def test_removes_only_first_match(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        remove_route(src, "out", dest, "in")
        self.assertEqual(len(routes), 1)


# =============================================================================
# clear_routes
# =============================================================================

class TestClearRoutes(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_clears_all_routes(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "a", "dest": dest, "dest-channel": "b"})
        add_route({"src": src, "src-channel": "c", "dest": dest, "dest-channel": "d"})
        clear_routes()
        self.assertEqual(routes, [])


# =============================================================================
# Wiring console primitives
# =============================================================================

class TestWiringConsolePrimitives(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_address_source_sets_wire_src(self):
        comp = declare_component("src")
        address_source(comp)
        self.assertIs(wire["src"], comp)

    def test_address_source_resets_persist(self):
        wire["persist"] = True
        declare_component("src")
        address_source("src")
        self.assertFalse(wire["persist"])

    def test_address_source_resets_channel_links(self):
        wire["channel-links"] = [("a", "b")]
        declare_component("src")
        address_source("src")
        self.assertEqual(wire["channel-links"], [])

    def test_address_dest_sets_wire_dest(self):
        comp = declare_component("dest")
        address_dest(comp)
        self.assertIs(wire["dest"], comp)

    def test_address_components_sets_both(self):
        src = declare_component("src")
        dest = declare_component("dest")
        address_components(src, dest)
        self.assertIs(wire["src"], src)
        self.assertIs(wire["dest"], dest)

    def test_persist_links_sets_flag(self):
        persist_links()
        self.assertTrue(wire["persist"])

    def test_link_channels_appends_tuple(self):
        declare_component("src")
        declare_component("dest")
        address_components("src", "dest")
        link_channels("out", "in")
        self.assertEqual(wire["channel-links"], [("out", "in")])

    def test_link_channels_raises_with_no_src(self):
        with self.assertRaises(ValueError):
            link_channels("out", "in")

    def test_link_channels_raises_with_no_dest(self):
        src = declare_component("src")
        address_source(src)
        with self.assertRaises(ValueError):
            link_channels("out", "in")


# =============================================================================
# commit_links
# =============================================================================

class TestCommitLinks(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_creates_route_from_string_ids(self):
        src = declare_component("src")
        dest = declare_component("dest")
        address_components("src", "dest")
        link_channels("out", "in")
        commit_links()
        self.assertEqual(len(routes), 1)
        self.assertIs(routes[0]["src"], src)
        self.assertIs(routes[0]["dest"], dest)
        self.assertEqual(routes[0]["src-channel"], "out")
        self.assertEqual(routes[0]["dest-channel"], "in")

    def test_creates_route_from_component_refs(self):
        src = declare_component("src")
        dest = declare_component("dest")
        address_components(src, dest)
        link_channels("out", "in")
        commit_links()
        self.assertIs(routes[0]["src"], src)
        self.assertIs(routes[0]["dest"], dest)

    def test_src_id_populated_from_string(self):
        declare_component("src")
        declare_component("dest")
        address_components("src", "dest")
        link_channels("out", "in")
        commit_links()
        self.assertEqual(routes[0]["src_id"], "src")
        self.assertEqual(routes[0]["dest_id"], "dest")

    def test_src_id_populated_from_component_ref(self):
        src = declare_component("src")
        dest = declare_component("dest")
        address_components(src, dest)
        link_channels("out", "in")
        commit_links()
        self.assertEqual(routes[0]["src_id"], "src")
        self.assertEqual(routes[0]["dest_id"], "dest")

    def test_clears_channel_links_after_commit(self):
        declare_component("src")
        declare_component("dest")
        address_components("src", "dest")
        link_channels("out", "in")
        commit_links()
        self.assertEqual(wire["channel-links"], [])

    def test_resets_persist_after_commit(self):
        declare_component("src")
        declare_component("dest")
        address_components("src", "dest")
        persist_links()
        link_channels("out", "in")
        commit_links()
        self.assertFalse(wire["persist"])

    def test_preserves_src_dest_context_after_commit(self):
        declare_component("src")
        declare_component("dest")
        address_components("src", "dest")
        link_channels("out", "in")
        commit_links()
        self.assertIsNotNone(wire["src"])
        self.assertIsNotNone(wire["dest"])

    def test_multiple_links_create_multiple_routes(self):
        declare_component("src")
        declare_component("dest")
        address_components("src", "dest")
        link_channels("a", "x")
        link_channels("b", "y")
        commit_links()
        self.assertEqual(len(routes), 2)

    def test_persistent_route_via_commit(self):
        declare_component("src")
        declare_component("dest")
        address_components("src", "dest")
        persist_links()
        link_channels("out", "in")
        commit_links()
        self.assertTrue(routes[0]["persistent"])

    def test_raises_with_no_src(self):
        with self.assertRaises(ValueError):
            commit_links()

    def test_raises_with_no_dest(self):
        src = declare_component("src")
        address_source(src)
        with self.assertRaises(ValueError):
            commit_links()

    def test_raises_with_no_links(self):
        src = declare_component("src")
        dest = declare_component("dest")
        address_components(src, dest)
        with self.assertRaises(ValueError):
            commit_links()

    def test_raises_on_unknown_string_src(self):
        declare_component("dest")
        address_source("nonexistent")
        address_dest("dest")
        link_channels("out", "in")
        with self.assertRaises(ValueError):
            commit_links()

    def test_raises_on_unknown_string_dest(self):
        declare_component("src")
        address_source("src")
        address_dest("nonexistent")
        link_channels("out", "in")
        with self.assertRaises(ValueError):
            commit_links()


# =============================================================================
# route_everything
# =============================================================================

class TestRouteEverything(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_delivers_message_to_dest_inbox(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        src["outbox"].append({"channel": "out", "signal": 42, "timestamp": "1.0"})
        route_everything()
        self.assertEqual(len(dest["inbox"]), 1)
        self.assertEqual(dest["inbox"][0]["signal"], 42)

    def test_rewrites_channel_on_delivery(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        src["outbox"].append({"channel": "out", "signal": 1, "timestamp": "1.0"})
        route_everything()
        self.assertEqual(dest["inbox"][0]["channel"], "in")

    def test_preserves_signal_and_timestamp(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        src["outbox"].append({"channel": "out", "signal": {"x": 99}, "timestamp": "123.456"})
        route_everything()
        self.assertEqual(dest["inbox"][0]["signal"], {"x": 99})
        self.assertEqual(dest["inbox"][0]["timestamp"], "123.456")

    def test_drains_src_outbox(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        src["outbox"].append({"channel": "out", "signal": 1, "timestamp": "1.0"})
        route_everything()
        self.assertEqual(src["outbox"], [])

    def test_unmatched_channel_not_delivered(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        src["outbox"].append({"channel": "other", "signal": 1, "timestamp": "1.0"})
        route_everything()
        self.assertEqual(dest["inbox"], [])

    def test_fanout_delivers_to_all_destinations(self):
        src = declare_component("src")
        d1 = declare_component("d1")
        d2 = declare_component("d2")
        add_route({"src": src, "src-channel": "out", "dest": d1, "dest-channel": "in"})
        add_route({"src": src, "src-channel": "out", "dest": d2, "dest-channel": "in"})
        src["outbox"].append({"channel": "out", "signal": "x", "timestamp": "1.0"})
        route_everything()
        self.assertEqual(len(d1["inbox"]), 1)
        self.assertEqual(len(d2["inbox"]), 1)

    def test_fanout_copies_are_distinct_objects(self):
        src = declare_component("src")
        d1 = declare_component("d1")
        d2 = declare_component("d2")
        add_route({"src": src, "src-channel": "out", "dest": d1, "dest-channel": "a"})
        add_route({"src": src, "src-channel": "out", "dest": d2, "dest-channel": "b"})
        src["outbox"].append({"channel": "out", "signal": "x", "timestamp": "1.0"})
        route_everything()
        self.assertIsNot(d1["inbox"][0], d2["inbox"][0])

    def test_multiple_messages_all_routed(self):
        src = declare_component("src")
        dest = declare_component("dest")
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        src["outbox"].append({"channel": "out", "signal": 1, "timestamp": "1.0"})
        src["outbox"].append({"channel": "out", "signal": 2, "timestamp": "2.0"})
        route_everything()
        self.assertEqual(len(dest["inbox"]), 2)

    def test_component_not_in_routes_outbox_untouched(self):
        src = declare_component("src")
        src["outbox"].append({"channel": "out", "signal": 1, "timestamp": "1.0"})
        route_everything()
        self.assertEqual(len(src["outbox"]), 1)  # no route, not drained


# =============================================================================
# activate_one_turn_per_component
# =============================================================================

class TestActivateOneTurnPerComponent(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_activates_component_with_inbox(self):
        activated = []
        comp = register_component("c", lambda: activated.append(True))
        comp["inbox"].append(make_message("x", 1))
        activate_one_turn_per_component()
        self.assertEqual(len(activated), 1)

    def test_pops_exactly_one_message(self):
        comp = register_component("c", lambda: None)
        comp["inbox"].append(make_message("x", 1))
        comp["inbox"].append(make_message("x", 2))
        activate_one_turn_per_component()
        self.assertEqual(len(comp["inbox"]), 1)

    def test_sets_g_component_during_activation(self):
        captured = {}
        def fn():
            captured["comp"] = g["component"]
        comp = register_component("c", fn)
        comp["inbox"].append(make_message("x", 1))
        activate_one_turn_per_component()
        self.assertIs(captured["comp"], comp)

    def test_sets_g_msg_during_activation(self):
        captured = {}
        def fn():
            captured["msg"] = g["msg"]
        comp = register_component("c", fn)
        msg = make_message("x", 99)
        comp["inbox"].append(msg)
        activate_one_turn_per_component()
        self.assertIs(captured["msg"], msg)

    def test_clears_g_after_activation(self):
        comp = register_component("c", lambda: None)
        comp["inbox"].append(make_message("x", 1))
        activate_one_turn_per_component()
        self.assertIsNone(g["component"])
        self.assertIsNone(g["msg"])

    def test_skips_component_with_empty_inbox(self):
        activated = []
        register_component("c", lambda: activated.append(True))
        activate_one_turn_per_component()
        self.assertEqual(activated, [])

    def test_always_active_fires_with_empty_inbox(self):
        msgs = []
        def fn():
            msgs.append(g["msg"])
        comp = register_component("c", fn)
        comp["always_active"] = True
        activate_one_turn_per_component()
        self.assertEqual(len(msgs), 1)
        self.assertIsNone(msgs[0])

    def test_always_active_uses_inbox_message_when_available(self):
        msgs = []
        def fn():
            msgs.append(g["msg"])
        comp = register_component("c", fn)
        comp["always_active"] = True
        msg = make_message("x", 1)
        comp["inbox"].append(msg)
        activate_one_turn_per_component()
        self.assertIs(msgs[0], msg)

    def test_fifo_ordering_across_cycles(self):
        order = []
        def fn():
            order.append(g["msg"]["signal"])
        comp = register_component("c", fn)
        comp["inbox"].append(make_message("x", "first"))
        comp["inbox"].append(make_message("x", "second"))
        activate_one_turn_per_component()
        activate_one_turn_per_component()
        self.assertEqual(order, ["first", "second"])


# =============================================================================
# is_quiescent
# =============================================================================

class TestIsQuiescent(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_true_with_no_components(self):
        self.assertTrue(is_quiescent())

    def test_true_when_all_empty(self):
        declare_component("a")
        declare_component("b")
        self.assertTrue(is_quiescent())

    def test_false_when_inbox_has_messages(self):
        comp = declare_component("a")
        comp["inbox"].append(make_message("x", 1))
        self.assertFalse(is_quiescent())

    def test_false_when_outbox_has_messages(self):
        comp = declare_component("a")
        comp["outbox"].append(make_message("x", 1))
        self.assertFalse(is_quiescent())


# =============================================================================
# run_cycle
# =============================================================================

class TestRunCycle(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_routes_then_activates_in_order(self):
        events = []
        def fn():
            events.append(g["msg"]["signal"])
        src = register_component("src", lambda: None)
        dest = register_component("dest", fn)
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        src["outbox"].append({"channel": "out", "signal": "hello", "timestamp": "1.0"})
        run_cycle()
        self.assertEqual(events, ["hello"])


# =============================================================================
# run
# =============================================================================

class TestRun(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_fixed_cycles_runs_exact_count(self):
        count = []
        comp = register_component("c", lambda: count.append(1))
        comp["always_active"] = True
        run(cycles=3)
        self.assertEqual(len(count), 3)

    def test_runs_until_quiescent(self):
        def producer():
            emit_signal("out", "ping")
        def consumer():
            pass
        src = register_component("src", producer)
        dest = register_component("dest", consumer)
        add_route({"src": src, "src-channel": "out", "dest": dest, "dest-channel": "in"})
        src["inbox"].append(make_message("kick", None))
        run()
        self.assertTrue(is_quiescent())

    def test_always_runs_at_least_one_cycle(self):
        count = []
        comp = register_component("c", lambda: count.append(1))
        comp["always_active"] = True
        run(cycles=0)
        self.assertGreaterEqual(len(count), 1)

    def test_end_to_end_message_delivery(self):
        def producer():
            emit_signal("out", {"text": "hello"})
        def consumer():
            g["component"]["state"]["received"] = g["msg"]["signal"]
        src = register_component("producer", producer)
        dest = register_component("consumer", consumer)
        address_components("producer", "consumer")
        link_channels("out", "in")
        commit_links()
        src["inbox"].append(make_message("kick", None))
        run()
        self.assertEqual(dest["state"]["received"], {"text": "hello"})


if __name__ == "__main__":
    unittest.main()
