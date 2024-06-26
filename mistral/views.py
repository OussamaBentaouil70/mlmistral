from django.conf import settings
from dotenv import load_dotenv
import jwt
load_dotenv() ## loading all the environment variables
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
from rest_framework.decorators import api_view
from .models import Owner, Member
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password

nltk.download('punkt')
nltk.download('stopwords')
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
# Define the URL of the Mistral API
OLLAMA_MISTRAL_API_URL = "http://localhost:11434/api/generate"
# Define the name of the model to be used
MODEL_NAME = "mistral"

# Define the URL of the Elasticsearch database
ELASTICSEARCH_URL = "https://localhost:9200/rules_index/_search"
USERNAME = "elastic"
PASSWORD = os.getenv('ELASTIC_PASSWORD')



def extract_token_from_headers(view_func):
    def _wrapped_view(request, *args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return JsonResponse({'error': 'Token not provided'}, status=401)

        try:
            decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            request.user = decoded
        except jwt.ExpiredSignatureError:
            return JsonResponse({'error': 'Token has expired'}, status=401)
        except jwt.InvalidTokenError:
            return JsonResponse({'error': 'Invalid token'}, status=400)

        return view_func(request, *args, **kwargs)

    return _wrapped_view


User = get_user_model()

def get_user_model(role):
    return Owner if role == 'owner' else Member






@csrf_exempt
def register_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            username = data.get('username')
            full_name = data.get('full_name')
            email = data.get('email')
            password = data.get('password')
            address = data.get('address')
            bio = data.get('bio')
            tag = data.get('tag')
            role = data.get('role')
            

            if not username:
                return JsonResponse({'error': 'Username is required'}, status=400)

            Model = get_user_model(role)
            if Model.objects.filter(username=username).exists():
                return JsonResponse({'error': 'Username already exists'}, status=400)

            if not password or len(password) < 6:
                return JsonResponse({'error': 'Password is required and should be at least 6 characters long'}, status=400)

            if not email:
                return JsonResponse({'error': 'Email is required'}, status=400)

            if Model.objects.filter(email=email).exists():
                return JsonResponse({'error': 'Email already exists'}, status=400)

            hashed_password = make_password(password)

            new_user = Model.objects.create(
                username=username,
                email=email,
                password=hashed_password,
                role=role,
                full_name=full_name,
                address=address,
                bio=bio,
                tag=tag
            )

            return JsonResponse({
                'username': new_user.username, 
                'email': new_user.email, 
                'role': new_user.role, 
                'full_name': new_user.full_name,
                'address': new_user.address,
                'bio': new_user.bio,
                'tag': new_user.tag
                }, status=201)
        except Exception as e:
            print("Error while registering user", e)
            return JsonResponse({'error': 'Internal server error'}, status=500)

@csrf_exempt
def login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                return JsonResponse({'error': 'Email and password are required'}, status=400)

            user = Member.objects.filter(email=email).first() or Owner.objects.filter(email=email).first()

            if not user or not check_password(password, user.password):
                return JsonResponse({'error': 'Invalid email or password'}, status=400)

            token_payload = {
                "username": user.username,
                 "fullname": user.full_name,
                'email': user.email,
                "tag": user.tag,
                "role": user.role,
                "address": user.address,
                "bio": user.bio
            }

            token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm='HS256')

            response_data = {
                'token': token,
                'user': {
                    "username": user.username,
                    "fullname": user.full_name,
                    "address": user.address,
                    "bio": user.bio,
                    'tag': user.tag,
                    'email': user.email,
                    'role': user.role,
                    
                }
            }

            response = JsonResponse(response_data)
            response.set_cookie('token', token, httponly=True)
            
            return response
        except Exception as e:
            print("Error while logging in user", e)
            return JsonResponse({'error': 'Internal server error'}, status=500)





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
@extract_token_from_headers
def generate_text(request):
    user = request.user
    print(user)
    if request.method == 'POST':
        try:
            # Parse the JSON data from the request body
            data = json.loads(request.body.decode('utf-8'))
            prompt = data.get('prompt')
            tag = user.get("tag")  # Extract the tag from the request
            print(tag)
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
@extract_token_from_headers
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


