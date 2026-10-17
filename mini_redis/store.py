"""문자열 데이터, 메모리 사용량, LRU 순서와 만료 시각을 관리하는 저장소."""

import math
import time
from typing import Callable, List, Optional

from .structures.hash_map import HashMap
from .structures.linked_list import DoublyLinkedList, Node
from .structures.min_heap import MinHeap


TEXT_ENCODING = "utf-8"
UNLIMITED_MEMORY = 0
OUT_OF_MEMORY_ERROR = (
    "(error) OOM command not allowed when used_memory > 'maxmemory'"
)
INVALID_MAXMEMORY_ERROR = "maxmemory는 0 이상의 정수여야 합니다."
INVALID_EXPIRATION_ERROR = "만료 시간은 정수여야 합니다."
TTL_KEY_NOT_FOUND = -2
TTL_NO_EXPIRATION = -1
TTL_HEAP_REBUILD_FACTOR = 2


class Entry:
    """키, 문자열 값, LRU 노드와 선택적인 만료 시각을 보관한다."""

    def __init__(self, key: str, value: str, lru_node: Node) -> None:
        self.key = key
        self.value = value
        self.lru_node = lru_node
        self.expire_at: Optional[float] = None


def _entry_size(key: str, value: str) -> int:
    """자료구조 오버헤드를 제외한 키와 값의 바이트 수를 계산한다."""
    return len(key.encode(TEXT_ENCODING)) + len(value.encode(TEXT_ENCODING))


