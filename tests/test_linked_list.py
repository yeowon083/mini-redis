"""연결 리스트의 양방향 연결과 노드 보존을 검증한다."""

import unittest

from mini_redis.structures.linked_list import DoublyLinkedList


class LinkedListTests(unittest.TestCase):
    """빈 리스트부터 앞·중간·뒤 노드의 이동과 삭제까지 확인한다."""

    def assert_nodes(self, linked_list, expected_nodes) -> None:
        """양방향 순회가 같은 노드를 가리키고 끝에서 닫히는지 확인한다."""
        self.assertEqual(linked_list.size(), len(expected_nodes))
        previous_node = None
        node = linked_list.head
        for expected_node in expected_nodes:
            self.assertIs(node, expected_node)
            self.assertIs(node.prev, previous_node)
            previous_node = node
            node = node.next
        self.assertIsNone(node)
        self.assertIs(linked_list.tail, previous_node)

        next_node = None
        node = linked_list.tail
        for expected_node in reversed(expected_nodes):
            self.assertIs(node, expected_node)
            self.assertIs(node.next, next_node)
            next_node = node
            node = node.prev
        self.assertIsNone(node)
        self.assertIs(linked_list.head, next_node)

    def test_empty_removals_keep_list_empty(self) -> None:
        linked_list = DoublyLinkedList()
        self.assertIsNone(linked_list.remove_front())
        self.assertIsNone(linked_list.remove_back())
        self.assert_nodes(linked_list, [])

    def test_insertions_keep_data_and_both_directions(self) -> None:
        linked_list = DoublyLinkedList()
        middle = linked_list.insert_front("middle")
        self.assert_nodes(linked_list, [middle])
        first = linked_list.insert_front("first")
        last = linked_list.insert_back("last")
        self.assert_nodes(linked_list, [first, middle, last])
        self.assertEqual([first.data, middle.data, last.data], ["first", "middle", "last"])

    def test_single_node_can_be_removed_from_either_end(self) -> None:
        for insertion in ("insert_front", "insert_back"):
            for removal in ("remove_front", "remove_back"):
                with self.subTest(insertion=insertion, removal=removal):
                    linked_list = DoublyLinkedList()
                    node = getattr(linked_list, insertion)("only")
                    self.assertIs(getattr(linked_list, removal)(), node)
                    self.assertIsNone(node.prev)
                    self.assertIsNone(node.next)
                    self.assert_nodes(linked_list, [])

    def test_remove_middle_head_and_tail_clears_detached_links(self) -> None:
        linked_list = DoublyLinkedList()
        first = linked_list.insert_back("first")
        middle = linked_list.insert_back("middle")
        last = linked_list.insert_back("last")
        for removed, remaining in (
            (middle, [first, last]), (first, [last]), (last, [])
        ):
            linked_list.remove_node(removed)
            self.assertIsNone(removed.prev)
            self.assertIsNone(removed.next)
            self.assert_nodes(linked_list, remaining)

    def test_move_preserves_node_identity_size_and_links(self) -> None:
        linked_list = DoublyLinkedList()
        first = linked_list.insert_back("first")
        middle = linked_list.insert_back("middle")
        last = linked_list.insert_back("last")
        linked_list.move_to_front(first)
        self.assert_nodes(linked_list, [first, middle, last])
        linked_list.move_to_front(middle)
        self.assert_nodes(linked_list, [middle, first, last])
        linked_list.move_to_front(last)
        self.assert_nodes(linked_list, [last, middle, first])

    def test_move_single_node_and_reuse_emptied_list(self) -> None:
        linked_list = DoublyLinkedList()
        node = linked_list.insert_back("only")
        linked_list.move_to_front(node)
        self.assert_nodes(linked_list, [node])
        linked_list.remove_back()
        replacement = linked_list.insert_front("new")
        self.assert_nodes(linked_list, [replacement])
