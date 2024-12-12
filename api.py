from fastapi import FastAPI
from api.wallet.transfer import router as transfer_router

app = FastAPI()

app.include_router(transfer_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)