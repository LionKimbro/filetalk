## 📐 FileTalk 2025 Epoch 3 "Patchboard" Architecture

version: 1

author: Lion Kimbro &  Wing-Cat

date: 2025-06-05

### 1. 🎯 Purpose of This Document

This document formalizes a specific architectural pattern within the broader **FileTalk 2025** ecosystem — the **Patchboard Paradigm** introduced in Epoch 3. It is not a justification for the system’s existence; that’s the domain of the FileTalk Manifesto. Instead, this document records the **interface expectations, communication style, and design principles** of a modular, dynamically-patchable software ecosystem.

This architectural layer is a **garden within the garden** — an intentionally bounded yet interoperable subsystem. It allows for:

* Dynamic patching of modules, similar to a modular synth (Moog board).
* Experimental wiring and reuse of modules.
* Plug-and-play module replacement.

While FileTalk2025 programs are compatible by default at the file-level, this pattern introduces a slightly more structured convention (e.g., `channel`, `signal`, `timestamp`) that allows for rich and swappable interconnection. Any standard FileTalk2025 module can be **adapted into** or **out of** this ecosystem with simple translation wrappers.

---

### 2. 🧱 Core Principles

* **Single OUTBOX and INCOMING per module.** Every module writes outgoing messages to its designated OUTBOX folder and listens for incoming messages in its INCOMING folder.
* **Plain JSON dictionaries as messages.** All communication is via human-readable `.json` files. See section "Message Format" for details.
* **Externalized routing.** Programs do not route their own messages. Instead, a central Patchboard component dispatches messages to their destinations based on external configuration.
* **Interoperability through convention.** Modules are expected to follow conventions for message structure and file behavior, but may otherwise vary in implementation language or architecture.
* **Replaceability and rewiring.** Any module can be removed, inserted, or rewired without altering the rest of the system.
* **Optional introspectibility.** Modules may expose metadata, status, and descriptive info to allow discovery or diagnostics by other parts of the system. The mechanism for this is by convention — see section "Introspection and Self-Description" for current thinking on status, identity, and capability files.

---

### 3. 🔁 The Flow of Messages

*(Note: See the "Message Format" section for tracing behaviors and conventions.)*

* Each module writes messages to its OUTBOX folder.
* The Patchboard Router watches all OUTBOX folders and uses an external patch map to determine where each message should go.
* It copies each message into the INCOMING folder of one or more recipient modules, typically transforming it in the process, and then deletes the original message from the sender's OUTBOX.
* Messages are processed by polling — receivers scan their INCOMING folder periodically, process complete `.json` files, and delete (or archive) them.
* Messages are treated as **signals** — the sender does not know or care who the recipient is. In fact, there may be no recipient at all; messages without any downstream targets are simply discarded by the Patchboard Router to prevent accumulation.

---

### 4. 📩 Message Format

All messages are JSON dictionaries with the following **core fields**:

* `channel` (str): the logical label or topic of the message (e.g., `start_timer`, `status_update`).
* `signal` (any JSON-compatible value): the payload or instruction — can be a string, dict, list, etc.
* `timestamp` (str): Unix timestamp (seconds since epoch) representing when the message was sent. This must be a string and may include fractional seconds if the message producer can provide them.

#### Optional or Proposed Fields:

* `id` (str): Unique identifier for message tracking. This may be assigned by the originating module or left unset. Message IDs can assist in logging, deduplication, or referencing prior activity.
* `trace` (list): Path or history of modules the message has passed through.

#### Notes:

* All messages must be valid JSON dictionaries.

##### Timestamp Format (Preliminary Notes):

Messages must include a `timestamp` field representing the number of seconds since the Unix epoch. This value must be expressed as a **string**, not an integer or float. If subsecond precision is available, the string may include fractional digits — but message authors must not include more digits than they can meaningfully resolve.

Examples:

* "1749210921" (whole second precision)
* "1749210921.433" (millisecond precision)

This approach ensures clarity, avoids rounding errors, and keeps timestamps compatible across diverse systems and languages.

##### File Reference Format:

