"""
Patchboard Router - Headless FileTalk-controlled message router.

Routes JSON messages between OUTBOX and INBOX directories based on channel matching.
Single-process, single-threaded, poll-based.
"""

import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

import lionscliapp as app


# =============================================================================
# CONSTANTS
# =============================================================================

kPROJECT_DIR = ".patchboard-router"
kEVENTS_LOG = "events.jsonl"
kSTATUS_FILE = "status.json"
kROUTES_FILE = "routes.json"
kINBOX = "INBOX"
kOUTBOX = "OUTBOX"


# =============================================================================
# GLOBAL STATE
# =============================================================================

g = {
    "mode": "normal",           # "normal" | "draining"
    "quit_requested": False,
    "tick": 0,
    "router_id": None,          # UUID at startup
    "started_at_utc": None,     # Unix timestamp string
    "routes": [],               # List of route dicts (authoritative)
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
    # Paths (set during init)
    "project_dir": None,
    "events_path": None,
    "status_path": None,
    "routes_path": None,
    "inbox_path": None,
    "outbox_path": None,
}


# =============================================================================
# PATH UTILITIES
# =============================================================================

def canonicalize_path(p):
    """Convert path to canonical form: absolute and resolved."""
    return Path(p).resolve()


def paths_equal(p1, p2):
    """Compare two paths for equality after canonicalization."""
    return str(canonicalize_path(p1)) == str(canonicalize_path(p2))


# =============================================================================
# FILE I/O UTILITIES
# =============================================================================

