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