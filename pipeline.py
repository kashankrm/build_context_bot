from utils import chat_completion as chat_model, html2text, search_with_sites, download_page
import asyncio

#Bot class takes model name and has a scractpad
class Bot:
    def __init__(self, model_name):
        self.model_name = model_name
        self.scratchpad = ""
        self.chat_completion = chat_model
        self.history = []

    # def chat(self, text):
    #     self.scratchpad += text
    #     return self.chat_completion(self.model_name, self.scratchpad)
    
    def add_to_history(self, role, name, content):
        assert role in ["system", "assistant", "user"], "Role must be one of system, assistant, user"
        message = {"role": role, "name": name, "content": content}
        self.history.append(message)
        return self.history
    
    def talk(self, prompt, role=None, name=None, scratchpad_flag=False):
        history = self.history
        if scratchpad_flag:
            scratchpad_message = self.scratchpad
            history = history + [{"role": "assistant", "name": "bot", "content": "My temporary scratchpad is:\n"+scratchpad_message}]
        message = self.chat_completion(prompt, self.model_name, history, role, name)
        return message

    def assign_history(self, history):
        self.history = history
        return self.history

    def delete_history(self):
        self.history = []
        return self.history

# pipe class that takes a list of inputs and list of outputs with a prompt that uses all inputs to process 
# and outputs all outputs stored in the output variable. It uses bot class
class Pipe:
    def __init__(self, inputs, outputs, prompt):
        self.inputs = inputs
        self.outputs = outputs
        self.prompt = prompt
        self.bot = None
        self.output = None
    
    def set_bot(self, bot):
        self.bot = bot
    
    def run(self):
        assert self.bot is not None, "Bot must be set before running the pipe"
        prompt = self.prompt
        for input in self.inputs:
            prompt += input
        self.output = self.bot.talk(prompt)
        return self.output 

# coversation class uses Bot class to create a conversation wth user
class Conversation:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.hooks = []
        self.run_conversation = True
        self.add_hook(self.quit_hook)
    
    def add_hook(self, hook):
        self.hooks.append(hook)
    
    def handle_hooks(self, message):
        for hook in self.hooks:
            triggered = hook(message)
            if triggered:
                return True
        return False    
    def quit_hook(self, message):
        if message == "quit":
            print("quit hook triggered")
            self.run_conversation = False
            return True
        return False
    
    def start_conversation(self):
        print("Bot: Hello, I am a chatbot. What is your name?\n")
        self.bot.add_to_history("system", "bot", "Hello, I am a chatbot. What is your name?")
        
        while self.run_conversation:
            print("You: ", end="")
            user_input = ""
            while user_input == "":
                inp = input().strip()
                if inp == "":
                    continue
                else:
                    user_input = inp
            
            skip = self.handle_hooks(user_input)
            if skip:
                continue
            self.bot.add_to_history("user", "user", user_input)
            print("\nBot: ", end="")
            bot_output = self.bot.talk(user_input, "user", "user")
            self.bot.add_to_history("assistant", "bot", bot_output)
            print(bot_output+"\n")

