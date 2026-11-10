"""Size guidance from the garment's own size chart, not from the try-on image.

For each size, ease = garment measurement - body measurement (cm). Each garment says what ease it is
designed for (a wrap dress sits close, a denim jacket is roomy). We pick the size whose ease is inside
that range for the most measurements, and say how sure we are and why.
"""

LABELS = {"chest": "Chest", "waist": "Waist", "hip": "Hip"}


def recommend(garment, body):
    body = {k: float(v) for k, v in (body or {}).items() if k in LABELS and v not in (None, "") and float(v) > 0}
    used = [m for m in LABELS if m in body and m in garment["ease"]]
    if "chest" not in used:
        return {"size": None, "confidence": "none", "rows": [],
                "why": "Add at least your chest measurement and we'll check every size against the size chart."}

    def rows_for(size):
        out = []
        for m in used:
            lo, hi = garment["ease"][m]
            ease = garment["chart"][size][m] - body[m]
            state = "tight" if ease < lo else "loose" if ease > hi else "as designed"
            off = lo - ease if ease < lo else ease - hi if ease > hi else 0.0
            out.append({"measure": LABELS[m], "body": body[m], "garment": garment["chart"][size][m],
                        "ease": round(ease, 1), "range": [lo, hi], "state": state, "off": round(off, 1)})
        return out

    sizes = list(garment["chart"])
    scored = []
    for i, s in enumerate(sizes):
        r = rows_for(s)
        # fewest measurements out of range, then smallest total miss; a tight fit is worse than a loose one
        scored.append((sum(x["state"] != "as designed" for x in r),
                       sum(x["off"] * (1.5 if x["state"] == "tight" else 1) for x in r), i, s, r))
    misses, _, _, size, rows = min(scored)
    if misses == 0:
        confidence = "high" if len(used) >= 2 else "medium"
        why = (f"{size} matches the size chart for all {len(used)} measurements you gave."
               if len(used) >= 2 else f"{size} matches on chest. Add waist{' or hip' if 'hip' in garment['ease'] else ''} to be surer.")
    else:
        confidence = "low"
        bad = ", ".join(f"{x['measure'].lower()} would be {x['state']}" for x in rows if x["state"] != "as designed")
        why = f"No size fits every measurement. {size} is closest, but your {bad}."
        edge = sizes[-1] if any(x["state"] == "tight" for x in rows) else sizes[0]
        if size == edge:
            why += f" This item only goes from {sizes[0]} to {sizes[-1]}; we'd rather say so than guess."
    return {"size": size, "confidence": confidence, "rows": rows, "why": why}


if __name__ == "__main__":
    tee = {"ease": {"chest": [6, 14], "waist": [8, 20]},
           "chart": {"S": {"chest": 94, "waist": 90}, "M": {"chest": 100, "waist": 96}, "L": {"chest": 106, "waist": 102}}}
    assert recommend(tee, {"chest": 90, "waist": 82})["size"] == "M"
    assert recommend(tee, {"chest": 90, "waist": 82})["confidence"] == "high"
    assert recommend(tee, {})["confidence"] == "none"
    assert recommend(tee, {"chest": 110, "waist": 70})["confidence"] == "low"
    print("ok")
