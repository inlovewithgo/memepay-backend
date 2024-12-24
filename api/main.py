import json
from typing import Dict, Any
from solana.rpc.api import Client
from solana.transaction import Transaction 
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.types import TxOpts
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.client import Token
from solders.system_program import transfer, TransferParams
from spl.token.instructions import (
    get_associated_token_address,
    transfer_checked,
    TransferCheckedParams,
    create_associated_token_account,
)
from utility.dataconfig import Config
from solana.rpc.types import TokenAccountOpts, TxOpts
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from utility.logger import logging

logger = logging.getLogger("solana_transactions")

class SolanaTransactionManager:
   def __init__(self, rpc_url: str):
       self.client = Client(rpc_url, commitment="confirmed", timeout=30)
       self.config = Config()

   def get_transaction_builder(self, fee_payer: Pubkey) -> Transaction:
       try:
           blockhash = self.client.get_latest_blockhash().value.blockhash
           return Transaction(fee_payer=fee_payer, recent_blockhash=blockhash)
       except Exception as e:
           logger.error(f"Error getting transaction builder: {str(e)}")
           raise

   def add_compute_budget(self, transaction: Transaction, price: int = Config.COMPUTE_PRICE,
                          limit: int = Config.COMPUTE_LIMIT):
       try:
           transaction.add(set_compute_unit_price(price))
           transaction.add(set_compute_unit_limit(limit))
           print(f"Added compute budget - price: {price}, limit: {limit}")
       except Exception as e:
           logger.error(f"Error adding compute budget: {str(e)}")
           raise

   def send_transaction(self, transaction: Transaction) -> str:
       try:
           serialized_txn = transaction.serialize()
           resp = self.client.send_raw_transaction(
               serialized_txn,
               opts=TxOpts(skip_confirmation=True, preflight_commitment="confirmed")
           )
           result = json.loads(resp.to_json())['result']
           logger.info(f"Transaction sent successfully: {result}")
           return result
       except Exception as e:
           logger.error(f"Failed to send transaction: {str(e)}")
           raise

   def send_swap(self, transaction: Transaction) -> str:
       try:
           serialized_txn = bytes(transaction)
           resp = self.client.send_raw_transaction(
               serialized_txn,
               opts=TxOpts(skip_confirmation=True, preflight_commitment="processed")
           )
           logger.info(f"Swap transaction sent successfully")
           return resp
       except Exception as e:
           logger.error(f"Failed to send swap transaction: {str(e)}")
           raise

   def get_spl_token_decimals(self, token_address: str) -> int:
       try:
           token_pubkey = Pubkey(token_address)
           supply_response = self.client.get_token_supply(token_pubkey)
           if supply_response.value:
               logger.info(f"Retrieved decimals for token {token_address}")
               return supply_response.value.decimals
           logger.warning(f"No supply response for token {token_address}")
           return None
       except Exception as e:
           logger.error(f"Error fetching token decimals: {str(e)}")
           return None

def send_sol(src_key: str, dest_addr: str, amt_sol: float) -> str:
    try:
        manager = SolanaTransactionManager(Config.RPC_URL)
        try:
            src_keypair = Keypair.from_base58_string(src_key)
        except Exception as e:
            logger.error(f"Failed to create keypair: {str(e)}")
            raise

        try:
            dest_pubkey = Pubkey.from_string(dest_addr)
        except Exception as e:
            logger.error(f"Failed to create destination pubkey: {str(e)}")
            raise

        send_amt_lamps = int(amt_sol * Config.LAMPORTS_PER_SOL)

        txn = manager.get_transaction_builder(src_keypair.pubkey())
        txn.add(
        transfer(
            TransferParams(
                from_pubkey   = src_keypair.pubkey(),
                to_pubkey     = dest_pubkey,
                lamports      = send_amt_lamps
            )
        )
    )   
        txn.sign(src_keypair)

        return manager.send_transaction(txn)
    except Exception as e:
        logger.error(f"Failed to send SOL: {str(e)}")
        raise

    
def create_assoc_tkn_acct(payer: Keypair, owner: Pubkey, mint: Pubkey) -> Pubkey:
   try:
       manager = SolanaTransactionManager(Config.RPC_URL)
       txn = manager.get_transaction_builder(payer.pubkey())
       create_txn = create_associated_token_account(payer=payer.pubkey(), owner=owner, mint=mint)
       txn.add(create_txn)
       manager.add_compute_budget(txn)
       txn.sign(payer)

       manager.send_transaction(txn)
       assoc_addr = get_associated_token_address(owner, mint)
       return assoc_addr
   except Exception as e:
       logger.error(f"Failed to create associated token account: {str(e)}")
       raise


def get_tkn_acct(wallet_addr: Pubkey, tkn_addr: Pubkey) -> Dict[str, Any]:
   client = Client(Config.RPC_URL)
   try:
       tkn_acct_data = client.get_token_accounts_by_owner(wallet_addr, TokenAccountOpts(tkn_addr))

       if not tkn_acct_data.value:
           logger.warning(f"No token account found for wallet: {wallet_addr}")
           return {'tkn_acct_pubkey': None, 'tkn_bal': 0, 'tkn_dec': 0}

       tkn_acct_pubkey = tkn_acct_data.value[0].pubkey
       balance_info = Token(
           conn=client,
           pubkey=tkn_addr,
           program_id=TOKEN_PROGRAM_ID,
           payer=client
       ).get_balance(tkn_acct_pubkey)

       result = {
           'tkn_acct_pubkey': tkn_acct_pubkey,
           'tkn_bal': balance_info.value.ui_amount,
           'tkn_dec': balance_info.value.decimals
       }
       logger.info(f"Retrieved token account info: {result}")
       return result
   except Exception as e:
       logger.error(f"Failed to get token account: {str(e)}")
       return {'tkn_acct_pubkey': None, 'tkn_bal': 0, 'tkn_dec': 0}
