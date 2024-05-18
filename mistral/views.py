
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
PASSWORD = "Nfk6eckgfUx0jhTcPb_G"


# Function to extract context keywords from the prompt
def extract_context_from_prompt(prompt):
    stop_words = set(stopwords.words('english'))
    # Tokenize the prompt and filter out non-alphanumeric words and stopwords
    words = [word.lower() for word in word_tokenize(prompt) if word.isalnum() and word.lower() not in stop_words]
    
    # Extracting context keywords based on specific criteria
    context_keywords = [word for word in words ]  # Update to include all words in the context
    
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
# Function to retrieve rules based on a specific tag ignoring SSL verification
# Function to retrieve rules based on a specific context within the description field and matching tag
# def retrieve_rules_by_context(context, tag):
#     # Prepare the query to find similar context within the description field and filter by tag
#     query = {
#         "query": {
#             "bool": {
#                 "must": [
#                     {
#                         "match": {
#                            "description": {
#                                "query": context,
#                                "operator": "and"
#                             }
#                         }
#                     },
#                     {
#                         "match": {
#                             "tag": tag
#                         }
#                     }
#                 ]
#             }
#         }
#     }

#     # Send a POST request to Elasticsearch without SSL verification
#     response = requests.post(ELASTICSEARCH_URL, json=query, auth=HTTPBasicAuth(USERNAME, PASSWORD), verify=False)

#     # Check if the request was successful
#     if response.status_code == 200:
#         # Parse the response JSON and extract the relevant data
#         response_data = response.json()
#         rules = [hit['_source'] for hit in response_data.get('hits', {}).get('hits', [])]

#         # Check if any rules were found with non-matching tags
#         mismatched_rules = [rule for rule in rules if rule.get('tag') != tag]
        
#         if mismatched_rules:
#             error_message = f"Rules with mismatched tags found: {', '.join([rule['description'] for rule in mismatched_rules])}"
#             return {'error': error_message}
        
#         return rules
#     else:
#         return None




def calculate_similarity(embedding1, embedding2):
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


# # Function to match the prompt with rules descriptions and return the corresponding rule
# def match_prompt_with_rules(prompt, rules):
#     matched_rule = None
#     print(rules)
#     for rule in rules:
#         if prompt.lower() in rule['description'].lower():
#             print(rule)
#             matched_rule = rule
#             break
#     return matched_rule



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

            # # Find the rule that matches the context of the prompt in the descriptions
            # matched_rule = match_prompt_with_rules(prompt, rules)

            # if matched_rule is not None and matched_rule.get('tag') != tag:
            #     return JsonResponse({'error': 'You are not allowed to view this rule'}, status=403)

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

            # Return the transformed response along with the matched rule as JSON
            return JsonResponse( rules,safe=False,  status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
