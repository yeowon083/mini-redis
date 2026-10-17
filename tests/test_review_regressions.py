"""큰 TTL의 정확성과 드문드문 남은 저장소의 순회 비용을 검증한다."""

import unittest

from mini_redis.cli import execute_command
from mini_redis.store import MiniRedis
from mini_redis.structures.min_heap import MinHeap
from tests.test_store_ttl import FakeClock


MAX_TTL_SECONDS = 2 ** 63 - 1
FLOAT_EXACT_INTEGER_LIMIT = 2 ** 53
GROWTH_KEY_COUNT = 10000
EXPECTED_RETAINED_BUCKETS = 16384


class CountingBuckets(list):
    """전체 버킷 순회와 키 해시로 찾는 단일 버킷 조회를 구분한다."""

    def __init__(self, buckets) -> None:
        super().__init__(buckets)
        self.scan_visits = 0
        self.index_reads = 0

    def __iter__(self):
        for bucket in super().__iter__():
            self.scan_visits += 1
            yield bucket

    def __getitem__(self, index):
        self.index_reads += 1
        return super().__getitem__(index)


class CountingLruNode:
    """읽기 전용 프록시로 재구성이 실제 확인한 살아 있는 노드를 센다."""

    def __init__(self, node, visited_keys) -> None:
        self.node = node
        self.visited_keys = visited_keys

    @property
    def data(self):
        self.visited_keys.append(self.node.data)
        return self.node.data

    @property
    def next(self):
        next_node = self.node.next
        if next_node is None:
            return None
        return CountingLruNode(next_node, self.visited_keys)


class LargeTtlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.store = MiniRedis(clock=self.clock)

    def test_maximum_cli_expire_returns_the_same_ttl_without_clock_movement(self) -> None:
        self.assertEqual(execute_command("SET key value", self.store), "OK")
        self.assertEqual(execute_command(f"EXPIRE key {MAX_TTL_SECONDS}", self.store), "(integer) 1")
        self.assertEqual(execute_command("TTL key", self.store), f"(integer) {MAX_TTL_SECONDS}")

    def test_large_float_clock_one_second_before_deadline_keeps_key_alive(self) -> None:
        self.store.set("key", "value")
        self.store.expire("key", FLOAT_EXACT_INTEGER_LIMIT + 1)
        # 이 시각은 float로 정확하지만 실제 만료 시각인 다음 정수는 float로 표현할 수 없다.
        self.clock.now = 100.0 + FLOAT_EXACT_INTEGER_LIMIT
        self.assertEqual(self.store.get("key"), "value")
        self.assertEqual(self.store.ttl("key"), 1)
        # 정확한 만료 경계는 반올림된 float가 아닌 정수 시계로 전달한다.
        self.clock.now = 100 + FLOAT_EXACT_INTEGER_LIMIT + 1
        self.assertIsNone(self.store.get("key"))
        self.assertEqual(self.store.ttl("key"), -2)

    def test_maximum_ttl_integer_clock_before_and_at_exact_deadline(self) -> None:
        self.store.set("key", "value")
        self.store.expire("key", MAX_TTL_SECONDS)
        self.clock.now = 100 + MAX_TTL_SECONDS - 1
        self.assertEqual(self.store.ttl("key"), 1)
        self.assertEqual(self.store.get("key"), "value")
        self.clock.now = 100 + MAX_TTL_SECONDS
        self.assertEqual(self.store.ttl("key"), -2)
        self.assertEqual(self.store.dbsize(), 0)
        self.assertEqual(self.store.used_memory, 0)

    def test_fractional_clock_preserves_floor_and_adjacent_float_boundaries(self) -> None:
        # float.fromhex의 두 값은 1.125 바로 전과 바로 다음 표현 가능한 실수다.
        self.clock.now = 0.125
        self.store.set("key", "value")
        self.store.expire("key", 1)
        self.assertEqual(self.store.ttl("key"), 1)
        self.clock.now = 0.375
        self.assertEqual(self.store.ttl("key"), 0)
        self.clock.now = float.fromhex("0x1.1ffffffffffffp+0")
        self.assertEqual(self.store.get("key"), "value")
        self.assertEqual(self.store.ttl("key"), 0)
        self.clock.now = 1.125
        self.assertIsNone(self.store.get("key"))
        self.clock.now = float.fromhex("0x1.2000000000001p+0")
        self.assertEqual(self.store.ttl("key"), -2)

    def test_huge_ttl_retains_fractional_start_when_entering_next_second(self) -> None:
        self.clock.now = 0.125
        self.store.set("key", "value")
        self.store.expire("key", MAX_TTL_SECONDS)
        self.assertEqual(self.store.ttl("key"), MAX_TTL_SECONDS)
        self.clock.now = 0.375
        self.assertEqual(self.store.ttl("key"), MAX_TTL_SECONDS - 1)
        self.clock.now = MAX_TTL_SECONDS
        self.assertEqual(self.store.get("key"), "value")
        self.assertEqual(self.store.ttl("key"), 0)
        self.clock.now = MAX_TTL_SECONDS + 1
        self.assertIsNone(self.store.get("key"))

    def test_reset_overwrite_and_delete_recreate_ignore_huge_old_deadlines(self) -> None:
        self.store.set("reset", "value")
        self.store.expire("reset", MAX_TTL_SECONDS)
        self.store.expire("reset", 2)
        self.store.set("overwrite", "old")
        self.store.expire("overwrite", MAX_TTL_SECONDS)
        self.store.set("overwrite", "new")
        self.store.set("recreate", "old")
        self.store.expire("recreate", MAX_TTL_SECONDS)
        self.store.delete("recreate")
        self.store.set("recreate", "new")
        self.clock.now = 102.0
        self.assertIsNone(self.store.get("reset"))
        self.assertEqual(self.store.ttl("overwrite"), -1)
        self.assertEqual(self.store.ttl("recreate"), -1)
        self.clock.now = 100 + MAX_TTL_SECONDS
        self.assertEqual(self.store.get("overwrite"), "new")
        self.assertEqual(self.store.get("recreate"), "new")

    def test_rejected_overwrite_preserves_exact_large_ttl_and_original_value(self) -> None:
        self.store.set("key", "value")
        self.store.expire("key", MAX_TTL_SECONDS)
        self.store.config_set_maxmemory(8)
        with self.assertRaises(MemoryError):
            self.store.set("key", "too large")
        self.assertEqual(self.store.ttl("key"), MAX_TTL_SECONDS)
        self.assertEqual(self.store.get("key"), "value")
        self.assertEqual(self.store.used_memory, 8)
        self.assertEqual(self.store.evicted_keys, 0)

    def test_heap_orders_short_and_large_deadlines_and_equal_deadlines(self) -> None:
        for key, seconds in (("huge", MAX_TTL_SECONDS), ("large", FLOAT_EXACT_INTEGER_LIMIT + 1),
                             ("short-b", 2), ("short-a", 2)):
            self.store.set(key, "value")
            self.store.expire(key, seconds)
        self.clock.now = 102.0
        self.assertCountEqual(self.store.keys(), ["huge", "large"])
        self.clock.now = 100 + FLOAT_EXACT_INTEGER_LIMIT
        self.assertEqual(self.store.ttl("large"), 1)
        self.clock.now += 1
        self.assertIsNone(self.store.get("large"))
        self.assertEqual(self.store.get("huge"), "value")
        self.clock.now = 100 + MAX_TTL_SECONDS
        self.assertEqual(self.store.dbsize(), 0)

    def test_min_heap_keeps_large_integer_priorities_distinct_from_float_priorities(self) -> None:
        heap = MinHeap()
        earlier = FLOAT_EXACT_INTEGER_LIMIT
        later = FLOAT_EXACT_INTEGER_LIMIT + 1
        items = [(later, "a"), (float(earlier), "z"), (later, "b"), (0.125, "fraction")]
        for item in items:
            heap.push(item)
        self.assertEqual([heap.pop() for _ in items],
                         [(0.125, "fraction"), (float(earlier), "z"), (later, "a"), (later, "b")])


