"""
Tests for the Patchboard Router.
"""

import json
import tempfile
import time
from pathlib import Path

import pytest

# Import router module components
import sys
_src_path = str(Path(__file__).parent.parent.parent / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# Import from src/patchboard_router, not tests/patchboard_router
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "patchboard_router.router",
    Path(__file__).parent.parent.parent / "src" / "patchboard_router" / "router.py"
)
router = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(router)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def reset_globals():
    """Reset router global state before and after each test."""
    # Store original state
    original = dict(router.g)
    original_stats = dict(router.g["stats"])

    # Reset to initial state
    router.g.update({
        "mode": "normal",
        "quit_requested": False,
        "tick": 0,
        "router_id": None,
        "started_at_utc": None,
        "routes": [],
        "routes_dirty": False,
        "state_dirty": False,
        "stats": {
            "seen": 0,
            "delivered": 0,
            "deleted": 0,
            "skipped_unreadable": 0,
            "skipped_missing_folder": 0,
            "discarded_unrouted": 0,
        },
        "project_dir": None,
        "events_path": None,
        "status_path": None,
        "routes_path": None,
        "inbox_path": None,
        "outbox_path": None,
    })

    yield

    # Restore original state
    router.g.update(original)
    router.g["stats"].update(original_stats)


# =============================================================================
# PATH UTILITIES TESTS
# =============================================================================

class TestPathUtilities:

    def test_canonicalize_path_absolute(self, temp_dir):
        """Canonicalize returns absolute path."""
        result = router.canonicalize_path(temp_dir)
        assert result.is_absolute()

    def test_canonicalize_path_resolves_dots(self, temp_dir):
        """Canonicalize resolves . and .. components."""
        subdir = temp_dir / "a" / "b"
        subdir.mkdir(parents=True)

        path_with_dots = temp_dir / "a" / "b" / ".." / "b"
        result = router.canonicalize_path(path_with_dots)
        assert result == subdir

    def test_paths_equal_same_path(self, temp_dir):
        """paths_equal returns True for equivalent paths."""
        p1 = temp_dir / "test"
        p2 = temp_dir / "." / "test"
        assert router.paths_equal(p1, p2)

    def test_paths_equal_different_paths(self, temp_dir):
        """paths_equal returns False for different paths."""
        p1 = temp_dir / "test1"
        p2 = temp_dir / "test2"
        assert not router.paths_equal(p1, p2)


# =============================================================================
# FILE I/O TESTS
# =============================================================================

class TestFileIO:

    def test_write_json_atomic_creates_file(self, temp_dir):
        """write_json_atomic creates a JSON file."""
        path = temp_dir / "test.json"
        data = {"key": "value"}

        router.write_json_atomic(path, data)

        assert path.exists()
        with open(path) as f:
            result = json.load(f)
        assert result == data

    def test_write_json_atomic_pretty(self, temp_dir):
        """write_json_atomic with 'p' flag produces indented output."""
        path = temp_dir / "test.json"
        data = {"key": "value"}

        router.write_json_atomic(path, data, "p")

        content = path.read_text()
        assert "\n" in content
        assert "  " in content  # indentation

    def test_write_json_atomic_compact(self, temp_dir):
        """write_json_atomic without 'p' flag produces compact output."""
        path = temp_dir / "test.json"
        data = {"key": "value"}

        router.write_json_atomic(path, data)

        content = path.read_text()
        assert content == '{"key": "value"}'

    def test_append_jsonl(self, temp_dir):
        """append_jsonl appends JSON lines."""
        path = temp_dir / "test.jsonl"

        router.append_jsonl(path, {"a": 1})
        router.append_jsonl(path, {"b": 2})

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"a": 1}
        assert json.loads(lines[1]) == {"b": 2}

    def test_read_json_file_success(self, temp_dir):
        """read_json_file returns data and True for valid JSON."""
        path = temp_dir / "test.json"
        path.write_text('{"key": "value"}')

        data, ok = router.read_json_file(path)

        assert ok is True
        assert data == {"key": "value"}

    def test_read_json_file_not_found(self, temp_dir):
        """read_json_file returns None and False for missing file."""
        path = temp_dir / "nonexistent.json"

        data, ok = router.read_json_file(path)

        assert ok is False
        assert data is None

    def test_read_json_file_invalid_json(self, temp_dir):
        """read_json_file returns None and False for invalid JSON."""
        path = temp_dir / "test.json"
        path.write_text("not valid json {{{")

        data, ok = router.read_json_file(path)

        assert ok is False
        assert data is None


