import requests
import json
import autogen
import http.client
import os
import json
import csv
import requests
import prompts
import argparse
from dotenv import load_dotenv
from langchain.prompts import PromptTemplate
from langchain.chains import load_summarize_chain
from langchain.chat_models.azure_openai import AzureChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
import sys
from langchain_community.document_loaders import WebBaseLoader
from langchain.vectorstores import Chroma
from langchain.embeddings.azure_openai import AzureOpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document  # Import Document class


parser = argparse.ArgumentParser(description="Outreach Agentic Team", add_help="you need")
parser.add_argument("--leads", type=str, help="Path to the CSV file containing lead data")
parser.add_argument("--profile", type=str, help="Path to the JSON file containing profile data")
args = parser.parse_args()
leads = args.leads
profile_path = args.profile

print("parser Arg: ", leads, profile_path)

if not leads:
    print("Please provide a valid CSV file containing lead data")
    sys.exit(1)

if not profile_path:
    print("Please provide a valid JSON file containing profile data")
    sys.exit(1)

# Load environment variables from .env file
load_dotenv()

config_list=[
    {
        "model": os.getenv("AZURE_OPENAI_MODEL"),
        "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
        "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "api_type": "azure",
        "api_version": os.getenv("OPENAI_API_VERSION"),
    }
]

# Retrieve API key from environment variables
RAPID_API_KEY = os.getenv("RAPIDAPI")



def summarize(content, type):
    # Initialize the AzureChatOpenAI model
    llm = AzureChatOpenAI(temperature=0, deployment_name="autogen_studio_deployment")
    
    # Split the text into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n"], chunk_size=10000, chunk_overlap=500)
    docs = text_splitter.create_documents([content])

    # Select the appropriate prompt based on the type
    if type == 'linkedin':
        map_prompt = prompts.linkedin_scraper_prompt
    elif type == 'website':
        map_prompt = prompts.website_scraper_prompt
    else:
        raise ValueError("Unsupported type provided for summarization")

    # Create a prompt template
    map_prompt_template = PromptTemplate(
        template=map_prompt, input_variables=["text"])

    # Load the summarize chain
    summary_chain = load_summarize_chain(
        llm=llm,
        chain_type='map_reduce',
        map_prompt=map_prompt_template,
        combine_prompt=map_prompt_template,
        verbose=False
    )

    # Run the summarize chain
    output = summary_chain.run(input_documents=docs)

    return output

def scrape_linkedin(linkedin_url: str):
    json_cache = profile_path
    username = linkedin_url.split('/')[4]  # Extract username from LinkedIn URL
    conn = http.client.HTTPSConnection("linkedin-api8.p.rapidapi.com")

    headers = {
        'x-rapidapi-key': RAPID_API_KEY,
        'x-rapidapi-host': "linkedin-api8.p.rapidapi.com"
    }

    # Try to fetch data from local cache
    try:
        with open(json_cache, 'r') as f:
            cached_data = json.load(f)
            if isinstance(cached_data, dict):
                cached_data = [cached_data]  # Convert to list for uniform processing
            elif not isinstance(cached_data, list):
                print(f"Error: Cached data is neither a list nor a dictionary. Type: {type(cached_data)}")
                return None

            for entry in cached_data:
                if not isinstance(entry, dict):
                    print(f"Error: Entry is not a dictionary. Entry: {entry}")
                    continue
                if 'linkedin_url' not in entry or 'response' not in entry:
                    print(f"Error: Entry missing required keys. Entry: {entry}")
                    continue
                if entry['linkedin_url'] == linkedin_url:
                    print('Fetched data from Local Cache')
                    # Ensure entry['response'] is correctly formatted before summarizing
                    response_json = json.dumps(entry['response'])
                    return summarize(response_json, 'linkedin')  # Convert dict to JSON string
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f'No local cache found...({e})')
        cached_data = []

    # Request LinkedIn profile data from RapidAPI
    print('Fetching new json data... (updating local cache)')
    profile_json = {}
    posts_json = {}

    try:
        conn.request("GET", f"/get-profile-data-by-url?url=https%3A%2F%2Fwww.linkedin.com%2Fin%2F{username}%2F", headers=headers)
        res = conn.getresponse()
        profile_data = res.read()
        profile_json = json.loads(profile_data.decode("utf-8"))
        print(f"Profile Data: {profile_json}")
    except Exception as e:
        print(f"Error fetching profile data: {e}")

    # Request LinkedIn posts data
    try:
        conn.request("GET", f'/get-profile-posts?username={username}', headers=headers)
        res = conn.getresponse()
        posts_data = res.read()
        posts_json = json.loads(posts_data.decode("utf-8"))
        print(f"Posts Data: {posts_json}")
    except Exception as e:
        print(f"Error fetching posts data: {e}")

    # Combine profile and posts data
    combined_data = {
        'linkedin_url': linkedin_url,
        'response': {
            "profile_data": profile_json,
            "posts_data": posts_json
        }
    }

    # Save the combined data to local cache
    cached_data.append(combined_data)
    with open(json_cache, 'w') as f:
        json.dump(cached_data, f, indent=4)

    # Summarize and return the combined data
    response_json = json.dumps(combined_data['response'])
    return summarize(response_json, 'linkedin')

