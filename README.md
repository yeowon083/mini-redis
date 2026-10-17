# Mini Redis

해시맵, 이중 연결 리스트, 최소 힙을 직접 구현하며 만드는 CLI 저장소입니다.
Python 3.8 이상을 대상으로 하며 외부 패키지 설치는 필요하지 않습니다.

## 실행하기

필수 Phase 1~6의 제품 기능을 구현했습니다. 문자열 저장, LRU 메모리 축출과 TTL 만료를
터미널에서 사용할 수 있습니다. Python 3.8 호환 문법을 사용하며 실제 검증 환경과 결과는
아래 테스트 안내를 참고하세요.

저장소 루트에서 실행합니다.

```console
python -m mini_redis
```

`mini-redis> ` 뒤에 명령을 입력합니다. `exit`, `quit`, EOF 또는 Ctrl+C로 종료합니다.
빈 입력은 무시합니다. 명령과 CONFIG/INFO의 하위 이름은 대소문자를 구분하지 않으며,
키와 값은 입력한 대소문자를 유지합니다. `exit`와 `quit`에는 인자를 붙이지 않습니다.

```console
mini-redis> SET user:1 "Alice Kim"
OK
mini-redis> GET user:1
"Alice Kim"
mini-redis> EXISTS user:1
(integer) 1
mini-redis> EXPIRE user:1 60
(integer) 1
mini-redis> SET user:1 Bob
OK
mini-redis> TTL user:1
(integer) -1
mini-redis> DEL user:1
(integer) 1
mini-redis> GET user:1
(nil)
mini-redis> quit
```

## 명령과 출력

| 명령 형식 | 결과 |
| --- | --- |
| `SET key value` | 저장 또는 덮어쓰기 후 `OK` |
| `GET key` | 큰따옴표로 감싼 값, 없는 키는 `(nil)` |
| `DEL key` | 삭제했으면 `(integer) 1`, 없으면 `(integer) 0` |
| `EXISTS key` | 있으면 `(integer) 1`, 없으면 `(integer) 0` |
| `DBSIZE` | 살아 있는 키 수 |
| `KEYS` | 번호와 큰따옴표를 붙인 전체 키 목록, 없으면 `(empty array)` |
| `CONFIG SET maxmemory bytes` | 0 이상의 바이트 제한 설정 후 `OK`, 0은 무제한 |
| `INFO memory` | `used_memory`, `maxmemory`, `evicted_keys`를 줄별로 출력 |
| `EXPIRE key seconds` | 만료 설정 또는 즉시 삭제 1, 없는 키 0 |
| `TTL key` | 없는 키 -2, 무기한 -1, 남은 초 내림 |

숫자 결과에는 `(integer)`를 붙입니다. KEYS는 순서를 보장하지 않으며 인자나 패턴을 받지 않습니다.
DEL과 EXISTS도 한 번에 키 하나만 받습니다. GET/KEYS 출력은 JSON 문자열 표기처럼 따옴표,
역슬래시와 제어 문자를 이스케이프하고 한글은 그대로 표시합니다.

입력은 표준 라이브러리 `shlex.split` 규칙을 따릅니다. 공백을 포함한 키나 값은 작은따옴표나
큰따옴표로 감싸며, 빈 문자열은 `""`로 입력합니다. 예를 들어 `SET note 'say "hello"'`는
따옴표를 포함한 값을 저장합니다. 닫히지 않은 따옴표나 끝의 불완전한 역슬래시는 구문 오류입니다.
셸 스타일 파서이므로 입력의 `\n`을 줄바꿈 문자로 자동 변환하지 않습니다.

정수는 선택적인 `+`/`-` 뒤의 ASCII 숫자만 허용하며 범위는 -2^63부터 2^63-1까지입니다.
실수, 밑줄과 비 ASCII 숫자는 거절합니다. EXPIRE는 음수를 허용하고 0 이하이면 즉시 삭제합니다.
CONFIG의 메모리 제한에는 음수를 사용할 수 없습니다.

```console
mini-redis> HELLO
(error) ERR unknown command 'HELLO'
mini-redis> GET
(error) ERR wrong number of arguments for 'GET' command
mini-redis> EXPIRE name later
(error) ERR value is not an integer or out of range
mini-redis> INFO other
(error) ERR syntax error
mini-redis> CONFIG SET maxmemory 4
OK
mini-redis> SET name Alice
(error) OOM command not allowed when used_memory > 'maxmemory'
```