class ContextBuilder:
    # an ai bot that can be used to build a context on a particular topic

    def __init__(self, bot: Bot):
        self.bot = bot
        
        self.question_answer_pair = []
        
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

        questions = self.bot.talk(question_prompt, "user", "user", False)
        questions = ("1) "+questions).split('\n')
        questions = [" ".join(question.split(' ')[1:]) for question in questions ]
        print("Questions: ")
        print("\n".join(questions))
        return questions
    
    def answer_question(self, question):

        print("Question: ", question)
        search_results = asyncio.run(search_with_sites(question, [],10))
        #prompt to choose a link to explore
        choose_link_prompt = f"Forget all of your information about everything. Given this query: {question}\n\n Here is the list of links \
            to answer your question along with a small snippet of the text. \
                Write QUESTION_ANSERABLE if the question can be answered based on given information otherwise write QUESTION_NOT_ANSWERABLE. \
                     Do not answer the question yet.\n LINKS: \n\n"
        search_results_lst = []
        for index, result in enumerate(search_results):
            search_results_lst.append(f'[{index}] "{result["snippet"]}"\n\nURL: {result["link"]}\n')
        search_results_lst = "\n".join(search_results_lst)
        chat_answer = self.bot.talk(choose_link_prompt+search_results_lst, "user", "user", False)
        if "QUESTION_ANSWERABLE" not in chat_answer:
            search_results_lst = []
            for index, result in enumerate(search_results):
                summary = self.summarize_webpage(question,result['link'])
                search_results_lst.append(f'[{index}] "{summary}"\n\nURL: {result["link"]}\n')
            search_results_lst = "\n".join(search_results_lst)
            answer_question_prompt = f"Forget all of your information about everything. Given this query: {question}\n\n Here is the list of links \
                to answer your question along with the summary of the text. \
                    Answer the question using only these links.\n LINKS: \n\n"
            answer = self.bot.talk(answer_question_prompt+search_results_lst, "user", "user", False)
        else:
            #Answer the question
            history = [{"role": "system", "name": "admin_user", "content": choose_link_prompt+search_results_lst},
                    {"role": "assistant", "name": "assistant", "content": chat_answer},
                    ]
            
            self.bot.assign_history(history)
            answer = self.bot.talk(f"Now answer this question: {question}\n\n ", "user", "user", False)
            self.bot.delete_history()
        
        print("Answer: ", answer)
        return answer
    
    def find_more_qa_pair(self, query):
        print("Finding more qa pairs for: ", query)
        qa_pairs = self.question_answer_pair
        questions = self.generate_questions(query,qa_pairs)
        for ques in questions:
            ans = self.answer_question(ques)
            qa_pairs.append((ques,ans))
        return qa_pairs

    def add_question(self,question):
        ans = self.answer_question(question)
        self.question_answer_pair.append((question,ans))
        

    def build_context(self, message):
        print("Building context for: ", message)        
                
        QUERY_SOLVED = False
        while not QUERY_SOLVED:
            #Generate questions
            self.find_more_qa_pair(message)

            #Check if the query is solved
            question_asnwer_info = f"Given this query: {message}\n You have raised these questions and found thier answers\n"
            for index, (ques,ans) in enumerate(self.question_answer_pair):
                question_asnwer_info += f'[{index}] Question: {ques}\nAnswer: {ans}\n\n'
            check_answerable_prompt = question_asnwer_info + f"Based on these \n\n\
                Write QUESTION_ANSWERABLE if the question can be answered based on given information otherwise write QUESTION_NOT_ANSWERABLE. \
                    Do not answer the question yet.\n\n"
            check_answerable = self.bot.talk(check_answerable_prompt, "user", "user", False)
            if "QUESTION_ANSWERABLE" not in check_answerable:
                continue
            else:
                QUERY_SOLVED = True
                #Answer the question
                history = [{"role": "system", "name": "admin_user", "content": check_answerable_prompt},
                        {"role": "assistant", "name": "assistant", "content": check_answerable},
                        ]
                self.bot.assign_history(history)
                answer = self.bot.talk(f"Now answer this question: {message}\n\n ", "user", "user", False)
                self.bot.delete_history()
                self.question_answer_pair.append((message,answer))
        print("Finally the answer for the query: ", message)
        print("Answer: ", answer)
        return self.question_answer_pair

    
    def summarize_webpage(self, query, url):

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
            chunk_summary = self.bot.talk(prompt, "user", "user", False)
            summary += '\n'+chunk_summary
        return summary

class ContextBuildBot(Bot):
    def __init__(self,model_name,contextbot) -> None:
        super().__init__(model_name)
        
        self.contextbot = contextbot
    
    def context_hook(self, message):
        if message.startswith("addcontext"):
            message = message.split("addcontext")[1].strip()
            self.contextbot.find_more_qa_pair(message)
            qa_text = ""
            for index, (ques,ans) in enumerate(self.contextbot.question_answer_pair):
                qa_text += f'[{index}] Question: {ques}\nAnswer: {ans}\n\n'
            self.add_to_history("assistant", "bot", "Context:"+qa_text)
            print(qa_text)
            return True
        elif message.startswith("addquestion"):
            message = message.split("addquestion")[1].strip()
            self.contextbot.add_question(message)
            qa_text = ""
            for index, (ques,ans) in enumerate(self.contextbot.question_answer_pair):
                qa_text += f'[{index}] Question: {ques}\nAnswer: {ans}\n\n'
            self.add_to_history("assistant", "bot", "Context:"+qa_text)
            print(qa_text)
            return True
        elif message.startswith("showcontext"):
            qa_text = ""
            for index, (ques,ans) in enumerate(self.contextbot.question_answer_pair):
                qa_text += f'[{index}] Question: {ques}\nAnswer: {ans}\n\n'
            self.add_to_history("assistant", "bot", "Context:"+qa_text)
            print(qa_text)    
            return True
        return False

if __name__ == "__main__":
    
    contextbuilder = ContextBuilder(Bot("gpt-3.5-turbo"))
    contextbot = ContextBuildBot("gpt-3.5-turbo", contextbuilder)
    conversation = Conversation(contextbot)
    conversation.add_hook(contextbot.context_hook)

    conversation.start_conversation()
