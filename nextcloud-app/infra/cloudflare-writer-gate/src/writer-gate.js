/**
 * Cooperative software-lease authority and public origin gate.
 *
 * Production activation requires separate approval, account secrets, and a
 * successful isolated rehearsal. This Worker fails closed when ownership is
 * unclear. It is not a hardware fence.
 */

const SCHEMA_VERSION = 1;
const DEFAULT_TTL_SECONDS = 30;
const DEFAULT_DRAIN_SECONDS = 5;
const DEFAULT_GRACE_SECONDS = 15;
const SOURCE_NAME = "cloudflare-durable-object-lease";

export class WriterLeaseObject {
  constructor(ctx, env) {
    // Cloudflare DO runtime passes DurableObjectState as the first argument
    // (docs name it `ctx`; older samples used `state`).
    this.ctx = ctx;
    this.env = env;
  }

  async fetch(request) {
    try {
      const url = new URL(request.url);
      const now = new Date();
      let body = {};
      if (request.method !== "GET" && request.method !== "HEAD") {
        try {
          body = await request.json();
        } catch {
          return json({ ok: false, reason: "invalid_json" }, 400);
        }
      }

      const current = await this.loadState();
      let decision;
      switch (`${request.method} ${url.pathname}`) {
        case "GET /lease/status":
          decision = status(current, now, policyFromEnv(this.env));
          break;
        case "POST /lease/bootstrap":
          decision = bootstrapOwner(current, body, now, policyFromEnv(this.env));
          break;
        case "POST /lease/renew":
          decision = renewLease(current, body, now, policyFromEnv(this.env));
          break;
        case "POST /lease/request-takeover":
          decision = requestTakeover(current, body, now, policyFromEnv(this.env));
          break;
        case "POST /lease/acquire":
          decision = acquireLease(current, body, now, policyFromEnv(this.env));
          break;
        case "POST /lease/permit":
          decision = requestPermit(current, body, now);
          break;
        default:
          return json({ ok: false, reason: "not_found" }, 404);
      }

      if (decision.persist) {
        await this.ctx.storage.put("lease", decision.response.state);
      }
      return json(decision.response, decision.ok ? 200 : 409);
    } catch (err) {
      const message = err && err.message ? String(err.message) : "do_handler_exception";
      return json({ ok: false, reason: "do_exception", message }, 500);
    }
  }

  async loadState() {
    const stored = await this.ctx.storage.get("lease");
    if (!stored || stored.schema_version !== SCHEMA_VERSION) {
      return emptyState();
    }
    return stored;
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/lease/")) {
      try {
        if (!authorized(request, env.LEASE_API_TOKEN)) {
          return json({ ok: false, reason: "unauthorized" }, 401);
        }
        if (!env.WRITER_LEASE) {
          return json({ ok: false, reason: "do_binding_missing" }, 500);
        }
        const id = env.WRITER_LEASE.idFromName("filantropia-odoo-writer");
        const stub = env.WRITER_LEASE.get(id);
        return await stub.fetch(request);
      } catch (err) {
        const message = err && err.message ? String(err.message) : "lease_route_exception";
        return json({ ok: false, reason: "lease_route_exception", message }, 500);
      }
    }

