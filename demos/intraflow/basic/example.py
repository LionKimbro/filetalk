"""demos/intraflow/basic/example.py"""

import tkinter as tk
import intraflow as flow


# ================================================================
# GLOBAL GUI CONTEXT
# ================================================================

ui = {
    "root": None,
    "canvas": None,
    "widgets": {}
}


# ================================================================
# WIDGET HELPERS
# ================================================================

def widget(name):
    return ui["widgets"][name]

def add_widget(name, w):
    ui["widgets"][name] = w
    return w


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
    """Set IntraFlow context for a GUI event, call fn(), then clear context."""
    flow.g["evt"] = evt
    flow.g["component"] = comp
    fn()
    flow.g["component"] = None
    flow.g["evt"] = None


# ================================================================
# ACTIVATION FUNCTIONS
# ================================================================

def entry_activation():
    pass  # Entry only emits; it doesn't process incoming messages


def text_activation():
    msg = flow.g["msg"]
    if msg["channel"] == "set":
        w = flow.g["component"]["state"]["widget"]
        w.delete("1.0", tk.END)
        w.insert(tk.END, str(msg.get("signal", "(None)")))


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
    canvas.create_text(10, y, anchor="nw", text=f"{msg['channel']}: {msg['signal']}")
    comp["state"]["y"] += 18


# ================================================================
# EVENT HANDLER FUNCTIONS
# ================================================================

def entry_return_handler():
    w = flow.g["component"]["state"]["widget"]
    flow.emit_signal("text", w.get())


def button_click_handler():
    flow.emit_signal("clicked", None)


# ================================================================
# COMPONENT FACTORIES
# ================================================================

def make_entry(component_id, parent):
    w = tk.Entry(parent)
    w.pack(fill="x")
    add_widget(component_id, w)
    comp = flow.register_component(component_id, entry_activation)
    comp["state"]["widget"] = w
    register_widget_component(w, comp)
    w.bind("<Return>", lambda evt: handle_event(evt, comp, entry_return_handler))
    return comp


def make_text(component_id, parent):
    w = tk.Text(parent, height=5)
    w.pack(fill="x")
    add_widget(component_id, w)
    comp = flow.register_component(component_id, text_activation)
    comp["state"]["widget"] = w
    register_widget_component(w, comp)
    return comp


def make_button(component_id, parent, label="Emit Click"):
    comp = flow.register_component(component_id, button_activation)
    w = tk.Button(parent, text=label,
                  command=lambda: handle_event(None, comp, button_click_handler))
    w.pack()
    add_widget(component_id, w)
    comp["state"]["widget"] = w
    register_widget_component(w, comp)
    return comp


def make_logger(component_id, canvas):
    comp = flow.register_component(component_id, logger_activation)
    comp["state"]["widget"] = canvas
    comp["state"]["y"] = 10
    register_widget_component(canvas, comp)
    return comp


# ================================================================
# GUI BUILD
# ================================================================

def build_gui():
    root = tk.Tk()
    root.title("IntraFlow Patchable GUI")

    canvas = tk.Canvas(root, width=600, height=300, bg="white")
    canvas.pack(fill="both", expand=True)

    ui["root"] = root
    ui["canvas"] = canvas
    add_widget("canvas", canvas)

    make_entry("entry", root)
    make_text("text", root)
    make_button("button", root)
    make_logger("logger", canvas)


# ================================================================
# RUNTIME LOOP
# ================================================================

def tick():
    flow.run_cycle()
    ui["root"].after(16, tick)   # ~60hz


# ================================================================
# WIRING
# ================================================================

def wire_default():
    """

        [entry:text]──────► [set:text]
                     │
                     └────► [log:logger]


      [button:clicked] ───► [log:logger]

    """
    flow.address_components("entry", "text")
    flow.link_channels("text", "set")
    flow.commit_links()

    flow.address_components("entry", "logger")
    flow.link_channels("text", "log")
    flow.commit_links()

    flow.address_components("button", "logger")
    flow.link_channels("clicked", "log")
    flow.commit_links()


# ================================================================
# MAIN
# ================================================================

def main():
    build_gui()
    wire_default()
    tick()
    ui["root"].mainloop()


if __name__ == "__main__":
    main()
