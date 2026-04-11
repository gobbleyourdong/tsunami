#!/usr/bin/env python3
"""Build DPO pairs targeting ER05, HF09, and T01-T04 failures.

These tests have NEVER passed in any SFT version. DPO teaches the
contrastive boundary: "do A, NOT B."

Outputs: workspace/training_data/dpo_pairs_v1.jsonl
"""
import json
from transformers import AutoTokenizer

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/dpo_pairs_v1.jsonl"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Scaffold a new project", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Project name"}}}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Edit a file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "message_result", "description": "Send final result to user", "parameters": {"type": "object", "properties": {"content": {"type": "string"}, "done": {"type": "boolean"}}}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Chat with user", "parameters": {"type": "object", "properties": {"content": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "plan_update", "description": "Update the build plan", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "tasks": {"type": "array", "items": {"type": "string"}}}}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA check", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "file_read", "description": "Read a file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}},
]

SYSTEM = (
    "You are Tsunami, a local AI agent that builds apps by calling tools.\n\n"
    "ROUTING:\n"
    "- Build request -> project_init\n"
    "- Greeting/question/thanks -> message_result (done=true)\n"
    "- Research question -> search_web\n"
    "- Complex multi-component request -> plan_update FIRST\n"
    "- Error: Missing module -> shell_exec npm install\n"
    "- Error: Type/syntax -> file_edit\n"
    "- Error: Wrong path (cd fails) -> shell_exec with CORRECTED path\n"
    "- Error: Missing file -> file_write\n\n"
    "THE PIPELINE:\n"
    "1. project_init(name)\n"
    "2. file_write(path, content)\n"
    "3. shell_exec(build command)\n"
    "4. Fix errors if any\n"
    "5. undertow() QA\n"
    "6. message_result(content, done=true)"
)


def make_pair(messages, chosen_tc, rejected_tc):
    """Build a DPO pair using the chat template."""
    prompt_text = tokenizer.apply_chat_template(
        messages, tools=TOOLS, tokenize=False, add_generation_prompt=True
    )
    chosen_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_c", "type": "function", "function": chosen_tc}
    ]}]
    chosen_text = tokenizer.apply_chat_template(
        messages + chosen_msg, tools=TOOLS, tokenize=False
    )
    chosen_response = chosen_text[len(prompt_text):]

    rejected_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_r", "type": "function", "function": rejected_tc}
    ]}]
    rejected_text = tokenizer.apply_chat_template(
        messages + rejected_msg, tools=TOOLS, tokenize=False
    )
    rejected_response = rejected_text[len(prompt_text):]

    return {"prompt": prompt_text, "chosen": chosen_response, "rejected": rejected_response}