    // Public website gate: only proxy when the current epoch owns the origin.
    // WebSocket upgrades are not supported through this Worker proxy; Odoo bus
    // /live features that require Upgrade must stay off this path or use a
    // dedicated non-Worker route until WS support is added (Phase C note).
    if (isWebSocketUpgrade(request)) {
      return new Response("websocket not supported on writer gate", { status: 501 });
    }
    if (!env.ORIGIN_TRL5_URL || !env.ORIGIN_FRANK_URL) {
      return temporaryUnavailableResponse(request, env, {
        code: "writer_gate_misconfigured",
        technical: "writer gate misconfigured",
      });
    }
    if (!env.LEASE_API_TOKEN) {
      return temporaryUnavailableResponse(request, env, {
        code: "lease_authority_misconfigured",
        technical: "lease authority misconfigured",
      });
    }
    const id = env.WRITER_LEASE.idFromName("filantropia-odoo-writer");
    const stub = env.WRITER_LEASE.get(id);
    const statusRequest = new Request(new URL("/lease/status", request.url), {
      method: "GET",
      headers: {
        Authorization: `Bearer ${env.LEASE_API_TOKEN}`,
        Accept: "application/json",
      },
    });
    const statusResponse = await stub.fetch(statusRequest);
    if (!statusResponse.ok) {
      return temporaryUnavailableResponse(request, env, {
        code: "lease_authority_unavailable",
        technical: "lease authority unavailable",
      });
    }
    const payload = await statusResponse.json();
    if (!payload.ok || payload.phase !== "active" || !payload.state?.owner_node_id) {
      return temporaryUnavailableResponse(request, env, {
        code: "no_active_writer_epoch",
        technical: "no active writer epoch",
        phase: payload.phase || "unknown",
        // Takeover window: lease TTL + drain + self-fence grace, then promote.
        expected_minutes: expectedRecoveryMinutes(env),
      });
    }
    const owner = payload.state.owner_node_id;
    const origin =
      owner === "trl5"
        ? env.ORIGIN_TRL5_URL
        : owner === "frank"
          ? env.ORIGIN_FRANK_URL
          : null;
    if (!origin) {
      return temporaryUnavailableResponse(request, env, {
        code: "unknown_writer_origin",
        technical: "unknown writer origin",
      });
    }
    const permitRequest = new Request(new URL("/lease/permit", request.url), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.LEASE_API_TOKEN}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        origin_node_id: owner,
        epoch: payload.state.epoch,
      }),
    });
    const permitResponse = await stub.fetch(permitRequest);
    let permit;
    try {
      permit = await permitResponse.json();
    } catch {
      return temporaryUnavailableResponse(request, env, {
        code: "writer_permit_unavailable",
        technical: "writer permit unavailable",
      });
    }
    if (!permit.ok || !permit.request_permit) {
      return temporaryUnavailableResponse(request, env, {
        code: "writer_permit_denied",
        technical: "writer permit denied",
        expected_minutes: expectedRecoveryMinutes(env),
      });
    }

    // Residual race: lease may expire between permit and upstream fetch. Host
    // lease_guard is the hard stop; worst case is a short-lived request to an
    // origin about to lose the epoch.
    const upstream = new URL(request.url);
    const target = new URL(origin);
    upstream.protocol = target.protocol;
    upstream.hostname = target.hostname;
    upstream.port = target.port;
    const headers = new Headers(request.headers);
    headers.set("X-Filantropia-Writer-Epoch", String(payload.state.epoch));
    headers.set("X-Filantropia-Writer-Node", owner);
    if (env.ORIGIN_SHARED_SECRET) {
      headers.set("X-Filantropia-Origin-Auth", env.ORIGIN_SHARED_SECRET);
    }
    const timeoutMs = numberOr(env.ORIGIN_FETCH_TIMEOUT_MS, 10000);
    const hosting = hostingModeForOwner(owner);
    try {
      const originResponse = await fetch(
        new Request(upstream.toString(), {
          method: request.method,
          headers,
          body:
            request.method === "GET" || request.method === "HEAD"
              ? undefined
              : request.body,
          redirect: "manual",
          signal: AbortSignal.timeout(timeoutMs),
        }),
      );
      return decoratePublicResponse(
        request,
        originResponse,
        hosting,
        payload.state.epoch,
      );
    } catch {
      return temporaryUnavailableResponse(request, env, {
        code: "origin_unreachable",
        technical: "origin unreachable",
        expected_minutes: expectedRecoveryMinutes(env),
      });
    }
  },
};

/**
 * Public hosting labels only. Do not expose internal hostnames.
 * trl5 -> Local (primary site host)
 * frank -> Embassy (delegated standby writer)
 */
function hostingModeForOwner(owner) {
  if (owner === "trl5") {
    return { mode: "local", label: "Local" };
  }
  if (owner === "frank") {
    return { mode: "embassy", label: "Embassy" };
  }
  return { mode: "unknown", label: "Unknown" };
}

