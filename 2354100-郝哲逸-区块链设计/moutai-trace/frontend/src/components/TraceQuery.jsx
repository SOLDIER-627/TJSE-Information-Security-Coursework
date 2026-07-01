import { useState } from 'react';
import { Form, Input, Button, Card, message, Timeline, Descriptions, Tag, Space, Typography, Empty, Steps } from 'antd';
import { SearchOutlined, HistoryOutlined, CheckCircleOutlined, TruckOutlined, ShopOutlined, ToolOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const STAGE_CONFIG = {
  0: { color: 'purple', text: '原料阶段', icon: <ToolOutlined /> },
  1: { color: 'blue', text: '生产阶段', icon: <CheckCircleOutlined /> },
  2: { color: 'orange', text: '物流阶段', icon: <TruckOutlined /> },
  3: { color: 'green', text: '零售阶段', icon: <ShopOutlined /> }
};

export function TraceQuery({ contract, nodeNames }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [productInfo, setProductInfo] = useState(null);
  const [transferHistory, setTransferHistory] = useState([]);

  const handleSearch = async (values) => {
    if (!contract) {
      message.error('请先连接合约');
      return;
    }

    setLoading(true);
    try {
      // 查询产品信息
      const product = await contract.getProduct(values.productId);
      setProductInfo({
        id: product.id.toString(),
        name: product.name,
        batchNo: product.batchNo,
        productionDate: new Date(Number(product.productionDate) * 1000).toLocaleDateString(),
        manufacturer: product.manufacturer,
        currentOwner: product.currentOwner,
        currentStage: Number(product.currentStage)
      });

      // 查询运输历史
      const history = await contract.getProductHistory(values.productId);
      const formattedHistory = await Promise.all(history.map(async (record) => {
        // 获取节点名称
        let fromName = nodeNames && nodeNames[record.from] ? nodeNames[record.from] : record.from.slice(0, 6) + '...' + record.from.slice(-4);
        let toName = nodeNames && nodeNames[record.to] ? nodeNames[record.to] : record.to.slice(0, 6) + '...' + record.to.slice(-4);

        return {
          from: record.from,
          to: record.to,
          fromName,
          toName,
          fromLocation: record.fromLocation,
          toLocation: record.toLocation,
          timestamp: new Date(Number(record.timestamp) * 1000).toLocaleString(),
          remark: record.remark,
          verifier: record.verifier
        };
      }));
      setTransferHistory(formattedHistory);

      message.success('查询成功！');
    } catch (err) {
      console.error('查询失败:', err);
      message.error(`查询失败: ${err.reason || err.message}`);
      setProductInfo(null);
      setTransferHistory([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title={
        <Space>
          <SearchOutlined />
          <span>溯源查询</span>
        </Space>
      }
    >
      <Form
        form={form}
        layout="inline"
        onFinish={handleSearch}
      >
        <Form.Item
          name="productId"
          rules={[{ required: true, message: '请输入产品ID' }]}
        >
          <Input placeholder="输入产品ID" size="large" style={{ width: 200 }} />
        </Form.Item>

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            loading={loading}
            size="large"
            icon={<SearchOutlined />}
          >
            查询
          </Button>
        </Form.Item>
      </Form>

      {productInfo && (
        <Card
          title="产品信息"
          style={{ marginTop: 24 }}
          extra={
            <Tag color={STAGE_CONFIG[productInfo.currentStage]?.color || 'default'} icon={STAGE_CONFIG[productInfo.currentStage]?.icon}>
              {STAGE_CONFIG[productInfo.currentStage]?.text || '未知'}
            </Tag>
          }
        >
          <Descriptions column={2} bordered>
            <Descriptions.Item label="产品ID">{productInfo.id}</Descriptions.Item>
            <Descriptions.Item label="产品名称">{productInfo.name}</Descriptions.Item>
            <Descriptions.Item label="批次号">{productInfo.batchNo}</Descriptions.Item>
            <Descriptions.Item label="生产日期">{productInfo.productionDate}</Descriptions.Item>
            <Descriptions.Item label="生产厂家">
              {productInfo.manufacturer.slice(0, 6)}...{productInfo.manufacturer.slice(-4)}
            </Descriptions.Item>
            <Descriptions.Item label="当前持有者">
              {productInfo.currentOwner.slice(0, 6)}...{productInfo.currentOwner.slice(-4)}
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {productInfo && (
        <Card
          title="产品生命周期"
          style={{ marginTop: 16 }}
        >
          <Steps
            current={productInfo.currentStage}
            items={[
              { title: '原料', icon: <ToolOutlined /> },
              { title: '生产', icon: <CheckCircleOutlined /> },
              { title: '物流', icon: <TruckOutlined /> },
              { title: '零售', icon: <ShopOutlined /> }
            ]}
          />
        </Card>
      )}

      {productInfo && transferHistory.length > 0 && (
        <Card
          title={
            <Space>
              <HistoryOutlined />
              <span>运输轨迹</span>
            </Space>
          }
          style={{ marginTop: 16 }}
        >
          <Timeline
            items={transferHistory.map((record, index) => ({
              color: index === transferHistory.length - 1 ? 'green' : 'blue',
              content: (
                <Card size="small">
                  <Descriptions column={2} size="small">
                    <Descriptions.Item label="时间" span={2}>{record.timestamp}</Descriptions.Item>
                    <Descriptions.Item label="发货地点">{record.fromLocation}</Descriptions.Item>
                    <Descriptions.Item label="收货地点">{record.toLocation}</Descriptions.Item>
                    <Descriptions.Item label="发送方">
                      {record.fromName}
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        ({record.from.slice(0, 6)}...{record.from.slice(-4)})
                      </Text>
                    </Descriptions.Item>
                    <Descriptions.Item label="接收方">
                      {record.toName}
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        ({record.to.slice(0, 6)}...{record.to.slice(-4)})
                      </Text>
                    </Descriptions.Item>
                    {record.verifier && (
                      <Descriptions.Item label="验证员">{record.verifier}</Descriptions.Item>
                    )}
                    <Descriptions.Item label="备注">{record.remark || '无'}</Descriptions.Item>
                  </Descriptions>
                </Card>
              )
            }))}
          />
        </Card>
      )}

      {productInfo && transferHistory.length === 0 && (
        <Card style={{ marginTop: 16 }}>
          <Empty description="该产品尚未有运输记录" />
        </Card>
      )}
    </Card>
  );
}
