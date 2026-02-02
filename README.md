
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

---

## 🌿 Start Here: The Manifesto

### 📜 FileTalk (The Manifesto)

**What it is:**
The foundational statement of FileTalk's philosophy and goals.

* Defines *what FileTalk is and is not*
* Epoch-agnostic
* Timeless by intent

📄 **Read this first.**
Everything else in this repository flows from the ideas in [the Manifesto.](docs/manifesto/2025-06-04_filetalk-manifesto.md)

---

## 🔌 Patchboard: System Wiring & Message Routing

**What it is:**
A modular architecture for building live systems out of many small programs.

Patchboard introduces:

* inbox / outbox conventions,
* standardized message files,
* external routing via a Patchboard Router,
* and dynamic rewiring of program connections.

**Specifications:**

* 📄 [Patchboard Core Message Spec](docs/spec/patchboard-core.v1.md) — the fundamental message format (channel, signal, timestamp)
* 📄 [Patchboard File Transport Spec](docs/spec/patchboard-file-transport.v1.md) — how messages are represented as files in INBOX/OUTBOX directories

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

### 2️⃣ Patchboard

The **system architecture**.

* Programs connected into routed message networks
* Externalized wiring and live reconfiguration

---

### 3️⃣ Patchboard Router

The **routing fabric**.

* Watches module outboxes
* Copies messages into inboxes based on routing tables
* Enables rewiring without restarting modules
* Emits lifecycle messages (startup, shutdown, change notices)

The Patchboard Router is a headless, file-controlled process. Routes are added and removed by sending messages to its inbox. The router publishes its state as JSON files for external inspection.

**CLI Commands:**

```
patchboard run       # Launch the router
patchboard status    # Display current state
patchboard routes    # Display routing table
patchboard link      # Request route creation
patchboard unlink    # Request route removal
patchboard quit      # Request graceful shutdown
```

**Route creation example:**

```
patchboard link --sf /path/to/OUTBOX --sc data --df /path/to/INBOX --dc received
```

This creates a route: messages with channel "data" in the source OUTBOX are delivered to the destination INBOX with channel "received".

---

### 4️⃣ Patchboard Modules

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

## 📌 Status (2026-02-02)

* **FileTalk Manifesto:** stable and canonical
* **Patchboard Architecture:** active and evolving
* **Patchboard Router:** implemented and functional
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

## 🔮 What's Coming

Future development may include:

* example Patchboard Modules
* small, composable utilities
* complete demonstration systems
* monitoring and diagnostic tools

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