function decoratePublicResponse(request, originResponse, hosting, epoch) {
  const outHeaders = new Headers(originResponse.headers);
  outHeaders.set("X-Filantropia-Hosting", hosting.mode);
  outHeaders.set("X-Filantropia-Hosting-Label", hosting.label);
  if (epoch != null) {
    outHeaders.set("X-Filantropia-Writer-Epoch", String(epoch));
  }
  // Avoid leaking internal node ids on public responses.
  outHeaders.delete("X-Filantropia-Writer-Node");

  const contentType = (outHeaders.get("content-type") || "").toLowerCase();
  const isHtml = contentType.includes("text/html");
  const method = request.method.toUpperCase();
  const isRedirect = originResponse.status >= 300 && originResponse.status < 400;
  if (!isHtml || method === "HEAD" || method === "OPTIONS" || isRedirect) {
    return new Response(originResponse.body, {
      status: originResponse.status,
      statusText: originResponse.statusText,
      headers: outHeaders,
    });
  }

  // Inject a compact non-disclosing hosting pill for HTML documents.
  return new HTMLRewriter()
    .on("body", {
      element(element) {
        element.append(hostingBadgeHtml(hosting), { html: true });
      },
    })
    .transform(
      new Response(originResponse.body, {
        status: originResponse.status,
        statusText: originResponse.statusText,
        headers: outHeaders,
      }),
    );
}

function hostingBadgeHtml(hosting) {
  const mode = escapeHtml(hosting.mode || "unknown");
  const label = escapeHtml(hosting.label || "Unknown");
  const labelPt =
    mode === "local" ? "Local" : mode === "embassy" ? "Embaixada" : label;
  const accent = mode === "embassy" ? "#E8A020" : "#A89D3F";
  const glow =
    mode === "embassy" ? "rgba(232,160,32,.18)" : "rgba(168,157,63,.18)";
  return `
<aside id="fs-hosting-badge" data-fs-hosting="${mode}" aria-label="Hosting: ${label}" title="Site hosting: ${label}">
  <style>
    #fs-hosting-badge{
      position:fixed;right:12px;bottom:12px;z-index:2147483000;
      font:600 12px/1.2 system-ui,-apple-system,Segoe UI,sans-serif;
      color:#1f1a14;background:rgba(251,247,239,.94);
      border:1px solid rgba(31,26,20,.12);border-radius:999px;
      box-shadow:0 8px 24px rgba(31,26,20,.12);
      padding:8px 12px;display:inline-flex;align-items:center;gap:8px;
      backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
      pointer-events:none;user-select:none;
    }
    #fs-hosting-badge .dot{
      width:8px;height:8px;border-radius:50%;
      background:${accent};
      box-shadow:0 0 0 3px ${glow};
    }
    #fs-hosting-badge .txt{white-space:nowrap}
    #fs-hosting-badge .en{color:#5c5346;font-weight:500}
    @media print{#fs-hosting-badge{display:none!important}}
  </style>
  <span class="dot" aria-hidden="true"></span>
  <span class="txt">${labelPt} <span class="en">/ ${label}</span></span>
</aside>`;
}

function isWebSocketUpgrade(request) {
  const upgrade = (request.headers.get("Upgrade") || "").toLowerCase();
  return upgrade === "websocket";
}

/** Designed automatic recovery band shown to visitors (lease math + promote). */
function expectedRecoveryMinutes(env) {
  const ttl = numberOr(env.LEASE_TTL_SECONDS, DEFAULT_TTL_SECONDS);
  const drain = numberOr(env.LEASE_DRAIN_SECONDS, DEFAULT_DRAIN_SECONDS);
  const grace = numberOr(env.LEASE_GRACE_SECONDS, DEFAULT_GRACE_SECONDS);
  const leaseSeconds = ttl + drain + grace;
  // Warm standby promote + origin start is typically under a few minutes.
  const minMinutes = Math.max(1, Math.ceil(leaseSeconds / 60));
  const maxMinutes = Math.max(minMinutes + 1, 3);
  return { min: minMinutes, max: maxMinutes, lease_seconds: leaseSeconds };
}

