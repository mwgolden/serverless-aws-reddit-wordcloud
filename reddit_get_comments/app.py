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

def save_to_bucket(json_object, key):    
    s3 = boto3.resource("s3")
    obj = s3.Object(BUCKET, key)
    response = obj.put(Body=json.dumps(json_object['comments']))
    return response

def queue_more_comments(message):
    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName=QUEUE_NAME)
    response = queue.send_message(MessageBody=json.dumps(message))
    print(response)

def lambda_handler(event, context):
    bot_name = event['bot_name']
    post_id = event['post_id']  
    api_token = get_api_token({"bot_name":bot_name})
    headers = {
        "Authorization": f"Bearer {api_token}",
        "User-Agent":"MyFirstRedditBot/0.1"
    }
    comments, more = get_base_comments(post_id, headers)
    total_pages = math.ceil(len(more) / 100)
    page = 0
    obj = {
        "post_id": post_id,
        "page":page,
        "total_pages": total_pages,
        "comments":comments 
    }
    key = f"postid={post_id}/page={page}/{post_id}.json"
    saved = save_to_bucket(obj, key)
    more_comments = {
        "post_id": post_id,
        "comments": more,
        "page_size": 100,
        "total_pages": total_pages,
        "request_headers": headers     
    } 
    more_comments_key = f"temp/{post_id}_more_comments.json"
    save_to_bucket(more_comments, more_comments_key)
    for i in range(0, total_pages):
        start = i * 100
        stop = start + 100
        page = i + 1
        msg = {
            "post_id": post_id,
            "start": start,
            "stop": stop,
            "request_headers": headers,
            "s3_bucket": BUCKET,
            "bucket_key": more_comments_key,
            "page": page,
            "total_pages": total_pages
        }
        queue_more_comments(msg)  
    return {
        "statusCode": 200,
        "body": saved
    }