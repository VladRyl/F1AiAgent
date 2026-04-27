import fastf1
import feedparser
import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

load_dotenv()


cache_dir = "fastf1_cache"
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
fastf1.Cache.enable_cache(cache_dir)

@tool
def get_f1_schedule(year: int) -> str:
    """Returns the F1 schedule for a given year. Useful for finding upcoming races, dates, and locations."""
    try:
        schedule = fastf1.get_event_schedule(year)
        return schedule[['RoundNumber', 'Country', 'Location', 'EventName', 'EventDate']].to_string()
    except Exception as e:
        return f"Error fetching schedule: {str(e)}"


@tool
def get_race_results(year: int, location: str, session_type: str) -> str:
    """Returns the F1 race results for a given year, location, and session type (e.g., 'R' for race, 'Q' for qualifying)."""
    try:
        session = fastf1.get_session(year, location, session_type)
        session.load(telemetry=False, weather=False, messages=False)
        results = session.results[['Position', 'Abbreviation', 'TeamName', 'Status']]
        return results
    except Exception as e:
        return f"Error fetching results: {str(e)}"


@tool
def get_fantasy_prices() -> str:
    """Returns current F1 Fantasy information including prices, points, and other statistics for all drivers and constructors."""
    url = "https://fantasy.formula1.com/feeds/v2/statistics/driverconstructors_4.json"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        drivers_stats = {}
        for category in data.get('Data', {}).get('driver', []):
            stat_key = category.get('config', {}).get('key', 'unknown_stat')
            for p in category.get('participants', []):
                pid = p.get('playerid', 'Unknown')
                name = p.get('playername', 'Unknown')
                if pid not in drivers_stats:
                    drivers_stats[pid] = {
                        'name': name,
                        'team': p.get('teamname', 'Unknown'),
                        'price': p.get('curvalue', 0),
                        'stats': {}
                    }
                drivers_stats[pid]['stats'][stat_key] = p.get('statvalue', 0)
                
        constructors_stats = {}
        for category in data.get('Data', {}).get('constructor', []):
            stat_key = category.get('config', {}).get('key', 'unknown_stat')
            for p in category.get('participants', []):
                pid = p.get('playerid', 'Unknown')
                name = p.get('teamname', 'Unknown')
                if pid not in constructors_stats:
                    constructors_stats[pid] = {
                        'name': name,
                        'price': p.get('curvalue', 0),
                        'stats': {}
                    }
                constructors_stats[pid]['stats'][stat_key] = p.get('statvalue', 0)
                
        output = "F1 Fantasy Drivers Info:\n"
        for pid, info in drivers_stats.items():
            stats_str = ", ".join([f"{k}: {v}" for k, v in info['stats'].items()])
            output += f"- ID {pid}: {info['name']} ({info['team']}) | Price: ${info['price']}M | Stats: {stats_str}\n"
            
        output += "\nF1 Fantasy Constructors Info:\n"
        for pid, info in constructors_stats.items():
            stats_str = ", ".join([f"{k}: {v}" for k, v in info['stats'].items()])
            output += f"- ID {pid}: {info['name']} | Price: ${info['price']}M | Stats: {stats_str}\n"
            
        return output
    except Exception as e:
        return f"Error fetching fantasy info: {str(e)}"


@tool
def get_my_fantasy_team() -> str:
    """Returns the user's current F1 Fantasy team information."""
    url = os.getenv("FANTASY_TEAM_URL")
    cookie = os.getenv("FANTASY_COOKIE")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Cookie": cookie
    }
    if not url:
        return "Error: FANTASY_TEAM_URL environment variable is not set in .env."

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Error fetching my team: {str(e)}"


@tool
def get_f1_news() -> str:
    """Returns the latest F1 news from the Autosport RSS feed."""
    try:
        feed = feedparser.parse('https://www.autosport.com/rss/feed/f1')
        news_items = []
        for entry in feed.entries[:5]:
            news_items.append(f"Title: {entry.title}\nSummary: {entry.summary}\n")
        return "\n".join(news_items)
    except Exception as e:
        return f"Error fetching news: {str(e)}"


def run_f1_agent(query: str):
    if not os.getenv("GOOGLE_API_KEY"):
        return "Please set your GOOGLE_API_KEY environment variable. Run: export GOOGLE_API_KEY='your-key'"
        
    llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.2)
    tools = [get_f1_schedule, get_race_results, get_f1_news, get_fantasy_prices, get_my_fantasy_team]
    
    agent = create_agent(
        llm,
        tools=tools,
        system_prompt=f"You are an expert Formula 1 Fantasy AI Assistant. Today's date is {datetime.now().strftime('%Y-%m-%d')}. You use tools to gather actual F1 schedule, race results, latest news, and fantasy prices. You analyze this data to provide the best possible recommendations for an F1 Fantasy team strategy. Always base your advice on recent form and upcoming track characteristics. Answer clearly and concisely. Always answer strictly in Ukrainian language."
    )
    
    response = agent.invoke({"messages": [("user", query)]})
    content = response["messages"][-1].content
    if isinstance(content, list):
        return "".join([c.get("text", "") for c in content if isinstance(c, dict) and "text" in c])
    return str(content)


if __name__ == "__main__":
    print("Welcome to the F1 Fantasy AI Agent!")
    print("Type 'exit' to quit.")
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            print("Agent is thinking...")
            result = run_f1_agent(user_input)
            print(f"\nAI: {result}\n")
        except KeyboardInterrupt:
            print("\nExiting...")
            break