function prefersHtml(request) {
  const accept = (request.headers.get("Accept") || "").toLowerCase();
  if (!accept || accept === "*/*") {
    return true;
  }
  if (accept.includes("text/html")) {
    return true;
  }
  // Explicit machine clients keep a compact body.
  if (
    accept.includes("application/json") ||
    accept.includes("text/plain") ||
    accept.includes("application/problem+json")
  ) {
    return false;
  }
  return true;
}

function temporaryUnavailableResponse(request, env, detail) {
  const recovery = detail.expected_minutes || expectedRecoveryMinutes(env);
  const retryAfter = Math.max(15, Math.min(60, Number(recovery.lease_seconds) || 30));
  const headers = {
    "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate",
    Pragma: "no-cache",
    "Retry-After": String(retryAfter),
    "X-Filantropia-Unavailable-Code": String(detail.code || "temporary_unavailable"),
  };
  if (detail.phase) {
    headers["X-Filantropia-Lease-Phase"] = String(detail.phase);
  }

  if (!prefersHtml(request)) {
    headers["Content-Type"] = "application/json; charset=utf-8";
    return new Response(
      JSON.stringify({
        ok: false,
        reason: detail.code || "temporary_unavailable",
        technical: detail.technical || "temporary unavailable",
        phase: detail.phase || null,
        expected_recovery_minutes: recovery,
        message_pt:
          "O site FilantropiaSolar est\u00e1 temporariamente indispon\u00edvel durante uma mudan\u00e7a de servidor. Dever\u00e1 voltar dentro de poucos minutos.",
        message_en:
          "FilantropiaSolar is temporarily unavailable during a server failover. It should return within a few minutes.",
      }),
      { status: 503, headers },
    );
  }

  headers["Content-Type"] = "text/html; charset=utf-8";
  return new Response(failoverHtmlPage(recovery, detail), {
    status: 503,
    headers,
  });
}

