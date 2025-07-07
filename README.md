# MemePay Backend

MemePay is a modern crypto wallet service focused on **Solana** and **memecoins**.  
This repository contains the **backend** source code that powers MemePay's API and blockchain interactions.

---

## ✨ Features

- 🪙 Solana wallet creation & management using [`solana-py`](https://github.com/michaelh/solders)
- 💸 Send and receive SOL and memecoins
- 📦 Modular architecture for fast integration
- 🔐 Secure key management and transaction signing
- 🌐 Ready-to-deploy RESTful API backend

---

## ⚙️ Setup Instructions

### 1. Clone the repo

```bash
git clone https://github.com/inlovewithgo/memepay-backend.git
cd memepay-backend
```

### 2. Create a virtual enviorment

```
python -m venv env
```

### 3. Activate the environment

On Windows:
```bash
.\env\Scripts\activate
```

On macOS/Linux:
```bash
source env/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

## 📁 File Structure

```bash
.
├── core/               # Core logic for Solana interactions
├── api/                # API endpoints
├── utility/            # App configuration
├── requirements.txt    # Python dependencies
├── README.md           # Project info
```

## 🧪 Run the Backend
```bash
python main.py
```

## 📌 Notes
- Ensure your `.env` file is configured correctly for Solana RPC, database credentials, etc.
- This is the backend repo only. Frontend lives [here](https://github.com/inlovewithgo/memepay-frontend).

## 🤝 Contributing
Feel free to open issues or submit PRs if you'd like to help improve MemePay!
( MemePay has been closed until further notice, Contributions can be still made )
