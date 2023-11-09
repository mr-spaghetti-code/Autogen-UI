"""
This is the source code for processing SAP Data using Autogen and Chainlit
Features:
- Continuous messaging
- Multithreading 
Written by: Antoine Ross - October 2023.
"""

from typing import Dict, Optional, Union

import autogen
from autogen import Agent, AssistantAgent, UserProxyAgent, config_list_from_json
import chainlit as cl

# Edit the URL Here
URL = "https://www.w3schools.com/xml/simple.xml"

WELCOME_MESSAGE = f"""Trump, Elon Musk, Kim Kardashian, and your best friend are here for your intervention.
\n\n
How can they help you?
"""
# Agents
USER_PROXY_NAME = "User"
TRUMP = "Trump"
MUSK = "Elon Musk"
BESTIE = "Bestie"
KIM = "Kim Kardashian"

async def ask_helper(func, **kwargs):
    res = await func(**kwargs).send()
    while not res:
        res = await func(**kwargs).send()
    return res

class ChainlitAssistantAgent(AssistantAgent):
    """
    Wrapper for AutoGens Assistant Agent
    """
    def send(
        self,
        message: Union[Dict, str],
        recipient: Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ) -> bool:
        cl.run_sync(
            cl.Message(
                content=f'*Sending message to "{recipient.name}":*\n\n{message}',
                author=self.name,
            ).send()
        )
        super(ChainlitAssistantAgent, self).send(
            message=message,
            recipient=recipient,
            request_reply=request_reply,
            silent=silent,
        )

class ChainlitUserProxyAgent(UserProxyAgent):
    """
    Wrapper for AutoGens UserProxy Agent. Simplifies the UI by adding CL Actions. 
    """
    def get_human_input(self, prompt: str) -> str:
        if prompt.startswith(
            "Provide feedback to chat_manager. Press enter to skip and use auto-reply"
        ):
            res = cl.run_sync(
                ask_helper(
                    cl.AskActionMessage,
                    content="Continue or provide feedback?",
                    actions=[
                        cl.Action( name="continue", value="continue", label="✅ Continue" ),
                        cl.Action( name="feedback",value="feedback", label="💬 Provide feedback"),
                        cl.Action( name="exit",value="exit", label="🔚 Exit Conversation" )
                    ],
                )
            )
            if res.get("value") == "continue":
                return ""
            if res.get("value") == "exit":
                return "exit"

        reply = cl.run_sync(ask_helper(cl.AskUserMessage, content=prompt, timeout=60))

        return reply["content"].strip()

    def send(
        self,
        message: Union[Dict, str],
        recipient: Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ):
        cl.run_sync(
            cl.Message(
                content=f'*Sending message to "{recipient.name}"*:\n\n{message}',
                author=self.name,
            ).send()
        )
        super(ChainlitUserProxyAgent, self).send(
            message=message,
            recipient=recipient,
            request_reply=request_reply,
            silent=silent,
        )

@cl.on_chat_start
async def on_chat_start():
  try:
    config_list = config_list_from_json(env_or_file="OAI_CONFIG_LIST")
    trump = ChainlitAssistantAgent(
        name="Trump", llm_config={"config_list": config_list},
        system_message="""You are Donald Trump. Make sure you speak like Donald Trump using all his linguistics quirks. As Trump, your feedback is not very useful. You try to help User but ultimately just make it about yourself in a self-aggrandizing way. You constantly disagree with things even if you're wrong and you give absolutely absurd reasoning for it."""
    )
    musk = ChainlitUserProxyAgent(
        name="Musk", llm_config={"config_list": config_list}, 
        system_message="""You always have a four step master plan, but your plan for helping User goes wildly off the rails. Maybe someone just needs help making a peanut butter sandwich but you end up talking about making humans a multi-planetary species. You make dad jokes and reference memes that are irrelevant to the conversation."""
    )
    kim = ChainlitUserProxyAgent(
        name="Kim", llm_config={"config_list": config_list}, 
        system_message="""You care about user but tend to go on about some superfluous story. You speak like a valley girl and take way too long to get to the point. You always alude to stories about botox."""
    )
    bestie = ChainlitAssistantAgent(
        name="Bestie", llm_config={"config_list": config_list},
        system_message="""You want to help User overcome their problem. You genuinely care and make sure everyone helps as much as possible. You scoff at Trump's and Musk's remarks for being silly. You bring back the conversation back on topic which is to help user with their crisis. Speak as if you know the user, not too authoritatively."""
    )
    user_proxy = ChainlitUserProxyAgent(
        name="User",
        code_execution_config=False,
        system_message="""User. Administrate the agents on a plan to solve your problem. Reply TERMINATE at the end of your sentence if the task has been solved at full satisfaction. Otherwise, reply CONTINUE, or the reason why the task is not solved yet.""" 
    )
    
    cl.user_session.set(USER_PROXY_NAME, user_proxy)
    cl.user_session.set(TRUMP, trump)
    cl.user_session.set(MUSK, musk)
    cl.user_session.set(BESTIE, bestie)
    cl.user_session.set(KIM, kim)
    
    
    await cl.Message(content=WELCOME_MESSAGE, author="User").send()
    
  except Exception as e:
    print("Error: ", e)
    pass

@cl.on_message
async def run_conversation(message: cl.Message):
  try:
    TASK = message.content
    print("Task: ", TASK)
    trump = cl.user_session.get(TRUMP)
    user_proxy = cl.user_session.get(USER_PROXY_NAME)
    musk = cl.user_session.get(MUSK)
    bestie = cl.user_session.get(BESTIE)
    kim = cl.user_session.get(KIM)
    
    groupchat = autogen.GroupChat(agents=[user_proxy, trump, musk, bestie, kim], messages=[], max_round=50)
    manager = autogen.GroupChatManager(groupchat=groupchat)
    
    print("GC messages: ", len(groupchat.messages))
    
    if len(groupchat.messages) == 0:
      await cl.Message(content=f"""Starting agents on task: {TASK}...""").send()
      await cl.make_async(user_proxy.initiate_chat)( manager, message=TASK, )
    else:
      await cl.make_async(user_proxy.send)( manager, message=TASK, )
      
  except Exception as e:
    print("Error: ", e)
    pass