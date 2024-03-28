import streamlit as st
import hashlib
from openai import OpenAI
import re
import copy
import math


st.set_page_config(
    page_title="LLM-powered User Experience Design",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded")

_system_msg_use_cases = "You are a UX design assistant, helping to create use cases and storyboards."
_system_msg_user_stories = "You are a UX design assistant, helping to create user stories"

_prompt_storyboard = "Create a visual depiction of a step in the use case scenario, suitable for a storyboard. Use semi-realistic style. The step description is the following:"
_prompt_user_stories = "Create user stories following the template “As a [persona], I [want to], [so that].” based on the following:"
_prompt_use_case = "Create a realistic use case for the use of an application based on the following data:"
_prompt_use_case_2 = "Create a use case scenario. Use numbered list to describe the steps in scenario. Describe each step in one sentence. Focus on interaction between the user and the application."

_prompt_for_dalle = """
You are creating a storyboard for an application based on the following use-case scenario:

{scenario}

For each step in the scenario, create a prompt for dall-e to generate a frame of a storyboard. In each step, include context, so dall-e would understand, what is needed. Return a numbered list of prompts without additional comments.
"""

# prompts
system_msg_use_cases = _system_msg_use_cases
system_msg_user_stories = _system_msg_user_stories

prompt_storyboard = _prompt_storyboard
prompt_user_stories = _prompt_user_stories
prompt_use_case = _prompt_use_case
prompt_use_case_2 = _prompt_use_case_2


with st.expander("AI settings"):
    system_msg_use_cases = st.text_input("Use cases GPT instruction", system_msg_use_cases)
    prompt_use_case = st.text_input("Use cases prompt start", prompt_use_case)
    prompt_use_case_2 = st.text_input("Use case prompt end", prompt_use_case_2)
    system_msg_user_stories = st.text_input("User stories GPT instruction", system_msg_user_stories)
    prompt_user_stories = st.text_input("User stories prompt", prompt_user_stories)
    prompt_storyboard = st.text_input("Storyboard prompt", prompt_storyboard)    
    gpt_model = st.selectbox("GPT Model", ("gpt-3.5-turbo", "gpt-4-0125-preview"))



def new_data():
    data = {}
    data["app"] = {}
    data["scenario"] = ""
    data["storyboard"] = [] # ["desc": "Verbal description of what is happening", "url": "https"]
    st.session_state.data = data
    system_msg_use_cases = _system_msg_use_cases
    system_msg_user_stories = _system_msg_user_stories
    prompt_storyboard = _prompt_storyboard
    prompt_user_stories = _prompt_user_stories
    prompt_use_case = _prompt_use_case
    prompt_use_case_2 = _prompt_use_case_2


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
        new_data()
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
    message_parts = [prompt_use_case]
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
        message_parts.append("The user is described as following: %s" % user_desc)
        message_parts.append("The application solves the problem: %s" % problem)
        message_parts.append("The application description: %s" % app_desc)
        message_parts.append("The contect of use: %s" % context)
        message_parts.append(prompt_use_case_2)
        messages=[
            {"role": "system", "content": system_msg_use_cases},
            {"role": "user", "content": "\n".join(message_parts)}
        ]
        response = client.chat.completions.create(model=gpt_model, messages=messages)
        msg = response.choices[0].message.content
        return msg
    return ""


def generate_dalle_prompts(scenario:str):
    template = _prompt_for_dalle
    client = get_client()
    messages=[
            {"role": "system", "content": system_msg_use_cases},
            {"role": "user", "content": template.format(scenario = scenario)}
        ]
    response = client.chat.completions.create(model=gpt_model, messages=messages)
    msg = response.choices[0].message.content
    return extract_numerated_list(msg)


def generate_image(prompt:str):
    client = get_client()
    response = client.images.generate(
        model="dall-e-2",
        prompt=prompt,
        size="512x512",
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
    if scenario:
        message_parts = [prompt_user_stories]
        user_desc = data["app"].get("user_desc")
        app_desc = data["app"].get("app_desc")
        problem = data["app"].get("problem")
        context = data["app"].get("use_context")
        if user_desc: message_parts.append("The user is described as following: %s" % user_desc)
        if problem: message_parts.append("The application solves the problem: %s" % problem)
        if app_desc: message_parts.append("The application description: %s" % app_desc)
        if context: message_parts.append("The contect of use: %s" % context)
        message_parts.append("The suggested scenario of use: %s" % scenario)
        message_parts.append("Use numbered list for user stories.")
        messages=[
            {"role": "system", "content": system_msg_user_stories},
            {"role": "user", "content": "\n".join(message_parts)}
        ]
        response = client.chat.completions.create(model=gpt_model, messages=messages)
        msg = response.choices[0].message.content
        return msg
    return ""


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
    new_data()


def scenario_editor():
    st.header("App and user details")
    data = st.session_state.data
    data["app"]["user_desc"] = st.text_input("Who is the main user of the application?")
    data["app"]["problem"] = st.text_input("What problem does the application solve?")
    data["app"]["app_desc"] = st.text_input("How does the application do it?")
    data["app"]["use_context"] = st.text_input("In what context?")


def scenario_preview():
    data = st.session_state.data
    if not openai_api_key:
        st.info("Please add your OpenAI API key to continue.")
        st.stop()
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
        for row in range(rows):
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
    
    with st.expander("Scenario"):
        scenario_preview()
    with st.expander("Storyboard"):
        storyboard_preview()
    with st.expander("User stories"):
        userstory_preview()