def research(linkedin_url: str):
    llm_config_research_li = {
        "functions": [
            {
                "name": "scrape_linkedin",
                "description": "look for relevant information about the lead in the json file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "linkedin_url": {
                            "type": "string",
                            "description": "The LinkedIn URL to search in json file",
                        }
                    },
                    "required": ["linkedin_url"],
                },
            },
        ],
        "config_list": config_list
    }

    outbound_researcher = autogen.AssistantAgent(
        name="Outbound_researcher",
        system_message="Research the LinkedIn Profile of a potential lead and generate a detailed report; Add TERMINATE to the end of the research report;",
        llm_config=llm_config_research_li,
    )

    user_proxy = autogen.UserProxyAgent(
        name="User_proxy",
        code_execution_config={"last_n_messages": 2, "work_dir": "coding", "use_docker": False,},
        is_termination_msg=lambda x: x.get("content", "") and x.get(
            "content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="NEVER",
        function_map={
            "scrape_linkedin": scrape_linkedin,
        }
    )

    user_proxy.initiate_chat(outbound_researcher, message=f"Research this lead's website and LinkedIn Profile {lead_data}")

    user_proxy.stop_reply_at_receive(outbound_researcher)
    user_proxy.send(
        "Give me the research report that just generated again, return ONLY the report, and add TERMINATE at the end of the message", outbound_researcher)

    # Return the last message the expert received
    return user_proxy.last_message()["content"]

# Cache to store the last loaded URL in a file
last_loaded_url_file = "last_loaded_url.txt"
cached_splits_file = "cached_splits.json"


def load_last_loaded_url():
    """Load the last loaded URL from the file."""
    if os.path.exists(last_loaded_url_file):
        with open(last_loaded_url_file, "r") as f:
            return f.read().strip()  # Read and strip any trailing newlines or spaces
    return None


def save_last_loaded_url(url):
    """Save the last loaded URL to the file."""
    with open(last_loaded_url_file, "w") as f:
        f.write(url)


def load_cached_splits():
    """Load the cached document splits from the file and convert them to Document objects."""
    if os.path.exists(cached_splits_file):
        with open(cached_splits_file, "r") as f:
            cached_data = json.load(f)
            # Convert the cached data back into a list of Document objects
            return [Document(page_content=split['page_content'], metadata=split['metadata']) for split in cached_data]
    return None


def save_cached_splits(all_splits):
    """Save the document splits to a file."""
    # Convert Document objects to serializable dictionaries
    with open(cached_splits_file, "w") as f:
        json.dump([{"page_content": split.page_content, "metadata": split.metadata} for split in all_splits], f)


def rag_agent(url, question):
    global cached_splits

    # Load the last loaded URL from the file
    last_loaded_url = load_last_loaded_url()

    # Check if the URL has changed
    if url != last_loaded_url:
        print(f"Loading new website: {url}")

        # Load the website if the URL has changed
        loader = WebBaseLoader(url)
        docs = loader.load()

        # Split the documents only if a new URL is loaded
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, add_start_index=True
        )
        all_splits = text_splitter.split_documents(docs)

        # Save the splits to a file
        save_cached_splits(all_splits)

        # Save the last loaded URL to the file
        save_last_loaded_url(url)
    else:
        print("URL hasn't changed, using cached document splits.")
        all_splits = load_cached_splits()

    # Initialize Azure OpenAI Embeddings
    embeddings = AzureOpenAIEmbeddings(
        model="text-embedding-ada-002",  # Use the correct model version
        chunk_size=1000,
    )
    vectorstore = Chroma.from_documents(documents=all_splits, embedding=embeddings)
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 6})
    return retriever.invoke(question)

