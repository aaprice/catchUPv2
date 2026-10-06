# Ember Crypt feature backlog (Ralph works top to bottom)

- [ ] **Score**: `Game.score() -> int` = player xp + gold + 2*hp (if alive) + 100 if won. Test on a tiny level after a known sequence.
- [ ] **Resting**: action `wait` heals player +1 hp (not above max) ONLY if no living monster within Manhattan distance 4. Test both cases.
- [ ] **Poison**: optional `Enemy.poison: int = 0` (0..5, default 0 so existing JSON stays valid). When an enemy with poison>0 hits the player, player gets `poisoned` turns = poison; each player turn while poisoned: -1 hp, then decrement. Potion use cures poison. Add `"poisoned"` to `Game.status()`. Tests: hit applies, ticks, cure.
- [ ] **Status line**: `Game.status()["nearest_enemy"]` = `{"id","dist"}` of closest living monster (Manhattan) or `None`. Test.
- [ ] **Bot uses score**: `game.autoplay.play()` result includes `"score"` from `Game.score()`. Test level_01 bot result has score > 100.
