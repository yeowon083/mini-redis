"""직접 만든 해시 함수와 연결 리스트 체이닝을 사용하는 해시맵."""

from typing import Any, List, Optional

from .linked_list import DoublyLinkedList, Node


INITIAL_CAPACITY = 8
MAX_LOAD_FACTOR = 0.75
CAPACITY_GROWTH_FACTOR = 2
HASH_MULTIPLIER = 31
HASH_MASK = 0xFFFFFFFF


class HashMap:
    """문자열 키를 저장한다. 없는 값과 구분하기 위해 None은 저장하지 않는다."""

    def __init__(self) -> None:
        self._buckets = [DoublyLinkedList() for _ in range(INITIAL_CAPACITY)]
        self._size = 0

    def _bucket_index(self, key: str) -> int:
        """앞 글자의 결과에 다음 글자를 더하고, 크기를 32비트로 제한한다."""
        hash_value = 0
        for character in key:
            hash_value = (hash_value * HASH_MULTIPLIER + ord(character)) & HASH_MASK
        return hash_value % len(self._buckets)

    def _find_node(self, bucket: DoublyLinkedList, key: str) -> Optional[Node]:
        """같은 버킷 안에서 키가 일치하는 노드를 찾는다."""
        node = bucket.head
        while node is not None:
            stored_key, _ = node.data
            if stored_key == key:
                return node
            node = node.next
        return None

    def put(self, key: str, value: Any) -> None:
        """값을 추가하거나 덮어쓴다. 새 키로 부하가 커지면 버킷을 확장한다."""
        if value is None:
            raise ValueError("None은 해시맵에 저장할 수 없습니다.")
        bucket = self._buckets[self._bucket_index(key)]
        node = self._find_node(bucket, key)
        if node is not None:
            node.data = (key, value)
            return
        bucket.insert_back((key, value))
        self._size += 1
        if self._size > len(self._buckets) * MAX_LOAD_FACTOR:
            self._resize()

    def get(self, key: str) -> Any:
        """키의 값을 반환한다. 키가 없으면 None이다."""
        bucket = self._buckets[self._bucket_index(key)]
        node = self._find_node(bucket, key)
        if node is None:
            return None
        return node.data[1]

    def remove(self, key: str) -> Any:
        """키를 삭제하고 원래 값을 반환한다. 키가 없으면 None이다."""
        bucket = self._buckets[self._bucket_index(key)]
        node = self._find_node(bucket, key)
        if node is None:
            return None
        value = node.data[1]
        bucket.remove_node(node)
        self._size -= 1
        return value

    def contains(self, key: str) -> bool:
        """키가 존재하는지 확인한다. 0이나 빈 문자열도 저장된 값이다."""
        bucket = self._buckets[self._bucket_index(key)]
        return self._find_node(bucket, key) is not None

    def keys(self) -> List[str]:
        """전체 버킷과 키를 O(B+n)에 순회한다. 삭제해도 버킷은 줄이지 않는다."""
        result = []
        for bucket in self._buckets:
            node = bucket.head
            while node is not None:
                result.append(node.data[0])
                node = node.next
        return result

    def size(self) -> int:
        """현재 키 수를 반환한다."""
        return self._size

    def _resize(self) -> None:
        """버킷을 두 배 늘리고 새 인덱스에 기존 데이터를 다시 배치한다."""
        old_buckets = self._buckets
        new_capacity = len(old_buckets) * CAPACITY_GROWTH_FACTOR
        self._buckets = [DoublyLinkedList() for _ in range(new_capacity)]
        self._size = 0
        for bucket in old_buckets:
            node = bucket.head
            while node is not None:
                key, value = node.data
                self.put(key, value)
                node = node.next
