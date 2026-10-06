// [v2] Attached to the "EmberLevel" root by the editor builder. Holds level data + grid<->world mapping
// so runtime scripts (player, NPC) can reason in GRID coordinates, same as the Python sim.
using System.Collections.Generic;
using UnityEngine;

namespace Ember
{
    public class EmberLevelRuntime : MonoBehaviour
    {
        public LevelData level;
        public float tile = 2f;

        // live state (runtime only)
        [System.NonSerialized] public Dictionary<Vector2Int, GameObject> items = new Dictionary<Vector2Int, GameObject>();
        [System.NonSerialized] public Dictionary<Vector2Int, GameObject> enemies = new Dictionary<Vector2Int, GameObject>();
        [System.NonSerialized] public Dictionary<Vector2Int, GameObject> doors = new Dictionary<Vector2Int, GameObject>();

        // grid (x right, y down) -> world (X right, Z forward/up-screen). Y is height.
        public Vector3 GridToWorld(int x, int y, float height = 0f) => new Vector3(x * tile, height, -y * tile);

        void Awake()
        {
            // rebuild lookup from child names written by the builder: Kind_id_x_y
            foreach (Transform child in transform)
            {
                var parts = child.name.Split('_');
                if (parts.Length < 3) continue;
                if (!int.TryParse(parts[parts.Length - 2], out int gx) || !int.TryParse(parts[parts.Length - 1], out int gy)) continue;
                var key = new Vector2Int(gx, gy);
                if (parts[0] == "Item") items[key] = child.gameObject;
                else if (parts[0] == "Enemy") enemies[key] = child.gameObject;
                else if (parts[0] == "Door") doors[key] = child.gameObject;
            }
        }
    }
}
