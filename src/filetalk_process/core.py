# filetalk_process/core.py

import sys
import json
import time
import traceback

# global state
g = {
    "invocation": None,  # the JSON loaded from the first argument
    "summary": None  # the summary output from the process
}


# ----------------------------
# internal helpers
# ----------------------------

def _utc_now_str():
    return f"{time.time():.6f}"


# ----------------------------
# lifecycle
# ----------------------------

def start(flags=""):
    """
    Loads invocation JSON from sys.argv[-1] and initializes summary.

    flags:
      "s" -- add simple "events" logging to summary
      "c" -- add "complex_events" logging to summary
      "r" -- record_request_id() immediately into summary (RECOMMENDED)
      "a" -- attach_invocation() immediately (makes summary output larger)
    """
    if len(sys.argv) < 2:
        raise RuntimeError("No invocation JSON path supplied on command line")

    path = sys.argv[-1]

    with open(path, "r", encoding="utf-8") as f:
        inv = json.load(f)

    g["invocation"] = inv

    g["summary"] = {
        "type": "filetalk-program-invocation-summary",
        "STANDARD": {},
        "CUSTOM": {}
    }

    std = g["summary"]["STANDARD"]

    inv_std = inv.get("STANDARD", {})

    if "r" in flags:
        record_request_id()
    
    if "a" in flags:
        attach_invocation()

    if "s" in flags:
        g["summary"]["STANDARD"]["events"] = []

    if "c" in flags:
        g["summary"]["STANDARD"]["complex-events"] = []
    
    return g


def attach_invocation():
    """
    Copies full invocation JSON into summary STANDARD.invocation
    """
    g["summary"]["STANDARD"]["invocation"] = json.loads(json.dumps(g["invocation"]))  # deep copy

def record_request_id():
    request_id = g["invocation"]["STANDARD"].get("request-id")
    if request_id:
        g["summary"]["STANDARD"]["request-id"] = request_id


# ----------------------------
# standard setters
# ----------------------------

def mark_complete(complete=True):
    g["summary"]["STANDARD"]["complete"] = complete


def set_status(s):
    g["summary"]["STANDARD"]["status"] = s


def set_exit_code(n):
    g["summary"]["STANDARD"]["exit-code"] = int(n)


def timestamp_now():
    g["summary"]["STANDARD"]["timestamp-utc"] = _utc_now_str()


# ----------------------------
# standard state setters
# ----------------------------

def state_ok():
    mark_complete(True)
    set_status("ok")
    set_exit_code(0)

def state_generic_error():
    mark_complete(False)
    set_status("generic-error")
    set_exit_code(1)

def state_invalid_invocation():
    mark_complete(False)
    set_status("invalid-invocation")
    set_exit_code(2)

def state_external_dependency_failure():
    mark_complete(False)
    set_status("external-dependency-failure")
    set_exit_code(3)

def state_partial_completion():
    mark_complete(False)
    set_status("partial-completion")
    set_exit_code(4)


# ----------------------------
# events
# ----------------------------

def add_event(text_or_kind, tags=None, flags="i"):
    """
    add_event("text")
      -> simple narrative event
    
    add_event(kind, tags=[...], flags="i|w|e")
      -> structured complex event
    """
    STD = g["summary"]["STANDARD"]
    
    if "events" in STD:
        STD["events"].append(text_or_kind)
    
    if "complex_events" in STD:
        level = "info"
        if "w" in flags:
            level = "warn"
        if "e" in flags:
            level = "error"
        
        ev = {
            "timestamp-utc": _utc_now_str(),
            "level": level,
            "kind": text_or_kind,
            "tags": list(tags) if tags else [],
            "msg": "",  # fill with record_message(msg)
            "data": {}  # fill with record_data(data)
        }
        
        g["summary"]["STANDARD"]["complex-events"].append(ev)


def record_message(msg):
    lst = g["summary"]["STANDARD"]["complex-events"]
    if not lst:
        raise RuntimeError("No complex event to record message on")
    lst[-1]["msg"] = msg


def record_data(d):
    lst = g["summary"]["STANDARD"]["complex-events"]
    if not lst:
        raise RuntimeError("No complex event to record data on")
    if not isinstance(d, dict):
        raise ValueError("record_data requires dict")
    lst[-1]["data"].update(d)


def record_exception(exc=None):
    if exc is None:
        exc = sys.exc_info()[1]
    
    tb = traceback.format_exc()

    STD = g["summary"]["STANDARD"]
    
    if "events" in STD:
        STD["events"].append(tb)
    
    if "complex-events" in STD:
        ev = {
            "timestamp-utc": _utc_now_str(),
            "level": "error",
            "kind": "exception",
            "tags": ["exception"],
            "msg": str(exc),
            "data": {
                "type": exc.__class__.__name__ if exc else None,
                "traceback": tb
            }
        }

        STD["complex-events"].append(ev)


# ----------------------------
# output
# ----------------------------

def output_summary(flags=""):
    """
    flags:
      t -> timestamp_now()
      o -> set_status("ok")
      c -> mark_complete()
      0-9 -> set exit code to that digit
    """

    if "t" in flags:
        timestamp_now()

    if "o" in flags:
        set_status("ok")
    elif "e" in flags:
        set_status("generic-error")
    elif "p" in flags:
        set_status("partial-completion")
    
    if "c" in flags:
        mark_complete()

    for ch in flags:
        if ch.isdigit():
            set_exit_code(int(ch))
            break
    
    inv_std = g["invocation"].get("STANDARD", {})
    path = inv_std.get("summary-file")

    if not path:
        raise RuntimeError("Invocation STANDARD.summary-file not provided")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(g["summary"], f, indent=2)

    return path
