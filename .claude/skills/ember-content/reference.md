# Ember content reference (loaded on demand — progressive disclosure)

## Item
| field | rule |
|---|---|
| id | `^[a-z][a-z0-9_]{1,31}$`, unique |
| kind | weapon / armor / potion / key / trinket |
| power | 0..20. weapon=+atk, armor=+def, potion heals power*5, key/trinket=0 |
| value | 0..500 gold. weapon/armor value >= power*8 |
| description | 5..200 chars |

## Enemy
| field | rule |
|---|---|
| hp 1..60, atk 1..15, defense 0..10, xp 1..100 | |
| loot | existing item ids |
| threat (derived) | hp//4 + atk*2 + defense*2. Good range 5..30 |

## Level
- `map`: list of equal-length strings; legend `#` wall `.` floor `@` start (1) `>` exit (1) `D` locked door.
- Border all `#`. Placements (`enemies`, `items`: `{id,x,y}`) only on `.` cells, no overlaps. x = column, y = row (0-based).
- Door gating: if exit behind `D`, a `kind=key` item must be reachable without passing `D` (or dropped by enemy — validator only counts floor keys).
- Sum enemy threat <= `threat_budget`.

## Player baseline
hp 30, atk 4, def 1. Damage = max(1, atk - def). Player swings first.

## Example level (tiny, valid)
```json
{"name":"Rat Nest","theme":"damp ossuary","threat_budget":30,
 "map":["##########","#@...#...#","#.##.#.#.#","#....D.#>#","##########"],
 "enemies":[{"id":"crypt_rat","x":6,"y":1}],
 "items":[{"id":"iron_key","x":1,"y":3}]}
```
