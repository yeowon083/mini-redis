"""충돌과 확장 뒤에도 키와 값이 보존되는지 검증한다."""

import unittest

from mini_redis.structures.hash_map import (
    CAPACITY_GROWTH_FACTOR,
    INITIAL_CAPACITY,
    MAX_LOAD_FACTOR,
    HashMap,
)


class HashMapTests(unittest.TestCase):
    """충돌과 재해싱을 포함하여 저장·조회·삭제를 검증한다."""

    def test_missing_key_in_empty_map(self) -> None:
        mapping = HashMap()
        self.assertIsNone(mapping.get("missing"))
        self.assertIsNone(mapping.remove("missing"))
        self.assertFalse(mapping.contains("missing"))
        self.assertEqual(mapping.keys(), [])
        self.assertEqual(mapping.size(), 0)

    def test_overwrite_keeps_size_and_accepts_false_values(self) -> None:
        mapping = HashMap()
        for value in ("old", "", 0, False):
            mapping.put("key", value)
            self.assertEqual(mapping.get("key"), value)
            self.assertTrue(mapping.contains("key"))
            self.assertEqual(mapping.size(), 1)
        self.assertEqual(mapping.keys(), ["key"])

    def test_none_is_rejected_without_modifying_existing_value(self) -> None:
        mapping = HashMap()
        mapping.put("key", "keep")
        for key in ("key", "new"):
            with self.assertRaises(ValueError):
                mapping.put(key, None)
        self.assertEqual(mapping.size(), 1)
        self.assertEqual(mapping.get("key"), "keep")
        self.assertFalse(mapping.contains("new"))

    def test_collision_chain_survives_overwrite_and_all_deletion_positions(self) -> None:
        mapping = HashMap()
        # 초기 8개 버킷에서 아래 키들은 같은 버킷에 들어간다.
        collision_keys = ["a", "i", "q", "y"]
        first_index = mapping._bucket_index(collision_keys[0])
        for key in collision_keys:
            self.assertEqual(mapping._bucket_index(key), first_index)
            mapping.put(key, key.upper())
        mapping.put("q", "updated")
        self.assertEqual(mapping.get("q"), "updated")
        for key in ("i", "a", "y", "q"):
            expected = "updated" if key == "q" else key.upper()
            self.assertEqual(mapping.remove(key), expected)
            self.assertFalse(mapping.contains(key))
            remaining = [item for item in collision_keys if item != key]
            self.assertCountEqual(mapping.keys(), remaining)
            for remaining_key in remaining:
                self.assertTrue(mapping.contains(remaining_key))
            collision_keys = remaining
        self.assertEqual(mapping.size(), 0)
        self.assertIsNone(mapping.remove("a"))

    def test_resize_only_after_load_factor_exceeded(self) -> None:
        mapping = HashMap()
        threshold = int(INITIAL_CAPACITY * MAX_LOAD_FACTOR)
        for index in range(threshold):
            mapping.put(str(index), index)
        self.assertEqual(len(mapping._buckets), INITIAL_CAPACITY)
        mapping.put("0", "updated")
        self.assertEqual(len(mapping._buckets), INITIAL_CAPACITY)
        mapping.put("extra", "value")
        self.assertEqual(len(mapping._buckets), INITIAL_CAPACITY * CAPACITY_GROWTH_FACTOR)
        self.assertEqual(mapping.size(), threshold + 1)
        self.assertEqual(mapping.get("0"), "updated")
        for index in range(1, threshold):
            self.assertEqual(mapping.get(str(index)), index)

    def test_repeated_growth_preserves_value_identity_and_removal(self) -> None:
        mapping = HashMap()
        keys = ["", "한글", "😀"] + ["key:" + str(index) for index in range(200)]
        values = [object() for _ in keys]
        for key, value in zip(keys, values):
            mapping.put(key, value)
        self.assertEqual(mapping.size(), len(keys))
        self.assertCountEqual(mapping.keys(), keys)
        for key, value in zip(keys, values):
            self.assertIs(mapping.get(key), value)
        for key, value in zip(keys, values):
            self.assertIs(mapping.remove(key), value)
        self.assertEqual(mapping.size(), 0)
        mapping.put("reused", "ok")
        self.assertEqual(mapping.get("reused"), "ok")