class SparseStoreTests(unittest.TestCase):
    def make_sparse_store(self) -> MiniRedis:
        store = MiniRedis(clock=lambda: 100.0)
        for index in range(GROWTH_KEY_COUNT):
            store.set(str(index), "x")
        expanded_capacity = len(store._entries._buckets)
        for index in range(GROWTH_KEY_COUNT):
            store.delete(str(index))
        self.assertEqual(expanded_capacity, EXPECTED_RETAINED_BUCKETS)
        self.assertEqual(len(store._entries._buckets), expanded_capacity)
        self.assertEqual(store.dbsize(), 0)
        self.assertEqual(store.used_memory, 0)
        return store

    def test_keys_still_visits_all_retained_buckets_without_shrinking(self) -> None:
        store = self.make_sparse_store()
        store.set("only", "x")
        buckets = CountingBuckets(store._entries._buckets)
        store._entries._buckets = buckets
        self.assertEqual(store.keys(), ["only"])
        self.assertEqual(buckets.scan_visits, EXPECTED_RETAINED_BUCKETS)
        self.assertEqual(buckets.index_reads, 0)

    def test_ttl_rebuild_reads_only_live_lru_nodes_without_scanning_retained_buckets(self) -> None:
        store = self.make_sparse_store()
        for key in ("a", "b", "no-ttl"):
            store.set(key, "x")
        for seconds in range(1000, 1006):
            store.expire("a", seconds)
        buckets = CountingBuckets(store._entries._buckets)
        store._entries._buckets = buckets
        original_head = store._lru.head
        visited_keys = []
        store._lru.head = CountingLruNode(original_head, visited_keys)
        try:
            store.expire("a", 1006)
        finally:
            store._lru.head = original_head
        self.assertEqual(buckets.scan_visits, 0)
        self.assertCountEqual(visited_keys, ["a", "b", "no-ttl"])
        self.assertEqual(len(visited_keys), 3)
        # EXPIRE의 조회 1회와 살아 있는 노드 각각의 조회 3회는 전체 버킷 순회와 별개다.
        self.assertEqual(buckets.index_reads, 4)
        self.assertEqual(store._expiration_heap.size(), 1)
        self.assertEqual(store.ttl("a"), 1006)
        self.assertEqual(len(store._entries._buckets), EXPECTED_RETAINED_BUCKETS)
