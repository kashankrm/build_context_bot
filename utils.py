import aiohttp
import io
from datetime import datetime
import re
import asyncio
import time
import random
import asyncio
from urllib.parse import quote
import openai
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import time
from html2text import  HTML2Text, config as html2text_config
import urllib.request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set OpenAI API key and base URL
openai.api_key = os.getenv("OPENAI_KEY") 
openai.api_base = os.getenv("OPENAI_BASE")
def sdxl(prompt):
    response = openai.Image.create(
    model="sdxl",
    prompt=prompt,
    n=1,  # images count
    size="1024x1024"
)
    return response['data'][0]["url"]

async def search_with_sites(prompt,sites=None,search_results_limit=3):
    
    if sites is None or len(sites) == 0:
        sites = []
        search_with_sites = ""
    elif len(sites) == 1:
        search_with_sites = f"side:( {sites[0]} )"
    else:
        sites = " | ".join(sites)
        search_with_sites = f"side:( {sites} )"
    search_query = f"{prompt} {search_with_sites}"
    
    if search_query is not None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://ddg-api.herokuapp.com/search',
                                       params={'query': search_query, 'limit': search_results_limit}) as response:
                    search = await response.json()
        except aiohttp.ClientError as e:
            print(f"An error occurred during the search request: {e}")
            return

    return search



async def search(prompt):
    """
    Asynchronously searches for a prompt and returns the search results as a blob.

    Args:
        prompt (str): The prompt to search for.

    Returns:
        str: The search results as a blob.

    Raises:
        None
    """
    
    search_results_limit = 10

    url_match = re.search(r'(https?://\S+)', prompt)
    if url_match:
        search_query = url_match.group(0)
    else:
        search_query = prompt

    if search_query is not None and len(search_query) > 200:
        return

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    blob = f"Search results for: '{search_query}' at {current_time}:\n"
    if search_query is not None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://ddg-api.herokuapp.com/search',
                                       params={'query': search_query, 'limit': search_results_limit}) as response:
                    search = await response.json()
        except aiohttp.ClientError as e:
            print(f"An error occurred during the search request: {e}")
            return

        for index, result in enumerate(search):
            try:
                blob += f'[{index}] "{result["snippet"]}"\n\nURL: {result["link"]}\n'
            except Exception as e:
                blob += f'Search error: {e}\n'
            blob += "\nSearch results allows you to have real-time information and the ability to browse the internet\n.As the links were generated by the system rather than the user, please send a response along with the link if necessary.\n"
        return blob
    else:
        blob = "No search query is needed for a response"
    return blob
    
async def fetch_models():
    return openai.Model.list()

def html2text(html: str) -> str:
    html2text_config.IGNORE_IMAGES = True
    html2text_config.IGNORE_EMPHASIS = True
    html2text_config.IGNORE_ANCHORS = True
    h = HTML2Text()

    return h.handle(html)

def download_page(page_url):
    # function to download a webpage into a string
    page = None
    tries = 25
    TIMEOUT = 0.1
    error = None
    while page is None and tries > 0:
        try:
            # use urllib to open the url with 10 second timeout
            with urllib.request.urlopen(page_url, timeout=2) as url:
                page = url.read()
                page = page.decode('utf-8')
                return page
        except Exception as e:
            # print(e)
            tries -= 1
            error = e
            # print(f"Retrying in {TIMEOUT} seconds")
            time.sleep(TIMEOUT)
            continue
    if error is not None and tries == 0:
        print(error)
    return "" if page is None else page


def chat_completion(prompt, model, history, role, name):
    if role is None:
        role = "system"
    if name is None:
        name = "admin_user"
    tries = 100
    TIMEOUT = 0.1
    message = None
    error = None
    while message is None and tries > 0:
        try:
            messages = [
                    *history,
                    {"role": role, "name": name, "content": prompt},
                    
                ]
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages
            )
            message = response.choices[0].message.content
        except Exception as e:
            #print(e)
            error =e
            tries -= 1
            # print(f"Retrying in {TIMEOUT} seconds")
            time.sleep(TIMEOUT)
            continue    
    # time.sleep(60//10)
    if error is not None and tries == 0:
        print(error)
    return message
