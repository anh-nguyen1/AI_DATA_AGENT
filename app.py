import os
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv
from google import genai

# Setup page config for Streamlit
st.set_page_config(page_title="Snowflake AI Data Agent", page_icon="🤖", layout="wide")

# Load credentials
load_dotenv()

# Initialize Gemini Client
@st.cache_resource
def get_ai_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize Snowflake Connection
@st.cache_resource
def get_snowflake_cursor():
    ctx = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA')
    )
    return ctx, ctx.cursor()

try:
    ai_client = get_ai_client()
    ctx, cs = get_snowflake_cursor()
except Exception as e:
    st.error(f"Failed to connect to databases/AI: {e}")
    st.stop()

# --- WEB UI INTERFACE ---
st.title("🤖 Snowflake AI Data Agent")
st.caption("Ask questions in plain English, and the AI will fetch data directly from Snowflake!")

# Text input for user query
user_question = st.text_input("💬 Ask your database:", placeholder="e.g., Show me 3 customers from the AUTOMOBILE segment")

if user_question:
    with st.spinner("🤔 Gemini is thinking & generating SQL..."):
        prompt = f"""
        You are an expert Data Engineer. Your job is to convert the user's natural language question into a valid Snowflake SQL query.
        The target table is called 'CUSTOMER' and it contains columns like 'C_NAME', 'C_MKTSEGMENT', 'C_PHONE', 'C_ACCTBAL', 'C_ADDRESS'.
        
        CRITICAL RULE: Return ONLY the raw SQL code string. Do NOT wrap it in markdown block formatting like ```sql.
        
        User Question: {user_question}
        """
        try:
            # Call AI
            response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            generated_sql = response.text.strip()
            
            # Display generated SQL in an expander box
            with st.expander("👉 View Generated SQL Code"):
                st.code(generated_sql, language="sql")
            
            # Execute on Snowflake
            cs.execute(generated_sql)
            columns = [col[0] for col in cs.description]
            results = cs.fetchall()
            
            # Display Results
            st.success("⚡ Data fetched successfully!")
            if not results:
                st.warning("No records found.")
            else:
                # Map results to a clean table layout
                import pandas as pd
                df = pd.DataFrame(results, columns=columns)
                st.dataframe(df, use_container_width=True)
                
        except Exception as e:
            st.error(f"An error occurred: {e}")