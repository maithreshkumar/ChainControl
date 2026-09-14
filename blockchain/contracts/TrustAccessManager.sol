// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

contract TrustAccessManager is AccessControl {
    bytes32 public constant IDENTITY_ADMIN_ROLE = keccak256("IDENTITY_ADMIN_ROLE");
    bytes32 public constant ACCESS_ADMIN_ROLE = keccak256("ACCESS_ADMIN_ROLE");
    bytes32 public constant TRANSFER_AGENT_ROLE = keccak256("TRANSFER_AGENT_ROLE");
    bytes32 public constant ASSET_MINTER_ROLE = keccak256("ASSET_MINTER_ROLE");
    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");
    bytes32 public constant EMERGENCY_ADMIN_ROLE = keccak256("EMERGENCY_ADMIN_ROLE");

    constructor(address governance) {
        require(governance != address(0), "governance is zero");
        _grantRole(DEFAULT_ADMIN_ROLE, governance);
        _grantRole(IDENTITY_ADMIN_ROLE, governance);
        _grantRole(ACCESS_ADMIN_ROLE, governance);
        _grantRole(TRANSFER_AGENT_ROLE, governance);
        _grantRole(ASSET_MINTER_ROLE, governance);
        _grantRole(AUDITOR_ROLE, governance);
        _grantRole(EMERGENCY_ADMIN_ROLE, governance);
    }
}
