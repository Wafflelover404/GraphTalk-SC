import re

def split_into_paragraphs(text, max_paragraph_length=200):
    """
    Splits a large text into paragraphs based on:
    1. Existing double line breaks
    2. Sentence boundaries when text is too long
    3. Maintains list items and other formatting
    """
    # First split by existing double line breaks
    paragraphs = re.split(r'\n\s*\n', text.strip())
    
    # Further process paragraphs that are still too long
    processed_paragraphs = []
    for paragraph in paragraphs:
        if len(paragraph) > max_paragraph_length:
            # Split at sentence boundaries (after .!? followed by space and capital)
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZА-Я])', paragraph)
            current_paragraph = ""
            
            for sentence in sentences:
                if len(current_paragraph) < max_paragraph_length:
                    processed_paragraphs.append(current_paragraph.strip())
                    current_paragraph = sentence
                else:
                    if current_paragraph:
                        current_paragraph += " " + sentence
                    else:
                        current_paragraph = sentence
            
            if current_paragraph:
                processed_paragraphs.append(current_paragraph.strip())
        else:
            processed_paragraphs.append(paragraph.strip())
    
    return processed_paragraphs

# Example usage
if __name__ == "__main__":
    # Read input from file
    input_file = "input.txt"
    output_file = "output.txt"  
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            input_text = f.read()
        
        # Split into paragraphs
        formatted_paragraphs = split_into_paragraphs(input_text)
        
        # Save the result to output file
        with open(output_file, "w", encoding="utf-8") as f:
            for paragraph in formatted_paragraphs:
                print(
                    f"""
                    {paragraph}

                    -----------

                    """
                )
        
        print(f"Successfully processed text. Output saved to {output_file}")
    
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")   