# ER05: Wrong path -> shell_exec with CORRECTED path
ER05_PAIRS = []
path_errors = [
    ("workspace/deliverables/app", "deliverables/app"),
    ("workspace/deliverables/counter", "deliverables/counter"),
    ("workspace/deliverables/todo", "deliverables/todo"),
    ("/workspace/deliverables/dashboard", "deliverables/dashboard"),
    ("workspace/deliverables/chat-app", "deliverables/chat-app"),
]
for wrong_path, correct_path in path_errors:
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "The build just failed. Fix it."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "shell_exec",
                "arguments": json.dumps({"command": f"cd {wrong_path} && npx vite build"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[shell_exec] bash: cd: {wrong_path}: No such file or directory"},
    ]
    chosen = {"name": "shell_exec", "arguments": json.dumps({"command": f"cd {correct_path} && npx vite build"})}
    rejected = {"name": "project_init", "arguments": json.dumps({"name": correct_path.split("/")[-1]})}
    ER05_PAIRS.append(make_pair(msgs, chosen, rejected))

for wrong_path, correct_path in path_errors[:3]:
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "The build just failed. Fix it."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "shell_exec",
                "arguments": json.dumps({"command": f"cd {wrong_path} && npx vite build"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[shell_exec] bash: cd: {wrong_path}: No such file or directory"},
    ]
    chosen = {"name": "shell_exec", "arguments": json.dumps({"command": f"cd {correct_path} && npx vite build"})}
    rejected = {"name": "shell_exec", "arguments": json.dumps({"command": f"cd {wrong_path} && npx vite build"})}
    ER05_PAIRS.append(make_pair(msgs, chosen, rejected))


# HF09: Complex build -> plan_update (not project_init)
HF09_PAIRS = []
complex_requests = [
    ("Build a full e-commerce platform with product listings, shopping cart, checkout flow, user authentication, and an admin dashboard",
     "E-commerce platform", ["Product catalog page", "Shopping cart", "Checkout flow", "User auth", "Admin dashboard"]),
    ("I need a project management tool with kanban boards, Gantt charts, team assignment, time tracking, and reports",
     "Project management tool", ["Kanban board view", "Gantt chart view", "Team assignment", "Time tracking", "Reports dashboard"]),
    ("Create a social media dashboard that aggregates posts from multiple platforms with analytics and scheduled posting",
     "Social media dashboard", ["Platform integrations", "Feed aggregation", "Analytics charts", "Post scheduler"]),
    ("Build a CRM with contact management, deal pipeline, email integration, task management, and reporting",
     "CRM system", ["Contact management", "Deal pipeline", "Email integration", "Task management", "Reports"]),
    ("Make a learning management system with courses, quizzes, progress tracking, certificates, and a student dashboard",
     "Learning management system", ["Course builder", "Quiz engine", "Progress tracking", "Certificate generator", "Student dashboard"]),
]
for prompt, goal, tasks in complex_requests:
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    chosen = {"name": "plan_update", "arguments": json.dumps({"goal": goal, "tasks": tasks})}
    rejected = {"name": "project_init", "arguments": json.dumps({"name": goal.lower().replace(" ", "-")[:20]})}
    HF09_PAIRS.append(make_pair(msgs, chosen, rejected))


# T01-T04: Greetings -> message_result (not message_chat/file_read)
GREETING_PAIRS = []
greetings = [
    ("Hello!", "Hello! What would you like me to build today?"),
    ("Hi there", "Hi! Ready to build something. What do you have in mind?"),
    ("Hey", "Hey! What would you like to build?"),
    ("Thanks, that's all I needed!", "Glad I could help! Let me know if you need anything else."),
    ("Thank you so much!", "You're welcome! Happy to help anytime."),
    ("What can you build?", "I can build web apps, games, dashboards, and more. Just describe what you want!"),
    ("Good morning!", "Good morning! What shall we build today?"),
    ("Goodbye!", "Goodbye! Come back anytime you need an app built."),
]
for user_msg, result_content in greetings:
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}]
    chosen = {"name": "message_result", "arguments": json.dumps({"content": result_content, "done": True})}
    if "thank" in user_msg.lower() or "bye" in user_msg.lower():
        rejected = {"name": "message_chat", "arguments": json.dumps({"content": "Is there anything else I can help with?"})}
    elif "what can" in user_msg.lower():
        rejected = {"name": "search_web", "arguments": json.dumps({"query": "what can AI build"})}
    else:
        rejected = {"name": "file_read", "arguments": json.dumps({"path": "deliverables/app/src/App.tsx"})}
    GREETING_PAIRS.append(make_pair(msgs, chosen, rejected))


# Safety: don't suppress project_init globally
SAFETY_PAIRS = []
for prompt in ["Build me a calculator app", "Make a todo list", "Create a weather dashboard"]:
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    chosen = {"name": "project_init", "arguments": json.dumps({"name": prompt.split()[-2].lower() + "-app"})}
    rejected = {"name": "message_result", "arguments": json.dumps({"content": "Sure, I can build that!", "done": True})}
    SAFETY_PAIRS.append(make_pair(msgs, chosen, rejected))


all_pairs = ER05_PAIRS + HF09_PAIRS + GREETING_PAIRS + SAFETY_PAIRS

print(f"\nDPO pairs built:")
print(f"  ER05 (wrong path):       {len(ER05_PAIRS)}")
print(f"  HF09 (plan gate):        {len(HF09_PAIRS)}")
print(f"  Greetings (T01-T04):     {len(GREETING_PAIRS)}")
print(f"  Safety (keep proj_init): {len(SAFETY_PAIRS)}")
print(f"  TOTAL: {len(all_pairs)}")

with open(OUT_PATH, "w") as f:
    for pair in all_pairs:
        f.write(json.dumps(pair) + "\n")

print(f"\nWritten to {OUT_PATH}")
for i, pair in enumerate(all_pairs[:2]):
    print(f"\n--- Pair {i} ---")
    print(f"  prompt[-80:]: ...{pair['prompt'][-80:]}")
    print(f"  chosen[:80]:  {pair['chosen'][:80]}")
    print(f"  rejected[:80]: {pair['rejected'][:80]}")
