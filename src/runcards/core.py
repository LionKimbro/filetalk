# filetalk_process/core.py
"""runcards.core  -- Job Card and Report Card definition and use


Typical use:

blank = {...}

if not runcards.has_json_arg("xp"):
    runcards.print_stub(blank, "SRj")
else:
    runcards.start("scr")

    try:
        do_work()
        runcards.state_ok()
    except:
        runcards.record_exception()
        runcards.state_generic_error()
    finally:
        runcards.output_reportcard("t")
"""

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

def _now_str():
    return f"{time.time():.6f}"


# ----------------------------
# lifecycle
# ----------------------------


def has_json_arg(flags = "xp"):
    """Check if a JSON argument has been passed to the program.

    Flags:
      "x"  -- require that it has a ".json" extension
      "p"  -- require that it parse as valid JSON data
      "v"  -- [TODO] require that it validate as a Job Card
    """
    long_enough = len(sys.argv) >= 2
    if not long_enough:
        return False

    path = sys.argv[-1]
    
    if "x" in flags:
        if not path.lower().endswith(".json"):
            return False
    
    if "p" in flags:
        try:
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)
        except json.decoder.JSONDecodeError:
            return False
        
    return True


def generate_stub(blank_args, flags=""):
    jobcard = {
        "type": "json-job-card",
        "STANDARD": {},
        "ARGS": blank_args
    }

    if "r" in flags:
        jobcard["STANDARD"]["report-card-file"] = "<optional path to write report card to>"
    elif "R" in flags:
        jobcard["STANDARD"]["report-card-file"] = "<path to write report card to>"

    if "j" in flags:
        jobcard["STANDARD"]["job-id"] = "<optional job id>"
    elif "J" in flags:
        jobcard["STANDARD"]["job-id"] = "<job id>"

    return jobcard

def print_stub(blank_args, flags=""):
    jobcard = generate_stub(blank_args, flags)
    print(json.dumps(jobcard, indent=2))


def start(flags=""):
    """
    Loads job card JSON from sys.argv[-1] and initializes report card.

    flags:
      "?" -- [TODO] allow execution without an argument
      "?" -- [TODO] optionally pre-populate a report card file location, if one not supplied
      "v" -- [TODO] validate input; fill out report card with incomplete if it's bad
      "s" -- add simple "events" logging to report card
      "c" -- add "complex-events" logging to report card
      "r" -- record_job_id() immediately into report card (RECOMMENDED)
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
        record_job_id()
    
    if "a" in flags:
        attach_jobcard()

    if "s" in flags:
        STD["events"] = []

    if "c" in flags:
        STD["complex-events"] = []
    
    return g


def attach_jobcard():
    """
    Copies full job card JSON into report card STANDARD.job-card
    """
    deepcopy = json.loads(json.dumps(g["job-card"]))
    g["report-card"]["STANDARD"]["job-card"] = deepcopy

def record_job_id():
    job_id = g["job-card"]["STANDARD"].get("job-id")
    if job_id:
        g["report-card"]["STANDARD"]["job-id"] = job_id


# ----------------------------
# standard setters
# ----------------------------

def mark_complete(complete=True):
    set("complete", complete)

def timestamp_now():
    set("timestamp", _now_str())

def set_status(status):
    set("status", status)

def set_exit_code(exit_code):
    set("exit-code", exit_code)

def set(var, value):
    if var in ("exit-code", "status", "complete", "timestamp"):
        g["report-card"]["STANDARD"][var] = value
    else:
        raise KeyError(var)

def get(var):
    if var in ("exit-code", "status", "complete", "timestamp"):
        return g["report-card"]["STANDARD"][var]
    else:
        raise KeyError(var)


# ----------------------------
# standard state setters
# ----------------------------

def state_ok():
    mark_complete(True)
    set_status("ok")
    set_exit_code(0)
    timestamp_now()

def state_generic_error():
    mark_complete(False)
    set_status("generic-error")
    set_exit_code(1)
    timestamp_now()
    
def state_invalid_jobcard():
    mark_complete(False)
    set_status("invalid-job-card")
    set_exit_code(2)
    timestamp_now()
    
def state_external_dependency_failure():
    mark_complete(False)
    set_status("external-dependency-failure")
    set_exit_code(3)
    timestamp_now()
    
def state_partial_completion():
    mark_complete(False)
    set_status("partial-completion")
    set_exit_code(4)
    timestamp_now()

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
    
    if "complex-events" in STD:
        level = "info"
        if "w" in flags:
            level = "warn"
        if "e" in flags:
            level = "error"
        
        ev = {
            "timestamp": _now_str(),
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


def record_exception():
    exc_type, exc, tb_obj = sys.exc_info()

    if exc is None:
        raise RuntimeError("runcards.record_exception() called with no active exception")
    
    tb = traceback.format_exc()

    STD = g["report-card"]["STANDARD"]

    if "events" in STD:
        STD["events"].append(tb)

    if "complex-events" in STD:
        ev = {
            "timestamp": _now_str(),
            "level": "error",
            "kind": "exception",
            "tags": ["exception"],
            "msg": str(exc),
            "data": {
                "type": exc_type.__name__ if exc_type else None,
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
      e -> set_status("generic-error")
      p -> set_status("partial-completion")
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
