
import os                               # Standard library to interact with the Operating System
import snowflake.connector              # Official Snowflake connector library
from dotenv import load_dotenv          # Library to load secret variables from .env file
from google import genai                # Google GenAI official SDK to communicate with Gemini

# Load environment variables from the .env file
load_dotenv()

# Initialize the Gemini AI client using the API Key stored safely in .env
api_key = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=api_key)

# Retrieve Snowflake credentials
SF_USER = os.getenv('SNOWFLAKE_USER')
SF_PASSWORD = os.getenv('SNOWFLAKE_PASSWORD')
SF_ACCOUNT = os.getenv('SNOWFLAKE_ACCOUNT')
SF_WAREHOUSE = os.getenv('SNOWFLAKE_WAREHOUSE')
SF_DATABASE = os.getenv('SNOWFLAKE_DATABASE')
SF_SCHEMA = os.getenv('SNOWFLAKE_SCHEMA')

# Establish a connection to the Snowflake database
ctx = snowflake.connector.connect(
    user=SF_USER, password=SF_PASSWORD, account=SF_ACCOUNT,
    warehouse=SF_WAREHOUSE, database=SF_DATABASE, schema=SF_SCHEMA
)
cs = ctx.cursor()

print("========================================================")
print("🤖 AI DATA AGENT IS READY TO CHAT WITH YOUR SNOWFLAKE!")
print("Type your question below. (Type 'exit' or 'quit' to stop)")
print("========================================================")

# Start an infinite loop to allow continuous typing in Terminal
while True:
    print("\n--------------------------------------------------------")
    user_question = input("Ask Snowflake: ")
    
    # Check if the user wants to terminate the program
    if user_question.lower() in ['exit', 'quit']:
        print("Goodbye! Closing agent session.")
        break
        
    # Skip empty inputs safely
    if not user_question.strip():
        continue

    # Define strict prompt rules for Gemini text-to-sql generation
    prompt = f"""
    You are an expert Data Engineer. Your job is to convert the user's natural language question into a valid Snowflake SQL query.
    The target table is called 'CUSTOMER' and it contains columns like 'C_NAME', 'C_MKTSEGMENT', 'C_PHONE', 'C_ACCTBAL', 'C_ADDRESS'.
    
    CRITICAL RULE: Return ONLY the raw SQL code string. Do NOT wrap it in markdown block formatting like ```sql.
    
    User Question: {user_question}
    """

    try:
        print("Gemini is thinking & generating SQL...")
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        generated_sql = response.text.strip()
        print(f"Generated SQL:\n[ {generated_sql} ]")
        
        print("Executing on Snowflake...")
        cs.execute(generated_sql)
        
        # NEW: Dynamically fetch column names from the SQL cursor description
        columns = [col[0] for col in cs.description]
        results = cs.fetchall()
        
        print("\n--- Final Results from Snowflake ---")
        if not results:
            print("No data found for this query.")
        else:
            # Print headers nicely
            print(" | ".join(columns))
            print("-" * (len(" | ".join(columns)) + 4))
            # Print row results dynamically based on what columns the AI selected
            for row in results:
                print(" | ".join(str(item) for item in row))

    except Exception as e:
        print(f" An error occurred: {e}")

# Clean up and close connections safely after exiting the loop
cs.close()
ctx.close()
print("Database session closed safely.")