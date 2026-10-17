# Mini Redis

해시맵, 이중 연결 리스트, 최소 힙을 직접 구현하며 만드는 CLI 저장소입니다.
Python 3.8 이상을 대상으로 하며 외부 패키지 설치는 필요하지 않습니다.

## 현재 상태

Phase 3: 기본 자료구조와 String 저장소 API를 구현했습니다.
현재 모듈을 실행하면 준비 상태를 출력하고 종료합니다. CLI 명령 입력은 Phase 6에서 연결합니다.

저장소 루트에서 실행합니다.

```console
python -m mini_redis
python -m unittest discover -s tests -v
```

## 구현 순서와 구조

| Phase | 작업 | 구현할 모듈 |
| --- | --- | --- |
| 1 | 최소 실행 구조와 동작 규칙 | `mini_redis/__main__.py`, `tests/` |
| 2 | 연결 리스트, 체이닝 해시맵, 최소 힙 | `mini_redis/structures/linked_list.py`, `hash_map.py`, `min_heap.py` |
| 3 | String 저장과 조회, 삭제, 메모리 집계 | `mini_redis/store.py` |
| 4 | LRU 추적과 메모리 제한 | `mini_redis/store.py` |
| 5 | TTL과 만료 정리 | `mini_redis/store.py` |
| 6 | 명령 해석, 결과 출력, REPL | `mini_redis/cli.py` |

예정 모듈은 해당 기능을 구현할 때 추가합니다. 자료구조는 입출력을 담당하지 않고,
저장소는 데이터를 관리하며, CLI는 입력과 출력만 담당합니다.

## 기본 자료구조

- `DoublyLinkedList`: 노드의 앞뒤 연결을 바꿔 삽입·삭제·맨 앞으로 이동을 O(1)에 수행합니다.
  노드를 직접 전달하는 작업은 그 노드가 해당 리스트에 속해 있어야 합니다.
- `HashMap`: 문자열 키의 글자들을 숫자로 계산해 버킷을 정합니다. 같은 버킷에 들어온
  키는 연결 리스트에서 구분합니다. 버킷 대비 키 수가 0.75를 넘으면 버킷을 2배 늘립니다.
  조회·삽입·삭제는 평균 O(1)이지만 충돌이 몰리면 느려집니다.
- `MinHeap`: `(만료 시각, 키)`를 배열에 보관하고 가장 빠른 항목을 맨 앞에 둡니다.
  삽입·삭제는 O(log n), 최소값 조회는 O(1)입니다. 같은 시각이면 키 순서로 비교합니다.

빈 리스트의 앞뒤 삭제, 없는 해시맵 키 조회·삭제, 빈 힙 조회·삭제는 `None`을 반환합니다.
해시맵에는 없는 값과 구분하기 위해 `None`을 저장할 수 없습니다.

## 저장소 API

`mini_redis.store.MiniRedis`는 문자열 키와 값을 받습니다.
아직 CLI 입력은 연결하지 않았으며 Python 코드에서 사용할 수 있습니다.

```python
from mini_redis.store import MiniRedis

store = MiniRedis()
store.set("user:1", "Alice")
print(store.get("user:1"))  # Alice
print(store.used_memory)   # 11 (키 6바이트 + 값 5바이트)
```

| 명령 | 메서드 | 반환값 |
| --- | --- | --- |
| SET | `set(key, value)` | 없음 |
| GET | `get(key)` | 문자열, 없는 키는 `None` |
| DEL | `delete(key)` | 삭제 1, 없는 키 0 |
| EXISTS | `exists(key)` | 존재 1, 없는 키 0 |
| DBSIZE | `dbsize()` | 키 수 |
| KEYS | `keys()` | 전체 키 목록, 순서 보장 없음 |

`used_memory`는 키와 값의 UTF-8 바이트 수 합계입니다. 자료구조 오버헤드는 제외합니다.
덮어쓰기는 키 수를 유지하며, 삭제는 같은 경로에서 데이터와 사용량을 함께 갱신합니다.
LRU와 메모리 제한은 Phase 4, TTL은 Phase 5에서 추가합니다.

## 개발 원칙

- 정책값과 반복되는 상수에는 의미 있는 이름을 붙입니다.
- 쉬운 이름, 짧은 함수, 순서가 분명한 코드와 한국어 설명을 사용합니다.
- 필수 자료구조를 `dict`, `set`, `collections`로 대체하지 않습니다.
- 필요한 기능만 구현하고 외부 의존성과 불필요한 추상화를 줄입니다.
- 각 Phase에서 별도 리뷰어가 코드와 테스트를 검증하고, 수정 후 Git 커밋을 남깁니다.

로컬 명세, 세부 설계, 작업 체크리스트와 리뷰 기록은 Git에서 제외한 `.docs/`에 보관합니다.
