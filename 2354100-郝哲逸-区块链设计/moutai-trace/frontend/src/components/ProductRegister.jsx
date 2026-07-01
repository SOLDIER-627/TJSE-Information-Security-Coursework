import { useState } from 'react';
import { Form, Input, Button, Card, message, DatePicker, Space, Typography } from 'antd';
import { PlusOutlined, CheckCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

export function ProductRegister({ contract, account, onRegisterSuccess }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [registeredProduct, setRegisteredProduct] = useState(null);

  const handleSubmit = async (values) => {
    if (!contract) {
      message.error('请先连接合约');
      return;
    }

    setLoading(true);
    try {
      // 转换日期为时间戳
      const productionDate = Math.floor(new Date(values.productionDate).getTime() / 1000);

      const tx = await contract.registerProduct(
        values.name,
        values.batchNo,
        productionDate
      );

      message.loading('交易提交中...', 0);
      const receipt = await tx.wait();
      message.destroy();

      if (receipt.status === 1) {
        message.success('产品注册成功！');

        // 获取产品ID（从事件中解析）
        const event = receipt.logs.find(log => {
          try {
            const parsed = contract.interface.parseLog(log);
            return parsed.name === 'ProductRegistered';
          } catch {
            return false;
          }
        });

        let productId = null;
        if (event) {
          const parsed = contract.interface.parseLog(event);
          productId = parsed.args[0].toString();
        }

        setRegisteredProduct({
          id: productId,
          name: values.name,
          batchNo: values.batchNo,
          productionDate: values.productionDate.format('YYYY-MM-DD')
        });

        form.resetFields();

        if (onRegisterSuccess) {
          onRegisterSuccess(productId);
        }
      } else {
        message.error('交易执行失败');
      }
    } catch (err) {
      message.destroy();
      console.error('注册失败:', err);
      message.error(`注册失败: ${err.reason || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title={
        <Space>
          <PlusOutlined />
          <span>产品注册</span>
        </Space>
      }
      extra={<Text type="secondary">当前账户: {account?.slice(0, 6)}...{account?.slice(-4)}</Text>}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          productionDate: dayjs()
        }}
      >
        <Form.Item
          label="产品名称"
          name="name"
          rules={[{ required: true, message: '请输入产品名称' }]}
        >
          <Input placeholder="例如：飞天茅台" size="large" />
        </Form.Item>

        <Form.Item
          label="批次号"
          name="batchNo"
          rules={[{ required: true, message: '请输入批次号' }]}
        >
          <Input placeholder="例如：BATCH-2024-001" size="large" />
        </Form.Item>

        <Form.Item
          label="生产日期"
          name="productionDate"
          rules={[{ required: true, message: '请选择生产日期' }]}
        >
          <DatePicker style={{ width: '100%' }} size="large" />
        </Form.Item>

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            loading={loading}
            size="large"
            block
            icon={<PlusOutlined />}
          >
            注册产品
          </Button>
        </Form.Item>
      </Form>

      {registeredProduct && (
        <Card
          style={{ marginTop: 16, backgroundColor: '#f6ffed', borderColor: '#b7eb8f' }}
        >
          <Space orientation="vertical" style={{ width: '100%' }}>
            <Space>
              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
              <Title level={5} style={{ margin: 0 }}>注册成功</Title>
            </Space>
            <Text>产品ID: <Text strong>{registeredProduct.id}</Text></Text>
            <Text>产品名称: <Text strong>{registeredProduct.name}</Text></Text>
            <Text>批次号: <Text strong>{registeredProduct.batchNo}</Text></Text>
            <Text>生产日期: <Text strong>{registeredProduct.productionDate}</Text></Text>
          </Space>
        </Card>
      )}
    </Card>
  );
}
