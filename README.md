
# FileTalk

**FileTalk** is a worldview and design philosophy for building software systems whose components communicate by **writing and reading files**.

At its heart:

* **Files are the interface**
* **JSON is the medium**
* **The filesystem is the meeting ground**

FileTalk favors legibility, decoupling, and durability over speed and hidden infrastructure.
By operating at the level of files, systems become:

* inspectable by humans,
* resilient to crashes and restarts,
* portable across languages and platforms,
* and friendly to experimentation and repair.

FileTalk is not a framework.
It is a way of thinking about systems.

This repository contains the **FileTalk worldview** and two concrete projects that grow naturally from it:

* 🪪 **JSON Run Cards** — how programs are launched and how runs are observed
* 🔌 **Patchboard** — how programs are wired into live, reconfigurable systems

---

## 🌿 Start Here: The Manifesto

### 📜 FileTalk (The Manifesto)

**What it is:**
The foundational statement of FileTalk’s philosophy and goals.

* Defines *what FileTalk is and is not*
* Epoch-agnostic
* Timeless by intent

📄 **Read this first.**
Everything else in this repository flows from the ideas in [the Manifesto.](docs/manifesto/2025-06-04_filetalk-manifesto.md)

---

## 🧭 Two Projects Under the FileTalk Umbrella

FileTalk itself is a worldview, not a protocol suite.
However, certain recurring needs arise naturally in FileTalk-style systems.
This repository develops two complementary projects to address those needs.

---

### 🪪 JSON Run Cards (Execution & Observability)

**What it is:**
A concrete convention for representing program runs using paired JSON artifacts:

* **Job Cards** — describe what work to perform
* **Report Cards** — summarize what happened during the run

Run Cards provide a simple, tool-friendly interface between:

* runners,
* schedulers,
* dashboards,
* and the programs being executed.

They intentionally:

* eliminate ad-hoc command-line argument parsing,
* replace shell incantations with structured data,
* and make runs replayable, inspectable, and automatable.

Run Cards say:

> “Here is the work.”
> “Here is the report.”

They are compatible with FileTalk systems, but not dependent on any particular system architecture.

---

### 🔌 Patchboard (System Wiring & Message Routing)

**What it is:**
A modular architecture for building live systems out of many small programs.

Patchboard introduces:

* inbox / outbox conventions,
* standardized message files,
* external routing via a Patchboard Router,
* and dynamic rewiring of program connections.

Programs emit messages without knowing where they will go.
Connections are defined outside the programs themselves.

Patchboard is inspired by:

* modular synthesizers,
* signal routing boards,
* and classic Unix composability — extended into network-like graphs.

> ⚠️ **Important:**
> Patchboard is one *architectural application* of FileTalk, not the definition of FileTalk itself.
> Other FileTalk architectures are possible and welcome.

---

## 🧠 Conceptual Map

The project distinguishes several related but separate concepts:

### 1️⃣ FileTalk

The **worldview**.

* Philosophy of plainspoken, file-based program cooperation
* Defined by the Manifesto
* No required topology or infrastructure

---

### 2️⃣ JSON Run Cards

The **execution interface**.

* Job Cards and Report Cards
* Used by runners, schedulers, and dashboards
* About starting programs and observing runs

Not about inter-program messaging.

---

### 3️⃣ Patchboard

The **system architecture**.

* Programs connected into routed message networks
* Externalized wiring and live reconfiguration

---

### 4️⃣ Patchboard Router

The **routing fabric**.

* Watches module outboxes
* Copies messages into inboxes based on patch maps
* Enables rewiring without restarting modules

---

### 5️⃣ Patchboard Modules

The **participants**.

* Small, independent programs
* Read from inbox, write to outbox
* Any language capable of file I/O

Modules may be:

* native Patchboard participants,
* standalone FileTalk-style tools,
* or adapted via small translation processes.

---

## 🤝 Participation Without Native Modules

Programs do not need to be written as Patchboard Modules to participate in Patchboard systems.

Any program that can emit files — logs, exports, snapshots, reports — can be connected via small adapters that translate file output into Patchboard messages, and vice versa.

This allows systems to incorporate:

* legacy tools,
* command-line utilities,
* batch jobs,
* experimental scripts,

without rewriting them or making them Patchboard-aware.

Patchboard Modules are a **native participation style**, not a requirement.

---

## 📌 Status (2026-01-27)

* **FileTalk Manifesto:** stable and canonical
* **JSON Run Cards:** active, early but stabilizing
* **Patchboard Architecture:** active and evolving
* **Patchboard Router:** currently primitive and experimental
* **Modules & Examples:** early prototypes

This repository prioritizes **clarity and direction** over completeness.
Some components are intentionally simple or provisional.

---

## 🌱 Philosophy

FileTalk systems aim to be:

* inspectable by humans,
* composable without heavy frameworks,
* resilient to crashes and restarts,
* honest about their state,
* built from small, replaceable parts.

FileTalk is not about performance first.
It is about **understandability over time**.

---

## 🔮 What’s Coming

In the near future, this repository will grow to include:

* reference runners for JSON Run Cards
* a more capable Patchboard Router
* example Patchboard Modules
* small, composable utilities
* complete demonstration systems

All additions will follow the spirit of the Manifesto:
plain, inspectable, and remixable.

---

## 🌄 Closing

If you are curious about building systems that feel more like
**villages of programs** than monoliths or services,
FileTalk may resonate with you.

Begin with the Manifesto.
Everything else grows from there.

🐾

---

## Author

FileTalk is authored and maintained by **Lion Kimbro**.

You can follow ongoing thoughts, experiments, and updates on X:
👉 [https://x.com/LionKimbro](https://x.com/LionKimbro)
