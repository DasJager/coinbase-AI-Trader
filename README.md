# Automated Trading Bot with LLM-Driven Decisions

## Overview

This Python project implements an automated trading bot that interacts with a cryptocurrency exchange API to fetch market data, assess trading opportunities using a Language Model (LLM), and execute trades based on the LLM's recommendations. The bot is designed to handle real-time trading decisions for the BTC/USDC pair, and it can automatically place buy or sell orders based on the LLM's analysis.

**Disclaimer**: This code is still a work in progress. If you're interested in contributing or forking this repository, please feel free to do so! I’m excited to see this project grow and potentially become a standard in modern trading. We need more real AI-driven projects that are both FREE and capable of running locally. Let's make that a reality together! 

**Disclaimer**: This project is purely for informational and educational purposes only. It is intended to demonstrate how such a system could be built, not for live trading. The use of this code in a live trading environment is done at your own risk, and the creators of this project are not responsible for any financial losses. BUT YES! it does work in practice

## Features

- **Market Data Fetching**: Retrieves real-time ticker data, including best bid and ask prices, and recent trades.
- **JWT Authentication**: Securely interacts with the exchange API using JSON Web Tokens (JWT) for authentication.
- **Balance Checking**: Fetches and displays the current balances of BTC and USDC in the account.
- **LLM-Driven Trading Decisions**: Constructs prompts using market data and account balances, and queries an LLM to decide whether to buy, sell, or hold.
- **Automated Order Placement**: Places buy or sell orders on the exchange based on the LLM's recommendation.
- **Logging**: Comprehensive logging to track bot actions, API responses, and errors.

## Installation

### Prerequisites

- **Python 3.x**: Ensure you have Python 3.x installed on your system.
- **Pip**: Python's package installer, used to install required dependencies.
- **OpenAI API Key**: Required for interacting with the LLM (configured locally in this project).
