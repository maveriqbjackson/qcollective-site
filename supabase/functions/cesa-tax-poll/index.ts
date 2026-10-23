// cesa-tax-poll — The Q Collective
// "Which CESA taxes would you vote yes on?" — an informal, anonymous poll.
//
// GET  → public totals only (no individual answers ever leave the database).
// POST → { answers: {key: "yes"|"no"|"unsure"}, zip?: "80228", src?: "...", token: <Turnstile> }
//        Cloudflare Turnstile must confirm a person first. One ballot per
//        browser/network per 24 hours, tracked with a one-way hash (no IP stored).
//
// Uses the same TURNSTILE_SECRET as sunday-signup, and talks to the database
// directly through SUPABASE_DB_URL (always provided to Edge Functions).
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import postgres from "npm:postgres@3.4.5";

const ALLOWED = ["https://theqcollective.org", "https://www.theqcollective.org", "https://maveriqbjackson.github.io"];

let sql: ReturnType<typeof postgres> | null = null;
function db() {
  if (!sql) sql = postgres(Deno.env.get("SUPABASE_DB_URL")!, { max: 1, prepare: false, idle_timeout: 5 });
  return sql;
}

function cors(origin: string | null) {
  const o = origin && ALLOWED.includes(origin) ? origin : ALLOWED[0];
  return {
    "Access-Control-Allow-Origin": o,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type, apikey, authorization",
    "Vary": "Origin",
  };
}
function reply(body: unknown, status: number, origin: string | null, extra: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors(origin), "Content-Type": "application/json", ...extra },
  });
}

async function sha256(text: string) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function results() {
  const rows = await db()`select public.cesa_tax_poll_results() as r`;
  return rows[0]?.r;
}

Deno.serve(async (req: Request) => {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors(origin) });

  if (req.method === "GET") {
    try {
      return reply(await results(), 200, origin, { "Cache-Control": "public, max-age=30" });
    } catch (e) {
      console.error("step=results", String(e));
      return reply("error", 502, origin);
    }
  }
  if (req.method !== "POST") return reply("method", 405, origin);

  const secret = (Deno.env.get("TURNSTILE_SECRET") || "").trim();
  if (!secret) return reply("not-configured", 503, origin);

  let body: { answers?: Record<string, string>; zip?: string; src?: string; token?: string } = {};
  try { body = await req.json(); } catch { return reply("invalid", 400, origin); }
  const token = String(body.token || "");
  if (!token || !body.answers || typeof body.answers !== "object") return reply("invalid", 400, origin);
  const zip = /^\d{5}$/.test(String(body.zip || "")) ? String(body.zip) : null;
  const src = String(body.src || "").slice(0, 24);

  // 1) Is this a person?
  const ip = req.headers.get("cf-connecting-ip") || (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  const form = new FormData();
  form.append("secret", secret);
  form.append("response", token);
  if (ip) form.append("remoteip", ip);
  try {
    const v = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form });
    const out = await v.json();
    if (!out.success) {
      console.log("turnstile rejected:", JSON.stringify(out["error-codes"] || []));
      return reply("bot", 403, origin);
    }
  } catch (e) {
    console.error("step=turnstile-verify", String(e));
    return reply("error", 502, origin);
  }

  // 2) Record the ballot. The hash can't be turned back into an IP address.
  const vh = await sha256(secret + "|cesa-tax-poll|" + ip + "|" + (req.headers.get("user-agent") || ""));
  try {
    const rows = await db()`select public.cesa_tax_poll_vote(${JSON.stringify(body.answers)}::jsonb, ${zip}, ${vh}, ${src || null}) as r`;
    const status = rows[0]?.r;
    return reply({ status, results: await results() }, status === "invalid" ? 400 : 200, origin);
  } catch (e) {
    console.error("step=vote", String(e));
    return reply("error", 502, origin);
  }
});
