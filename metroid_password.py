#!/usr/bin/env python3
"""Inspect and edit Metroid (NES) passwords from the command line."""

import argparse
import itertools
import json
import sys


ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz?-"
PASSWORD_LENGTH = 24
BUFFER_LENGTH = 18

START_LOCATIONS = {
    "brinstar": (False, False, False),
    "norfair": (True, False, False),
    "kraidsLair": (False, True, False),
    "ridleysLair": (False, False, True),
    "tourian": (True, True, False),
}

POWER_UPS = {
    "morphball": (76, 0),
    "bombs": (72, 6),
    "longbeam": (74, None),
    "wavebeam": (78, None),
    "icebeam": (79, None),
    "screwattack": (75, 26),
    "variasuit": (77, 11),
    "hijumpboots": (73, 24),
}

AREAS = {
    "brinstar": {
        "missile": [1, 8],
        "energy": [4, 9, 12],
        "doors": {
            "longBeam": 2,
            "tourianBridge": 3,
            "bombs": 5,
            "iceBeam": 7,
            "varia": 10,
        },
    },
    "norfair": {
        "missile": [13, 14, 16, 17, 18, 19, 20, 21, 22, 27, 28, 31],
        "energy": [30],
        "doors": {"hiJumpBoots": 23, "screwAttack": 25, "waveBeam": 29, "iceBeam": 15},
    },
    "ridley": {
        "missile": [43, 46, 49],
        "energy": [45, 48],
        "doors": {"one": 44, "ridleysRoom": 47},
    },
    "kraid": {
        "missile": [33, 34, 39, 40],
        "energy": [36, 42],
        "doors": {"one": 32, "two": 35, "three": 37, "four": 38, "kraidsRoom": 41},
    },
    "tourian": {
        "doors": {"one": 50, "two": 51, "three": 52},
        "zebetite": [53, 54, 55, 56, 57],
    },
}

BOSSES = {"motherBrain": 58, "ridley": 124, "kraid": 126}
STATUES = {"ridley": 125, "kraid": 127}


