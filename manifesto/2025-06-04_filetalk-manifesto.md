# The FileTalk 2025 Manifesto

**Author:** Lion Kimbro & Wing-Kat
**Date:** 2025-06-02

---

## 🧭 Introduction

**FileTalk2025** is not a radical vision -- it's a return to the forgotten dream of a composer's toolkit: where software modules snap together like Eurorack synths, each one clear, exposed, and ready to function, to be connected, and reconnected, as the creative spirit wills.

The last time this vision stood so clearly was in the Unix world of the 1970s, a full fifty years ago.  In that world, small programs, written in various programming languages - it didn't matter which ones - were able to freely communicate and collaborate.  Whole libraries collapsed into tiny tools - `cat`, `ls`, `awk`, `sed` - whose names fit in a breath and whose arguments unlocked universes.  This order ran the world for decades - and its execution still pulses within our running systems today.  And yet there were limitations too - each pipeline was linear.  Configuration became byzantine, and had to be expressed in that one command line.  GUIs were nowhere to be seen.  And the left-to-right pipeline was unsuited for the complex network web of relationships that full persisting systems demand.

With FileTalk 2025, I am calling for a return to the core insights behind the Unix philosophy.  Yes, artificial intelligence is rewriting everything about how we program today.  But I still believe in architecture, I still believe in systems.  I do not believe that we have fully mined the architectural insights of the past.  It is not enough to say, "AI will do it."  We must still walk the cathedrals and the catacombs of our systems - and they must still offer passage.  There is still so much work to do, so much work that remained undone.

So let us make see-through programs: tools that expose their state, tools that communicate in a plainspoken way.  Let us return to software meant to be played with - reusable, remixable, and ready to be patched together.

This manifesto outlines the **core philosophy** and **communication patterns** of FileTalk2025.

---

## 🌱 Core Philosophy

* **Modularity Over Monoliths** — A FileTalk system is built from parts. Each part is small. Each part is self-contained. Each part can be replaced.
* **Plain-Spoken Software** — The file is the interface. Programs talk by writing JSON to a folder and reading JSON from a folder. Nothing fancy. Nothing hidden.
* **No Threads, No Sockets** — Programs do not speak through tangled threads or network ports. They speak by leaving letters in each other's mailboxes.
* **Legibility** — Anyone should be able to see what a program is doing by opening its files. JSON is human-readable, diffable, and universal.
* **Immanent Replaceability** — If a module follows the file interface pattern, it can be swapped out for another. That’s the contract. That’s the freedom.

These principles are not only about simplicity — they are about **commonality**. They rely on what every programmer knows. How to read a file. How to write a file. How to parse JSON. How to wait one second and poll again. These are the tools of every language, every platform, every coder. FileTalk uses what is **ordinary** to build what is **extraordinary**.

---

## 🔌 How FileTalk Programs Speak

FileTalk programs communicate in three primary ways:

### 1. Sending Messages

A program sends a message by writing a JSON file to a folder.

* The folder is chosen based on purpose — for example, the receiving program’s `input/` folder.
* The file can be named however you like, though typically a GUID is used, such as `7269d7c7-b078-41e7-9c1a-31c62cf52df3.json`.
* The contents are plain JSON — a dictionary or list, easily parseable.

This is the essence of commanding another module: Write to its mailbox. Speak plainly. Speak cleanly.

### 2. Receiving Messages

A program listens by polling a directory and reading any `.json` files it finds.

* Each file is parsed.
* Each message is handled.
* Each file is deleted (or archived) once it's processed.

If the file isn’t ready — if it was still being written and is incomplete — the file is skipped, and will be tried again next poll.

### 3. Publishing Status

Programs can leave snapshots of their state in a shared directory. These are files like:

* `current_state.json`
* `latest_output.json`
* `status_123.json`

Other programs — or humans — can read these at any time. This is not a request-response model. It is visibility. Transparency. A program says, "This is what I see."

---

## 🧪 A Glimpse of the Ecology

FileTalk is not a single program. It is a community of processes. A patchable system.

Imagine:

* A `duration_logger.py` that records start/stop events
* A `day_keeper.py` that defines the boundaries of days
* A `summary_builder.py` that reads from both and creates visual logs
* A `status_server.py` that watches many programs and aggregates status
* A `notifier.py` that sends you messages based on certain conditions
* A `generic_control_panel.py` that provides a reusable UI:

  * Sliders, buttons, a single-line text entry, a multi-line text output, and a canvas for drawing
  * Drawings are rendered dynamically when drawing instructions are written to a designated file
  * User actions (e.g., pressing a button or changing a slider) are logged with timestamps, and the most recent command is shown in a "latest command" file
  * A live text input area automatically writes to a log whenever the associated timestamp changes

These control panels can serve many purposes — interactive dashboards, visual monitoring stations, or live command consoles. Any FileTalk module can emit instructions or read user input from them.

All these pieces are independent. All speak through files. All can be inspected, replaced, recombined. This is not a framework. It is a **fabric**.

Let each program:

* Speak plainly
* Accept readable commands
* Show its state
* Be inspectable
* Be interchangeable

Let FileTalk2025 be a **village of programs** — transparent, generous, and alive.
