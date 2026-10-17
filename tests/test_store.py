"""저장소의 기본 명령과 UTF-8 메모리 집계가 함께 유지되는지 검증한다."""

import unittest

from mini_redis.store import MiniRedis


class StoreTests(unittest.TestCase):
    """공개 API로 저장·덮어쓰기·삭제와 키 목록을 확인한다."""

    def test_empty_store_and_missing_key_operations(self) -> None:
        store = MiniRedis()
        self.assertIsNone(store.get("missing"))
        self.assertEqual(store.exists("missing"), 0)
        self.assertEqual(store.delete("missing"), 0)
        self.assertEqual(store.dbsize(), 0)
        self.assertEqual(store.keys(), [])
        self.assertEqual(store.used_memory, 0)

    def test_set_get_and_delete_single_key(self) -> None:
        store = MiniRedis()
        store.set("user:1", "Alice")
        self.assertEqual(store.get("user:1"), "Alice")
        self.assertEqual(store.exists("user:1"), 1)
        self.assertEqual(store.dbsize(), 1)
        self.assertEqual(store.keys(), ["user:1"])
        self.assertEqual(store.used_memory, 11)

        self.assertEqual(store.delete("user:1"), 1)
        self.assertEqual(store.delete("user:1"), 0)
        self.assertIsNone(store.get("user:1"))
        self.assertEqual(store.exists("user:1"), 0)
        self.assertEqual(store.dbsize(), 0)
        self.assertEqual(store.keys(), [])
        self.assertEqual(store.used_memory, 0)

    def test_overwrite_grows_shrinks_and_keeps_one_key(self) -> None:
        store = MiniRedis()
        for value, expected_bytes in (("a", 4), ("longer", 9), ("", 3), ("", 3)):
            with self.subTest(value=value):
                store.set("key", value)
                self.assertEqual(store.get("key"), value)
                self.assertEqual(store.dbsize(), 1)
                self.assertEqual(store.keys(), ["key"])
                self.assertEqual(store.used_memory, expected_bytes)
        self.assertEqual(store.delete("key"), 1)
        self.assertEqual(store.used_memory, 0)

    def test_utf8_bytes_include_key_and_value(self) -> None:
        store = MiniRedis()
        # '이름' 6바이트 + '앨리스' 9바이트, 이모지 각 4바이트.
        store.set("이름", "앨리스")
        self.assertEqual(store.used_memory, 15)
        store.set("😀", "🐍")
        self.assertEqual(store.used_memory, 23)
        self.assertEqual(store.get("이름"), "앨리스")
        store.set("이름", "A")
        self.assertEqual(store.used_memory, 15)
        self.assertEqual(store.delete("😀"), 1)
        self.assertEqual(store.used_memory, 7)
        self.assertEqual(store.delete("이름"), 1)
        self.assertEqual(store.used_memory, 0)

    def test_empty_key_and_value_are_stored_not_treated_as_missing(self) -> None:
        store = MiniRedis()
        store.set("", "")
        self.assertEqual(store.get(""), "")
        self.assertIsNone(store.get("missing"))
        self.assertEqual(store.exists(""), 1)
        self.assertEqual(store.dbsize(), 1)
        self.assertEqual(store.used_memory, 0)
        store.set("", "한")
        self.assertEqual(store.used_memory, 3)
        self.assertEqual(store.delete(""), 1)
        self.assertEqual(store.used_memory, 0)

    def test_read_operations_and_missing_delete_do_not_change_data(self) -> None:
        store = MiniRedis()
        store.set("key", "value")
        for _ in range(3):
            self.assertEqual(store.get("key"), "value")
            self.assertIsNone(store.get("missing"))
            self.assertEqual(store.exists("key"), 1)
            self.assertEqual(store.exists("missing"), 0)
            self.assertEqual(store.delete("missing"), 0)
            self.assertEqual(store.keys(), ["key"])
            self.assertEqual(store.dbsize(), 1)
            self.assertEqual(store.used_memory, 8)

    def test_keys_result_cannot_modify_store(self) -> None:
        store = MiniRedis()
        store.set("keep", "value")
        keys = store.keys()
        keys.clear()
        keys.append("invented")
        self.assertEqual(store.keys(), ["keep"])
        self.assertEqual(store.dbsize(), 1)
        self.assertEqual(store.get("keep"), "value")
        self.assertEqual(store.exists("invented"), 0)

    def test_collisions_and_growth_preserve_store_accounting(self) -> None:
        store = MiniRedis()
        keys = ["a", "i", "q", "y"] + ["key:" + str(index) for index in range(100)]
        expected_memory = 0
        for key in keys:
            store.set(key, "값")
            expected_memory += len(key.encode("utf-8")) + 3
            self.assertEqual(store.used_memory, expected_memory)
        self.assertEqual(store.dbsize(), len(keys))
        self.assertCountEqual(store.keys(), keys)
        for key in keys:
            self.assertEqual(store.get(key), "값")
            self.assertEqual(store.delete(key), 1)
            expected_memory -= len(key.encode("utf-8")) + 3
            self.assertEqual(store.used_memory, expected_memory)
        self.assertEqual(store.dbsize(), 0)
        self.assertEqual(store.keys(), [])
        store.set("reused", "ok")
        self.assertEqual(store.get("reused"), "ok")
        self.assertEqual(store.used_memory, 8)

    def test_store_instances_do_not_share_data(self) -> None:
        first = MiniRedis()
        second = MiniRedis()
        first.set("same", "first")
        second.set("same", "second")
        self.assertEqual(first.get("same"), "first")
        self.assertEqual(second.get("same"), "second")
        first.delete("same")
        self.assertEqual(first.used_memory, 0)
        self.assertEqual(second.get("same"), "second")
        self.assertEqual(second.used_memory, 10)
