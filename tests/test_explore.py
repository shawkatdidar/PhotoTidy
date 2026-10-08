import unittest

import numpy as np

from photo_tidy import explore


def photo(uuid, ts, screenshot=False):
    return {"uuid": uuid, "ts": ts, "size": 100, "favorite": False, "screenshot": screenshot}


class ExploreTests(unittest.TestCase):
    def test_nearest_ranks_and_excludes_the_source(self):
        meta = [photo("red", 1), photo("blue", 2), photo("pink", 3)]
        vectors = np.array([[1, 0], [0, 1], [.9, .1]], dtype=np.float32)
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        matches = explore.nearest(meta, vectors, vectors[0], exclude="red")
        self.assertEqual([m["uuid"] for m in matches], ["pink", "blue"])

    def test_collections_use_time_and_visual_scenes_without_losing_photos(self):
        hour = 3600
        meta = [photo(str(i), i * 60) for i in range(6)]
        meta += [photo(str(i), 10 * hour + (i - 6) * 60) for i in range(6, 9)]
        meta.append(photo("screen", 10 * hour + 3 * 60, screenshot=True))
        vectors = np.array([[1, 0, 0]] * 3 + [[0, 1, 0]] * 3 + [[0, 0, 1]] * 3 + [[1, 0, 0]], dtype=np.float32)
        found = explore.collections(meta, vectors)
        self.assertEqual([c["count"] for c in found], [3, 5])  # Timestamp zero is not a dated photo.
        self.assertEqual(found[1]["scene_count"], 1)
        all_ids = [p["uuid"] for c in found for scene in c["scenes"] for p in scene["photos"]]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertNotIn("screen", all_ids)


if __name__ == "__main__":
    unittest.main()
