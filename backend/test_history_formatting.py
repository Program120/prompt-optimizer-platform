
def format_history(history_msgs):
    # 将消息按轮次分组 (User + Assistant = 1 Round)
    rounds = []
    current_round = []
    
    for msg in history_msgs:
        if msg.get("role") == "user":
            # 遇到新用户消息，之前的存为一个轮次
            if current_round:
                rounds.append(current_round)
            current_round = [msg]
        else:
            current_round.append(msg)
    
    # 添加最后一个轮次
    if current_round:
        rounds.append(current_round)
    
    history_context_str = ""
    
    # helper
    def format_round(msgs):
        round_content = []
        for m in msgs:
            r = m.get("role")
            c = m.get("content", "")
            if r == "user":
                round_content.append(f"[用户]: {c}")
            elif r == "assistant":
                round_content.append(f"[模型回复]: {c}")
        return "\n".join(round_content)

    # 分离 "之前轮" 和 "上一轮"
    if rounds:
        last_round_msgs = rounds[-1]
        prior_rounds_msgs_list = rounds[:-1]
        
        # 1. 处理之前轮
        if prior_rounds_msgs_list:
            history_context_str += "【之前轮标签】\n"
            for r_msgs in prior_rounds_msgs_list:
                history_context_str += "<round>\n" + format_round(r_msgs) + "\n</round>\n"
        
        # 2. 处理上一轮
        history_context_str += "【上一轮标签】\n"
        history_context_str += "<round>\n" + format_round(last_round_msgs) + "\n</round>"

    return history_context_str

# Test cases
history1 = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there"}
]
print("--- Case 1: 1 Round ---")
print(format_history(history1))

history2 = [
    {"role": "user", "content": "Q1"},
    {"role": "assistant", "content": "A1"},
    {"role": "user", "content": "Q2"},
    {"role": "assistant", "content": "A2"}
]
print("\n--- Case 2: 2 Rounds ---")
print(format_history(history2))

history3 = [
    {"role": "user", "content": "Q1"},
    {"role": "assistant", "content": "A1"},
    {"role": "user", "content": "Q2"}, # No answer for Q2 yet in history? Or partial.
]
print("\n--- Case 3: Partial Last Round ---")
print(format_history(history3))