def write_json_atomic(path, obj, flags=""):
    """Write JSON to path atomically (temp file + rename).

    Flags:
        'p' - pretty/indented output
        'c' - compact output (default)
    """
    path = Path(path)
    indent = 2 if "p" in flags else None
    content = json.dumps(obj, indent=indent, ensure_ascii=False)
    if indent:
        content += "\n"

    # Write to temp file in same directory, then rename
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        Path(tmp_path).replace(path)
    except:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def append_jsonl(path, obj):
    """Append a JSON object as a line to a JSONL file."""
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def read_json_file(path):
    """Read and parse a JSON file. Returns (data, True) or (None, False)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), True
    except (json.JSONDecodeError, FileNotFoundError, OSError):
        return None, False


# =============================================================================
# PATCHBOARD MESSAGE HELPERS
# =============================================================================

def make_message(channel, signal):
    """Create a Patchboard Core message dict with timestamp."""
    return {
        "channel": channel,
        "signal": signal,
        "timestamp": f"{time.time():.6f}",
    }


def _generate_message_filename():
    """Generate a unique filename for a message."""
    ts = f"{time.time():.6f}"
    unique = uuid.uuid4().hex[:8]
    return f"msg_{ts}_{unique}.json"


def write_message(folder, channel, signal):
    """Write a message to a folder atomically. Returns the generated filename."""
    folder = Path(folder)
    msg = make_message(channel, signal)
    filename = _generate_message_filename()
    filepath = folder / filename
    write_json_atomic(filepath, msg)
    return filename


def read_message(filepath):
    """Read and parse a message file. Returns (msg_dict, True) or (None, False)."""
    return read_json_file(filepath)


# =============================================================================
# EVENTS LOG
# =============================================================================

def log_event(event_type, data=None):
    """Append an event to the events log."""
    event = {
        "event": event_type,
        "ts_utc": f"{time.time():.6f}",
    }
    if data:
        event.update(data)
    append_jsonl(g["events_path"], event)


def replay_events_log_and_rebuild_routing_table():
    """Replay events.jsonl to reconstruct routing table on startup."""
    g["routes"] = []

    if not g["events_path"].exists():
        return

    with open(g["events_path"], "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("event")

            if event_type == "route_added":
                route = {
                    "source-folder": event["source-folder"],
                    "source-channel": event["source-channel"],
                    "destination-channel": event["destination-channel"],
                    "destination-folder": event["destination-folder"],
                }
                if route not in g["routes"]:
                    g["routes"].append(route)

            elif event_type == "route_removed":
                route = {
                    "source-folder": event["source-folder"],
                    "source-channel": event["source-channel"],
                    "destination-channel": event["destination-channel"],
                    "destination-folder": event["destination-folder"],
                }
                if route in g["routes"]:
                    g["routes"].remove(route)


# =============================================================================
# ROUTING TABLE MANAGEMENT
# =============================================================================

def _make_route_dict(src_folder, src_channel, dest_channel, dest_folder):
    """Create a canonical route dictionary."""
    return {
        "source-folder": str(canonicalize_path(src_folder)),
        "source-channel": src_channel,
        "destination-channel": dest_channel,
        "destination-folder": str(canonicalize_path(dest_folder)),
    }


def is_duplicate_route(src_folder, src_channel, dest_channel, dest_folder):
    """Check if route already exists."""
    route = _make_route_dict(src_folder, src_channel, dest_channel, dest_folder)
    return route in g["routes"]


def add_route(src_folder, src_channel, dest_channel, dest_folder):
    """Add a route to the routing table. Returns True if added, False if duplicate."""
    route = _make_route_dict(src_folder, src_channel, dest_channel, dest_folder)

    if route in g["routes"]:
        return False

    g["routes"].append(route)
    log_event("route_added", route)
    g["routes_dirty"] = True
    g["state_dirty"] = True
    return True


def remove_route(src_folder, src_channel, dest_channel, dest_folder):
    """Remove a route from the routing table. Returns True if removed, False if not found."""
    route = _make_route_dict(src_folder, src_channel, dest_channel, dest_folder)

    if route not in g["routes"]:
        return False

    g["routes"].remove(route)
    log_event("route_removed", route)
    g["routes_dirty"] = True
    g["state_dirty"] = True
    return True


def routes_for_source(source_folder, channel):
    """Return list of (dest_channel, dest_folder) for matching routes."""
    source_key = str(canonicalize_path(source_folder))
    results = []

    for route in g["routes"]:
        if route["source-folder"] == source_key:
            if route["source-channel"] == channel or route["source-channel"] == "*":
                results.append((
                    route["destination-channel"],
                    Path(route["destination-folder"])
                ))

    return results


def get_all_source_folders():
    """Return set of all unique source folders from the routing table."""
    return {Path(route["source-folder"]) for route in g["routes"]}


# =============================================================================
# STATE PUBLICATION
# =============================================================================

def publish_status():
    """Write status.json snapshot."""
    status = {
        "schema_version": "1",
        "router_id": g["router_id"],
        "started_at_utc": g["started_at_utc"],
        "tick": g["tick"],
        "last_change": f"{time.time():.6f}",
        "delay_seconds": app.ctx["router.delay_seconds"],
        "stats": dict(g["stats"]),
    }
    write_json_atomic(g["status_path"], status, "p")
    g["state_dirty"] = False


def publish_routes():
    """Write routes.json snapshot."""
    routes_doc = {
        "schema-version": "1",
        "updated-at-utc": f"{time.time():.6f}",
        "routes": list(g["routes"]),
    }
    write_json_atomic(g["routes_path"], routes_doc, "p")
    g["routes_dirty"] = False


def emit_notice():
    """Write a change-notice message to router OUTBOX."""
    write_message(g["outbox_path"], "notice", {})


def publish_state_if_dirty():
    """Publish status and/or routes if changed since last publication."""
    if g["routes_dirty"]:
        publish_routes()
        emit_notice()
    if g["state_dirty"]:
        publish_status()


# =============================================================================
# DELIVERY ENGINE (LA-LA POLICY)
# =============================================================================

def do_delivery_pass(flags=""):
    """Execute one delivery pass using la-la routing policy.

    Flags:
        'd' - draining mode (only router OUTBOX as source)
    """
    draining = "d" in flags

    # Determine source folders
    if draining:
        source_folders = [g["outbox_path"]]
    else:
        source_folders = list(get_all_source_folders())
        # Always include router OUTBOX for lifecycle messages
        if g["outbox_path"] not in source_folders:
            source_folders.append(g["outbox_path"])

    # Plan phase
    copies, deletes = _plan_deliveries(source_folders)

    # Copy phase
    successful = _execute_copies(copies)

    # Delete phase
    _execute_deletes(deletes, successful, copies)

    g["tick"] += 1
    g["state_dirty"] = True


def _plan_deliveries(source_folders):
    """Scan source folders, compute copy and delete operations.

    Returns (copies, deletes) where:
        copies: [(src_path, msg, dest_folder, dest_channel), ...]
        deletes: [src_path, ...]
    """
    copies = []
    deletes = []
    discard_unrouted = app.ctx.get("router.discard_unrouted", True)

    for folder in source_folders:
        folder = Path(folder)
        if not folder.exists():
            continue

        for filepath in folder.glob("*.json"):
            msg, ok = read_message(filepath)
            if not ok:
                g["stats"]["skipped_unreadable"] += 1
                continue

            channel = msg.get("channel", "")
            destinations = routes_for_source(folder, channel)

            if not destinations:
                if discard_unrouted:
                    deletes.append(filepath)
                    g["stats"]["discarded_unrouted"] += 1
                continue

            for dest_channel, dest_folder in destinations:
                copies.append((filepath, msg, dest_folder, dest_channel))
            deletes.append(filepath)
            g["stats"]["seen"] += 1

    return copies, deletes


def _execute_copies(copies):
    """Perform all planned copy operations.

    Returns dict: {src_path: [dest_paths that succeeded]}
    """
    successful = {}

    for src_path, msg, dest_folder, dest_channel in copies:
        if not dest_folder.exists():
            g["stats"]["skipped_missing_folder"] += 1
            continue

        # Create new message with rewritten channel
        new_msg = {
            "channel": dest_channel,
            "signal": msg.get("signal", {}),
            "timestamp": msg.get("timestamp", f"{time.time():.6f}"),
        }

        filename = _generate_message_filename()
        dest_path = dest_folder / filename

        try:
            write_json_atomic(dest_path, new_msg)
            successful.setdefault(src_path, []).append(dest_path)
            g["stats"]["delivered"] += 1
        except OSError:
            pass  # Copy failed, don't record as successful

    return successful


def _execute_deletes(deletes, successful, copies):
    """Delete source files only if all their copies succeeded."""
    # Build set of sources that had copies planned
    sources_with_copies = {src for src, _, _, _ in copies}

    for src_path in deletes:
        # Delete if:
        # 1. Source had no routes (discard_unrouted case) - not in sources_with_copies
        # 2. Source had routes and ALL copies succeeded
        if src_path not in sources_with_copies:
            # Unrouted message being discarded
            try:
                src_path.unlink()
                g["stats"]["deleted"] += 1
            except OSError:
                pass
        elif src_path in successful:
            # Had copies, check if all succeeded
            planned_count = sum(1 for s, _, _, _ in copies if s == src_path)
            actual_count = len(successful[src_path])
            if actual_count >= planned_count:
                try:
                    src_path.unlink()
                    g["stats"]["deleted"] += 1
                except OSError:
                    pass


# =============================================================================
# CONTROL INPUT PROCESSING
# =============================================================================

def process_control_inputs():
    """Read and dispatch messages from router INBOX."""
    inbox = g["inbox_path"]
    if not inbox.exists():
        return

    for filepath in list(inbox.glob("*.json")):
        msg, ok = read_message(filepath)
        if not ok:
            continue

        channel = msg.get("channel", "")
        signal = msg.get("signal", {})

        if channel == "link":
            handle_link_message(signal)
        elif channel == "unlink":
            handle_unlink_message(signal)
        elif channel == "quit":
            handle_quit_message(signal)

        # Delete processed message
        try:
            filepath.unlink()
        except OSError:
            pass


def handle_link_message(signal):
    """Process a link request."""
    src_folder = signal.get("source-folder")
    src_channel = signal.get("source-channel")
    dest_channel = signal.get("destination-channel")
    dest_folder = signal.get("destination-folder")
    ack_path = signal.get("ack-path")

    if not all([src_folder, src_channel, dest_channel, dest_folder]):
        return

    add_route(src_folder, src_channel, dest_channel, dest_folder)

    if ack_path:
        write_acknowledgement(ack_path, "link")


def handle_unlink_message(signal):
    """Process an unlink request."""
    src_folder = signal.get("source-folder")
    src_channel = signal.get("source-channel")
    dest_channel = signal.get("destination-channel")
    dest_folder = signal.get("destination-folder")
    ack_path = signal.get("ack-path")

    if not all([src_folder, src_channel, dest_channel, dest_folder]):
        return

    remove_route(src_folder, src_channel, dest_channel, dest_folder)

    if ack_path:
        write_acknowledgement(ack_path, "unlink")


def handle_quit_message(signal):
    """Set quit_requested flag."""
    g["quit_requested"] = True


def write_acknowledgement(ack_path, channel):
    """Write acknowledgement artifact to ack_path."""
    ack = make_message("filetalk-patchboard-router-acknowledgement", channel)
    write_json_atomic(ack_path, ack)


# =============================================================================
# PREDICATES
# =============================================================================

def is_quit_requested():
    """Check if quit has been requested."""
    return g["quit_requested"]


def is_draining():
    """Check if in draining mode."""
    return g["mode"] == "draining"


def has_deliverable_messages_in_router_outbox():
    """Check if router OUTBOX has messages that match any route."""
    outbox = g["outbox_path"]
    if not outbox.exists():
        return False

    for filepath in outbox.glob("*.json"):
        msg, ok = read_message(filepath)
        if not ok:
            continue
        channel = msg.get("channel", "")
        if routes_for_source(outbox, channel):
            return True

    return False


# =============================================================================
# LIFECYCLE
# =============================================================================

def initialize_filesystem_and_paths():
    """Ensure project directory, INBOX, OUTBOX, and events log exist. Set path globals."""
    # Get project root from lionscliapp (execution root + project dir)
    project_dir = Path(app.ctx.get("path.project_root", ".")) / kPROJECT_DIR

    # Actually, lionscliapp handles project dir creation, so use its path
    # The project dir is already created by lionscliapp under execroot
    # We need to get execroot and append our project dir
    from lionscliapp import paths
    project_dir = paths.get_project_root()

    g["project_dir"] = project_dir
    g["events_path"] = project_dir / kEVENTS_LOG
    g["status_path"] = project_dir / kSTATUS_FILE
    g["routes_path"] = project_dir / kROUTES_FILE
    g["inbox_path"] = project_dir / kINBOX
    g["outbox_path"] = project_dir / kOUTBOX

    # Ensure directories exist
    g["inbox_path"].mkdir(parents=True, exist_ok=True)
    g["outbox_path"].mkdir(parents=True, exist_ok=True)

    # Ensure events log exists
    if not g["events_path"].exists():
        g["events_path"].touch()


def emit_startup_message_and_event():
    """Log startup event and write startup message to router OUTBOX."""
    g["router_id"] = str(uuid.uuid4())
    g["started_at_utc"] = f"{time.time():.6f}"

    log_event("startup")
    write_message(g["outbox_path"], "startup", {})


def emit_shutdown_message_and_event():
    """Log shutdown event and write shutdown message to router OUTBOX."""
    log_event("shutdown")
    write_message(g["outbox_path"], "shutdown", {})


def run_main_loop():
    """The main polling loop. Exits when quit_requested."""
    delay = app.ctx.get("router.delay_seconds", 0.5)

    while not is_quit_requested():
        do_delivery_pass()
        process_control_inputs()
        publish_state_if_dirty()
        time.sleep(delay)


def enter_draining_mode_and_drain():
    """Freeze routing, emit shutdown, drain deliveries from router OUTBOX."""
    g["mode"] = "draining"

    emit_shutdown_message_and_event()

    # Drain: keep delivering from router OUTBOX until empty
    while has_deliverable_messages_in_router_outbox():
        do_delivery_pass("d")


# =============================================================================
# CLI COMMANDS
# =============================================================================

def cmd_run():
    """Launch the router main loop (authoritative process)."""
    initialize_filesystem_and_paths()
    replay_events_log_and_rebuild_routing_table()
    emit_startup_message_and_event()

    # Initial delivery pass
    do_delivery_pass()

    # Initial state publication
    publish_status()
    publish_routes()

    print(f"Patchboard Router started (id: {g['router_id']})")
    print(f"  INBOX:  {g['inbox_path']}")
    print(f"  OUTBOX: {g['outbox_path']}")
    print(f"  Delay:  {app.ctx.get('router.delay_seconds', 0.5)}s")
    print("Press Ctrl+C or send quit message to stop.")

    try:
        run_main_loop()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        g["quit_requested"] = True

    enter_draining_mode_and_drain()

    # Final state publication
    publish_status()
    publish_routes()

    print("Patchboard Router stopped.")


def cmd_status():
    """Display current state from status.json."""
    from lionscliapp import paths
    status_path = paths.get_project_root() / kSTATUS_FILE

    if not status_path.exists():
        print("Router has not been started (no status.json found).")
        sys.exit(1)

    data, ok = read_json_file(status_path)
    if not ok:
        print("Failed to read status.json")
        sys.exit(1)

    print(json.dumps(data, indent=2))


def cmd_routes():
    """Display current routing table from routes.json."""
    from lionscliapp import paths
    routes_path = paths.get_project_root() / kROUTES_FILE

    if not routes_path.exists():
        print("Router has not been started (no routes.json found).")
        sys.exit(1)

    data, ok = read_json_file(routes_path)
    if not ok:
        print("Failed to read routes.json")
        sys.exit(1)

    print(json.dumps(data, indent=2))


def _parse_link_unlink_args():
    """Parse --sf, --sc, --df, --dc, --ack arguments from sys.argv."""
    args = {
        "sf": None,  # source-folder
        "sc": None,  # source-channel
        "df": None,  # destination-folder
        "dc": None,  # destination-channel
        "ack": None, # ack-path (optional)
    }

    argv = sys.argv[1:]  # Skip program name
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--sf", "-sf") and i + 1 < len(argv):
            args["sf"] = argv[i + 1]
            i += 2
        elif arg in ("--sc", "-sc") and i + 1 < len(argv):
            args["sc"] = argv[i + 1]
            i += 2
        elif arg in ("--df", "-df") and i + 1 < len(argv):
            args["df"] = argv[i + 1]
            i += 2
        elif arg in ("--dc", "-dc") and i + 1 < len(argv):
            args["dc"] = argv[i + 1]
            i += 2
        elif arg in ("--ack", "-ack") and i + 1 < len(argv):
            args["ack"] = argv[i + 1]
            i += 2
        else:
            i += 1

    return args


def cmd_link():
    """Write link request message to router INBOX."""
    args = _parse_link_unlink_args()

    if not all([args["sf"], args["sc"], args["df"], args["dc"]]):
        print("Usage: patchboard link --sf <source-folder> --sc <source-channel> --df <dest-folder> --dc <dest-channel> [--ack <path>]")
        sys.exit(1)

    from lionscliapp import paths
    inbox_path = paths.get_project_root() / kINBOX

    if not inbox_path.exists():
        print("Router INBOX not found. Is the router running?")
        sys.exit(1)

    signal = {
        "source-folder": str(canonicalize_path(args["sf"])),
        "source-channel": args["sc"],
        "destination-channel": args["dc"],
        "destination-folder": str(canonicalize_path(args["df"])),
    }
    if args["ack"]:
        signal["ack-path"] = str(canonicalize_path(args["ack"]))

    write_message(inbox_path, "link", signal)
    print("Link request sent.")


def cmd_unlink():
    """Write unlink request message to router INBOX."""
    args = _parse_link_unlink_args()

    if not all([args["sf"], args["sc"], args["df"], args["dc"]]):
        print("Usage: patchboard unlink --sf <source-folder> --sc <source-channel> --df <dest-folder> --dc <dest-channel> [--ack <path>]")
        sys.exit(1)

    from lionscliapp import paths
    inbox_path = paths.get_project_root() / kINBOX

    if not inbox_path.exists():
        print("Router INBOX not found. Is the router running?")
        sys.exit(1)

    signal = {
        "source-folder": str(canonicalize_path(args["sf"])),
        "source-channel": args["sc"],
        "destination-channel": args["dc"],
        "destination-folder": str(canonicalize_path(args["df"])),
    }
    if args["ack"]:
        signal["ack-path"] = str(canonicalize_path(args["ack"]))

    write_message(inbox_path, "unlink", signal)
    print("Unlink request sent.")


def cmd_quit():
    """Write quit message to router INBOX."""
    from lionscliapp import paths
    inbox_path = paths.get_project_root() / kINBOX

    if not inbox_path.exists():
        print("Router INBOX not found. Is the router running?")
        sys.exit(1)

    write_message(inbox_path, "quit", {})
    print("Quit request sent.")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Entry point via lionscliapp."""
    app.declare_app("patchboard", "0.1")
    app.describe_app("Headless FileTalk-controlled patchboard router")
    app.declare_projectdir(kPROJECT_DIR)

    # Configuration keys
    app.declare_key("router.delay_seconds", 0.5)
    app.describe_key("router.delay_seconds", "Seconds between routing passes")

    app.declare_key("router.max_deliveries_per_tick", 500)
    app.describe_key("router.max_deliveries_per_tick", "Maximum deliveries per pass")

    app.declare_key("router.discard_unrouted", True)
    app.describe_key("router.discard_unrouted", "Delete messages with no matching routes")

    # Commands
    app.declare_cmd("run", cmd_run)
    app.describe_cmd("run", "Launch the router main loop")

    app.declare_cmd("status", cmd_status)
    app.describe_cmd("status", "Display current router state")

    app.declare_cmd("routes", cmd_routes)
    app.describe_cmd("routes", "Display current routing table")

    app.declare_cmd("link", cmd_link)
    app.describe_cmd("link", "Request creation of a route")

    app.declare_cmd("unlink", cmd_unlink)
    app.describe_cmd("unlink", "Request removal of a route")

    app.declare_cmd("quit", cmd_quit)
    app.describe_cmd("quit", "Request graceful shutdown")

    app.main()
