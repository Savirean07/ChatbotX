# Outbound Writing Assistant

This repository contains a Python script designed to automate the process of researching leads, scraping LinkedIn profiles, summarizing content, and generating personalized outreach messages. The script leverages a multi-agentic team approach, integrating various APIs, the Autogen framework, Azure OpenAI for language processing, and a retrieval-augmented generation (RAG) system to streamline lead research, content generation, and email writing.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Code Overview](#code-overview)
  - [Project Structure](#project-structure)
  - [Multi-Agentic Workflow](#multi-agentic-workflow)
  - [Functions](#functions)
- [Usage](#usage)
  - [LinkedIn Data Scraping and Summarization](#linkedin-data-scraping-and-summarization)
  - [Researching LinkedIn and Website Data](#researching-linkedin-and-website-data)
  - [Retrieving Company Information (RAG Agent)](#retrieving-company-information-rag-agent)
  - [Generating Cold Outreach Message](#generating-cold-outreach-message)
- [Caching Mechanism](#caching-mechanism)
- [License](#license)

## Features

- **LinkedIn Profile and Post Scraping**: Scrapes LinkedIn profile and post data using RapidAPI.
- **Data Caching**: Caches LinkedIn profile data locally in `json_cache.json` to avoid redundant API requests.
- **Summarization**: Summarizes LinkedIn profile data and website content using Azure OpenAI’s language model.
- **Retrieval-Augmented Generation (RAG) Agent**: Extracts relevant information from company websites.
- **Automated Cold Email Generation**: Analyzes research materials to craft personalized outreach messages.

## Prerequisites

- **Azure OpenAI**: Set up an account with API keys for language models and embeddings.
- **RapidAPI Key**: For accessing LinkedIn scraping functionality.
- **Python Packages**: Install the following required Python packages:
    ```bash
    pip install requests langchain dotenv chroma autogen
    ```

## Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Wintellisys/Lead_Generation_Agentic_Team.git
   cd Lead_Generation_Agentic_Team
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Create a `.env` file with the following variables:

   ```
   AZURE_OPENAI_MODEL=<your_azure_openai_model>
   AZURE_OPENAI_API_KEY=<your_azure_openai_api_key>
   AZURE_OPENAI_ENDPOINT=<your_azure_openai_endpoint>
   OPENAI_API_VERSION=<api_version>
   RAPIDAPI=<your_rapidapi_key>
   ```

## Code Overview

### Project Structure

- `scrape_linkedin`: Scrapes LinkedIn profile data and caches the results.
- `summarize`: Uses Azure OpenAI to summarize scraped data.
- `rag_agent`: Loads website content and retrieves relevant information.
- `research`: Collects research on LinkedIn profiles and company websites.
- `create_outreach_msg`: Generates personalized cold email content using scraped data.
- **Data Cache Files**:
    - `json_cache.json`: Caches LinkedIn data.
    - `last_loaded_url.txt`: Tracks the last loaded URL for caching purposes.
    - `cached_splits.json`: Caches document splits for efficient RAG retrieval.

### Multi-Agentic Workflow

The script employs a multi-agentic team to handle different aspects of the outreach process, including LinkedIn data scraping, email strategy, and content review:

1. **Outbound Researcher**: Gathers information from LinkedIn profiles and websites.
2. **Outbound Strategist**: Analyzes the research material and drafts cold email structures.
3. **Outbound Copywriter**: Crafts and refines email content.
4. **Reviewer**: Ensures quality and effectiveness.
5. **Admin**: Oversees the entire process and gives final approval.

### Functions

- **`scrape_linkedin(linkedin_url: str)`**: Scrapes LinkedIn profile and post data based on the provided LinkedIn URL, and caches the data to avoid redundant API calls.
- **`summarize(content: str, type: str)`**: Summarizes data based on content type (`linkedin` or `website`) using Azure OpenAI’s language model.
- **`research(linkedin_url: str)`**: Collects and organizes LinkedIn profile and website research.
- **`rag_agent(url: str, question: str)`**: Loads content from a provided URL and retrieves relevant information based on a question.
- **`create_outreach_msg(research_material: str)`**: Generates a personalized cold email based on research material.

## Usage

### LinkedIn Data Scraping and Summarization

```python
linkedin_url = "https://www.linkedin.com/in/example-profile"
linkedin_summary = scrape_linkedin(linkedin_url)
print(linkedin_summary)
```

### Researching LinkedIn and Website Data

```python
research_material = research(linkedin_url)
print(research_material)
```

### Retrieving Company Information (RAG Agent)

```python
company_url = "https://yourcompany.com"
question = "What services does the company provide?"
company_info = rag_agent(company_url, question)
print(company_info)
```

### Generating Cold Outreach Message

```python
# Load signature data
signature = load_company_signature()

# Create an outreach message
outreach_message = create_outreach_msg(research_material)
print(outreach_message)
```

## Caching Mechanism

The code employs caching to optimize performance:
- **LinkedIn Cache**: Stores LinkedIn profile data in `json_cache.json`.
- **RAG Cache**: Stores document splits for website data in `cached_splits.json`.

## License

This project is licensed under the MIT License.
