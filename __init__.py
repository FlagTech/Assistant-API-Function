import time
import openai
import json
import re
from IPython.display import HTML

_client = None
def set_client(client):
    global _client
    _client = client

def submit_message(user_message, thread_id, assistant_id, **options):
    try:
        message = _client.beta.threads.messages.create(
            thread_id=thread_id, role="user",
            content=user_message,
            **options
        )
    except Exception as e:
        # 處理 Assistants API 卡在執行狀態的狀況。
        error_message = e.message
        match = re.search(r"run_[\w\d]+", error_message)
        run_id = match.group()
        print('結束前一個執行狀態...')
        run = _client.beta.threads.runs.cancel(
            thread_id=thread_id,
            run_id=run_id
        )
        message = _client.beta.threads.messages.create(
            thread_id=thread_id, role="user",
            content=user_message,
            **options
        )
        
    run = _client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
    )
    return run, message

def wait_on_run(run):
    print('-' * 35)
    while run.status == "queued" or run.status == "in_progress":
        run = _client.beta.threads.runs.retrieve(
            thread_id=run.thread_id,
            run_id=run.id,
        )
        bars = r'/―\|'
        for char in bars:
            print(f'\r{char}', end='')
            time.sleep(0.25)
    print('')
    return run

def get_response(thread_id, **options):
    return _client.beta.threads.messages.list(
        thread_id=thread_id,
        order="asc",
        **options
    )

def update_tools(ass_id, functions_table):
    tools = []
    for function in functions_table:
        tools.append(
            {"type": "function", "function": function['spec']}
        )
    _client.beta.assistants.update(
        assistant_id=ass_id,
        tools=tools
    )
def call_tools(tool_calls, functions_table):
    tool_outputs = []
    for tool in tool_calls:
        func_name = tool.function.name
        arguments = json.loads(tool.function.arguments)
        print(f'{func_name}({arguments})')
        for function in functions_table:
            if function['spec']['name'] == func_name:
                func = function['function']
                tool_outputs.append({
                    'tool_call_id': tool.id,
                    'output': func(**arguments)
                })
                break
    return tool_outputs

def show_html(response):
    for message in response.data:
        for item in message:
            if 'file_ids' in item[0] and len(item[1]) != 0:
                for num,file in enumerate(item[1]):
                    content = _client.files.content(file)
                    # 儲存 HTML
                    content.stream_to_file(f'test{num}.html')
                    # 顯示 HTML
                    html_content = content.content.decode('utf-8')
                    display(HTML(html_content))



def chat_with_functions(user_input, thread_id,  assistant_id):
    run, message = submit_message(user_input, thread_id, assistant_id)
    run = wait_on_run(run)
    if run.status == 'completed':
        response = get_response(thread_id,after=message.id)
        for data in response:
            print(f'AI 回覆：{data.content[0].text.value}')
        show_html(response)
    else:
        print(run.status)
