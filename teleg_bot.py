import os
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes
import pandas as pd
import requests
import json
from groq import Groq
import yfinance as yf
import inspect
from pydantic import TypeAdapter
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
API_KEY=os.getenv("WEATHER_API_KEY")
base_URL="http://api.weatherapi.com/v1/current.json"
client = OpenAI(
    base_url="https://api.together.xyz/v1",
    api_key=OPENAI_API_KEY,
)
def get_symbol(name):
    """
    return a symbol of a company
    param: 
        input: company name
        output: symbol of that company
    """
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={name}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        for result in data.get("quotes", []):
            if result.get("quoteType") == "EQUITY":
                return result["symbol"]
    return None
def get_stock_price(symbol):
    """
    return stock price from a symbol of a company
    param: 
        input: symbol
        output: stock price
    """
    if symbol:
        stock = yf.Ticker(symbol)
        return stock.info["regularMarketPrice"]

def get_weather(city):
    """
    return the current weather based on the city
    param:
        input: city
        output: temperature
    """
    params = {
    "key": API_KEY,
    "q": city
    }

    response = requests.get(base_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        weather_info={
            "city": city,
            "temperature": data['current']['temp_c']
        }
    return weather_info

tools=[
      {
        "type": "function",
        "function": {
          "name": "get_symbol",
          "description": inspect.getdoc(get_symbol),
          "parameters": TypeAdapter(get_symbol).json_schema()
        }
      },
      {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": inspect.getdoc(get_stock_price),
            "parameters": TypeAdapter(get_stock_price).json_schema()
        }
      },
        {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": inspect.getdoc(get_weather),
          "parameters": TypeAdapter(get_weather).json_schema()
        }
      }

    ]


chat_history = []

#answer questions and process requests
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global chat_history
    user_prompt = update.message.text
        

    chat_history.append({"role": "user", "content": user_prompt})

    function_map = {
            "get_symbol": get_symbol,
            "get_stock_price": get_stock_price,
            "get_weather": get_weather
    }
    while True:      
        response = client.chat.completions.create(
            model="meta-llama/Llama-4-Scout-17B-16E-Instruct",
            messages=chat_history,
            tools=tools,
            tool_choice="auto",
            )

        reply = response.choices[0].message
        print(reply)
        if not reply.tool_calls:
            text = reply.content
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text.strip())
            break
        chat_history.append({
            "role": reply.role,
            "content": reply.content
        }) 
        
        for tool_call in reply.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                func = function_map.get(function_name)
                if not func:
                    result = f"Function '{function_name}' is not implemented."
                else:
                    result = func(**function_args)

                chat_history.append({
                    "role": "function",
                    "name": function_name,
                    "content": json.dumps(result)
                })
        second_response = client.chat.completions.create(
                model="meta-llama/Llama-4-Scout-17B-16E-Instruct",
                messages=chat_history,
            )
        follow_up = second_response.choices[0].message
        chat_history.append({
            "role": follow_up.role,
            "content": follow_up.content
        })
        text = follow_up.content
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text.strip())
        break


# starting the Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hi, I'm a bot, ask me anything")

application = ApplicationBuilder().token(BOT_TOKEN).build()

start_handler = CommandHandler('start', start)
application.add_handler(start_handler)

chat_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), chat)
application.add_handler(chat_handler)


print("Bot is running...")
application.run_polling()