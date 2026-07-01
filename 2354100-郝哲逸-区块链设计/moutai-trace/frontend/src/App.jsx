import { useState, useEffect } from 'react';
import { Layout, Menu, Card, Select, Button, Space, Typography, message, Input, Modal, Form, Divider, Alert } from 'antd';
import {
  PlusOutlined,
  SwapOutlined,
  SearchOutlined,
  TeamOutlined,
  SettingOutlined,
  WalletOutlined,
  PlayCircleOutlined
} from '@ant-design/icons';
import { useContract } from './hooks/useContract';
import { ProductRegister } from './components/ProductRegister';
import { TransferForm } from './components/TransferForm';
import { TraceQuery } from './components/TraceQuery';
import { NodeManagement } from './components/NodeManagement';
import { SimulationPanel } from './components/SimulationPanel';

const { Header, Content, Sider } = Layout;
const { Title, Text } = Typography;

function App() {
  const {
    provider,
    contract,
    account,
    accounts,
    isConnected,
    error,
    switchAccount,
    setContractAddress
  } = useContract();

  const [activeMenu, setActiveMenu] = useState('simulation');
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [contractAddressInput, setContractAddressInput] = useState('');
  const [nodeNames, setNodeNames] = useState({});
  const [authorizedNodes, setAuthorizedNodes] = useState({});
  const [isAdminAccount, setIsAdminAccount] = useState(false);

  // 加载节点名称和授权状态
  useEffect(() => {
    if (contract && accounts.length > 0) {
      loadNodeInfo();
    }
  }, [contract, accounts]);

  // 检查当前账户是否是管理员
  useEffect(() => {
    if (contract && account) {
      checkAdmin();
    }
  }, [contract, account]);

  const checkAdmin = async () => {
    try {
      const adminAddress = await contract.admin();
      setIsAdminAccount(adminAddress.toLowerCase() === account.toLowerCase());
    } catch (err) {
      setIsAdminAccount(false);
    }
  };

  const loadNodeInfo = async () => {
    try {
      const names = {};
      const authorized = {};
      for (const acc of accounts) {
        // 使用getNodeInfo获取完整信息
        const nodeInfo = await contract.getNodeInfo(acc);
        if (nodeInfo.name) {
          names[acc] = nodeInfo.name;
        }
        // 确保转换为布尔值（Ethers.js可能返回其他类型）
        authorized[acc] = Boolean(nodeInfo.isAuthorized);
      }
      setNodeNames(names);
      setAuthorizedNodes(authorized);
    } catch (err) {
      console.error('加载节点信息失败:', err);
    }
  };

  const handleContractConnect = () => {
    if (contractAddressInput) {
      setContractAddress(contractAddressInput);
      message.success('合约地址已设置');
      setSettingsVisible(false);
    }
  };

  const menuItems = [
    {
      key: 'simulation',
      icon: <PlayCircleOutlined />,
      label: '自动模拟'
    },
    {
      key: 'register',
      icon: <PlusOutlined />,
      label: '产品注册'
    },
    {
      key: 'transfer',
      icon: <SwapOutlined />,
      label: '运输管理'
    },
    {
      key: 'query',
      icon: <SearchOutlined />,
      label: '溯源查询'
    },
    {
      key: 'nodes',
      icon: <TeamOutlined />,
      label: '节点管理'
    }
  ];

  const renderContent = () => {
    switch (activeMenu) {
      case 'simulation':
        return (
          <SimulationPanel
            contract={contract}
            provider={provider}
            account={account}
            accounts={accounts}
            isAdmin={isAdminAccount}
            onSimulationComplete={loadNodeInfo}
          />
        );
      case 'register':
        return <ProductRegister contract={contract} account={account} />;
      case 'transfer':
        return <TransferForm contract={contract} account={account} accounts={accounts} authorizedNodes={authorizedNodes} nodeNames={nodeNames} />;
      case 'query':
        return <TraceQuery contract={contract} nodeNames={nodeNames} />;
      case 'nodes':
        return <NodeManagement contract={contract} account={account} accounts={accounts} onNodeChange={loadNodeInfo} isAdmin={isAdminAccount} />;
      default:
        return null;
    }
  };

  const getNodeName = (address) => {
    return nodeNames[address] || '未命名节点';
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        background: '#fff',
        padding: '0 24px',
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <Space>
          <Text style={{ fontSize: 20, fontWeight: 'bold' }}>🍶</Text>
          <Title level={4} style={{ margin: 0 }}>茅台酒溯源区块链系统</Title>
        </Space>

        <Space size="large">
          {isConnected && (
            <>
              <Space>
                <WalletOutlined />
                <Text>当前账户:</Text>
                <Select
                  value={account}
                  onChange={(value) => {
                    const index = accounts.indexOf(value);
                    if (index !== -1) {
                      switchAccount(index);
                    }
                  }}
                  style={{ width: 280 }}
                  options={accounts.map((acc, idx) => ({
                    value: acc,
                    label: (
                      <Space>
                        <Text>{getNodeName(acc)}</Text>
                        <Text type="secondary">({acc.slice(0, 6)}...{acc.slice(-4)})</Text>
                      </Space>
                    )
                  }))}
                />
              </Space>
            </>
          )}

          <Button
            icon={<SettingOutlined />}
            onClick={() => setSettingsVisible(true)}
          >
            设置
          </Button>
        </Space>
      </Header>

      <Layout>
        <Sider
          width={200}
          style={{ background: '#fff' }}
        >
          <Menu
            mode="inline"
            selectedKeys={[activeMenu]}
            items={menuItems}
            onClick={({ key }) => setActiveMenu(key)}
            style={{ height: '100%', borderRight: 0 }}
          />
        </Sider>

        <Content style={{ padding: 24, background: '#f5f5f5' }}>
          {!isConnected && (
            <Alert
              title="未连接到区块链"
              description={error || '请确保Ganache或Hardhat节点正在运行，并在设置中配置正确的RPC URL'}
              type="error"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          {isConnected && !contract && (
            <Alert
              title="未连接合约"
              description="请在设置中输入已部署的合约地址"
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          {renderContent()}
        </Content>
      </Layout>

      <Modal
        title={
          <Space>
            <SettingOutlined />
            <span>系统设置</span>
          </Space>
        }
        open={settingsVisible}
        onCancel={() => setSettingsVisible(false)}
        footer={null}
      >
        <Form layout="vertical">
          <Form.Item label="合约地址">
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="输入合约地址"
                value={contractAddressInput}
                onChange={(e) => setContractAddressInput(e.target.value)}
              />
              <Button type="primary" onClick={handleContractConnect}>
                连接
              </Button>
            </Space.Compact>
          </Form.Item>

          <Divider />

          <Form.Item label="连接状态">
            <Space orientation="vertical">
              <Text>
                {isConnected ? (
                  <Text type="success">✓ 已连接到区块链节点</Text>
                ) : (
                  <Text type="danger">✗ 未连接</Text>
                )}
              </Text>
              <Text>
                {contract ? (
                  <Text type="success">✓ 已连接合约</Text>
                ) : (
                  <Text type="warning">○ 未连接合约</Text>
                )}
              </Text>
              <Text>
                {isAdminAccount ? (
                  <Text type="success">✓ 当前账户是管理员</Text>
                ) : (
                  <Text type="secondary">○ 当前账户不是管理员</Text>
                )}
              </Text>
            </Space>
          </Form.Item>

          <Divider />

          <Form.Item label="可用账户">
            <div style={{ maxHeight: 200, overflow: 'auto' }}>
              {accounts.map((acc, idx) => (
                <Card key={acc} size="small" style={{ marginBottom: 8 }}>
                  <Space>
                    <Text strong>账户 {idx}:</Text>
                    <Text code>{acc.slice(0, 10)}...{acc.slice(-8)}</Text>
                  </Space>
                </Card>
              ))}
            </div>
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}

export default App;