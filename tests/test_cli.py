"""명령의 공개 동작과 REPL 복구를 저장소 구현과 함께 검증한다."""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import call, patch

from mini_redis.cli import execute_command, run
from mini_redis.store import MiniRedis
from tests.test_store_ttl import FakeClock


SYNTAX_ERROR = "(error) ERR syntax error"
INTEGER_ERROR = "(error) ERR value is not an integer or out of range"
PROMPT = "mini-redis> "
MAX_SIGNED_INTEGER = 2 ** 63 - 1
MIN_SIGNED_INTEGER = -(2 ** 63)


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.store = MiniRedis(clock=self.clock)

    def execute(self, line: str) -> str:
        return execute_command(line, self.store)

    def test_whitespace_is_ignored(self) -> None:
        for line in ("", " ", "\t  \n"):
            with self.subTest(line=line):
                self.assertEqual(self.execute(line), "")

    def test_set_get_overwrite_and_missing_value(self) -> None:
        self.assertEqual(self.execute("GET missing"), "(nil)")
        self.assertEqual(self.execute("SET name Alice"), "OK")
        self.assertEqual(self.execute("GET name"), '"Alice"')
        self.assertEqual(self.execute('SET name "Bob Smith"'), "OK")
        self.assertEqual(self.execute("GET name"), '"Bob Smith"')
        self.assertEqual(self.execute("DBSIZE"), "(integer) 1")

    def test_empty_key_and_value_are_valid_strings(self) -> None:
        self.assertEqual(self.execute('SET "" ""'), "OK")
        self.assertEqual(self.execute('GET ""'), '""')
        self.assertEqual(self.execute("KEYS"), '1) ""')
        self.assertEqual(self.execute("INFO memory"),
                         "used_memory:0\nmaxmemory:0\nevicted_keys:0")

    def test_command_case_does_not_change_key_case(self) -> None:
        self.assertEqual(self.execute("sEt Name Alice"), "OK")
        self.assertEqual(self.execute("gEt Name"), '"Alice"')
        self.assertEqual(self.execute("GET name"), "(nil)")
        self.assertEqual(self.execute("cOnFiG sEt MaXmEmOrY 100"), "OK")
        self.assertIn("maxmemory:100", self.execute("iNfO MeMoRy"))

    def test_delete_exists_and_database_size_format_integers(self) -> None:
        self.assertEqual(self.execute("EXISTS a"), "(integer) 0")
        self.execute("SET a value")
        self.assertEqual(self.execute("EXISTS a"), "(integer) 1")
        self.assertEqual(self.execute("DEL a"), "(integer) 1")
        self.assertEqual(self.execute("DEL a"), "(integer) 0")
        self.assertEqual(self.execute("DBSIZE"), "(integer) 0")

    def test_keys_are_numbered_and_values_are_escaped(self) -> None:
        expected_keys = ['a"b', "한 글", "back\\slash", "line\nkey"]
        for key in expected_keys:
            self.store.set(key, "value")
        lines = self.execute("KEYS").splitlines()
        returned_keys = []
        for number, line in enumerate(lines, start=1):
            prefix = f"{number}) "
            self.assertTrue(line.startswith(prefix))
            returned_keys.append(json.loads(line[len(prefix):]))
        self.assertCountEqual(returned_keys, expected_keys)

    def test_empty_keys_result(self) -> None:
        self.assertEqual(self.execute("KEYS"), "(empty array)")

    def test_get_escapes_quotes_slashes_and_control_characters(self) -> None:
        self.store.set("key", '한글 "quote" \\ \n\t\r')
        self.assertEqual(self.execute("GET key"),
                         '"한글 \\"quote\\" \\\\ \\n\\t\\r"')

    def test_single_double_quotes_and_literal_hash_are_supported(self) -> None:
        for command, expected in (
            ('SET key "hello world"', "hello world"),
            ("SET key 'hello world'", "hello world"),
            (r'SET key "say \"hi\""', 'say "hi"'),
            ("SET key #value", "#value"),
        ):
            with self.subTest(command=command):
                self.assertEqual(self.execute(command), "OK")
                self.assertEqual(json.loads(self.execute("GET key")), expected)

    def test_unknown_command_reports_original_case(self) -> None:
        self.assertEqual(self.execute("NoSuch value"),
                         "(error) ERR unknown command 'NoSuch'")

    def test_argument_counts_for_all_commands(self) -> None:
        for command in (
            "SET", "SET key", "SET key value extra", "gEt", "GET a b",
            "DEL", "DEL a b", "EXISTS", "EXISTS a b", "DBSIZE extra",
            "KEYS *", "EXPIRE", "EXPIRE key", "EXPIRE key 1 extra",
            "TTL", "TTL a b", "CONFIG", "CONFIG SET maxmemory",
            "CONFIG SET maxmemory 10 extra", "INFO", "INFO memory extra",
            "exit extra", "QUIT extra",
        ):
            with self.subTest(command=command):
                original_name = command.split()[0]
                self.assertEqual(
                    self.execute(command),
                    f"(error) ERR wrong number of arguments for '{original_name}' command",
                )

    def test_argument_count_error_precedes_integer_error(self) -> None:
        for command in ("EXPIRE key nope extra", "CONFIG SET maxmemory nope extra"):
            with self.subTest(command=command):
                self.assertIn("wrong number of arguments", self.execute(command))

    def test_malformed_quotes_and_subcommands_report_syntax_errors(self) -> None:
        for command in ('SET key "unfinished', "SET key trailing\\",
                        "CONFIG GET maxmemory 1", "CONFIG SET other 1", "INFO other"):
            with self.subTest(command=command):
                self.assertEqual(self.execute(command), SYNTAX_ERROR)

    def test_invalid_integer_forms_do_not_change_existing_state(self) -> None:
        self.execute("SET key value")
        self.execute("EXPIRE key 10")
        self.execute("CONFIG SET maxmemory 100")
        invalid_numbers = (
            "1.5", "1_0", "1e2", "１２", "١٢", "true", "+", "-", "0x10",
            "++1", "--1", "1-", '" 1"', '"1 "',
            str(MAX_SIGNED_INTEGER + 1), str(MIN_SIGNED_INTEGER - 1), "9" * 5000,
        )
        for number in invalid_numbers:
            for prefix in ("EXPIRE key", "CONFIG SET maxmemory"):
                with self.subTest(prefix=prefix, number=number[:30]):
                    self.assertEqual(self.execute(f"{prefix} {number}"), INTEGER_ERROR)
        self.assertEqual(self.store.maxmemory, 100)
        self.assertEqual(self.execute("TTL key"), "(integer) 10")
        self.assertEqual(self.execute("GET key"), '"value"')

    def test_signed_integer_boundaries_and_leading_zeroes(self) -> None:
        self.assertEqual(self.execute(f"CONFIG SET maxmemory +{MAX_SIGNED_INTEGER}"), "OK")
        self.assertEqual(self.store.maxmemory, MAX_SIGNED_INTEGER)
        self.assertEqual(self.execute("CONFIG SET maxmemory -1"), INTEGER_ERROR)
        self.assertEqual(self.execute("CONFIG SET maxmemory -0"), "OK")
        self.assertEqual(self.execute("CONFIG SET maxmemory +" + "0" * 5000 + "12"), "OK")
        self.assertEqual(self.store.maxmemory, 12)
        self.execute("SET key value")
        self.assertEqual(self.execute(f"EXPIRE key {MAX_SIGNED_INTEGER}"), "(integer) 1")
        self.assertEqual(self.execute(f"EXPIRE key {MIN_SIGNED_INTEGER}"), "(integer) 1")
        self.assertEqual(self.execute("GET key"), "(nil)")

    def test_spec_lru_example_reports_twenty_two_bytes_and_one_eviction(self) -> None:
        self.assertEqual(self.execute("CONFIG SET maxmemory 30"), "OK")
        self.execute("SET user:1 Alice")
        self.execute("SET user:2 Bob")
        self.assertEqual(self.execute("GET user:2"), '"Bob"')
        self.execute("SET user:3 Charlie")
        self.assertEqual(self.execute("GET user:1"), "(nil)")
        self.assertEqual(self.execute("INFO memory"),
                         "used_memory:22\nmaxmemory:30\nevicted_keys:1")

    def test_oom_returns_store_message_and_preserves_value_and_ttl(self) -> None:
        self.execute("SET key value")
        self.execute("EXPIRE key 10")
        self.execute("CONFIG SET maxmemory 8")
        self.assertEqual(self.execute("SET key toolarge"),
                         "(error) OOM command not allowed when used_memory > 'maxmemory'")
        self.assertEqual(self.execute("GET key"), '"value"')
        self.assertEqual(self.execute("TTL key"), "(integer) 10")
        self.assertEqual(self.execute("INFO memory"),
                         "used_memory:8\nmaxmemory:8\nevicted_keys:0")

    def test_ttl_expiration_and_memory_cleanup_through_commands(self) -> None:
        self.assertEqual(self.execute("TTL key"), "(integer) -2")
        self.execute("SET key value")
        self.assertEqual(self.execute("TTL key"), "(integer) -1")
        self.assertEqual(self.execute("EXPIRE missing 1"), "(integer) 0")
        self.assertEqual(self.execute("EXPIRE key 2"), "(integer) 1")
        self.clock.now += 1.25
        self.assertEqual(self.execute("TTL key"), "(integer) 0")
        self.clock.now += 0.75
        self.assertEqual(self.execute("GET key"), "(nil)")
        self.assertEqual(self.execute("KEYS"), "(empty array)")
        self.assertEqual(self.execute("DBSIZE"), "(integer) 0")
        self.assertEqual(self.execute("INFO memory"),
                         "used_memory:0\nmaxmemory:0\nevicted_keys:0")

    def test_overwrite_clears_ttl_and_expired_keys_do_not_cause_eviction(self) -> None:
        self.execute("CONFIG SET maxmemory 4")
        self.execute("SET a x")
        self.execute("EXPIRE a 1")
        self.clock.now += 1
        self.execute("SET b xx")
        self.assertEqual(self.execute("INFO memory"),
                         "used_memory:3\nmaxmemory:4\nevicted_keys:0")
        self.execute("EXPIRE b 2")
        self.execute("SET b x")
        self.clock.now += 2
        self.assertEqual(self.execute("GET b"), '"x"')
        self.assertEqual(self.execute("TTL b"), "(integer) -1")

    def test_nonpositive_expire_is_immediate(self) -> None:
        for seconds in ("0", "-1"):
            self.execute("SET key value")
            self.assertEqual(self.execute("EXPIRE key " + seconds), "(integer) 1")
            self.assertEqual(self.execute("EXISTS key"), "(integer) 0")

    def test_execute_exit_returns_empty_without_terminating_caller(self) -> None:
        self.assertEqual(self.execute("exit"), "")
        self.assertEqual(self.execute("QUIT"), "")
        self.assertEqual(self.execute("SET a value"), "OK")


