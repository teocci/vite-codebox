import { createServer } from './createServer.js'
import { WS } from '@codeblox/shared/config.js'

const srv = createServer({
  host: WS.host,
  port: WS.port,
  authRequired: WS.authRequired,
  seed: WS.seed,
})

console.log(`[codeblox] ws server on ws://${WS.host}:${WS.port}`)
console.log(
  `[codeblox] auth.required=${WS.authRequired}` +
    (WS.authRequired ? ` token=${srv.auth.masked}` : '') +
    ` · seed=${WS.seed} · parts=${srv.store.size}`,
)

const shutdown = () => srv.close().then(() => process.exit(0))
process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
