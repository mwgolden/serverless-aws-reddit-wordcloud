import boto3
import json
import requests

ENDPOINT = "http://oauth.reddit.com/api/morechildren"
BUCKET = "com.wgolden.reddit-comments"
QUEUE_NAME = "reddit-comments-queue"

def comment_to_dict(data):
    return {
        "parent_id":   data['data']['parent_id'], 
        "comment_id": 't1_'+data['data']['id'], 
        "body" :       data['data']['body'], 
        "score":       data['data']['score'], 
        "upvotes":     data['data']['ups'], 
        "downvotes":   data['data']['downs']
    }

def get_more_comments(post_id, comment_ids, headers):
    params = {
        "link_id":f"t3_{post_id}",
        "children":",".join(comment_ids),
        "api_type":"json"
    }
    response = requests.get(ENDPOINT, headers=headers, params=params).json()
    comments = [comment_to_dict(data) for data in response['json']['data']['things'] if data['kind'] == 't1']
    return comments

def save_to_bucket(json_object):
    post_id = json_object['post_id']
    page = json_object['page']
    key = f"postid={post_id}/page={page}/{post_id}.json"
    s3 = boto3.resource("s3")
    obj = s3.Object(BUCKET, key)
    response = obj.put(Body=json.dumps(json_object['comments']))
    return response

def get_from_bucket(bucket, key):
    s3 = boto3.client('s3')
    file_obj = s3.get_object(Bucket=bucket,Key=key)
    fileData = file_obj['Body'].read()
    return json.loads(fileData)

def lambda_handler(event, context):
    records = event['Records']
    for record in records:
        message = json.loads(record['body'])
        post_id = message['post_id']
        s3_bucket = message['s3_bucket']
        bucket_key = message['bucket_key']
        start = message['start']
        stop = message['stop']
        headers = message['request_headers']
        total_pages = message['total_pages']
        page = message['page']
        comment_ids = get_from_bucket(s3_bucket, bucket_key)
        next_100_comments = comment_ids[start:stop]
        comments = get_more_comments(post_id, next_100_comments, headers)
        obj = {
            "post_id": post_id,
            "page":page,
            "total_pages": total_pages,
            "comments":comments 
        }
        res = save_to_bucket(obj)
        print(res)
    return {
        "statusCode": 200,
        "body": ''
    }