def get_my_company_details(details):
    llm_config_rag_agent = {
        "functions": [
            {
                "name": "rag_agent",
                "description": "look for relevant information about the website",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to search in json file",
                        },
                        "question": {
                            "type": "string",
                            "description": "The question to search in json file",
                        }
                    },
                    "required": ["url", "question"],
                },
            },
        ],
        "config_list": config_list
    }

    assistant = autogen.AssistantAgent(
        name="assistant",
        llm_config=llm_config_rag_agent,
        system_message="You are a helpful assistant that can use rag_agent function to search the website and retrieve the relevant information and reply TERMINATE when the task is done",
    )

    user_proxy = autogen.UserProxyAgent(
        name="User_proxy",
        code_execution_config={"last_n_messages": 2, "work_dir": "coding", "use_docker": False,},
        is_termination_msg=lambda x: x.get("content", "") and x.get(
            "content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="NEVER",
        function_map={
            "rag_agent": rag_agent,
        }
    )

    # Starting the chat with the assistant
    user_proxy.initiate_chat(assistant, message="Please find relevant information about my company for this lead here are the materials. {research_material} from the website: https://wintellisys.com/wealth-wingman/")
    user_proxy.stop_reply_at_receive(assistant)
    user_proxy.send("Give me the relevant information that just generated again, return ONLY the information, and add TERMINATE at the end of the message", assistant)

    # Get the generated report content
    report_content = user_proxy.last_message()["content"]

    return report_content

# Create the outreach creation function

def load_company_signature():
    # Load company details from a JSON file
    with open('signature.json', 'r') as file:
        company_details = json.load(file)
    return company_details

# create_outreach_msg function
def create_outreach_msg(research_material):
    outbound_strategist = autogen.AssistantAgent(
        name="outbound_strategist",
        system_message="""
        You are a senior outbound strategist responsible for analyzing research material and crafting the most effective cold email structure with relevant personalization points. 
        Your role involves ensuring that each email is tailored to the recipient's background and achievements, aligning the content with their needs and the services offered by my company. 
        Ensure that all emails are formatted correctly, and add the following signature at the end of every email using the load_company_signature function:

        Best Regards,
        name
        title
        email
        linkedin
        company
        phone
        image
        """,
        llm_config={"config_list": config_list},
    )


    outbound_copywriter = autogen.AssistantAgent(
        name="outbound_copywriter",
        system_message="You are a professional AI copywriter who is writing cold emails for leads. You will write a short cold email based on the structure provided by the outbound strategist and also do not remove feedback from the reviewer. After 2 rounds of content iteration, add TERMINATE to the end of the message.",
        llm_config={"config_list": config_list},
    )

    reviewer = autogen.AssistantAgent(
        name="reviewer",
        system_message="You are a world-class cold email critic. You will review & critique the cold email and provide feedback to the writer. After 2 rounds of content iteration, add TERMINATE to the end of the message.",
        llm_config={"config_list": config_list},
    )

    user_proxy = autogen.UserProxyAgent(
        name="admin",
        system_message="A human admin. Interact with the outbound strategist to discuss the structure. Actual writing needs to be approved by this admin.",
        code_execution_config=False,
        is_termination_msg=lambda x: x.get("content", "") and x.get(
            "content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="TERMINATE",
    )

    groupchat = autogen.GroupChat(
        agents=[user_proxy, outbound_strategist, outbound_copywriter, reviewer],
        messages=[],
        max_round=3
    )
    manager = autogen.GroupChatManager(groupchat=groupchat)


    # Register the tool signature with the assistant agent.
    outbound_strategist.register_for_llm(name="load_company_signature", description="load company signature from the json file")(load_company_signature)

    # Register the tool function with the user proxy agent.
    user_proxy.register_for_execution(name="load_company_signature")(load_company_signature)

    user_proxy.initiate_chat(
        manager, message=f"Write a personalized cold email to lead, here are the materials: {research_material}"
    )

    user_proxy.stop_reply_at_receive(manager)
    user_proxy.send(
        "Give me the cold email that was just generated again, return ONLY the cold email, and add TERMINATE at the end of the message.", manager
    )

    # Get the generated email content
    email_content = user_proxy.last_message()["content"]

    # Append your personal details
    # email_with_signature = append_personal_details(email_content)

    return email_content



llm_config_outbound_writing_assistant = {
    "functions": [
        {
            "name": "research",
            "description": "research about a given lead, return the research material in report format",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_data": {
                        "type": "object",
                        "description": "The information about a lead",
                    }
                },
                "required": ["lead_data"],
            },
        },
        {
            "name": "get_my_company_details",
            "description": "get my company details from the website, return the details in report format",
            "parameters": {
                "type": "object",
                "properties": {
                    "details": {
                        "type": "string",
                        "description": "Please find relevant information about my company for this lead here are the materials. {research_material} from the website: https://wintellisys.com/wealth-wingman/",
                    }
                },
                "required": ["details"],
            },
        },
        {
            "name": "create_outreach_msg",
            "description": "Write an outreach message based on the given research material & lead information and website details",
            "parameters": {
                "type": "object",
                "properties": {
                    "research_material": {
                        "type": "string",
                        "description": "research material of a given topic, including reference links when available",
                    },
                },
                "required": ["research_material"],
            },
        },
    ],
    "config_list": config_list
}


