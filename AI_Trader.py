import time
import json
import logging
from datetime import datetime, timedelta, timezone
import openai
from coinbase.rest import RESTClient
import uuid

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# Your API credentials
client = RESTClient(
    api_key='organizations/',
    api_secret='-----BEGIN EC PRIVATE KEY-----\\n-----END EC PRIVATE KEY-----\n',
timeout=10000)

# Initialize the LLM API client
openai.api_base = "http://localhost:1234/v1"
openai.api_key = "lm-studio"


# Function to make a trade decision using LLM and KNN strategy
def make_llm_trade_decision(prompt):
    try:
        # Enhance the prompt with KNN prediction context
        enhanced_prompt = (
            f"{prompt}\n"
            "You are an expert day trader utilizing a KNN prediction model for market analysis."
            "Recent price movements indicate either an upward or downward trend."
            "If the trend is positive and strong, respond with BUY."
            "If the trend is negative and strong, respond with SELL."
            "If the trend is unclear or weak, respond with HOLD."
            "Based on this prediction and your strategy, should we BUY, SELL, or HOLD? Respond with one word: BUY, SELL, or HOLD."
        )



        logger.debug(f"Sending enhanced prompt to LLM:\n{enhanced_prompt}")
        
        response = openai.Completion.create(
            model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
            prompt=enhanced_prompt,
            max_tokens=100,
            temperature=0.0
        )

        logger.debug(f"Raw LLM response: {response}")

        if isinstance(response, dict) and 'choices' in response:
            reply = response['choices'][0]['text']
            logger.debug(f"LLM parsed response: {reply}")

            if "BUY" in reply.upper():
                return "BUY"
            elif "SELL" in reply.upper():
                return "SELL"
            elif "HOLD" in reply.upper():
                return "HOLD"
            else:
                logger.warning("Unclear response from LLM, defaulting to HOLD.")
                return "HOLD"
        else:
            logger.error("Unexpected response format from LLM.")
            return "HOLD"
    except Exception as e:
        logger.exception("Failed to communicate with LLM.")
        return "HOLD"


def get_product_book(product_id):
    try:
        logger.debug(f"Fetching product book data for {product_id}...")

        # Fetch the product book data using the SDK's built-in method
        product_book_data = client.get_product_book(product_id=product_id, limit=100)

        # Log the entire raw response to inspect its structure
        #logger.debug(f"Full product book data: {product_book_data}")

        # Ensure the product_book_data is valid and contains expected fields
        if not product_book_data or 'pricebook' not in product_book_data:
            logger.error("Product book data is empty or missing 'pricebook'.")
            return None, None, None

        # Extract bids and asks from the 'pricebook' section of the data
        pricebook = product_book_data.get('pricebook', {})
        bids = pricebook.get('bids', [])
        asks = pricebook.get('asks', [])

        # Find the best bid (highest bid price) and best ask (lowest ask price)
        best_bid = float(bids[0]['price']) if bids else None
        best_ask = float(asks[0]['price']) if asks else None

        if best_bid is None or best_ask is None:
            logger.error("Failed to extract best bid or best ask from the data.")
            return None, None, None

        # recent trades from bids and asks data
        recent_trades = []

        # Assume that each trade happens at the midpoint between a bid and an ask
        for i in range(min(len(bids), len(asks))):
            trade_price = (float(bids[i]['price']) + float(asks[i]['price'])) / 2
            trade_size = min(float(bids[i]['size']), float(asks[i]['size']))  # Assume trade size is the smaller of bid/ask
            recent_trades.append({
                'trade_id': f"trade_{i}",
                'price': trade_price,
                'size': trade_size
            })

        # Log how many trades were simulated
        logger.debug(f"Number of simulated recent trades: {len(recent_trades)}")

        # Condensed format to fit more trades into the prompt
        max_trades = 100  # Set the maximum number of trades to include in the prompt
        recent_trades = recent_trades[:max_trades]

        trades_summary = "".join([
            f"{trade['trade_id']} {trade['price']} {trade['size']}"
            for trade in recent_trades
        ])

        # Construct a text prompt for the LLM
        prompt = (
            f"Market data for {product_id}:"
            f"Best Bid: {best_bid}"
            f"Best Ask: {best_ask}"
            f"Time: {datetime.now()}"
            f"Recent Trades:{trades_summary}"
        )

        logger.debug(f"Constructed prompt for LLM: {prompt}")

        return prompt, best_bid, best_ask

    except Exception as e:
        logger.exception(f"Error getting product book data for {product_id}: {e}")
        return None, None, None


