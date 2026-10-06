// [v2] Minimal playable layer: grid movement, walls, key+door, pickups, bump-to-attack, exit.
// Deliberately NOT the full combat rules: the real rules live in game/world.py.
// EXERCISE (M10): have your agent port world.py combat to C#, then verify parity by replaying the same
// action list in both and comparing logs. Cross-language verification loop.
using System.Collections.Generic;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace Ember
{
    public class EmberGridPlayer : MonoBehaviour
    {
        public EmberLevelRuntime level;
        public int hitsToKill = 3;
        public Vector2Int pos;
        public List<string> inventory = new List<string>();
        string message = "WASD/arrows to move. Bump enemies to attack. Find the key, reach the exit.";
        readonly Dictionary<Vector2Int, int> damage = new Dictionary<Vector2Int, int>();
        bool won;

        void Start()
        {
            if (level == null) level = FindLevel();
            if (level == null || level.level == null) { Debug.LogWarning("[Ember] no EmberLevel in scene"); enabled = false; return; }
            for (int y = 0; y < level.level.Height; y++)
                for (int x = 0; x < level.level.Width; x++)
                    if (level.level.Tile(x, y) == '@') pos = new Vector2Int(x, y);
            transform.position = level.GridToWorld(pos.x, pos.y, 1f);
        }

        static EmberLevelRuntime FindLevel()
        {
            var root = GameObject.Find("EmberLevel");
            return root != null ? root.GetComponent<EmberLevelRuntime>() : null;
        }

        void Update()
        {
            if (won || level == null) return;
            Vector2Int d = ReadMove();
            if (d != Vector2Int.zero) Step(d);
        }

        Vector2Int ReadMove()
        {
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k == null) return Vector2Int.zero;
            if (k.wKey.wasPressedThisFrame || k.upArrowKey.wasPressedThisFrame) return new Vector2Int(0, -1);
            if (k.sKey.wasPressedThisFrame || k.downArrowKey.wasPressedThisFrame) return new Vector2Int(0, 1);
            if (k.aKey.wasPressedThisFrame || k.leftArrowKey.wasPressedThisFrame) return new Vector2Int(-1, 0);
            if (k.dKey.wasPressedThisFrame || k.rightArrowKey.wasPressedThisFrame) return new Vector2Int(1, 0);
#else
            if (Input.GetKeyDown(KeyCode.W) || Input.GetKeyDown(KeyCode.UpArrow)) return new Vector2Int(0, -1);
            if (Input.GetKeyDown(KeyCode.S) || Input.GetKeyDown(KeyCode.DownArrow)) return new Vector2Int(0, 1);
            if (Input.GetKeyDown(KeyCode.A) || Input.GetKeyDown(KeyCode.LeftArrow)) return new Vector2Int(-1, 0);
            if (Input.GetKeyDown(KeyCode.D) || Input.GetKeyDown(KeyCode.RightArrow)) return new Vector2Int(1, 0);
#endif
            return Vector2Int.zero;
        }

        void Step(Vector2Int d)
        {
            var next = pos + d;
            char t = level.level.Tile(next.x, next.y);
            if (level.enemies.TryGetValue(next, out var enemy) && enemy != null)
            {
                damage.TryGetValue(next, out int hits);
                hits++;
                damage[next] = hits;
                message = $"Hit {IdOf(enemy.name)} ({hits}/{hitsToKill})";
                if (hits >= hitsToKill) { Destroy(enemy); level.enemies.Remove(next); message += " - defeated!"; }
                return;
            }
            if (t == '#') { message = "Wall."; return; }
            if (t == 'D' && level.doors.ContainsKey(next))
            {
                int key = inventory.FindIndex(i => i.Contains("key"));
                if (key < 0) { message = "Locked. Need a key."; return; }
                inventory.RemoveAt(key);
                Destroy(level.doors[next]);
                level.doors.Remove(next);
                message = "Unlocked the door.";
            }
            pos = next;
            transform.position = level.GridToWorld(pos.x, pos.y, 1f);
            if (level.items.TryGetValue(pos, out var item) && item != null)
            {
                string id = IdOf(item.name);
                inventory.Add(id);
                Destroy(item);
                level.items.Remove(pos);
                message = $"Picked up {id}.";
            }
            if (t == '>') { won = true; message = "You escaped the Ember Crypt!"; }
        }

        // "Kind_some_id_x_y" -> "some_id"
        static string IdOf(string objName)
        {
            int first = objName.IndexOf('_');
            int lastY = objName.LastIndexOf('_');
            int lastX = objName.LastIndexOf('_', lastY - 1);
            return lastX > first ? objName.Substring(first + 1, lastX - first - 1) : objName;
        }

        void OnGUI()
        {
            GUI.Box(new Rect(10, 10, 520, 54), "");
            GUI.Label(new Rect(18, 14, 510, 22), message);
            GUI.Label(new Rect(18, 36, 510, 22), "Inventory: " + string.Join(", ", inventory));
        }
    }
}
