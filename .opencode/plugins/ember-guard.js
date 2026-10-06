// [v2] OpenCode plugin = Claude Code hooks equivalent (compare .claude/hooks/*.py, M06 vs M06b).
//
//   Claude Code hook            OpenCode plugin event
//   PreToolUse  (exit 2)   ->   "tool.execute.before"  (throw Error = block; message goes to model)
//   PostToolUse (JSON)     ->   "tool.execute.after"   (mutate output = feedback to model)
//   Stop (veto)            ->   no veto event; use outer loop (Ralph) or /verify command instead
//
// Loaded automatically from .opencode/plugins/. Runs in OpenCode's Bun runtime. `$` = Bun shell.
// API shapes per opencode.ai/docs/plugins (Oct 2026). If an event signature changed in your version,
// check the docs and adjust — small, contained file.
import { appendFileSync, mkdirSync } from "node:fs"
import { join } from "node:path"

const BLOCK = [
  [/\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r/i, "recursive force delete"],
  [/git\s+push\b.*(--force|-f\b)/i, "force push"],
  [/git\s+reset\s+--hard/i, "hard reset discards work; use git stash"],
  [/Remove-Item\b.*-Recurse/i, "recursive delete (PowerShell)"],
  [/(curl|wget|iwr|Invoke-WebRequest)\b.*\|\s*(sh|bash|iex|python)/i, "pipe-download-to-shell"],
  [/(>|sed\s+-i|\btee\b|Set-Content|Out-File|\bmv\s).*game[\/\\]data[\/\\](items|enemies|level_01)\.json/i,
    "core content written via shell; use edit/write tools so validation runs"],
]
const CONTENT = /game[\/\\]data[\/\\].*\.json$/i

export const EmberGuard = async ({ $, directory }) => {
  const pendingEdits = new Map()            // callID -> filePath (args are visible in "before")
  const audit = join(directory, "runs", "bash_audit.log")

  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "bash") {
        const cmd = output.args?.command ?? ""
        try { mkdirSync(join(directory, "runs"), { recursive: true }); appendFileSync(audit, `${new Date().toISOString()}\t${cmd}\n`) } catch {}
        for (const [re, why] of BLOCK) {
          if (re.test(cmd)) throw new Error(`Blocked by .opencode/plugins/ember-guard.js: ${why}. Command: ${cmd}`)
        }
      }
      if (input.tool === "edit" || input.tool === "write") {
        const fp = output.args?.filePath ?? ""
        if (CONTENT.test(fp) && !fp.endsWith("shop.json")) pendingEdits.set(input.callID, fp)
      }
    },

    "tool.execute.after": async (input, output) => {
      const fp = pendingEdits.get(input.callID)
      if (!fp) return
      pendingEdits.delete(input.callID)
      // reuse the SAME validator the Claude Code hook uses -> one source of truth
      const payload = JSON.stringify({ tool_input: { file_path: fp } })
      const res = await $`uv run --quiet python .claude/hooks/validate_content.py < ${new Response(payload)}`
        .cwd(directory).quiet().nothrow()
      const text = res.stdout.toString().trim()
      if (!text) return
      try {
        const verdict = JSON.parse(text)
        if (verdict.decision === "block") {
          output.output = `${output.output ?? ""}\n\n[ember-validate] ${verdict.reason}`
        }
      } catch { /* validator printed non-JSON; ignore */ }
    },
  }
}
