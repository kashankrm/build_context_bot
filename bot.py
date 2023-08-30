from utils import generate_response, generate_gpt4_response, poly_image_gen, dall_e_gen, search_with_sites,chat_completion
import asyncio
from bs4 import BeautifulSoup
from html2text import  HTML2Text, config as html2text_config
from typing import Optional
from smmry.smmryapi import SmmryAPI
import time

SMMRY_API = "7A8DA68451"
smmry = SmmryAPI(SMMRY_API)

import urllib.request
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

# def parse_html_to_txt(html):
#     elem = BeautifulSoup(html, features="html.parser")
#     text = ''
#     for e in elem.descendants:
#         if isinstance(e, str):
#             text += e.strip()
#         elif e.name in ['br',  'p', 'h1', 'h2', 'h3', 'h4','tr', 'th']:
#             text += '\n'
#         elif e.name == 'li':
#             text += '\n- '
#     return text

def html2text(html: str) -> str:
    html2text_config.IGNORE_IMAGES = True
    html2text_config.IGNORE_EMPHASIS = True
    html2text_config.IGNORE_ANCHORS = True
    h = HTML2Text()

    return h.handle(html)
class BuildContextBot:
    # an ai bot that can be used to build a context on a particular topic

    def __init__(self, config):
        self.config = config
        self.context = []
        self.search = None
        self.history = []
        self.prompt = None
        self.image = None
    
    
    def generate_questions(self, message, qa_pair):
        #prompt to ask questions about the query
        question_prompt = f"Do not use your previous knowledge about other things. "

        question_prompt += f"Given this query: {message}\n\n "

        if len(qa_pair) > 0:
            qa_str = ""
            for index, (ques,ans) in enumerate(qa_pair):
                qa_str += f'[{index}] Question: {ques}\nAnswer: {ans}\n\n'
            question_prompt += f"Here is the list of questions and answers you have found so far: \n\n {qa_str} \n\n"
        
        question_prompt += f"Raise questions that you need to answer in order to answer the query "

        question_prompt += f"but do not attempt to answer these questions or query. \
                List at least 1 question and at most 10. Write them in a list and separate them on a new line. \
                Only list question that are very relevant, avoid listing too many questions. \
                Order them in order of importance. \n\n Questions: \n\n 1) "

        questions = chat_completion(question_prompt, self.config['MODEL'], [])
        questions = ("1) "+questions).split('\n')
        questions = [" ".join(question.split(' ')[1:]) for question in questions ]
        print("Questions: ")
        print("\n".join(questions))
        return questions
    
    def answer_question(self, question):
        print("Question: ", question)
        search_results = asyncio.run(search_with_sites(question, self.config['SEARCH_SITES'],10))
        #prompt to choose a link to explore
        choose_link_prompt = f"Forget all of your information about everything. Given this query: {question}\n\n Here is the list of links \
            to answer your question along with a small snippet of the text. \
                Write QUESTION_ANSERABLE if the question can be answered based on given information otherwise write QUESTION_NOT_ANSWERABLE. \
                     Do not answer the question yet.\n LINKS: \n\n"
        search_results_lst = []
        for index, result in enumerate(search_results):
            search_results_lst.append(f'[{index}] "{result["snippet"]}"\n\nURL: {result["link"]}\n')
        search_results_lst = "\n".join(search_results_lst)
        chat_answer = chat_completion(choose_link_prompt+search_results_lst, self.config['MODEL'], [])
        if "QUESTION_ANSWERABLE" not in chat_answer:
            search_results_lst = []
            for index, result in enumerate(search_results):
                summary = self.summarize_webpage(question,result['link'])
                search_results_lst.append(f'[{index}] "{summary}"\n\nURL: {result["link"]}\n')
            search_results_lst = "\n".join(search_results_lst)
            answer_question_prompt = f"Forget all of your information about everything. Given this query: {question}\n\n Here is the list of links \
                to answer your question along with the summary of the text. \
                    Answer the question using only these links.\n LINKS: \n\n"
            answer = chat_completion(answer_question_prompt+search_results_lst, self.config['MODEL'], [])
        else:
            #Answer the question
            history = [{"role": "system", "name": "admin_user", "content": choose_link_prompt+search_results_lst},
                    {"role": "assistant", "name": "assistant", "content": chat_answer},
                    ]
            answer = chat_completion(f"Now answer this question: {question}\n\n ",self.config['MODEL'],history)
        
        print("Answer: ", answer)
        return answer
    
    def find_more_qa_pair(self, query, qa_pairs):
        print("Finding more qa pairs for: ", query)
        questions = self.generate_questions(query,qa_pairs)
        for ques in questions:
            ans = self.answer_question(ques)
            qa_pairs.append((ques,ans))
        return qa_pairs


    def build_context(self, message):
        print("Building context for: ", message)
        
        question_answer_pair = []
        QUERY_SOLVED = False
        while not QUERY_SOLVED:
            self.find_more_qa_pair(message, question_answer_pair)
        
    
            question_asnwer_info = f"Given this query: {message}\n You have raised these questions and found thier answers\n"
            for index, (ques,ans) in enumerate(question_answer_pair):
                question_asnwer_info += f'[{index}] Question: {ques}\nAnswer: {ans}\n\n'
            check_answerable_prompt = question_asnwer_info + f"Based on these \n\n\
                Write QUESTION_ANSWERABLE if the question can be answered based on given information otherwise write QUESTION_NOT_ANSWERABLE. \
                    Do not answer the question yet.\n\n"
            check_answerable = chat_completion(check_answerable_prompt, self.config['MODEL'], [])
            if "QUESTION_ANSWERABLE" not in check_answerable:
                continue
            else:
                QUERY_SOLVED = True
                #Answer the question
                history = [{"role": "system", "name": "admin_user", "content": check_answerable_prompt},
                        {"role": "assistant", "name": "assistant", "content": check_answerable},
                        ]
                answer = chat_completion(f"Now answer this question: {message}\n\n ",self.config['MODEL'],history)
                question_answer_pair.append((message,answer))
        print("Finally the answer for the query: ", message)
        print("Answer: ", answer)
        return question_answer_pair

    
    def summarize_webpage(self, query, url):
        # try:

        #     summary = smmry.summarize(url,sm_length=40)
        # except Exception as e:
        #     print(e)
        #     return ""

        wepage_text = html2text(download_page(url))
        chunks = wepage_text.split('\n')
        chunks = [chunk for chunk in chunks if len(chunk) > 0]
        chunks = [chunk for chunk in chunks if chunk[0] != '-']
        chunk_pieces = []
        for i in range(0,len(chunks),200):
            chunk_pieces.append("\n".join(chunks[i:i+200]))
        summary = ""        
        for chunk in chunk_pieces:
            prompt = f"Summarize the following webpage into bullet points where each point is a simple fact. While considering the context that query was: {query}\n\n Do not miss any fact\
            : {url}\n\n{chunk}\n\nSummary:"
            chunk_summary = chat_completion(prompt, self.config['MODEL'], [])
            summary += '\n'+chunk_summary
        return summary

if __name__ == "__main__":
    config = {
        'MODEL': 'gpt-3.5-turbo-16k',
        'SUMMARY_MODEL': 'text-davinci-003',
        'SEARCH_SITES': []#["Wikihow.com", "Wikipedia.org", "StackOverflow.com", "StackExchange.com", "Quora.com", "Reddit.com", "Medium.com"]
    }
    b = BuildContextBot(config)
    b.build_context("why did pakistani team lose the cricket match against india in 2016?")
    print(b.context)


    