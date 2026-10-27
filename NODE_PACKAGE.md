# Node Package

Source templates live in `node-package/`. Build a distributable archive from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\node-package\build-package.ps1
```

The result is `node-package/dist/ChainControl-Node.zip`. It includes the Observer source, agent, Compose definition, scripts, and empty configuration directory. It deliberately excludes `.env`, credentials, genesis, chain data, and all private keys.

`setup.bat` checks Docker, generates one local Besu identity, enrolls it, waits for approval, verifies the canonical genesis SHA-256, and writes bootnodes plus the initial allowlist. `start.bat` launches Besu, the control agent, and Observer. `stop.bat` preserves state. `status.bat` queries real local sync state.

The named volume `chaincontrol-<node UUID>-data` holds the private node key and blockchain database. `.node/credential` authenticates only that node to its status/configuration/heartbeat endpoints. Back both up according to organizational policy; do not copy an identity to another computer.

`reset-dev-node.bat` is intentionally destructive and requires the exact phrase `DELETE-THIS-DEV-NODE`. It is for disposable development nodes only and deletes that package's local key and chain copy. It does not reset the shared chain.

