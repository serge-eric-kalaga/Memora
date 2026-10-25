import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
names = {
    "turbo": "accuracy-turbo-reserve-v3.json",
    "parakeet": "accuracy-routed-fr-parakeet-reserve-v3.json",
    "full": "accuracy-full-fr-reserve-v3.json",
}
data = {n: json.loads((root / "agents/logs" / p).read_text()) for n, p in names.items()}
keys = {r["id"] for r in data["full"]["results"]}
rows = {
    n: {r["id"]: r for r in d["results"] if r["id"] in keys} for n, d in data.items()
}
assert all(set(rs) == keys for rs in rows.values())
for ident in keys:
    base = rows["turbo"][ident]
    for name in names:
        assert (
            rows[name][ident]["sha256"] == base["sha256"]
            and rows[name][ident]["reference"] == base["reference"]
        )
output = {
    "scope": "Existing FR reserveV3 reused, not a new holdout;24FRcases+2negatives",
    "inputs": {
        n: {
            "path": names[n],
            "sha256": hashlib.sha256(
                (root / "agents/logs" / names[n]).read_bytes()
            ).hexdigest(),
        }
        for n in names
    },
    "results": {},
    "differences": [],
}
for name, rs in rows.items():
    fr = [r for r in rs.values() if r["language"] == "fr"]
    profiles = {}
    for profile in [
        "all",
        "clean",
        "noise20",
        "noise10",
        "reverb",
        "opus32",
        "quiet24",
    ]:
        selected = [r for r in fr if profile == "all" or r["profile"] == profile]
        n = sum(r["scores"]["numeric"]["wer"]["n"] for r in selected)
        err = sum(r["scores"]["numeric"]["wer"]["errors"] for r in selected)
        profiles[profile] = {
            "n": n,
            "errors": err,
            "rate": err / n,
            "critical_pass": sum(
                x["pass"] for r in selected for x in r["critical_results"]
            ),
            "critical_total": sum(len(r["critical_results"]) for r in selected),
        }
    output["results"][name] = {
        "profiles": profiles,
        "elapsed": sum(r["elapsed"] for r in rs.values()),
        "negatives_no_text": all(
            not r["hypothesis"].strip()
            for r in rs.values()
            if r["profile"] == "negative"
        ),
        "peak_rss_gib": max(
            r["memory_after"]["process_peak_rss_bytes"] for r in rs.values()
        )
        / 1024**3,
    }
    for profile, score in profiles.items():
        print(name, profile, score)
    print(
        "time/memory",
        output["results"][name]["elapsed"],
        output["results"][name]["peak_rss_gib"],
    )
for ident in sorted(keys):
    if rows["full"][ident]["language"] != "fr":
        continue
    output["differences"].append(
        {
            "id": ident,
            "reference": rows["full"][ident]["reference"],
            "hypotheses": {name: rs[ident]["hypothesis"] for name, rs in rows.items()},
            "critical": {
                name: rs[ident]["critical_results"] for name, rs in rows.items()
            },
        }
    )
(root / "agents/logs/accuracy-full-fr-reserve-v3-comparison.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2)
)