# =============================================================================
# MESSAGE HELPERS TESTS
# =============================================================================

class TestMessageHelpers:

    def test_make_message_structure(self):
        """make_message creates correct structure."""
        msg = router.make_message("test-channel", {"data": 123})

        assert "channel" in msg
        assert "signal" in msg
        assert "timestamp" in msg
        assert msg["channel"] == "test-channel"
        assert msg["signal"] == {"data": 123}

    def test_make_message_timestamp_format(self):
        """make_message timestamp is numeric string."""
        msg = router.make_message("ch", {})

        ts = float(msg["timestamp"])
        assert ts > 0

    def test_write_message_creates_file(self, temp_dir):
        """write_message creates a JSON file in the folder."""
        folder = temp_dir / "outbox"
        folder.mkdir()

        filename = router.write_message(folder, "test", {"hello": "world"})

        filepath = folder / filename
        assert filepath.exists()

        data, ok = router.read_json_file(filepath)
        assert ok
        assert data["channel"] == "test"
        assert data["signal"] == {"hello": "world"}

    def test_write_message_unique_filenames(self, temp_dir):
        """write_message generates unique filenames."""
        folder = temp_dir / "outbox"
        folder.mkdir()

        filenames = set()
        for _ in range(10):
            filename = router.write_message(folder, "ch", {})
            filenames.add(filename)

        assert len(filenames) == 10

    def test_read_message_success(self, temp_dir):
        """read_message parses valid message file."""
        filepath = temp_dir / "msg.json"
        filepath.write_text('{"channel": "test", "signal": {}, "timestamp": "123"}')

        msg, ok = router.read_message(filepath)

        assert ok
        assert msg["channel"] == "test"


# =============================================================================
# ROUTING TABLE TESTS
# =============================================================================

