lines = open("main.py", encoding="utf-8").readlines()  
idx = next((i for i, line in enumerate(lines) if "@app.get(\"/delivery-analysis\"" in line), None)  
print(f"Found idx: {idx}") 
