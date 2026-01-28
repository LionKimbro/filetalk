# runner.py
# FileTalk Runner (v1 skeleton)

import json
import os
import sys
import time
import queue
import threading
import subprocess
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog

import filetalk_process.core as ftp


g = {
    "exec_complete": False,
    "exec_error": None,
    "exec_errorcode": None,
    "traceback": None,
    
    "config_path": None,
    "config": None,
    "definitions": [],
    "selected": None, "last_selected": None,
    "running": False,
    "invocation_record": None,

    "status_msg": "",
    "suppress_tree_events": False,
    "sync_scheduled": False,
    
    "ui": {}
}


# Queues are module-global (never reassigned)
main_to_worker = queue.Queue()
worker_to_main = queue.Queue()


def _request_sync_gui():
    if g["sync_scheduled"]:
        return
    g["sync_scheduled"] = True
    g["ui"]["root"].after_idle(_sync_gui)


def _safe_write_json(path, obj):
    # best-effort; no printing
    try:
        p = Path(path)
        p.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def _fail_after_config_load(error, errorcode):
    g["exec_error"] = error
    g["exec_errorcode"] = errorcode
    raise SystemExit(0)


def _load_json_file(path):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    return json.loads(s)


def selected_index():
    if g["selected"] is None:
        return None
    try:
        return g["definitions"].index(g["selected"])
    except ValueError:
        return None


def _config_paths_ok():
    cfg = g["config"]
    paths = cfg["paths"]

    exec_dir = Path(paths["execution-log-dir"])
    defs_path = Path(paths["definitions"])

    # execution-log-dir: create if missing, but ONLY if parent exists
    if exec_dir.exists():
        if not exec_dir.is_dir():
            _fail_after_config_load("execution-log-dir exists but is not a directory", "EXEC-LOG-DIR-NOT-DIR")
    else:
        parent = exec_dir.parent
        if not parent.exists():
            _fail_after_config_load(
                "parent directory for execution-log-dir not found; will not create for you",
                "PARENT-DIR-NOT-FOUND",
            )
        try:
            exec_dir.mkdir()
        except Exception:
            _fail_after_config_load("could not create execution-log-dir", "EXEC-LOG-DIR-CREATE-FAILED")

    # definitions: if missing, definitions := []
    if defs_path.exists():
        if not defs_path.is_file():
            _fail_after_config_load("definitions path exists but is not a file", "DEFINITIONS-NOT-FILE")

    return True

def _load_definitions_or_exit():
    defs_path = g["config"]["paths"]["definitions"]
    p = Path(defs_path)

    if not p.exists():
        g["definitions"] = []
        return

    try:
        data = _load_json_file(p)
    except Exception:
        _fail_after_config_load("invalid JSON in definitions file", "JSON-INVALID")

    if not isinstance(data, list):
        _fail_after_config_load("definitions JSON must be a list", "DEFINITIONS-NOT-LIST")

    # sanitize minimal shape
    g["definitions"] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        g["definitions"].append(item)


def _save_definitions_to_disk():
    defs_path = g["config"]["paths"]["definitions"]
    _safe_write_json(defs_path, g["definitions"])

def _sync_disk():
    _safe_write_json(g["config"]["paths"]["definitions"], g["definitions"])
    _safe_write_json(g["config_path"], g["config"])


def _set_var(varname, value, flags=""):
    var = g["ui"][varname]
    if value is None:
        value = ""
    if "b" in flags:
        value = bool(value)
    elif not isinstance(value, str):
        value = str(value)
    if var.get() != value:
        var.set(value)

# meta: #sync-gui-editor systems=sync roles=sync callers=1,_sync_gui
def _sync_gui_editor():
    d = g["selected"]
    if d is None:
        _set_var("title_var", "")
        _set_var("exe_var", "")
        _set_var("summary_expected_var", "")
        _set_var("summary_path_var", "")
        _set_params_text("{}\n")
    else:
        _set_var("title_var", d["title"])
        _set_var("exe_var", d["executable"])
        _set_var("summary_expected_var", d["summary_expected"], "b")
        _set_var("summary_path_var", d["summary_path"])
        params = d["parameters"]
        if not isinstance(params, dict):
            params = {}
        _set_params_text(json.dumps(params, indent=2) + "\n")

