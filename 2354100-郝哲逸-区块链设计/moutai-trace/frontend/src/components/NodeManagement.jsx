import { useState, useEffect } from 'react';
import { Card, Table, Button, Space, Tag, Typography, message, Modal, Form, Input, Select, Alert, Descriptions, Image } from 'antd';
import { TeamOutlined, UserAddOutlined, DeleteOutlined, InfoCircleOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const CATEGORY_COLORS = {
  '原料供给': 'cyan',
  '产品生产': 'blue',
  '批发销售': 'orange',
  '零售': 'green',
  '管理': 'purple',
  '未分类': 'default'
};

export function NodeManagement({ contract, account, accounts, onNodeChange, isAdmin }) {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [form] = Form.useForm();

  useEffect(() => {
    if (contract) {
      loadNodes();
    }
  }, [contract]);

  const loadNodes = async () => {
    setLoading(true);
    try {
      const nodeData = [];
      for (const acc of accounts) {
        const nodeInfo = await contract.getNodeInfo(acc);
        const isAuthorized = nodeInfo.isAuthorized;
        nodeData.push({
          address: acc,
          name: nodeInfo.name || '未授权',
          phone: nodeInfo.phone || '-',
          category: nodeInfo.category || '未分类',
          location: nodeInfo.location || '-',
          description: nodeInfo.description || '-',
          isAuthorized: Boolean(isAuthorized)
        });
      }
      setNodes(nodeData);
    } catch (err) {
      console.error('加载节点失败:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAuthorize = async (values) => {
    try {
      const tx = await contract.authorizeNodeWithInfo(
        values.address,
        values.name,
        values.phone || '',
        values.category,
        values.location || '',
        values.description || ''
      );
      message.loading('授权中...', 0);
      const receipt = await tx.wait();
      message.destroy();

      if (receipt.status === 1) {
        message.success('授权成功！');
        await loadNodes();
        if (onNodeChange) {
          await onNodeChange();
        }
        setModalVisible(false);
        form.resetFields();
      }
    } catch (err) {
      message.destroy();
      message.error(`授权失败: ${err.reason || err.message}`);
    }
  };

  const handleRemove = async (address) => {
    try {
      const tx = await contract.removeNode(address);
      message.loading('移除中...', 0);
      const receipt = await tx.wait();
      message.destroy();

      if (receipt.status === 1) {
        message.success('移除成功！');
        await loadNodes();
        if (onNodeChange) {
          await onNodeChange();
        }
      }
    } catch (err) {
      message.destroy();
      message.error(`移除失败: ${err.reason || err.message}`);
    }
  };

  const showNodeDetail = (record) => {
    setSelectedNode(record);
    setDetailModalVisible(true);
  };

  const columns = [
    {
      title: '节点地址',
      dataIndex: 'address',
      key: 'address',
      render: (addr) => `${addr.slice(0, 10)}...${addr.slice(-8)}`
    },
    {
      title: '节点名称',
      dataIndex: 'name',
      key: 'name'
    },
    {
      title: '类别',
      dataIndex: 'category',
      key: 'category',
      render: (category) => (
        <Tag color={CATEGORY_COLORS[category] || 'default'}>
          {category}
        </Tag>
      )
    },
    {
      title: '状态',
      dataIndex: 'isAuthorized',
      key: 'isAuthorized',
      render: (authorized) => (
        <Tag color={authorized ? 'green' : 'default'}>
          {authorized ? '已授权' : '未授权'}
        </Tag>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<InfoCircleOutlined />}
            onClick={() => showNodeDetail(record)}
          >
            详情
          </Button>
          {isAdmin && record.isAuthorized && record.address !== account && (
            <Button
              danger
              size="small"
              icon={<DeleteOutlined />}
              onClick={() => handleRemove(record.address)}
            >
              移除
            </Button>
          )}
        </Space>
      )
    }
  ];

  return (
    <Card
      title={
        <Space>
          <TeamOutlined />
          <span>节点管理</span>
        </Space>
      }
      extra={
        isAdmin && (
          <Button
            type="primary"
            icon={<UserAddOutlined />}
            onClick={() => setModalVisible(true)}
          >
            授权新节点
          </Button>
        )
      }
    >
      {!isAdmin && (
        <Alert
          title="权限提示"
          description="只有管理员才能授权和移除节点"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Table
        dataSource={nodes}
        columns={columns}
        rowKey="address"
        loading={loading}
        pagination={false}
      />

      {/* 授权新节点弹窗 */}
      <Modal
        title="授权新节点"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleAuthorize}
          initialValues={{ category: '产品生产' }}
        >
          <Form.Item
            label="节点地址"
            name="address"
            rules={[{ required: true, message: '请选择或输入节点地址' }]}
          >
            <Select
              placeholder="选择账户（不包括当前管理员账户）"
              options={accounts
                .filter(acc => acc !== account)
                .map(acc => ({
                  value: acc,
                  label: `${acc.slice(0, 10)}...${acc.slice(-8)}`
                }))}
            />
          </Form.Item>

          <Form.Item
            label="节点名称"
            name="name"
            rules={[{ required: true, message: '请输入节点名称' }]}
          >
            <Input placeholder="例如：茅台酒厂A、物流中心B" />
          </Form.Item>

          <Form.Item
            label="联系电话"
            name="phone"
          >
            <Input placeholder="例如：13800138000" />
          </Form.Item>

          <Form.Item
            label="节点类别"
            name="category"
            rules={[{ required: true, message: '请选择节点类别' }]}
          >
            <Select
              options={[
                { value: '原料供给', label: '原料供给' },
                { value: '产品生产', label: '产品生产' },
                { value: '批发销售', label: '批发销售' },
                { value: '零售', label: '零售' }
              ]}
            />
          </Form.Item>

          <Form.Item
            label="地址"
            name="location"
          >
            <Input placeholder="例如：贵州省仁怀市茅台镇" />
          </Form.Item>

          <Form.Item
            label="描述"
            name="description"
          >
            <Input.TextArea placeholder="节点描述信息" rows={2} />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              授权
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 节点详情弹窗 */}
      <Modal
        title="节点详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
      >
        {selectedNode && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="节点名称">{selectedNode.name}</Descriptions.Item>
            <Descriptions.Item label="节点地址">
              <Text copyable={{ text: selectedNode.address, tooltips: ['Copy address', 'Copied!'] }}>
                {selectedNode.address}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="联系电话">{selectedNode.phone || '-'}</Descriptions.Item>
            <Descriptions.Item label="节点类别">
              <Tag color={CATEGORY_COLORS[selectedNode.category] || 'default'}>
                {selectedNode.category}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="地址">{selectedNode.location || '-'}</Descriptions.Item>
            <Descriptions.Item label="描述">{selectedNode.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="授权状态">
              <Tag color={selectedNode.isAuthorized ? 'green' : 'default'}>
                {selectedNode.isAuthorized ? '已授权' : '未授权'}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </Card>
  );
}
