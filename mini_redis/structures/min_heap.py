"""만료 시각이 가장 빠른 항목을 찾는 배열 기반 최소 힙."""

from fractions import Fraction
from typing import List, Optional, Tuple, Union


Expiration = Tuple[Union[float, Fraction], str]


class MinHeap:
    """(만료 시각, 키)를 저장한다. 같은 시각은 키의 문자열 순서로 비교한다."""

    def __init__(self) -> None:
        self._items: List[Expiration] = []

    def push(self, item: Expiration) -> None:
        """뒤에 추가한 항목을 부모와 비교하며 올린다. O(log n)."""
        self._items.append(item)
        self._heapify_up(len(self._items) - 1)

    def pop(self) -> Optional[Expiration]:
        """가장 작은 항목을 제거한다. 비어 있으면 None이다. O(log n)."""
        if not self._items:
            return None
        minimum = self._items[0]
        last_item = self._items.pop()
        if self._items:
            self._items[0] = last_item
            self._heapify_down(0)
        return minimum

    def peek(self) -> Optional[Expiration]:
        """가장 작은 항목을 제거하지 않고 반환한다. O(1)."""
        if not self._items:
            return None
        return self._items[0]

    def size(self) -> int:
        """저장된 항목 수를 반환한다."""
        return len(self._items)

    def _heapify_up(self, index: int) -> None:
        """자식이 부모보다 작으면 자리를 바꾼다."""
        while index > 0:
            parent_index = (index - 1) // 2
            if self._items[parent_index] <= self._items[index]:
                return
            self._items[parent_index], self._items[index] = (
                self._items[index], self._items[parent_index]
            )
            index = parent_index

    def _heapify_down(self, index: int) -> None:
        """두 자식 중 작은 쪽과 비교하여 항목을 내려보낸다."""
        while True:
            # 배열에서 부모 i의 자식 위치는 2*i+1, 2*i+2이다.
            left_index = 2 * index + 1
            right_index = left_index + 1
            smallest_index = index
            if (
                left_index < len(self._items)
                and self._items[left_index] < self._items[smallest_index]
            ):
                smallest_index = left_index
            if (
                right_index < len(self._items)
                and self._items[right_index] < self._items[smallest_index]
            ):
                smallest_index = right_index
            if smallest_index == index:
                return
            self._items[index], self._items[smallest_index] = (
                self._items[smallest_index], self._items[index]
            )
            index = smallest_index
