import json
import textwrap

from . import core


LINE = "─" * 78


def _wrap(s, indent=4, width=74):
    pad = " " * indent
    return "\n".join(pad + line for line in textwrap.wrap(str(s), width))


def _kv(label, value, indent=2):
    pad = " " * indent
    return f"{pad}{label:14}: {value}"


def format_summary(summary=None):
    """
    Returns a deluxe, human-friendly string representation of a
    FileTalk program invocation summary.
    """

    summary = summary or core.g["summary"]

    out = []

    if not summary or not isinstance(summary, dict):
        return "<< invalid or empty summary >>"

    out.append("")
    out.append(LINE)
    out.append(" FileTalk Process Summary")
    out.append(LINE)

    out.append(_kv("type", summary.get("type", "?")))

    std = summary.get("STANDARD", {})
    cust = summary.get("CUSTOM", {})

    # -------------------------
    # STANDARD
    # -------------------------

    if std:
        out.append("")
        out.append(" STANDARD")
        out.append(" " + "-" * 76)

        for k in [
            "request-id",
            "status",
            "complete",
            "exit-code",
            "timestamp-utc",
        ]:
            if k in std:
                out.append(_kv(k, std[k]))

        if "invocation" in std:
            out.append("")
            out.append("  invocation:")
            inv_txt = json.dumps(std["invocation"], indent=2)
            for line in inv_txt.splitlines():
                out.append("    " + line)

    # -------------------------
    # SIMPLE EVENTS
    # -------------------------

    if "events" in std and std["events"]:
        out.append("")
        out.append(" EVENTS (narrative)")
        out.append(" " + "-" * 76)

        for i, msg in enumerate(std["events"], 1):
            out.append("")
            out.append(f"  [{i}]")
            out.extend(_wrap(msg, indent=4).splitlines())

    # -------------------------
    # COMPLEX EVENTS
    # -------------------------

    if "complex-events" in std and std["complex-events"]:
        out.append("")
        out.append(" EVENTS (structured)")
        out.append(" " + "-" * 76)

        for i, ev in enumerate(std["complex-events"], 1):
            out.append("")
            out.append(f"  [{i}] {ev.get('kind', '?')}  ({ev.get('level', '?')})")

            if "timestamp-utc" in ev:
                out.append(_kv("time", ev["timestamp-utc"], indent=4))

            if ev.get("tags"):
                out.append(_kv("tags", ", ".join(ev["tags"]), indent=4))

            if ev.get("msg"):
                out.append("    message:")
                out.extend(_wrap(ev["msg"], indent=6).splitlines())

            if ev.get("data"):
                out.append("    data:")
                data_txt = json.dumps(ev["data"], indent=2)
                for line in data_txt.splitlines():
                    out.append("      " + line)

    # -------------------------
    # CUSTOM
    # -------------------------

    if cust:
        out.append("")
        out.append(" CUSTOM (program output)")
        out.append(" " + "-" * 76)

        cust_txt = json.dumps(cust, indent=2)
        for line in cust_txt.splitlines():
            out.append("  " + line)

    out.append("")
    out.append(LINE)
    out.append("")

    return "\n".join(out)


def print_summary(summary=None):
    """
    Pretty-prints a FileTalk program invocation summary to stdout.
    """
    print(format_summary(summary))