class BitBuffer:
    """The game's 18-byte password data and its bit/checksum operations."""

    def __init__(self, data=None):
        self.data = list(data) if data is not None else [0] * BUFFER_LENGTH
        if len(self.data) != BUFFER_LENGTH:
            raise ValueError(f"Game state must contain exactly {BUFFER_LENGTH} bytes")
        if any(not isinstance(value, int) or value < 0 or value > 255 for value in self.data):
            raise ValueError("Game state bytes must be integers from 0 to 255")

    def get_bit(self, bit):
        if not isinstance(bit, int) or bit < 0 or bit >= BUFFER_LENGTH * 8:
            raise ValueError(f"Bit index {bit!r} out-of-bounds")
        return bool(self.data[bit // 8] & (1 << (bit % 8)))

    def set_bit(self, bit, value):
        if not isinstance(bit, int) or bit < 0 or bit >= BUFFER_LENGTH * 8:
            raise ValueError(f"Bit index {bit!r} out-of-bounds")
        mask = 1 << (bit % 8)
        if value:
            self.data[bit // 8] |= mask
        else:
            self.data[bit // 8] &= ~mask

    def fix_checksum(self):
        self.data[17] = sum(self.data[:17]) % 256

    def checksum_ok(self):
        return self.data[17] == sum(self.data[:17]) % 256

    def rotate(self, direction):
        amount = self.data[16] % 128
        if direction not in ("left", "right"):
            raise ValueError(f"Unknown bit rotation direction: {direction}")
        if amount == 0:
            return

        value = int.from_bytes(self.data[:16], "big")
        mask = (1 << 128) - 1
        if direction == "left":
            value = ((value << amount) | (value >> (128 - amount))) & mask
        else:
            value = ((value >> amount) | (value << (128 - amount))) & mask
        self.data[:16] = value.to_bytes(16, "big")


def _pack_characters(characters):
    packed = []
    for index in range(0, PASSWORD_LENGTH, 4):
        first, second, third, fourth = characters[index:index + 4]
        packed.extend((
            ((first << 2) | (second >> 4)) & 0xFF,
            ((second << 4) | (third >> 2)) & 0xFF,
            ((third << 6) | fourth) & 0xFF,
        ))
    return packed


def _unpack_bytes(data):
    characters = []
    for index in range(0, 18, 3):
        first, second, third = data[index:index + 3]
        characters.extend((
            first >> 2,
            ((first & 0x03) << 4) | (second >> 4),
            ((second & 0x0F) << 2) | (third >> 6),
            third & 0x3F,
        ))
    return characters


def password_to_buffer(password):
    if len(password) != PASSWORD_LENGTH:
        raise ValueError(f"Password must be exactly {PASSWORD_LENGTH} characters")
    characters = []
    for index, character in enumerate(password):
        if character == " ":
            characters.append(255)
        elif character in ALPHABET:
            characters.append(ALPHABET.index(character))
        else:
            raise ValueError(f"Invalid character {character!r} at position {index}")
    buffer = BitBuffer(_pack_characters(characters))
    buffer.rotate("left")
    return buffer


def buffer_to_password(buffer):
    duplicate = BitBuffer(buffer.data)
    duplicate.rotate("right")
    characters = _unpack_bytes(duplicate.data)
    output = []
    for index, character in enumerate(characters):
        if character == 255:
            output.append(" ")
        elif 0 <= character < len(ALPHABET):
            output.append(ALPHABET[character])
        else:
            raise ValueError(f"Invalid Metroid alphabet character {character} at position {index}")
    return "".join(output)


def parse_time(value):
    pieces = value.split(":")
    if len(pieces) != 3:
        raise ValueError("Time must use HH:MM:SS format")
    try:
        hours, minutes, seconds = (int(piece) for piece in pieces)
    except ValueError as error:
        raise ValueError("Time must use numeric HH:MM:SS values") from error
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError("Time must have nonnegative hours and minutes/seconds from 00 to 59")
    return hours * 3600 + minutes * 60 + seconds


def timer_seconds(buffer, refresh_rate):
    ticks = int.from_bytes(bytes(buffer.data[11:15]), "little")
    return ticks * 256 // refresh_rate


def set_timer_seconds(buffer, seconds, refresh_rate):
    ticks = (seconds * refresh_rate // 256) & 0xFFFFFFFF
    buffer.data[11:15] = ticks.to_bytes(4, "little")


def format_time(seconds):
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def game_state(buffer):
    start_bits = (buffer.get_bit(64), buffer.get_bit(65), buffer.get_bit(66))
    start_location = "invalid" if buffer.get_bit(67) else next(
        (name for name, bits in START_LOCATIONS.items() if bits == start_bits),
        "invalid",
    )
    powerups = {
        name: {
            "equipped": buffer.get_bit(equipped_bit),
            "taken": buffer.get_bit(taken_bit) if taken_bit is not None else None,
        }
        for name, (equipped_bit, taken_bit) in POWER_UPS.items()
    }
    areas = {}
    for name, configuration in AREAS.items():
        area = {}
        for kind in ("missile", "energy", "zebetite"):
            if kind in configuration:
                area[kind] = [buffer.get_bit(bit) for bit in configuration[kind]]
        if "doors" in configuration:
            area["doors"] = {
                door: buffer.get_bit(bit) for door, bit in configuration["doors"].items()
            }
        areas[name] = area
    return {
        "missiles": buffer.data[10],
        "startLocation": start_location,
        "reset": buffer.get_bit(67),
        "swimsuit": buffer.get_bit(71),
        "powerups": powerups,
        "items": areas,
        "bossesKilled": {name: buffer.get_bit(bit) for name, bit in BOSSES.items()},
        "statuesRaised": {name: buffer.get_bit(bit) for name, bit in STATUES.items()},
        "gameAge": {
            "ntsc": format_time(timer_seconds(buffer, 60)),
            "pal": format_time(timer_seconds(buffer, 50)),
        },
    }


def game_state_valid(buffer):
    return not buffer.get_bit(67) and (buffer.get_bit(76) or not buffer.get_bit(0))


def _checksum_difference(password):
    buffer = password_to_buffer(password)
    return (sum(buffer.data[:17]) - buffer.data[17]) % 256


def find_valid_capitalization(password):
    """Return a checksum- and game-valid capitalization, or None if absent."""
    normalized = "".join(password.split())
    if len(normalized) != PASSWORD_LENGTH:
        raise ValueError(f"Password must be exactly {PASSWORD_LENGTH} characters")
    if any(character not in ALPHABET for character in normalized):
        raise ValueError("Password contains a character outside the Metroid alphabet")

    lowercase = list(normalized.lower())
    case_positions = [
        index for index, character in enumerate(lowercase)
        if "a" <= character <= "z"
    ]

    # Password character 22-23 determine the rotation amount in byte 16.
    # Holding those case choices fixed makes the checksum contribution of each
    # remaining character independent, allowing a meet-in-the-middle search.
    fixed_positions = [index for index in (21, 22) if index in case_positions]
    variable_positions = [index for index in case_positions if index not in fixed_positions]
    fixed_choices = [
        (lowercase[index], lowercase[index].upper()) for index in fixed_positions
    ]

    for selected_fixed in itertools.product(*fixed_choices):
        base = lowercase.copy()
        for index, character in zip(fixed_positions, selected_fixed):
            base[index] = character
        base_difference = _checksum_difference("".join(base))
        deltas = []
        for index in variable_positions:
            changed = base.copy()
            changed[index] = changed[index].upper()
            deltas.append((_checksum_difference("".join(changed)) - base_difference) % 256)

        midpoint = len(deltas) // 2
        left_deltas = deltas[:midpoint]
        right_deltas = deltas[midpoint:]
        left_sums = {}
        for mask in range(1 << len(left_deltas)):
            total = sum(
                delta for bit, delta in enumerate(left_deltas) if mask & (1 << bit)
            ) % 256
            left_sums.setdefault(total, []).append(mask)

        for right_mask in range(1 << len(right_deltas)):
            right_total = sum(
                delta for bit, delta in enumerate(right_deltas)
                if right_mask & (1 << bit)
            ) % 256
            needed = (-base_difference - right_total) % 256
            for left_mask in left_sums.get(needed, ()):
                candidate = base.copy()
                for bit, index in enumerate(variable_positions[:midpoint]):
                    if left_mask & (1 << bit):
                        candidate[index] = candidate[index].upper()
                for bit, index in enumerate(variable_positions[midpoint:]):
                    if right_mask & (1 << bit):
                        candidate[index] = candidate[index].upper()
                candidate = "".join(candidate)
                buffer = password_to_buffer(candidate)
                if buffer.checksum_ok() and game_state_valid(buffer):
                    return candidate
    return None


def _set_indexed_item(buffer, specification, kind, value):
    try:
        area, item_kind, number = specification.split(":")
        number = int(number)
        if item_kind != kind:
            raise ValueError
        item_bits = AREAS[area][kind]
        if not 1 <= number <= len(item_bits):
            raise ValueError
        bit = item_bits[number - 1]
    except (KeyError, ValueError, IndexError) as error:
        raise ValueError(
            f"Invalid item {specification!r}; use AREA:{kind}:NUMBER"
        ) from error
    buffer.set_bit(bit, value)


def _set_door(buffer, specification, value):
    try:
        area, door = specification.split(":", 1)
        bit = AREAS[area]["doors"][door]
    except (KeyError, ValueError) as error:
        raise ValueError(f"Invalid door {specification!r}; use AREA:DOOR-NAME") from error
    buffer.set_bit(bit, value)


def apply_edits(buffer, args):
    if args.missiles is not None:
        buffer.data[10] = args.missiles
    if args.start_location:
        for bit, value in zip((64, 65, 66), START_LOCATIONS[args.start_location]):
            buffer.set_bit(bit, value)
    if args.swimsuit is not None:
        buffer.set_bit(71, args.swimsuit)
    for name in args.equip:
        equipped_bit, taken_bit = POWER_UPS[name]
        buffer.set_bit(equipped_bit, True)
        if taken_bit is not None:
            buffer.set_bit(taken_bit, True)
    for name in args.unequip:
        equipped_bit, taken_bit = POWER_UPS[name]
        buffer.set_bit(equipped_bit, False)
        if taken_bit is not None:
            buffer.set_bit(taken_bit, False)
    for specifications, kind, value in (
        (args.collect, "missile", True),
        (args.clear_item, "missile", False),
        (args.collect_energy, "energy", True),
        (args.clear_energy, "energy", False),
    ):
        for specification in specifications:
            _set_indexed_item(buffer, specification, kind, value)
    for specification in args.open_door:
        _set_door(buffer, specification, True)
    for specification in args.close_door:
        _set_door(buffer, specification, False)
    for name in args.kill_boss:
        buffer.set_bit(BOSSES[name], True)
    for name in args.revive_boss:
        buffer.set_bit(BOSSES[name], False)
    for name in args.raise_statue:
        buffer.set_bit(STATUES[name], True)
    for name in args.lower_statue:
        buffer.set_bit(STATUES[name], False)
    for index in args.zebetite_dead:
        buffer.set_bit(AREAS["tourian"]["zebetite"][index - 1], True)
    for index in args.zebetite_alive:
        buffer.set_bit(AREAS["tourian"]["zebetite"][index - 1], False)
    if args.ntsc_time:
        set_timer_seconds(buffer, parse_time(args.ntsc_time), 60)
    if args.pal_time:
        set_timer_seconds(buffer, parse_time(args.pal_time), 50)
    buffer.fix_checksum()


def add_edit_arguments(parser):
    parser.add_argument("--missiles", type=int, choices=range(256), metavar="0-255")
    parser.add_argument("--start-location", choices=START_LOCATIONS)
    parser.add_argument("--swimsuit", action="store_true", default=None)
    parser.add_argument("--no-swimsuit", dest="swimsuit", action="store_false")
    parser.add_argument("--equip", action="append", choices=POWER_UPS, default=[])
    parser.add_argument("--unequip", action="append", choices=POWER_UPS, default=[])
    parser.add_argument("--collect", action="append", default=[], metavar="AREA:missile:NUMBER")
    parser.add_argument("--clear-item", action="append", default=[], metavar="AREA:missile:NUMBER")
    parser.add_argument("--collect-energy", action="append", default=[], metavar="AREA:energy:NUMBER")
    parser.add_argument("--clear-energy", action="append", default=[], metavar="AREA:energy:NUMBER")
    parser.add_argument("--open-door", action="append", default=[], metavar="AREA:DOOR-NAME")
    parser.add_argument("--close-door", action="append", default=[], metavar="AREA:DOOR-NAME")
    parser.add_argument("--kill-boss", action="append", choices=BOSSES, default=[])
    parser.add_argument("--revive-boss", action="append", choices=BOSSES, default=[])
    parser.add_argument("--raise-statue", action="append", choices=STATUES, default=[])
    parser.add_argument("--lower-statue", action="append", choices=STATUES, default=[])
    parser.add_argument("--zebetite-dead", action="append", type=int, choices=range(1, 6), default=[])
    parser.add_argument("--zebetite-alive", action="append", type=int, choices=range(1, 6), default=[])
    parser.add_argument("--ntsc-time", metavar="HH:MM:SS")
    parser.add_argument("--pal-time", metavar="HH:MM:SS")
    parser.add_argument("--json", action="store_true", help="print the updated state as JSON")


def make_parser():
    parser = argparse.ArgumentParser(
        description="Inspect, validate, and edit original Metroid game passwords."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show", help="show a password's decoded game state")
    show.add_argument("password")
    show.add_argument("--json", action="store_true", help="print machine-readable JSON")
    validate = commands.add_parser("validate", help="check the checksum and game-state validity")
    validate.add_argument("password")
    find_case = commands.add_parser(
        "find-case",
        help="find a valid capitalization for a password with unknown letter case",
    )
    find_case.add_argument("password", help="24 characters; optional grouping whitespace is ignored")
    fix = commands.add_parser("fix-checksum", help="repair a password's checksum")
    fix.add_argument("password")
    edit = commands.add_parser("edit", help="edit game state and print a new password")
    edit.add_argument("password")
    add_edit_arguments(edit)
    return parser


def run(args):
    if args.command == "find-case":
        candidate = find_valid_capitalization(args.password)
        if candidate is None:
            print("No valid capitalization found.", file=sys.stderr)
            return 1
        print(candidate)
        return 0

    buffer = password_to_buffer(args.password)
    if args.command == "validate":
        checksum_ok = buffer.checksum_ok()
        state_valid = game_state_valid(buffer)
        if checksum_ok and state_valid:
            print("Password checksum and game state are valid.")
            return 0
        problems = []
        if not checksum_ok:
            problems.append("checksum is invalid")
        if not state_valid:
            problems.append("game state is invalid")
        print("Password invalid: " + "; ".join(problems), file=sys.stderr)
        return 1
    if args.command == "fix-checksum":
        buffer.fix_checksum()
        print(buffer_to_password(buffer))
        return 0
    if args.command == "edit":
        apply_edits(buffer, args)
        if args.json:
            print(json.dumps({
                "password": buffer_to_password(buffer),
                "checksumOK": buffer.checksum_ok(),
                "valid": game_state_valid(buffer),
                "gameState": game_state(buffer),
            }, indent=2))
        else:
            print(buffer_to_password(buffer))
        return 0

    valid = game_state_valid(buffer)
    if args.json:
        print(json.dumps({
            "password": buffer_to_password(buffer),
            "checksumOK": buffer.checksum_ok(),
            "valid": valid,
            "gameState": game_state(buffer),
        }, indent=2))
    else:
        print(f"Password: {buffer_to_password(buffer)}")
        print(f"Checksum: {'valid' if buffer.checksum_ok() else 'invalid'}")
        print(f"Game state: {'valid' if valid else 'invalid'}")
        print(json.dumps(game_state(buffer), indent=2))
    return 0


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (ValueError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
