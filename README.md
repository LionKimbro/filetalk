
# FileTalk

**FileTalk** is a philosophy and architectural approach for building software systems whose components communicate by **writing and reading files**.

At its core:

* **Files are the interface**
* **JSON is the medium**
* **The filesystem is the bus**

This approach is intentionally slower than in-process communication between tightly coupled components. That trade-off is deliberate. By operating at the level of files, FileTalk systems gain legibility, decoupling, crash resilience, and language independence — qualities that are difficult to achieve in faster, more opaque architectures.

FileTalk favors inspectability and composability over abstraction-heavy frameworks or hidden infrastructure. It is deliberately low-tech, portable across languages and platforms, and designed to support systems that can be understood, repaired, and evolved over long periods of time.

This repository contains both **the core FileTalk paradigm** and **a concrete system built on top of it**.

---

## Recommended Reading Order

If you are new to FileTalk, read the following **in order**:

### 1. 📜 FileTalk (The Manifesto)

**What it is:**
The foundational philosophy and design principles of FileTalk.

* Defines *what FileTalk is*
* Epoch-agnostic
* Timeless by intent

📄 **Start here.**
This document explains *why* FileTalk exists and what problem it addresses.

---

### 2. 🔌 FileTalk Patchboard (Architecture)

**What it is:**
A concrete, modular system built *on top of* the FileTalk paradigm.

* Introduces dynamic routing
* Externalizes connections between programs
* Enables live rewiring of systems

📄 This document describes the **current active architecture** and should be read *after* the Manifesto.

> ⚠️ **Note:**
> FileTalk Patchboard is one *application* of FileTalk — not the definition of FileTalk itself.
> Other FileTalk architectures may exist or emerge in the future.

---

## Conceptual Structure

The project distinguishes **five related but separate concepts**:

### 1️⃣ FileTalk

The **paradigm**.

* A philosophy of file-based, plainspoken program communication
* Defined by the Manifesto
* Independent of any specific routing or topology

---

### 2️⃣ FileTalk Patchboard

The **system / architecture**.

* A modular, dynamically routed FileTalk system
* Inspired by modular synthesizers (patch cords, signal flow)
* Programs emit messages without knowing their destinations

---

### 3️⃣ Patchboard Router

The **routing fabric**.

* A central process that watches module outboxes
* Routes messages to inboxes based on external configuration
* Enables live rewiring without restarting modules

---

### 4️⃣ Patchboard Interface

The **contract**.

* Inbox / outbox conventions
* Message file format
* Polling and lifecycle rules
* Expectations that modules follow to participate in Patchboard systems

This defines *how* Patchboard Modules speak.

---

### 5️⃣ Patchboard Modules

The **participants**.

* Small, independent programs
* Read messages from an inbox
* Emit messages to an outbox
* Can be written in any language capable of file I/O

Modules may be:

* Patchboard-compatible
* Standalone FileTalk programs
* Adapted in or out of Patchboard systems


### Participation Without Native Modules

Programs do not need to be written as Patchboard Modules to participate in a FileTalk Patchboard system.

Any program that can be coaxed into emitting data as files — logs, status dumps, snapshots, exports, or reports — can be connected to a Patchboard system via small adapter processes. These adapters translate existing file output into messages that conform to the Patchboard Interface, and may also relay Patchboard messages outward into formats expected by external tools.

This allows FileTalk Patchboard systems to incorporate legacy software, command-line tools, batch jobs, and experimental scripts without requiring them to be rewritten or made Patchboard-aware.

Patchboard Modules represent a *native* participation model, not an exclusive one.
---

## Status (2026-01-03)

* **FileTalk (Manifesto):** stable and canonical
* **FileTalk Patchboard:** active and evolving
* **Patchboard Router:** currently primitive and experimental
* **Modules:** early examples and prototypes

This repository prioritizes **clarity and direction** over completeness.
Some components are intentionally simple or provisional.

---

## Philosophy

FileTalk systems aim to be:

* Inspectable by humans
* Composable without central frameworks
* Resilient to crashes and restarts
* Honest about their state
* Built from small, replaceable parts

FileTalk is not a framework.
It is a way of thinking about systems.

---

## What’s Coming

(2026-01-03:) In the coming weeks, this repository will grow to include:

* A reference Patchboard Router
* Example Patchboard Modules
* Small, composable utilities
* Practical demonstrations of FileTalk Patchboard systems

Each addition will follow the principles laid out in the Manifesto.

---

## Closing

If you are curious about building systems that feel more like **villages of programs** than monoliths or services, FileTalk may resonate with you.

Begin with the Manifesto.
Everything else follows from there.

🐾


## Author

FileTalk is authored and maintained by **Lion Kimbro**.

You can follow ongoing thoughts, experiments, and updates on X:  
👉 https://x.com/LionKimbro

