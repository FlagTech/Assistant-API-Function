import time
import openai
import json
import re
from IPython.display import HTML

_client = None
def set_client(client):
    global _client
    _client = client

def submit_message(assistant_id, thread_id, user_message, **options):
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

def input_and_run(input, thread_id, assistant_id, **args):
    message = _client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=input,
        **args
    )
    run = _client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )

    return message, run

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

def show_html(messages):
    # 找出有文件內容的對話物件
    index = len(messages.data) - 1
    # 找到文件位置
    file_index = messages.data[index].content[0].text.annotations

    if len(file_index) != 0:
        file_ids = file_index[0].file_path.file_id
        content = _client.files.content(file_ids)
        # 儲存 HTML
        content.stream_to_file('test.html')
        # 顯示 HTML
        html_content = content.content.decode('utf-8')
        display(HTML(html_content))

def handle_model_response(response):
    for item in response.data[0].content:
        item_str = str(item)
        #檢查回覆物件的文字是否符合特定物件名稱
        if 'MessageContentImageFile' in item_str:
            #提取模型圖片輸出
            response_image_id = item.image_file.file_id
            response_image = _client.files.content(response_image_id)
            image_data_bytes = response_image.read()
            #儲存圖片
            with open("response_img.png", "wb") as file:
                file.write(image_data_bytes)
                print(f'已儲存模型回覆之圖片：response_img.png({response_image_id})')
        elif 'MessageContentText' in item_str:
            #處理annotations
            if item.text.annotations:
                for TextAnnotationFilePath in item.text.annotations:
                    print('文字輸出備註中包含檔案：',
                          TextAnnotationFilePath.file_path.file_id) 
            #提取模型純文字輸出
            response_text = item.text.value
    return response_text

def chat_with_functions(user_input, ass_id, thread_id):
    if not user_input: # 沒有輸入就結束對話
        return thread_id
    else:              # 在既有的討論串上繼續對話
        run, message = submit_message(ass_id, thread_id, user_input)
    print(ass_id)
    print(thread_id)
    print(run.id)
    
    done = False
    while not done:
        run = wait_on_run(run) # 等待產生回覆
        if run.status == 'requires_action':
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            outputs = call_tools(tool_calls, tools_table)
            print(outputs)
            # 把結果傳回
            run = _client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs = outputs
            )
        elif run.status == 'completed':
            done = True

    # 處理模型回覆
    response = get_response(thread_id, after=message.id)
    response = handle_model_response(response)
    return response
