# NFT Model

`AssetRegistry` uses OpenZeppelin ERC-721. A token represents one unique governed physical or digital asset. On-chain data contains the application UUID hash, content/metadata hashes, owner address, and lifecycle state; confidential metadata and files remain off-chain.

Minting requires `ASSET_MINTER_ROLE`. Every ownership update other than mint/burn requires `TRANSFER_AGENT_ROLE`, including inherited `transferFrom` and `safeTransferFrom`, which prevents an owner from bypassing ChainControl approval. `governedTransfer` also validates the current owner and rejects frozen or archived assets.

The business workflow is request → recipient acceptance → independent scoped approval → blockchain pending → completed after receipt/event indexing. MySQL ownership is a projection, never changed optimistically. Reconciliation compares it with `ownerOf` and records discrepancies. Freeze, unfreeze, archive, mint, and transfer emit auditable contract events.
