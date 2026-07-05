# 🤖 Snowflake AI Data Agent

A simple yet secure Text-to-SQL data assistant built using **Streamlit**, **Gemini 2.5 Flash**, and **Snowflake**. It allows anyone to ask questions about the database in plain English or Vietnamese and get clean data tables instantly, along with quick business summaries.

## ✨ What it does

* **Text-to-SQL**: No more writing manual SQL queries. Just type your question and let the agent handle the joins and aggregates.
* **Smart Memory**: Remembers up to 10 past chat turns so you can ask follow-up questions easily (e.g., "Who is our biggest customer?" followed by "Where do they live?").
* **Built-in Guardrails**: 
  * Automatically injects `LIMIT 1000` to prevent crashing the app when scanning huge tables.
  * Blocks any attempts to ask for non-existent columns (like SSN, personal emails) with a clean error message instead of hallucinating fake SQL.

## 🛠️ Setup & Credentials

This project uses a `.env` file to manage secrets securely. **Do not push your `.env` file to GitHub.**

### Local Configuration (`.env`)
Create a `.env` file in the root folder:

```env
GEMINI_API_KEY="your_api_key_here"

SNOWFLAKE_USER="your_user"
SNOWFLAKE_PASSWORD="your_password"
SNOWFLAKE_ACCOUNT="your_account_id"
SNOWFLAKE_WAREHOUSE="your_warehouse"
SNOWFLAKE_DATABASE="your_database"
SNOWFLAKE_SCHEMA="your_schema"

# Performance adjustments
CACHE_TTL_SECONDS=3600
MAX_QUERY_LIMIT=1000

