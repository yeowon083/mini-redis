"""패키지가 독립 프로세스에서 안전하게 시작되는지 확인한다."""

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESS_TIMEOUT_SECONDS = 10


class StartupTests(unittest.TestCase):
    """실행 진입점과 패키지 가져오기의 기본 동작을 검증한다."""

    def test_module_starts_without_waiting_for_input(self) -> None:
        """입력 없는 실행도 종료되어 자동화 환경에서 멈추지 않아야 한다."""
        result = subprocess.run(
            [sys.executable, "-m", "mini_redis"],
            cwd=PROJECT_ROOT,
            input=b"",
            capture_output=True,
            timeout=PROCESS_TIMEOUT_SECONDS,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip())
        self.assertEqual(result.stderr, b"")

    def test_import_does_not_start_the_application(self) -> None:
        """모듈을 가져오기만 할 때는 출력이나 실행을 시작하지 않는다."""
        result = subprocess.run(
            [sys.executable, "-c", "import mini_redis; import mini_redis.__main__"],
            cwd=PROJECT_ROOT,
            input=b"",
            capture_output=True,
            timeout=PROCESS_TIMEOUT_SECONDS,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")
