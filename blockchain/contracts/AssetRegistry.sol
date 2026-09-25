// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {TrustAccessManager} from "./TrustAccessManager.sol";

contract AssetRegistry is ERC721, Pausable {
    enum AssetState { NONE, ACTIVE, FROZEN, ARCHIVED, REVOKED }

    struct AssetProof {
        bytes32 assetIdHash;
        bytes32 contentHash;
        bytes32 metadataHash;
        AssetState state;
    }

    TrustAccessManager public immutable accessManager;
    uint256 private nextTokenId = 1;
    mapping(uint256 => AssetProof) private proofs;
    mapping(bytes32 => uint256) public tokenByAssetIdHash;

    event AssetMinted(uint256 indexed tokenId, bytes32 indexed assetIdHash, address indexed owner, bytes32 contentHash, bytes32 metadataHash);
    event AssetTransferred(uint256 indexed tokenId, address indexed from, address indexed to);
    event AssetFrozen(uint256 indexed tokenId, bool frozen);
    event AssetUnfrozen(uint256 indexed tokenId);
    event AssetArchived(uint256 indexed tokenId);

    modifier onlyRole(bytes32 role) {
        require(accessManager.hasRole(role, msg.sender), "not authorized");
        _;
    }

    constructor(address accessManagerAddress) ERC721("ChainControl Asset", "CCA") {
        require(accessManagerAddress != address(0), "manager is zero");
        accessManager = TrustAccessManager(accessManagerAddress);
    }

    function mintAsset(address owner, bytes32 assetIdHash, bytes32 contentHash, bytes32 metadataHash)
        external whenNotPaused onlyRole(accessManager.ASSET_MINTER_ROLE()) returns (uint256 tokenId)
    {
        require(owner != address(0) && assetIdHash != bytes32(0), "invalid asset");
        require(tokenByAssetIdHash[assetIdHash] == 0, "asset exists");
        tokenId = nextTokenId++;
        proofs[tokenId] = AssetProof(assetIdHash, contentHash, metadataHash, AssetState.ACTIVE);
        tokenByAssetIdHash[assetIdHash] = tokenId;
        _safeMint(owner, tokenId);
        emit AssetMinted(tokenId, assetIdHash, owner, contentHash, metadataHash);
    }

    function setFrozen(uint256 tokenId, bool frozen) external whenNotPaused onlyRole(accessManager.EMERGENCY_ADMIN_ROLE()) {
        require(_ownerOf(tokenId) != address(0), "asset missing");
        require(proofs[tokenId].state != AssetState.REVOKED, "asset revoked");
        proofs[tokenId].state = frozen ? AssetState.FROZEN : AssetState.ACTIVE;
        emit AssetFrozen(tokenId, frozen);
        if (!frozen) emit AssetUnfrozen(tokenId);
    }

    function archiveAsset(uint256 tokenId) external whenNotPaused onlyRole(accessManager.EMERGENCY_ADMIN_ROLE()) {
        require(_ownerOf(tokenId) != address(0), "asset missing");
        require(proofs[tokenId].state != AssetState.REVOKED, "asset revoked");
        proofs[tokenId].state = AssetState.ARCHIVED;
        emit AssetArchived(tokenId);
    }

    function governedTransfer(uint256 tokenId, address from, address to)
        external whenNotPaused onlyRole(accessManager.TRANSFER_AGENT_ROLE())
    {
        require(ownerOf(tokenId) == from, "owner changed");
        require(to != address(0), "recipient is zero");
        _transfer(from, to, tokenId);
    }

    function getAssetProof(uint256 tokenId) external view returns (AssetProof memory) {
        require(_ownerOf(tokenId) != address(0), "asset missing");
        return proofs[tokenId];
    }

    function _update(address to, uint256 tokenId, address auth) internal override whenNotPaused returns (address from) {
        from = _ownerOf(tokenId);
        if (from != address(0)) {
            require(proofs[tokenId].state == AssetState.ACTIVE, "asset not transferable");
            if (to != address(0)) {
                require(accessManager.hasRole(accessManager.TRANSFER_AGENT_ROLE(), msg.sender), "governed transfer required");
            }
        }
        address previous = super._update(to, tokenId, auth);
        if (previous != address(0) && to != address(0)) emit AssetTransferred(tokenId, previous, to);
        return previous;
    }

    function pause() external onlyRole(accessManager.EMERGENCY_ADMIN_ROLE()) { _pause(); }
    function unpause() external onlyRole(accessManager.EMERGENCY_ADMIN_ROLE()) { _unpause(); }
}