def get_balances():
    try:
        # Fetch account balances using the SDK
        response = client.get_accounts()

        # Extract the list of accounts from the response
        accounts = response.get('accounts', [])

        # Log the raw accounts response for debugging
        #logger.debug(f"Accounts data: {accounts}")

        btc_balance = None
        usdc_balance = None

        # Loop through the accounts to find balances for BTC and USDC
        for account in accounts:
            if isinstance(account, dict):
                currency = account.get('currency', '')
                available_balance = account.get('available_balance', {}).get('value', 0)

                if currency == "BTC":
                    btc_balance = float(available_balance)
                elif currency == "USDC":
                    usdc_balance = float(available_balance)

        # Print and return balances
        if btc_balance is not None:
            print(f"Your BTC balance is: {btc_balance} BTC")
        else:
            print("BTC account not found.")

        if usdc_balance is not None:
            print(f"Your USDC balance is: {usdc_balance} USDC")
        else:
            print("USDC account not found.")

        return btc_balance, usdc_balance

    except Exception as e:
        logger.exception("Failed to retrieve account balances.")
        return None, None



# Get current BTC price
def get_current_btc_price():
    try:
        logger.info("Fetching current BTC price...")

        # Fetch the product book data using the SDK's method
        product_book_data = client.get_product_book(product_id="BTC-USDC")

        # Check if 'pricebook' exists in the returned data
        if 'pricebook' not in product_book_data:
            logger.error("'pricebook' key is missing in the product book data.")
            return None

        # Extract bids and asks from 'pricebook'
        pricebook = product_book_data.get('pricebook', {})
        bids = pricebook.get('bids', [])
        asks = pricebook.get('asks', [])

        # Ensure bids and asks are available
        if not bids or not asks:
            logger.error("Bids or asks are missing in the 'pricebook'.")
            return None

        # Get the best bid and ask from the first entry
        best_bid = float(bids[0]['price']) if bids else None
        best_ask = float(asks[0]['price']) if asks else None

        # Calculate the midpoint as the current price
        if best_bid and best_ask:
            current_price = (best_bid + best_ask) / 2
            logger.info(f"Calculated BTC price: {current_price:.8f} USDC (midpoint of best_bid and best_ask)")
            return current_price
        else:
            logger.error("Best bid or best ask is missing.")
            return None

    except Exception as e:
        logger.exception("Failed to retrieve BTC price.")
        return None


# Place buy order for $2 worth of BTC
def market_order_buy(price):
    try:
        amount_usdc = 2.00  # Trade $2 at a time
        logger.info(f"Placing buy order for {amount_usdc:.2f} USDC at {price:.2f} USDC/BTC")

        # Generate a unique order ID
        order_id = str(uuid.uuid4())

        # Use the SDK's built-in method to place a buy order
        order = client.market_order_buy(
            product_id="BTC-USDC", 
            quote_size=f"{amount_usdc:.2f}",  # The amount of USDC to spend
            client_order_id=order_id
        )

        logger.info(f"Buy order placed successfully at price {price:.2f} USDC/BTC")
    except Exception as e:
        logger.exception("Error placing buy order.")



# Place sell order for $2 worth of BTC
def market_order_sell(price):
    try:
        amount_usdc = 2.00  # Trade $2 at a time
        amount_btc = amount_usdc / price  # Convert $2 USDC to BTC at the current price
        logger.info(f"Placing sell order for {amount_btc:.8f} BTC at {price:.2f} USDC/BTC")

        # Generate a unique order ID
        order_id = str(uuid.uuid4())

        # Use the SDK's built-in method to place a sell order
        order = client.market_order_sell(
            product_id="BTC-USDC", 
            base_size=f"{amount_btc:.8f}",  # The amount of BTC to sell
            client_order_id=order_id
        )

        logger.info(f"Sell order placed successfully at price {price:.2f} USDC/BTC")
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
        prompt, best_bid, best_ask = get_product_book('BTC-USDC')

        if prompt and best_bid and best_ask:
            current_price = get_current_btc_price()

            if current_price is not None:
        
                # Append the current price, balances, and recent trades to the prompt
                prompt += (
                    f"Current BTC price: {current_price} USDC."
                    f"BTC Balance: {btc_balance} BTC."
                    f"USDC Balance: {usdc_balance} USDC."
                )

                # Get the decision from the LLM
                decision = make_llm_trade_decision(prompt)
                logger.info(f"Trade decision: {decision}")

                # Execute the trade based on LLM's decision
                if decision == "BUY" and usdc_balance > 0:
                    market_order_buy(current_price)
                elif decision == "SELL" and btc_balance > 0:
                    market_order_sell(current_price)
                else:
                    logger.info("Decision was to HOLD, or insufficient balance for trade.")

            else:
                logger.warning("Failed to fetch the current BTC price.")

        else:
            logger.warning("Failed to construct prompt for LLM. Skipping this cycle.")

        time.sleep(2)

if __name__ == "__main__":
    main()



