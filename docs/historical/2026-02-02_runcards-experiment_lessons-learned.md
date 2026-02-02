# Run-Cards Experiment — Lessons Learned  
**Date:** 2026-02-02  
**Written by:** Wing-Cat  
**With direction by:** Lion Kimbro  
**Location:** `filetalk/doc/historical/2026-02-02_runcards-experiment_lessons-learned.md`

---

## Summary

This document records the motivation, evolution, and retirement of the
**Run-Cards** and **Runner** experiment inside the FileTalk ecosystem.

It is written by Wing-Cat, with direct guidance and correction from Lion Kimbro,
who originated the problem, built the systems, and ultimately chose their removal.

The purpose of this document is not to justify the experiment, nor to disown it,
but to preserve the *thinking* that occurred so it does not have to be re-done.

---

## Original Problem: Frustration with CLI Arguments

Lion’s original problem was simple, persistent, and deeply felt:

> Command-line arguments are frustrating.

More specifically:

- Writing argument parsers is repetitive and joyless.
- CLI flags are brittle and annoying to evolve.
- Arguments are a poor medium for structured configuration.
- Arguments are awkward to persist, replay, or edit.
- Every new CLI program repeats the same boilerplate.

Lion articulated the core intuition early:

> Programs want **configuration**, not strings.

This frustration — not ambition for orchestration — is what started the entire line
of work that followed.

---

## First Idea: Pass a JSON Configuration File

Lion proposed a straightforward solution:

> “Why can’t a program just accept a JSON file containing its entire configuration?”

This immediately addressed the pain:

- No argument parsing
- Explicit structure
- Easy validation
- Natural persistence
- Replayable execution

To make this ergonomic, Lion added an additional convention:

- If the program is run “naked” (with no arguments), it prints a **stub JSON
  configuration** and exits.

At this stage, the idea was clean, focused, and directly aligned with the original
problem.

---

## The Invocation Question

The experiment began to strain when a new question arose:

> “Configuration of *what*, exactly?”

The JSON file described everything *except* how the program itself should be run.

Examples of ambiguity that surfaced:

- `foo.exe`
- `python foo.py`
- `python -m foo`
- `perl foo.pl`
- virtual environments
- paths
- OS-specific invocation rules

This invocation information clearly did **not** belong in the configuration JSON —
but it also could not be ignored.

This asymmetry created tension that could not be resolved locally.

---

## Run-Cards and the Turn Toward Indirection

To resolve the mismatch, the idea evolved:

- Introduce **logical program names**
- Bind those names to invocation procedures
- Treat the JSON file as a **frozen function call**
- Introduce a **Runner** to execute these run-cards

At this point, the system became something more than a configuration mechanism.

It began to resemble:
- A language for invocation
- A binding registry
- A runtime
- An execution intermediary

The ideas were not stupid.
They were *heavy*.

Lion described the experience at the time as “getting thick in the woods.”
The complexity was felt before it was fully articulated.

---

## Re-centering on the Actual Pain

At this point, Wing-Cat intervened.

Wing-Cat suggested to Lion that the system had drifted away from the original pain,
and proposed a reset:

> “What if we stop solving invocation and instead eliminate the pain as fast as possible?”

Together, Lion and Wing-Cat identified the true, minimal targets:

1. **Argument parsing and maintenance**
2. **Persistence / having a data store**

Not:
- universal invocation
- frozen calls
- runners
- orchestration layers

This reframing marked the decisive turn.

---

## lionscliapp

From that reframing, Wing-Cat and Lion designed **lionscliapp**.

lionscliapp is a framework for writing CLI programs that:

- Eliminates repeated argument-parsing boilerplate
- Provides structured command dispatch
- Includes persistence as a first-class concern
- Lives *inside* the program rather than wrapping it
- Uses normal CLI invocation without indirection

Key facts:

- It was designed quickly.
- It was implemented quickly.
- It shipped successfully.
- It lives on PyPI.
- It has already simplified multiple real programs.

Most importantly, it solved the *actual problem* without introducing a new
execution model.

Lion is happy with it and intends to continue using and expanding it.

---

## Retirement of Run-Cards and Runner

With lionscliapp in place, Run-Cards and the Runner no longer justified their
existence.

Keeping them would imply:
- A parallel execution model
- Continued cognitive overhead
- A temptation to re-enter a heavier abstraction space

Instead, Lion chose intentional deletion:

- Preserve the lessons
- Remove the artifacts

This was not failure.
It was consolidation.

---

## Lessons Learned

1. **The real problem was CLI argument pain**
   Solving invocation was a drift away from the source of frustration.

2. **JSON configuration is valuable, but invocation is a separate layer**
   Attempting to unify them pulled in unnecessary machinery.

3. **Frozen calls imply a runtime**
   Treating configuration as executable inevitably creates binding,
   naming, and orchestration concerns.

4. **Solve the smallest recurring pain first**
   Removing repeated parser boilerplate delivered immediate value.

5. **Local improvements beat universal abstractions**
   Making every program easier to write mattered more than abstracting
   over all programs.

6. **Some ideas are right, but too heavy for their moment**
   Run-Cards were not dumb — they were simply more than the problem required.

---

## Open Insight: A CLI Valet

Despite retiring Run-Cards, Lion continues to believe something is still wrong
with how intent is delivered to programs.

The intuition remains:

> The front door to a program needs a *valet*.

A future “CLI valet” might:
- Help assemble requests
- Assist in expressing intent succinctly
- Possibly generate or edit configuration files
- Remember past invocations
- Stay out of execution itself

Any future attempt should avoid:
- runners
- frozen execution artifacts
- orchestration layers

The insight remains open, but better bounded.

---

## References

- FileTalk codebase state **before removal of Run-Cards and Runner**  
  Git tag: `boundary/runcards/final`

---

## Closing

This document exists so the thinking survives deletion.

The experiment clarified the problem.
The deletion preserves the clarity.
