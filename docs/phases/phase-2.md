# Phase 2 — Authoritative WS server + transport security

- **Phase ID:** 2
- **Version:** 0.2.0
- **Date:** 2026-07-25
- **Tests:** 44 (suite total at release; live-verified with two authenticated tabs)
- **Status:** ✅ DONE (44 tests; live-verified).

> Retrospective. Phase 2 was built before this tracking structure existed and is recorded here as
> part of the `v0.2.0` baseline release. Depends on [Phase 1](phase-1.md).

## Objective

Move authority out of the browser. The server — not the client — validates commands, assigns part
ids, and decides what the world contains; clients subscribe to diffs. The swap had to leave the
Phase 1 engine untouched, which meant the server's diff shape had to match what the local driver
already produced.

## What was built

**`server/` — the authoritative world.** `createServer.js` accepts `ws` connections behind a
bearer-token handshake; `auth.js` validates the token (generated at runtime to `.codeblox/token`,
which is gitignored) and assigns a role — `commander` may mutate, `viewer` may only subscribe.
Unauthenticated connections are rejected. `WorldStore.js` holds the world in memory and owns id
allocation. `commands.js` runs incoming batches through the shared `protocol.validate` and
`expand`, so the client and server agree on the vocabulary by construction; an invalid material
returns an error ack and changes nothing.

**Snapshot and diffs.** A connecting client receives a full snapshot applied as *settled*
geometry, so a reload or reconnect restores the world without replaying any drop animation.
Subsequent mutations broadcast as diffs to every subscriber.

**`src/net/WsClient.js`** drops into `main.js` in place of the Phase 1 local driver behind the
same diff shape — the engine did not change. When the server is unreachable, `main.js` falls back
to applying command batches locally, so the viewer stays usable offline.

**Ports.** The server listens on 7799; 8787 was abandoned because it falls inside a Windows
excluded port range and fails with `EACCES`. `npm start` runs the viewer (:5173) and the server
together via `concurrently`.

## Files changed

| File | Change |
|---|---|
| `server/createServer.js` | `ws` server, connection lifecycle, snapshot on connect, diff broadcast |
| `server/auth.js` | Bearer-token handshake, `commander`/`viewer` role assignment |
| `server/WorldStore.js` | Authoritative in-memory world, server-side id allocation |
| `server/commands.js` | Batch validation/expansion via the shared protocol, error acks |
| `server/index.js` | Entry point and bind config |
| `src/net/WsClient.js` | Snapshot + diff client, token in the handshake |
| `src/main.js` | `WsClient` wiring with local-apply fallback when the server is unreachable |
| `package.json` | `serve` / `start` scripts, `ws` + `concurrently` dependencies |
| `.gitignore` | Ignore the runtime-generated `.codeblox/` token dir |

## Verification

- `npm start`, then two authenticated tabs → both mirror a single command stream.
- Connecting without a token → rejected.
- `{op:'box',mat:'not_a_material'}` → error ack, world unchanged.
- Reloading a tab → the snapshot restores the world with no re-animation.
- Unit suites: `tests/server.test.js`, `tests/world-store.test.js`.

## Notes / follow-ups

### Deferred: WSS/TLS termination (not scheduled)

The plan lists WSS/TLS as part of this phase; it was **not** built. `server/createServer.js`
creates a plain `ws` server with no TLS context and no reverse-proxy configuration, so the
transport is unencrypted. The bearer token in the handshake is therefore sent in clear text.

This is acceptable while everything is localhost — the viewer, the server, and the token file all
sit on one machine. It stops being acceptable the moment the server is network-exposed.

**Blocks:** deploying to a VPS, and any remote use of the Go CLI — including `codeblox auth status`,
whose live check would otherwise put a credential on the wire unencrypted.

**Scope when picked up:** terminate TLS either natively in `createServer.js` (cert/key paths bound
by env, per the no-secrets-in-config rule) or behind nginx/Caddy, and switch the client endpoint
scheme to `wss://`. Decide which before P-3 hard-codes an endpoint default.

Not scheduled into the current plan — fold it into P-3 or cut it as its own phase when the server
is about to leave localhost.