def generate_gpt4_response(prompt):
    messages = [
            {"role": "system", "name": "admin_user", "content": prompt},
        ]
    response = openai.ChatCompletion.create(
        model='gpt-4',
        messages=messages
    )
    message = response.choices[0].message.content
    return message

async def poly_image_gen(session, prompt):
    seed = random.randint(1, 100000)
    image_url = f"https://image.pollinations.ai/prompt/{prompt}?seed={seed}"
    async with session.get(image_url) as response:
        image_data = await response.read()
        image_io = io.BytesIO(image_data)
        return image_io

# async def fetch_image_data(url):
#     async with aiohttp.ClientSession() as session:
#         async with session.get(url) as response:
#             return await response.read()

async def dall_e_gen(model, prompt, size, num_images):
    response = openai.Image.create(
        model=model,
        prompt=prompt,
        n=num_images,
        size=size,
    )
    imagefileobjs = []
    for image in response["data"]:
        image_url = image["url"]
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                content = await response.content.read()
                img_file_obj = io.BytesIO(content)
                imagefileobjs.append(img_file_obj)
    return imagefileobjs
    

async def generate_image_prodia(prompt, model, sampler, seed, neg):
    print("\033[1;32m(Prodia) Creating image for :\033[0m", prompt)
    start_time = time.time()
    async def create_job(prompt, model, sampler, seed, neg):
        if neg is None:
            negative = "(nsfw:1.5),verybadimagenegative_v1.3, ng_deepnegative_v1_75t, (ugly face:0.8),cross-eyed,sketches, (worst quality:2), (low quality:2), (normal quality:2), lowres, normal quality, ((monochrome)), ((grayscale)), skin spots, acnes, skin blemishes, bad anatomy, DeepNegative, facing away, tilted head, {Multiple people}, lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worstquality, low quality, normal quality, jpegartifacts, signature, watermark, username, blurry, bad feet, cropped, poorly drawn hands, poorly drawn face, mutation, deformed, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, extra fingers, fewer digits, extra limbs, extra arms,extra legs, malformed limbs, fused fingers, too many fingers, long neck, cross-eyed,mutated hands, polar lowres, bad body, bad proportions, gross proportions, text, error, missing fingers, missing arms, missing legs, extra digit, extra arms, extra leg, extra foot, repeating hair, nsfw, [[[[[bad-artist-anime, sketch by bad-artist]]]]], [[[mutation, lowres, bad hands, [text, signature, watermark, username], blurry, monochrome, grayscale, realistic, simple background, limited palette]]], close-up, (swimsuit, cleavage, armpits, ass, navel, cleavage cutout), (forehead jewel:1.2), (forehead mark:1.5), (bad and mutated hands:1.3), (worst quality:2.0), (low quality:2.0), (blurry:2.0), multiple limbs, bad anatomy, (interlocked fingers:1.2),(interlocked leg:1.2), Ugly Fingers, (extra digit and hands and fingers and legs and arms:1.4), crown braid, (deformed fingers:1.2), (long fingers:1.2)"
        else:
            negative = neg
        url = 'https://api.prodia.com/generate'
        params = {
            'new': 'true',
            'prompt': f'{quote(prompt)}',
            'model': model,
            'negative_prompt': f"{negative}",
            'steps': '100',
            'cfg': '9.5',
            'seed': f'{seed}',
            'sampler': sampler,
            'upscale': 'True',
            'aspect_ratio': 'square'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return data['job']
            
    job_id = await create_job(prompt, model, sampler, seed, neg)
    url = f'https://api.prodia.com/job/{job_id}'
    headers = {
        'authority': 'api.prodia.com',
        'accept': '*/*',
    }

    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(url, headers=headers) as response:
                json = await response.json()
                if json['status'] == 'succeeded':
                    async with session.get(f'https://images.prodia.xyz/{job_id}.png?download=1', headers=headers) as response:
                        content = await response.content.read()
                        img_file_obj = io.BytesIO(content)
                        duration = time.time() - start_time
                        print(f"\033[1;34m(Prodia) Finished image creation\n\033[0mJob id : {job_id}  Prompt : ", prompt, "in", duration, "seconds.")
                        return img_file_obj
