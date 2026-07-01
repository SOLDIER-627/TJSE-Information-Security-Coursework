// 部署脚本
import hre from "hardhat";
import fs from "fs";

async function main() {
  console.log("开始部署茅台酒溯源智能合约...\n");

  // 获取部署者账户
  const [deployer] = await hre.ethers.getSigners();
  console.log("部署账户地址:", deployer.address);
  console.log("账户余额:", (await hre.ethers.provider.getBalance(deployer.address)).toString(), "wei\n");

  // 部署合约
  const MoutaiTrace = await hre.ethers.getContractFactory("MoutaiTrace");
  const moutaiTrace = await MoutaiTrace.deploy();

  await moutaiTrace.waitForDeployment();

  const contractAddress = await moutaiTrace.getAddress();
  console.log("MoutaiTrace 合约已部署到:", contractAddress);

  // 输出部署信息
  console.log("\n========== 部署完成 ==========");
  console.log("合约地址:", contractAddress);
  console.log("管理员地址:", deployer.address);
  console.log("================================\n");

  // 保存部署信息到文件
  const deployInfo = {
    network: hre.network.name,
    contractAddress: contractAddress,
    deployer: deployer.address,
    deployTime: new Date().toISOString(),
    abi: (await hre.artifacts.readArtifact("MoutaiTrace")).abi
  };

  // 确保目录存在
  const deployDir = "./deployments";
  if (!fs.existsSync(deployDir)) {
    fs.mkdirSync(deployDir, { recursive: true });
  }

  fs.writeFileSync(
    `${deployDir}/${hre.network.name}.json`,
    JSON.stringify(deployInfo, null, 2)
  );
  console.log(`部署信息已保存到: ${deployDir}/${hre.network.name}.json`);
}

// 执行部署
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
