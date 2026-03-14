"""CrewAI multi-agent crew with TapPass governance.

All LLM calls and tool executions across the entire crew
are governed, classified, and logged.
"""

import os
from tappass import Agent
from crewai import Agent as CrewAgent, Crew, Task
from crewai_tools import SerperDevTool

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

# --- Connect to TapPass ---

tp = Agent(TAPPASS_URL, TAPPASS_API_KEY)

# Set environment so CrewAI auto-routes through TapPass
tp.configure_environment()

# Wrap tools with governance
search = SerperDevTool()
governed_tools = tp.govern([search])


# --- Define crew agents ---

researcher = CrewAgent(
    role="Senior Research Analyst",
    goal="Discover the latest trends in AI agent governance and EU regulation",
    backstory="You are an expert analyst focused on AI regulation in Europe.",
    tools=governed_tools,
    verbose=True,
)

writer = CrewAgent(
    role="Technical Writer",
    goal="Create a clear, concise summary of research findings",
    backstory="You write clear technical summaries for executive audiences.",
    verbose=True,
)


# --- Define tasks ---

research_task = Task(
    description=(
        "Research the current state of AI agent governance in Europe. "
        "Focus on EU AI Act requirements, GDPR implications, "
        "and NIS2 cybersecurity directive impact."
    ),
    expected_output="A detailed research report with sources and key findings.",
    agent=researcher,
)

summary_task = Task(
    description=(
        "Based on the research report, create a 1-page executive summary "
        "with key findings, regulatory timeline, and recommended actions."
    ),
    expected_output="A concise executive summary suitable for a CISO.",
    agent=writer,
)


# --- Run the crew ---

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, summary_task],
    verbose=True,
)

result = crew.kickoff()
print("\n" + "=" * 60)
print("Result:")
print(result)

# Check what happened: tappass logs