All file paths included in messages (e.g., `status_file`, `log_path`) should be **absolute paths**. This avoids ambiguity about the working directory and allows monitoring or restart tools to locate resources unambiguously. If a relative path is ever used, it must be clearly marked and should be accompanied by a base path or contextual information.

##### Trace Field Behavior (Preliminary Notes):

The optional top-level `trace` key enables message tracing. If present, it activates traceability for that message. Modules and the Patchboard Router may inspect this field and append detailed records during the message's journey through the system.

Each trace entry is expected to be a dictionary containing at minimum:

* a **high-resolution timestamp** (preferably with millisecond or finer precision),
* the **name or identifier** of the module or actor appending the trace,
* contextual notes, such as the folder location (e.g., "entered OUTBOX of logger") or transformation performed,
* optional metadata as needed by the writer.

Messages without a `trace` key are treated as untraced. This convention makes tracing emergent and flexible — it can be introduced at any stage, and different modules may trace selectively or differently. The Patchboard Router is expected to honor the presence of `trace` and append both pick-up and drop-off events where applicable.

##### Full Example Message:

Below is a full example message demonstrating all fields:

```json
{
  "channel": "heartbeat",
  "signal": {
    "timestamp": "1749210921.433",
    "next_due": "1749210926.433",
    "status_file": "/srv/commandpad/status.json",
    "restart_cmd": "python3 /srv/commandpad/main.py /srv/commandpad/config.json",
    "notes": "Alive and responsive."
  },
  "timestamp": 1749210921,
  "id": "msg-20250605-00042",
  "trace": [
    {
      "module": "commandpad",
      "location": "OUTBOX",
      "timestamp": "1749210921.433",
      "notes": "Heartbeat issued."
    },
    {
      "module": "patchboard",
      "action": "routed",
      "from": "/srv/commandpad/OUTBOX",
      "to": "/srv/monitor/INCOMING",
      "timestamp": "1749210921.501"
    }
  ]
}
```

---

### 5. 🩺 System Health

System health in the Patchboard architecture refers to the ability of the system and its modules to gracefully detect, respond to, and recover from operational issues. This includes signaling aliveness, handling partially written messages, recognizing dead modules, and enabling recovery strategies. The subsections that follow describe optional conventions and recommended behaviors for participating modules and tools.

#### Heartbeat Messages

Some modules may choose to emit a heartbeat as a regular **message** using the `channel` value `"heartbeat"`. These are written to the module’s standard OUTBOX and routed like any other message. They follow the general message structure and should be processed by whichever component wishes to monitor health.

A heartbeat message should include a `signal` dictionary with the following suggested fields: at regular intervals as a way of signaling that they are alive. This file is optional but recommended for long-running processes that wish to participate in health monitoring.

The heartbeat file should be written in a known location (typically in the module’s `STATUS` or equivalent directory) and should contain a valid JSON dictionary with the following suggested fields:

* `timestamp`: The time of the most recent heartbeat (preferably high-resolution, e.g., Unix time with milliseconds).
* `next_due`: (optional) A timestamp indicating the latest moment by which the next heartbeat should arrive. It is not the expected interval between beats — rather, it represents a deadline. If the current time exceeds `next_due`, the module should be considered unresponsive or degraded.
* `status_file`: (optional) A relative or absolute path to a status file providing more details about the module.
* `restart_cmd`: (optional) A shell command or script line that could be used to restart the module if it becomes unresponsive.
* `notes`: (optional) Freeform text describing context, system state, or other metadata.

Heartbeat files are a plain, observable mechanism that can be monitored by:

* The Patchboard Router itself
* A dedicated heartbeat watcher module
* Dashboards or human operators

Their simplicity supports a wide range of monitoring strategies without requiring central coordination or specialized protocols.

* **Partial Writes:** Programs must skip files that fail to parse and retry them on the next poll. If a file cannot be parsed as a complete JSON dictionary — typically due to being mid-write — it should be skipped for the moment and retried on the next poll cycle.

  In the event that a file remains unparseable for a prolonged period (e.g., no change in size or modification time across several polls), future cleanup strategies may include:

  * Logging the anomaly,
  * Alerting the system or user,
  * Deleting the message after a defined grace period if it's considered abandoned.
    This cleanup behavior may eventually be handled by the Patchboard Router or by a dedicated janitor module.
