
# 🛠️ Program Invocation in a FileTalk World

### Kickers, Specifications, and the Shape of Execution

**Author:** Lion Kimbro & Wing-Kat
**Context:** FileTalk2025 Architecture Notes

---

## 🌊 From “Running Programs” to “Submitting Requests”

In most software traditions, programs are things you *run*.

You type a command.
You pass flags.
You hope you remembered the right combination.
Then the process vanishes, leaving behind only its exit code and whatever it printed.

In FileTalk, this mental model shifts.

Programs are not things you merely *run*.
They are **machines that accept structured requests and produce structured results**.

Execution is not a ritual performed at the command line.
It is the act of **submitting a specification to a machine**.

That specification is JSON.

JSON is not a convenience here — it is the **canonical interface**.

All invocation paths ultimately construct the same thing:

> a structured, machine-readable request describing what is to be done.

---

## 🧾 The JSON Specification as the True Interface

Every FileTalk-compatible program is defined by the shape of the request it accepts.

Not by:

* flags
* switches
* positional arguments

But by:

* fields
* types
* defaults
* nested structure

This request object may describe:

* input paths
* output destinations
* modes of operation
* thresholds
* formatting rules
* policy decisions

It is:

* serializable
* archivable
* diffable
* replayable

A run is no longer an ephemeral act.
It becomes a **documented decision**.

This allows:

* experiments to be reproduced
* pipelines to be versioned
* GUIs to be generated
* audits to be performed

The JSON specification is the *grammar of the machine*.

---

## 🚀 Kickers: Interfaces That Construct Specifications

Humans still need ways to tell machines what they want.

But in FileTalk, interfaces no longer *are* the program.
They are merely **kickers** — tools that build and submit JSON requests to the real machine.

There may be many kickers for one program:

* command-line kickers
* GUI kickers
* automated orchestration kickers
* scripting kickers

All of them produce the same thing:

> a JSON execution specification.

They differ only in **how that specification is constructed**.

---

## ⌨️ CLI as Shorthand Specification Builder

People still love command lines — and rightly so.

They are fast.
They are scriptable.
They are composable.

In the FileTalk worldview, the command line becomes:

> a compact, human-friendly syntax for building JSON specifications.

So instead of thinking:

> “This command line *is* the interface.”

We think:

> “This command line *compiles into* the interface.”

The CLI parser is now a **front-end compiler**:

* tokenize arguments
* normalize values
* apply defaults
* validate structure
* emit JSON spec

Then:

* submit that spec to the machine
* or save it as a reusable configuration file
* or pass it into a FileTalk message folder

The program does not fundamentally care whether the JSON came from:

* a CLI
* a GUI
* a saved file
* another program

Only that the request is valid.

---

## 🖥️ GUI as Visual Specification Constructor

Graphical interfaces fit naturally into this same architecture.

A GUI is not a separate mode of operation.
It is not “special support”.

It is simply another kicker.

The GUI:

* reads the program’s declared input schema
* constructs widgets for each parameter
* allows interactive configuration
* assembles a JSON request

When the user presses **Run**, the GUI:

> submits the same specification the CLI would have produced.

This creates powerful symmetry:

* CLI and GUI are peers
* both are optional
* neither defines the program’s semantics

The *program* is the machine.
Interfaces are only how requests are composed.

---

## 📜 Self-Describing Programs

To support this ecosystem, FileTalk programs can expose:

> the specification of the specification.

When run without arguments — or when explicitly asked — a program may emit:

* the expected JSON structure
* field descriptions
* defaults
* allowed values
* UI hints

This allows:

* automatic UI generation
* validation tools
* documentation builders
* orchestration systems

A program becomes a **self-describing machine**.

Not just executable — but explainable.

---

## 📦 Output: Two Kinds of Results

In traditional tools, everything goes to stdout and stderr.

In FileTalk, output is separated into two conceptual streams:

### 1. Genuine Output (Primary Artifacts)

This is the work product:

* generated files
* transformed datasets
* indexes
* reports
* images

These are:

* domain-specific
* meaningful beyond execution
* often persisted long-term

They belong to the program’s *function*.

---

### 2. Execution Summaries (Operational Narrative)

Separately, programs emit **summary files** that describe what happened:

* success or failure
* warnings
* errors
* metrics
* timestamps
* environment notes

These are not the work product.
They are the **story of the run**.

They answer questions like:

* Did it work?
* What went wrong?
* What was skipped?
* How long did it take?

They are structured JSON, suitable for:

* dashboards
* logs
* orchestration tools
* audit trails

In FileTalk terms:

> Genuine output is what the machine *made*.
> Summary output is what the machine *experienced*.

Both matter.
They should not be mixed.

---

## 🧩 Invocation as Just Another Message

Once invocation is treated as JSON, it becomes compatible with FileTalk’s core mechanism:

> sending messages by writing files.

A kicker does not have to run the program directly.

It can instead:

* write the spec to the program’s `input/` folder
* where the program will process it on its next poll

This unifies:

* interactive use
* automation
* scheduling
* remote triggering

All without:

* RPC
* sockets
* servers
* orchestration frameworks

Just files.
Just messages.
Just machines listening to mailboxes.

---

## 🧵 Programs as Machines in a Fabric

In this model, a program is no longer:

> something you launch and forget.

It is:

> a persistent machine that accepts structured requests, produces structured results, and publishes structured state.

Invocation becomes:

* composable
* inspectable
* interceptable

A control panel can submit requests.
A script can submit requests.
Another program can submit requests.

Everything speaks the same language:

> JSON in folders.

This is not a framework.
It is an ecology.

---

## 🌱 Why This Matters

This architecture restores something that modern software quietly lost:

* continuity
* inspectability
* human-scale systems

Instead of black-box services and hidden pipelines, we get:

* visible messages
* persistent requests
* replayable runs
* understandable failure modes

And we regain something else, too:

> the joy of patching systems together.

Not by rewriting everything,
but by **letting small machines speak plainly to one another**.

---

## ✨ Closing

FileTalk began as a philosophy of communication.
But communication implies intention.
And intention requires a language of requests.

By making JSON specifications the heart of invocation:

* programs become machines
* interfaces become helpers
* execution becomes history
* systems become legible

The command line still has its place.
So does the GUI.

But neither is the center.

The center is the machine —
and the structured request that tells it what to do.

Let tools be small.
Let requests be explicit.
Let interfaces be many.
Let machines be readable.

Let the village of programs speak in files —
and let every act of execution leave a trail that can be understood, replayed, and loved.

