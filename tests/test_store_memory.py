"""공개 명령으로 메모리 제한과 LRU 축출 정책을 검증한다."""

import unittest

from mini_redis.store import MiniRedis


class StoreMemoryTests(unittest.TestCase):
    """읽기·쓰기·실패 후에도 저장소 상태가 함께 유지되는지 확인한다."""

    def assert_memory(self, store: MiniRedis, used: int, limit: int, evicted: int) -> None:
        expected = "used_memory:{}\nmaxmemory:{}\nevicted_keys:{}".format(
            used, limit, evicted
        )
        self.assertEqual(store.info_memory(), expected)
        self.assertEqual(store.used_memory, used)

    def test_default_is_unlimited_and_reports_empty_memory(self) -> None:
        store = MiniRedis()
        self.assert_memory(store, 0, 0, 0)
        store.set("key", "value" * 100)
        self.assert_memory(store, 503, 0, 0)

    def test_get_moves_key_to_front_before_eviction(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(4)
        store.set("a", "1")
        store.set("b", "2")
        self.assertEqual(store.get("a"), "1")
        store.set("c", "3")
        self.assertCountEqual(store.keys(), ["a", "c"])
        self.assert_memory(store, 4, 4, 1)

    def test_overwrite_updates_recency_and_memory_for_growth_and_shrink(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(6)
        store.set("a", "1")
        store.set("b", "2")
        store.set("a", "123")
        self.assert_memory(store, 6, 6, 0)
        store.set("c", "3")
        self.assertCountEqual(store.keys(), ["a", "c"])
        store.set("a", "")
        self.assert_memory(store, 3, 6, 1)
        store.set("d", "456")
        self.assertCountEqual(store.keys(), ["a", "d"])
        self.assert_memory(store, 5, 6, 2)

    def test_one_write_evicts_several_keys_and_count_accumulates(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(6)
        for key in ("a", "b", "c"):
            store.set(key, "1")
        store.set("d", "1234")
        self.assertEqual(store.keys(), ["d"])
        self.assert_memory(store, 5, 6, 3)
        store.set("e", "2")
        self.assertEqual(store.keys(), ["e"])
        self.assert_memory(store, 2, 6, 4)

    def test_exact_limit_is_allowed_and_one_byte_above_is_rejected(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(4)
        store.set("a", "123")
        self.assert_memory(store, 4, 4, 0)
        with self.assertRaises(MemoryError):
            store.set("b", "1234")
        self.assertEqual(store.keys(), ["a"])
        self.assert_memory(store, 4, 4, 0)

    def test_lowering_limit_waits_until_next_successful_set(self) -> None:
        store = MiniRedis()
        store.set("a", "1")
        store.set("b", "2")
        store.set("c", "3")
        store.config_set_maxmemory(3)
        self.assert_memory(store, 6, 3, 0)
        self.assertEqual(store.get("a"), "1")
        self.assertEqual(store.dbsize(), 3)
        store.set("d", "4")
        self.assertEqual(store.keys(), ["d"])
        self.assert_memory(store, 2, 3, 3)

    def test_reset_to_zero_disables_eviction_without_resetting_count(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(2)
        store.set("a", "1")
        store.set("b", "2")
        store.config_set_maxmemory(0)
        store.set("c", "12345")
        self.assertCountEqual(store.keys(), ["b", "c"])
        self.assert_memory(store, 8, 0, 1)

    def test_utf8_limit_counts_korean_and_emoji_bytes(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(7)
        store.set("한", "😀")
        self.assert_memory(store, 7, 7, 0)
        with self.assertRaises(MemoryError):
            store.set("😀", "😀")
        self.assertEqual(store.keys(), ["한"])
        self.assert_memory(store, 7, 7, 0)

    def test_new_key_oom_preserves_values_memory_count_and_recency(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(4)
        store.set("a", "1")
        store.set("b", "2")
        with self.assertRaises(MemoryError):
            store.set("c", "1234")
        self.assertCountEqual(store.keys(), ["a", "b"])
        self.assert_memory(store, 4, 4, 0)
        store.set("c", "3")
        self.assertCountEqual(store.keys(), ["b", "c"])
        self.assertEqual(store.get("b"), "2")
        self.assert_memory(store, 4, 4, 1)

    def test_overwrite_oom_preserves_old_value_and_does_not_touch_key(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(4)
        store.set("a", "1")
        store.set("b", "2")
        with self.assertRaises(MemoryError):
            store.set("a", "1234")
        self.assert_memory(store, 4, 4, 0)
        store.set("c", "3")
        self.assertCountEqual(store.keys(), ["b", "c"])
        self.assertEqual(store.get("b"), "2")
        self.assert_memory(store, 4, 4, 1)

        # 값 보존을 확인하는 GET은 별도 저장소에서 실행해 LRU 검증에 영향을 주지 않는다.
        original = MiniRedis()
        original.config_set_maxmemory(4)
        original.set("a", "old")
        with self.assertRaises(MemoryError):
            original.set("a", "longer")
        self.assertEqual(original.get("a"), "old")
        self.assert_memory(original, 4, 4, 0)

    def test_oom_after_lowering_limit_does_not_evict_existing_keys(self) -> None:
        store = MiniRedis()
        store.set("a", "1")
        store.set("b", "2")
        store.config_set_maxmemory(1)
        with self.assertRaises(MemoryError):
            store.set("c", "3")
        self.assertCountEqual(store.keys(), ["a", "b"])
        self.assert_memory(store, 4, 1, 0)
        store.set("c", "")
        self.assertEqual(store.keys(), ["c"])
        self.assert_memory(store, 1, 1, 2)

    def test_delete_removes_lru_node_without_counting_as_eviction(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(6)
        for key in ("a", "b", "c"):
            store.set(key, "1")
        self.assertEqual(store.delete("b"), 1)
        self.assertEqual(store.delete("missing"), 0)
        self.assert_memory(store, 4, 6, 0)
        store.set("d", "123")
        self.assertCountEqual(store.keys(), ["c", "d"])
        self.assert_memory(store, 6, 6, 1)
        for key in ("c", "d"):
            store.delete(key)
        self.assert_memory(store, 0, 6, 1)
        store.set("a", "1")
        store.set("b", "1234")
        self.assertEqual(store.keys(), ["b"])
        self.assert_memory(store, 5, 6, 2)

    def test_other_reads_config_and_missing_operations_do_not_touch_lru(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(4)
        store.set("a", "1")
        store.set("b", "2")
        self.assertEqual(store.exists("a"), 1)
        self.assertCountEqual(store.keys(), ["a", "b"])
        self.assertEqual(store.dbsize(), 2)
        self.assertIsNone(store.get("missing"))
        self.assertEqual(store.delete("missing"), 0)
        self.assert_memory(store, 4, 4, 0)
        store.config_set_maxmemory(4)
        store.set("c", "3")
        self.assertCountEqual(store.keys(), ["b", "c"])

    def test_invalid_limits_raise_value_error_and_preserve_setting(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(4)
        store.set("a", "1")
        for invalid in (-1, True, False, 4.0, "4", None):
            with self.subTest(limit=invalid):
                with self.assertRaises(ValueError):
                    store.config_set_maxmemory(invalid)
                self.assert_memory(store, 2, 4, 0)

    def test_empty_key_value_and_repeated_overwrites_leave_no_stale_nodes(self) -> None:
        store = MiniRedis()
        store.config_set_maxmemory(2)
        store.set("", "")
        for _ in range(3):
            store.set("a", "1")
            self.assertEqual(store.get("a"), "1")
        store.set("b", "2")
        self.assertEqual(store.keys(), ["b"])
        self.assert_memory(store, 2, 2, 2)
