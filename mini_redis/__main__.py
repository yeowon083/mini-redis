"""python -m mini_redis 실행 진입점."""

from .cli import run


def main() -> None:
    """명령 입력 반복을 시작한다."""
    run()


if __name__ == "__main__":
    main()
