import contextlib
import io
import json
import unittest

import metroid_password as metroid


class PasswordFormatTests(unittest.TestCase):
    @staticmethod
    def password_from_raw_buffer(buffer):
        buffer.fix_checksum()
        return metroid.buffer_to_password(buffer)

    def test_known_password_vectors(self):
        cases = (
            (
                "000000000000000000000000",
                [0] * 18,
            ),
            (
                "00000000000A00000000000A",
                [0, 0, 0, 0, 0, 0, 0, 0, 10, 0, 0, 0, 0, 0, 0, 0, 0, 10],
            ),
            (
                "JUSTINBAILEY------------",
                [166, 243, 142, 164, 185, 101, 36, 169, 209, 127,
                 255, 255, 255, 255, 255, 255, 255, 255],
            ),
        )
        for password, expected in cases:
            with self.subTest(password=password):
                buffer = metroid.password_to_buffer(password)
                self.assertEqual(buffer.data, expected)
                self.assertEqual(metroid.buffer_to_password(buffer), password)

    def test_checksum_and_validity_known_vectors(self):
        valid = metroid.password_to_buffer("000000000000000000000000")
        self.assertTrue(valid.checksum_ok())
        self.assertTrue(metroid.game_state_valid(valid))

        invalid_checksum = metroid.password_to_buffer("bogusBOGUSbogusBOGUSbogu")
        self.assertFalse(invalid_checksum.checksum_ok())
        self.assertFalse(metroid.game_state_valid(invalid_checksum))

        invalid_reset_state = metroid.password_to_buffer("00000000000A00000000000A")
        self.assertTrue(invalid_reset_state.checksum_ok())
        self.assertFalse(metroid.game_state_valid(invalid_reset_state))

        invalid_morphball_state = metroid.password_to_buffer("0G0000000000000000000001")
        self.assertTrue(invalid_morphball_state.checksum_ok())
        self.assertFalse(metroid.game_state_valid(invalid_morphball_state))

        accessible_morphball_state = metroid.password_to_buffer("0G000000000040000000000H")
        self.assertTrue(accessible_morphball_state.checksum_ok())
        self.assertTrue(metroid.game_state_valid(accessible_morphball_state))

    def test_checksum_repair_round_trips(self):
        buffer = metroid.password_to_buffer("bogusBOGUSbogusBOGUSbogu")
        buffer.fix_checksum()
        self.assertTrue(buffer.checksum_ok())
        self.assertEqual(len(metroid.buffer_to_password(buffer)), 24)

    def test_password_validation(self):
        with self.assertRaisesRegex(ValueError, "exactly 24"):
            metroid.password_to_buffer("short")
        with self.assertRaisesRegex(ValueError, "Invalid character"):
            metroid.password_to_buffer("!" * 24)

    def test_find_case_yields_all_safe_capitalizations(self):
        candidates = list(metroid.find_valid_capitalizations("00000000000040000000000g"))
        self.assertGreater(len(candidates), 0)
        for candidate in candidates:
            buffer = metroid.password_to_buffer(candidate)
            self.assertTrue(buffer.checksum_ok())
            self.assertTrue(metroid.game_state_valid(buffer))
            self.assertEqual(len(candidate), 24)

    def test_safety_checks_allow_long_timer(self):
        buffer = metroid.BitBuffer()
        buffer.set_bit(76, True)
        buffer.data[11:15] = (1_000_000_000).to_bytes(4, "little")
        password = self.password_from_raw_buffer(buffer)
        decoded = metroid.password_to_buffer(password)
        self.assertTrue(decoded.checksum_ok())
        self.assertTrue(metroid.game_state_valid(decoded))

    def test_find_case_rejects_the_previously_risky_candidate(self):
        buffer = metroid.password_to_buffer("EAtINGcrAyOniSverytastYs")
        self.assertTrue(buffer.checksum_ok())
        self.assertFalse(metroid.game_state_valid(buffer))

    def test_find_case_reports_no_match_when_case_cannot_change_input(self):
        self.assertEqual(list(metroid.find_valid_capitalizations("0" * 23 + "1")), [])

    def test_find_case_requires_24_password_characters(self):
        with self.assertRaisesRegex(ValueError, "exactly 24"):
            list(metroid.find_valid_capitalizations("too short"))

    def test_safety_checks_reject_invalid_start_flags(self):
        buffer = metroid.BitBuffer()
        buffer.set_bit(65, True)
        buffer.set_bit(66, True)
        password = self.password_from_raw_buffer(buffer)
        decoded = metroid.password_to_buffer(password)
        self.assertTrue(decoded.checksum_ok())
        self.assertFalse(metroid.game_state_valid(decoded))

