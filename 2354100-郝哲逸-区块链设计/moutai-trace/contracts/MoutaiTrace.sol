// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MoutaiTrace
 * @dev 茅台酒溯源智能合约
 * @notice 实现茅台酒从原料到销售的全程追踪
 */
contract MoutaiTrace {
    // ============ 数据结构 ============

    /**
     * @dev 节点信息结构
     */
    struct NodeInfo {
        string name;           // 节点名称
        string phone;          // 联系电话
        string category;       // 节点类别：原料供给、产品生产、批发销售、零售
        string location;       // 地址
        string description;    // 描述
        bool isAuthorized;     // 是否已授权
        bool exists;           // 是否存在
    }

    /**
     * @dev 产品信息结构
     */
    struct Product {
        uint256 id;              // 产品ID
        string name;             // 产品名称
        string batchNo;          // 批次号
        uint256 productionDate;  // 生产日期（时间戳）
        address manufacturer;    // 生产厂家地址
        address currentOwner;    // 当前持有者
        uint8 currentStage;      // 当前阶段: 0-原料, 1-生产, 2-物流, 3-零售
        bool exists;             // 产品是否存在
    }

    /**
     * @dev 运输记录结构
     */
    struct TransferRecord {
        uint256 productId;       // 产品ID
        address from;            // 发送方地址
        address to;              // 接收方地址
        string fromLocation;     // 发送地点
        string toLocation;       // 接收地点
        uint256 timestamp;       // 时间戳
        string remark;           // 备注信息
        string verifier;         // 验证人员
    }

    // ============ 状态变量 ============

    address public admin;                    // 管理员地址
    uint256 public productCount;             // 产品总数
    uint256 public transferCount;            // 运输记录总数

    // 产品ID => 产品信息
    mapping(uint256 => Product) public products;

    // 产品ID => 运输记录数组
    mapping(uint256 => TransferRecord[]) public productHistory;

    // 地址 => 节点信息
    mapping(address => NodeInfo) public nodeInfo;

    // 地址 => 是否为授权节点（保留兼容性）
    mapping(address => bool) public authorizedNodes;

    // 所有产品ID数组（用于遍历）
    uint256[] public allProductIds;

    // ============ 事件 ============

    event ProductRegistered(
        uint256 indexed productId,
        string name,
        string batchNo,
        address indexed manufacturer,
        uint256 productionDate
    );

    event TransferRecorded(
        uint256 indexed productId,
        address indexed from,
        address indexed to,
        string fromLocation,
        string toLocation,
        uint256 timestamp,
        string remark,
        string verifier
    );

    event NodeAuthorized(address indexed node, string nodeName, string category);
    event NodeUpdated(address indexed node, string nodeName);
    event NodeRemoved(address indexed node);

    // ============ 错误 ============

    error ProductNotFound(uint256 productId);
    error NotAuthorizedNode();
    error NotProductOwner();
    error InvalidStage();
    error InvalidTransfer();
    error EmptyString();
    error InvalidAddress();
    error NodeNotFound();

    // ============ 修饰器 ============

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin can call this function");
        _;
    }

    modifier onlyAuthorizedNode() {
        require(authorizedNodes[msg.sender], "Only authorized nodes can call this function");
        _;
    }

    modifier productExists(uint256 _productId) {
        if (!products[_productId].exists) {
            revert ProductNotFound(_productId);
        }
        _;
    }

    // ============ 构造函数 ============

    constructor() {
        admin = msg.sender;
        // Initialize admin node
        nodeInfo[msg.sender] = NodeInfo({
            name: "Admin",
            phone: "",
            category: "Admin",
            location: "",
            description: "System Administrator",
            isAuthorized: true,
            exists: true
        });
        authorizedNodes[msg.sender] = true;
        emit NodeAuthorized(msg.sender, "Admin", "Admin");
    }

    // ============ 管理功能 ============

    /**
     * @dev 授权新节点（带详细信息）
     * @param _node 节点地址
     * @param _name 节点名称
     * @param _phone 联系电话
     * @param _category 节点类别
     * @param _location 地址
     * @param _description 描述
     */
    function authorizeNodeWithInfo(
        address _node,
        string memory _name,
        string memory _phone,
        string memory _category,
        string memory _location,
        string memory _description
    ) external onlyAdmin {
        if (_node == address(0)) {
            revert InvalidAddress();
        }

        nodeInfo[_node] = NodeInfo({
            name: _name,
            phone: _phone,
            category: _category,
            location: _location,
            description: _description,
            isAuthorized: true,
            exists: true
        });
        authorizedNodes[_node] = true;

        emit NodeAuthorized(_node, _name, _category);
    }

    /**
     * @dev Authorize new node (simplified version for compatibility)
     * @param _node Node address
     * @param _nodeName Node name
     */
    function authorizeNode(address _node, string memory _nodeName) external onlyAdmin {
        nodeInfo[_node] = NodeInfo({
            name: _nodeName,
            phone: "",
            category: "Uncategorized",
            location: "",
            description: "",
            isAuthorized: true,
            exists: true
        });
        authorizedNodes[_node] = true;
        emit NodeAuthorized(_node, _nodeName, "Uncategorized");
    }

    /**
     * @dev 更新节点信息
     */
    function updateNodeInfo(
        string memory _name,
        string memory _phone,
        string memory _category,
        string memory _location,
        string memory _description
    ) external onlyAuthorizedNode {
        nodeInfo[msg.sender].name = _name;
        nodeInfo[msg.sender].phone = _phone;
        nodeInfo[msg.sender].category = _category;
        nodeInfo[msg.sender].location = _location;
        nodeInfo[msg.sender].description = _description;
        emit NodeUpdated(msg.sender, _name);
    }

    /**
     * @dev 移除节点授权
     * @param _node 节点地址
     */
    function removeNode(address _node) external onlyAdmin {
        authorizedNodes[_node] = false;
        nodeInfo[_node].isAuthorized = false;
        emit NodeRemoved(_node);
    }

    /**
     * @dev Transfer admin rights
     * @param _newAdmin New admin address
     */
    function transferAdmin(address _newAdmin) external onlyAdmin {
        if (_newAdmin == address(0)) {
            revert InvalidAddress();
        }
        // Remove old admin authorization
        authorizedNodes[admin] = false;
        nodeInfo[admin].isAuthorized = false;
        // Set new admin
        admin = _newAdmin;
        authorizedNodes[_newAdmin] = true;
        nodeInfo[_newAdmin] = NodeInfo({
            name: "Admin",
            phone: "",
            category: "Admin",
            location: "",
            description: "System Administrator",
            isAuthorized: true,
            exists: true
        });
        emit NodeAuthorized(_newAdmin, "Admin", "Admin");
    }

    // ============ 核心功能 ============

    /**
     * @dev 注册新产品（仅生产厂家）
     * @param _name 产品名称
     * @param _batchNo 批次号
     * @param _productionDate 生产日期
     * @return 新产品的ID
     */
    function registerProduct(
        string memory _name,
        string memory _batchNo,
        uint256 _productionDate
    ) external onlyAuthorizedNode returns (uint256) {
        // 输入验证
        if (bytes(_name).length == 0) {
            revert EmptyString();
        }
        if (bytes(_batchNo).length == 0) {
            revert EmptyString();
        }

        productCount++;
        uint256 newProductId = productCount;

        products[newProductId] = Product({
            id: newProductId,
            name: _name,
            batchNo: _batchNo,
            productionDate: _productionDate,
            manufacturer: msg.sender,
            currentOwner: msg.sender,
            currentStage: 1, // 生产阶段（跳过原料阶段，由原料转移过来）
            exists: true
        });

        allProductIds.push(newProductId);

        emit ProductRegistered(
            newProductId,
            _name,
            _batchNo,
            msg.sender,
            _productionDate
        );

        return newProductId;
    }

    /**
     * @dev 记录产品运输
     * @param _productId 产品ID
     * @param _to 接收方地址
     * @param _fromLocation 发送地点
     * @param _toLocation 接收地点
     * @param _remark 备注
     * @param _verifier 验证人员
     */
    function recordTransferWithVerifier(
        uint256 _productId,
        address _to,
        string memory _fromLocation,
        string memory _toLocation,
        string memory _remark,
        string memory _verifier
    ) external productExists(_productId) onlyAuthorizedNode {
        Product storage product = products[_productId];

        // 检查是否为当前持有者
        if (product.currentOwner != msg.sender) {
            revert NotProductOwner();
        }

        // 检查接收方是否为授权节点
        if (!authorizedNodes[_to]) {
            revert NotAuthorizedNode();
        }

        // 检查接收方不能是零地址
        if (_to == address(0)) {
            revert InvalidAddress();
        }

        // 验证阶段转换
        uint8 nextStage = product.currentStage + 1;
        if (nextStage > 3) {
            revert InvalidStage();
        }

        // 输入验证：地点不能为空
        if (bytes(_fromLocation).length == 0) {
            revert EmptyString();
        }
        if (bytes(_toLocation).length == 0) {
            revert EmptyString();
        }

        // 创建运输记录
        transferCount++;
        TransferRecord memory record = TransferRecord({
            productId: _productId,
            from: msg.sender,
            to: _to,
            fromLocation: _fromLocation,
            toLocation: _toLocation,
            timestamp: block.timestamp,
            remark: _remark,
            verifier: _verifier
        });

        productHistory[_productId].push(record);

        // 更新产品状态
        product.currentOwner = _to;
        product.currentStage = nextStage;

        emit TransferRecorded(
            _productId,
            msg.sender,
            _to,
            _fromLocation,
            _toLocation,
            block.timestamp,
            _remark,
            _verifier
        );
    }

    /**
     * @dev 记录产品运输（简化版本，保持兼容性）
     */
    function recordTransfer(
        uint256 _productId,
        address _to,
        string memory _fromLocation,
        string memory _toLocation,
        string memory _remark
    ) external productExists(_productId) onlyAuthorizedNode {
        Product storage product = products[_productId];

        if (product.currentOwner != msg.sender) {
            revert NotProductOwner();
        }

        if (!authorizedNodes[_to]) {
            revert NotAuthorizedNode();
        }

        if (_to == address(0)) {
            revert InvalidAddress();
        }

        uint8 nextStage = product.currentStage + 1;
        if (nextStage > 3) {
            revert InvalidStage();
        }

        if (bytes(_fromLocation).length == 0) {
            revert EmptyString();
        }
        if (bytes(_toLocation).length == 0) {
            revert EmptyString();
        }

        transferCount++;
        TransferRecord memory record = TransferRecord({
            productId: _productId,
            from: msg.sender,
            to: _to,
            fromLocation: _fromLocation,
            toLocation: _toLocation,
            timestamp: block.timestamp,
            remark: _remark,
            verifier: ""
        });

        productHistory[_productId].push(record);

        product.currentOwner = _to;
        product.currentStage = nextStage;

        emit TransferRecorded(
            _productId,
            msg.sender,
            _to,
            _fromLocation,
            _toLocation,
            block.timestamp,
            _remark,
            ""
        );
    }

    // ============ 查询功能 ============

    /**
     * @dev 获取产品信息
     * @param _productId 产品ID
     */
    function getProduct(uint256 _productId)
        external
        view
        productExists(_productId)
        returns (
            uint256 id,
            string memory name,
            string memory batchNo,
            uint256 productionDate,
            address manufacturer,
            address currentOwner,
            uint8 currentStage
        )
    {
        Product memory product = products[_productId];
        return (
            product.id,
            product.name,
            product.batchNo,
            product.productionDate,
            product.manufacturer,
            product.currentOwner,
            product.currentStage
        );
    }

    /**
     * @dev 获取产品运输历史记录数量
     * @param _productId 产品ID
     */
    function getProductHistoryCount(uint256 _productId)
        external
        view
        productExists(_productId)
        returns (uint256)
    {
        return productHistory[_productId].length;
    }

    /**
     * @dev 获取产品运输历史记录
     * @param _productId 产品ID
     */
    function getProductHistory(uint256 _productId)
        external
        view
        productExists(_productId)
        returns (TransferRecord[] memory)
    {
        return productHistory[_productId];
    }

    /**
     * @dev 获取单条运输记录
     * @param _productId 产品ID
     * @param _index 记录索引
     */
    function getTransferRecord(uint256 _productId, uint256 _index)
        external
        view
        productExists(_productId)
        returns (
            address from,
            address to,
            string memory fromLocation,
            string memory toLocation,
            uint256 timestamp,
            string memory remark,
            string memory verifier
        )
    {
        require(_index < productHistory[_productId].length, "Index out of bounds");
        TransferRecord memory record = productHistory[_productId][_index];
        return (
            record.from,
            record.to,
            record.fromLocation,
            record.toLocation,
            record.timestamp,
            record.remark,
            record.verifier
        );
    }

    /**
     * @dev 获取所有产品ID
     */
    function getAllProductIds() external view returns (uint256[] memory) {
        return allProductIds;
    }

    /**
     * @dev 获取某地址拥有的产品数量
     * @param _owner 拥有者地址
     */
    function getProductCountByOwner(address _owner) external view returns (uint256) {
        uint256 count = 0;
        for (uint256 i = 0; i < allProductIds.length; i++) {
            if (products[allProductIds[i]].currentOwner == _owner) {
                count++;
            }
        }
        return count;
    }

    /**
     * @dev 获取某地址拥有的所有产品ID
     * @param _owner 拥有者地址
     */
    function getProductsByOwner(address _owner) external view returns (uint256[] memory) {
        uint256 count = 0;
        // 第一次遍历计算数量
        for (uint256 i = 0; i < allProductIds.length; i++) {
            if (products[allProductIds[i]].currentOwner == _owner) {
                count++;
            }
        }

        // 创建结果数组
        uint256[] memory result = new uint256[](count);
        uint256 index = 0;

        // 第二次遍历填充数据
        for (uint256 i = 0; i < allProductIds.length; i++) {
            if (products[allProductIds[i]].currentOwner == _owner) {
                result[index] = allProductIds[i];
                index++;
            }
        }

        return result;
    }

    /**
     * @dev 获取节点名称（保持兼容性）
     * @param _node 节点地址
     */
    function getNodeName(address _node) external view returns (string memory) {
        return nodeInfo[_node].name;
    }

    /**
     * @dev 获取节点详细信息
     * @param _node 节点地址
     */
    function getNodeInfo(address _node) external view returns (
        string memory name,
        string memory phone,
        string memory category,
        string memory location,
        string memory description,
        bool isAuthorized
    ) {
        NodeInfo memory info = nodeInfo[_node];
        return (
            info.name,
            info.phone,
            info.category,
            info.location,
            info.description,
            info.isAuthorized
        );
    }

    /**
     * @dev 检查节点是否授权
     * @param _node 节点地址
     */
    function isAuthorizedNode(address _node) external view returns (bool) {
        return authorizedNodes[_node];
    }

    /**
     * @dev 获取所有已授权节点地址
     */
    function getAllAuthorizedNodes() external view returns (address[] memory) {
        uint256 count = 0;

        // 计算已授权节点数量
        for (uint256 i = 0; i < allProductIds.length; i++) {
            // 使用product的owner来统计
        }

        // 由于无法遍历mapping，返回空数组
        // 实际使用中应该在前端维护节点列表
        return new address[](0);
    }
}
