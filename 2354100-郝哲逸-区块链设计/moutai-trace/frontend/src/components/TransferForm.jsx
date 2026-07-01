import { useState, useEffect } from 'react';
import { Form, Input, Button, Card, message, Select, Space, Typography, Tag, Descriptions, Divider, Steps } from 'antd';
import { SwapOutlined, HistoryOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;
const { TextArea } = Input;

const STAGE_CONFIG = {
  0: { color: 'purple', text: '原料阶段' },
  1: { color: 'blue', text: '生产阶段' },
  2: { color: 'orange', text: '物流阶段' },
  3: { color: 'green', text: '零售阶段' }
};

// 验证员列表
const VERIFIERS = [
  '李晓婷', '张伟豪', '王雅娜', '刘军宇', '陈雪婷', '杨宇航', '赵晓梅',
  '周建华', '吴晓明', '郑秀芳', '孙志强', '钱伟杰'
];

export function TransferForm({ contract, account, accounts, authorizedNodes, nodeNames }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [transferHistory, setTransferHistory] = useState([]);

  // 加载当前账户拥有的产品
  useEffect(() => {
    if (contract && account) {
      loadProducts();
    }
  }, [contract, account]);

  const loadProducts = async () => {
    try {
      const productIds = await contract.getProductsByOwner(account);
      const productDetails = [];

      for (const id of productIds) {
        const product = await contract.getProduct(id);
        // 确保stage是数字类型（Ethers.js返回的可能是BigNumber）
        const stage = Number(product.currentStage);
        const stageText = ['原料', '生产', '物流', '零售'][stage] || '未知';
        productDetails.push({
          id: id.toString(),
          name: product.name,
          batchNo: product.batchNo,
          stage: stage,
          stageText
        });
      }

      setProducts(productDetails);
    } catch (err) {
      console.error('加载产品失败:', err);
    }
  };

  const loadProductHistory = async (productId) => {
    if (!contract || !productId) return;

    try {
      const history = await contract.getProductHistory(productId);
      const formattedHistory = history.map(record => ({
        from: record.from,
        to: record.to,
        fromLocation: record.fromLocation,
        toLocation: record.toLocation,
        timestamp: new Date(Number(record.timestamp) * 1000).toLocaleString(),
        remark: record.remark,
        verifier: record.verifier
      }));
      setTransferHistory(formattedHistory);
    } catch (err) {
      console.error('加载历史失败:', err);
      setTransferHistory([]);
    }
  };

  const handleProductSelect = async (productId) => {
    const product = products.find(p => p.id === productId);
    setSelectedProduct(product);
    await loadProductHistory(productId);
  };

  const handleSubmit = async (values) => {
    if (!contract) {
      message.error('请先连接合约');
      return;
    }

    setLoading(true);
    try {
      const tx = await contract.recordTransferWithVerifier(
        values.productId,
        values.toAddress,
        values.fromLocation,
        values.toLocation,
        values.remark || '',
        values.verifier || ''
      );

      message.loading('交易提交中...', 0);
      const receipt = await tx.wait();
      message.destroy();

      if (receipt.status === 1) {
        message.success('运输记录成功！');
        form.resetFields(['toAddress', 'fromLocation', 'toLocation', 'remark', 'verifier']);
        setSelectedProduct(null);
        setTransferHistory([]);
        await loadProducts();
      } else {
        message.error('交易执行失败');
      }
    } catch (err) {
      message.destroy();
      console.error('运输记录失败:', err);
      message.error(`运输记录失败: ${err.reason || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // 根据当前阶段确定可转移的目标
  const getAvailableTargets = () => {
    if (!selectedProduct) {
      return [];
    }

    // stage已经是数字类型（在loadProducts中转换）
    const stage = selectedProduct.stage;

    // 如果authorizedNodes还没加载，返回空数组
    if (!authorizedNodes || Object.keys(authorizedNodes).length === 0) {
      return [];
    }

    // 产品已到达零售阶段，不能再转移
    if (stage >= 3) {
      return [];
    }

    // 只显示已授权且不是当前账户的节点
    const authorizedAccounts = accounts.filter(acc => {
      const isAuth = authorizedNodes[acc];
      const isNotCurrent = acc !== account;
      return isNotCurrent && isAuth === true;
    });

    return authorizedAccounts.map(acc => ({
      value: acc,
      label: `${nodeNames && nodeNames[acc] ? nodeNames[acc] : '未命名节点'} (${acc.slice(0, 6)}...${acc.slice(-4)})`
    }));
  };

  return (
    <Card
      title={
        <Space>
          <SwapOutlined />
          <span>运输管理</span>
        </Space>
      }
      extra={<Text type="secondary">当前账户: {account?.slice(0, 6)}...{account?.slice(-4)}</Text>}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
      >
        <Form.Item
          label="选择产品"
          name="productId"
          rules={[{ required: true, message: '请选择产品' }]}
        >
          <Select
            placeholder="选择要运输的产品"
            size="large"
            onChange={handleProductSelect}
            options={products.map(p => ({
              value: p.id,
              label: `${p.name} (ID: ${p.id}) - ${p.stageText}阶段`
            }))}
          />
        </Form.Item>

        {selectedProduct && (
          <Card size="small" style={{ marginBottom: 16, backgroundColor: '#f5f5f5' }}>
            <Descriptions column={2} size="small">
              <Descriptions.Item label="产品名称">{selectedProduct.name}</Descriptions.Item>
              <Descriptions.Item label="批次号">{selectedProduct.batchNo}</Descriptions.Item>
              <Descriptions.Item label="当前阶段">
                <Tag color={STAGE_CONFIG[selectedProduct.stage]?.color || 'default'}>
                  {selectedProduct.stageText}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            <Divider style={{ margin: '12px 0' }} />

            <Steps
              size="small"
              current={selectedProduct.stage}
              items={[
                { title: '原料' },
                { title: '生产' },
                { title: '物流' },
                { title: '零售' }
              ]}
            />
          </Card>
        )}

        <Form.Item
          label="目标节点"
          name="toAddress"
          rules={[{ required: true, message: '请选择目标节点' }]}
        >
          <Select
            placeholder="选择目标节点"
            size="large"
            options={getAvailableTargets()}
            disabled={!selectedProduct || selectedProduct.stage >= 3}
          />
        </Form.Item>

        <Form.Item
          label="发货地点"
          name="fromLocation"
          rules={[{ required: true, message: '请输入发货地点' }]}
        >
          <Input placeholder="例如：贵州茅台镇" size="large" />
        </Form.Item>

        <Form.Item
          label="收货地点"
          name="toLocation"
          rules={[{ required: true, message: '请输入收货地点' }]}
        >
          <Input placeholder="例如：上海物流中心" size="large" />
        </Form.Item>

        <Form.Item
          label="验证员"
          name="verifier"
        >
          <Select
            placeholder="选择验证员（可选）"
            size="large"
            allowClear
            options={VERIFIERS.map(v => ({ value: v, label: v }))}
          />
        </Form.Item>

        <Form.Item
          label="备注"
          name="remark"
        >
          <TextArea placeholder="运输备注信息" rows={2} />
        </Form.Item>

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            loading={loading}
            size="large"
            block
            icon={<SwapOutlined />}
            disabled={!selectedProduct || selectedProduct.stage >= 3}
          >
            记录运输
          </Button>
        </Form.Item>
      </Form>

      {transferHistory.length > 0 && (
        <Divider>
          <Space>
            <HistoryOutlined />
            <span>运输历史</span>
          </Space>
        </Divider>
      )}

      {transferHistory.map((record, index) => (
        <Card key={index} size="small" style={{ marginBottom: 8 }}>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="时间">{record.timestamp}</Descriptions.Item>
            {record.verifier && (
              <Descriptions.Item label="验证员">{record.verifier}</Descriptions.Item>
            )}
            <Descriptions.Item label="从">{record.fromLocation} ({record.from.slice(0, 6)}...{record.from.slice(-4)})</Descriptions.Item>
            <Descriptions.Item label="到">{record.toLocation} ({record.to.slice(0, 6)}...{record.to.slice(-4)})</Descriptions.Item>
            <Descriptions.Item label="备注" span={2}>{record.remark || '无'}</Descriptions.Item>
          </Descriptions>
        </Card>
      ))}
    </Card>
  );
}
