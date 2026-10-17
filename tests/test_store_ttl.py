"""실제 대기 없이 만료 경계와 다른 저장소 기능의 상태 일치를 검증한다."""

import unittest

from mini_redis.store import MiniRedis


class FakeClock:
    """테스트가 현재 시각과 시계 호출 횟수를 직접 조절한다."""

    def __init__(self) -> None:
        self.now = 100.0
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return self.now


class StoreTtlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.store = MiniRedis(clock=self.clock)

    def test_missing_and_persistent_keys_have_distinct_ttl(self) -> None:
        self.assertEqual(self.store.ttl("missing"), -2)
        self.assertEqual(self.store.expire("missing", 10), 0)
        self.store.set("key", "value")
        self.assertEqual(self.store.ttl("key"), -1)

    def test_ttl_rounds_down_and_expires_at_exact_deadline(self) -> None:
        self.store.set("key", "value")
        self.assertEqual(self.store.expire("key", 2), 1)
        self.assertEqual(self.store.ttl("key"), 2)
        self.clock.now += 0.25
        self.assertEqual(self.store.ttl("key"), 1)
        self.clock.now += 1.5
        self.assertEqual(self.store.ttl("key"), 0)
        self.assertEqual(self.store.get("key"), "value")
        self.clock.now += 0.25
        self.assertEqual(self.store.ttl("key"), -2)
        self.assertIsNone(self.store.get("key"))
        self.assertEqual(self.store.used_memory, 0)

    def test_nonpositive_expiration_deletes_immediately(self) -> None:
        for seconds in (0, -1, -100):
            with self.subTest(seconds=seconds):
                self.store.set("key", "value")
                self.assertEqual(self.store.expire("key", seconds), 1)
                self.assertEqual(self.store.expire("key", seconds), 0)
                self.assertEqual(self.store.dbsize(), 0)
                self.assertEqual(self.store.used_memory, 0)
                self.assertEqual(self.store.evicted_keys, 0)

    def test_expire_rejects_noninteger_seconds_without_changing_ttl(self) -> None:
        self.store.set("key", "value")
        self.store.expire("key", 10)
        for seconds in (True, False, 1.0, "1", None):
            for key in ("key", "missing"):
                with self.subTest(seconds=seconds, key=key):
                    with self.assertRaises(ValueError):
                        self.store.expire(key, seconds)
                    self.assertEqual(self.store.ttl("key"), 10)

    def test_reset_to_later_deadline_ignores_previous_record(self) -> None:
        self.store.set("key", "value")
        self.store.expire("key", 2)
        self.clock.now += 1
        self.store.expire("key", 5)
        self.clock.now += 1
        self.assertEqual(self.store.get("key"), "value")
        self.assertEqual(self.store.ttl("key"), 4)
        self.clock.now += 4
        self.assertIsNone(self.store.get("key"))

    def test_reset_to_earlier_deadline_expires_before_old_record(self) -> None:
        self.store.set("key", "value")
        self.store.expire("key", 10)
        self.store.expire("key", 2)
        self.clock.now += 2
        self.assertEqual(self.store.dbsize(), 0)
        self.clock.now += 8
        self.assertEqual(self.store.info_memory(),
                         "used_memory:0\nmaxmemory:0\nevicted_keys:0")

    def test_successful_overwrite_clears_ttl_and_old_record(self) -> None:
        self.store.set("key", "old")
        self.store.expire("key", 2)
        self.store.set("key", "새 값")
        self.assertEqual(self.store.ttl("key"), -1)
        self.clock.now += 2
        self.assertEqual(self.store.get("key"), "새 값")
        self.assertEqual(self.store.used_memory, 10)

    def test_delete_and_recreate_do_not_inherit_old_ttl(self) -> None:
        self.store.set("key", "old")
        self.store.expire("key", 2)
        self.assertEqual(self.store.delete("key"), 1)
        self.store.set("key", "new")
        self.clock.now += 2
        self.assertEqual(self.store.get("key"), "new")
        self.assertEqual(self.store.ttl("key"), -1)

    def test_recreated_key_with_same_deadline_expires_once(self) -> None:
        self.store.set("keep", "v")
        self.store.set("key", "old")
        self.store.expire("key", 2)
        self.store.delete("key")
        self.store.set("key", "new")
        self.store.expire("key", 2)
        self.clock.now += 2
        self.assertEqual(self.store.keys(), ["keep"])
        self.assertEqual(self.store.used_memory, 5)
        self.assertEqual(self.store.evicted_keys, 0)

    def test_equal_deadlines_remove_all_expired_keys(self) -> None:
        for key in ("가", "b", "", "a"):
            self.store.set(key, "값")
            self.store.expire(key, 2)
        self.clock.now += 2
        self.assertEqual(self.store.dbsize(), 0)
        self.assertEqual(self.store.used_memory, 0)
        self.assertEqual(self.store._lru.size(), 0)

    def test_every_public_command_cleans_expired_entries_before_work(self) -> None:
        commands = (
            ("set", lambda store: store.set("new", "v")),
            ("get", lambda store: store.get("missing")),
            ("delete", lambda store: store.delete("missing")),
            ("exists", lambda store: store.exists("missing")),
            ("dbsize", lambda store: store.dbsize()),
            ("keys", lambda store: store.keys()),
            ("config", lambda store: store.config_set_maxmemory(20)),
            ("info", lambda store: store.info_memory()),
            ("expire", lambda store: store.expire("missing", 2)),
            ("ttl", lambda store: store.ttl("missing")),
        )
        for name, command in commands:
            with self.subTest(command=name):
                clock = FakeClock()
                store = MiniRedis(clock=clock)
                store.set("expired", "value")
                store.expire("expired", 1)
                clock.now += 1
                command(store)
                # 후속 명령이 정리를 대신하지 않도록 내부 상태를 바로 확인한다.
                self.assertFalse(store._entries.contains("expired"))
                self.assertEqual(store.used_memory, 4 if name == "set" else 0)
                self.assertEqual(store.evicted_keys, 0)

    def test_each_public_command_reads_clock_once(self) -> None:
        self.store.set("key", "value")
        commands = (
            lambda: self.store.set("key", "value"),
            lambda: self.store.get("key"),
            lambda: self.store.delete("missing"),
            lambda: self.store.exists("key"),
            lambda: self.store.dbsize(),
            lambda: self.store.keys(),
            lambda: self.store.config_set_maxmemory(0),
            lambda: self.store.info_memory(),
            lambda: self.store.expire("key", 2),
            lambda: self.store.ttl("key"),
        )
        for index, command in enumerate(commands):
            with self.subTest(command_index=index):
                previous_calls = self.clock.calls
                command()
                self.assertEqual(self.clock.calls - previous_calls, 1)

    def test_expire_and_ttl_do_not_refresh_lru(self) -> None:
        self.store.config_set_maxmemory(4)
        self.store.set("a", "1")
        self.store.set("b", "2")
        self.store.expire("a", 10)
        self.assertEqual(self.store.ttl("a"), 10)
        self.store.set("c", "3")
        self.assertEqual(sorted(self.store.keys()), ["b", "c"])
        self.assertEqual(self.store.evicted_keys, 1)
        self.clock.now += 10
        self.assertEqual(sorted(self.store.keys()), ["b", "c"])

    def test_expired_entries_free_memory_before_set_without_eviction(self) -> None:
        self.store.config_set_maxmemory(4)
        self.store.set("a", "1")
        self.store.set("b", "2")
        self.store.expire("b", 1)
        self.clock.now += 1
        self.store.set("c", "3")
        self.assertEqual(sorted(self.store.keys()), ["a", "c"])
        self.assertEqual(self.store.used_memory, 4)
        self.assertEqual(self.store.evicted_keys, 0)

    def test_oom_preserves_value_ttl_and_lru_but_cleans_expired_keys(self) -> None:
        self.store.config_set_maxmemory(6)
        for key in ("a", "b", "c"):
            self.store.set(key, "1")
        self.store.expire("a", 10)
        self.store.expire("c", 1)
        self.clock.now += 1
        with self.assertRaises(MemoryError):
            self.store.set("a", "123456")
        self.assertEqual(self.store.ttl("a"), 9)
        self.assertEqual(self.store._entries.get("a").value, "1")
        self.assertEqual(self.store._lru.tail.data, "a")
        self.assertEqual(self.store.used_memory, 4)
        self.assertEqual(self.store.evicted_keys, 0)
        self.store.set("d", "123")
        self.assertEqual(sorted(self.store.keys()), ["b", "d"])
        self.assertEqual(self.store.evicted_keys, 1)

    def test_expire_on_already_expired_key_reports_missing(self) -> None:
        self.store.set("key", "value")
        self.store.expire("key", 1)
        self.clock.now += 1
        self.assertEqual(self.store.expire("key", 10), 0)
        self.assertEqual(self.store.delete("key"), 0)

    def test_repeated_expiration_changes_keep_heap_bounded(self) -> None:
        self.store.set("key", "value")
        self.store.set("permanent", "v")
        for seconds in range(1, 101):
            self.store.expire("key", seconds)
            self.assertLessEqual(self.store._expiration_heap.size(), 4)
        self.clock.now += 99
        self.assertEqual(self.store.ttl("key"), 1)
        self.clock.now += 1
        self.assertEqual(self.store.keys(), ["permanent"])
        self.assertEqual(self.store._expiration_heap.size(), 0)

    def test_removing_last_key_always_clears_expiration_heap(self) -> None:
        for removal in ("delete", "expire", "deadline"):
            with self.subTest(removal=removal):
                self.store.set("key", "value")
                self.store.expire("key", 10)
                self.store.expire("key", 20)
                if removal == "delete":
                    self.store.delete("key")
                elif removal == "expire":
                    self.store.expire("key", 0)
                else:
                    self.clock.now += 20
                    self.store.dbsize()
                self.assertEqual(self.store._expiration_heap.size(), 0)
                self.assertEqual(self.store._lru.size(), 0)
                self.assertEqual(self.store.used_memory, 0)
