from django.shortcuts import render
from django.http import JsonResponse
# prevent unauthorized POST requests from malicious websites.
from django.views.decorators.csrf import csrf_exempt
# for making HTTP requests
import requests
# for working with JSON data
import json
#used for working with regular expressions
import re

# Define the URL of the Mistral API
OLLAMA_MISTRAL_API_URL = "http://localhost:11434/api/generate"
# Define the name of the model to be used
MODEL_NAME = "mistral"

# Function to transform text by removing newlines, backslashes, and joining words
def transform_text(input_text):
    transformed_text = input_text.replace('\n', ' ')
    transformed_text = transformed_text.replace('\\', '')
    transformed_text = re.sub(r'([A-Za-z]+)\s([A-Za-z]+)', r'\1\2', transformed_text)
    return transformed_text


# View to generate text using Mistral API
@csrf_exempt
def generate_text(request):
    if request.method == 'POST':
        try:
            # Parse the JSON data from the request body
            data = json.loads(request.body.decode('utf-8'))
            prompt = data.get('prompt')
            
            # Check if 'prompt' is missing in the request
            if not prompt:
                return JsonResponse({'error': 'Missing prompt'}, status=400)

            # Prepare payload for the API request
            payload = {
                'model': MODEL_NAME,
                'prompt': prompt
            }

            # Send a POST request to the Mistral API
            response = requests.post(OLLAMA_MISTRAL_API_URL, json=payload, stream=True)

            # Check if the API request was successful
            if response.status_code != 200:
                return JsonResponse({'error': f'API request failed with status code {response.status_code}'}, status=500)

            # Combine the response lines into a single string
            combined_response = ''
            for line in response.iter_lines():
                if line:
                    response_data = json.loads(line)
                    combined_response += response_data['response'] + ' '
            # Transform the combined response text
            transformed_response = transform_text(combined_response)
            print('after transformed : ' + transformed_response)
            # Return the transformed response as JSON
            return JsonResponse({'response': transformed_response.strip()}, status=200)

        except Exception as e:
            # Return an error response if an exception occurs
            return JsonResponse({'error': str(e)}, status=500)
    else:
        # Return an error response for non-POST requests
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)