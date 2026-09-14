// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {TrustAccessManager} from "./TrustAccessManager.sol";

contract IdentityRegistry is Pausable {
    enum IdentityState { NONE, ACTIVE, SUSPENDED, REVOKED }

    struct Identity {
        address controller;
        IdentityState state;
        uint64 keyVersion;
        uint64 updatedAt;
    }

    TrustAccessManager public immutable accessManager;
    mapping(bytes32 => Identity) private identities;
    mapping(address => bytes32) public didHashByController;

    event IdentityRegistered(bytes32 indexed didHash, address indexed controller);
    event IdentityStateChanged(bytes32 indexed didHash, IdentityState state);
    event IdentityKeyRotated(bytes32 indexed didHash, address indexed oldController, address indexed newController, uint64 keyVersion);

    modifier onlyRole(bytes32 role) {
        require(accessManager.hasRole(role, msg.sender), "not authorized");
        _;
    }

    constructor(address accessManagerAddress) {
        require(accessManagerAddress != address(0), "manager is zero");
        accessManager = TrustAccessManager(accessManagerAddress);
    }

    function registerIdentity(bytes32 didHash, address controller) external whenNotPaused onlyRole(accessManager.IDENTITY_ADMIN_ROLE()) {
        require(didHash != bytes32(0) && controller != address(0), "invalid identity");
        require(identities[didHash].state == IdentityState.NONE, "identity exists");
        require(didHashByController[controller] == bytes32(0), "controller exists");
        identities[didHash] = Identity(controller, IdentityState.ACTIVE, 1, uint64(block.timestamp));
        didHashByController[controller] = didHash;
        emit IdentityRegistered(didHash, controller);
    }

    function setIdentityState(bytes32 didHash, IdentityState state) external whenNotPaused onlyRole(accessManager.IDENTITY_ADMIN_ROLE()) {
        require(state != IdentityState.NONE, "invalid state");
        Identity storage identity = identities[didHash];
        require(identity.state != IdentityState.NONE, "identity missing");
        require(identity.state != IdentityState.REVOKED, "identity permanently revoked");
        identity.state = state;
        identity.updatedAt = uint64(block.timestamp);
        emit IdentityStateChanged(didHash, state);
    }

    function rotateKey(bytes32 didHash, address newController) external whenNotPaused onlyRole(accessManager.IDENTITY_ADMIN_ROLE()) {
        require(newController != address(0), "controller is zero");
        require(didHashByController[newController] == bytes32(0), "controller exists");
        Identity storage identity = identities[didHash];
        require(identity.state != IdentityState.NONE && identity.state != IdentityState.REVOKED, "identity inactive");
        address oldController = identity.controller;
        delete didHashByController[oldController];
        identity.controller = newController;
        identity.keyVersion += 1;
        identity.updatedAt = uint64(block.timestamp);
        didHashByController[newController] = didHash;
        emit IdentityKeyRotated(didHash, oldController, newController, identity.keyVersion);
    }

    function getIdentity(bytes32 didHash) external view returns (Identity memory) {
        return identities[didHash];
    }

    function isActive(bytes32 didHash) external view returns (bool) {
        return identities[didHash].state == IdentityState.ACTIVE;
    }

    function pause() external onlyRole(accessManager.EMERGENCY_ADMIN_ROLE()) { _pause(); }
    function unpause() external onlyRole(accessManager.EMERGENCY_ADMIN_ROLE()) { _unpause(); }
}

