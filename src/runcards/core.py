# filetalk_process/core.py

import sys
import json
import time
import traceback

# global state
g = {
    "job-card": None,  # the JSON loaded from the first argument
    "report-card": None  # the report card from the process
}


# ----------------------------
# internal helpers
# ----------------------------

def _utc_now_str():
    return f"{time.time():.6f}"


# ----------------------------
# lifecycle
# ----------------------------


def has_json_arg(flags = ""):
    """Use flag 'j' if you want to require a .json filename."""
    long_enough = len(sys.argv) >= 2
    if not long_enough:
        return False
    if "j" in flags:
        return sys.argv[-1].lower().endswith(".json")
    return True


def generate_stub(blank_args, flags=""):
    jobcard = {
        "type": "json-job-card",
        "STANDARD": {},
        "ARGS": blank_args
    }

    if "s" in flags:
        jobcard["STANDARD"]["report-card-file"] = "<optional path to write report card to>"
    elif "S" in flags:
        jobcard["STANDARD"]["report-card-file"] = "<path to write report card to>"

    if "r" in flags:
        jobcard["STANDARD"]["request-id"] = "<optional request id>"
    elif "R" in flags:
        jobcard["STANDARD"]["request-id"] = "<request id>"

    if "j" in flags:
        return json.dumps(jobcard, indent=2)
    else:
        return jobcard

def print_stub(blank_args, flags=""):
    if "j" not in flags:
        flags = flags+"j"
    print(generate_stub(blank_args, flags))


def start(flags=""):
    """
    Loads job card JSON from sys.argv[-1] and initializes report card.

    flags:
      "?" -- [TODO] allow execution without an argument
      "?" -- [TODO] optionally pre-populate a report card file location, if one not supplied
      "v" -- [TODO] validate input; fill out report card with incomplete if it's bad
      "s" -- add simple "events" logging to report card
      "c" -- add "complex_events" logging to report card
      "r" -- record_request_id() immediately into report card (RECOMMENDED)
      "a" -- attach_jobcard() immediately (makes report card output larger)
    """
    with open(sys.argv[-1], "r", encoding="utf-8") as f:
        inv = json.load(f)

    g["job-card"] = inv

    g["report-card"] = {
        "type": "json-report-card",
        "STANDARD": {},
        "CUSTOM": {}
    }

    STD = g["report-card"]["STANDARD"]

    if "r" in flags:
        record_request_id()
    
    if "a" in flags:
        attach_jobcard()

    if "s" in flags:
        STD["events"] = []

    if "c" in flags:
        STD["complex-events"] = []
    
    return g


def attach_jobcard():
    """
    Copies full job acrd JSON into report card STANDARD.job-card
    """
    g["report-card"]["STANDARD"]["job-card"] = json.loads(json.dumps(g["job-card"]))  # deep copy

def record_request_id():
    request_id = g["job-card"]["STANDARD"].get("request-id")
    if request_id:
        g["report-card"]["STANDARD"]["request-id"] = request_id


# ----------------------------
# standard setters
# ----------------------------

def mark_complete(complete=True):
    g["report-card"]["STANDARD"]["complete"] = complete

def timestamp_now():
    g["report-card"]["STANDARD"]["timestamp-utc"] = _utc_now_str()

def set_status(status):
    g["report-card"]["STANDARD"]["status"] = status

def set_exit_code(exit_code):
    g["report-card"]["STANDARD"]["exit_code"] = exit_code

def set(var, value):
    if var in ("exit-code", "status", "complete", "timestamp-utc", "complete"):
        g["report-card"]["STANDARD"][var] = value

def get(var):
    if var in ("exit-code", "status", "complete", "timestamp-utc", "complete"):
        return g["report-card"]["STANDARD"][var]


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

def state_invalid_jobcard():
    mark_complete(False)
    set_status("invalid-jobcard")
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
    STD = g["report-card"]["STANDARD"]
    
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
        
        g["report-card"]["STANDARD"]["complex-events"].append(ev)


def record_message(msg):
    lst = g["report-card"]["STANDARD"]["complex-events"]
    if not lst:
        raise RuntimeError("No complex event to record message on")
    lst[-1]["msg"] = msg


def record_data(d):
    lst = g["report-card"]["STANDARD"]["complex-events"]
    if not lst:
        raise RuntimeError("No complex event to record data on")
    if not isinstance(d, dict):
        raise ValueError("record_data requires dict")
    lst[-1]["data"].update(d)


def record_exception(exc=None):
    if exc is None:
        exc = sys.exc_info()[1]
    
    tb = traceback.format_exc()

    STD = g["report-card"]["STANDARD"]
    
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

def output_reportcard(flags=""):
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
    
    path = g["job-card"]["STANDARD"].get("report-card-file")

    if not path:
        raise RuntimeError("Job card STANDARD.report-card-file not provided")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(g["report-card"], f, indent=2)

    return path