function failoverHtmlPage(recovery, detail) {
  const minM = Number(recovery.min) || 1;
  const maxM = Number(recovery.max) || 3;
  const refreshSeconds = 20;
  const code = escapeHtml(detail.code || "temporary_unavailable");
  const phase = escapeHtml(detail.phase || "");
  const phaseLine = phase
    ? `<p class="meta">Estado t\u00e9cnico: <code>${code}</code> (fase de lease: <code>${phase}</code>)</p>`
    : `<p class="meta">Estado t\u00e9cnico: <code>${code}</code></p>`;

  return `<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="${refreshSeconds}">
  <title>FilantropiaSolar \u2014 dispon\u00edvel em breve</title>
  <style>
    :root {
      --olive: #A89D3F;
      --orange: #E8A020;
      --ink: #1f1a14;
      --muted: #5c5346;
      --paper: #fbf7ef;
      --card: #ffffff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(232, 160, 32, 0.18), transparent 40%),
        radial-gradient(circle at bottom left, rgba(168, 157, 63, 0.16), transparent 45%),
        var(--paper);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem 1.25rem;
    }
    main {
      width: min(34rem, 100%);
      background: var(--card);
      border: 1px solid rgba(31, 26, 20, 0.08);
      border-radius: 18px;
      box-shadow: 0 18px 40px rgba(31, 26, 20, 0.08);
      padding: 2rem 1.75rem 1.75rem;
    }
    .brand {
      font-style: italic;
      font-size: 1.35rem;
      letter-spacing: 0.01em;
      margin: 0 0 0.35rem;
    }
    .tag {
      margin: 0 0 1.4rem;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 0.85rem;
      color: var(--muted);
    }
    .tag .we { color: var(--olive); font-weight: 600; }
    .tag .ra { color: var(--orange); font-weight: 600; }
    h1 {
      margin: 0 0 0.75rem;
      font-size: 1.55rem;
      line-height: 1.25;
    }
    p {
      margin: 0 0 0.9rem;
      line-height: 1.45;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 1rem;
      color: var(--ink);
    }
    .en {
      color: var(--muted);
      font-size: 0.95rem;
    }
    .meta {
      margin-top: 1.25rem;
      color: var(--muted);
      font-size: 0.8rem;
    }
    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.78em;
    }
    .pulse {
      width: 0.7rem;
      height: 0.7rem;
      border-radius: 50%;
      background: var(--orange);
      display: inline-block;
      margin-right: 0.45rem;
      box-shadow: 0 0 0 0 rgba(232, 160, 32, 0.55);
      animation: pulse 1.6s infinite;
      vertical-align: middle;
    }
    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(232, 160, 32, 0.45); }
      70% { box-shadow: 0 0 0 12px rgba(232, 160, 32, 0); }
      100% { box-shadow: 0 0 0 0 rgba(232, 160, 32, 0); }
    }
  </style>
</head>
<body>
  <main role="status" aria-live="polite">
    <p class="brand">FilantropiaSolar</p>
    <p class="tag">built by <span class="we">we</span><span class="ra">ra</span></p>
    <h1><span class="pulse" aria-hidden="true"></span>O site volta em breve</h1>
    <p>
      Estamos a concluir uma mudan\u00e7a de servidor para manter o servi\u00e7o
      seguro. O website FilantropiaSolar dever\u00e1 ficar dispon\u00edvel outra vez dentro
      de cerca de <strong>${minM} a ${maxM} minutos</strong>.
    </p>
    <p class="en">
      FilantropiaSolar is temporarily unavailable while a server change
      finishes. The site should return within about
      <strong>${minM}\u2013${maxM} minutes</strong>. This page refreshes every
      ${refreshSeconds} seconds.
    </p>
    <p class="en">Esta p\u00e1gina atualiza automaticamente a cada ${refreshSeconds} segundos.</p>
    ${phaseLine}
  </main>
</body>
</html>`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Compare bearer tokens without short-circuiting on the first differing byte.
 * Length mismatches still scan the longer buffer so timing does not leak
 * prefix equality.
 */
function tokensEqualConstantTime(a, b) {
  const enc = new TextEncoder();
  const left = enc.encode(String(a));
  const right = enc.encode(String(b));
  const len = Math.max(left.length, right.length);
  let diff = left.length === right.length ? 0 : 1;
  for (let i = 0; i < len; i += 1) {
    const x = i < left.length ? left[i] : 0;
    const y = i < right.length ? right[i] : 0;
    diff |= x ^ y;
  }
  return diff === 0;
}

function authorized(request, token) {
  if (!token) {
    return false;
  }
  const header = request.headers.get("Authorization") || "";
  const prefix = "Bearer ";
  if (header.length < prefix.length || header.slice(0, prefix.length) !== prefix) {
    return false;
  }
  return tokensEqualConstantTime(header.slice(prefix.length), token);
}

function policyFromEnv(env) {
  return {
    lease_ttl_seconds: numberOr(env.LEASE_TTL_SECONDS, DEFAULT_TTL_SECONDS),
    in_flight_drain_seconds: numberOr(env.LEASE_DRAIN_SECONDS, DEFAULT_DRAIN_SECONDS),
    self_fence_grace_seconds: numberOr(env.LEASE_GRACE_SECONDS, DEFAULT_GRACE_SECONDS),
    source_name: env.LEASE_SOURCE_NAME || SOURCE_NAME,
  };
}

function numberOr(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function emptyState() {
  return {
    schema_version: SCHEMA_VERSION,
    owner_node_id: null,
    epoch: 0,
    generation: null,
    lease_expires_at: null,
    takeover_pending: false,
    takeover_requested_at: null,
    previous_owner_node_id: null,
    previous_epoch: null,
    previous_generation: null,
    self_fence_grace_until: null,
    in_flight_drain_until: null,
    proof_id: null,
  };
}

function phaseOf(state, now) {
  if (state.takeover_pending) {
    if (readyToAcquire(state, now)) {
      return "acquirable";
    }
    if (state.in_flight_drain_until && now < new Date(state.in_flight_drain_until)) {
      return "draining";
    }
    return "takeover_pending";
  }
  if (state.owner_node_id && state.lease_expires_at && now < new Date(state.lease_expires_at)) {
    return "active";
  }
  if (state.owner_node_id && state.lease_expires_at && now >= new Date(state.lease_expires_at)) {
    return "acquirable";
  }
  return "unowned";
}

function readyToAcquire(state, now) {
  if (state.takeover_pending) {
    const leaseDone = !state.lease_expires_at || now >= new Date(state.lease_expires_at);
    const drainDone =
      !state.in_flight_drain_until || now >= new Date(state.in_flight_drain_until);
    const graceDone =
      !state.self_fence_grace_until || now >= new Date(state.self_fence_grace_until);
    return leaseDone && drainDone && graceDone;
  }
  return Boolean(
    state.owner_node_id && state.lease_expires_at && now >= new Date(state.lease_expires_at),
  );
}

function bootstrapOwner(state, body, now, policy) {
  const nodeId = String(body.node_id || "");
  const generation = String(body.generation || "");
  if (!nodeId || !generation) {
    return fail(state, now, "identity_required");
  }
  if (state.owner_node_id || state.takeover_pending) {
    return fail(state, now, "authority_not_empty_for_bootstrap");
  }
  const next = {
    ...emptyState(),
    owner_node_id: nodeId,
    epoch: Math.max(state.epoch || 0, 0) + 1,
    generation,
    lease_expires_at: iso(addSeconds(now, policy.lease_ttl_seconds)),
  };
  return ok(next, now, "bootstrap_granted", true, true);
}

function renewLease(state, body, now, policy) {
  const nodeId = String(body.node_id || "");
  const generation = String(body.generation || "");
  const epoch = Number(body.epoch);
  const readinessOk = Boolean(body.readiness_ok);
  if (!readinessOk) {
    return fail(state, now, "local_readiness_failed");
  }
  if (state.takeover_pending) {
    return fail(state, now, "takeover_pending_renewal_refused");
  }
  if (
    state.owner_node_id !== nodeId ||
    state.epoch !== epoch ||
    state.generation !== generation ||
    !state.lease_expires_at ||
    now >= new Date(state.lease_expires_at)
  ) {
    return fail(state, now, "not_current_owner_or_lease_expired");
  }
  const next = {
    ...state,
    lease_expires_at: iso(addSeconds(now, policy.lease_ttl_seconds)),
  };
  return ok(next, now, "lease_renewed", true, true);
}

function requestTakeover(state, body, now, policy) {
  const requester = String(body.requester_node_id || "");
  const target = String(body.target_node_id || "");
  const generation = String(body.target_generation || "");
  if (!requester || requester === target || !target || !generation) {
    return fail(state, now, "invalid_takeover_request");
  }
  if (state.takeover_pending) {
    if (state.previous_owner_node_id === target && state.previous_generation === generation) {
      return ok(state, now, "takeover_already_pending", true, false, fencingProof(state, now, policy));
    }
    return fail(state, now, "conflicting_takeover_pending");
  }
  if (!state.owner_node_id) {
    return fail(state, now, "no_active_owner_to_take_over");
  }
  if (state.owner_node_id !== target || state.generation !== generation) {
    return fail(state, now, "takeover_target_mismatch");
  }
  const leaseDeadline = state.lease_expires_at ? new Date(state.lease_expires_at) : now;
  const next = {
    ...emptyState(),
    epoch: state.epoch,
    lease_expires_at: iso(leaseDeadline),
    takeover_pending: true,
    takeover_requested_at: iso(now),
    previous_owner_node_id: state.owner_node_id,
    previous_epoch: state.epoch,
    previous_generation: state.generation,
    self_fence_grace_until: iso(
      addSeconds(
        leaseDeadline > now ? leaseDeadline : now,
        policy.self_fence_grace_seconds,
      ),
    ),
    in_flight_drain_until: iso(addSeconds(now, policy.in_flight_drain_seconds)),
    proof_id: `lease-takeover-${state.epoch}-${Math.floor(now.getTime() / 1000)}`,
  };
  return ok(next, now, "takeover_pending", true, false, fencingProof(next, now, policy));
}

function acquireLease(state, body, now, policy) {
  const nodeId = String(body.node_id || "");
  const generation = String(body.generation || "");
  const previousEpoch = Number(body.previous_epoch);
  if (!nodeId || !generation || !Number.isFinite(previousEpoch)) {
    return fail(state, now, "invalid_acquire_request");
  }
  if (!readyToAcquire(state, now)) {
    return fail(state, now, "lease_not_yet_acquirable");
  }
  if (state.takeover_pending) {
    if (state.previous_epoch !== previousEpoch) {
      return fail(state, now, "previous_epoch_mismatch");
    }
    // Match Python lease authority: previous owner must not reacquire during
    // takeover. Failback uses an explicit returning-node path after remote fence.
    // readyToAcquire() already enforces drain + lease expiry + self-fence grace.
    if (nodeId === state.previous_owner_node_id) {
      return fail(state, now, "previous_owner_cannot_reacquire_during_takeover");
    }
  } else if (state.owner_node_id && state.epoch !== previousEpoch) {
    return fail(state, now, "previous_epoch_mismatch");
  }
  const next = {
    ...emptyState(),
    owner_node_id: nodeId,
    epoch: state.epoch + 1,
    generation,
    lease_expires_at: iso(addSeconds(now, policy.lease_ttl_seconds)),
  };
  return ok(next, now, "lease_acquired", true, true);
}

function requestPermit(state, body, now) {
  const origin = String(body.origin_node_id || "");
  const epoch = Number(body.epoch);
  const phase = phaseOf(state, now);
  const allowed =
    phase === "active" &&
    state.owner_node_id === origin &&
    state.epoch === epoch &&
    state.lease_expires_at &&
    now < new Date(state.lease_expires_at) &&
    !state.takeover_pending;
  return {
    ok: allowed,
    persist: false,
    response: {
      ok: allowed,
      state,
      phase,
      reason: allowed ? "permit_granted" : "permit_denied",
      request_permit: allowed,
    },
  };
}

function status(state, now, policy) {
  const phase = phaseOf(state, now);
  const proof =
    state.takeover_pending || phase === "acquirable"
      ? fencingProof(state, now, policy)
      : null;
  return {
    ok: true,
    persist: false,
    response: {
      ok: true,
      state,
      phase,
      reason: "status",
      fencing_proof: proof,
      request_permit: phase === "active",
    },
  };
}

function fencingProof(state, now, policy) {
  if (!state.previous_owner_node_id || !state.previous_generation || !state.proof_id) {
    return null;
  }
  // Keep proof freshness tied to the observation time while takeover remains
  // pending/acquirable. A fixed takeover-time expiry left standbys permanently
  // blocked_unfenced after the short grace+TTL window even though the lease
  // authority still allowed acquire.
  const verified = now;
  const expires = addSeconds(now, Math.max(policy.lease_ttl_seconds, 60));
  return {
    schema_version: 1,
    target_node_id: state.previous_owner_node_id,
    target_generation: state.previous_generation,
    source: policy.source_name,
    proof_id: state.proof_id,
    verified_at_utc: iso(verified),
    expires_at_utc: iso(expires),
    previous_epoch: state.previous_epoch,
    phase: phaseOf(state, now),
    acquirable: readyToAcquire(state, now),
  };
}

function ok(state, now, reason, success, permit, fencing_proof = null) {
  return {
    ok: success,
    persist: true,
    response: {
      ok: success,
      state,
      phase: phaseOf(state, now),
      reason,
      fencing_proof,
      request_permit: permit,
    },
  };
}

function fail(state, now, reason) {
  return {
    ok: false,
    persist: false,
    response: {
      ok: false,
      state,
      phase: phaseOf(state, now),
      reason,
      request_permit: false,
    },
  };
}

function addSeconds(date, seconds) {
  return new Date(date.getTime() + seconds * 1000);
}

function iso(date) {
  return new Date(date).toISOString().replace(/\.\d{3}Z$/, "Z");
}

function json(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