class ReplTests(unittest.TestCase):
    def test_errors_and_blank_input_do_not_prevent_later_commands(self) -> None:
        commands = ["", 'SET key "broken', "UNKNOWN", "exit extra", "SET key value", "GET key", "quit"]
        output = io.StringIO()
        with patch("builtins.input", side_effect=commands) as mocked_input:
            with redirect_stdout(output):
                run()
        self.assertEqual(output.getvalue().splitlines(), [
            SYNTAX_ERROR,
            "(error) ERR unknown command 'UNKNOWN'",
            "(error) ERR wrong number of arguments for 'exit' command",
            "OK", '"value"',
        ])
        self.assertEqual(mocked_input.call_args_list, [call(PROMPT)] * len(commands))

    def test_exit_and_quit_stop_without_consuming_following_input(self) -> None:
        for command in ("exit", "QuIt"):
            with self.subTest(command=command):
                output = io.StringIO()
                with patch("builtins.input", side_effect=[command, "SET key value"]) as mocked_input:
                    with redirect_stdout(output):
                        run()
                self.assertEqual(mocked_input.call_count, 1)
                self.assertEqual(output.getvalue(), "")

    def test_eof_and_keyboard_interrupt_exit_with_newline(self) -> None:
        for exception in (EOFError, KeyboardInterrupt):
            with self.subTest(exception=exception):
                output = io.StringIO()
                with patch("builtins.input", side_effect=exception):
                    with redirect_stdout(output):
                        self.assertIsNone(run())
                self.assertEqual(output.getvalue(), "\n")

    def test_run_uses_supplied_store(self) -> None:
        store = MiniRedis()
        output = io.StringIO()
        with patch("builtins.input", side_effect=["SET key value", "quit"]):
            with redirect_stdout(output):
                run(store)
        self.assertEqual(store.get("key"), "value")
        self.assertEqual(output.getvalue(), "OK\n")
