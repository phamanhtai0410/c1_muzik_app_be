### There are contracts: FactoryERC721, FactoryERC1155, Exchange, Promotion

&nbsp;

## FactoryERC721

&nbsp;

Ownership system is used with this functionality

&nbsp;

###Variables and events:

&nbsp;

address public **signer**; - all instances created from this factory pull it up as a signer for deploy, if it changes, then it changes accordingly everywhere and immediately

mapping(uint256 => bool) public **orderIDUsed**; - protection system for preventing transaction resending 

event **NewInstance**(uint256 orderID, string name, string symbol, address sender, address instance); - event for backend about collection deploy

&nbsp;

###Functions

&nbsp;

**setSigner**(address _signer) external onlyOwner - changes signer address

**deployERC721Instance**(uint256 orderID, string memory _name, string memory _symbol, uint256 deadline, bytes calldata signature) external nonReentrant - creates a new collection instance

where **signature** = signed ECDSA.toEthSignedMessageHash(keccak256(abi.encodePacked(block.chainid, orderID, _msgSender(), address(this), _name, _symbol, deadline)))

&nbsp;

##ERC721Instance

&nbsp;

Signer role is retrieved from factory, all access control logic is on the backend side

&nbsp;

###Variables and events

&nbsp;


IFactory public **factory**; - connection with factory

mapping(uint256 => bool) **mintIDUsed**; - protection system for preventing transaction resending 


uint256 public **totalIDs**; - used instead of  totalSupply() because contract is ERC721Burnable

event **Mint**(uint256 mintID, uint256 totalSupply, address sender); - event for backend about token minting

&nbsp;
 
###Functions

&nbsp;

**mint**(uint256 mintID, string calldata _tokenURI, uint256 deadline, bytes calldata signature) external nonReentrant - mints nft to the transaction sender

where **signature** = signed ECDSA.toEthSignedMessageHash(keccak256(abi.encodePacked(block.chainid, mintID, _msgSender(), address(this), _tokenURI, deadline)))

&nbsp;

##FactoryERC1155

&nbsp;

Ownership system is used with this functionality

&nbsp;

###Variables and events:

&nbsp;

&nbsp;

event **NewInstance**(uint256 orderID, string name, string symbol, address sender, address instance); - event for backend about collection deploy
 
&nbsp;

###Functions

&nbsp;

**setSigner**(address _signer) external onlyOwner - changes signer address

**deployERC1155Instance**(uint256 orderID, string memory _name, string memory _symbol, uint256 deadline, bytes calldata signature)

where **signature** = signed ECDSA.toEthSignedMessageHash(keccak256(abi.encodePacked(block.chainid, orderID, _msgSender(), address(this), _name, _symbol, deadline)))

&nbsp;

##ERC1155Instance

&nbsp;

Signer role is retrieved from factory, all access control logic is on the backend side

&nbsp;

###Variables and events

&nbsp;


IFactory public **factory**; - connection with factory

string public **name**; - collection name

string public **symbol**; - collection symbol

mapping(uint256 => bool) **mintIDUsed**; - protection system for preventing transaction resending 


uint256 public **totalIDs**; - used instead of  totalSupply() because contract is ERC721Burnable

event **Mint**(uint256 mintID, uint256 tokenID, uint256 amount, address sender); - event for backend about token minting

&nbsp;
 
###Functions

&nbsp;

**mint**(uint256 mintID, uint256 amount, string calldata _tokenURI, uint256 deadline, bytes calldata signature) external nonReentrant - mints nft to the transaction sender

where **signature** = signed ECDSA.toEthSignedMessageHash(keccak256(abi.encodePacked(block.chainid, mintID, _msgSender(), address(this), amount, _tokenURI, deadline)))

&nbsp;

##Exchange

&nbsp;

Role-based permission system is used with this functionality

&nbsp;

###Variables and events:

&nbsp;

bytes32 public constant **SIGNER_ROLE** = keccak256("SIGNER_ROLE");

mapping(uint256 => bool) public **orderIDUsed**;  - protection system for preventing transaction resending 

event **Trade**(uint256 orderID, address[2] fromTo, address[2] nftAndToken, uint256[2] idAndAmount, address[] additionalTokenReceivers, uint256[] allAmounts);

&nbsp;

###Functions

&nbsp;

**trade**(uint256 orderID, address[2] calldata fromTo, address[2] calldata nftAndToken, uint256[2] calldata idAndAmount, address[] calldata additionalTokenReceivers, uint256[] calldata allAmounts, uint256 deadline, bytes calldata signature) external payable nonReentrant - executes the trade, orderID from the backend, fromTo[0] - the one who sells nft, gets allAmounts[0], nftAndToken - nft address and token address 20, idAndAmount - if amount is 0, then the collection is 721, additionalTokenReceivers get allAmounts[ ] from 1 ( NOT 0) to the end,

where **signature** = signed ECDSA.toEthSignedMessageHash(keccak256(abi.encodePacked(block.chainid, orderID, fromTo, nftAndToken, idAndAmount, additionalTokenReceivers, allAmounts, deadline)))

**forceTradeBatch**(address[2][] calldata fromTo, address[2][] calldata nftAndToken, uint256[2][] calldata idAndAmount, address[][] calldata additionalTokenReceivers, uint256[][] calldata allAmounts) external onlyRole(SIGNER_ROLE) - allows backend to execute an array of trades at the expense of the caller (backend), without signatures

&nbsp;

##Promotion

&nbsp;

Ownership system is used with this functionality

&nbsp;

###Variables and events:

&nbsp;

address public **signer**;

address public **feeReceive**r; - zero address can not be set

event **PromotionSuccess**(uint256 package, uint256 promotionChainId, address promotionToken, uint256 promotionId, address sender);

&nbsp;

###Functions

&nbsp;

**promote**(uint256 package, address token, uint256 amount, uint256promotionChainId, address promotionToken, uint256 promotionId, uint256 deadline, bytes calldata signature) external payable nonReentrant - Transfers the amount of the token to the address of the owner from the caller, issues a PromotionSuccess event

where **signature** = signed ECDSA.toEthSignedMessageHash(keccak256(abi.encodePacked(block.chainid, _msgSender(), address(this), package, token, amount, promotionChainId, promotionToken, promotionId, deadline)))

**setSigner**(address _signer) external onlyOwner; - changes signer address

**setFeeReceiver**(address _feeReceiver) external onlyOwner - zero address can not be set

&nbsp;

##Contract addresses:

&nbsp;

[USDT](https://rinkeby.etherscan.io/address/0x2fA5bA53F23a6e79D2047bEdaCef787b21C9076a)

[WMATIC](https://rinkeby.etherscan.io/address/0xB527C30fbefaBc5FD62c5Fcb1c191D915c5cade4)

&nbsp;

###Rinkeby

&nbsp;

[FactoryERC721](https://rinkeby.etherscan.io/address/0x9fe527F3652D162521366C46DE16d0e27b3B183A)

[FactoryERC1155](https://rinkeby.etherscan.io/address/0xBFEc563010Ca78a3cf05996edfa81289a349276a)

[Exchange](https://rinkeby.etherscan.io/address/0x10D4397AE24AEB7d3dc832EadA809B1a2c2774B6)

[Promotion](https://rinkeby.etherscan.io/address/0xc343952d91a367AcD27DBC4485a0Ad96d55EB8A6)
