import requests, base64
from solders.keypair import Keypair # type: ignore
from solders.pubkey import Pubkey # type: ignore
from solana.rpc.api import Client
import time, json
from solders.transaction import Transaction # type: ignore
from solders.transaction import VersionedTransaction # type: ignore
from solders import message
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Processed
import json
from typing import Optional


class JupiterReferralAPI:
    def __init__(self):
        self.base_url = "https://referral.jup.ag"
        self.client = Client(
            'https://solana-mainnet.api.syndica.io/api-key/faKTzw51EinVZKmoyEVd7wbePKtmKhFYt4HEDuoxGAW4fkbEFUVrsL2MY1uRc9kXcQTZC8acLTQGb8dEufyX65LrzXd38S7NHS',
            commitment="confirmed", timeout=30)

    def create_token_account(self,
                             referral_pubkey: str,
                             mint: str,
                             fee_payer: str) -> Optional[dict]:
        """
        Create a new token account for a referral account.

        Args:
            referral_pubkey (str): Public key of the referral from dashboard
            mint (str): The mint address
            fee_payer (str): The fee payer address

        Returns:
            dict: Response containing the transaction data
            None: If the request fails
        """

        # Construct the endpoint URL
        endpoint = f"{self.base_url}/api/referral/{referral_pubkey}/token-accounts/create"

        # Prepare the request payload
        payload = {
            "mint": mint,
            "feePayer": fee_payer
        }

        # Set headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        try:
            # Make the POST request
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers
            )

            # Check if request was successful
            response.raise_for_status()

            # Parse and return the response
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"Error making request: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing response: {str(e)}")
            return None

    def send_tx(self, txn: Transaction, keypair: Keypair) -> str:
        txn_data = txn.get('tx')
        raw_transaction = VersionedTransaction.from_bytes(base64.b64decode(txn_data))
        signature = keypair.sign_message(message.to_bytes_versioned(raw_transaction.message))
        signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])
        opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)

        result = self.client.send_raw_transaction(txn=bytes(signed_txn), opts=opts)
        transaction_id = json.loads(result.to_json())['result']
        return transaction_id


def main():
    # Example usage
    api = JupiterReferralAPI()

    # Replace these with actual values
    referral_pubkey = "3cnbobTC5P1oBinqZsDkSpX2AJX8qLy68RLYgexSisrA"
    mint = "32i3VKoMrkY1sszZSsYF3o6zejiiTs1xh5jgqMHDpump"
    fee_payer = "FEEe6yjpq1JDqQSmRQ2puNAVnT81jV64A2h65FXB5SqZ"
    keypair = "4JPS249rAJzSCKc32GjppL3zBkuUeGbP7qi8T3pHnWMftq7zmwyzBJ7CLGDkMKEBYCVnafYrbLzZAHq9BkaFQaef"
    sender = Keypair.from_base58_string(keypair)
    # Create token account
    result = api.create_token_account(
        referral_pubkey=referral_pubkey,
        mint=mint,
        fee_payer=fee_payer
    )
    print(result)
    send = api.send_tx(result, sender)
    print(f"Transaction sent: https://solscan.io/tx/{send}")


if __name__ == "__main__":
    main()