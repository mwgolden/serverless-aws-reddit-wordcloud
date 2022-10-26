import requests
import json
import boto3
import math
from functools import reduce

ENDPOINT = "https://oauth.reddit.com/comments"
BUCKET = "com.wgolden.reddit-comments"
QUEUE_NAME = "reddit-comments-queue"

def get_api_token(bot):
    client = boto3.client('lambda')
    response = client.invoke(
        FunctionName = 'get_api_access_token',
        InvocationType = 'RequestResponse',
        Payload = json.dumps(bot)
    )
    data = json.load(response['Payload'])
    api_token = data['body']['access_token']
    return api_token

def comment_to_dict(data):
    return {
        "parent_id":   data['data']['parent_id'], 
        "comment_id": 't1_'+data['data']['id'], 
        "body" :       data['data']['body'], 
        "score":       data['data']['score'], 
        "upvotes":     data['data']['ups'], 
        "downvotes":   data['data']['downs']
    }

def get_base_comments(post_id, headers):
    endpoint = f"{ENDPOINT}/{post_id}"
    params = {"sort": "old", "threaded": False}
    response = requests.get(endpoint, headers=headers,params=params).json()[1]
    comments = [comment_to_dict(comment) for comment in response['data']['children'] if comment['kind'] == 't1']
    more_items = [data for data in response['data']['children'] if data['kind'] == 'more'] 
    more_comments = [item['data']['children'] for item in more_items]
    more = []
    if len(more_comments) > 0:
        more = reduce(lambda a, b: a + b, more_comments)
    return (comments, more)

def save_to_bucket(json_object):
    post_id = json_object['post_id']
    page = json_object['page']
    key = f"{post_id}/{post_id}_{page}.json"
    s3 = boto3.resource("s3")
    obj = s3.Object(BUCKET, key)
    response = obj.put(Body=json.dumps(json_object))
    return response

def queue_more_comments(message):
    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName=QUEUE_NAME)
    response = queue.send_message(MessageBody=json.dumps(message))
    print(response)

def lambda_handler(event, context):
    inputParams = {
        "bot_name":"reddit_bot"
    }    
    api_token = get_api_token(inputParams)
    headers = {
        "Authorization": f"Bearer {api_token}",
        "User-Agent":"MyFirstRedditBot/0.1"
    }
    post_id = 'y8tz9q'
    comments, more = get_base_comments(post_id, headers)
    total_pages = math.ceil(len(more) / 100)
    obj = {
        "post_id": post_id,
        "page":0,
        "total_pages": total_pages,
        "comments":comments 
    }
    saved = save_to_bucket(obj)
    page_num = 0

    while len(more) > 0:
        more_comments = more[:100]
        more = more[100:]
        page_num =  page_num + 1
        message = {
            "bot_name":"reddit_bot",
            "user_agent": "MyFirstRedditBot/0.1",
            "post_id": "y8tz9q",
            "comments": more_comments,
            "page_num": page_num,
            "total_pages": total_pages
        } 
        queue_more_comments(message)  
    return {
        "statusCode": 200,
        "body": saved
    }