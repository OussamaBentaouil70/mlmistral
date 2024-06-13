import json
import requests
from requests.auth import HTTPBasicAuth
from django.http import JsonResponse, HttpResponse
from pymongo import MongoClient
import os
import uuid
import urllib3
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage

from mistral.views import extract_token_from_headers

# Suppress only the single InsecureRequestWarning from urllib3 needed in this context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Define the Elasticsearch endpoint and index name
ELASTICSEARCH_URL = 'https://localhost:9200/'
INDEX_NAME = 'rules_index'

# Define the authentication credentials for Elasticsearch
USERNAME = 'elastic'
PASSWORD = 'Nfk6eckgfUx0jhTcPb_G'

# Connect to MongoDB Atlas
client = MongoClient("mongodb+srv://oussama:oussama@cluster0.043id4v.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client['rule_mining']


@csrf_exempt
def create_index_with_mapping(request):
    headers = {'Content-Type': 'application/json'}
    index_mapping = {
        "mappings": {
            "properties": {
                "name": {"type": "text"},
                "description": {"type": "text"},
                "tag": {"type": "keyword"}
            }
        }
    }
    response = requests.put(
        ELASTICSEARCH_URL + INDEX_NAME,
        json=index_mapping,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
        headers=headers,
        verify=False
    )
    
    if response.status_code == 200:
        return JsonResponse({'message': f"Index '{INDEX_NAME}' created successfully."})
    else:
        return JsonResponse({'error': f"Failed to create index '{INDEX_NAME}'. Status code: {response.status_code}", 'details': response.text}, status=400)



@csrf_exempt
@extract_token_from_headers
def upload_file(request):
    if request.method == 'POST' and request.FILES['file']:
        file = request.FILES['file']
        fs = FileSystemStorage()
        filename = fs.save(file.name, file)
        file_path = fs.path(filename)
        extracted_data = extract_data_from_file(file_path)
        
        if not extracted_data:
            return JsonResponse({'error': "No data extracted from the file."}, status=400)

        save_to_mongodb(extracted_data)
        index_to_elasticsearch(extracted_data)

        return JsonResponse({'message': "File uploaded and data indexed successfully."})
    return JsonResponse({'error': 'Invalid request method or no file uploaded'}, status=405)



@csrf_exempt
@extract_token_from_headers
def search_rules(request):
    if request.method == 'POST':
        user = request.user
        tag = user.get('tag', '')
        print(tag)
        rules = search_in_elasticsearch(tag)
        return JsonResponse(rules, safe=False)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


 
@csrf_exempt
@extract_token_from_headers
def generate_brl_files(request):
    if request.method == 'POST':
        user = request.user
        tag = user.get('tag', '')
        rules = search_in_elasticsearch(tag)
        if rules:
            directory = f"Rules_{tag}"
            for rule in rules:
                generate_brl_file(rule, directory)
            return JsonResponse({'message': f"BRL files generated in {directory}"})
        return JsonResponse({'message': 'No rules found for the given tag'}, status=404)
    return JsonResponse({'error': 'Invalid request method'}, status=405)



# Helper functions
def extract_data_from_file(file_path):
    extracted_data = []
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for i in range(0, len(lines), 3):
            if len(lines[i].split(': ')) >= 2 and len(lines) > i + 1:
                name = lines[i].split(': ')[1].strip()
                description = lines[i + 1].split(': ')[1].strip()
                extracted_data.append({'name': name, 'description': description, 'tag': os.path.basename(file_path).split('.')[0]})
            else:
                print(f"Skipping malformed data at line {i} in the input file.")
    return extracted_data



# Save extracted data to MongoDB with collection named Rule_<tag>
def save_to_mongodb(data):
    for item in data:
        collection_name = f"Rule_{item['tag']}"
        collection = db[collection_name]
        collection.insert_one(item)



# Index the extracted data to Elasticsearch
def index_to_elasticsearch(data):
    headers = {'Content-Type': 'application/json'}
    bulk_data = ""
    
    for item in data:
        item.pop('_id', None)  # Remove the _id field before indexing
        
        # Create the request body for indexing
        action = {
            "index": {
                "_index": INDEX_NAME,
                "_id": item["name"]
            }
        }
        
        bulk_data += json.dumps(action) + "\n" + json.dumps(item) + "\n"

    # Make a POST request to index the data
    response = requests.post(
        ELASTICSEARCH_URL + "_bulk",
        data=bulk_data,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
        headers=headers,
        verify=False
    )

    if response.status_code == 200:
        print(f"Data indexed successfully.")
    else:
        print(f"Failed to index data. Status code: {response.status_code}")
        print(response.text)  # Print response content for further investigation



# Search for rules in Elasticsearch based on the tag
def search_in_elasticsearch(tag):
    headers = {'Content-Type': 'application/json'}
    query = {
        "query": {
            "match": {
                "tag": tag
            }
        }
    }

    # Send a POST request to Elasticsearch with basic authentication
    response = requests.post(
        ELASTICSEARCH_URL + INDEX_NAME + "/_search",
        json=query,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
        headers=headers,
        verify=False
    )

    # Check if the request was successful       
    if response.status_code == 200:
        # Parse the response JSON and extract the relevant data
        response_data = response.json()
        rules = [{'name': hit['_source']['name'], 'description': hit['_source']['description']} for hit in response_data.get('hits', {}).get('hits', [])]
        return rules
    else:
        print(f"Failed to search in index. Status code: {response.status_code}")
        print(response.text)
        return []



# Generate a BRL file for a rule
def generate_brl_file(rule, directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

    file_name = os.path.join(directory, rule['name'].replace(" ", "_") + ".brl")
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ilog.rules.studio.model.brl:ActionRule xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:ilog.rules.studio.model.brl="http://ilog.rules.studio/model/brl.ecore">
  <name>{rule['name']}</name>
  <uuid>{uuid.uuid4()}</uuid>
  <locale>en_US</locale>
  <definition><![CDATA[{rule['description']}]]></definition>
</ilog.rules.studio.model.brl:ActionRule>"""

    with open(file_name, 'w') as file:
        file.write(xml_content)
    print(f"Generated BRL file: {file_name}")
