# Fixes

Internal index of fix items (`F-N`). The last column holds the phase id or the release version;
it is left blank until the fix is finalized. Detail files: `docs/fixes/`.

| ID | Symptom | Root cause | Fix | Phase |
|----|---------|------------|-----|-------|
| [F-1](fixes/F-1.md) | Past roughly 330 parts, every codeblox command fails at the handshake with ErrMessageTooBig — including the clear that would recover the world. Nothing short of restarting the server helps, and `codeblox info` keeps reporting a healthy server from its cache while every build fails. | (tbd) | (tbd) | 0.7.0 |
| [F-2](fixes/F-2.md) | An out-of-bounds `fill` sails through the skill's client-side bounds gate and is only refused by the server, mid-build — where there is no partial undo, so the world is left half-built. The gate reports the batch as clean. | (tbd) | (tbd) | 0.7.0 |
