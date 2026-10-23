/* ============================================================
   Q COLLECTIVE — ASSISTANT CONFIG
   After you deploy the Cloudflare Worker (see q-assistant-worker.js),
   paste its URL between the quotes below and re-upload THIS one file.
   Nothing else on the site needs to change to turn the assistant on.
   ============================================================ */
window.Q_WORKER_URL = "https://q-assistant.maveriqbjackson.workers.dev";   // e.g. "https://q-assistant.yourname.workers.dev"


/* ============================================================
   SUNDAY UPDATE BOT CHECK (Cloudflare Turnstile)
   Paste the Turnstile SITE KEY between the quotes to switch it on.
   Leave it empty ("") and sign-ups work exactly as before.
   The SECRET key never goes here. It goes in Supabase only.
   ============================================================ */
window.Q_TURNSTILE_SITEKEY = "0x4AAAAAAFiiYOU9M5lZKjjn";