* **Crash Recovery:** No assumptions are made about uptime. Programs can start, stop, or restart freely.
* **Dead Modules:** Heartbeat messages may be optionally emitted by long-running processes to indicate they’re alive.
* **Monitoring Tools:** System health can be tracked via specialized modules or additional functionality in the Patchboard Router.
* **Routing Failures:** If a destination INCOMING folder is missing or unwritable, the Patchboard must log the failure and may optionally retry.

---

### 6. 🗂️ Recommended Module Directory Layout

This section defines a recommended layout for FileTalk2025-compliant modules. While only an `inbox/` and `outbox/` directory are strictly required for message participation, this structure supports introspection, discoverability, and integration with tools like `filetalk2025.py`.

```
my_module/
├── inbox/               # Required: messages come in here
├── outbox/              # Required: messages go out from here
├── status/              # Optional: exposes status.json, describe.json, etc.
│   ├── status.json
│   ├── errors.jsonl
│   └── describe.json
├── data/                # Optional: internal state files, caches, etc.
│   └── log.jsonl        # Recommended location for JSONL-based event logs
├── config.json          # Required: human-editable configuration file
└── module.json          # Optional: declares participation in FileTalk2025
```

#### module.json (optional)

Modules may include a `module.json` file at the root to declare themselves as FileTalk2025-compatible and offer metadata or structured pointers:

```json
{
  "type": "FileTalk2025-Module",
  "epoch": "3",
  "description": "/srv/my_module/status/describe.json"
}
```

This file is not required but may be helpful for discovery services, or development utilities.

### 7. 🔎 Introspection, Self-Description, and Discovery

Modules may optionally expose files that make them discoverable and transparent to the system:

* `status.json`: Current module status, including health, state, or latest update.
* `errors.json`: Errors accumulated in the execution of the module.
* `describe.json`: Metadata about the module’s identity, capabilities, input/output channels, etc.

These files can be read, polled, or aggregated by other modules (e.g., monitors, dashboards, or orchestration layers).

#### 7.1 🟢 status.json

The `status.json` file provides a snapshot of the module’s current internal condition. It is intended to be machine-readable, optional, and customizable per module, but may follow some basic conventions to enable general tooling and dashboards.

A typical `status.json` might include:

```json
{
  "timestamp": "1749211567.112",
  "state": "running",
  "uptime": "3489.155",
  "interval": "1.0",
  "details": {
    "active_jobs": 3,
    "last_message_channel": "task_completed"
  },
  "diagnostics": {
    "memory_usage_mb": 64.5,
    "thread_count": 5
  }
}
```

* `timestamp` is the last time this file was updated.
* `state` is a short string like "running", "idle", "error", or "awaiting\_input".
* `uptime` measures how long the module has been running in seconds.
* `interval` is the polling interval (in seconds) at which the module checks its inbox.
* `details` is an optional dictionary for module-specific state.
* `diagnostics` is an optional dictionary for health or performance metrics.

#### 7.2 🟡 errors.jsonl

The `errors.jsonl` file is used to record significant error events encountered by a module during its execution. It is stored (conventionally) in the `status/` directory and follows the JSON Lines format: each line is a standalone JSON object.

Each error entry must include:

* `timestamp`: A string value representing when the error occurred (Unix time, with optional fractional seconds).
* `error`: A short human-readable description of the error.

Example entry:

```json
{"timestamp": "1749213321.781", "error": "Failed to open config file: Permission denied"}
```

The file is intended to be append-only. Monitoring tools, dashboards, or log collectors may tail this file to identify issues or observe trends. Modules may impose retention policies or truncate the file periodically to prevent unbounded growth.

#### 7.3 🟡 describe.json

The `describe.json` file provides a structured, outward-facing self-description of the module. It is meant to be readable by orchestration tools, dashboards, or other modules seeking to discover, identify, or replicate the running process. While optional, it is recommended for modules participating in Patchboard-style environments.

