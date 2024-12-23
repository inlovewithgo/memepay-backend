from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from solders.keypair import Keypair # type: ignore
from solders.pubkey import Pubkey as Pubkey # type: ignore
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (
    transfer_checked,
    TransferCheckedParams,
)

from utility.dataconfig import Config
from ..main import create_assoc_tkn_acct, SolanaTransactionManager, get_tkn_acct

router = APIRouter()

class SendTokenRequest(BaseModel):
    src_key: str
    tkn_addr: str
    dest_addr: str
    tkn_amt: float

@router.post("/wallet/send_token")
async def send_tkn(request: SendTokenRequest):
    try:
        src_keypair = Keypair.from_base58_string(request.src_key)
        tkn_pubkey = Pubkey(request.tkn_addr)
        dest_pubkey = Pubkey(request.dest_addr)

        RPC_URL = Config.RPC_URL
        manager = SolanaTransactionManager(RPC_URL)
        txn = manager.get_transaction_builder(src_keypair.public_key)

        src_tkn_data = get_tkn_acct(src_keypair.public_key, tkn_pubkey)
        if not src_tkn_data['tkn_acct_pubkey']:
            raise HTTPException(status_code=400, detail="Source account does not have that token")

        dest_tkn_data = get_tkn_acct(dest_pubkey, tkn_pubkey)
        dest_tkn_acct_pubkey = (
            dest_tkn_data['tkn_acct_pubkey'] if dest_tkn_data['tkn_acct_pubkey']
            else create_assoc_tkn_acct(src_keypair, dest_pubkey, tkn_pubkey)
        )

        send_amt_lamps = int(request.tkn_amt * 10 ** int(src_tkn_data['tkn_dec']))
        txn.add(transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=src_tkn_data['tkn_acct_pubkey'],
                mint=tkn_pubkey,
                dest=dest_tkn_acct_pubkey,
                owner=src_keypair.public_key,
                amount=send_amt_lamps,
                decimals=src_tkn_data['tkn_dec'],
            )
        ))
        txn.sign([src_keypair])

        txn_hash = manager.send_transaction(txn)
        return {"status": "success", "transaction_hash": txn_hash}

    except KeyError as ke:
        raise HTTPException(status_code=400, detail=f"Missing key: {str(ke)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))