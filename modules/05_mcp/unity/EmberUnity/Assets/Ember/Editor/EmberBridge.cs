// [v2] Ember Bridge for Unity Editor: JSON-lines TCP server on 127.0.0.1:9877 (Blender bridge used 9876).
//   agent ──MCP──► unity_mcp_server.py ──TCP──► THIS (polled on EditorApplication.update = main thread) ──► EmberLevelBuilder
// Menu: Ember > Start Bridge / Stop Bridge / Auto-start Bridge (toggle; survives script reloads).
// Security: WHITELISTED commands only. No "execute arbitrary C#". Same rule as the Blender add-on (M05).
// Note: Unity throttles editor updates when the window is unfocused -> calls may lag. Preferences >
// General > Interaction Mode = "No Throttling" makes the bridge snappy.
using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using Ember;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class EmberBridge
{
    const int Port = 9877;
    const string AutoKey = "Ember.Bridge.AutoStart";

    [Serializable] class Req { public string cmd; public string args; }
    [Serializable] class Resp { public bool ok; public string result; public string error; }
    [Serializable] class BuildArgs { public LevelData level; public float tile = 2f; public float wall_height = 3f; }
    [Serializable] class PropArgs { public string kind; public int x; public int y; public float tile = 2f; }
    [Serializable] class ShotArgs { public string path; public int width = 1280; public int height = 720; }

    class Conn { public TcpClient client; public NetworkStream stream; public StringBuilder buf = new StringBuilder(); }

    static TcpListener listener;
    static readonly List<Conn> conns = new List<Conn>();
    static readonly byte[] readBuf = new byte[65536];

    static EmberBridge()
    {
        AssemblyReloadEvents.beforeAssemblyReload += Stop;     // free the port before domain reload
        EditorApplication.quitting += Stop;
        if (EditorPrefs.GetBool(AutoKey, false)) EditorApplication.delayCall += Start;
    }

    [MenuItem("Ember/Start Bridge")]
    public static void Start()
    {
        if (listener != null) return;
        try
        {
            listener = new TcpListener(IPAddress.Loopback, Port);
            listener.Start();
            EditorApplication.update += Poll;
            Debug.Log($"[Ember] bridge listening on 127.0.0.1:{Port}");
        }
        catch (Exception e)
        {
            listener = null;
            Debug.LogError($"[Ember] bridge failed to start: {e.Message}");
        }
    }

    [MenuItem("Ember/Stop Bridge")]
    public static void Stop()
    {
        EditorApplication.update -= Poll;
        foreach (var c in conns) { try { c.client.Close(); } catch { } }
        conns.Clear();
        if (listener != null) { listener.Stop(); listener = null; Debug.Log("[Ember] bridge stopped"); }
    }

    [MenuItem("Ember/Auto-start Bridge")]
    static void ToggleAuto()
    {
        bool v = !EditorPrefs.GetBool(AutoKey, false);
        EditorPrefs.SetBool(AutoKey, v);
        Debug.Log($"[Ember] auto-start = {v}");
        if (v) Start();
    }

    [MenuItem("Ember/Auto-start Bridge", true)]
    static bool ToggleAutoValidate()
    {
        Menu.SetChecked("Ember/Auto-start Bridge", EditorPrefs.GetBool(AutoKey, false));
        return true;
    }

    static void Poll()
    {
        if (listener == null) return;
        while (listener.Pending())
        {
            var c = listener.AcceptTcpClient();
            c.NoDelay = true;
            conns.Add(new Conn { client = c, stream = c.GetStream() });
        }
        for (int i = conns.Count - 1; i >= 0; i--)
        {
            var k = conns[i];
            try
            {
                // remote closed: socket readable but nothing to read
                if (k.client.Client.Poll(0, SelectMode.SelectRead) && k.client.Available == 0) { Drop(i); continue; }
                while (k.stream.DataAvailable)
                {
                    int n = k.stream.Read(readBuf, 0, readBuf.Length);
                    if (n <= 0) break;
                    k.buf.Append(Encoding.UTF8.GetString(readBuf, 0, n));
                }
                string s = k.buf.ToString();
                int nl;
                while ((nl = s.IndexOf('\n')) >= 0)
                {
                    string line = s.Substring(0, nl);
                    s = s.Substring(nl + 1);
                    var bytes = Encoding.UTF8.GetBytes(Handle(line) + "\n");
                    k.stream.Write(bytes, 0, bytes.Length);
                }
                k.buf.Clear().Append(s);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[Ember] connection dropped: {e.Message}");
                Drop(i);
            }
        }
    }

    static void Drop(int i)
    {
        try { conns[i].client.Close(); } catch { }
        conns.RemoveAt(i);
    }

    static string Handle(string line)
    {
        var resp = new Resp();
        try
        {
            var req = JsonUtility.FromJson<Req>(line);
            string a = string.IsNullOrEmpty(req.args) ? "{}" : req.args;
            switch (req.cmd)
            {
                case "ping":
                    resp.result = $"pong unity={Application.unityVersion} scene={UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene().name}";
                    break;
                case "scene_info":
                    resp.result = SceneInfo();
                    break;
                case "clear":
                    resp.result = EmberLevelBuilder.Clear();
                    break;
                case "build_level":
                    var b = JsonUtility.FromJson<BuildArgs>(a);
                    resp.result = EmberLevelBuilder.Build(b.level, b.tile, b.wall_height);
                    break;
                case "add_prop":
                    var p = JsonUtility.FromJson<PropArgs>(a);
                    resp.result = EmberLevelBuilder.AddProp(p.kind, p.x, p.y, p.tile);
                    break;
                case "screenshot":
                    var sh = JsonUtility.FromJson<ShotArgs>(a);
                    resp.result = EmberLevelBuilder.Screenshot(sh.path, sh.width, sh.height);
                    break;
                default:
                    throw new ArgumentException($"unknown cmd '{req.cmd}'; available: ping, scene_info, clear, build_level, add_prop, screenshot");
            }
            resp.ok = !resp.result.StartsWith("ERROR");
            if (!resp.ok) { resp.error = resp.result; resp.result = null; }
        }
        catch (Exception e)
        {
            resp.ok = false;
            resp.error = $"{e.GetType().Name}: {e.Message}";
        }
        return JsonUtility.ToJson(resp);
    }

    static string SceneInfo()
    {
        var root = GameObject.Find(EmberLevelBuilder.RootName);
        if (root == null) return "no EmberLevel in scene";
        var counts = new Dictionary<string, int>();
        foreach (Transform t in root.transform)
        {
            string kind = t.name.Split('_')[0];
            counts[kind] = counts.TryGetValue(kind, out int n) ? n + 1 : 1;
        }
        var sb = new StringBuilder($"EmberLevel children={root.transform.childCount}:");
        foreach (var kv in counts) sb.Append($" {kv.Key}={kv.Value}");
        return sb.ToString();
    }
}
