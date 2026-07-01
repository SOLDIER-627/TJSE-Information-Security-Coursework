import { useState, useEffect, useCallback } from 'react';
import { ethers } from 'ethers';
import contractABI from '../contracts/MoutaiTrace.json';

// 合约地址（部署后需要更新）
const CONTRACT_ADDRESS = import.meta.env.VITE_CONTRACT_ADDRESS || '';

export function useContract() {
  const [provider, setProvider] = useState(null);
  const [signer, setSigner] = useState(null);
  const [contract, setContract] = useState(null);
  const [account, setAccount] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);

  // 初始化连接
  const initConnection = useCallback(async () => {
    try {
      // 连接到本地Ganache或Hardhat节点
      const rpcUrl = import.meta.env.VITE_RPC_URL || 'http://127.0.0.1:8545';
      const newProvider = new ethers.JsonRpcProvider(rpcUrl);
      setProvider(newProvider);

      // 获取所有账户
      const allAccounts = await newProvider.listAccounts();
      setAccounts(allAccounts.map(acc => acc.address || acc));

      // 设置默认签名者（第一个账户）
      if (allAccounts.length > 0) {
        const defaultSigner = await newProvider.getSigner(0);
        setSigner(defaultSigner);
        const address = await defaultSigner.getAddress();
        setAccount(address);

        // 创建合约实例
        if (CONTRACT_ADDRESS) {
          const newContract = new ethers.Contract(
            CONTRACT_ADDRESS,
            contractABI.abi,
            defaultSigner
          );
          setContract(newContract);
        }

        setIsConnected(true);
      }
    } catch (err) {
      console.error('连接失败:', err);
      setError(err.message);
    }
  }, []);

  // 切换账户（通过索引）
  const switchAccount = useCallback(async (index) => {
    if (provider && index >= 0 && index < accounts.length) {
      try {
        const newSigner = await provider.getSigner(index);
        setSigner(newSigner);
        const address = await newSigner.getAddress();
        setAccount(address);

        // 更新合约实例
        const contractAddress = CONTRACT_ADDRESS || localStorage.getItem('contractAddress');
        if (contractAddress) {
          const newContract = new ethers.Contract(
            contractAddress,
            contractABI.abi,
            newSigner
          );
          setContract(newContract);
        }
      } catch (err) {
        console.error('切换账户失败:', err);
        setError(err.message);
      }
    }
  }, [provider, accounts]);

  // 设置合约地址
  const setContractAddress = useCallback((address) => {
    if (signer && address) {
      try {
        const newContract = new ethers.Contract(
          address,
          contractABI.abi,
          signer
        );
        setContract(newContract);
        // 保存到localStorage以便切换账户时使用
        localStorage.setItem('contractAddress', address);
      } catch (err) {
        console.error('设置合约地址失败:', err);
        setError(err.message);
      }
    }
  }, [signer]);

  useEffect(() => {
    initConnection();
  }, [initConnection]);

  return {
    provider,
    signer,
    contract,
    account,
    accounts,
    isConnected,
    error,
    switchAccount,
    setContractAddress,
    initConnection
  };
}
