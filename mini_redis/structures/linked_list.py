"""노드를 바로 찾아 상수 시간에 옮기고 삭제하는 이중 연결 리스트."""

from typing import Any, Optional


class Node:
    """데이터와 양옆 노드를 보관한다."""

    def __init__(self, data: Any) -> None:
        self.data = data
        self.prev: Optional[Node] = None
        self.next: Optional[Node] = None


class DoublyLinkedList:
    """앞뒤 삽입과 소속 노드의 삭제·이동을 O(1)에 수행한다."""

    def __init__(self) -> None:
        self.head: Optional[Node] = None
        self.tail: Optional[Node] = None
        self._size = 0

    def insert_front(self, data: Any) -> Node:
        """맨 앞에 추가하고 생성한 노드를 반환한다."""
        node = Node(data)
        node.next = self.head
        if self.head is None:
            self.tail = node
        else:
            self.head.prev = node
        self.head = node
        self._size += 1
        return node

    def insert_back(self, data: Any) -> Node:
        """맨 뒤에 추가하고 생성한 노드를 반환한다."""
        node = Node(data)
        node.prev = self.tail
        if self.tail is None:
            self.head = node
        else:
            self.tail.next = node
        self.tail = node
        self._size += 1
        return node

    def remove_front(self) -> Optional[Node]:
        """맨 앞 노드를 분리한다. 비어 있으면 None을 반환한다."""
        node = self.head
        if node is not None:
            self.remove_node(node)
        return node

    def remove_back(self) -> Optional[Node]:
        """맨 뒤 노드를 분리한다. 비어 있으면 None을 반환한다."""
        node = self.tail
        if node is not None:
            self.remove_node(node)
        return node

    def remove_node(self, node: Node) -> None:
        """이 리스트에 소속된 노드를 분리한다. 소속 여부는 호출자가 보장한다."""
        if node.prev is None:
            self.head = node.next
        else:
            node.prev.next = node.next
        if node.next is None:
            self.tail = node.prev
        else:
            node.next.prev = node.prev
        node.prev = None
        node.next = None
        self._size -= 1

    def move_to_front(self, node: Node) -> None:
        """소속 노드를 새로 만들지 않고 맨 앞으로 옮긴다."""
        if node is self.head:
            return
        self.remove_node(node)
        node.next = self.head
        self.head.prev = node
        self.head = node
        self._size += 1

    def size(self) -> int:
        """현재 노드 수를 반환한다."""
        return self._size