def _sync_gui():
    g["sync_scheduled"] = False
    ui = g["ui"]
    
    # ----- status -----
    _set_var("status_var", g["status_msg"])

    # ----- editor fields -----
    d = g["selected"]

    if g["selected"] is not g["last_selected"]:
        _sync_gui_editor()
        g["last_selected"] = g["selected"]

    # ----- tree reconciliation -----
    tree = ui["tree"]
    if tree is not None:
        g["suppress_tree_events"] = True

        defs = g["definitions"]
        items = tree.get_children()

        # rebuild only if structure changed
        if len(items) != len(defs):
            tree.delete(*items)
            for i, d in enumerate(defs):
                title = d["title"] or f"(untitled {i+1})"
                tree.insert("", "end", iid=str(i), text=title)
        else:
            # update labels only
            for i, d in enumerate(defs):
                title = d["title"] or f"(untitled {i+1})"
                tree.item(str(i), text=title)

        # selection
        idx = selected_index()
        if idx is None:
            tree.selection_remove(tree.selection())
        else:
            iid = str(idx)
            tree.selection_set(iid)
            tree.focus(iid)

        g["suppress_tree_events"] = False

    # ----- run button enabled? -----
    btn_run = ui["btn_run"]
    if btn_run is not None:
        if g["running"]:
            btn_run.config(state="disabled")
        else:
            ready = _run_ready()
            btn_run.config(state="normal" if ready else "disabled")

    # ----- enable / disable other controls -----
    enabled = not g["running"]

    for key in [
        "btn_save", "btn_validate", "btn_insert_path",
        "btn_exe_browse", "btn_sum_browse",
        "btn_new", "btn_delete", "btn_up", "btn_down"
    ]:
        w = ui[key]
        if w is not None:
            try:
                w.config(state="normal" if enabled else "disabled")
            except Exception:
                pass

    t = ui["params_text"]
    if t is not None:
        try:
            t.config(state="normal" if enabled else "disabled")
        except Exception:
            pass


def _run_ready():
    if g["selected"] is None:
        return False

    # executable exists
    exe = g["ui"]["exe_var"].get().strip()
    if not exe or not Path(exe).exists():
        g["status_msg"] = "executable missing"
        return False

    # JSON valid
    obj, ok, err = _parse_params_json()
    if not ok:
        g["status_msg"] = f"JSON invalid: {err}"
        return False

    # summary path parent if needed
    if g["ui"]["summary_expected_var"].get():
        sp = g["ui"]["summary_path_var"].get().strip()
        if sp:
            try:
                if not Path(sp).resolve().parent.exists():
                    g["status_msg"] = "summary path parent missing"
                    return False
            except Exception:
                g["status_msg"] = "bad summary path"
                return False

    g["status_msg"] = "ready"
    return True


    
def _blank_definition():
    return {
        "title": "",
        "executable": "",
        "parameters": {},
        "summary_expected": True,
        "summary_path": "",
    }


def _refresh_tree():
    tree = g["ui"]["tree"]
    if tree is None:
        return

    tree.delete(*tree.get_children())

    for i, d in enumerate(g["definitions"]):
        title = d["title"]
        if not title:
            title = f"(untitled {i+1})"
        tree.insert("", "end", iid=str(i), text=title)

    # reselect
    idx = selected_index()
    if idx is not None:
        iid = str(idx)
        try:
            tree.selection_set(iid)
            tree.focus(iid)
        except Exception:
            pass


def _editor_set_from_selected():
    d = g["selected"]
    if d is None:
        _set_var("title_var", "")
        _set_var("exe_var", "")
        _set_var("summary_expected_var", True, "b")
        _set_var("summary_path_var", "")
        _set_params_text("{}")
        return

    _set_var("title_var", d["title"])
    _set_var("exe_var", d["executable"])
    _set_var("summary_expected_var", bool(d["summary_expected"]), "b")
    _set_var("summary_path_var", d["summary_path"])
    
    params = d["parameters"]
    if not isinstance(params, dict):
        params = {}
    _set_params_text(json.dumps(params, indent=2) + "\n")