class MiniRedis:
    """직접 구현한 해시맵으로 문자열을 저장한다. 입출력은 담당하지 않는다."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._entries = HashMap()
        self._lru = DoublyLinkedList()
        self._expiration_heap = MinHeap()
        self._clock = clock
        self.used_memory = 0
        self.maxmemory = UNLIMITED_MEMORY
        self.evicted_keys = 0

    def set(self, key: str, value: str) -> None:
        """저장한 키를 최근 사용으로 표시하고, 제한 초과분은 오래된 키부터 지운다."""
        self._remove_expired_entries(self._clock())
        new_size = _entry_size(key, value)
        # 저장 자체가 불가능하면 기존 값과 사용 순서를 바꾸지 않는다.
        if self.maxmemory != UNLIMITED_MEMORY and new_size > self.maxmemory:
            raise MemoryError(OUT_OF_MEMORY_ERROR)

        previous_entry = self._entries.get(key)
        previous_size = 0
        if previous_entry is None:
            lru_node = self._lru.insert_front(key)
            self._entries.put(key, Entry(key, value, lru_node))
        else:
            previous_size = _entry_size(previous_entry.key, previous_entry.value)
            previous_entry.value = value
            previous_entry.expire_at = None
            self._lru.move_to_front(previous_entry.lru_node)

        self.used_memory += new_size - previous_size
        self._evict_over_memory_limit()
        self._rebuild_expiration_heap_if_needed()

    def get(self, key: str) -> Optional[str]:
        """값을 반환한다. 없는 키는 None이며 빈 문자열과 구분한다."""
        self._remove_expired_entries(self._clock())
        entry = self._entries.get(key)
        if entry is None:
            return None
        self._lru.move_to_front(entry.lru_node)
        return entry.value

    def delete(self, key: str) -> int:
        """키를 삭제한다. 삭제했으면 1, 없는 키면 0을 반환한다."""
        self._remove_expired_entries(self._clock())
        deleted = self._delete_entry(key)
        self._rebuild_expiration_heap_if_needed()
        return int(deleted)

    def exists(self, key: str) -> int:
        """키가 있으면 1, 없으면 0을 반환한다. 값의 내용은 판단하지 않는다."""
        self._remove_expired_entries(self._clock())
        return int(self._entries.contains(key))

    def dbsize(self) -> int:
        """현재 저장된 키 수를 반환한다."""
        self._remove_expired_entries(self._clock())
        return self._entries.size()

    def keys(self) -> List[str]:
        """전체 키의 별도 목록을 반환한다. 정렬과 패턴 검색은 하지 않는다."""
        self._remove_expired_entries(self._clock())
        return self._entries.keys()

    def expire(self, key: str, seconds: int) -> int:
        """정수 초 뒤에 만료시킨다. 0 이하는 즉시 삭제하며 LRU는 바꾸지 않는다."""
        now = self._clock()
        self._remove_expired_entries(now)
        if isinstance(seconds, bool) or not isinstance(seconds, int):
            raise ValueError(INVALID_EXPIRATION_ERROR)
        entry = self._entries.get(key)
        if entry is None:
            return 0
        if seconds <= 0:
            self._delete_entry(key)
        else:
            entry.expire_at = now + seconds
            self._expiration_heap.push((entry.expire_at, key))
        self._rebuild_expiration_heap_if_needed()
        return 1

    def ttl(self, key: str) -> int:
        """없는 키는 -2, 무기한 키는 -1, 나머지는 남은 초를 내림해 반환한다."""
        now = self._clock()
        self._remove_expired_entries(now)
        entry = self._entries.get(key)
        if entry is None:
            return TTL_KEY_NOT_FOUND
        if entry.expire_at is None:
            return TTL_NO_EXPIRATION
        return math.floor(entry.expire_at - now)

    def config_set_maxmemory(self, maxmemory: int) -> None:
        """메모리 제한을 바꾼다. 축출은 다음 성공한 SET에서 수행한다."""
        self._remove_expired_entries(self._clock())
        if (
            isinstance(maxmemory, bool)
            or not isinstance(maxmemory, int)
            or maxmemory < UNLIMITED_MEMORY
        ):
            raise ValueError(INVALID_MAXMEMORY_ERROR)
        self.maxmemory = maxmemory

    def info_memory(self) -> str:
        """사용량, 제한과 LRU 축출 횟수를 줄별로 반환한다."""
        self._remove_expired_entries(self._clock())
        return (
            f"used_memory:{self.used_memory}\n"
            f"maxmemory:{self.maxmemory}\n"
            f"evicted_keys:{self.evicted_keys}"
        )

    def _evict_over_memory_limit(self) -> None:
        """사용량이 제한 이내가 될 때까지 가장 오래 사용하지 않은 키를 지운다."""
        if self.maxmemory == UNLIMITED_MEMORY:
            return
        while self.used_memory > self.maxmemory:
            oldest_node = self._lru.tail
            # 사용량이 남아 있으면 데이터와 연결된 LRU 노드도 반드시 존재한다.
            assert oldest_node is not None
            self._delete_entry(oldest_node.data)
            self.evicted_keys += 1

    def _remove_expired_entries(self, now: float) -> None:
        """기한이 지난 힙 기록을 꺼내 현재 만료 설정과 일치하는 키만 삭제한다."""
        while True:
            expiration = self._expiration_heap.peek()
            if expiration is None or expiration[0] > now:
                break
            expire_at, key = expiration
            self._expiration_heap.pop()
            entry = self._entries.get(key)
            # 덮어쓰기, 삭제, 만료 재설정 이전의 기록은 현재 데이터에 적용하지 않는다.
            if entry is not None and entry.expire_at == expire_at:
                self._delete_entry(key)
        self._rebuild_expiration_heap_if_needed()

    def _rebuild_expiration_heap_if_needed(self) -> None:
        """오래된 기록이 쌓였을 때만 현재 유효한 만료 설정으로 힙을 다시 만든다."""
        key_count = self._entries.size()
        if key_count == 0:
            if self._expiration_heap.size() > 0:
                self._expiration_heap = MinHeap()
            return
        if self._expiration_heap.size() <= key_count * TTL_HEAP_REBUILD_FACTOR:
            return
        expiration_heap = MinHeap()
        for key in self._entries.keys():
            entry = self._entries.get(key)
            if entry.expire_at is not None:
                expiration_heap.push((entry.expire_at, key))
        self._expiration_heap = expiration_heap

    def _delete_entry(self, key: str) -> bool:
        """데이터, LRU, 만료 설정과 메모리를 함께 정리하고 삭제 여부를 반환한다."""
        entry = self._entries.remove(key)
        if entry is None:
            return False
        self._lru.remove_node(entry.lru_node)
        entry.expire_at = None
        self.used_memory -= _entry_size(entry.key, entry.value)
        return True
