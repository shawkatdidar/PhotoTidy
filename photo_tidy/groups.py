import numpy as np

SIM_STRICT = 0.97       # near-identical: group regardless of time
SIM_DEFAULT = 0.95      # a photo is removable only if this similar to the best shot in its group
WINDOW_S = 30 * 60
BLUR_MAX = 30.0         # Laplacian variance below this is flagged as blurry


def _edges(emb, thresh):
    out = []
    n = len(emb)
    for s in range(0, n, 1024):
        sim = emb[s:s + 1024] @ emb.T
        ii, jj = np.where(sim >= thresh)
        for i, j in zip(ii + s, jj):
            if i < j:
                out.append((int(i), int(j), float(sim[i - s, j])))
    return out


def _score(m, mx):
    sharp = (m["blur"] or 0) / (mx["blur"] or 1)
    res = (m["width"] * m["height"]) / (mx["res"] or 1)
    size = m["size"] / (mx["size"] or 1)
    return 1000 * m["favorite"] + 200 * m["edited"] + 60 * sharp + 20 * res + 10 * size


def analyze(meta, emb, sim=SIM_DEFAULT):
    cand = [i for i, m in enumerate(meta) if not m["screenshot"]]
    sub = emb[cand]
    nbrs = {i: {} for i in range(len(cand))}
    for i, j, s in _edges(sub, sim - 0.03):
        dt = abs(meta[cand[i]]["ts"] - meta[cand[j]]["ts"])
        if s >= SIM_STRICT or dt <= WINDOW_S:
            nbrs[i][j] = s
            nbrs[j][i] = s

    assigned, groups = set(), []
    for i in range(len(cand)):
        if i in assigned or not nbrs[i]:
            continue
        members = [i] + [j for j in nbrs[i] if j not in assigned]
        if len(members) < 2:
            continue
        assigned.update(members)
        ms = [dict(meta[cand[k]], _i=cand[k]) for k in members]
        mx = {"blur": max((m["blur"] or 0) for m in ms), "size": max(m["size"] for m in ms),
              "res": max(m["width"] * m["height"] for m in ms)}
        ms.sort(key=lambda m: -_score(m, mx))
        best = ms[0]
        for m in ms:
            m["_sim"] = float(emb[best["_i"]] @ emb[m["_i"]])
        groups.append({
            "photos": [{"uuid": m["uuid"], "size": m["size"], "favorite": m["favorite"], "edited": m["edited"],
                        "ts": m["ts"], "sim": round(m["_sim"], 3),
                        "suggest_remove": m is not best and not m["favorite"] and m["_sim"] >= sim}
                       for m in ms],
        })
    groups.sort(key=lambda g: -sum(p["size"] for p in g["photos"] if p["suggest_remove"]))
    for n, g in enumerate(groups):
        g["id"] = n

    in_remove = {p["uuid"] for g in groups for p in g["photos"] if p["suggest_remove"]}
    shots = [m for m in meta if m["screenshot"] and not m["favorite"]]
    blurry = [m for m in meta if not m["screenshot"] and not m["favorite"] and m["blur"] is not None
              and m["blur"] < BLUR_MAX and m["uuid"] not in in_remove]
    slim = lambda ms: [{"uuid": m["uuid"], "size": m["size"], "ts": m["ts"], "blur": m["blur"]}
                       for m in sorted(ms, key=lambda m: -m["ts"])]
    return {
        "similar": groups, "screenshots": slim(shots), "blurry": slim(blurry),
        "stats": {"photos": len(meta),
                  "similar_groups": len(groups),
                  "similar_removable": len(in_remove),
                  "similar_bytes": sum(p["size"] for g in groups for p in g["photos"] if p["suggest_remove"]),
                  "screenshots": len(shots), "screenshot_bytes": sum(m["size"] for m in shots),
                  "blurry": len(blurry), "blurry_bytes": sum(m["size"] for m in blurry)},
    }
