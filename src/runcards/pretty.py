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


def format_reportcard(reportcard=None):
    """
    Returns a deluxe, human-friendly string representation of a
    Report Card.
    """

    reportcard = reportcard or core.g["report-card"]

    out = []

    if not reportcard or not isinstance(reportcard, dict):
        return "<< invalid or empty report card >>"

    out.append("")
    out.append(LINE)
    out.append("Report Card")
    out.append(LINE)

    out.append(_kv("type", reportcard.get("type", "?")))

    std = reportcard.get("STANDARD", {})
    cust = reportcard.get("CUSTOM", {})

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

        if "job-card" in std:
            out.append("")
            out.append("  job card:")
            jobcard_txt = json.dumps(std["job-card"], indent=2)
            for line in jobcard_txt.splitlines():
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


def print_reportcard(reportcard=None):
    """
    Pretty-prints a Report Card to stdout.
    """
    print(format_reportcard(reportcard))