class TestRoutingTable:

    def test_add_route_new(self, temp_dir, reset_globals):
        """add_route adds a new route and returns True."""
        # Set up events path
        router.g["events_path"] = temp_dir / "events.jsonl"

        result = router.add_route(
            temp_dir / "src",
            "input",
            "output",
            temp_dir / "dest"
        )

        assert result is True
        assert len(router.g["routes"]) == 1
        assert router.g["routes_dirty"] is True

    def test_add_route_duplicate(self, temp_dir, reset_globals):
        """add_route returns False for duplicate route."""
        router.g["events_path"] = temp_dir / "events.jsonl"

        router.add_route(temp_dir / "src", "ch", "ch", temp_dir / "dest")
        result = router.add_route(temp_dir / "src", "ch", "ch", temp_dir / "dest")

        assert result is False
        assert len(router.g["routes"]) == 1

    def test_remove_route_existing(self, temp_dir, reset_globals):
        """remove_route removes existing route and returns True."""
        router.g["events_path"] = temp_dir / "events.jsonl"

        router.add_route(temp_dir / "src", "ch", "ch", temp_dir / "dest")
        result = router.remove_route(temp_dir / "src", "ch", "ch", temp_dir / "dest")

        assert result is True
        assert len(router.g["routes"]) == 0

    def test_remove_route_nonexistent(self, temp_dir, reset_globals):
        """remove_route returns False for nonexistent route."""
        router.g["events_path"] = temp_dir / "events.jsonl"

        result = router.remove_route(temp_dir / "src", "ch", "ch", temp_dir / "dest")

        assert result is False

    def test_is_duplicate_route(self, temp_dir, reset_globals):
        """is_duplicate_route detects duplicates."""
        router.g["events_path"] = temp_dir / "events.jsonl"

        assert not router.is_duplicate_route(temp_dir / "src", "ch", "ch", temp_dir / "dest")

        router.add_route(temp_dir / "src", "ch", "ch", temp_dir / "dest")

        assert router.is_duplicate_route(temp_dir / "src", "ch", "ch", temp_dir / "dest")

    def test_routes_for_source_exact_match(self, temp_dir, reset_globals):
        """routes_for_source returns matching routes."""
        router.g["events_path"] = temp_dir / "events.jsonl"
        src = temp_dir / "src"
        dest = temp_dir / "dest"

        router.add_route(src, "input", "output", dest)

        results = router.routes_for_source(src, "input")

        assert len(results) == 1
        assert results[0][0] == "output"  # dest channel
        assert results[0][1] == dest  # dest folder

    def test_routes_for_source_wildcard(self, temp_dir, reset_globals):
        """routes_for_source matches wildcard routes."""
        router.g["events_path"] = temp_dir / "events.jsonl"
        src = temp_dir / "src"
        dest = temp_dir / "dest"

        router.add_route(src, "*", "all", dest)

        results = router.routes_for_source(src, "anything")

        assert len(results) == 1
        assert results[0][0] == "all"

    def test_routes_for_source_no_match(self, temp_dir, reset_globals):
        """routes_for_source returns empty list for no matches."""
        router.g["events_path"] = temp_dir / "events.jsonl"
        src = temp_dir / "src"
        dest = temp_dir / "dest"

        router.add_route(src, "specific", "output", dest)

        results = router.routes_for_source(src, "other")

        assert len(results) == 0

    def test_routes_for_source_fanout(self, temp_dir, reset_globals):
        """routes_for_source returns multiple routes for fanout."""
        router.g["events_path"] = temp_dir / "events.jsonl"
        src = temp_dir / "src"
        dest1 = temp_dir / "dest1"
        dest2 = temp_dir / "dest2"

        router.add_route(src, "input", "out1", dest1)
        router.add_route(src, "input", "out2", dest2)

        results = router.routes_for_source(src, "input")

        assert len(results) == 2


# =============================================================================
# EVENTS LOG TESTS
# =============================================================================

