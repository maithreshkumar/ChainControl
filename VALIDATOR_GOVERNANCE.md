# Validator Governance

Every newly admitted machine starts as a full/replica node. A Django superuser may request promotion only when the node is admitted, online, and reports 100% synchronization.

The service reads the actual set with `qbft_getValidatorsByBlockNumber("latest")`, submits `qbft_proposeValidatorVote(address, true)` to configured validator RPC endpoints, and publishes the same pending proposal only to authenticated agents whose nodes are already actual validators. This lets remote validators cast their own local vote without exposing management RPC over the network. The node becomes `VALIDATOR` in MySQL only after its address appears in Besu. A still-pending majority stays `IN_PROGRESS`; it is not reported as completed.

Removal uses the same flow with `false`. ChainControl refuses to remove the final validator and changes the projection back to `FULL_NODE` only after the address disappears from the actual set. Use **Refresh selected operations from the actual QBFT validator set** for an in-progress operation.

Before voting, confirm enough validators are online to retain QBFT safety/liveness. Do not promote all full nodes merely to increase node count. The active validator count is discovered dynamically and the initial four are only bootstrap defaults.

Required RPC namespaces (`QBFT`, `PERM`, `ADMIN`) are private management surfaces. Normal users, validators-as-application-users, Platform Admins, Managers, and Auditors cannot initiate this operation; Django superuser plus actual QBFT votes are both required.
