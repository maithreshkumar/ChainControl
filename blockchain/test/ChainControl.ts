import { expect } from "chai";
import hre from "hardhat";

const { ethers } = await hre.network.create();

describe("ChainControl contracts", function () {
  async function deploy() {
    const [governance, alice, bob, outsider] = await ethers.getSigners();
    const manager = await ethers.deployContract("TrustAccessManager", [governance.address]);
    const identity = await ethers.deployContract("IdentityRegistry", [await manager.getAddress()]);
    const asset = await ethers.deployContract("AssetRegistry", [await manager.getAddress()]);
    return { governance, alice, bob, outsider, manager, identity, asset };
  }

  it("rejects unauthorized identity registration", async function () {
    const { identity, outsider, alice } = await deploy();
    await expect(identity.connect(outsider).registerIdentity(ethers.id("did:ethr:alice"), alice.address)).to.be.revertedWith("not authorized");
  });

  it("registers and permanently revokes an identity", async function () {
    const { identity, alice } = await deploy();
    const didHash = ethers.id("did:ethr:alice");
    await identity.registerIdentity(didHash, alice.address);
    expect(await identity.isActive(didHash)).to.equal(true);
    await identity.setIdentityState(didHash, 3);
    expect(await identity.isActive(didHash)).to.equal(false);
    await expect(identity.setIdentityState(didHash, 1)).to.be.revertedWith("identity permanently revoked");
  });

  it("prevents duplicate and unauthorized minting", async function () {
    const { asset, alice, outsider } = await deploy();
    const assetId = ethers.id("asset-1");
    const content = ethers.id("content");
    const metadata = ethers.id("metadata");
    await expect(asset.connect(outsider).mintAsset(alice.address, assetId, content, metadata)).to.be.revertedWith("not authorized");
    await asset.mintAsset(alice.address, assetId, content, metadata);
    await expect(asset.mintAsset(alice.address, assetId, content, metadata)).to.be.revertedWith("asset exists");
  });

  it("allows owner transfer but blocks a frozen asset", async function () {
    const { asset, alice, bob } = await deploy();
    await asset.mintAsset(alice.address, ethers.id("asset-1"), ethers.id("content"), ethers.id("metadata"));
    await asset.connect(alice).transferFrom(alice.address, bob.address, 1);
    expect(await asset.ownerOf(1)).to.equal(bob.address);
    await asset.setFrozen(1, true);
    await expect(asset.connect(bob).transferFrom(bob.address, alice.address, 1)).to.be.revertedWith("asset not transferable");
  });
});
