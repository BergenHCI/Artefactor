import streamlit as st
import hashlib
from openai import OpenAI, RateLimitError
import re
import copy
import math
import backoff


st.set_page_config(
    page_title="LLM-powered User Experience Design",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded")

_system_msg_use_cases = "You are a UX design assistant, helping to create use cases and storyboards."
_system_msg_user_stories = "You are a UX design assistant, helping to create user stories"

_prompt_storyboard = "Create a visual depiction of a step in the use case scenario, suitable for a storyboard. Use semi-realistic style. The step description is the following:"


_user_stories_prompt = """Create user stories following the template “As a [persona], I [want to], [so that].” based on the following:

The user is described as following: {user}
The application solves the problem: {problem}
The application description: {application}
The contect of use: {context}
The suggested scenario of use:
{scenario}

Use numbered list for user stories."""


_scenario_prompt = """Create a realistic use case for the use of an application based on the following data:

The user is described as following: {user}
The application solves the problem: {problem}
The application description: {application}
The context of use: {context}

Create a use case scenario. Use numbered list to describe the steps in scenario. Describe each step in one sentence. Focus on interaction between the user and the application."""

_dalle_prompt = """You are creating a storyboard for an application based on the following use-case scenario:

{scenario}

For each step in the scenario, create a prompt for dall-e to generate a frame of a storyboard.
In each step, include context, so dall-e would understand, what is needed.
Return a numbered list of prompts without additional comments."""

# prompts
system_msg_use_cases = _system_msg_use_cases
system_msg_user_stories = _system_msg_user_stories

prompt_storyboard = _prompt_storyboard


gpt_model = "gpt-4-turbo-preview"

user_stories_prompt = _user_stories_prompt
scenario_prompt = _scenario_prompt
dalle_prompt = _dalle_prompt


def reset_data():
    data = {}
    data["app"] = {}
    data["scenario"] = ""
    data["storyboard"] = [] # ["desc": "Verbal description of what is happening", "url": "https"]
    st.session_state.data = data
    system_msg_use_cases = _system_msg_use_cases
    system_msg_user_stories = _system_msg_user_stories
    dalle_prompt = _dalle_prompt
    scenario_prompt = _scenario_prompt
    user_stories_prompt = _user_stories_prompt


with st.expander("AI settings"):
    system_msg_use_cases = st.text_input("Use cases GPT instruction", system_msg_use_cases)
    system_msg_user_stories = st.text_input("User stories GPT instruction", system_msg_user_stories)
    scenario_prompt = st.text_area("Scenario prompt", scenario_prompt, 5)
    dalle_prompt = st.text_area("Dall-E prompt", dalle_prompt, 5)
    user_stories_prompt = st.text_area("User stories prompt", user_stories_prompt, 5)


def extract_numerated_list(text:str):
    # Regular expression to match numerated list items:
    # Look for lines starting with one or more digits followed by a period and a space.
    # Use lookahead to ensure we match until the next start of a list item or the end of the text.
    pattern = re.compile(r'(\d+\.\s)(.*?)(?=\n\d+\.|\Z)', re.DOTALL)
    # Find all matches in the text
    matches = pattern.findall(text)
    if not matches:
        st.error("Can't extract list")
        st.stop()
    # Extract the text of each match
    list_items = ["".join(match[1]).strip() for match in matches]
    return list_items


with st.sidebar:
    openai_api_key = st.text_input("OpenAI API Key", key="chatbot_api_key", type="password")
    "[Get an OpenAI API key](https://platform.openai.com/account/api-keys)"
    if st.button("Clear data"):
        reset_data()
        st.rerun()

@st.cache_resource
def get_client():
    if not openai_api_key:
        st.error("Please provide Open AI API key first")
        st.stop()
    client = OpenAI(api_key=openai_api_key)
    return client


@st.cache_data(show_spinner="Generating..")
def generate_scenario(seed) -> str:
    data = st.session_state.data
    client = get_client()
    user_desc = data["app"].get("user_desc")
    app_desc = data["app"].get("app_desc")
    problem = data["app"].get("problem")
    context = data["app"].get("use_context")
    if not user_desc:
        st.error("Please provide user description")
    if not problem:
        st.error("Please describe the problem")
    if not app_desc:
        st.error("Please provide application description")
    if not context:
        st.error("Please describe the context of use")
    if user_desc and app_desc and context:
        message = scenario_prompt.format(
            user = user_desc, problem = problem, application = app_desc, context = context
        )
        messages=[
            {"role": "system", "content": system_msg_use_cases},
            {"role": "user", "content": message}
        ]
        response = client.chat.completions.create(model=gpt_model, messages=messages)
        msg = response.choices[0].message.content
        return msg
    return ""


def generate_dalle_prompts(scenario:str):
    client = get_client()
    messages=[
            {"role": "system", "content": system_msg_use_cases},
            {"role": "user", "content": dalle_prompt.format(scenario = scenario)}
        ]
    response = client.chat.completions.create(model=gpt_model, messages=messages)
    msg = response.choices[0].message.content
    return extract_numerated_list(msg)


@backoff.on_exception(backoff.expo, RateLimitError, max_tries=5, max_time=70)
def generate_image(prompt:str):
    client = get_client()
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url


@st.cache_data(show_spinner="Generating..")
def generate_user_stories(seed) -> list:
    data = st.session_state.data
    scenario = data.get("scenario")
    if not scenario:
        st.error("Generate scenario first")
        return []
    client = get_client()

    user_desc = data["app"].get("user_desc", "")
    app_desc = data["app"].get("app_desc", "")
    problem = data["app"].get("problem", "")
    context = data["app"].get("use_context", "")
    user_stories_prompt = _user_stories_prompt

    message = user_stories_prompt.format(
        user = user_desc, problem = problem, application = app_desc, context = context, scenario = scenario
    )
    messages=[
        {"role": "system", "content": system_msg_user_stories},
        {"role": "user", "content": message}
    ]
    response = client.chat.completions.create(model=gpt_model, messages=messages)
    msg = response.choices[0].message.content
    return msg


@st.cache_data(show_spinner="Generating..")
def generate_storyboard(seed):
    data = st.session_state.data
    # find scenario
    storyboard = []
    scenario = data.get("scenario")
    if not scenario:
        st.error("No scenario")
        return storyboard
    # get prompts for dall-e
    steps = generate_dalle_prompts(data["scenario"])
    # steps = extract_numerated_list(data["scenario"])
    for step in steps:
        img_url = generate_image(step)
        storyboard.append({"desc": "", "url": img_url})
    return storyboard


if "data" not in st.session_state:
    reset_data()


def scenario_editor():
    st.header("App and user details")
    data = st.session_state.data
    data["app"]["user_desc"] = st.text_input("Who is the main user of the application?")
    data["app"]["problem"] = st.text_input("What problem does the application solve?")
    data["app"]["app_desc"] = st.text_input("How does the application do it?")
    data["app"]["use_context"] = st.text_input("In what context?")


def scenario_preview():
    data = st.session_state.data
    
    if st.button("Generate use case scenario"):
        seed = hashlib.sha256(str(sorted(data.items())).encode()).hexdigest()
        st.session_state.data["scenario"] = generate_scenario(seed)
    if "scenario" in data:
        st.write(data["scenario"])

def storyboard_preview():
    data = st.session_state.data
    if st.button("Generate storyboard"):
        seed = hashlib.sha256(str(sorted(data.items())).encode()).hexdigest()
        data["storyboard"] = generate_storyboard(seed)
    if "storyboard" in data:
        storyboard = copy.deepcopy(data["storyboard"])
        steps_count = len(storyboard)
        if steps_count % 3 == 0:
            columns = 3
        else:
            columns = 4
        rows = math.ceil(steps_count / columns)
        for _ in range(rows):
            for c in st.columns(columns):
                with c:
                    step = storyboard and storyboard.pop(0) or None
                    if step:
                        st.image(step["url"], caption=step["desc"])

def userstory_preview():
    data = st.session_state.data
    if st.button("Generate user stories"):
        seed = hashlib.sha256(str(sorted(data.items())).encode()).hexdigest()
        data["stories"] = generate_user_stories(seed)
    if "stories" in data:
        st.write(data["stories"])

with st.container():
    scenario_editor()
    if not openai_api_key:
        st.info("Please add your OpenAI API key to continue.")
        st.stop()
    with st.container():
        with st.expander("Scenario"):
            scenario_preview()
        with st.expander("Storyboard"):
            storyboard_preview()
        with st.expander("User stories"):
            userstory_preview()

