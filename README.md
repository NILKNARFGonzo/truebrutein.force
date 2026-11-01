# truebrutein.force

## A Metroid Password Generation Tool; The Original

I recently came across
[a video on YouTube talking about Metroid's password system][metroid-password-system-youtube]. I
looked around for online password generators for Metroid and couldn't find any,
so I decided to make my own.

The name comes from the end screen for Metroid, which asks the player to "pray
for a true peace in space".

This project was bootstrapped with
[Create React App](https://github.com/facebookincubator/create-react-app). I
got technical details on Metroid's password system from
[jdratlif's Password Format Guide][password-format-guide], and transliterated
some of the bit-munging from the source for [mpg][mpg], which is why this is
released under GPL 3.

## Python CLI

`metroid_password.py` is a dependency-free command-line tool for decoding,
validating, repairing, and editing original Metroid passwords. It preserves
the game's password alphabet, bit rotation, and checksum format.

```sh
python3 metroid_password.py show 000000000000000000000000
python3 metroid_password.py validate 000000000000000000000000
python3 metroid_password.py find-case "justin bailey------------"
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
prints the first candidate with both a valid checksum and a valid game state.
`fix-checksum` repairs a password and prints the corrected value. Editing accepts repeated options:
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