def _set_params_text(s):
    t = g["ui"]["params_text"]
    if t is None:
        return
    t.config(state="normal")
    t.delete("1.0", "end")
    t.insert("1.0", s)
    t.config(state="normal")


def _set_summary_text(s):
    t = g["ui"]["summary_text"]
    if t is None:
        return
    t.config(state="normal")
    t.delete("1.0", "end")
    t.insert("1.0", s)
    t.config(state="disabled")


def _get_params_text():
    t = g["ui"]["params_text"]
    if t is None:
        return ""
    return t.get("1.0", "end-1c")


def _parse_params_json():
    s = _get_params_text().strip()
    if not s:
        return {}, True, None
    try:
        obj = json.loads(s)
    except Exception as e:
        return None, False, str(e)
    if not isinstance(obj, dict):
        return None, False, "parameters JSON must be an object/dictionary"
    return obj, True, None


def _validate_params_and_update_status():
    if g["running"]:
        _set_var("status_var", "running…")
        return False

    obj, ok, err = _parse_params_json()
    exe_ok = _executable_exists()
    if ok and exe_ok:
        _set_var("status_var", "ready")
        return True
    
    if not ok:
        _set_var("status_var", f"JSON invalid: {err}")
        return False
    
    if not exe_ok:
        _set_var("status_var", "executable missing")
        return False

    _set_var("status_var", "not ready")
    return False


def _executable_exists():
    p = g["ui"]["exe_var"].get().strip()
    if not p:
        return False
    try:
        return Path(p).exists()
    except Exception:
        return False


def _controls_set_enabled(enabled):
    # Editor controls
    state = "normal" if enabled else "disabled"

    for key in [
        "btn_save",
        "btn_run",
        "btn_validate",
        "btn_insert_path",
        "btn_exe_browse",
        "btn_sum_browse",
        "btn_new",
        "btn_delete",
        "btn_up",
        "btn_down",
    ]:
        w = g["ui"][key]
        if w is not None:
            try:
                w.config(state=state)
            except Exception:
                pass

    # text widgets
    for key in ["params_text"]:
        w = g["ui"][key]
        if w is not None:
            try:
                w.config(state="normal" if enabled else "disabled")
            except Exception:
                pass

    # tree
    tree = g["ui"]["tree"]
    if tree is not None:
        try:
            tree.config(selectmode="browse")
            tree_state = "normal" if enabled else "disabled"
            tree.config(state=tree_state)
        except Exception:
            pass


def _save_current_to_model():
    if g["selected"] is None:
        return False

    title = g["ui"]["title_var"].get()
    exe = g["ui"]["exe_var"].get()
    sum_expected = bool(g["ui"]["summary_expected_var"].get())
    sum_path = g["ui"]["summary_path_var"].get()

    params_obj, ok, err = _parse_params_json()
    if not ok:
        g["status_msg"] = f"JSON invalid: {err}"
        return False

    d = g["selected"]
    d["title"] = title
    d["executable"] = exe
    d["summary_expected"] = sum_expected
    d["summary_path"] = sum_path
    d["parameters"] = params_obj
    g["status_msg"] = "saved"
    return True


def save_definition():
    if g["running"]:
        return
    _save_current_to_model()
    _sync_disk()
    _request_sync_gui()


def _tree_item_to_definition(tree_itemid=None):
    if tree_itemid is None:
        tree_itemid = g["ui"]["tree"].selection()
        if not tree_itemid:
            return None
    
    try:
        idx = int(tree_itemid[0])
    except Exception:
        return None
    
    if 0 <= idx < len(g["definitions"]):
        return g["definitions"][idx]
    
    return None

