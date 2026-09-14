import hre from "hardhat";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

async function deploymentData(contract: any, name: string) {
  const receipt = await contract.deploymentTransaction()?.wait();
  const artifact = await hre.artifacts.readArtifact(name);
  return {
    version: "1.0.0",
    address: await contract.getAddress(),
    abi: artifact.abi,
    deploymentTxHash: receipt?.hash,
    deploymentBlock: receipt?.blockNumber,
  };
}

async function main() {
  const { ethers } = await hre.network.connect();
  const [governance] = await ethers.getSigners();
  const manager = await ethers.deployContract("TrustAccessManager", [governance.address]);
  await manager.waitForDeployment();
  const identity = await ethers.deployContract("IdentityRegistry", [await manager.getAddress()]);
  await identity.waitForDeployment();
  const asset = await ethers.deployContract("AssetRegistry", [await manager.getAddress()]);
  await asset.waitForDeployment();

  const output = {
    chainId: Number((await ethers.provider.getNetwork()).chainId),
    contracts: {
      TrustAccessManager: await deploymentData(manager, "TrustAccessManager"),
      IdentityRegistry: await deploymentData(identity, "IdentityRegistry"),
      AssetRegistry: await deploymentData(asset, "AssetRegistry"),
    },
  };
  const directory = path.resolve("deployments");
  await mkdir(directory, { recursive: true });
  await writeFile(path.join(directory, `${output.chainId}.json`), JSON.stringify(output, null, 2));
  console.log(JSON.stringify(output, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