class TestEventsLog:

    def test_log_event_appends(self, temp_dir, reset_globals):
        """log_event appends event to events log."""
        router.g["events_path"] = temp_dir / "events.jsonl"

        router.log_event("test_event", {"key": "value"})

        content = router.g["events_path"].read_text()
        event = json.loads(content.strip())
        assert event["event"] == "test_event"
        assert event["key"] == "value"
        assert "ts_utc" in event

    def test_replay_events_reconstructs_routes(self, temp_dir, reset_globals):
        """replay_events_log_and_rebuild_routing_table reconstructs routes."""
        events_path = temp_dir / "events.jsonl"
        router.g["events_path"] = events_path

        # Write events directly
        events = [
            {"event": "startup", "ts_utc": "1"},
            {"event": "route_added", "ts_utc": "2",
             "source-folder": "/src", "source-channel": "in",
             "destination-channel": "out", "destination-folder": "/dest"},
            {"event": "route_added", "ts_utc": "3",
             "source-folder": "/src2", "source-channel": "in2",
             "destination-channel": "out2", "destination-folder": "/dest2"},
        ]
        with open(events_path, "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        router.replay_events_log_and_rebuild_routing_table()

        assert len(router.g["routes"]) == 2

    def test_replay_events_handles_remove(self, temp_dir, reset_globals):
        """replay handles route_removed events."""
        events_path = temp_dir / "events.jsonl"
        router.g["events_path"] = events_path

        events = [
            {"event": "route_added", "ts_utc": "1",
             "source-folder": "/src", "source-channel": "in",
             "destination-channel": "out", "destination-folder": "/dest"},
            {"event": "route_removed", "ts_utc": "2",
             "source-folder": "/src", "source-channel": "in",
             "destination-channel": "out", "destination-folder": "/dest"},
        ]
        with open(events_path, "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        router.replay_events_log_and_rebuild_routing_table()

        assert len(router.g["routes"]) == 0

    def test_replay_events_empty_file(self, temp_dir, reset_globals):
        """replay handles empty events file."""
        events_path = temp_dir / "events.jsonl"
        events_path.touch()
        router.g["events_path"] = events_path

        router.replay_events_log_and_rebuild_routing_table()

        assert len(router.g["routes"]) == 0

    def test_replay_events_missing_file(self, temp_dir, reset_globals):
        """replay handles missing events file."""
        router.g["events_path"] = temp_dir / "nonexistent.jsonl"

        router.replay_events_log_and_rebuild_routing_table()

        assert len(router.g["routes"]) == 0


# =============================================================================
# DELIVERY ENGINE TESTS
# =============================================================================

class TestDeliveryEngine:

    def test_plan_deliveries_finds_messages(self, temp_dir, reset_globals):
        """_plan_deliveries finds messages in source folders."""
        src = temp_dir / "src"
        src.mkdir()
        dest = temp_dir / "dest"
        dest.mkdir()

        router.g["events_path"] = temp_dir / "events.jsonl"
        router.add_route(src, "test", "output", dest)

        # Write a message
        msg_path = src / "test.json"
        msg_path.write_text('{"channel": "test", "signal": {}, "timestamp": "1"}')

        copies, deletes = router._plan_deliveries([src])

        assert len(copies) == 1
        assert len(deletes) == 1

    def test_plan_deliveries_skips_unreadable(self, temp_dir, reset_globals):
        """_plan_deliveries skips unparseable files."""
        src = temp_dir / "src"
        src.mkdir()

        # Write invalid JSON
        (src / "bad.json").write_text("not json")

        copies, deletes = router._plan_deliveries([src])

        assert len(copies) == 0
        assert len(deletes) == 0
        assert router.g["stats"]["skipped_unreadable"] == 1

    def test_plan_deliveries_discards_unrouted(self, temp_dir, reset_globals):
        """_plan_deliveries marks unrouted messages for deletion."""
        src = temp_dir / "src"
        src.mkdir()

        # Write message with no matching route
        (src / "msg.json").write_text('{"channel": "unknown", "signal": {}, "timestamp": "1"}')

        # Mock app.ctx
        import lionscliapp as app
        app.reset()
        app.declare_app("test", "1.0")
        app.declare_key("router.discard_unrouted", True)

        copies, deletes = router._plan_deliveries([src])

        assert len(copies) == 0
        assert len(deletes) == 1
        assert router.g["stats"]["discarded_unrouted"] == 1

    def test_execute_copies_delivers_messages(self, temp_dir, reset_globals):
        """_execute_copies writes messages to destination."""
        src = temp_dir / "src"
        src.mkdir()
        dest = temp_dir / "dest"
        dest.mkdir()

        src_path = src / "msg.json"
        msg = {"channel": "input", "signal": {"data": 1}, "timestamp": "1"}

        copies = [(src_path, msg, dest, "output")]

        successful = router._execute_copies(copies)

        assert src_path in successful
        assert len(list(dest.glob("*.json"))) == 1

        # Check delivered message
        delivered = list(dest.glob("*.json"))[0]
        data, _ = router.read_json_file(delivered)
        assert data["channel"] == "output"
        assert data["signal"] == {"data": 1}

    def test_execute_copies_skips_missing_folder(self, temp_dir, reset_globals):
        """_execute_copies skips missing destination folders."""
        src = temp_dir / "src"
        src.mkdir()
        dest = temp_dir / "nonexistent"

        src_path = src / "msg.json"
        msg = {"channel": "input", "signal": {}, "timestamp": "1"}

        copies = [(src_path, msg, dest, "output")]

        successful = router._execute_copies(copies)

        assert len(successful) == 0
        assert router.g["stats"]["skipped_missing_folder"] == 1

    def test_execute_deletes_after_successful_copy(self, temp_dir, reset_globals):
        """_execute_deletes removes source after successful copies."""
        src = temp_dir / "src"
        src.mkdir()

        src_path = src / "msg.json"
        src_path.write_text('{"channel": "test", "signal": {}, "timestamp": "1"}')

        deletes = [src_path]
        successful = {src_path: [temp_dir / "dest" / "copy.json"]}
        copies = [(src_path, {}, temp_dir / "dest", "ch")]

        router._execute_deletes(deletes, successful, copies)

        assert not src_path.exists()
        assert router.g["stats"]["deleted"] == 1


# =============================================================================
# CONTROL INPUT TESTS
# =============================================================================

class TestControlInput:

    def test_handle_link_message(self, temp_dir, reset_globals):
        """handle_link_message adds a route."""
        router.g["events_path"] = temp_dir / "events.jsonl"

        signal = {
            "source-folder": str(temp_dir / "src"),
            "source-channel": "in",
            "destination-channel": "out",
            "destination-folder": str(temp_dir / "dest"),
        }

        router.handle_link_message(signal)

        assert len(router.g["routes"]) == 1

    def test_handle_link_message_with_ack(self, temp_dir, reset_globals):
        """handle_link_message writes acknowledgement if ack-path provided."""
        router.g["events_path"] = temp_dir / "events.jsonl"
        ack_path = temp_dir / "ack.json"

        signal = {
            "source-folder": str(temp_dir / "src"),
            "source-channel": "in",
            "destination-channel": "out",
            "destination-folder": str(temp_dir / "dest"),
            "ack-path": str(ack_path),
        }

        router.handle_link_message(signal)

        assert ack_path.exists()
        ack, _ = router.read_json_file(ack_path)
        assert ack["signal"] == "link"

    def test_handle_unlink_message(self, temp_dir, reset_globals):
        """handle_unlink_message removes a route."""
        router.g["events_path"] = temp_dir / "events.jsonl"

        # Add route first
        router.add_route(temp_dir / "src", "in", "out", temp_dir / "dest")
        assert len(router.g["routes"]) == 1

        signal = {
            "source-folder": str(temp_dir / "src"),
            "source-channel": "in",
            "destination-channel": "out",
            "destination-folder": str(temp_dir / "dest"),
        }

        router.handle_unlink_message(signal)

        assert len(router.g["routes"]) == 0

    def test_handle_quit_message(self, reset_globals):
        """handle_quit_message sets quit_requested flag."""
        assert router.g["quit_requested"] is False

        router.handle_quit_message({})

        assert router.g["quit_requested"] is True


# =============================================================================
# PREDICATES TESTS
# =============================================================================

class TestPredicates:

    def test_is_quit_requested(self, reset_globals):
        """is_quit_requested returns quit_requested state."""
        assert router.is_quit_requested() is False
        router.g["quit_requested"] = True
        assert router.is_quit_requested() is True

    def test_is_draining(self, reset_globals):
        """is_draining returns True in draining mode."""
        assert router.is_draining() is False
        router.g["mode"] = "draining"
        assert router.is_draining() is True


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:

    def test_full_delivery_cycle(self, temp_dir, reset_globals):
        """Test complete message delivery from source to destination."""
        src_outbox = temp_dir / "src" / "OUTBOX"
        dest_inbox = temp_dir / "dest" / "INBOX"
        src_outbox.mkdir(parents=True)
        dest_inbox.mkdir(parents=True)

        # Set up router state
        router.g["events_path"] = temp_dir / "events.jsonl"
        router.g["outbox_path"] = temp_dir / "router" / "OUTBOX"
        router.g["outbox_path"].mkdir(parents=True)

        # Add route
        router.add_route(src_outbox, "data", "received", dest_inbox)

        # Write source message
        router.write_message(src_outbox, "data", {"payload": "test123"})

        # Mock app.ctx
        import lionscliapp as app
        app.reset()
        app.declare_app("test", "1.0")
        app.declare_key("router.discard_unrouted", True)

        # Execute delivery
        router.do_delivery_pass()

        # Verify delivery
        delivered = list(dest_inbox.glob("*.json"))
        assert len(delivered) == 1

        msg, _ = router.read_json_file(delivered[0])
        assert msg["channel"] == "received"
        assert msg["signal"]["payload"] == "test123"

        # Verify source deleted
        assert len(list(src_outbox.glob("*.json"))) == 0

        # Verify stats
        assert router.g["stats"]["seen"] == 1
        assert router.g["stats"]["delivered"] == 1
        assert router.g["stats"]["deleted"] == 1

    def test_fanout_delivery(self, temp_dir, reset_globals):
        """Test message delivery to multiple destinations."""
        src = temp_dir / "src"
        dest1 = temp_dir / "dest1"
        dest2 = temp_dir / "dest2"
        src.mkdir()
        dest1.mkdir()
        dest2.mkdir()

        router.g["events_path"] = temp_dir / "events.jsonl"
        router.g["outbox_path"] = temp_dir / "router" / "OUTBOX"
        router.g["outbox_path"].mkdir(parents=True)

        # Add two routes from same source
        router.add_route(src, "broadcast", "copy1", dest1)
        router.add_route(src, "broadcast", "copy2", dest2)

        # Write source message
        router.write_message(src, "broadcast", {"msg": "hello"})

        import lionscliapp as app
        app.reset()
        app.declare_app("test", "1.0")
        app.declare_key("router.discard_unrouted", True)

        router.do_delivery_pass()

        # Verify both destinations received
        assert len(list(dest1.glob("*.json"))) == 1
        assert len(list(dest2.glob("*.json"))) == 1

        msg1, _ = router.read_json_file(list(dest1.glob("*.json"))[0])
        msg2, _ = router.read_json_file(list(dest2.glob("*.json"))[0])

        assert msg1["channel"] == "copy1"
        assert msg2["channel"] == "copy2"
        assert msg1["signal"] == msg2["signal"] == {"msg": "hello"}

    def test_shutdown_message_delivered_during_drain(self, temp_dir, reset_globals):
        """Test that shutdown message is delivered to subscribers during draining."""
        router_outbox = temp_dir / "router" / "OUTBOX"
        router_outbox.mkdir(parents=True)
        subscriber_inbox = temp_dir / "subscriber" / "INBOX"
        subscriber_inbox.mkdir(parents=True)

        router.g["events_path"] = temp_dir / "events.jsonl"
        router.g["outbox_path"] = router_outbox
        router.g["router_id"] = "test-router"
        router.g["started_at_utc"] = "12345"

        # Subscribe to shutdown messages from router OUTBOX
        router.add_route(router_outbox, "shutdown", "router-shutdown", subscriber_inbox)

        import lionscliapp as app
        app.reset()
        app.declare_app("test", "1.0")
        app.declare_key("router.discard_unrouted", True)

        # Run draining sequence
        router.enter_draining_mode_and_drain()

        # Verify shutdown message was delivered to subscriber
        delivered = list(subscriber_inbox.glob("*.json"))
        assert len(delivered) == 1

        msg, _ = router.read_json_file(delivered[0])
        assert msg["channel"] == "router-shutdown"

        # Verify router OUTBOX is empty (message was deleted after delivery)
        assert len(list(router_outbox.glob("*.json"))) == 0

    def test_has_deliverable_messages_detects_routed_messages(self, temp_dir, reset_globals):
        """Test has_deliverable_messages_in_router_outbox detection."""
        router_outbox = temp_dir / "router" / "OUTBOX"
        router_outbox.mkdir(parents=True)
        dest = temp_dir / "dest"
        dest.mkdir()

        router.g["events_path"] = temp_dir / "events.jsonl"
        router.g["outbox_path"] = router_outbox

        # No messages yet
        assert router.has_deliverable_messages_in_router_outbox() is False

        # Add message but no route
        router.write_message(router_outbox, "shutdown", {})
        assert router.has_deliverable_messages_in_router_outbox() is False

        # Add route for shutdown
        router.add_route(router_outbox, "shutdown", "shutdown", dest)
        assert router.has_deliverable_messages_in_router_outbox() is True