def _on_tree_select(evt=None):
    d = _tree_item_to_definition()

    if not d:
        return

    if d is g["selected"]:
        return
    
    _save_current_to_model()
    g["selected"] = d
    _request_sync_gui()

    
def _on_tree_double_click(evt):
    if g["running"]:
        return
    run_command()


def new_definition():
    if g["running"]:
        return

    _save_current_to_model()

    d = _blank_definition()
    g["definitions"].append(d)
    g["selected"] = d
    g["status_msg"] = "new"
    
    _sync_disk()
    _request_sync_gui()


def delete_definition():
    if g["running"]:
        return

    if g["selected"] is None:
        return

    try:
        idx = selected_index()
    except Exception:
        idx = None

    if idx is None:
        return

    del g["definitions"][idx]

    if g["definitions"]:
        new_idx = min(idx, len(g["definitions"]) - 1)
        g["selected"] = g["definitions"][new_idx]
    else:
        g["selected"] = None

    g["status_msg"] = "deleted"

    _sync_disk()
    _request_sync_gui()


def move_up():
    if g["running"]:
        return

    idx = selected_index()
    if idx is None or idx <= 0:
        return

    defs = g["definitions"]
    defs[idx - 1], defs[idx] = defs[idx], defs[idx - 1]
    g["selected"] = defs[idx - 1]

    g["status_msg"] = "moved"

    _sync_disk()
    _request_sync_gui()


def move_down():
    if g["running"]:
        return

    idx = selected_index()
    if idx is None or idx >= len(g["definitions"]) - 1:
        return

    defs = g["definitions"]
    defs[idx + 1], defs[idx] = defs[idx], defs[idx + 1]
    g["selected"] = defs[idx + 1]

    g["status_msg"] = "moved"

    _sync_disk()
    _request_sync_gui()


def validate_json():
    _validate_params_and_update_status()

def insert_path():
    if g["running"]:
        return
    t = g["ui"]["params_text"]
    if t is None:
        return
    path = filedialog.askopenfilename()
    if not path:
        path = filedialog.askdirectory()
    if not path:
        return
    full = str(Path(path).resolve())
    # insert quoted full path at cursor
    t.insert(tk.INSERT, json.dumps(full))


def browse_executable():
    if g["running"]:
        return
    path = filedialog.askopenfilename()
    if not path:
        return
    _set_var("exe_var", str(Path(path).resolve()))


def browse_summary_path():
    if g["running"]:
        return
    path = filedialog.askopenfilename()
    if not path:
        return
    _set_var("summary_path_var", str(Path(path).resolve()))


def _next_execution_number():
    n = g["config"]["next-execution-number"]
    try:
        return int(n)
    except Exception:
        return 0


def _set_next_execution_number(n):
    g["config"]["next-execution-number"] = int(n)
    _safe_write_json(g["config_path"], g["config"])


def _execution_paths(n):
    base = Path(g["config"]["paths"]["execution-log-dir"])
    params_file = base / f"execution-{n}-parameters.json"
    inv_file = base / f"execution-{n}-invocation.json"
    return str(params_file), str(inv_file)


def _preflight_run_checks():
    # re-check everything right before GO
    if g["selected"] is None:
        _set_var("status_var", "no selection")
        return False
    if not _save_current_to_model():
        return False
    if not _executable_exists():
        _set_var("status_var", "executable missing")
        return False
    obj, ok, err = _parse_params_json()
    if not ok:
        _set_var("status_var", f"JSON invalid: {err}")
        return False
    if g["ui"]["summary_expected_var"].get():
        sp = g["ui"]["summary_path_var"].get().strip()
        if sp:
            # must be resolvable; parent should exist
            try:
                parent = Path(sp).expanduser().resolve().parent
                if not parent.exists():
                    _set_var("status_var", "summary_path parent missing")
                    return False
            except Exception:
                _set_var("status_var", "bad summary_path")
                return False
    return True


