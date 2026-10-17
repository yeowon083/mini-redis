"""문자열 데이터와 UTF-8 바이트 사용량을 관리하는 저장소."""

from typing import List, Optional

from .structures.hash_map import HashMap


TEXT_ENCODING = "utf-8"


class Entry:
    """키와 문자열 값을 함께 보관한다."""

    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value


def _entry_size(key: str, value: str) -> int:
    """자료구조 오버헤드를 제외한 키와 값의 바이트 수를 계산한다."""
    return len(key.encode(TEXT_ENCODING)) + len(value.encode(TEXT_ENCODING))


class MiniRedis:
    """직접 구현한 해시맵으로 문자열을 저장한다. 입출력은 담당하지 않는다."""

    def __init__(self) -> None:
        self._entries = HashMap()
        self.used_memory = 0

    def set(self, key: str, value: str) -> None:
        """저장하거나 덮어쓴다. 기존 키는 개수를 늘리지 않고 크기만 갱신한다."""
        new_size = _entry_size(key, value)
        previous_entry = self._entries.get(key)
        previous_size = 0
        if previous_entry is not None:
            previous_size = _entry_size(previous_entry.key, previous_entry.value)

        self._entries.put(key, Entry(key, value))
        self.used_memory += new_size - previous_size

    def get(self, key: str) -> Optional[str]:
        """값을 반환한다. 없는 키는 None이며 빈 문자열과 구분한다."""
        entry = self._entries.get(key)
        if entry is None:
            return None
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

    def _delete_entry(self, key: str) -> bool:
        """삭제와 메모리 차감을 한곳에서 수행한다. 실제 삭제 여부를 반환한다."""
        entry = self._entries.remove(key)
        if entry is None:
            return False
        self.used_memory -= _entry_size(entry.key, entry.value)
        return True
