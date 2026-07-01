import { useState } from 'react';
import { Card, Button, Space, Typography, message, Progress, Descriptions, Tag, Divider, Alert } from 'antd';
import { PlayCircleOutlined, CheckCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { ethers } from 'ethers';

const { Title, Text } = Typography;

// 随机数据配置
const PRODUCT_NAMES = [
  '飞天茅台', '五星茅台', '茅台王子酒', '茅台迎宾酒', '赖茅酒',
  '茅台年份酒', '茅台纪念酒', '贵州大曲', '华茅酒', '汉酱酒'
];

const BATCH_PREFIXES = ['MT', 'FY', 'WW', 'WZ', 'LM', 'NF', 'JN', 'DZ', 'GZ', 'HM'];

const LOCATIONS = {
  material: ['贵州仁怀', '四川泸州', '云南昭通', '贵州毕节'],
  production: ['贵州茅台镇', '贵州仁怀市', '贵州遵义市'],
  logistics: ['上海物流中心', '北京物流中心', '广州物流中心', '成都物流中心'],
  retail: ['北京专卖店', '上海专卖店', '广州专卖店', '深圳专卖店', '杭州专卖店']
};

const VERIFIERS = [
  '李晓婷', '张伟豪', '王雅娜', '刘军宇', '陈雪婷', '杨宇航', '赵晓梅',
  '周建华', '吴晓明', '郑秀芳'
];

// 随机选择函数
const randomChoice = (arr) => arr[Math.floor(Math.random() * arr.length)];
const randomInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

// 生成随机批次号
const generateBatchNo = () => {
  const prefix = randomChoice(BATCH_PREFIXES);
  const year = new Date().getFullYear();
  const num = randomInt(1000, 9999);
  return `${prefix}-${year}-${num}`;
};

export function SimulationPanel({ contract, provider, account, accounts, isAdmin, onSimulationComplete }) {
  const [simulating, setSimulating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState('');
  const [simulationResult, setSimulationResult] = useState(null);

  const runSimulation = async () => {
    if (!contract) {
      message.error('请先连接合约');
      return;
    }

    if (!isAdmin) {
      message.error('只有管理员才能运行模拟');
      return;
    }

    if (accounts.length < 12) {
      message.error('需要至少12个账户来运行模拟');
      return;
    }

    if (!provider) {
      message.error('Provider未初始化');
      return;
    }

    setSimulating(true);
    setProgress(0);
    setSimulationResult(null);

    try {
      // 获取合约ABI和地址
      const contractABI = contract.interface;
      const contractAddress = await contract.getAddress();

      // 分配账户角色
      const materialSuppliers = accounts.slice(1, 3);      // 2个原料供应商
      const producers = accounts.slice(3, 6);               // 3个生产商
      const wholesalers = accounts.slice(6, 8);             // 2个批发商
      const retailers = accounts.slice(8, 13);              // 5个零售商

      const totalSteps = 12 + 5 * 3; // 授权节点 + 产品模拟
      let currentStep = 0;

      const updateProgress = (text) => {
        currentStep++;
        setProgress(Math.floor((currentStep / totalSteps) * 100));
        setProgressText(text);
      };

      // 检查并授权原料供应商
      for (let i = 0; i < materialSuppliers.length; i++) {
        updateProgress(`检查/授权原料供应商 ${i + 1}...`);
        const isAuth = await contract.authorizedNodes(materialSuppliers[i]);
        if (!isAuth) {
          const tx = await contract.authorizeNodeWithInfo(
            materialSuppliers[i],
            `原料供应商${String.fromCharCode(65 + i)}`,
            `138${randomInt(10000000, 99999999)}`,
            '原料供给',
            randomChoice(LOCATIONS.material),
            '茅台酒原料供应商，提供优质高粱、小麦等原料'
          );
          await tx.wait();
        }
      }

      // 检查并授权生产商
      for (let i = 0; i < producers.length; i++) {
        updateProgress(`检查/授权生产商 ${i + 1}...`);
        const isAuth = await contract.authorizedNodes(producers[i]);
        if (!isAuth) {
          const tx = await contract.authorizeNodeWithInfo(
            producers[i],
            `茅台酒厂${String.fromCharCode(65 + i)}`,
            `139${randomInt(10000000, 99999999)}`,
            '产品生产',
            randomChoice(LOCATIONS.production),
            '贵州茅台酒生产基地，传承千年酿造工艺'
          );
          await tx.wait();
        }
      }

      // 检查并授权批发商
      for (let i = 0; i < wholesalers.length; i++) {
        updateProgress(`检查/授权批发商 ${i + 1}...`);
        const isAuth = await contract.authorizedNodes(wholesalers[i]);
        if (!isAuth) {
          const tx = await contract.authorizeNodeWithInfo(
            wholesalers[i],
            `批发中心${String.fromCharCode(65 + i)}`,
            `137${randomInt(10000000, 99999999)}`,
            '批发销售',
            randomChoice(LOCATIONS.logistics),
            '茅台酒批发销售中心'
          );
          await tx.wait();
        }
      }

      // 检查并授权零售商
      for (let i = 0; i < retailers.length; i++) {
        updateProgress(`检查/授权零售商 ${i + 1}...`);
        const isAuth = await contract.authorizedNodes(retailers[i]);
        if (!isAuth) {
          const tx = await contract.authorizeNodeWithInfo(
            retailers[i],
            `零售店${String.fromCharCode(65 + i)}`,
            `136${randomInt(10000000, 99999999)}`,
            '零售',
            randomChoice(LOCATIONS.retail),
            '茅台酒官方授权零售店'
          );
          await tx.wait();
        }
      }

      const productsCreated = [];
      const numProducts = randomInt(3, 5);

      // 获取当前产品数量，用于计算新产品ID
      const startProductCount = await contract.productCount();

      // 模拟产品生命周期
      for (let p = 1; p <= numProducts; p++) {
        const productName = randomChoice(PRODUCT_NAMES);
        const batchNo = generateBatchNo();
        const productionDate = Math.floor(Date.now() / 1000) - randomInt(30, 180) * 86400;

        // 随机选择一个生产商
        const producerIndex = randomInt(0, producers.length - 1);
        const producer = producers[producerIndex];
        const producerSigner = await provider.getSigner(accounts.indexOf(producer));
        const producerContract = new ethers.Contract(contractAddress, contractABI, producerSigner);

        // 注册产品
        updateProgress(`注册产品 ${p}: ${productName}...`);
        const registerTx = await producerContract.registerProduct(
          productName,
          batchNo,
          productionDate
        );
        await registerTx.wait();

        // 获取新产品ID
        const newProductId = Number(startProductCount) + p;
        productsCreated.push({
          id: newProductId,
          name: productName,
          batchNo
        });

        // 阶段1: 生产 -> 批发商
        const wholesalerIndex = randomInt(0, wholesalers.length - 1);
        const wholesaler = wholesalers[wholesalerIndex];

        updateProgress(`产品 ${newProductId}: 生产 -> 批发商...`);
        const transferTx1 = await producerContract.recordTransferWithVerifier(
          newProductId,
          wholesaler,
          randomChoice(LOCATIONS.production),
          randomChoice(LOCATIONS.logistics),
          '产品出厂，质量检验合格',
          randomChoice(VERIFIERS)
        );
        await transferTx1.wait();

        // 阶段2: 批发商 -> 零售商
        const retailerIndex = randomInt(0, retailers.length - 1);
        const retailer = retailers[retailerIndex];
        const wholesalerSigner = await provider.getSigner(accounts.indexOf(wholesaler));
        const wholesalerContract = new ethers.Contract(contractAddress, contractABI, wholesalerSigner);

        updateProgress(`产品 ${newProductId}: 批发商 -> 零售商...`);
        const transferTx2 = await wholesalerContract.recordTransferWithVerifier(
          newProductId,
          retailer,
          randomChoice(LOCATIONS.logistics),
          randomChoice(LOCATIONS.retail),
          '批发销售，运输完成',
          randomChoice(VERIFIERS)
        );
        await transferTx2.wait();
      }

      // 获取统计信息
      const totalProducts = await contract.productCount();
      const totalTransfers = await contract.transferCount();

      setSimulationResult({
        nodesAuthorized: materialSuppliers.length + producers.length + wholesalers.length + retailers.length,
        productsCreated: productsCreated,
        totalProducts: totalProducts.toString(),
        totalTransfers: totalTransfers.toString()
      });

      message.success('模拟完成！');

      if (onSimulationComplete) {
        await onSimulationComplete();
      }

    } catch (err) {
      console.error('模拟失败:', err);
      message.error(`模拟失败: ${err.reason || err.message}`);
    } finally {
      setSimulating(false);
      setProgressText('');
    }
  };

  return (
    <Card
      title={
        <Space>
          <PlayCircleOutlined />
          <span>自动模拟</span>
        </Space>
      }
    >
      {!isAdmin && (
        <Alert
          title="权限提示"
          description="只有管理员才能运行自动模拟功能"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Descriptions column={1}>
        <Descriptions.Item label="功能说明">
          自动授权供应链节点并生成茅台酒产品的完整溯源流程
        </Descriptions.Item>
        <Descriptions.Item label="模拟内容">
          <Space orientation="vertical">
            <Text>• 授权12个节点（2个原料供应商、3个生产商、2个批发商、5个零售商）</Text>
            <Text>• 随机生成3-5个茅台酒产品</Text>
            <Text>• 模拟每个产品从生产到零售的完整流程</Text>
          </Space>
        </Descriptions.Item>
      </Descriptions>

      <Divider />

      {simulating && (
        <Space orientation="vertical" style={{ width: '100%', marginBottom: 16 }}>
          <Progress percent={progress} status="active" />
          <Text type="secondary">
            <LoadingOutlined /> {progressText}
          </Text>
        </Space>
      )}

      <Button
        type="primary"
        size="large"
        block
        icon={<PlayCircleOutlined />}
        onClick={runSimulation}
        disabled={!isAdmin || simulating}
        loading={simulating}
      >
        {simulating ? '模拟进行中...' : '开始模拟'}
      </Button>

      {simulationResult && (
        <Card
          style={{ marginTop: 16, backgroundColor: '#f6ffed', borderColor: '#b7eb8f' }}
        >
          <Space orientation="vertical" style={{ width: '100%' }}>
            <Space>
              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
              <Title level={5} style={{ margin: 0 }}>模拟完成</Title>
            </Space>

            <Descriptions column={2} size="small">
              <Descriptions.Item label="授权节点数">
                <Tag color="blue">{simulationResult.nodesAuthorized}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="创建产品数">
                <Tag color="green">{simulationResult.totalProducts}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="运输记录数">
                <Tag color="orange">{simulationResult.totalTransfers}</Tag>
              </Descriptions.Item>
            </Descriptions>

            <Divider style={{ margin: '12px 0' }}>创建的产品</Divider>

            {simulationResult.productsCreated.map((product, index) => (
              <Space key={index}>
                <Tag color="purple">ID: {product.id}</Tag>
                <Text strong>{product.name}</Text>
                <Text type="secondary">({product.batchNo})</Text>
              </Space>
            ))}
          </Space>
        </Card>
      )}
    </Card>
  );
}