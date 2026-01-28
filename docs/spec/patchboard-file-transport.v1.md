
# FileTalk File Transport Profile v1

**Version:** v1
**Created:** 2026-01-12
**Authors:** Lion Kimbro, ChatGPT (Wing-Cat)
**Status:** Stable
**Depends on:** FileTalk Core v1

---

## 1. Purpose

The FileTalk File Transport Profile defines how **FileTalk Core messages are transported using the filesystem**.

This profile specifies how messages are represented as files, how they are written and read, and how message lifecycle is managed within directories. It deliberately avoids defining routing, delivery guarantees, or higher-level system behavior.

For most users, this document describes **how FileTalk is first encountered in practice**, and should be read immediately after the FileTalk Core specification.

---

## 2. Transport Model

Under this profile:

* The filesystem is the transport medium
* Each message is represented as a single file
* Messages are exchanged by writing to and polling directories
* Delivery is pull-based and asynchronous

No assumptions are made about processes, threads, machines, or networks. Any system capable of reading and writing files can participate.

---

## 3. Message Representation

Each message file:

* Uses UTF-8 encoding
* Contains exactly one FileTalk Core message
* Is encoded as a JSON object
* Typically uses a `.json` file extension

No additional wrapping, framing, or metadata is required beyond the FileTalk Core message itself.

---

## 4. Filename Requirements

Within a given directory:

* **All message filenames must be unique**
* The transport profile does not prescribe a naming scheme

Implementations may use GUIDs, counters, timestamps, or other strategies to ensure uniqueness. The choice of naming scheme is left to the writer and does not affect transport compliance.

---

## 5. Directory Conventions and Ownership

Two directories are used by convention:

* `OUTBOX` — where a component writes outgoing messages
* `INCOMING` — where a component reads incoming messages

These directories are **conceptually owned** by the component:

* The component owns **writing** to its OUTBOX
* The component owns **reading** from its INCOMING

Other actors may legitimately:

* Write message files into a component’s INCOMING directory
* Read and remove message files from a component’s OUTBOX directory

Ownership here describes responsibility and intent, not filesystem permissions or exclusivity.

---

## 6. Writing Messages

Message writers must follow these rules:

* Messages must be written as JSON files conforming to FileTalk Core v1
* Files **may become visible before writing is complete**
* A message file is considered complete when it can be parsed as valid JSON

Partial visibility is expected and tolerated. A partially written file that fails JSON parsing is treated as incomplete, not erroneous.

### Discouraged Practices

The following practices are discouraged:

* Writing to temporary filenames followed by atomic rename
* Any mechanism that causes a file to appear and then disappear before it can be parsed

A file is considered “ready” when its final closing brace has been written to disk.

---

## 7. Reading Messages

Consumers reading message files must:

* Treat each file as an independent message
* Attempt to parse files as JSON objects
* Skip files that fail to parse and retry them later
* Avoid assuming filesystem order reflects message order

A parse failure is presumed to indicate an incomplete write and is not considered an error.

---

## 8. Ordering Considerations

The file transport provides **no ordering guarantees**.

However:

* Consumers **should attempt** to process messages in timestamp order when practical
* Timestamp-based ordering is best-effort and advisory only

Ordering is a consumer concern, not a transport promise.

---

## 9. Message Lifecycle and Directory Hygiene

Once a message has been fully processed:

* **It must not remain in the directory**
* It must be removed promptly to prevent reprocessing and buildup

Allowed actions include:

* Deleting the message file
* Moving the message file to an archive location

The specific method is implementation-defined, but removal from the directory is mandatory.

---

## 10. Multiple Consumers and Coordination

This profile does not mandate single-consumer semantics.

* Multiple consumers may observe message files
* Exactly one actor is responsible for removing a processed message file
* Consumer coordination is external to the transport profile

This design allows for fan-out, logging, debugging, and monitoring without entangling transport with routing or arbitration logic.

---

## 11. Non-Goals

This transport profile explicitly does **not** define:

* Routing semantics
* Switchboard or Patchboard behavior
* Message transformation
* Deduplication
* Delivery acknowledgments
* Reliability guarantees
* Concurrency control beyond filesystem semantics
* Security, permissions, or access control
* Monitoring, health signaling, or introspection

These concerns are intentionally left to higher-level specifications.

---

## 12. Relationship to Other Specifications

* **FileTalk Core v1** defines the message structure
* **FileTalk File Transport Profile v1** defines how messages move as files
* Routing architectures, health conventions, and introspection mechanisms build on top of these layers and are optional

The file transport profile is the **primary operational companion** to the FileTalk Core specification.

