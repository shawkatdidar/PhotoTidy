"""Search and virtual scene/event collections from cached photo embeddings."""
import numpy as np

EVENT_GAP_SECONDS = 6 * 60 * 60
MAX_EVENT_PHOTOS = 180
SCENE_SIMILARITY = 0.82
SEARCH_LIMIT = 80
NEARBY_LIMIT = 60


def photo_data(item, score=None):
    photo = {key: item[key] for key in ("uuid", "ts", "size", "favorite")}
    if score is not None:
        photo["score"] = round(float(score), 4)
    return photo


def nearest(meta, embeddings, vector, limit=SEARCH_LIMIT, exclude=None):
    """Return closest indexed photos; scores are ranks, not probabilities."""
    if not len(meta):
        return []
    query = np.asarray(vector, dtype=np.float32)
    if query.shape != (embeddings.shape[1],):
        raise ValueError("The model returned an incompatible embedding")
    query /= np.linalg.norm(query) + 1e-9
    scores = embeddings @ query
    order = np.argsort(-scores, kind="stable")
    matches = []
    for i in order:
        if meta[i]["uuid"] != exclude:
            matches.append(photo_data(meta[i], scores[i]))
            if len(matches) >= limit:
                break
    return matches


def nearby(meta, embeddings, uuid, limit=NEARBY_LIMIT):
    by_id = {item["uuid"]: i for i, item in enumerate(meta)}
    if uuid not in by_id:
        raise ValueError("That photo has not been indexed yet")
    source = by_id[uuid]
    return {
        "source": photo_data(meta[source]),
        "photos": nearest(meta, embeddings, embeddings[source], limit, exclude=uuid),
    }


def _scenes(event, meta, embeddings):
    clusters, sums = [], []
    for i in event:
        similarities = [float(embeddings[i] @ (s / (np.linalg.norm(s) + 1e-9))) for s in sums]
        best = int(np.argmax(similarities)) if similarities else -1
        if best >= 0 and similarities[best] >= SCENE_SIMILARITY:
            clusters[best].append(i)
            sums[best] += embeddings[i]
        else:
            clusters.append([i])
            sums.append(embeddings[i].copy())

    scenes = [cluster for cluster in clusters if len(cluster) >= 3]
    other = [i for cluster in clusters if len(cluster) < 3 for i in cluster]
    scenes.sort(key=lambda cluster: meta[cluster[0]]["ts"])
    result = [{"kind": "scene", "photos": [photo_data(meta[i]) for i in cluster]} for cluster in scenes]
    if other:
        other.sort(key=lambda i: meta[i]["ts"])
        result.append({"kind": "other", "photos": [photo_data(meta[i]) for i in other]})
    return result, len(scenes)


def collections(meta, embeddings):
    """Split the timeline into events, then group visually related shots in each."""
    indexed = sorted((i for i, item in enumerate(meta) if not item["screenshot"] and item["ts"] > 0),
                     key=lambda i: meta[i]["ts"])
    events, event = [], []
    for i in indexed:
        if event and (meta[i]["ts"] - meta[event[-1]]["ts"] > EVENT_GAP_SECONDS
                      or len(event) >= MAX_EVENT_PHOTOS):
            events.append(event)
            event = []
        event.append(i)
    if event:
        events.append(event)

    result = []
    for event in events:
        if len(event) < 3:
            continue
        scenes, count = _scenes(event, meta, embeddings)
        result.append({
            "id": meta[event[0]]["uuid"],
            "start": meta[event[0]]["ts"],
            "end": meta[event[-1]]["ts"],
            "count": len(event),
            "scene_count": count,
            "covers": [meta[i]["uuid"] for i in event[:3]],
            "scenes": scenes,
        })
    result.sort(key=lambda collection: -collection["start"])
    return result
