import os
import asyncio
import json
import re
from google import genai
from separator import split_into_paragraphs

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    

async def llm_json_interpret(text: str) -> dict | str:

    with open("docs/en/json-prompt.md", "r", encoding="utf-8") as f:
        system_prompt_standard = f.read()
    
    system_prompt = ( f"""
        JSON standard converter description:
        {system_prompt_standard}

        Instructions:
        You are a strict JSON generator. 
        Respond ONLY with valid JSON. No explanations or extra text. JSON MUST ALWAYS BE IN THE SAME LANGUAGE AS THE INPUT TEXT, NO EXCEPTIONS, ALL NODES, CONNECTIONS, ETC. IN SAME LANGUAGE INPUT. 

    """)

    contents = [
        system_prompt,
        text
    ]

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )
        collected = response.text

        print("=== Raw LLM output ===")
        print(collected)
        print("=====================")

        # Try to extract JSON from ```json ... ``` block or fallback to full text
        match = re.search(r"```json\s*(\{.*?\})\s*```", collected, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = collected

        return json.loads(json_str)

    except Exception as e:
        print("Exception:", e)
        return str(e)



async def large_text_convertion (text: str):
        paragraphs_json = []
        paragraphs = split_into_paragraphs(text)
        for paragraph in paragraphs:
            print(f"{paragraph}\n\n-----------\n\n")
            paragraph_json = await llm_json_interpret(paragraph)
            paragraph_json.append(paragraph_json)

async def main():
    sample_text = """
    Create a JSON object describing a book with these fields:
    title: "The Great Gatsby",
    author: "F. Scott Fitzgerald",
    year: 1925,
    genres: ["Novel", "Historical"]
    """
    result = await llm_json_interpret(sample_text)
    print("\n=== Parsed JSON Result ===")
    print(result)
if __name__ == "__main__":
    asyncio.run(main())