인자 수를 먼저 확인한 뒤 하위 이름과 정수 값을 검증합니다. 알 수 없는 명령, 인자 수 오류,
잘못된 정수나 따옴표는 저장소를 변경하지 않으며 오류를 출력한 뒤 다음 입력을 받습니다.

## 구현 순서와 구조

| Phase | 작업 | 구현 모듈 |
| --- | --- | --- |
| 1 | 최소 실행 구조와 동작 규칙 | `mini_redis/__main__.py`, `tests/` |
| 2 | 연결 리스트, 체이닝 해시맵, 최소 힙 | `mini_redis/structures/linked_list.py`, `hash_map.py`, `min_heap.py` |
| 3 | String 저장과 조회, 삭제, 메모리 집계 | `mini_redis/store.py` |
| 4 | LRU 추적과 메모리 제한 | `mini_redis/store.py` |
| 5 | TTL과 만료 정리 | `mini_redis/store.py` |
| 6 | 명령 해석, 결과 출력, REPL | `mini_redis/cli.py` |

자료구조는 입출력을 담당하지 않고, 저장소는 데이터를 관리하며, CLI는 입력 검증과 출력을 담당합니다.

## 기본 자료구조

- `DoublyLinkedList`: 노드의 앞뒤 연결을 바꿔 삽입·삭제·맨 앞으로 이동을 O(1)에 수행합니다.
  노드를 직접 전달하는 작업은 그 노드가 해당 리스트에 속해 있어야 합니다.
- `HashMap`: 문자열 키의 글자들을 숫자로 계산해 버킷을 정합니다. 같은 버킷에 들어온
  키는 연결 리스트에서 구분합니다. 버킷 대비 키 수가 0.75를 넘으면 버킷을 2배 늘립니다.
  삭제해도 버킷을 줄이지 않습니다. 조회·삭제는 평균 O(1), 삽입은 확장 비용을 나누어 보면
  평균 O(1)이지만 충돌이 몰리면 느려집니다. 키 목록은 빈 버킷까지 순회합니다.
- `MinHeap`: `(만료 시각, 키)`를 배열에 보관하고 가장 빠른 항목을 맨 앞에 둡니다.
  힙 기록 수가 H일 때 삽입·삭제는 O(log H), 최소값 조회는 O(1)입니다.
  같은 시각이면 키 순서로 비교합니다.

빈 리스트의 앞뒤 삭제, 없는 해시맵 키 조회·삭제, 빈 힙 조회·삭제는 `None`을 반환합니다.
해시맵에는 없는 값과 구분하기 위해 `None`을 저장할 수 없습니다.

## 저장소 API

`mini_redis.store.MiniRedis`는 문자열 키와 값을 받습니다.
CLI 외에 Python 코드에서도 사용할 수 있습니다.

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
반환된 시각은 표준 라이브러리 `Fraction`으로 정확히 보관하고, 만료 초를 더하거나 남은 시간을
빼거나 힙에서 비교할 때도 이 표현을 유지합니다. 큰 64비트 TTL을 더하면서 float로 반올림되어
기한보다 일찍 만료되거나 TTL이 증가하는 문제를 방지하며 소수 초도 자르지 않습니다.
시계가 float를 반환하면 그 float가 실제로 표현한 값을 보존합니다. 시계가 값을 반환하기 전에
이미 잃은 정밀도를 복구하거나 실제 시계의 해상도를 높이는 것은 아닙니다.

```python
store.expire("user:1", 10)
print(store.ttl("user:1"))  # 남은 정수 초 (호출 시점에 따라 달라짐)
store.set("user:1", "Bob")
print(store.ttl("user:1"))  # -1: SET으로 만료 설정 해제
```

