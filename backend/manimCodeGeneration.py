from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage
from llm import llmPro, llmFlash
from schema import mainmState, CheckMaimCode
from dotenv import load_dotenv
from langgraph.graph import END
import os
import subprocess
import uuid
load_dotenv()

MAX_REWRITE_ATTEMPTS = 3
@tool
def create_File_and_Write_mainm_Code(filename, content):
    """This tool is used to write a python code directly in a file for a Manim animation."""
    print("****************** Creating a file ****************")
    if not os.path.exists("./temp"):
        os.makedirs("./temp")
        
    filepath = f"./temp/{filename}"
    try:
        with open(filepath, "w") as f:
            f.write(content)
        return f"Successfully created file: {filepath}"
    except IOError as e:
        return f"Error writing to file: {e}"


def read_file(filename):
    """This tool is used to read a file"""
    print("****************** reading a file ****************")
    filepath = f"./temp/{filename}"
    try:
        with open(filepath, "r") as f:
            fileContent = f.read()
        
        return fileContent
    except IOError as e:
        return f"Error while reading a file: {e}"
    

import subprocess
import os

def run_manim_scene(filename, state: mainmState):
    print("****************** running a manim file ****************")
    flags=f"--progress_bar display -{state.quality}"
    filepath = f"./temp/{filename}"
    scene_name = filename.replace(".py", "")

    if not os.path.exists(filepath):
        return f"Error: File '{filepath}' not found."

    command = ["manim", "render", filepath, scene_name]
    command.extend(flags.split())

    print(f"--- Running Manim Command: {' '.join(command)} ---")
    
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        full_output = ""  # Collect all output
        for line in process.stdout:
            print(line, end='')       # Show real-time
            full_output += line       # Save for return

        process.wait()

        if process.returncode != 0:
            return f"MANIM EXECUTION FAILED. The file '{filename}' has an error. Review output below:\n\n{full_output}"

        print("--- Finished rendering successfully ---")
        return f"Manim render completed for {filename}."

    except FileNotFoundError:
        return "Error: 'manim' command not found. Is Manim installed and in your PATH?"

# @tool
# def remove_file(filename):
#     os.remove(filename)



def agent_create_file(state: mainmState):
    tools = [create_File_and_Write_mainm_Code]

    system_prompt = """
    You are a helpful AI. You expert in creating manim code in and try it be good in one go and use manim v.19
    Your tasks are:
    1. Write Manim python code for an animation and save it to a file using the provided tool.
    2. The class name for the animation scene must be the same as the filename (without the .py extension).
    
    Note:
    - Add the text "Developed by Suraj Patel" in a very small font to the bottom right corner of the scene. like Watermark
    - And all the content should be in frame.
    - if you are creating 3d then do it correctly
        -- 2D Scenes use a camera.frame to control the view.
        -- 3D Scenes use the camera object directly for control.

    You got These error many time try to overcome these issue:
    - TypeError: Code.__init__() got an unexpected keyword argument 'code'
    - NameError: name 'Text3D' is not defined
    - ValueError: latex error converting to dvi.
    - TypeError: Mobject.__getattr__.<locals>.getter() takes 1 positional argument but 2 were given

    """ 

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ]
    )

    # Generate a clean, usable ID
    # We'll use a prefix and the first 8 characters of the UUID's hex representation.
    unique_name = f"Animation_{uuid.uuid4().hex[:8]}"
    state.filename = f"{unique_name}.py"
    # 2. Write a clear, direct prompt using the clean ID
    human_message = f"""
    {state.description} 
    Use the filename "{unique_name}.py" and the class name "{unique_name}".
    """

    agent = create_tool_calling_agent(llmPro, tools, prompt=prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    print(f"--- Running agent with filename: {unique_name}.py ---")
    result = agent_executor.invoke({"input": human_message})
    print("\n--- Agent Final Answer ---")
    print(result['output'])
    print(f"{unique_name}.py")
    print(f"statte ************************* {state.filename} ")

    return state


def agent_check_file_code(state: mainmState):
    code=read_file(state.filename)
    message = state.description
    system_prompt = f"""
    You are an expert Manim developer...

    Code is 
    {code} 

    **Instructions**
    1. Analyze the Python script provided below in the "Code is..." section.
        1.1. Code is important. code should not produce any error in execution
        1.2. And all the content should be in frame. 
    2. Compare its code and visual style with the description below. code is more important code should not break on the execution
    3. Return **one** JSON object with two keys:
    • "is_code_good"   – true / false  
    • "error_message"  – empty string if good, otherwise concise reason

    """
    structured_llm = llmPro.with_structured_output(CheckMaimCode)
    print("\n--- Checking Code file ---")



    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"{message}")
    ]
    evaluation_result = structured_llm.invoke(messages)

    state.is_code_good = evaluation_result.is_code_good
    state.error_message = evaluation_result.error_message
    print("\n--- Agent Final Answer (Structured Object) ---")
    print(f"Type of result: {type(evaluation_result)}")
    print(f"Is Code Good: {state.is_code_good}")
    print(f"Error Message: {state.error_message}")
    return state

