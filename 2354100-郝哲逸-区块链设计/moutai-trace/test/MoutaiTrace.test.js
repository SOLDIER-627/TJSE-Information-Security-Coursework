import { expect } from "chai";
import pkg from "hardhat";
const { ethers } = pkg;

describe("MoutaiTrace", function () {
  let moutaiTrace;
  let admin;
  let manufacturer;
  let logistics;
  let retailer;

  before(async function () {
    [admin, manufacturer, logistics, retailer] = await ethers.getSigners();
  });

  beforeEach(async function () {
    const MoutaiTrace = await ethers.getContractFactory("MoutaiTrace");
    moutaiTrace = await MoutaiTrace.deploy();
    await moutaiTrace.waitForDeployment();
  });

  describe("部署", function () {
    it("应该正确设置管理员", async function () {
      expect(await moutaiTrace.admin()).to.equal(admin.address);
    });

    it("管理员应该是授权节点", async function () {
      expect(await moutaiTrace.authorizedNodes(admin.address)).to.be.true;
    });
  });

  describe("节点管理", function () {
    it("管理员可以授权新节点", async function () {
      await moutaiTrace.authorizeNode(manufacturer.address, "生产厂家");
      expect(await moutaiTrace.authorizedNodes(manufacturer.address)).to.be.true;
      expect(await moutaiTrace.getNodeName(manufacturer.address)).to.equal("生产厂家");
    });

    it("非管理员不能授权节点", async function () {
      await expect(
        moutaiTrace.connect(manufacturer).authorizeNode(logistics.address, "物流中心")
      ).to.be.revertedWith("Only admin can call this function");
    });

    it("管理员可以移除节点授权", async function () {
      await moutaiTrace.authorizeNode(manufacturer.address, "生产厂家");
      await moutaiTrace.removeNode(manufacturer.address);
      expect(await moutaiTrace.authorizedNodes(manufacturer.address)).to.be.false;
    });
  });

  describe("产品注册", function () {
    beforeEach(async function () {
      await moutaiTrace.authorizeNode(manufacturer.address, "生产厂家");
    });

    it("授权节点可以注册产品", async function () {
      const tx = await moutaiTrace.connect(manufacturer).registerProduct(
        "飞天茅台",
        "BATCH-2024-001",
        Math.floor(Date.now() / 1000)
      );

      // 验证事件被触发
      await expect(tx).to.emit(moutaiTrace, "ProductRegistered");

      expect(await moutaiTrace.productCount()).to.equal(1);
    });

    it("非授权节点不能注册产品", async function () {
      await expect(
        moutaiTrace.connect(logistics).registerProduct("飞天茅台", "BATCH-2024-001", 0)
      ).to.be.revertedWith("Only authorized nodes can call this function");
    });

    it("注册后产品信息正确", async function () {
      const productionDate = Math.floor(Date.now() / 1000);
      await moutaiTrace.connect(manufacturer).registerProduct(
        "飞天茅台",
        "BATCH-2024-001",
        productionDate
      );

      const product = await moutaiTrace.getProduct(1);
      expect(product.id).to.equal(1);
      expect(product.name).to.equal("飞天茅台");
      expect(product.batchNo).to.equal("BATCH-2024-001");
      expect(product.productionDate).to.equal(productionDate);
      expect(product.manufacturer).to.equal(manufacturer.address);
      expect(product.currentOwner).to.equal(manufacturer.address);
      // 产品注册后处于生产阶段（stage 1）
      expect(product.currentStage).to.equal(1);
    });
  });

  describe("产品运输", function () {
    beforeEach(async function () {
      // 授权所有节点
      await moutaiTrace.authorizeNode(manufacturer.address, "生产厂家");
      await moutaiTrace.authorizeNode(logistics.address, "物流中心");
      await moutaiTrace.authorizeNode(retailer.address, "零售商");

      // 注册产品
      await moutaiTrace.connect(manufacturer).registerProduct(
        "飞天茅台",
        "BATCH-2024-001",
        Math.floor(Date.now() / 1000)
      );
    });

    it("持有者可以转移产品", async function () {
      const tx = await moutaiTrace.connect(manufacturer).recordTransfer(
        1,
        logistics.address,
        "贵州茅台镇",
        "上海物流中心",
        "正常发货"
      );

      await expect(tx)
        .to.emit(moutaiTrace, "TransferRecorded");

      const product = await moutaiTrace.getProduct(1);
      expect(product.currentOwner).to.equal(logistics.address);
      // 从生产阶段(1)转移到物流阶段(2)
      expect(product.currentStage).to.equal(2);
    });

    it("非持有者不能转移产品", async function () {
      await expect(
        moutaiTrace.connect(logistics).recordTransfer(
          1,
          retailer.address,
          "上海物流中心",
          "北京零售店",
          "测试"
        )
      ).to.be.revertedWithCustomError(moutaiTrace, "NotProductOwner");
    });

    it("不能转移给非授权节点", async function () {
      const [_, __, ___, ____, stranger] = await ethers.getSigners();
      await expect(
        moutaiTrace.connect(manufacturer).recordTransfer(
          1,
          stranger.address,
          "贵州茅台镇",
          "未知地点",
          "测试"
        )
      ).to.be.revertedWithCustomError(moutaiTrace, "NotAuthorizedNode");
    });

    it("运输历史记录正确", async function () {
      // 第一次运输：厂家 -> 物流
      await moutaiTrace.connect(manufacturer).recordTransfer(
        1,
        logistics.address,
        "贵州茅台镇",
        "上海物流中心",
        "正常发货"
      );

      // 第二次运输：物流 -> 零售
      await moutaiTrace.connect(logistics).recordTransfer(
        1,
        retailer.address,
        "上海物流中心",
        "北京零售店",
        "配送完成"
      );

      const history = await moutaiTrace.getProductHistory(1);
      expect(history.length).to.equal(2);
      expect(history[0].from).to.equal(manufacturer.address);
      expect(history[0].to).to.equal(logistics.address);
      expect(history[1].from).to.equal(logistics.address);
      expect(history[1].to).to.equal(retailer.address);
    });
  });

  describe("查询功能", function () {
    beforeEach(async function () {
      await moutaiTrace.authorizeNode(manufacturer.address, "生产厂家");
      await moutaiTrace.connect(manufacturer).registerProduct(
        "飞天茅台",
        "BATCH-2024-001",
        Math.floor(Date.now() / 1000)
      );
    });

    it("可以获取所有产品ID", async function () {
      const ids = await moutaiTrace.getAllProductIds();
      expect(ids.length).to.equal(1);
      expect(ids[0]).to.equal(1);
    });

    it("可以查询不存在的产品", async function () {
      await expect(
        moutaiTrace.getProduct(999)
      ).to.be.revertedWithCustomError(moutaiTrace, "ProductNotFound");
    });

    it("可以获取产品历史记录数量", async function () {
      const count = await moutaiTrace.getProductHistoryCount(1);
      expect(count).to.equal(0);
    });
  });

  describe("输入验证", function () {
    beforeEach(async function () {
      await moutaiTrace.authorizeNode(manufacturer.address, "生产厂家");
    });

    it("不能注册空名称的产品", async function () {
      await expect(
        moutaiTrace.connect(manufacturer).registerProduct("", "BATCH-001", 0)
      ).to.be.revertedWithCustomError(moutaiTrace, "EmptyString");
    });

    it("不能注册空批次号的产品", async function () {
      await expect(
        moutaiTrace.connect(manufacturer).registerProduct("飞天茅台", "", 0)
      ).to.be.revertedWithCustomError(moutaiTrace, "EmptyString");
    });
  });

  describe("管理员转移", function () {
    it("管理员可以转移权限", async function () {
      await moutaiTrace.transferAdmin(manufacturer.address);
      expect(await moutaiTrace.admin()).to.equal(manufacturer.address);
      expect(await moutaiTrace.authorizedNodes(manufacturer.address)).to.be.true;
    });

    it("非管理员不能转移权限", async function () {
      await expect(
        moutaiTrace.connect(manufacturer).transferAdmin(logistics.address)
      ).to.be.revertedWith("Only admin can call this function");
    });
  });

  // 辅助函数：获取交易时间戳
  async function getTimestamp(tx) {
    const receipt = await tx.wait();
    const block = await ethers.provider.getBlock(receipt.blockNumber);
    return block.timestamp;
  }
});