최소 힙에는 `(만료 시각, 키)`를 넣습니다. 기한이 지난 항목을 꺼낼 때 현재 엔트리의 만료 시각과
비교하므로 재설정·덮어쓰기·삭제 이전 기록은 무시합니다. 기록이 살아 있는 키 수의 2배를 넘으면
현재 유효한 만료 설정만 모아 힙을 다시 만들며, 키가 하나도 없으면 힙도 비웁니다.
보통은 기한이 지난 힙 기록만 확인합니다. 재구성할 때는 기존 LRU 리스트를 따라 살아 있는
키만 순회하고 현재 엔트리를 해시맵에서 조회합니다. 빈 버킷 전체를 훑거나 LRU 순서를 바꾸지
않습니다. 만료 설정이 있는 키 수를 t라 하면 재구성은 평균 O(n + t log(t+1))입니다.
모든 키의 해시가 충돌하는 최악의 경우에는 조회 비용 때문에 O(n² + t log(t+1))이 됩니다.

## 시간 복잡도

아래는 문자열 길이와 숫자 연산 비용을 고정했을 때 만료 정리·축출·힙 재구성을 제외한 비용입니다.
`n`은 현재 살아 있는 키 수, `B`는 해시맵 버킷 수, `H`는 유효하지 않은 기록도 포함한
TTL 힙 기록 수, `t`는 만료 설정이 있는 살아 있는 키 수입니다.

| 작업 | 비용 |
| --- | --- |
| GET / EXISTS / TTL / DEL | 평균 O(1), 해시 충돌이 몰리면 O(n) |
| SET | 확장 비용을 나누면 평균 O(1), 충돌·확장 시 비용 추가 |
| DBSIZE / CONFIG / INFO | O(1) |
| KEYS | O(B+n) |
| EXPIRE (양수) | O(log H), 키 조회는 평균 O(1) |
| LRU 최근 위치 이동 / 키 하나 축출 | 평균 O(1) |
| TTL 힙 기록 하나 정리 | O(log H), 키 조회는 평균 O(1) |
| TTL 힙 재구성 | 평균 O(n + t log(t+1)), 최악 O(n² + t log(t+1)) |

모든 공개 저장소 명령은 만료 정리를 먼저 수행하므로, 만료가 몰리면 한 번에 여러 키를 지웁니다.
SET은 제한에 맞을 때까지 여러 키를 축출할 수 있으며 명령 도중 TTL 힙 재구성도 발생할 수 있습니다.
문자열 해싱·UTF-8 바이트 계산·입출력에는 문자열 길이에 비례하는 비용이 추가됩니다.
Fraction의 정확한 산술과 비교에도 분자·분모 크기에 따른 비용이 추가됩니다.
해시맵 확장은 새 버킷 배열과 현재 키를 재배치하므로 평균 O(B+n)이며, 해시 충돌이
몰리면 재배치도 O(n²)이 될 수 있습니다.

버킷 수 B는 과거 최대 데이터 규모에 따라 늘어나며 삭제 후에도 유지됩니다.
자료구조가 보관하는 공간은 문자열·큰 숫자 자체의 크기를 별도로 보면 Θ(B+n+H)입니다.
TTL 힙은 재구성으로 오래된 기록 누적을 제한하지만 버킷 축소는 구현하지 않습니다.
따라서 키를 모두 삭제해 `used_memory`가 0이어도 버킷 공간은 남고, 이후 KEYS는 그 버킷을
순회합니다. 이번 개선은 TTL 힙 재구성에서 빈 버킷 순회를 없애는 범위입니다.

## 범위와 제약

단일 프로세스의 대화형 String 저장소입니다. 네트워크 서버, Redis 프로토콜, 파일 저장,
백그라운드 만료 작업, 동시 접근, 패턴 검색과 다중 키 명령은 제공하지 않습니다.
프로그램을 종료하면 데이터가 사라집니다. 메모리 제한은 Python 프로세스의 실제 메모리 사용량이
아닌 키와 값의 UTF-8 바이트 합계에 적용합니다. `dict`, `set`, `collections`, `heapq`로
필수 자료구조를 대신하지 않으며 외부 실행 의존성도 없습니다.

## 테스트하기

저장소 루트에서 표준 라이브러리 unittest로 전체 테스트를 실행합니다.

```console
python -m unittest discover -s tests -v
```

자료구조의 충돌·확장·노드 연결, 저장소의 UTF-8 메모리·OOM·LRU·TTL, CLI 입력과 출력을
검증합니다. TTL 테스트는 실제 대기 대신 제어 가능한 시계를 사용합니다.
Python 3.12에서 실행 검증하며, Python 3.8은 호환 문법을 검사한 대상입니다.
실제 Python 3.8 런타임 검증은 아직 수행하지 않았습니다.

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
