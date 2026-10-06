// [v2] Editor-side builder: Ember level JSON -> grey-box scene (walls, doors, markers, enemies, items, player, camera).
// Menu: Ember > Import Level JSON...   |   Ember > Clear Level
// Also called by EmberBridge (TCP) so agents can build levels through MCP.
using System.Collections.Generic;
using System.IO;
using Ember;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class EmberLevelBuilder
{
    public const string RootName = "EmberLevel";
    const string MatDir = "Assets/Ember/Generated";

    static readonly Dictionary<string, Color> Colors = new Dictionary<string, Color>
    {
        { "wall", new Color(0.18f, 0.16f, 0.15f) }, { "floor", new Color(0.35f, 0.30f, 0.26f) },
        { "door", new Color(0.55f, 0.30f, 0.08f) }, { "start", new Color(0.1f, 0.8f, 0.2f) },
        { "exit", new Color(0.1f, 0.4f, 0.95f) }, { "enemy", new Color(0.85f, 0.1f, 0.05f) },
        { "item", new Color(0.95f, 0.8f, 0.1f) }, { "prop", new Color(0.6f, 0.55f, 0.5f) },
        { "ember", new Color(1f, 0.35f, 0f) }, { "player", new Color(0.2f, 0.9f, 0.9f) },
    };

    [MenuItem("Ember/Import Level JSON...")]
    static void ImportMenu()
    {
        string path = EditorUtility.OpenFilePanel("Ember level JSON (game/data/...)", "", "json");
        if (string.IsNullOrEmpty(path)) return;
        var lv = JsonUtility.FromJson<LevelData>(File.ReadAllText(path));
        Debug.Log("[Ember] " + Build(lv, 2f, 3f));
    }

    [MenuItem("Ember/Clear Level")]
    static void ClearMenu() => Debug.Log("[Ember] " + Clear());

    public static string Clear()
    {
        var root = GameObject.Find(RootName);
        if (root == null) return "nothing to clear";
        Undo.DestroyObjectImmediate(root);
        MarkDirty();
        return "cleared";
    }

    public static string Build(LevelData lv, float tile, float wallH)
    {
        if (lv == null || lv.map == null || lv.map.Length == 0) return "ERROR: empty level";
        Clear();
        var root = new GameObject(RootName);
        Undo.RegisterCreatedObjectUndo(root, "Ember build level");
        var rt = root.AddComponent<EmberLevelRuntime>();
        rt.level = lv;
        rt.tile = tile;

        int w = lv.Width, h = lv.Height, walls = 0, doors = 0;
        Prim(PrimitiveType.Cube, "Floor", root, new Vector3((w - 1) * tile / 2f, -0.05f, -(h - 1) * tile / 2f),
             new Vector3(w * tile, 0.1f, h * tile), "floor");
        for (int y = 0; y < h; y++)
        {
            for (int x = 0; x < w; x++)
            {
                char c = lv.map[y][x];
                Vector3 p = rt.GridToWorld(x, y);
                switch (c)
                {
                    case '#':
                        Prim(PrimitiveType.Cube, $"Wall_{x}_{y}", root, p + Vector3.up * wallH / 2f, new Vector3(tile, wallH, tile), "wall");
                        walls++;
                        break;
                    case 'D':
                        Prim(PrimitiveType.Cube, $"Door_{x}_{y}", root, p + Vector3.up * wallH * 0.45f,
                             new Vector3(tile * 0.9f, wallH * 0.9f, tile * 0.3f), "door");
                        doors++;
                        break;
                    case '@':
                        Prim(PrimitiveType.Cylinder, $"Start_{x}_{y}", root, p + Vector3.up * 0.05f, new Vector3(tile * 0.7f, 0.05f, tile * 0.7f), "start");
                        break;
                    case '>':
                        Prim(PrimitiveType.Cylinder, $"Exit_{x}_{y}", root, p + Vector3.up * 0.05f, new Vector3(tile * 0.8f, 0.05f, tile * 0.8f), "exit");
                        break;
                }
            }
        }
        foreach (var e in lv.enemies ?? new Placement[0])
            Prim(PrimitiveType.Capsule, $"Enemy_{e.id}_{e.x}_{e.y}", root, rt.GridToWorld(e.x, e.y, 1f), new Vector3(tile * 0.5f, 1f, tile * 0.5f), "enemy");
        foreach (var i in lv.items ?? new Placement[0])
            Prim(PrimitiveType.Sphere, $"Item_{i.id}_{i.x}_{i.y}", root, rt.GridToWorld(i.x, i.y, 0.5f), Vector3.one * 0.6f, "item");

        var player = Prim(PrimitiveType.Capsule, "Player", null, Vector3.zero, new Vector3(tile * 0.5f, 1f, tile * 0.5f), "player");
        player.transform.SetParent(root.transform, false);
        player.name = "PlayerAvatar";             // not "Kind_x_y" so runtime lookup ignores it
        player.AddComponent<EmberGridPlayer>().level = rt;

        SetupCamera(w * tile, h * tile);
        MarkDirty();
        return $"built {lv.name} {w}x{h}: walls={walls} doors={doors} enemies={(lv.enemies ?? new Placement[0]).Length} items={(lv.items ?? new Placement[0]).Length}";
    }

    public static string AddProp(string kind, int x, int y, float tile)
    {
        var root = GameObject.Find(RootName);
        if (root == null) return "ERROR: build a level first";
        var rt = root.GetComponent<EmberLevelRuntime>();
        if (rt.level.Tile(x, y) != '.') return $"ERROR: ({x},{y}) is '{rt.level.Tile(x, y)}', props only on floor '.'";
        Vector3 p = rt.GridToWorld(x, y);
        switch (kind)
        {
            case "pillar": Prim(PrimitiveType.Cylinder, $"Prop_pillar_{x}_{y}", root, p + Vector3.up * 1.5f, new Vector3(0.8f, 1.5f, 0.8f), "prop"); break;
            case "coffin": Prim(PrimitiveType.Cube, $"Prop_coffin_{x}_{y}", root, p + Vector3.up * 0.3f, new Vector3(0.8f, 0.6f, 1.8f), "prop"); break;
            case "brazier":
                Prim(PrimitiveType.Cylinder, $"Prop_brazier_{x}_{y}", root, p + Vector3.up * 0.5f, new Vector3(0.6f, 0.5f, 0.6f), "prop");
                Prim(PrimitiveType.Sphere, $"Prop_fire_{x}_{y}", root, p + Vector3.up * 1.15f, Vector3.one * 0.45f, "ember");
                var lightGo = new GameObject($"Prop_light_{x}_{y}");
                lightGo.transform.SetParent(root.transform, false);
                lightGo.transform.position = p + Vector3.up * 1.6f;
                var l = lightGo.AddComponent<Light>();
                l.type = LightType.Point; l.color = Colors["ember"]; l.range = tile * 4f; l.intensity = 2f;
                Undo.RegisterCreatedObjectUndo(lightGo, "Ember prop");
                break;
            default: return "ERROR: kind must be pillar|coffin|brazier";
        }
        MarkDirty();
        return $"added {kind} at ({x},{y})";
    }

    // ------------------------------------------------------------------ helpers
    static GameObject Prim(PrimitiveType t, string name, GameObject parent, Vector3 pos, Vector3 scale, string kind)
    {
        var go = GameObject.CreatePrimitive(t);
        go.name = name;
        if (parent != null) go.transform.SetParent(parent.transform, false);
        go.transform.position = pos;
        go.transform.localScale = scale;
        go.GetComponent<Renderer>().sharedMaterial = Mat(kind);
        Undo.RegisterCreatedObjectUndo(go, "Ember build");
        return go;
    }

    static Shader LitShader()
    {
        // URP (Unity 6 default) -> Built-in -> HDRP
        foreach (var n in new[] { "Universal Render Pipeline/Lit", "Standard", "HDRP/Lit" })
        {
            var s = Shader.Find(n);
            if (s != null) return s;
        }
        return Shader.Find("Unlit/Color");
    }

    static Material Mat(string kind)
    {
        if (!AssetDatabase.IsValidFolder(MatDir)) AssetDatabase.CreateFolder("Assets/Ember", "Generated");
        string path = $"{MatDir}/ember_{kind}.mat";
        var m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m != null) return m;
        m = new Material(LitShader());
        var c = Colors[kind];
        if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
        if (m.HasProperty("_Color")) m.SetColor("_Color", c);
        if (kind == "ember" && m.HasProperty("_EmissionColor"))
        {
            m.EnableKeyword("_EMISSION");
            m.SetColor("_EmissionColor", c * 3f);
        }
        AssetDatabase.CreateAsset(m, path);
        return m;
    }

    static void SetupCamera(float width, float depth)
    {
        Camera cam = Camera.main;
        if (cam == null)
        {
            var go = new GameObject("Main Camera");
            go.tag = "MainCamera";
            cam = go.AddComponent<Camera>();
            Undo.RegisterCreatedObjectUndo(go, "Ember camera");
        }
        cam.orthographic = true;
        cam.orthographicSize = Mathf.Max(depth / 2f, width / 2f / Mathf.Max(cam.aspect, 0.1f)) * 1.1f;
        cam.transform.position = new Vector3(width / 2f - 1f, 40f, -depth / 2f + 1f);
        cam.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
    }

    static void MarkDirty() => EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());

    public static string Screenshot(string path, int width, int height)
    {
        Camera cam = Camera.main;
        if (cam == null) return "ERROR: no Main Camera";
        var rtex = new RenderTexture(width, height, 24);
        var prev = cam.targetTexture;
        cam.targetTexture = rtex;
        cam.Render();
        RenderTexture.active = rtex;
        var tex = new Texture2D(width, height, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
        tex.Apply();
        cam.targetTexture = prev;
        RenderTexture.active = null;
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllBytes(path, tex.EncodeToPNG());
        Object.DestroyImmediate(rtex);
        Object.DestroyImmediate(tex);
        return path;
    }
}
