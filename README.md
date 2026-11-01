# truebrutein.force

## DISCAIMER

This is a fork of alexras/truepeacein.space. It is not marked so. My mistake.

## Python CLI

`metroid_password.py` is a dependency-free command-line tool for decoding,
validating, repairing, and editing original Metroid passwords. It preserves
the game's password alphabet, bit rotation, and checksum format.

```sh
python3 metroid_password.py show 000000000000000000000000
python3 metroid_password.py validate 000000000000000000000000
python3 metroid_password.py find-case "0000 0000 0000 4000 0000 000g"
python3 metroid_password.py find-case "eating crayon isvery tastys" --sort missiles
python3 metroid_password.py edit 000000000000000000000000 \
  --missiles 120 \
  --equip morphball \
  --collect brinstar:missile:1 \
  --open-door brinstar:longBeam \
  --start-location norfair \
  --ntsc-time 00:25:00
```

`show --json` prints the decoded game state as JSON. `find-case` ignores
whitespace used to group a password, tries all letter capitalizations, and
prints every candidate with a valid checksum and conservative game-state
checks: no reset flag, a recognized start location, an accessible Morph Ball,
with no game-time limit. Candidates are sorted by NTSC hours ascending by
default; `--sort` accepts `hours`, `ntsc`, `pal`, `missiles`, `items`,
`powerups`, `bosses`, or `location`, all ascending. Each candidate includes
its timer, missile count, collected-item count, equipped power-ups, defeated
bosses, and start location. If no candidate passes these checks, it refuses to
produce a password. These checks reduce the chance of producing a dangerous
password but cannot guarantee that every game copy or emulator will accept it
or avoid a crash. Only use passwords from sources you trust and keep a
save-state or other backup.
`fix-checksum` and `edit` also refuse to output a password that fails these
game-state checks. Editing accepts repeated options:
`--collect AREA:missile:NUMBER` and `--collect-energy AREA:energy:NUMBER` mark
items collected (numbers are one-based); `--clear-item` and `--clear-energy`
remove them. `--open-door`/`--close-door`, `--equip`/`--unequip`,
`--kill-boss`/`--revive-boss`, `--raise-statue`/`--lower-statue`, and
`--zebetite-dead`/`--zebetite-alive` update their corresponding game state.
`--swimsuit` and `--no-swimsuit` toggle the swimsuit flag, and `--pal-time`
sets the PAL timer. Every edit recalculates the password checksum.

Run the focused Python tests with:

```sh
python3 -m unittest -v
```

[metroid-password-system-youtube]: https://youtu.be/Q3M_c_PzC2A
[password-format-guide]: http://games.technoplaza.net/mpg/password.txt
[mpg]: http://games.technoplaza.net/mpg/
