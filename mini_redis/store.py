"""문자열 데이터와 UTF-8 메모리 사용량, LRU 순서를 관리하는 저장소."""

from typing import List, Optional

from .structures.hash_map import HashMap
from .structures.linked_list import DoublyLinkedList, Node


TEXT_ENCODING = "utf-8"
UNLIMITED_MEMORY = 0
OUT_OF_MEMORY_ERROR = (
    "(error) OOM command not allowed when used_memory > 'maxmemory'"
)
INVALID_MAXMEMORY_ERROR = "maxmemory는 0 이상의 정수여야 합니다."


class Entry:
    """키, 문자열 값과 바로 이동할 수 있는 LRU 노드를 보관한다."""

    def __init__(self, key: str, value: str, lru_node: Node) -> None:
        self.key = key
        self.value = value
        self.lru_node = lru_node


def _entry_size(key: str, value: str) -> int:
    """자료구조 오버헤드를 제외한 키와 값의 바이트 수를 계산한다."""
    return len(key.encode(TEXT_ENCODING)) + len(value.encode(TEXT_ENCODING))


class MiniRedis:
    """직접 구현한 해시맵으로 문자열을 저장한다. 입출력은 담당하지 않는다."""

    def __init__(self) -> None:
        self._entries = HashMap()
        self._lru = DoublyLinkedList()
        self.used_memory = 0
        self.maxmemory = UNLIMITED_MEMORY
        self.evicted_keys = 0

    def set(self, key: str, value: str) -> None:
        """저장한 키를 최근 사용으로 표시하고, 제한 초과분은 오래된 키부터 지운다."""
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
            self._lru.move_to_front(previous_entry.lru_node)

        self.used_memory += new_size - previous_size
        self._evict_over_memory_limit()

    def get(self, key: str) -> Optional[str]:
        """값을 반환한다. 없는 키는 None이며 빈 문자열과 구분한다."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        self._lru.move_to_front(entry.lru_node)
        return entry.value

    def delete(self, key: str) -> int:
        """키를 삭제한다. 삭제했으면 1, 없는 키면 0을 반환한다."""
        return int(self._delete_entry(key))

    def exists(self, key: str) -> int:
        """키가 있으면 1, 없으면 0을 반환한다. 값의 내용은 판단하지 않는다."""
        return int(self._entries.contains(key))

    def dbsize(self) -> int:
        """현재 저장된 키 수를 반환한다."""
        return self._entries.size()

    def keys(self) -> List[str]:
        """전체 키의 별도 목록을 반환한다. 정렬과 패턴 검색은 하지 않는다."""
        return self._entries.keys()

    def config_set_maxmemory(self, maxmemory: int) -> None:
        """메모리 제한을 바꾼다. 축출은 다음 성공한 SET에서 수행한다."""
        if (
            isinstance(maxmemory, bool)
            or not isinstance(maxmemory, int)
            or maxmemory < UNLIMITED_MEMORY
        ):
            raise ValueError(INVALID_MAXMEMORY_ERROR)
        self.maxmemory = maxmemory

    def info_memory(self) -> str:
        """사용량, 제한과 LRU 축출 횟수를 줄별로 반환한다."""
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

    def _delete_entry(self, key: str) -> bool:
        """데이터, LRU 노드와 메모리를 함께 정리하고 실제 삭제 여부를 반환한다."""
        entry = self._entries.remove(key)
        if entry is None:
            return False
        self._lru.remove_node(entry.lru_node)
        self.used_memory -= _entry_size(entry.key, entry.value)
        return True