def run_command():
    if g["running"]:
        return

    _save_current_to_model()

    if not _run_ready():
        _request_sync_gui()
        return

    n = _next_execution_number()
    params_file, _ = _execution_paths(n)

    try:
        params_obj = g["selected"]["parameters"]
        Path(params_file).write_text(json.dumps(params_obj, indent=2) + "\n", encoding="utf-8")
    except Exception:
        g["status_msg"] = "could not write parameters file"
        _request_sync_gui()
        return

    inv = {
        "execution_number": n,
        "title": g["selected"]["title"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "executable": g["selected"]["executable"],
        "parameters_file": params_file,
        "summary_expected": bool(g["selected"]["summary_expected"]),
        "summary_path": g["selected"]["summary_path"],
        "summary_contents": None,
        "exit_status": None,
        "invocation_error": None,
    }

    g["invocation_record"] = inv
    g["running"] = True
    g["status_msg"] = "running…"
    
    _request_sync_gui()
    _sync_disk()

    main_to_worker.put("GO")


def _worker_loop():
    while True:
        try:
            msg = main_to_worker.get(timeout=0.5)
        except queue.Empty:
            continue

        if msg != "GO":
            continue

        inv = g["invocation_record"]
        if inv is None:
            worker_to_main.put("ERR")
            continue

        exe = inv["executable"]
        params_file = inv["parameters_file"]

        try:
            if not exe or not Path(exe).exists():
                inv["invocation_error"] = "executable not found"
                worker_to_main.put("ERR")
                continue
            if not params_file or not Path(params_file).exists():
                inv["invocation_error"] = "parameters file not found"
                worker_to_main.put("ERR")
                continue

            # run python script with parameters file
            cmd = [exe, params_file]

            if os.name == "nt" and exe.lower().endswith((".bat", ".cmd")):
                res = subprocess.run(cmd, shell=True)
            else:
                res = subprocess.run(cmd)
            inv["exit_status"] = int(res.returncode)
            worker_to_main.put("DONE")
        except Exception as e:
            inv["invocation_error"] = str(e)
            worker_to_main.put("ERR")


def _poll_worker_to_main():
    try:
        msg = worker_to_main.get_nowait()
    except queue.Empty:
        pass
    else:
        if msg == "DONE" or msg == "ERR":
            _on_worker_finished(msg)

    root = g["ui"]["root"]
    if root is not None:
        root.after(100, _poll_worker_to_main)


def _on_worker_finished(msg):
    inv = g["invocation_record"]
    if inv is None:
        # should not happen, but restore UI
        g["running"] = False
        _controls_set_enabled(True)
        return

    # If ERR, show message in status, still log invocation
    if msg == "ERR":
        if inv["invocation_error"]:
            _set_var("status_var", f"ERR: {inv['invocation_error']}")
        else:
            _set_var("status_var", "ERR")
    else:
        _set_var("status_var", "done")

    # Summary read + display (main thread)
    if inv["summary_expected"]:
        sp = inv["summary_path"].strip()
        if sp:
            try:
                summary_obj = _load_json_file(sp)
                inv["summary_contents"] = summary_obj
                _set_summary_text(json.dumps(summary_obj, indent=2) + "\n")
            except Exception:
                inv["summary_contents"] = None
                # treat as invocation_error only if none exists yet
                if not inv["invocation_error"]:
                    inv["invocation_error"] = "summary file missing or invalid"
                _set_summary_text("")
        else:
            inv["summary_contents"] = None
            _set_summary_text("")
    else:
        inv["summary_contents"] = None
        _set_summary_text("")

    # Exit code display
    if inv["exit_status"] is None:
        _set_var("exit_code_var", "")
    else:
        _set_var("exit_code_var", str(inv["exit_status"]))

    # Write invocation record to disk
    n = inv["execution_number"]
    _, inv_file = _execution_paths(n)
    _safe_write_json(inv_file, inv)

    # Advance execution number
    _set_next_execution_number(n + 1)

    # Clear running state
    g["running"] = False
    g["invocation_record"] = None

    # Re-enable UI
    _controls_set_enabled(True)


def _build_gui():
    # ui handles
    g["ui"]["root"] = None
    g["ui"]["tree"] = None

    root = tk.Tk()
    root.title("FileTalk Runner")
    g["ui"]["root"] = root

    # editor vars/widgets (kept in g so functions stay 0-arg)
    g["ui"]["title_var"] = tk.StringVar()
    g["ui"]["exe_var"] = tk.StringVar()
    g["ui"]["summary_expected_var"] = tk.BooleanVar(value=True)
    g["ui"]["summary_path_var"] = tk.StringVar()
    g["ui"]["status_var"] = tk.StringVar()
    g["ui"]["exit_code_var"] = tk.StringVar()

    g["ui"]["params_text"] = None
    g["ui"]["summary_text"] = None

    g["ui"]["btn_save"] = None
    g["ui"]["btn_run"] = None
    g["ui"]["btn_validate"] = None
    g["ui"]["btn_insert_path"] = None
    g["ui"]["btn_exe_browse"] = None
    g["ui"]["btn_sum_browse"] = None
    g["ui"]["btn_new"] = None
    g["ui"]["btn_delete"] = None
    g["ui"]["btn_up"] = None
    g["ui"]["btn_down"] = None

    outer = ttk.Frame(root, padding=8)
    outer.pack(fill="both", expand=True)

    outer.columnconfigure(0, weight=1)
    outer.columnconfigure(1, weight=4)
    outer.rowconfigure(0, weight=1)

    # Left: tree + controls
    left = ttk.Frame(outer)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    left.rowconfigure(1, weight=1)
    left.columnconfigure(0, weight=1)

    lbl = ttk.Label(left, text="Commands")
    lbl.grid(row=0, column=0, sticky="w")

    tree = ttk.Treeview(left, show="tree", selectmode="browse")
    tree.grid(row=1, column=0, sticky="nsew")
    g["ui"]["tree"] = tree

    tree.bind("<<TreeviewSelect>>", _on_tree_select)
    tree.bind("<Double-1>", _on_tree_double_click)

    btns = ttk.Frame(left)
    btns.grid(row=2, column=0, sticky="ew", pady=(8, 0))
    for i in range(4):
        btns.columnconfigure(i, weight=1)

    b_new = ttk.Button(btns, text="New", command=new_definition)
    b_del = ttk.Button(btns, text="Delete", command=delete_definition)
    b_up = ttk.Button(btns, text="Up", command=move_up)
    b_dn = ttk.Button(btns, text="Down", command=move_down)

    b_new.grid(row=0, column=0, sticky="ew", padx=(0, 4))
    b_del.grid(row=0, column=1, sticky="ew", padx=(0, 4))
    b_up.grid(row=0, column=2, sticky="ew", padx=(0, 4))
    b_dn.grid(row=0, column=3, sticky="ew")

    g["ui"]["btn_new"] = b_new
    g["ui"]["btn_delete"] = b_del
    g["ui"]["btn_up"] = b_up
    g["ui"]["btn_down"] = b_dn

    # Right: editor
    right = ttk.Frame(outer)
    right.grid(row=0, column=1, sticky="nsew")
    right.columnconfigure(1, weight=1)
    right.rowconfigure(5, weight=1)
    right.rowconfigure(9, weight=1)

    # Title row + Save/Run
    ttk.Label(right, text="Title:").grid(row=0, column=0, sticky="w")
    e_title = ttk.Entry(right, textvariable=g["ui"]["title_var"])
    e_title.grid(row=0, column=1, sticky="ew", padx=(4, 4))

    b_save = ttk.Button(right, text="Save", command=save_definition)
    b_run = ttk.Button(right, text="Run", command=run_command)
    b_save.grid(row=0, column=2, sticky="ew", padx=(0, 4))
    b_run.grid(row=0, column=3, sticky="ew")

    g["ui"]["btn_save"] = b_save
    g["ui"]["btn_run"] = b_run

    # Executable row
    ttk.Label(right, text="Executable:").grid(row=1, column=0, sticky="w", pady=(8, 0))
    e_exe = ttk.Entry(right, textvariable=g["ui"]["exe_var"])
    e_exe.grid(row=1, column=1, sticky="ew", padx=(4, 4), pady=(8, 0))
    b_exe = ttk.Button(right, text="Browse…", command=browse_executable)
    b_exe.grid(row=1, column=2, sticky="ew", pady=(8, 0))
    g["ui"]["btn_exe_browse"] = b_exe
    b_help = ttk.Button(right, text="Help", command=_show_executable_help)
    b_help.grid(row=1, column=3, sticky="ew", pady=(8, 0))
    g["ui"]["btn_exe_help"] = b_help
    
    # Summary row
    cb = ttk.Checkbutton(right, text="Summary:", variable=g["ui"]["summary_expected_var"])
    cb.grid(row=2, column=0, sticky="w", pady=(6, 0))
    e_sum = ttk.Entry(right, textvariable=g["ui"]["summary_path_var"])
    e_sum.grid(row=2, column=1, sticky="ew", padx=(4, 4), pady=(6, 0))
    b_sum = ttk.Button(right, text="Browse…", command=browse_summary_path)
    b_sum.grid(row=2, column=2, sticky="ew", pady=(6, 0))
    g["ui"]["btn_sum_browse"] = b_sum

    # Parameters label
    ttk.Label(right, text="Parameters (JSON):").grid(row=3, column=0, sticky="w", pady=(10, 0), columnspan=2)

    # Params text area
    params_frame = ttk.Frame(right)
    params_frame.grid(row=4, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
    params_frame.rowconfigure(0, weight=1)
    params_frame.columnconfigure(0, weight=1)

    t_params = tk.Text(params_frame, height=12, wrap="none")
    t_params.grid(row=0, column=0, sticky="nsew")
    g["ui"]["params_text"] = t_params

    # Buttons under params
    btn_row = ttk.Frame(right)
    btn_row.grid(row=6, column=0, columnspan=4, sticky="w", pady=(6, 0))
    b_val = ttk.Button(btn_row, text="Validate JSON", command=validate_json)
    b_ins = ttk.Button(btn_row, text="Insert Path…", command=insert_path)
    b_val.grid(row=0, column=0, padx=(0, 6))
    b_ins.grid(row=0, column=1)

    g["ui"]["btn_validate"] = b_val
    g["ui"]["btn_insert_path"] = b_ins

    # Status
    ttk.Label(right, text="Status:").grid(row=7, column=0, sticky="w", pady=(8, 0))
    lbl_status = ttk.Label(right, textvariable=g["ui"]["status_var"])
    lbl_status.grid(row=7, column=1, sticky="w", pady=(8, 0), columnspan=3)

    # Summary output
    ttk.Label(right, text="Summary:").grid(row=8, column=0, sticky="w", pady=(10, 0), columnspan=2)

    summary_frame = ttk.Frame(right)
    summary_frame.grid(row=9, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
    summary_frame.rowconfigure(0, weight=1)
    summary_frame.columnconfigure(0, weight=1)

    t_sum = tk.Text(summary_frame, height=10, wrap="none", state="disabled")
    t_sum.grid(row=0, column=0, sticky="nsew")
    g["ui"]["summary_text"] = t_sum

    # Exit code entry (beneath summary)
    ttk.Label(right, text="Exit Code:").grid(row=10, column=0, sticky="w", pady=(6, 0))
    e_exit = ttk.Entry(right, textvariable=g["ui"]["exit_code_var"], state="readonly")
    e_exit.grid(row=10, column=1, sticky="w", pady=(6, 0))

    return root

def _show_executable_help():
    root = g["ui"]["root"]

    win = tk.Toplevel(root)
    win.title("Executable Help")
    win.geometry("700x500")
    win.transient(root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True, padx=8, pady=8)

    yscroll = tk.Scrollbar(frame, orient="vertical")
    yscroll.pack(side="right", fill="y")

    text = tk.Text(frame, wrap="word", yscrollcommand=yscroll.set)
    text.pack(side="left", fill="both", expand=True)

    yscroll.config(command=text.yview)

    help_text = (
        "What goes in the Executable field?\n\n"
        "This must be a path to something that can be EXECUTED and that accepts exactly ONE "
        "argument: the path to a JSON file containing parameters. The Runner will invoke it like:\n\n"
        "    <executable> <path-to-parameters.json>\n\n"
        "The Runner does NOT pass environment variables, does NOT stream output, and does NOT pass "
        "multiple arguments. All information must flow through files (FileTalk style).\n\n"
        "----------------------------------------\n"
        "Windows (recommended: use a .BAT file)\n\n"
        "On Windows, the easiest and most reliable method is to create a small batch file that "
        "invokes your program correctly.\n\n"
        "Example: run_my_tool.bat\n\n"
        "    @echo off\n"
        "    REM %1 is the JSON parameter file path\n"
        "    python C:\\path\\to\\my_script.py \"%~1\"\n\n"
        "Important:\n"
        "  * Always use \"%~1\" (with quotes) when passing the argument onward\n"
        "  * This preserves spaces in file paths\n\n"
        "Then set Executable to:\n\n"
        "    C:\\path\\to\\run_my_tool.bat\n\n"
        "----------------------------------------\n"
        "macOS / Linux (use a .SH file)\n\n"
        "Create a shell script and make it executable.\n\n"
        "Example: run_my_tool.sh\n\n"
        "    #!/bin/bash\n"
        "    python3 /home/user/my_script.py \"$1\"\n\n"
        "Then run once:\n\n"
        "    chmod +x run_my_tool.sh\n\n"
        "And set Executable to:\n\n"
        "    /home/user/run_my_tool.sh\n\n"
        "----------------------------------------\n"
        "Why use wrapper scripts?\n\n"
        "Different programs may need virtual environments, working directories, containers, or "
        "special setup. Rather than teaching the Runner how to handle every case, your wrapper script "
        "owns those details. The Runner only delivers the JSON file path and records what happened.\n\n"
        "This keeps machines explicit, inspectable, and reproducible — the FileTalk way.\n"
    )

    text.insert("1.0", help_text)
    text.config(state="disabled")

    btn = tk.Button(win, text="Close", command=win.destroy)
    btn.pack(pady=(0, 8))


args_stub = {
    "paths": {
        "execution-log-dir": "<path to execution log dir>",
        "definitions": "<path to definitions.json>"
    },
    "next-execution-number": 0
}

def main():
    if not ftp.has_json_arg("j"):
        ftp.print_stub(args_stub, "Sr")  # require summary file; optional request-id
        return

    # Start FileTalk process for runner itself
    ftp.start("cr")  # c=complex events, r=request-id

    try:
        # read configuration from arguments
        inv = ftp.g["invocation"]
        cfg = g["config"] = inv["ARGS"]
        
        if "paths" not in cfg:
            _fail_after_config_load("config missing paths", "CONFIG-MISSING-PATHS")
        paths = cfg["paths"]
        for k in ["execution-log-dir", "definitions", "summary-file"]:
            if k not in paths:
                _fail_after_config_load(f"config missing paths.{k}", "CONFIG-MISSING-PATH")

        _config_paths_ok()
        _load_definitions_or_exit()

        # choose default selection
        if g["definitions"]:
            g["selected"] = g["definitions"][0]
        else:
            g["selected"] = None

        # worker thread
        t = threading.Thread(target=_worker_loop, daemon=True)
        t.start()

        # GUI
        root = _build_gui()
        _refresh_tree()
        _editor_set_from_selected()

        # poll worker results
        root.after(100, _poll_worker_to_main)

        root.mainloop()
        g["exec_complete"] = True

    except SystemExit:
        # summary already written in _fail_after_config_load; just exit
        raise
    except Exception as e:
        # unexpected; still write summary
        ftp.record_exception()
        ftp.output_summary("cte1")
    finally:
        ftp.output_summary("cot0")  # (c)omplete, status: (o)k, (t)imestamp, exit code (0)

    raise SystemExit(ftp.get("exit-code"))