class GameStateTests(unittest.TestCase):
    def test_game_state_fields_round_trip(self):
        args = metroid.make_parser().parse_args([
            "edit", "0" * 24,
            "--missiles", "42",
            "--start-location", "norfair",
            "--swimsuit",
            "--equip", "morphball",
            "--equip", "longbeam",
            "--collect", "brinstar:missile:2",
            "--collect-energy", "kraid:energy:2",
            "--open-door", "brinstar:tourianBridge",
            "--kill-boss", "motherBrain",
            "--raise-statue", "ridley",
            "--zebetite-dead", "5",
            "--ntsc-time", "01:02:03",
        ])
        buffer = metroid.password_to_buffer(args.password)
        metroid.apply_edits(buffer, args)
        state = metroid.game_state(buffer)

        self.assertEqual(state["missiles"], 42)
        self.assertEqual(state["startLocation"], "norfair")
        self.assertTrue(state["swimsuit"])
        self.assertTrue(state["powerups"]["morphball"]["equipped"])
        self.assertTrue(state["powerups"]["morphball"]["taken"])
        self.assertTrue(state["powerups"]["longbeam"]["equipped"])
        self.assertTrue(state["items"]["brinstar"]["missile"][1])
        self.assertTrue(state["items"]["kraid"]["energy"][1])
        self.assertTrue(state["items"]["brinstar"]["doors"]["tourianBridge"])
        self.assertTrue(state["items"]["tourian"]["zebetite"][4])
        self.assertTrue(state["bossesKilled"]["motherBrain"])
        self.assertTrue(state["statuesRaised"]["ridley"])
        self.assertEqual(state["gameAge"]["ntsc"], "01:02:00")
        self.assertTrue(buffer.checksum_ok())
        updated_password = metroid.buffer_to_password(buffer)
        decoded_again = metroid.password_to_buffer(updated_password)
        self.assertEqual(decoded_again.data, buffer.data)

    def test_timers_use_the_same_tick_counter(self):
        buffer = metroid.BitBuffer()
        buffer.data[11:15] = bytes([0x89, 0xAB, 0xCD, 0xEF])
        self.assertEqual(metroid.timer_seconds(buffer, 60), 0xEFCDAB89 * 256 // 60)
        self.assertEqual(metroid.timer_seconds(buffer, 50), 0xEFCDAB89 * 256 // 50)

    def test_invalid_item_and_time_are_reported(self):
        buffer = metroid.BitBuffer()
        with self.assertRaisesRegex(ValueError, "Invalid item"):
            metroid._set_indexed_item(buffer, "brinstar:missile:99", "missile", True)
        with self.assertRaisesRegex(ValueError, "minutes/seconds"):
            metroid.parse_time("01:60:00")


class CommandLineTests(unittest.TestCase):
    def test_show_json_includes_decoded_state(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = metroid.main(["show", "0" * 24, "--json"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertTrue(payload["checksumOK"])
        self.assertEqual(payload["gameState"]["startLocation"], "brinstar")

    def test_validate_reports_bad_checksum(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = metroid.main(["validate", "bogusBOGUSbogusBOGUSbogu"])
        self.assertEqual(result, 1)
        self.assertIn("checksum is invalid", stderr.getvalue())

    def test_find_case_command_accepts_grouped_lowercase(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = metroid.main(["find-case", "0000 0000 0000 4000 0000 000g"])
        self.assertEqual(result, 0)
        lines = stdout.getvalue().splitlines()
        candidates = [line for line in lines if line and not line.startswith(" ")]
        self.assertGreater(len(candidates), 0)
        for candidate in candidates:
            buffer = metroid.password_to_buffer(candidate)
            self.assertTrue(buffer.checksum_ok())
            self.assertTrue(metroid.game_state_valid(buffer))
        self.assertIn("NTSC:", stdout.getvalue())
        self.assertIn("Missiles:", stdout.getvalue())
        self.assertIn("Equipped:", stdout.getvalue())
        self.assertIn("Defeated:", stdout.getvalue())

    def test_find_case_command_lists_all_safe_results(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = metroid.main(["find-case", "eating crayon isvery tastys"])
        self.assertEqual(result, 0)
        lines = stdout.getvalue().splitlines()
        candidates = [line for line in lines if line and not line.startswith(" ")]
        self.assertGreater(len(candidates), 1)
        for candidate in candidates:
            buffer = metroid.password_to_buffer(candidate)
            self.assertTrue(buffer.checksum_ok())
            self.assertTrue(metroid.game_state_valid(buffer))
        ntsc_ages = [
            metroid.parse_time(line.split("NTSC: ", 1)[1].split(" |", 1)[0])
            for line in lines
            if line.startswith("  NTSC: ")
        ]
        self.assertEqual(ntsc_ages, sorted(ntsc_ages))

    def test_find_case_sorts_by_requested_stat(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = metroid.main([
                "find-case",
                "eating crayon isvery tastys",
                "--sort",
                "missiles",
            ])
        self.assertEqual(result, 0)
        missile_counts = [
            int(line.split("Missiles: ", 1)[1].split(" |", 1)[0])
            for line in stdout.getvalue().splitlines()
            if line.startswith("  Missiles: ")
        ]
        self.assertGreater(len(missile_counts), 1)
        self.assertEqual(missile_counts, sorted(missile_counts))

    def test_edit_emits_a_valid_updated_password(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = metroid.main(["edit", "0" * 24, "--missiles", "27"])
        output = stdout.getvalue().strip()
        self.assertEqual(result, 0)
        self.assertTrue(metroid.password_to_buffer(output).checksum_ok())
        self.assertEqual(metroid.game_state(metroid.password_to_buffer(output))["missiles"], 27)

    def test_edit_allows_long_game_timer(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = metroid.main(["edit", "0" * 24, "--ntsc-time", "1000:00:00"])
        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        buffer = metroid.password_to_buffer(stdout.getvalue().strip())
        self.assertTrue(metroid.game_state_valid(buffer))
        self.assertGreater(metroid.timer_seconds(buffer, 60), 999 * 60 * 60)

    def test_fix_checksum_refuses_unsafe_state(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = metroid.main(["fix-checksum", "EAtINGcrAyOniSverytastYs"])
        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Refusing to output", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
