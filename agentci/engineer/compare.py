"""Compare candidate vs baseline per-case results. Baseline is fetched THROUGH Phoenix MCP."""


def _index(rows: list[dict]) -> dict:
    return {r["id"]: r for r in rows}


def compute_flips(baseline: list[dict], candidate: list[dict]) -> dict:
    """Return {'pass_to_fail': [ids], 'fail_to_pass': [ids]} over ids present in both."""
    b, c = _index(baseline), _index(candidate)
    ptf, ftp = [], []
    for cid in sorted(b.keys() & c.keys()):
        if b[cid]["passed"] and not c[cid]["passed"]:
            ptf.append(cid)
        elif not b[cid]["passed"] and c[cid]["passed"]:
            ftp.append(cid)
    return {"pass_to_fail": ptf, "fail_to_pass": ftp}


def is_regression(baseline: list[dict], candidate: list[dict]) -> bool:
    """A candidate is flagged iff >=1 TUNE-partition pass->fail flip (D10)."""
    tune_base = [r for r in baseline if r["split"] == "tune"]
    tune_cand = [r for r in candidate if r["split"] == "tune"]
    return len(compute_flips(tune_base, tune_cand)["pass_to_fail"]) > 0
