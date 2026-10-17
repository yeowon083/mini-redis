"""입력한 명령을 검증하고 저장소의 결과를 Redis 스타일로 보여 준다."""

import json
import shlex
from typing import List, Optional

from .store import MiniRedis


PROMPT = "mini-redis> "
SUCCESS = "OK"
MISSING_VALUE = "(nil)"
EMPTY_KEYS = "(empty array)"
SYNTAX_ERROR = "(error) ERR syntax error"
INTEGER_ERROR = "(error) ERR value is not an integer or out of range"
MIN_INTEGER = -(2 ** 63)
MAX_INTEGER = 2 ** 63 - 1
EXIT_COMMANDS = ("exit", "quit")


def _argument_error(command: str) -> str:
    return f"(error) ERR wrong number of arguments for '{command}' command"


def _quoted(text: str) -> str:
    """따옴표, 역슬래시와 제어 문자를 안전하게 표시한다."""
    return json.dumps(text, ensure_ascii=False)


def _integer_result(value: int) -> str:
    return f"(integer) {value}"


def _parse_integer(text: str) -> Optional[int]:
    """ASCII 숫자와 선택적인 부호만 허용하고 64비트 범위를 확인한다."""
    digits = text[1:] if text.startswith(("+", "-")) else text
    if not digits or any(character < "0" or character > "9" for character in digits):
        return None
    # 아주 긴 숫자도 int 변환 제한에 걸리지 않도록 크기를 먼저 확인한다.
    significant_digits = digits.lstrip("0") or "0"
    if len(significant_digits) > len(str(-MIN_INTEGER)):
        return None
    value = int(significant_digits)
    if text.startswith("-"):
        value = -value
    if value < MIN_INTEGER or value > MAX_INTEGER:
        return None
    return value


def execute_command(line: str, store: MiniRedis) -> str:
    """명령 한 줄을 실행한다. 파싱·인자 오류는 저장소에 전달하지 않는다."""
    try:
        tokens = shlex.split(line)
    except ValueError:
        return SYNTAX_ERROR
    return _execute_tokens(tokens, store)


def _execute_tokens(tokens: List[str], store: MiniRedis) -> str:
    if not tokens:
        return ""
    original_command = tokens[0]
    command = original_command.upper()

    if command == "SET":
        if len(tokens) != 3:
            return _argument_error(original_command)
        try:
            store.set(tokens[1], tokens[2])
        except MemoryError as error:
            return str(error)
        return SUCCESS

    if command in ("GET", "DEL", "EXISTS", "TTL"):
        if len(tokens) != 2:
            return _argument_error(original_command)
        key = tokens[1]
        if command == "GET":
            value = store.get(key)
            return MISSING_VALUE if value is None else _quoted(value)
        if command == "DEL":
            return _integer_result(store.delete(key))
        if command == "EXISTS":
            return _integer_result(store.exists(key))
        return _integer_result(store.ttl(key))

    if command in ("DBSIZE", "KEYS"):
        if len(tokens) != 1:
            return _argument_error(original_command)
        if command == "DBSIZE":
            return _integer_result(store.dbsize())
        keys = store.keys()
        if not keys:
            return EMPTY_KEYS
        return "\n".join(
            f"{number}) {_quoted(key)}" for number, key in enumerate(keys, start=1)
        )

    if command == "EXPIRE":
        if len(tokens) != 3:
            return _argument_error(original_command)
        seconds = _parse_integer(tokens[2])
        if seconds is None:
            return INTEGER_ERROR
        return _integer_result(store.expire(tokens[1], seconds))

    if command == "CONFIG":
        if len(tokens) != 4:
            return _argument_error(original_command)
        if tokens[1].upper() != "SET" or tokens[2].lower() != "maxmemory":
            return SYNTAX_ERROR
        maxmemory = _parse_integer(tokens[3])
        if maxmemory is None or maxmemory < 0:
            return INTEGER_ERROR
        store.config_set_maxmemory(maxmemory)
        return SUCCESS

    if command == "INFO":
        if len(tokens) != 2:
            return _argument_error(original_command)
        if tokens[1].lower() != "memory":
            return SYNTAX_ERROR
        return store.info_memory()

    if command.lower() in EXIT_COMMANDS:
        if len(tokens) != 1:
            return _argument_error(original_command)
        return ""
    return f"(error) ERR unknown command '{original_command}'"


def run(store: Optional[MiniRedis] = None) -> None:
    """종료 명령이나 EOF/Ctrl+C를 받을 때까지 한 줄씩 처리한다."""
    if store is None:
        store = MiniRedis()
    while True:
        try:
            line = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            return
        try:
            tokens = shlex.split(line)
        except ValueError:
            print(SYNTAX_ERROR)
            continue
        if len(tokens) == 1 and tokens[0].lower() in EXIT_COMMANDS:
            return
        result = _execute_tokens(tokens, store)
        if result:
            print(result)
