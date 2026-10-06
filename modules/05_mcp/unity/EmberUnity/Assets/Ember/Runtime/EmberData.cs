// [v2] Plain data mirror of game/content.py Level schema. JsonUtility needs [Serializable] + public fields
// whose names match the JSON keys exactly (snake_case kept on purpose).
using System;

namespace Ember
{
    [Serializable]
    public class Placement
    {
        public string id;
        public int x;
        public int y;
    }

    [Serializable]
    public class LevelData
    {
        public string name;
        public string theme;
        public string[] map;
        public Placement[] enemies = new Placement[0];
        public Placement[] items = new Placement[0];
        public int threat_budget;

        public int Width => map != null && map.Length > 0 ? map[0].Length : 0;
        public int Height => map != null ? map.Length : 0;
        public char Tile(int x, int y) => (x < 0 || y < 0 || y >= Height || x >= Width) ? '#' : map[y][x];
    }
}