def agent_re_write_manim_code(state: mainmState):
    tools = [create_File_and_Write_mainm_Code]
    filename = state.filename
    error_message = state.error_message
    description = state.description
    state.rewrite_attempts += 1 
    code = read_file(filename)

    # 1. Define the prompt with placeholders for all variables.
    system_prompt = """
    You are a helpful AI assistant and an expert in Manim code and use manim v.19
    Your task is to fix the error in the provided Manim code file.

    ERROR HANDLING:
    - If the `run_manim_scene` tool returns an error, **DO NOT** start from scratch.
    - Your task is now to re write code
    - Analyze the error message from the failed execution.

    Note: 
    - And all the content should be in frame. 
    - if you are creating 3d then do it correctly
        -- 2D Scenes use a camera.frame to control the view.
        -- 3D Scenes use the camera object directly for control.

    You got These error many time try to overcome these issue:
        - TypeError: Code.__init__() got an unexpected keyword argument 'code'
        - NameError: name 'Text3D' is not defined
        - ValueError: latex error converting to dvi.
        - TypeError: Mobject.__getattr__.<locals>.getter() takes 1 positional argument but 2 were given
    File to fix: {filename}
    code: {code}
    Error message to address: {error_message}
    """

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ]
    )
    
    agent = create_tool_calling_agent(llmPro, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=5)
    
    human_message = f"Please fix the error in the code based on the error message provided. and i want this {description}"

    # 2. Provide all required variables in the .invoke() call.
    result = agent_executor.invoke({
        "input": human_message,
        "filename": filename,
        "code":code,
        "error_message": error_message
    })

    print("\n--- re_write_manim_code ---")
    print(result['output'])
    return state

def agent_run_manim_code(state: mainmState):
    result_message = run_manim_scene(filename=state.filename, state=state)
    print(f"Execution Result: {result_message}")


    if "MANIM EXECUTION FAILED" in result_message:
        state.execution_success = False
        state.error_message = result_message
    else:
        state.execution_success = True
        state.error_message = ""

    return state


def manimRouter(state: mainmState):
    if state.is_code_good is True:
        return "agent_run_manim_code"
    elif state.rewrite_attempts >= 3:
        print("❌ Rewrite limit reached. Ending graph.")
        return END
    else: 
        return "agent_re_write_manim_code"
    
def executionRouter(state: mainmState):
    """Routes the graph after a Manim execution attempt."""
    if state.execution_success:
        print("✅ Manim execution successful. Ending graph.")
        return "done"
    else:
        # Prevent infinite loops
        if state.rewrite_attempts >= 3:
            print("❌ Rewrite limit reached after execution failure. Ending graph.")
            return "limit"
        print("❌ Manim execution failed. Routing to rewrite node.")
        return "fix"


def handle_failure_and_reset(state: mainmState) -> mainmState:
    """Resets the attempt counter to start the entire process over."""
    if state.create_again >= 1:
        return END
    else:
        print(f"❌ Maximum rewrite attempts reached. Resetting and starting over.")
        state.rewrite_attempts  = 0
        state.create_again += 1
        return state

def should_start_over_router(state: mainmState):
    """Checks the 'create_again' flag to decide the next step."""
    
    # CORRECT: Check if this is the first and only time we are starting over.
    if state.create_again == 1:
        print("✅ Starting the process over one time.")
        return "agent_create_file" # Loop back to the beginning
    else:
        # If create_again is > 1, the single retry has already been used.
        print("❌ Full retry and start-over process failed. Ending.")
        return END