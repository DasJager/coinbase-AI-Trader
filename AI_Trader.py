import time
import secrets
import requests
import uuid
import http.client
import json
import logging
from datetime import datetime
import openai
from cryptography.hazmat.primitives import serialization
import jwt

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# Replace these with your actual values
key_name = "organizations/"
key_secret = """-----BEGIN EC PRIVATE KEY-----\\n-----END EC PRIVATE KEY-----\n"""
request_host = "api.coinbase.com"

# Initialize the LLM API client
openai.api_base = "http://localhost:1234/v1"
openai.api_key = "lm-studio"

# Function to collect market ticker data and feed it directly to the LLM
def get_market_ticker(product_id):
    try:
        logger.debug(f"Fetching market ticker data for {product_id}...")
        request_path = f"/api/v3/brokerage/products/{product_id}/ticker"
        uri = f"GET {request_host}{request_path}"

        # Generate the JWT token
        jwt_token = build_jwt(uri)

        # Set up the headers with the JWT token
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }

        # Make the request to get the ticker data
        conn = http.client.HTTPSConnection(request_host)
        conn.request("GET", request_path, '', headers)
        res = conn.getresponse()
        data = res.read()

        # Check the response status code
        if res.status == 200:
            ticker_data = json.loads(data.decode("utf-8"))

            # Extract relevant data points
            best_bid = float(ticker_data.get('best_bid', '0'))
            best_ask = float(ticker_data.get('best_ask', '0'))

            # Summarize recent trades
            trades_summary = "\n".join([
                f"Trade ID: {trade['trade_id']}, Price: {trade['price']}, Size: {trade['size']}, Side: {trade['side']}"
                for trade in ticker_data.get('trades', [])[:100]  # Limiting to first 100 trades for summary
            ])

            # Construct a text prompt for the LLM
            prompt = (
                f"Market data for {product_id}:\n"
                f"Best Bid: {best_bid}\n"
                f"Best Ask: {best_ask}\n"
                f"Time: {datetime.now()}\n\n"
                f"Recent Trades:\n{trades_summary}\n"
            )

            logger.debug(f"Constructed prompt for LLM: {prompt}")

            return prompt, best_bid, best_ask  # Return the prompt, best_bid, and best_ask

        else:
            logger.error(f"Failed to retrieve ticker for {product_id}: {res.status} - {data.decode('utf-8')}")
            return None, None, None
    except Exception as e:
        logger.exception(f"Error getting market ticker for {product_id}.")
        return None, None, None


# Build JWT for authentication
def build_jwt(uri):
    try:
        logger.debug("Building JWT for authentication...")
        private_key_bytes = key_secret.encode('utf-8')
        private_key = serialization.load_pem_private_key(private_key_bytes, password=None)
        
        jwt_payload = {
            'sub': key_name,
            'iss': "cdp",
            'nbf': int(time.time()),
            'exp': int(time.time()) + 120,
            'uri': uri,
        }
        
        jwt_token = jwt.encode(
            jwt_payload,
            private_key,
            algorithm='ES256',
            headers={'kid': key_name, 'nonce': secrets.token_hex()},
        )
        logger.info("JWT built successfully.")
        return jwt_token
    except Exception as e:
        logger.exception("Failed to build JWT.")
        return None

def get_balances():
    request_path = "/api/v3/brokerage/accounts"
    uri = f"GET {request_host}{request_path}"
    jwt_token = build_jwt(uri)
    
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(f'https://{request_host}{request_path}', headers=headers)
    
    if response.status_code == 200:
        accounts = response.json()['accounts']
        btc_balance = None
        usdc_balance = None

        for account in accounts:
            if account['currency'] == "BTC":
                btc_balance = float(account['available_balance']['value'])
            elif account['currency'] == "USDC":
                usdc_balance = float(account['available_balance']['value'])

        if btc_balance is not None:
            print(f"Your BTC balance is: {btc_balance} BTC")
        else:
            print("BTC account not found.")

        if usdc_balance is not None:
            print(f"Your USDC balance is: {usdc_balance} USDC")
        else:
            print("USDC account not found.")

        return btc_balance, usdc_balance
    else:
        print(f"Failed to retrieve accounts: {response.status_code} - {response.text}")
        return None, None



# Function to make a trade decision using LLM and KNN strategy
def make_llm_trade_decision(prompt):
    try:
        # Enhance the prompt with KNN prediction context
        enhanced_prompt = (
            f"{prompt}\n\n"
            "You are an expert day trader utilizing a KNN prediction model for market analysis.\n"
            "A positive value suggests an upward trend (BUY), while a negative value suggests a downward trend (SELL).\n"
            "Based on this prediction and your strategy, should we BUY, SELL, or HOLD? Respond with one word: BUY, SELL, or HOLD."
        )


        logger.debug(f"Sending enhanced prompt to LLM:\n{enhanced_prompt}")
        
        response = openai.Completion.create(
            model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
            prompt=enhanced_prompt,
            max_tokens=150
        )

        logger.debug(f"Raw LLM response: {response}")

        if isinstance(response, dict) and 'choices' in response:
            reply = response['choices'][0]['text']
            logger.debug(f"LLM parsed response: {reply}")

            if "BUY" in reply.upper():
                return "BUY"
            elif "SELL" in reply.upper():
                return "SELL"
            else:
                return "HOLD"
        else:
            logger.error("Unexpected response format from LLM.")
            return "HOLD"
    except Exception as e:
        logger.exception("Failed to communicate with LLM.")
        return "HOLD"



