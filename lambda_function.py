import requests
from urllib.parse import parse_qs, unquote
import boto3
import json
import re

OPENAI_API_KEY="apikey"

def read_file_from_s3(bucket_name, key):
    """
    Read and return the content of a file from an S3 bucket.

    Args:
    bucket_name (str): Name of the S3 bucket.
    key (str): The key of the file in the S3 bucket (file path in the bucket).

    Returns:
    str: Content of the file as a string, or None if an error occurs.
    """
    # Create an S3 client
    s3 = boto3.client('s3')

    try:
        # Fetch the file object
        response = s3.get_object(Bucket=bucket_name, Key=key)
        print(response)
        # Read the file's content
        content = response['Body'].read().decode('utf-8')

        return content
    except Exception as e:
        print(f"An error occurred: {e}")
        return ""

def write_to_s3(bucket_name, file_name, data):
    """
    Write data to a file in an S3 bucket.

    Args:
    bucket_name (str): Name of the S3 bucket.
    file_name (str): File path in the S3 bucket where data will be written.
    data (str): Data to write to the file.
    """
    # Create an S3 client
    s3_client = boto3.client('s3')
    
    try:
        # Writing data to S3
        s3_client.put_object(Bucket=bucket_name, Key=file_name, Body=data)
        print("Data written to S3 successfully!")
    except Exception as e:
        print(f"An error occurred: {e}")

def lambda_handler(event, context):
    chatgpt_response = "Hello, I'm your call assistant."

    try:
        query_string = ""
        if "body-json" in event:
            query_string = event['body-json']
        decoded_query = unquote(query_string)
        parsed_query = parse_qs(decoded_query)

        if "SpeechResult" in parsed_query:
            speech_result = parsed_query['SpeechResult'][0]

            bucket_name = 'callerai'
            key = f"conversations/conversation_{parsed_query['CallSid'][0]}.json"

            try:
                speech_result = re.sub(r'[^a-zA-Z0-9,. ]', '', speech_result)
                chatgpt_request_json = '{"role": "user", "content": "' + speech_result + '"}'
                chatgpt_request_json_object = json.loads(chatgpt_request_json)
                print(chatgpt_request_json_object)
            except Exception as e:
                print("Error decoding JSON:", e)
                chatgpt_request_json_object = None
            if chatgpt_request_json_object:
                # get conversation if exists
                conversation = read_file_from_s3(bucket_name, key)
                conversation_raw = conversation
                conversation_array = []
                if conversation:
                    conversation = "[" + conversation + "]"
                    conversation_array = json.loads(conversation)
                    conversation_raw += ", "
                conversation_array.append(chatgpt_request_json_object)
                conversation_raw += chatgpt_request_json

                openai_response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": conversation_array
                    }
                )
                chatgpt_response = openai_response.json()["choices"][0]["message"]["content"]

                if chatgpt_response:
                    chatgpt_response = re.sub(r'[^a-zA-Z0-9,. ]', '', chatgpt_response)
                    chatgpt_response_json = '{"role": "assistant", "content": "' + chatgpt_response + '"}'

                    conversation_raw += ", " + chatgpt_response_json
                    write_to_s3(bucket_name, key, conversation_raw)
    except Exception as e:
        chatgpt_response = "There was an error, please try again later"
    
    print("chatgpt_response:", chatgpt_response)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/xml"},
        "body": f"""<?xml version="1.0" encoding="UTF-8"?><Response><Say>{chatgpt_response}</Say><Gather input="speech" timeout="3" action="https://50ysaba6mf.execute-api.us-east-1.amazonaws.com/stage" method="POST"><Pause length="1"/><Say>Please say your next question</Say></Gather><Say>We didn't receive any input. Goodbye!</Say></Response>"""
    }