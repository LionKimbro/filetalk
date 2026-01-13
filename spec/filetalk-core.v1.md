
# FileTalk Core v1

**FileTalk Core Message Specification**

**Version:** v1
**Created:** 2026-01-12
**Authors:** Lion Kimbro, ChatGPT (Wing-Cat)
**Status:** Stable
**Scope:** Epoch-agnostic

---

## 1. Purpose

FileTalk Core defines the **minimal, irreducible message structure** shared by all FileTalk systems, across all epochs, transports, and execution environments.

This document intentionally specifies *only* what is required for messages to exist as FileTalk messages. All concerns related to routing, transport, delivery guarantees, health signaling, introspection, or infrastructure are explicitly excluded and delegated to auxiliary specifications.

The goal of FileTalk Core is not completeness, but **stability**.

---

## 2. Core Message Structure

A FileTalk Core message is a JSON object with exactly three required fields:

* `channel`
* `signal`
* `timestamp`

No other fields are required by the core specification.

### 2.1 `channel`

The `channel` field is a string used as an **opaque routing identifier**.

Channels are not semantic labels, topics, or classifications. They do not carry meaning, intent, or destination semantics. Components emitting or receiving messages must not interpret the meaning of a channel value.

Routing logic — including delivery, fan-out, filtering, or channel renaming — is performed entirely by **external mechanisms**, outside the scope of FileTalk Core.

### 2.2 `signal`

The `signal` field contains the **payload** of the message.

All semantic meaning of a message resides in the signal. The signal may be any JSON-compatible value, including objects, arrays, strings, numbers, booleans, or null.

FileTalk Core imposes no constraints on the structure or interpretation of the signal.

### 2.3 `timestamp`

The `timestamp` field is a string representing the number of seconds since the Unix epoch.

Fractional seconds are permitted and, when present, must be represented as a decimal fraction using a period (`.`) as the separator. No fixed precision is required; message producers must not claim more precision than they can meaningfully provide.

Examples of valid timestamps:

* `"1736726400"`
* `"1736726400.5"`
* `"1736726400.527381"`

The timestamp is informational and carries no ordering or delivery guarantees within the core specification.

---

## 3. Example Message

```json
{
  "channel": "signal-out",
  "signal": {
    "command": "start",
    "parameters": {
      "duration": 5
    }
  },
  "timestamp": "1736726400.527381"
}
```

This example demonstrates:

* A channel used purely as a routing identifier
* A structured signal carrying all semantic meaning
* A timestamp including fractional seconds

---

## 4. Design Principles

### 4.1 Transport-Agnosticism

FileTalk Core deliberately avoids defining how messages are transported.

Messages may be conveyed via filesystem operations, in-memory queues, inter-process communication, network transports, or other mechanisms. The same message structure applies regardless of transport.

This allows components to operate unchanged across different execution environments, and enables systems to evolve from local experimentation to distributed deployment without architectural fracture.

### 4.2 Opaque Routing Channels

Channels are treated as **opaque identifiers**, not semantic constructs.

By preventing components from reasoning about routing topology or destination meaning, FileTalk Core ensures that delivery configuration remains external, mechanical, and patchable. This separation avoids entangling business logic with infrastructure concerns.

### 4.3 Messages Over Mechanisms

FileTalk prioritizes stable message shape over fixed delivery machinery.

By minimizing the core definition and resisting infrastructure commitments, FileTalk allows higher-level systems to innovate freely while retaining a common communicative substrate.

---

## 5. Non-Goals

FileTalk Core explicitly does **not** define:

* Routing semantics
* Transport mechanisms
* Filesystem conventions
* In-memory bus behavior
* Delivery guarantees
* Ordering guarantees
* Reliability or retry semantics
* Message identifiers
* Tracing or provenance
* Heartbeats or liveness signaling
* Introspection or self-description
* Security, authentication, or authorization

These concerns may be addressed by auxiliary specifications.

---

## 6. Relationship to Other Specifications

FileTalk Core is designed to be used in conjunction with additional specifications that build upon it.

### 6.1 File Transport Profile (Primary)

The **File Transport Profile** defines how FileTalk Core messages are serialized, written, observed, and consumed as files on a filesystem. It specifies conventions for atomic writes, polling, partial-write handling, and retry behavior.

For most users and most deployments, the File Transport Profile is the **primary and canonical way FileTalk is first encountered**, and should be read immediately after this document.

### 6.2 Additional Specifications (Secondary and Tertiary)

Other specifications may define higher-level behavior, including:

* Routing architectures (e.g., Patchboard-style systems)
* Health and monitoring conventions
* Introspection and discovery mechanisms
* Debugging, tracing, or visualization layers

These specifications are optional and situational. They build upon FileTalk Core and, where applicable, the File Transport Profile, but are not required for basic participation.

---

## 7. Authority and Versioning

The machine-readable JSON specification (`filetalk-core.v1.json`) is the **normative source of truth** for FileTalk Core.

This Markdown document exists to explain intent, boundaries, and usage. In the event of disagreement, the JSON specification is authoritative.

Future versions of FileTalk Core are expected to evolve conservatively, preserving backward compatibility by maintaining the required fields defined here.

