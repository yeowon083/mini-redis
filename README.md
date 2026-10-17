# Mini Redis

해시맵, 이중 연결 리스트, 최소 힙을 직접 구현하며 만드는 CLI 저장소입니다.
Python 3.8 이상을 대상으로 하며 외부 패키지 설치는 필요하지 않습니다.

## 현재 상태

Phase 1: 패키지 구조, 실행 진입점, 테스트 환경과 설계를 준비했습니다.
현재 실행하면 준비 상태를 출력하고 종료합니다. 저장소와 CLI 명령은 이후 Phase에서 구현합니다.

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

## 개발 원칙

- 정책값과 반복되는 상수에는 의미 있는 이름을 붙입니다.
- 쉬운 이름, 짧은 함수, 순서가 분명한 코드와 한국어 설명을 사용합니다.
- 필수 자료구조를 `dict`, `set`, `collections`로 대체하지 않습니다.
- 필요한 기능만 구현하고 외부 의존성과 불필요한 추상화를 줄입니다.
- 각 Phase에서 별도 리뷰어가 코드와 테스트를 검증하고, 수정 후 Git 커밋을 남깁니다.

로컬 명세, 세부 설계, 작업 체크리스트와 리뷰 기록은 Git에서 제외한 `.docs/`에 보관합니다.
