import os
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv
from google import genai
import pandas as pd

# Setup page config for Streamlit
st.set_page_config(page_title="Snowflake AI Data Agent", page_icon="🤖", layout="wide")

# Load environment variables from the .env file
load_dotenv()

# Initialize the Gemini AI client using the API Key stored safely in .env
@st.cache_resource
def get_ai_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Establish a connection to the Snowflake database
@st.cache_resource
def get_snowflake_connection():
    return snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA')
    )
#cache schema to prevent repetitive disk queries and speed up performance
@st.cache_data(ttl=3600) 
def fetch_database_schema():
    ctx_temp = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA')
    )
    cs = ctx_temp.cursor()
    db_name = os.getenv('SNOWFLAKE_DATABASE')
    schema_name = os.getenv('SNOWFLAKE_SCHEMA')

    cs.execute(f"""
        SELECT table_name, column_name 
        FROM {db_name}.INFORMATION_SCHEMA.COLUMNS 
        WHERE table_schema = '{schema_name}'
        ORDER BY table_name, ordinal_position;
    """)
    metadata_results = cs.fetchall()
    cs.close()
    ctx_temp.close()

    db_structure = ""
    current_table = ""
    for row in metadata_results:
        table_name, column_name = row[0], row[1]
        if table_name != current_table:
            db_structure += f"\n- Table '{table_name}' has columns: "
            current_table = table_name
        db_structure += f"'{column_name}', "
    return db_structure

try:
    ai_client = get_ai_client()
    ctx = get_snowflake_connection()
    #pre-load the schema infor into memory cache
    db_structure = fetch_database_schema()
except Exception as e:
    st.error(f"Failed to connect to databases/AI: {e}")
    st.stop()

# Streamlit runs linearly on user actions; session_state ensures memory persistence across runs
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/snowflake.png", width=100)
    st.markdown("### 🛠️ Agent Control Panel")
    #Display the current size pf tyhe sliding history window
    history_len = len(st.session_state.chat_history)
    st.metric(label="Context Buffer Size", value=f"{history_len}/10")

    if st.button("🗑️ Clear Chat Context", use_container_width=True):
        st.session_state.chat_history = []
        st.success("Chat History cleared!")
        st.rern()
    
    st.markdown("---")
    st.markdown("🔒 **Security Mode:** Guardrails Active\n⚡ **Caching:** Enabled")

#Main UI interface
st.title("🤖 Snowflake AI Data Agent")
st.caption("Ask questions in plain English or Vietnamese, and the AI will fetch data dynamically from Snowflake!")

# Text input for user query
user_question = st.text_input("💬 Ask your database:", placeholder="e.g., Show me the top 3 orders with the highest total price")