# Get current BTC price
def get_current_btc_price():
    logger.info("Fetching current BTC price...")
    request_path = "/api/v3/brokerage/products/BTC-USDC/ticker"
    uri = f"GET {request_host}{request_path}"
    jwt_token = build_jwt(uri)

    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Content-Type': 'application/json'
    }

    response = requests.get(f'https://{request_host}{request_path}', headers=headers)

    if response.status_code == 200:
        ticker_data = response.json()

        # Log the entire response to inspect the structure
        logger.debug(f"Ticker data response: {json.dumps(ticker_data, indent=2)}")

        # Calculate the midpoint of best_bid and best_ask as the current price
        if 'best_bid' in ticker_data and 'best_ask' in ticker_data:
            best_bid = float(ticker_data['best_bid'])
            best_ask = float(ticker_data['best_ask'])
            current_price = (best_bid + best_ask) / 2
            logger.info(f"Calculated BTC price: {current_price:.8f} USDC (midpoint of best_bid and best_ask)")
            return current_price
        else:
            logger.error("Keys 'best_bid' or 'best_ask' not found in the ticker data.")
            return None
    else:
        logger.error(f"Failed to retrieve BTC price: {response.status_code} - {response.text}")
        return None

# Place buy order for $2 worth of BTC
def place_buy_order(price):
    try:
        amount_usdc = 2.00  # Trade $2 at a time
        logger.info(f"Placing buy order for {amount_usdc:.2f} USDC at {price:.2f} USDC/BTC")
        amount_usdc_str = f"{amount_usdc:.2f}"

        request_path = "/api/v3/brokerage/orders"
        uri = f"POST {request_host}{request_path}"
        jwt_token = build_jwt(uri)
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        order_id = str(uuid.uuid4())
        order = {
            "order_configuration": {
                "market_market_ioc": {
                    "quote_size": amount_usdc_str  # The amount of USDC to spend
                }
            },
            "side": "BUY",
            "client_order_id": order_id,
            "product_id": "BTC-USDC"  # The trading pair
        }
        
        response = requests.post(f'https://{request_host}{request_path}', headers=headers, json=order)
        
        if response.status_code == 200:
            logger.info(f"Buy order placed successfully at price {price:.2f} USDC/BTC")
        else:
            logger.error(f"Failed to place buy order: {response.status_code} - {response.text}")
    except Exception as e:
        logger.exception("Error placing buy order.")

# Place sell order for $2 worth of BTC
def place_sell_order(price):
    try:
        amount_usdc = 2.00  # Trade $2 at a time
        amount_btc = amount_usdc / price  # Convert $2 USDC to BTC at the current price
        logger.info(f"Placing sell order for {amount_btc:.8f} BTC at {price:.2f} USDC/BTC")
        amount_btc_str = f"{amount_btc:.8f}"

        request_path = "/api/v3/brokerage/orders"
        uri = f"POST {request_host}{request_path}"
        jwt_token = build_jwt(uri)
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        order_id = str(uuid.uuid4())
        order = {
            "order_configuration": {
                "market_market_ioc": {
                    "base_size": amount_btc_str  # The amount of BTC to sell
                }
            },
            "side": "SELL",
            "product_id": "BTC-USDC",
            "client_order_id": order_id
        }
        
        response = requests.post(f'https://{request_host}{request_path}', headers=headers, json=order)
        
        if response.status_code == 200:
            logger.info(f"Sell order placed successfully at price {price:.2f} USDC/BTC")
        else:
            logger.error(f"Failed to place sell order: {response.status_code} - {response.text}")
    except Exception as e:
        logger.exception("Error placing sell order.")




# Main trading logic
def main():
    logger.info("Starting main trading loop...")
    while True:
        # Get the current balances
        btc_balance, usdc_balance = get_balances()

        if btc_balance is None or usdc_balance is None:
            logger.warning("Failed to retrieve account balances. Skipping this cycle.")
            continue

        # Fetch real-time market data and construct prompt for LLM
        prompt, best_bid, best_ask = get_market_ticker('BTC-USDC')

        if prompt and best_bid and best_ask:
            current_price = get_current_btc_price()

            if current_price is not None:
                # Fetch recent trades for the product
                recent_trades = get_recent_trades('BTC-USDC')

                # Append the current price, balances, and recent trades to the prompt
                prompt += (
                    f"\nCurrent BTC price: {current_price} USDC."
                    f"\nBTC Balance: {btc_balance} BTC."
                    f"\nUSDC Balance: {usdc_balance} USDC."
                    f"\n\nRecent Trades:\n{recent_trades}"
                )

                # Get the decision from the LLM
                decision = make_llm_trade_decision(prompt)
                logger.info(f"Trade decision: {decision}")

                # Execute the trade based on LLM's decision
                if decision == "BUY" and usdc_balance > 0:
                    place_buy_order(current_price)
                elif decision == "SELL" and btc_balance > 0:
                    place_sell_order(current_price)
                else:
                    logger.info("Decision was to HOLD, or insufficient balance for trade.")

            else:
                logger.warning("Failed to fetch the current BTC price.")

        else:
            logger.warning("Failed to construct prompt for LLM. Skipping this cycle.")

        time.sleep(2)

if __name__ == "__main__":
    main()