outbound_writing_assistant = autogen.AssistantAgent(
    name="writing_assistant",
    system_message="You are an outbound assistant. You can use the research function to collect information about a lead, get my company details from the website, and then use the create_outreach_msg function to write a personalized outreach message. Reply TERMINATE when your task is done.",
    llm_config=llm_config_outbound_writing_assistant,
)

user_proxy = autogen.UserProxyAgent(
    name="User_proxy",
    code_execution_config=False,
    human_input_mode="TERMINATE",
    function_map={
        "create_outreach_msg": create_outreach_msg,
        "research": research,
        "get_my_company_details": get_my_company_details,
    }
)

# Load lead data from CSV file
def load_lead_data_from_csv(csv_file):
    with open(csv_file, mode='r', encoding='utf-8-sig') as file:
        csv_reader = csv.DictReader(file)
        leads = [row for row in csv_reader]
    return leads

# Define the path to your CSV file
# csv_file_path = '/home/jangirrahul/Desktop/Agentic_Teams/Chatbot_projects/LEAD_GEN/LEAD_GENERATION/Scrapper/valid_urls.csv'

# lead_data = {
#     "Email": sys.argv[1],
#     "Name": sys.argv[2],
#     "Position": sys.argv[3],
#     "linkedin_url": sys.argv[4],
# }

# Load leads from CSV
# leads = load_lead_data_from_csv(csv_file_path)

# Iterate through each lead in the CSV and process it using the multi-agentic team
# for lead_data in leads:
#     user_proxy.initiate_chat(
#         outbound_writing_assistant, 
#         message=f"create an effective outreach message for the LinkedIn profile: {lead_data}",
#         parameters={"lead_data": lead_data}  # Pass only the LinkedIn URL
#     )


# def load_lead_data_from_json(json_input):
#     """Parse JSON input and return a list of dictionaries with lead data."""
#     leads = []
#     for lead in json_input:
#         if len(lead) == 5:  # Ensure each lead has exactly five elements
#             lead_data = {
#                 "Email": lead[0],
#                 "Name": lead[1],
#                 "Position": lead[2],
#                 "linkedin_url": lead[3],
#                 "email_status": lead[4],
#             }
#             leads.append(lead_data)
#         else:
#             print("Each lead entry must contain exactly five elements: Email, Name, Position, LinkedIn URL, Email Status.")
#             sys.exit(1)
#     return leads

# Parse the JSON list of lists from command-line arguments
try:
    leads_input = json.loads(leads)
except (IndexError, json.JSONDecodeError):
    print("Please provide a valid JSON string as the first argument.")
    sys.exit(1)

# Convert the JSON input to lead data
# leads = load_lead_data_from_json(leads_input)

# Process each lead using the multi-agentic team
for lead_data in leads_input:
    user_proxy.initiate_chat(
        outbound_writing_assistant,
        message=f"create an effective outreach message for the LinkedIn profile: {lead_data}",
        parameters={"lead_data": lead_data}
    )