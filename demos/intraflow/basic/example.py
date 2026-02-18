"""demos/intraflow/basic/example.py"""

import tkinter as tk
import intraflow as flow


# ================================================================
# GLOBAL CONTEXT
# ================================================================

g = {
    "evt": None,
    "component": None,
    "suppress_events": False,
}

widgets = {}


# ================================================================
# WIDGET-TO-COMPONENT REGISTRY
# ================================================================

_widget_components = {}  # id(widget) -> list of component dicts

def register_widget_component(w, comp):
    _widget_components.setdefault(id(w), []).append(comp)

def get_components_for_widget(w):
    return _widget_components.get(id(w), [])


# ================================================================
# EVENT HANDLING
# ================================================================

def handle_event(evt, comp, fn):
    """Set GUI event context, call fn(), then clear context."""
    if g["suppress_events"]:
        return
    g["evt"] = evt
    g["component"] = comp
    fn()
    g["component"] = None
    g["evt"] = None


# ================================================================
# ACTIVATION FUNCTIONS
# ================================================================

def entry_activation():
    msg = flow.g["msg"]
    if msg["channel"] == "text":
        w = flow.g["component"]["state"]["widget"]
        g["suppress_events"] = True
        w.delete(0, tk.END)
        w.insert(0, str(msg["signal"]))
        g["suppress_events"] = False


def text_activation():
    msg = flow.g["msg"]
    if msg["channel"] == "set":
        w = flow.g["component"]["state"]["widget"]
        g["suppress_events"] = True
        w.delete("1.0", tk.END)
        w.insert(tk.END, str(msg.get("signal", "(None)")))
        g["suppress_events"] = False


def button_activation():
    msg = flow.g["msg"]
    if msg["channel"] == "label":
        w = flow.g["component"]["state"]["widget"]
        w.config(text=str(msg["signal"]))


def logger_activation():
    comp = flow.g["component"]
    msg = flow.g["msg"]
    canvas = comp["state"]["widget"]
    y = comp["state"]["y"]
    g["suppress_events"] = True
    canvas.create_text(10, y, anchor="nw", text=f"{msg['channel']}: {msg['signal']}")
    g["suppress_events"] = False
    comp["state"]["y"] += 18


def fixed_emitter_activation():
    msg = flow.g["msg"]
    comp = flow.g["component"]
    if msg["channel"] == "emit":
        flow.emit_signal("output", comp["state"]["signal"])
    elif msg["channel"] == "set":
        comp["state"]["signal"] = msg["signal"]


# ================================================================
# EVENT HANDLER FUNCTIONS
# ================================================================

def entry_return_handler():
    w = g["component"]["state"]["widget"]
    g["component"]["outbox"].append(flow.make_message("text", w.get()))


def button_click_handler():
    g["component"]["outbox"].append(flow.make_message("clicked", None))


# ================================================================
# ATTACH FUNCTIONS
# ================================================================

def attach_widget(component_id, w, activation):
    comp = flow.register_component(component_id, activation)
    comp["state"]["widget"] = w
    register_widget_component(w, comp)
    return comp


def attach_entry(component_id, w):
    comp = attach_widget(component_id, w, entry_activation)
    w.bind("<Return>", lambda evt: handle_event(evt, comp, entry_return_handler))
    return comp


def attach_text(component_id, w):
    return attach_widget(component_id, w, text_activation)


def attach_button(component_id, w):
    comp = attach_widget(component_id, w, button_activation)
    w.config(command=lambda: handle_event(None, comp, button_click_handler))
    return comp


def attach_logger(component_id, w):
    comp = attach_widget(component_id, w, logger_activation)
    comp["state"]["y"] = 10
    return comp


# ================================================================
# GUI BUILD
# ================================================================

def build_gui():
    root = tk.Tk()
    root.title("IntraFlow Patchable GUI")

    canvas = tk.Canvas(root, width=600, height=300, bg="white")
    canvas.pack(fill="both", expand=True)

    widgets["root"] = root
    widgets["canvas"] = canvas

    entry = tk.Entry(root)
    entry.pack(fill="x")
    widgets["entry"] = entry

    text = tk.Text(root, height=5)
    text.pack(fill="x")
    widgets["text"] = text

    btn = tk.Button(root, text="Emit Click")
    btn.pack()
    widgets["button"] = btn

    btn2 = tk.Button(root, text="Click Emitter #2")
    btn2.pack()
    widgets["button2"] = btn2

    attach_entry("entry", entry)
    attach_text("text", text)
    attach_button("button", btn)
    attach_button("button2", btn2)
    attach_logger("logger", canvas)


# ================================================================
# RUNTIME LOOP
# ================================================================

def tick():
    flow.run_cycle()
    widgets["root"].after(16, tick)   # ~60hz


# ================================================================
# WIRING
# ================================================================

def wire_default():
    """

        [entry:text]──────► [set:text]
                     │
                     └────► [log:logger]
                     │
                     └────► [label:button2]


      [button:clicked] ───► [log:logger]

      [button2:clicked] ──► [emit:fixed_emitter:output]  ──► [log:logger]

    """
    emitter = flow.register_component("fixed_emitter", fixed_emitter_activation)
    emitter["state"]["signal"] = "boo!"

    flow.address_components("entry", "text")
    flow.link_channels("text", "set")
    flow.commit_links()

    flow.address_components("entry", "logger")
    flow.link_channels("text", "log")
    flow.commit_links()

    flow.address_components("button", "logger")
    flow.link_channels("clicked", "log")
    flow.commit_links()

    flow.address_components("entry", "button2")
    flow.link_channels("text", "label")
    flow.commit_links()

    flow.address_components("button2", "fixed_emitter")
    flow.link_channels("clicked", "emit")
    flow.commit_links()

    flow.address_components("fixed_emitter", "logger")
    flow.link_channels("output", "log")
    flow.commit_links()


# ================================================================
# MAIN
# ================================================================

def main():
    build_gui()
    wire_default()
    tick()
    widgets["root"].mainloop()


if __name__ == "__main__":
    main()
