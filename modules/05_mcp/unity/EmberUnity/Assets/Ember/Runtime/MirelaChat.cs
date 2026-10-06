// [v2] LLM NPC inside Unity: Mirela talks via local Ollama (/api/chat). Same wire format as M01 hello.py.
// Add to any GameObject, press Play, press T to talk.
// Unity 2022+: Project Settings > Player > Other Settings > "Allow downloads over HTTP" = Allowed in development builds
// (or Always) — otherwise http://localhost requests are blocked as insecure.
// EXERCISE (M10 ★★★): give her TOOLS by porting lib/harness.py's loop to C# (list_stock / sell_item over a C# shop).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace Ember
{
    public class MirelaChat : MonoBehaviour
    {
        public string ollamaUrl = "http://localhost:11434/api/chat";
        public string model = "gemma4:e4b";
        [TextArea(4, 10)]
        public string persona = "You are Mirela Ashgrove, wry superstitious ember-merchant at the crypt mouth. " +
                                "Call the player 'little flame'. Under 40 words. Stock: Red Tonic 10g (heals 10), " +
                                "Phoenix Draught 40g (heals 25), Ember Blade 60g (+5 atk), Ash Mail 70g (+4 def), Iron Key 5g. " +
                                "Never invent other items or prices.";

        [Serializable] class Msg { public string role; public string content; }
        [Serializable] class ChatReq { public string model; public bool stream; public Msg[] messages; }
        [Serializable] class ChatResp { public Msg message; }

        readonly List<Msg> history = new List<Msg>();
        string input = "";
        string log = "";
        bool open, busy;

        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            if (Keyboard.current != null && Keyboard.current.tKey.wasPressedThisFrame && !open) open = true;
#else
            if (Input.GetKeyDown(KeyCode.T) && !open) open = true;
#endif
        }

        void OnGUI()
        {
            if (!open) { GUI.Label(new Rect(10, 70, 300, 22), "Press T to talk to Mirela"); return; }
            GUI.Box(new Rect(10, 70, 560, 260), $"Mirela ({model})");
            GUI.Label(new Rect(20, 95, 540, 180), log);
            GUI.SetNextControlName("chat");
            input = GUI.TextField(new Rect(20, 285, 420, 24), input);
            GUI.FocusControl("chat");
            bool enter = Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.Return;
            if ((GUI.Button(new Rect(450, 285, 50, 24), busy ? "..." : "Say") || enter) && !busy && input.Trim().Length > 0)
            {
                StartCoroutine(Send(input.Trim()));
                input = "";
            }
            if (GUI.Button(new Rect(505, 285, 55, 24), "Close")) open = false;
        }

        IEnumerator Send(string text)
        {
            busy = true;
            history.Add(new Msg { role = "user", content = text });
            AppendLog($"you: {text}");
            var msgs = new List<Msg> { new Msg { role = "system", content = persona } };
            msgs.AddRange(history);                                   // stateless API: resend everything (M01)
            var body = JsonUtility.ToJson(new ChatReq { model = model, stream = false, messages = msgs.ToArray() });
            using (var req = new UnityWebRequest(ollamaUrl, "POST"))
            {
                req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(body));
                req.downloadHandler = new DownloadHandlerBuffer();
                req.SetRequestHeader("Content-Type", "application/json");
                yield return req.SendWebRequest();
                if (req.result != UnityWebRequest.Result.Success)
                {
                    AppendLog($"[error] {req.error} (Ollama running? HTTP allowed in Player settings?)");
                }
                else
                {
                    var resp = JsonUtility.FromJson<ChatResp>(req.downloadHandler.text);
                    string reply = resp?.message?.content ?? "(no reply)";
                    int thinkEnd = reply.IndexOf("</think>", StringComparison.Ordinal);   // strip reasoning if any
                    if (thinkEnd >= 0) reply = reply.Substring(thinkEnd + 8).Trim();
                    history.Add(new Msg { role = "assistant", content = reply });
                    AppendLog($"mirela: {reply}");
                }
            }
            busy = false;
        }

        void AppendLog(string line)
        {
            log += line + "\n";
            var lines = log.Split('\n');
            if (lines.Length > 9) log = string.Join("\n", lines, lines.Length - 9, 9);
        }
    }
}
