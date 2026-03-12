"""
CRANIUM FUND - Automated Treasury Smart Contract Interface
Architectural Choice: Smart contracts provide immutable, transparent 
profit distribution without manual intervention, ensuring 80% always 
goes to hardware fund.
"""
import os
import logging
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError, TransactionNotFound
from eth_account import Account
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class TreasuryConfig:
    """Configuration for treasury profit splitting"""
    cranium_percentage: Decimal = Decimal('0.80')  # 80% to hardware fund
    operations_percentage: Decimal = Decimal('0.10')  # 10% to operations
    growth_percentage: Decimal = Decimal('0.10')  # 10% to growth/marketing
    min_balance_trigger: Decimal = Decimal('100.0')  # Minimum balance to trigger distribution

class SmartTreasury:
    """
    Zero-trust automated treasury management with smart contract integration
    Edge Cases Handled:
    - Network congestion with gas price optimization
    - Failed transactions with retry logic
    - Insufficient funds with graceful degradation
    - Invalid contract states with validation checks
    """
    
    # ABI for simplified treasury smart contract
    TREASURY_CONTRACT_ABI = [
        {
            "inputs": [
                {"internalType": "address", "name": "_craniumWallet", "type": "address"},
                {"internalType": "address", "name": "_operationsWallet", "type": "address"},
                {"internalType": "address", "name": "_growthWallet", "type": "address"}
            ],
            "stateMutability": "nonpayable",
            "type": "constructor"
        },
        {
            "inputs": [],
            "name": "distributeFunds",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "getBalances",
            "outputs": [
                {"internalType": "uint256", "name": "contractBalance", "type": "uint256"},
                {"internalType": "uint256", "name": "craniumShare", "type": "uint256"},
                {"internalType": "uint256", "name": "operationsShare", "type": "uint256"},
                {"internalType": "uint256", "name": "growthShare", "type": "uint256"}
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "craniumWallet",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    
    def __init__(self, config: Optional[TreasuryConfig] = None):
        """Initialize treasury with configuration"""
        self.config = config or TreasuryConfig()
        self.web3 = None
        self.contract = None
        self.contract_address = None
        self._initialized = False
        
        # Load environment
        load_dotenv()
        
    def initialize_network(self, network: str = "polygon") -> bool:
        """Initialize Web3 connection to specified network"""
        try:
            rpc_url = self._get_rpc_url(network)
            if not rpc_url:
                logger.error(f"No RPC URL configured for network: {network}")
                return False
            
            self.web3 = Web3(Web3.HTTPProvider(rpc_url))
            
            if not self.web3.is_connected():
                logger.error(f"Failed to connect to {network} network")
                return False
            
            logger.info(f"Connected to {network} network (