// sunday-signup — The Q Collective
// Bot-checked front door for the Sunday Update sign-up form.
//
// The form gets a Cloudflare Turnstile token in the visitor's browser and posts
// it here with the email. We ask Cloudflare whether the token is real, and only
// then add the person through the same subscribe_sunday() database function the
// site has always used, so every list rule (flood switch, Tor block, reminders)
// still applies.
//
// Needs one secret in Supabase (Edge Functions > Secrets): TURNSTILE_SECRET.
// Until that secret exists this function answers "not-configured" and the site
// keeps using the old direct path, so nothing breaks while it is switched off.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const ALLOWED = ["https://theqcollective.org", "https://www.theqcollective.org", "https://maveriqbjackson.github.io"];

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

  const secret = Deno.env.get("TURNSTILE_SECRET") || "";
  if (!secret) return reply("not-configured", 503, origin);

  let body: { email?: string; src?: string; token?: string } = {};
  try { body = await req.json(); } catch { return reply("invalid", 400, origin); }
  const email = String(body.email || "").trim().slice(0, 254);
  const src = String(body.src || "").slice(0, 24);
  const token = String(body.token || "");
  if (!email || !token) return reply("invalid", 400, origin);

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
  } catch {
    return reply("error", 502, origin);
  }
  if (!human) return reply("bot", 403, origin);

  const url = Deno.env.get("SUPABASE_URL")!;
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const headers: Record<string, string> = {
    apikey: key,
    Authorization: "Bearer " + key,
    "Content-Type": "application/json",
  };
  // pass the visitor's country and browser through so the database's logging and Tor block still see them
  const cc = req.headers.get("cf-ipcountry");
  const ua = req.headers.get("user-agent");
  if (cc) headers["cf-ipcountry"] = cc;
  if (ua) headers["user-agent"] = ua;

  const r = await fetch(url + "/rest/v1/rpc/subscribe_sunday", {
    method: "POST",
    headers,
    body: JSON.stringify({ e: email, src: src || null }),
  });
  if (!r.ok) return reply("error", 502, origin);
  return reply(await r.json(), 200, origin);
});
