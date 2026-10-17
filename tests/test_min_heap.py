"""만료 기록을 항상 가장 이른 순서로 꺼내는지 검증한다."""

import random
import unittest

from mini_redis.structures.min_heap import MinHeap


RANDOM_SEED = 20261017
MIXED_OPERATION_COUNT = 300


class MinHeapTests(unittest.TestCase):
    """빈 힙, 같은 시각, 중복 항목과 삽입/삭제 혼합을 검증한다."""

    def test_empty_heap_returns_none(self) -> None:
        heap = MinHeap()
        self.assertIsNone(heap.peek())
        self.assertIsNone(heap.pop())
        self.assertEqual(heap.size(), 0)

    def test_single_item_can_be_peeked_repeatedly_and_removed(self) -> None:
        heap = MinHeap()
        item = (1.5, "key")
        heap.push(item)
        self.assertEqual(heap.peek(), item)
        self.assertEqual(heap.peek(), item)
        self.assertEqual(heap.size(), 1)
        self.assertEqual(heap.pop(), item)
        self.assertIsNone(heap.peek())
        heap.push((0.0, "new"))
        self.assertEqual(heap.pop(), (0.0, "new"))

    def test_varied_orders_pop_in_sorted_order(self) -> None:
        items = [(float(index), str(index)) for index in range(20)]
        for ordered_items in (items, list(reversed(items)), items[::2] + items[1::2]):
            with self.subTest(ordered_items=ordered_items):
                heap = MinHeap()
                for item in ordered_items:
                    heap.push(item)
                for remaining, expected in enumerate(sorted(items)):
                    self.assertEqual(heap.peek(), expected)
                    self.assertEqual(heap.pop(), expected)
                    self.assertEqual(heap.size(), len(items) - remaining - 1)
                self.assertIsNone(heap.pop())

    def test_equal_times_use_key_order_and_preserve_duplicates(self) -> None:
        heap = MinHeap()
        items = [(2.5, "한글"), (2.5, "b"), (2.5, "a"), (2.5, "a")]
        for item in items:
            heap.push(item)
        self.assertEqual([heap.pop() for _ in items], sorted(items))

    def test_mixed_operations_match_sorted_reference(self) -> None:
        random_source = random.Random(RANDOM_SEED)
        heap = MinHeap()
        expected_items = []
        for index in range(MIXED_OPERATION_COUNT):
            if expected_items and random_source.choice([True, False]):
                expected_items.sort()
                self.assertEqual(heap.pop(), expected_items.pop(0))
            else:
                item = (float(random_source.randrange(30)), str(index))
                heap.push(item)
                expected_items.append(item)
            self.assertEqual(heap.size(), len(expected_items))
            expected_minimum = min(expected_items) if expected_items else None
            self.assertEqual(heap.peek(), expected_minimum)
        self.assertEqual(
            [heap.pop() for _ in expected_items], sorted(expected_items)
        )
