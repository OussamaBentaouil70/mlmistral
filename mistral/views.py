from dotenv import load_dotenv
load_dotenv() ## loading all the environment variables
from urllib.request import HTTPBasicAuthHandler
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
from requests.auth import HTTPBasicAuth
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import torch
from sentence_transformers import SentenceTransformer
import os

nltk.download('punkt')
nltk.download('stopwords')
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
# Define the URL of the Mistral API
OLLAMA_MISTRAL_API_URL = "http://localhost:11434/api/generate"
# Define the name of the model to be used
MODEL_NAME = "mistral"

# Define the URL of the Elasticsearch database
ELASTICSEARCH_URL = "https://localhost:9200/rules/_search"
USERNAME = "elastic"
PASSWORD = os.getenv('ELASTIC_PASSWORD')



# Function to extract context keywords from the prompt
def extract_context_from_prompt(prompt):
    stop_words = set(stopwords.words('english'))
    # Tokenize the prompt and filter out non-alphanumeric words and stopwords
    words = [word.lower() for word in word_tokenize(prompt) if word.isalnum() and word.lower() not in stop_words]
    
    # Extracting context keywords based on specific criteria
    context_keywords = [word for word in words ]  
    
    return ' '.join(context_keywords)

# Function to transform text by removing newlines, backslashes, and joining words
def transform_text(input_text):
    transformed_text = input_text.replace('\n', ' ')
    transformed_text = transformed_text.replace('\\', '')
    transformed_text = re.sub(r'([A-Za-z]+)\s([A-Za-z]+)', r'\1\2', transformed_text)
    return transformed_text

# Function to retrieve rules based on a specific tag from the Elasticsearch database
def retrieve_rules_by_tag(tag):
    # Prepare the query to retrieve rules based on the tag
    query = {
        "query": {
            "match": {
                "tag": tag
            }
        }
    }

    # Send a POST request to Elasticsearch with basic authentication
    response = requests.post(ELASTICSEARCH_URL, json=query, auth=HTTPBasicAuth(USERNAME, PASSWORD),  verify=False)

    # Check if the request was successful   
    if response.status_code == 200:
        # Parse the response JSON and extract the relevant data
        response_data = response.json()
        rules = [{'name': hit['_source']['name'], 'description': hit['_source']['description']} for hit in response_data.get('hits', {}).get('hits', [])]
        return rules
    else:
        return None


# Function to calculate the cosine similarity between two embeddings
def calculate_similarity(embedding1, embedding2):
      # cosine_similarity returns a tensor, so we extract the value using item() and return it as a float value
      # tensor is a multi-dimensional matrix containing elements of a single data type.
    similarity_score = torch.nn.functional.cosine_similarity(embedding1.unsqueeze(0), embedding2.unsqueeze(0)).item()
   
    return similarity_score



def retrieve_rule_by_similarity(prompt, tag):
    # Prepare the query to filter rules by tag
    query = {
        "query": {
            "match": {
                "tag": tag
            }
        }
    }

    # Send a POST request to Elasticsearch without SSL verification to get rules by tag
    response = requests.post(ELASTICSEARCH_URL, json=query, auth=HTTPBasicAuth(USERNAME, PASSWORD), verify=False)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response JSON and extract the relevant data
        response_data = response.json()
        rules_by_tag = [hit['_source'] for hit in response_data.get('hits', {}).get('hits', [])]

        max_similarity = 0
        best_matched_rule = None

        # Compare rules descriptions with the prompt and find the most similar rule
        for rule in rules_by_tag:
            doc1_embedding = model.encode(prompt, convert_to_tensor=True)
            doc2_embedding = model.encode(rule.get('description', ''), convert_to_tensor=True)
            similarity_score = calculate_similarity(doc1_embedding, doc2_embedding)

            if similarity_score > max_similarity:
                max_similarity = similarity_score
                best_matched_rule = rule

        return best_matched_rule

    return None




# View to generate text using Mistral API and retrieve rules based on a tag matching the prompt
@csrf_exempt
def generate_text(request):
    if request.method == 'POST':
        try:
            # Parse the JSON data from the request body
            data = json.loads(request.body.decode('utf-8'))
            prompt = data.get('prompt')
            tag = data.get('tag')  # Extract the tag from the request

            if not prompt:
                return JsonResponse({'error': 'Missing prompt'}, status=400)
            
            context = extract_context_from_prompt(prompt)
            print(context)
            print(tag)
            #TODO: Add more phrases to identify rule-related prompts
            phrases = ["give rules", "rules"]

            if any(phrase in context.lower() for phrase in phrases):
             rules = retrieve_rules_by_tag(tag)
            else:
             # Retrieve rules based on the context of the prompt from the Elasticsearch database
                # rules = retrieve_rules_by_context(context, tag)
                rules = retrieve_rule_by_similarity(prompt, tag)
            

            if not rules:
                return JsonResponse({'error': 'You are not allowed to view this rule'}, status=500)


            # Prepare payload for the Mistral API request
            payload = {
                'model': MODEL_NAME,
                'prompt': prompt
            }

            # Send a POST request to the Mistral API
            response = requests.post(OLLAMA_MISTRAL_API_URL, json=payload, stream=True)

            if response.status_code != 200:
                return JsonResponse({'error': f'API request failed with status code {response.status_code}'}, status=500)

        
            return JsonResponse( rules,safe=False,  status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)


# View to generate text using Mistral API and retrieve rules based on a tag matching the prompt
@csrf_exempt
def get_response_from_prompt(request):
    if request.method == 'POST':
        try:
            # Parse the JSON data from the request body
            data = json.loads(request.body.decode('utf-8'))
            prompt = data.get('prompt')

            if not prompt:
                return JsonResponse({'error': 'Missing prompt'}, status=400)
            
            # Prepare payload for the Mistral API request
            payload = {
                'model': MODEL_NAME,
                'prompt': prompt
            }

            # Send a POST request to the Mistral API
            response = requests.post(OLLAMA_MISTRAL_API_URL, json=payload, stream=True)

            if response.status_code != 200:
                return JsonResponse({'error': f'API request failed with status code {response.status_code}'}, status=500)

            # Combine the response lines into a single string
            combined_response = ''
            for line in response.iter_lines():
                if line:
                    response_data = json.loads(line)
                    combined_response += response_data['response'] + ' '

            transformed_response = transform_text(combined_response)

            # Return the transformed response as JSON
            return JsonResponse({'response': transformed_response}, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
