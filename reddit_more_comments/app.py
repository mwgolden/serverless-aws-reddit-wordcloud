import boto3
import json
import requests

ENDPOINT = "http://oauth.reddit.com/api/morechildren"
BUCKET = "com.wgolden.reddit-comments"

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
    key = f"{post_id}/{post_id}_{page}.json"
    s3 = boto3.resource("s3")
    obj = s3.Object(BUCKET, key)
    response = obj.put(Body=json.dumps(json_object))
    return response

def lambda_handler(event, context):
    records = event['Records']
    for record in records:
        message = json.loads(record['body'])
        bot_name = message['bot_name']
        user_agent = message['user_agent']
        post_id = message['post_id']
        comment_ids = message['comments']
        page = message['page_num']
        total_pages = message['total_pages']

        api_token = get_api_token({"bot_name": bot_name})
        headers = {
            "Authorization": f"Bearer {api_token}",
            "User-Agent":user_agent
        }
        comments = get_more_comments(post_id, comment_ids, headers)
        obj = {
            "post_id": post_id,
            "page":page,
            "total_pages": total_pages,
            "comments":comments 
        }
        save_to_bucket(obj)