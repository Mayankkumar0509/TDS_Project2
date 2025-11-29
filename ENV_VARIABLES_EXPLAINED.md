# Environment Variables Explanation

## Your Question: "Why export if I have .env file?"

### ✅ **SHORT ANSWER: You DON'T need to export!**

Your `.env` file is automatically loaded by Python. No need to export from terminal.

---

## How It Works

### **Your Current Setup** ✅
```
.env file:
QUIZ_SECRET=gmk0509

config.py (Line 5):
load_dotenv()  # ← Automatically reads .env

main.py (Line 40):
quiz_secret = os.getenv("QUIZ_SECRET", "")  # ← Gets the value
```

**Result**: Python automatically reads `QUIZ_SECRET=gmk0509` from `.env`

### **Without .env (Alternative)** ⚠️
```bash
# Terminal command (only if NO .env file):
export QUIZ_SECRET="gmk0509"

# Then run server
uvicorn main:app --port 8000
```

**Result**: Python reads from shell environment variable

---

## Why I Suggested Export

When I said to export `QUIZ_SECRET`, I was giving **defensive instructions** for cases where:
1. `.env` file wasn't loaded properly
2. You were testing from different terminals
3. You wanted to ensure the variable was definitely available

**But you already had `.env`**, so exporting was redundant! ✅

---

## Correct Way to Start Server

### **Method 1: Using .env file (YOUR SETUP)** ✅ RECOMMENDED
```bash
cd /home/mayank/TDS/project/LLM_Quiz
source venv/bin/activate
uvicorn main:app --port 8000
```

✅ **Reads from**: `.env` file automatically  
✅ **No export needed**  
✅ **Secure** - secrets not in shell history  

### **Method 2: Using export (FALLBACK)**
```bash
cd /home/mayank/TDS/project/LLM_Quiz
source venv/bin/activate
export QUIZ_SECRET="gmk0509"
uvicorn main:app --port 8000
```

⚠️ **Reads from**: Shell environment  
⚠️ **Requires export**  
⚠️ **Secrets visible** in shell history (`.bash_history`)  

---

## How python-dotenv Works

```python
# config.py
from dotenv import load_dotenv
import os

load_dotenv()  # ← This function:
               # 1. Finds .env file in current directory
               # 2. Reads all KEY=VALUE pairs
               # 3. Adds them to os.environ
               # 4. Now os.getenv() can access them

QUIZ_SECRET = os.getenv("QUIZ_SECRET", "default")
#             └─ Reads from os.environ after load_dotenv()
```

---

## File Hierarchy (What Gets Priority)

1. **Shell export** (if you do `export VAR=value`)
2. **`.env` file** (if you have it)
3. **Default value** (in `os.getenv("VAR", "default")`)

**Example**:
```bash
# If you do: export QUIZ_SECRET="overridden"
# It takes priority over .env file
# Because shell environ is checked first
```

---

## Your .env File ✅

```dotenv
QUIZ_SECRET=gmk0509
AIML_BASE_URL=https://aipipe.org/openai/v1
AIML_MODEL=gpt-4o-mini
AIML_API_KEY=eyJhbGciOiJIUzI1NiJ9...
MAX_FILE_SIZE_MB=5
TIMEOUT_SECONDS=180
LOG_LEVEL=INFO
```

**All these are automatically loaded** when you call `load_dotenv()`

✅ No need to export  
✅ No need to set environment variables  
✅ Just start the server!

---

## Verification

### To check if .env is being read correctly:

```bash
# Method 1: Check if secret is loaded
curl -X POST "http://localhost:8000/solve" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","secret":"gmk0509","url":"https://example.com"}'
# Should return 200 if secret matches

# Method 2: Test with wrong secret
curl -X POST "http://localhost:8000/solve" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","secret":"wrong","url":"https://example.com"}'
# Should return 403 (Forbidden)
```

---

## Summary Table

| Item | Your Setup | With Export | Comment |
|---|---|---|---|
| `.env` file exists | ✅ YES | No | python-dotenv handles it |
| Export needed | ❌ NO | ✅ YES | Only if no .env file |
| Security | ✅ Better | ⚠️ Weaker | .env not in shell history |
| Easier | ✅ YES | ⚠️ Extra step | Just start server |
| Works in Docker | ✅ YES | ❌ NO | export lost in new container |
| Works in CI/CD | ✅ YES | ⚠️ Difficult | .env easier to manage |

---

## FINAL RECOMMENDATION

### Just do this:
```bash
cd /home/mayank/TDS/project/LLM_Quiz
source venv/bin/activate
uvicorn main:app --port 8000
```

✅ Your `.env` will be loaded automatically  
✅ No need to export  
✅ Server will start with `QUIZ_SECRET=gmk0509`  
✅ Your code reads it with `os.getenv("QUIZ_SECRET")`  

**You're all set!** 🎉
