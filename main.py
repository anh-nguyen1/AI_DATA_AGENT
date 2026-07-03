
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

    try:
        print("🔍 Fetching database layout from Snowflake...")
        
        # 1. Dynamically retrieve database schema layout from Snowflake INFORMATION_SCHEMA
        cs.execute(f"""
            SELECT table_name, column_name 
            FROM {SF_DATABASE}.INFORMATION_SCHEMA.COLUMNS 
            WHERE table_schema = '{SF_SCHEMA}'
            ORDER BY table_name, ordinal_position;
        """)
        metadata_results = cs.fetchall()
        
        # Format raw database metadata into a structured list string
        db_structure = ""
        current_table = ""
        for row in metadata_results:
            table_name, column_name = row[0], row[1]
            if table_name != current_table:
                db_structure += f"\n- Table '{table_name}' has columns: "
                current_table = table_name
            db_structure += f"'{column_name}', "

        print("🤔 Gemini is thinking & generating SQL...")
        
        # 2. Construct dynamic prompt embedding the retrieved db_structure for Gemini
        prompt = f"""
            You are an expert Data Engineer specializing in Snowflake. Your job is to convert the user's natural language question into a valid Snowflake SQL query.
            
            Here is the dynamic database schema layout provided directly from Snowflake metadata (Database: {db_name}, Schema: {schema_name}):
            {db_structure}
            
            CRITICAL RULES:
            1. Return ONLY the raw SQL code string. Do NOT wrap it in markdown block formatting like ```sql or ```.
            2. Do NOT include any conversational text, explanations, intro, or outro.
            3. Even if the user asks in Vietnamese or format their question informally, you must ONLY output the final executable SQL statement.
            4. Always use fully qualified table paths in the query (e.g., {db_name}.{schema_name}.TABLE_NAME) to guarantee execution success.
            
            STRICT ANTI-HALLUCINATION GUARDRAILS:
            5. If the user asks for information, columns, or concepts that DO NOT exist in the provided schema (e.g., SSN, email, etc.), you MUST NOT fake, guess, or map them to unrelated columns (like mapping SSN to ID, or Email to Phone). In this case, strictly return exactly this string: "ERROR: Requested data does not exist in the schema."
            6. If the user's question is ambiguous (e.g., "highest amount of money" without specifying account balance or order total), prioritize the most logical column in the customer context (e.g., C_ACCTBAL) but do not invent new column names.
            
            User Question: {user_question}
            """

        # 3. Request Gemini to generate the executable SQL query
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        generated_sql = response.text.strip()
        print(f"Generated SQL:\n[ {generated_sql} ]")
        
        # 4. Execute the generated SQL statement on Snowflake
        print("Executing on Snowflake...")
        cs.execute(generated_sql)
        
        # Dynamically fetch column names from the SQL cursor description
        columns = [col[0] for col in cs.description]
        results = cs.fetchall()
        
        # 5. Print out the structured results table onto the Terminal screen
        print("\n--- Final Results from Snowflake ---")
        if not results:
            print("No data found for this query.")
        else:
            # Print headers nicely with custom separators
            print(" | ".join(columns))
            print("-" * (len(" | ".join(columns)) + 4))
            # Print row results dynamically based on what columns the AI selected
            for row in results:
                print(" | ".join(str(item) for item in row))

    except Exception as e:
        print(f"❌ An error occurred: {e}")

# Clean up and close connections safely after exiting the loop
cs.close()
ctx.close()
print("Database session closed safely.")