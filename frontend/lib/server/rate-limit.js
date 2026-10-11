/** IP-first Redis rate limits for Next BFF (guest traffic hits web first). */

import { createClient } from "redis";

const BUCKETS = {
  global: { limit: 100, windowSec: 60, messageKey: "rateLimit.gentle" },
  public_read: { limit: 40, windowSec: 60, messageKey: "rateLimit.gentle" },
  auth_tx: { limit: 15, windowSec: 60, messageKey: "rateLimit.signInPause" },
  click_unsub: { limit: 40, windowSec: 60, messageKey: "rateLimit.gentle" },
};

const FALLBACK = {
  "rateLimit.gentle":
    "Let’s pause briefly so the site stays fast for you. Try again in a few seconds.",
  "rateLimit.signInPause":
    "Let’s pause briefly so sign-in stays secure for you. Try again in a few seconds.",
  "rateLimit.savePause":
    "Let’s pause briefly so your application can be saved cleanly. Try again in a few seconds.",
  "rateLimit.postPause":
    "Let’s pause briefly so your listing can be reviewed properly. Try again in a few seconds.",
  "rateLimit.verifyHuman":
    "Please complete the quick security check so we can keep your account safe. Then try again.",
};

const memory = new Map();
let redisClient;
let redisFailed = false;

function rateLimitEnabled() {
  const raw = (process.env.RATE_LIMIT_ENABLED || "").trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(raw)) return true;
  if (["0", "false", "no", "off"].includes(raw)) return false;
  return Boolean((process.env.RAILWAY_ENVIRONMENT || "").trim());
}

export function getClientIp(request) {
  const cf = (request.headers.get("cf-connecting-ip") || "").trim();
  if (cf && cf.length < 64) return cf;
  const real = (request.headers.get("x-real-ip") || "").trim();
  if (real) return real;
  const xff = (request.headers.get("x-forwarded-for") || "").split(",")[0]?.trim();
  if (xff) return xff;
  return "unknown";
}

function slowDownPayload(messageKey, retryAfter) {
  const key = FALLBACK[messageKey] ? messageKey : "rateLimit.gentle";
  return {
    error: "slow_down",
    message_key: key,
    retry_after_seconds: Math.max(1, Number(retryAfter) || 60),
    message: FALLBACK[key],
  };
}

export function slowDownResponse(messageKey = "rateLimit.gentle", retryAfter = 60, status = 429) {
  const payload = slowDownPayload(messageKey, retryAfter);
  return Response.json(payload, {
    status,
    headers: {
      "Retry-After": String(payload.retry_after_seconds),
      "Cache-Control": "no-store",
    },
  });
}

async function getRedis() {
  if (redisFailed) return null;
  if (redisClient) return redisClient;
  const url = (process.env.REDIS_URL || "").trim();
  if (!url) return null;
  try {
    redisClient = createClient({ url });
    redisClient.on("error", () => {
      redisFailed = true;
    });
    await redisClient.connect();
    return redisClient;
  } catch {
    redisFailed = true;
    redisClient = null;
    return null;
  }
}

function incrMemory(key, windowSec) {
  const now = Date.now() / 1000;
  const prev = memory.get(key);
  let count = 0;
  let expires = now + windowSec;
  if (prev && now < prev.expires) {
    count = prev.count;
    expires = prev.expires;
  }
  count += 1;
  memory.set(key, { count, expires });
  return { count, retry: Math.max(1, Math.ceil(expires - now)) };
}

async function incr(key, windowSec) {
  const client = await getRedis();
  if (!client) return incrMemory(key, windowSec);
  const count = await client.incr(key);
  let ttl = await client.ttl(key);
  if (ttl < 0) {
    await client.expire(key, windowSec);
    ttl = windowSec;
  }
  return { count, retry: Math.max(1, ttl) };
}

/**
 * @returns {Promise<Response|null>} 429 response or null if allowed
 */
export async function assertRateLimit(request, bucket, { messageKey } = {}) {
  if (!rateLimitEnabled()) return null;
  const meta = BUCKETS[bucket];
  if (!meta) return null;
  const id = getClientIp(request);
  const key = `rl:web:${bucket}:${id}`;
  try {
    const { count, retry } = await incr(key, meta.windowSec);
    if (count > meta.limit) {
      return slowDownResponse(messageKey || meta.messageKey, retry);
    }
  } catch {
    // fail-open for public BFF reads
  }
  return null;
}

export async function withRateLimit(request, bucket, handler, opts) {
  const limited = await assertRateLimit(request, bucket, opts);
  if (limited) return limited;
  return handler();
}