if user_question:
    with st.spinner("🔍 Fetching database layout & thinking..."):
        try:
            db_name = os.getenv('SNOWFLAKE_DATABASE')
            schema_name = os.getenv('SNOWFLAKE_SCHEMA')
            #Limits input history token count and keeps context window clean for Gemini AI
            limited_history = st.session_state.chat_history[-10] if st.session_state.chat_history else []
            
            # Compile past conversational history strings to supply contextual references for Gemini
            history_context = ""
            if limited_history:
                history_context = "\nHere is the ongoing conversation history for context (Max 10 turns):\n"
                for chat in limited_history:
                    history_context += f"User: {chat['user']}\nAI Generated SQL: {chat['sql']}\n"
     
            # 2. Construct dynamic prompt embedding the retrieved db_structure and contextual history
            prompt = f"""
            You are an expert Data Engineer specializing in Snowflake. Your job is to convert the user's natural language question into a valid Snowflake SQL query.
            
            Here is the dynamic database schema layout provided directly from Snowflake metadata (Database: {db_name}, Schema: {schema_name}):
            {db_structure}
            
            {history_context}
            
            CRITICAL RULES:
            1. Return ONLY the raw SQL code string. Do NOT wrap it in markdown block formatting like ```sql or ```.
            2. Do NOT include any conversational text, explanations, intro, or outro.
            3. Always use fully qualified table paths in the query (e.g., {db_name}.{schema_name}.TABLE_NAME) to guarantee execution success.
            4. IMPORTANT FOR FOLLOW-UP QUESTIONS: If the user asks a follow-up question referencing previous data, schema, combine, join, or modify the previous SQL logic if applicable.
            5. If the user asks to list all data, dump a table, or if the query could potentially return massive rows, you MUST FORCEFULLY APPEND A 'LIMIT 1000' clause at the end of the SQL query. NEVER allow a query to fetch millions of records unfiltered.
            
            STRICT ANTI-HALLUCINATION GUARDRAILS:
            6. If the user asks for information, columns, or concepts that DO NOT exist in the provided schema (e.g., SSN, email, etc.), you MUST NOT fake, guess, or map them to unrelated columns (like mapping SSN to ID, or Email to Phone). In this case, strictly return exactly this string: "ERROR: Requested data does not exist in the schema."
            7. If the user's question is ambiguous (e.g., "highest amount of money" without specifying account balance or order total), prioritize the most logical column in the customer context (e.g., C_ACCTBAL) but do not invent new column names.
            
            User Question: {user_question}
            """
            
            # 3. Request Gemini to generate the executable SQL query
            response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            generated_sql = response.text.strip()

            # Hardcoded python fallback safety check to inject LIMIT if the AI fails to follow instructions
            if "LIMIT" not in generated_sql.upper() and "SELECT" in generated_sql.upper():
                if "COUNT(" not in generated_sql.upper():
                    generated_sql = generated_sql.rstrip(';') + " LIMIT 1000;"
            
            # --- ANTI-HALLUCINATION GUARDRAIL CHECK ---
            # Break pipeline early if conversational text triggers the predefined guardrail error phrase
            if "ERROR: Requested data does not exist in the schema." in generated_sql:
                st.error("⚠️ Requested data components or concepts do not exist in the database schema.")
                st.stop()
            
            # Display the generated SQL statement inside an interactive expander
            with st.expander("👉 View Generated SQL Code"):
                st.code(generated_sql, language="sql")
            
            # 4. Execute the generated SQL statement on Snowflake
            cs = ctx.cursor()
            cs.execute(generated_sql)
            columns = [col[0] for col in cs.description]
            query_results = cs.fetchall()
            cs.close() # Close cursor session immediately after use
            
            # 5. Render query results on the Streamlit Web Interface
            st.success("⚡ Data fetched successfully!")
            if not query_results:
                st.warning("No records found.")
                current_insight = "No records were returned from the database for this specific query."
                df_summary = None
            else:
                df = pd.DataFrame(query_results, columns=columns)
                st.dataframe(df, use_container_width=True)
                # Extract sample rows as metadata for insight prompt
                df_summary = df.head(5).to_string() 

                with st.spinner("🤖 Generating data insights..."):
                    insight_prompt = f"""
                    You are a professional business data analyst. Based on the user's question: '{user_question}' 
                    and the actual data results returned from the database (showing a preview of the data):
                    {df_summary}
                    
                    Provide a concise summary or business explanation of the result in plain English or Vietnamese (matching the user's input language). 
                    Keep it under 3 sentences. Do not mention technical terms like SQL, dataframe, rows, or database.
                    """
                    insight_response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=insight_prompt)
                    current_insight = insight_response.text.strip()
                    st.info(f"💡 **AI Insight:** {current_insight}")

                st.session_state.chat_history.append({
                    "user": user_question,
                    "sql": generated_sql,
                    "insight": current_insight
                })
                
        except Exception as e:
            st.error(f"An error occurred: {e}")
    
    #Print chat history on the screen
    if st.session_state.chat_history:
        st.markdown("---")
        st.subheader("📜 Conversation History")

        for idx, chat in enumerate(reversed(st.session_state.chat_history)):
            with st.chat_message("user"):
                st.write(chat["user"])
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(f"**Explanation:** {chat['insight']}")
                with st.expander("Show Generated SQL"):
                    st.code(chat["sql"], language="sql")