A `describe.json` file typically contains the following fields:

```json
{
  "inbox": "/srv/my_module/inbox",
  "outbox": "/srv/my_module/outbox",
  "status_file": "/srv/my_module/status/status.json",
  "errors_file": "/srv/my_module/status/errors.jsonl",
  "describe_file": "/srv/my_module/status/describe.json",
  "config_file": "/srv/my_module/config.json",
  "module_root": "/srv/my_module",
  "entry": "python3 /srv/my_module/main.py /srv/my_module/config.json",
  "title": "My Module Instance",
  "notes": "This is a self-describing module running in the FileTalk 2025 Patchboard ecosystem."
}
```

* `inbox`, `outbox`, `status_file`, `errors_file`, `describe_file`, and `config_file` must be full absolute paths.
* `entry` describes the exact command that could be used to recreate this process, independent of programming language.
* `title` and `notes` are optional, human-readable fields to aid documentation and interface clarity.

This file is not required for FileTalk compliance but is highly encouraged for discoverable, modular systems.

---

### 8. 🧰 Tools, Utilities, and Archetypes

This section sketches useful module types and patterns:

* **Logger** — Appends messages it receives to a JSONL log.
* **Transformer** — Reads messages, alters the `signal` or structure, emits new messages.
* **UI Module** — Connects to a generic control panel, showing status or responding to input.
* **Watcher/Heartbeat Monitor** — Observes status files or expects heartbeats, raises alerts on silence.
* **Snapshotter** — Periodically emits `status.json`-like snapshots of a system’s internal state.
* **Muxer/Demuxer** — Combines or splits channels based on tags or message contents.

These modules can be built incrementally and inserted at any point in the system.

---

### 9. 🔮 Future Extensions

Ideas for evolution of the system:

* **Live Patching:** Allow modules or external tools to send messages that modify the patch map dynamically.
* **Graphical Patchboard Editors:** Visual UI to rewire module connections in real time.
* **Debug Routers:** Tap into signal flows, inspect and replay messages.
* **Validation Layers:** Ensure message formats conform to contracts or expected schemas.
* **Message Playback and Simulation:** Replay prior message flows for debugging or prototyping.

### &#x20;10. 🧭 Related Works and Comparisons

This section surveys existing architectures, ecosystems, or tools that share philosophical or structural similarities with the FileTalk 2025 system, or the FileTalk 2025 Patchboard Paradigm. The goal is not only to **compare** but to **locate this architecture historically and conceptually** — and to explore whether existing tools could enhance or replace parts of the system.

10.1 🧪 Similar Concepts in the Wild

* **Node-RED** – Visual flow-based programming for IoT and automation.
* **Pure Data / Max/MSP** – Visual patch-based environments for sound and control signals.
* **Unix Philosophy + shell scripting** – Composable programs connected via pipes and files.
* **ZeroMQ** – A flexible, socket-based message-passing library with pub/sub, pipeline, and RPC patterns.
* **Redis Streams / Kafka / MQTT** – Centralized or distributed message brokers with persistence and subscriptions.
* **Dataflow Programming Environments** – NoFlo, Apache NiFi, Flowhub.

10.2 ⚖️ Comparison Points

| FeatureFileTalk PatchboardRelated Systems (e.g., Node-RED, ZeroMQ) |                                |                                |
| ------------------------------------------------------------------ | ------------------------------ | ------------------------------ |
| Routing Mechanism                                                  | Filesystem-based, externalized | Socket/event bus-based         |
| Message Format                                                     | JSON files, append-only        | Binary or protocol-specific    |
| Discoverability                                                    | Via status/describe.json       | Tool-specific                  |
| Modularity                                                         | Directory + config conventions | Often visual or code-based     |
| Debuggability                                                      | Human-readable traces + logs   | Varies                         |
| Infrastructure Requirements                                        | None                           | Often requires runtime daemons |
| Philosophy                                                         | Unix + modular synths + JSON   | Varies                         |

#### 10.3 🧭 What Makes This Different?

