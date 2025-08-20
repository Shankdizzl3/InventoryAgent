import ollama

def chat_with_llama3(prompt_text):
    """
    Sends a prompt to the locally running llama3 model via Ollama
    and prints the response.
    """
    print(f"Sending prompt to llama3: '{prompt_text}'")
    try:
        # Call the Ollama API. The default model is llama3 if not specified.
        # You can explicitly set it with model='llama3'
        response = ollama.chat(model='llama3', messages=[
            {
                'role': 'user',
                'content': prompt_text,
            },
        ])
        # Extract the content from the response
        generated_text = response['message']['content']
        print("\nResponse from llama3:")
        print(generated_text)
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure Ollama is running and the 'llama3' model is available.")

if __name__ == "__main__":
    # Example prompt
    user_prompt = "Explain the concept of a 'token' in large language models in simple terms."
    chat_with_llama3(user_prompt)

    # You can try another prompt
    # user_prompt_2 = "Write a very short, cheerful poem about a cat."
    # chat_with_llama3(user_prompt_2)
