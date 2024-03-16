import streamlit as st
import hashlib
from openai import OpenAI
import re


st.set_page_config(
    page_title="LLM-powered User Experience Design",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded")


# prompts
system_msg_use_cases = "You are a UX design assistant, helping to create use cases and storyboards."
system_msg_user_stories = "You are a UX design assistant, helping to create user stories"

prompt_storyboard = "Sketch of a step in a use case of an application in a stick figure style: "
prompt_user_stories = "Create user stories following the template “As a [persona], I [want to], [so that].” based on the following:"
prompt_use_case = "Create a realistic use case for the use of an application based on the following data:"
prompt_use_case_2 = "Create a use case scenario of 5 or less steps. Use numbered list to describe the steps in scenario. Describe each step in one sentence. Focus on interaction between the user and the application."


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
    system_msg_use_cases = "You are a UX design assistant, helping to create use cases and storyboards."
    system_msg_user_stories = "You are a UX design assistant, helping to create user stories"
    prompt_storyboard = "Sketch of a step in a use case of an application in a stick figure style: "
    prompt_user_stories = "Create user stories following the template “As a [persona], I [want to], [so that].” based on the following:"
    prompt_use_case = "Create a realistic use case for the use of an application based on the following data:"
    prompt_use_case_2 = "Create a use case scenario of 5 or less steps. Use numbered list to describe the steps in scenario. Describe each step in one sentence. Focus on interaction between the user and the application."


def extract_numerated_list(text:str) -> list:
    # Regular expression to match numerated list items: 
    # It looks for lines starting with one or more digits followed by a period.
    pattern = re.compile(r'\b\d+\.\s*(.*)')
    # Find all matches in the text
    matches = pattern.findall(text)
    if not matches:
        st.error("Can not parse the use case scenario")
    return matches


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
    steps = extract_numerated_list(data["scenario"])
    for step in steps:
        prompt = prompt_storyboard
        prompt += step
        img_url = generate_image(prompt)
        storyboard.append({"desc": step, "url": img_url})
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
    # st.header("Scenario")
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
    # st.header("Storyboard")
    data = st.session_state.data
    if st.button("Generate storyboard"):
        seed = hashlib.sha256(str(sorted(data.items())).encode()).hexdigest()
        data["storyboard"] = generate_storyboard(seed)
    if "storyboard" in data:
        for step in data["storyboard"]:
            st.image(step["url"], caption=step["desc"], width=512)

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