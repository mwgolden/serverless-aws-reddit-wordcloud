import json
import boto3
import io
import re
import html
from functools import reduce
import requests
import time
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS
from PIL import Image


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

def process_text(str):
    #unescape characters
    str = html.unescape(str)
    #remove urls
    str = re.sub('(?<=\])\((http:|https:|\/\/|www|).+\)', '', str)
    str = re.sub('(http:.+|https:.+|www.+).+', '', str)
    #remove user call outs
    str = re.sub('\[@.+\]', '', str)
    # remove emotes
    str = re.sub('\[img\]\(.+\)', '',str)
    #remove remaining non-alphnumeric characters
    str =  re.sub(r'[^\w]', ' ', str)
    #remove spaces preceding spaces
    str = re.sub('(?<=\s) ', '', str)
    #remove leading or trailing whitespace
    str = str.strip()
    return str

def comment_to_list(data):
    return [
        data['data']['parent_id'], 
        't1_'+data['data']['id'], 
        process_text(data['data']['body']), 
        data['data']['score'], 
        data['data']['ups'], 
        data['data']['downs']
    ]

def get_base_comments(post_id, headers):
    endpoint = f"https://oauth.reddit.com/comments/{post_id}"
    params = {"sort": "old", "threaded": False}
    response = requests.get(endpoint, headers=headers,params=params).json()[1]
    comments = [comment_to_list(comment) for comment in response['data']['children'] if comment['kind'] == 't1']
    more_items = [data for data in response['data']['children'] if data['kind'] == 'more'] 
    more_comments = [item['data']['children'] for item in more_items]
    more = []
    if len(more_comments) > 0:
        more = reduce(lambda a, b: a + b, more_comments)
    return (comments, more)

def get_more_comments(post_id, comment_ids, headers):
    params = {
        "link_id":f"t3_{post_id}",
        "children":",".join(comment_ids),
        "api_type":"json"
    }
    endpoint = f"http://oauth.reddit.com/api/morechildren"
    response = requests.get(endpoint, headers=headers, params=params).json()
    comments = [comment_to_list(data) for data in response['json']['data']['things'] if data['kind'] == 't1']
    return comments

def image_to_byte_array(img: Image, format: str = 'png'):
    result = io.BytesIO()
    img.save(result, format=format)
    result = result.getvalue()
    return result

def save_to_bucket(post_id, wordcloud):
    bucket_name = "com.wgolden.reddit-word-cloud"
    file_name = post_id + ".png"
    s3 = boto3.resource('s3')
    object = s3.Object(bucket_name, f"{post_id}/{file_name}")
    image_bytes = image_to_byte_array(img=wordcloud.to_image())
    response = object.put(Body=image_bytes)
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
    print(headers)
    post_id = 'y8tz9q'
    comments, more = get_base_comments(post_id, headers)
    print(f"comments: {len(comments)}")
    #print(f"more: {len(more)}")
    #while len(more) > 0:
    #    q = more[:100]
    #    more = more[100:]
    #    print(f"comments remaining: {len(more)}")
    #    [comments.append(comment) for comment in get_more_comments(post_id, q, headers)]
        #time.sleep(2)

    text = ''
    for comment in comments:
        text = text + comment[2] + ' '
    
    wordcloud = WordCloud(
        width=3000, 
        height=2000, 
        random_state=1,
        background_color='salmon',
        colormap='Pastel1',
        collocations=False,
        stopwords=STOPWORDS).generate(text)
    
    save_to_bucket(post_id=post_id, wordcloud=wordcloud)

    return {
        "statusCode": 200,
        "body": ""
    }