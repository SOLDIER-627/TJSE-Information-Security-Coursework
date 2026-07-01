import "@nomicfoundation/hardhat-toolbox";

/** @type import('hardhat/config').HardhatUserConfig */
export default {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      }
    }
  },
  networks: {
    // Ganache本地网络配置
    ganache: {
      url: "http://127.0.0.1:7545",
      chainId: 1337
    },
    // Hardhat内置网络
    hardhat: {
      chainId: 31337
    },
    // 本地开发网络（用于Hardhat node）
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337
    }
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts"
  }
};
