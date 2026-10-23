// sunday-signup — The Q Collective
// Bot-checked front door for the Sunday Update sign-up form.
//
// The form gets a Cloudflare Turnstile token in the visitor's browser and posts
// it here with the email. We ask Cloudflare whether the token is real, and only
// then add the person through the same subscribe_sunday() database function the
// site has always used, so every list rule (flood switch, Tor block, reminders)
// still applies.
//
// v2 (Oct 23, 2026): talks to the database directly through SUPABASE_DB_URL
// (always provided to Edge Functions) instead of the REST API with a service
// key, because this project uses the new-style API keys and the legacy service
// key was refused. Every failure is now logged with the step that failed.
//
// Needs one secret in Supabase (Edge Functions > Secrets): TURNSTILE_SECRET.
// Until that secret exists this function answers "not-configured" and the site
// keeps using the old direct path, so nothing breaks while it is switched off.
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
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type, apikey, authorization",
    "Vary": "Origin",
  };
}

function reply(body: unknown, status: number, origin: string | null) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors(origin), "Content-Type": "application/json" },
  });
}

Deno.serve(async (req: Request) => {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors(origin) });
  if (req.method !== "POST") return reply("method", 405, origin);

  const secret = (Deno.env.get("TURNSTILE_SECRET") || "").trim();
  if (!secret) return reply("not-configured", 503, origin);

  let body: { email?: string; src?: string; token?: string } = {};
  try { body = await req.json(); } catch { return reply("invalid", 400, origin); }
  const email = String(body.email || "").trim().slice(0, 254);
  const src = String(body.src || "").slice(0, 24);
  const token = String(body.token || "");
  if (!email || !token) return reply("invalid", 400, origin);

  // 1) Ask Cloudflare whether this is a person.
  const ip = req.headers.get("cf-connecting-ip") || (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  const form = new FormData();
  form.append("secret", secret);
  form.append("response", token);
  if (ip) form.append("remoteip", ip);
  let human = false;
  try {
    const v = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form });
    const out = await v.json();
    human = !!out.success;
    if (!human) console.log("turnstile rejected:", JSON.stringify(out["error-codes"] || []));
  } catch (e) {
    console.error("step=turnstile-verify", String(e));
    return reply("error", 502, origin);
  }
  if (!human) return reply("bot", 403, origin);

  // 2) Add them with the same database rules as always. Country and browser are
  //    passed through so the Tor block and sign-up logging still see them.
  const hdr = JSON.stringify({
    "cf-ipcountry": req.headers.get("cf-ipcountry") || "",
    "user-agent": req.headers.get("user-agent") || "",
  });
  try {
    const res = await db().begin(async (tx) => {
      await tx`select set_config('request.headers', ${hdr}, true)`;
      const rows = await tx`select public.subscribe_sunday(${email}, ${src || null}) as r`;
      return rows[0]?.r;
    });
    return reply(res, 200, origin);
  } catch (e) {
    console.error("step=subscribe", String(e));
    return reply("error", 502, origin);
  }
});
