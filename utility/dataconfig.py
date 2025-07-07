from dataclasses import dataclass

@dataclass
class Config:
    LAMPORTS_PER_SOL: int = 1000000000
    RPC_URL: str = 'https://solana-mainnet.api.syndica.io/api-key/'
    DEFAULT_SLIPPAGE: int = 5
    DEFAULT_PRIORITY_FEE: float = 0.0005
    COMPUTE_PRICE: int = 400000
    COMPUTE_LIMIT: int = 200000
    FEE_RECIPIENT: str = ""
    FEE_PERCENTAGE: float = 0.005  # 0.5%
    FEE_KEY: str = ""
    FEE_PRIVATE_KEY: str = ""

CUSTOM_OPTIONS = {
    "send_options": {"skip_preflight": True, "max_retries": 5},
    "confirmation_retries": 50,
    "confirmation_retry_timeout": 1000,
    "last_valid_block_height_buffer": 200,
    "commitment": "processed",
    "resend_interval": 1500,
    "confirmation_check_interval": 1000,
    "skip_confirmation_check": True,
}

