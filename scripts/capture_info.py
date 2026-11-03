"""Helpers for reading session metadata out of an Nw_Capture_App zip."""
import json


def capture_started_ms(zf):
    """Epoch ms when the capture session started.

    Prefers summary.json's first_started_ms. Some captures ship without
    summary.json, so fall back to the earliest started_ms across the
    per-request *.meta.json files.
    """
    names = zf.namelist()
    if "summary.json" in names:
        return json.loads(zf.read("summary.json"))["first_started_ms"]
    starts = []
    for n in names:
        if n.endswith(".meta.json"):
            try:
                ms = json.loads(zf.read(n)).get("started_ms")
            except (ValueError, KeyError):
                continue
            if isinstance(ms, int):
                starts.append(ms)
    if not starts:
        raise SystemExit("capture has no summary.json and no started_ms in any meta file")
    return min(starts)
