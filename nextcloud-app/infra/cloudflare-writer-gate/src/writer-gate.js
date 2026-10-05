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
  constructor(state, env) {
    this.state = state;
    this.env = env;
  }

  async fetch(request) {
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
      await this.state.storage.put("lease", decision.response.state);
    }
    return json(decision.response, decision.ok ? 200 : 409);
  }

  async loadState() {
    const stored = await this.state.storage.get("lease");
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
      if (!authorized(request, env.LEASE_API_TOKEN)) {
        return json({ ok: false, reason: "unauthorized" }, 401);
      }
      const id = env.WRITER_LEASE.idFromName("filantropia-odoo-writer");
      const stub = env.WRITER_LEASE.get(id);
      return stub.fetch(request);
    }

    // Public website gate: only proxy when the current epoch owns the origin.
    if (!env.ORIGIN_TRL5_URL || !env.ORIGIN_FRANK_URL) {
      return new Response("writer gate misconfigured", { status: 503 });
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
      return new Response("lease authority unavailable", { status: 503 });
    }
    const payload = await statusResponse.json();
    if (!payload.ok || payload.phase !== "active" || !payload.state?.owner_node_id) {
      return new Response("no active writer epoch", { status: 503 });
    }
    const owner = payload.state.owner_node_id;
    const origin =
      owner === "trl5"
        ? env.ORIGIN_TRL5_URL
        : owner === "frank"
          ? env.ORIGIN_FRANK_URL
          : null;
    if (!origin) {
      return new Response("unknown writer origin", { status: 503 });
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
    const permit = await permitResponse.json();
    if (!permit.ok || !permit.request_permit) {
      return new Response("writer permit denied", { status: 503 });
    }

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
    return fetch(
      new Request(upstream.toString(), {
        method: request.method,
        headers,
        body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
        redirect: "manual",
      }),
    );
  },
};

function authorized(request, token) {
  if (!token) {
    return false;
  }
  const header = request.headers.get("Authorization") || "";
  return header === `Bearer ${token}`;
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
  const expires = state.self_fence_grace_until
    ? new Date(state.self_fence_grace_until)
    : state.lease_expires_at
      ? new Date(state.lease_expires_at)
      : now;
  const verified = state.takeover_requested_at
    ? new Date(state.takeover_requested_at)
    : now;
  return {
    schema_version: 1,
    target_node_id: state.previous_owner_node_id,
    target_generation: state.previous_generation,
    source: policy.source_name,
    proof_id: state.proof_id,
    verified_at_utc: iso(verified),
    expires_at_utc: iso(addSeconds(expires, policy.lease_ttl_seconds)),
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
