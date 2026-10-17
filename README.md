# Mini Redis

해시맵, 이중 연결 리스트, 최소 힙을 직접 구현하며 만드는 CLI 저장소입니다.
Python 3.8 이상을 대상으로 하며 외부 패키지 설치는 필요하지 않습니다.

## 현재 상태

Phase 5: 기본 자료구조와 String 저장소 API, LRU, 메모리 제한과 TTL을 구현했습니다.
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
| EXPIRE | `expire(key, seconds)` | 설정 또는 즉시 삭제 1, 없는 키 0, 정수가 아니면 `ValueError` |
| TTL | `ttl(key)` | 없는 키 -2, 무기한 -1, 남은 초 내림 |
| CONFIG SET maxmemory | `config_set_maxmemory(maxmemory)` | 없음, 잘못된 값은 `ValueError` |
| INFO memory | `info_memory()` | `used_memory`, `maxmemory`, `evicted_keys`를 줄별로 표시한 문자열 |

`used_memory`는 키와 값의 UTF-8 바이트 수 합계입니다. 자료구조 오버헤드는 제외합니다.
덮어쓰기는 키 수를 유지하며, 삭제는 같은 경로에서 데이터, LRU 노드, 만료 설정과 사용량을 함께 갱신합니다.
이 속성을 직접 읽으면 직전 명령 이후 만료된 키가 남아 있을 수 있습니다.
저장소 명령을 호출하면 먼저 만료를 정리하며, `info_memory()`로 정리된 사용량을 확인할 수 있습니다.

### LRU와 메모리 제한

성공한 SET과 GET은 해당 키를 최근 사용한 위치인 연결 리스트 맨 앞으로 옮깁니다.
각 엔트리가 자신의 노드를 보관하므로 순서 변경은 O(1)입니다. 나머지 명령은 순서를 바꾸지 않습니다.

`maxmemory`의 기본값 0은 무제한입니다. `config_set_maxmemory()`는 0 이상의 정수만 받으며,
불리언, 실수, 문자열과 음수는 `ValueError`를 발생시키고 기존 설정을 유지합니다.
제한을 낮춰도 바로 축출하지 않으며, 다음 성공한 SET 이후 제한을 초과하면 가장 오래 사용하지 않은
키부터 반복 삭제합니다. `evicted_keys`는 이때 축출한 키 수만 누적하며 DEL과 만료 삭제는 포함하지 않습니다.

SET할 키와 값의 바이트 합이 제한보다 크면 `MemoryError`를 발생시킵니다.
이 경우 기존 값, TTL과 LRU 순서를 보존하며 다른 살아 있는 키도 축출하지 않습니다.
명령 시작 시 이미 만료된 데이터는 먼저 정리하므로 그만큼 사용량은 줄어들 수 있습니다.

```python
store.config_set_maxmemory(12)
print(store.info_memory())
# used_memory:11
# maxmemory:12
# evicted_keys:0
```

### TTL과 만료 정리

`expire(key, seconds)`는 키가 살아 있을 시간을 정수 초로 지정합니다. 불리언, 실수와 문자열은
`ValueError`로 거절합니다. 0 이하의 정수는 키를 즉시 삭제합니다. TTL을 다시 설정하면
새 만료 시각을 적용하며, 성공한 SET은 기존 TTL을 해제합니다. EXPIRE와 TTL은 LRU 순서를 바꾸지 않습니다.

남은 시간은 내림하므로 살아 있는 키도 1초 미만이 남으면 TTL이 0입니다.
현재 시각이 만료 시각에 도달하면 키는 없는 것으로 처리합니다. 모든 공개 저장소 명령은
시작할 때 만료된 키를 정리합니다. 별도 백그라운드 작업은 없으며 실제 저장소 접근 시 정리됩니다.

기본 시계는 벽시계 변경에 영향을 받지 않는 `time.monotonic`이며, `MiniRedis(clock=시계함수)`로
초 단위 숫자를 반환하는 함수를 전달할 수 있습니다. 각 명령은 현재 시각을 한 번 읽습니다.

```python
store.expire("user:1", 10)
print(store.ttl("user:1"))  # 남은 정수 초 (호출 시점에 따라 달라짐)
store.set("user:1", "Bob")
print(store.ttl("user:1"))  # -1: SET으로 만료 설정 해제
```

최소 힙에는 `(만료 시각, 키)`를 넣습니다. 기한이 지난 항목을 꺼낼 때 현재 엔트리의 만료 시각과
비교하므로 재설정·덮어쓰기·삭제 이전 기록은 무시합니다. 기록이 살아 있는 키 수의 2배를 넘으면
현재 유효한 만료 설정만 모아 힙을 다시 만들며, 키가 하나도 없으면 힙도 비웁니다.
보통은 기한이 지난 힙 기록만 확인하고, 재구성할 때만 전체 키를 순회합니다.
재구성은 O(n log n)이므로 모든 명령이 O(1)인 것은 아닙니다.

## 개발 원칙

- 정책값과 반복되는 상수에는 의미 있는 이름을 붙입니다.
- 쉬운 이름, 짧은 함수, 순서가 분명한 코드와 한국어 설명을 사용합니다.
- 필수 자료구조를 `dict`, `set`, `collections`로 대체하지 않습니다.
- 필요한 기능만 구현하고 외부 의존성과 불필요한 추상화를 줄입니다.
- 조율자는 작업 배정, 기록, Git 이력과 보고를 담당하며 코드와 테스트를 수정하지 않습니다.
- 구현자는 제품 코드를, 별도 테스터는 테스트 작성과 실행을 담당합니다.
- 별도 리뷰어는 코드와 테스트, 검증 결과를 읽고 지적·판정만 전달하며 테스트를 실행하거나 수정하지 않습니다.
- 각 Phase는 구현, 테스트, 리뷰와 필요한 수정을 마친 뒤 Git 커밋을 남깁니다.

로컬 명세, 세부 설계, 작업 체크리스트와 리뷰 기록은 Git에서 제외한 `.docs/`에 보관합니다.