What makes the FileTalk 2025 Patchboard paradigm **distinct**:

* **Files as the communication fabric.** No sockets, no servers, no daemons — just JSON and the filesystem.
* **Extremely low barrier to entry.** Any language, any script, any system that can write/read files can participate.
* **Emergent introspection.** Without requiring central registration, modules can self-describe and expose status.
* **Moog-inspired plug-and-play.** Patching modules together is like routing signal cables — simple, visible, and experiment-friendly.
* **Crash resilience through logs and heartbeat signaling.**
* **No vendor lock-in, no infrastructure assumptions.** Entirely local and composable.

---

### 📘 Appendix A: Glossary

#### 🧩 Modules

* **Patchboard Router** — The central coordinating module that watches all OUTBOX folders and routes messages to their designated INCOMING folders based on a dynamic patch map.
* **Command Pad** — A message-emitting GUI module written with tkinter. It features a text input area (`Entry`) and a text output area (`Text`). Any text entered is emitted on a designated channel; incoming messages on a corresponding channel are displayed in the output. It also supports adjustable title and label elements via control channels.&#x20;

#### 📂 Directories & Files

* **OUTBOX** — A folder where a module writes its outgoing messages. Messages here are picked up and routed by the Patchboard Router.
* **INCOMING** — A folder where a module receives incoming messages routed by the Patchboard Router.
* **status.json** — A JSON file that optionally represents the current status of a module, including any diagnostic or operational state.
* **describe.json** — A metadata file optionally provided by a module to describe its role, identity, capabilities, and communication conventions.

#### ✉️ Message Anatomy

* **Message** — The fundamental unit of communication in FileTalk 2025. A message is a JSON dictionary containing at minimum a `channel`, a `signal`, and a `timestamp`. Messages are written to OUTBOX folders and routed to INCOMING folders by the Patchboard Router. Optional fields such as `id` and `trace` may enrich the message with unique identity or delivery history.
* **channel** — A label indicating the purpose or type of the message (e.g., "start\_timer").
* **signal** — The core data or payload of the message.
* **timestamp** — A required string field on all messages denoting seconds since the Unix epoch. May include fractional seconds.
* **id** — An optional identifier string used for message tracking.
* **trace** — A message field used to record the history of a message’s traversal through modules and transformations. Each trace entry typically includes timestamp, actor, and contextual metadata.
* **Heartbeat Message** — A message with channel `"heartbeat"` that is periodically emitted by a module to signal liveness. Routed like any other message.

#### 🧭 Architectural Concepts

* **Module** — A self-contained program that participates in the FileTalk ecosystem by reading messages from its INCOMING folder and writing messages to its OUTBOX folder. Modules may also expose optional status or description files, and can be dynamically rewired within the Patchboard architecture.
* **Patchboard Paradigm** — The architectural pattern introduced in Epoch 3 of FileTalk 2025, enabling modular programs to interoperate through OUTBOX and INCOMING folders routed by a shared Patchboard.
* **System Health** — The collective term for resilience strategies within the ecosystem, including heartbeats, file monitoring, recovery patterns, and health diagnostics. Modules may emit heartbeat messages and maintain status files to support observability.
* **Traceability** — The ability for messages to carry a structured history of their movement and transformation across modules. Enabled by the `trace` field, this supports debugging, auditing, and visualization of message flow.
* **Routing** — The process by which the Patchboard Router delivers messages from one module’s OUTBOX to one or more INCOMING folders. Routing behavior is governed by a dynamic patch map and can include message transformation or duplication.

---

### 📙 Appendix B: Questions to Come Back To

* Should it be possible to request discoverability info with a specific channel call to a module's inbox?
  → Perhaps the message could include a `"target_path"` field, and the module would respond by writing its `describe.json` (or similar) to that location instead of replying with a routed message. This would allow local or filesystem-based tools to "ping" modules without needing to monitor incoming messages.

Let this document serve as the evolving architectural map of the Patchboard Paradigm. The implementation will follow — but this is the pattern we return to, the shape we agree upon, the garden we cultivate.

🐾
