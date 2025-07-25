from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.graph import END
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from pydantic import ValidationError
from schema import DescriptionGenerationState, GenDescriptions, PickOneDescription, CheckPickedDescription
from llm import llmPro, llmFlash
import logging



load_dotenv()


def generate_Multiple_Description(state: DescriptionGenerationState):
    """
    Generates three animation descriptions using the model's structured output feature.
    """
    print("****** Generating Three Descriptions (Structured Output) ********\n")
    user_query = state.user_query

    structured_llm = llmFlash.with_structured_output(GenDescriptions)
    system_prompt = """
Your task is to generate **three candidate descriptions** that match the user's query.

Each description should be:
- Detailed
- Clear
- Technically descriptive
- Written to be used later as input for generating **Manim** (Mathematical Animation Engine) code.
"""
    msg = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query)
    ]

    try:
        # 4. Invoke the structured chain. The result is a Pydantic object, not a string.
        result = structured_llm.invoke(msg)
        
        print(result.descriptions, "\n\n")
        return state.model_copy(update={"descriptions": result.descriptions})

    except Exception as e:
        # This will now catch API errors or rare cases where the model fails
        # to generate structured output despite the constraints.
        logging.exception("Description generation with structured output failed")
        raise

def pick_One_Description_And_Generate_Detailed_Description(state: DescriptionGenerationState):
    print("******Picked one description ********\n\n")
    user_query = state.user_query
    contnet = state.descriptions
    structured_llm = llmPro.with_structured_output(PickOneDescription)
    system_prompt = f"""
You are a helpful AI assistant that generates a detailed and precise description from a Three AI-generated description.

You will be given:
- A human query
- Three AI-generated descriptions

Your task:
- All the frame should be center 
- Pick the best description, OR
- Merge them into a better one, OR
- Create a new, clearer, more detailed version based on them.
- then create detailed description
- Focused on structure, methods color size, or animations

This description will later be used to generate **Manim** (Mathematical Animation Engine) code, so it must be:
- Precise
- Technically descriptive
- Focused on structure, methods color size, or animations

"""

    msg = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query),
        AIMessage(content="\n".join(contnet))
    ]
    try:
        result = structured_llm.invoke(msg)
        print(result.description)
        return state.model_copy(update={"pickedOne": result.description})
    except (ValidationError, RuntimeError) as err:
        logging.exception("pick_One_Description_And_Generate_Detailed_Description failed")
        raise

def validate_Description(state: DescriptionGenerationState):
    """ This function checks the description, 
    if the description is correct then True otherwise False """
    print("******Checking is this Correct or not ********\n\n")
    picked_description = state.pickedOne
    user_query = state.user_query

    
    structured_llm = llmFlash.with_structured_output(CheckPickedDescription)
    system_prompt = f"""
Your task is to determine if the Candidate description is detailed, technically accurate, and directly addresses the user's query. The description will be used to generate Manim animations, so it must be precise.

Important Instruction:
1.  User Query: The original request from the user.
2.  Candidate Description: The description to be evaluated.

Instructions:
- If the description is high-quality, detailed, and relevant to the user's query, return `true` and leave error empty.
- If the description is vague, incomplete, irrelevant, or contains errors, return `false` and explain why in the error field.

Your entire response MUST be a single, valid JSON object and nothing else. Do not include explanations, markdown, or any text outside the JSON structure.

Example 1 (Good Description):
```json
{{
  "is_this_good_descrription": true,
  "pickedOneError": ""
}}

Example 2 (Bad Description)
{{
  "is_this_good_descrription": false,
  "pickedOneError": "The description lacks detail and does not explain how to perform the steps mentioned."
}}


Candidate Description:
{picked_description}

"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query)
    ]

    try:
        result = structured_llm.invoke(messages)
        print("Description is good or not: ",result.is_this_good_descrription)
        print("Description Error: ", result.pickedOneError)
        return state.model_copy(update={
            "is_good": result.is_this_good_descrription,
            "pickedOneError": result.pickedOneError
        })

    except (ValidationError, ValueError) as e:
        logging.exception("CheckPickedDescription parsing failed")
        raise

def refineDescription(state: DescriptionGenerationState):
    print("**** refineDescription *****")
    user_query = state.user_query
    description = state.pickedOne
    pickedDescriptionError = state.pickedOneError or "No specific error provided."
    structured = llmPro.with_structured_output(PickOneDescription)
    DescriptionRefine = state.DescriptionRefine + 1
    system_prompt = f"""
You are a helpful AI assistant that generates high-quality, technically accurate descriptions. These descriptions will be used to generate **Manim** (Mathematical Animation Engine) code.

You will be given:
- A user query
- One or more candidate descriptions
- The previous description's evaluation or error (if applicable)

Your task is to:
1. Decide whether any of the provided descriptions are suitable.
2. If one is suitable, select it.
3. If neither is sufficient, either:
   - Merge the descriptions into a better one, or
   - Create a new, clearer and more detailed version.
4. Ensure the final description is focused and technically accurate.

Requirements:
- The description must directly address the user's query.
- It must be precise and structured.
- Use specific details about:
  - Structure
  - Methods
  - Colors
  - Sizes
  - Animations (if applicable)
- Avoid vague or general language.

Output:
- A single, clear, and technically descriptive paragraph that is ready for Manim code generation.

Previous Description:
{description}


Description Evaluation / Error:
{pickedDescriptionError}
"""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query),
    ]
    try:
        result = structured.invoke(messages)
        return state.model_copy(update={
            "pickedOne":result.description,
            "DescriptionRefine": DescriptionRefine
            })
    except (ValidationError, ValueError) as e:
        logging.exception("CheckPickedDescription parsing failed")
        raise

def router(state: DescriptionGenerationState) -> str:
    if state.is_good is True:
        return END
    elif state.DescriptionRefine >= 2:
        return END
    else: 
        return "refineDescription"

