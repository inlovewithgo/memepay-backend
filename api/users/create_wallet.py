from fastapi import APIRouter, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from solana.rpc.api import Client
from solders.keypair import Keypair
from base58 import b58encode
from typing import Dict
from database.models import WalletResponse, PhraseRequest
import uuid
from mnemonic import Mnemonic

from bip32utils import BIP32Key
import hashlib

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)

@router.post("/createwallet", response_model=WalletResponse)
async def create_wallet():
    try:
        keypair = Keypair()

        public_key = str(keypair.pubkey())
        private_key = b58encode(bytes(keypair)).decode('ascii')

        wallet_id = str(uuid.uuid4())

        mnemo = Mnemonic("english")
        mnemonic_phrase = mnemo.generate(strength=128)

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
            seed = mnemo.to_seed(request.phrase)
            keypair = Keypair.from_seed(hashlib.sha256(seed).digest()[:32])

            return {
                "status": "success",
                "valid": True,
                "public_key": str(keypair.pubkey())
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