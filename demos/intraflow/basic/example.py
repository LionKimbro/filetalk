import tkinter as tk
import intraflow.intraflow as flow


# ================================================================
# GLOBAL GUI CONTEXT
# ================================================================

ui = {
    "root": None,
    "canvas": None,
    "widgets": {}
}


# ================================================================
# GUI HELPERS
# ================================================================

def widget(name):
    return ui["widgets"][name]


def add_widget(name, w):
    ui["widgets"][name] = w
    return w


# ================================================================
# COMPONENTS
# ================================================================

#
# ENTRY COMPONENT
#
def entry_activation():
    # No incoming messages required; activation is event driven
    pass


def entry_emit(text):
    flow.emit_signal("text", text)


#
# TEXT DISPLAY COMPONENT
#
def text_activation():
    msg = flow.g["msg"]
    if msg["channel"] == "set":
        w = widget("text")
        w.delete("1.0", tk.END)
        w.insert(tk.END, msg["signal"])


#
# BUTTON COMPONENT
#
def button_activation():
    # Button only emits from GUI event
    pass


def button_emit():
    flow.emit_signal("clicked", None)


#
# LOGGER COMPONENT (draw messages onto canvas)
#
def logger_activation():
    msg = flow.g["msg"]

    c = widget("canvas")
    text = f"{msg['channel']}: {msg['signal']}"
    c.create_text(10, logger_activation.y, anchor="nw", text=text)

    logger_activation.y += 18

logger_activation.y = 10


# ================================================================
# GUI BUILD
# ================================================================

def build_gui():
    root = tk.Tk()
    root.title("IntraFlow Patchable GUI")

    canvas = tk.Canvas(root, width=600, height=300, bg="white")
    canvas.pack(fill="both", expand=True)

    ui["root"] = root
    add_widget("canvas", canvas)

    entry = tk.Entry(root)
    entry.pack(fill="x")
    add_widget("entry", entry)

    text = tk.Text(root, height=5)
    text.pack(fill="x")
    add_widget("text", text)

    btn = tk.Button(root, text="Emit Click")
    btn.pack()
    add_widget("button", btn)

    # Bind events
    entry.bind("<Return>", lambda e: entry_emit(entry.get()))
    text.bind("<Control-Return>", lambda e: flow.emit_signal("submit", text.get("1.0", tk.END)))
    btn.config(command=button_emit)


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
    flow.address_components(("component", "entry"), ("component", "text"))
    flow.link_channels("text", "set")
    flow.commit_links()

    flow.address_components(("component", "entry"), ("component", "logger"))
    flow.link_channels("text", "log")
    flow.commit_links()

    flow.address_components(("component", "button"), ("component", "logger"))
    flow.link_channels("clicked", "log")
    flow.commit_links()


# ================================================================
# MAIN
# ================================================================

def main():
    build_gui()

    flow.register_component("entry", entry_activation)
    flow.register_component("text", text_activation)
    flow.register_component("button", button_activation)
    flow.register_component("logger", logger_activation)

    wire_default()

    tick()
    ui["root"].mainloop()


if __name__ == "__main__":
    main()
