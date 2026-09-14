import { defineConfig } from "hardhat/config";
import hardhatEthers from "@nomicfoundation/hardhat-ethers";
import hardhatTypechain from "@nomicfoundation/hardhat-typechain";
import hardhatMocha from "@nomicfoundation/hardhat-mocha";
import hardhatEthersChaiMatchers from "@nomicfoundation/hardhat-ethers-chai-matchers";
import hardhatNetworkHelpers from "@nomicfoundation/hardhat-network-helpers";

const privateKey = process.env.BLOCKCHAIN_SIGNER_PRIVATE_KEY;

export default defineConfig({
  plugins: [hardhatEthers, hardhatTypechain, hardhatMocha, hardhatEthersChaiMatchers, hardhatNetworkHelpers],
  solidity: {
    version: "0.8.28",
    settings: { optimizer: { enabled: true, runs: 200 } },
  },
  networks: {
    besu: {
      type: "http",
      url: process.env.WEB3_PROVIDER_URL ?? "http://127.0.0.1:8545",
      chainId: Number(process.env.CHAIN_ID ?? 1337),
      accounts: privateKey ? [privateKey] : [],
    },
  },
});
