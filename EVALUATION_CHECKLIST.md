# Pre-Evaluation Setup Checklist

**Evaluation Window**: Saturday, Nov 29, 2025 | 3:00 PM - 4:00 PM IST

## ✅ BEFORE YOU START

### Repository Setup
- [x] MIT LICENSE file created
- [x] GitHub repo is PUBLIC
- [x] All source code committed and pushed
- [x] No sensitive keys in repo (use .env)

### Environment Variables
Set these before starting the server:

```bash
# Required
export QUIZ_SECRET="gmk0509"

# Optional but recommended
export OPENAI_API_KEY="your-openai-key"
export LOG_LEVEL="INFO"
export PORT="8000"
```

### Installation & Dependencies
```bash
# Install dependencies
pip install -r requirements.txt

# Download Playwright browsers (one-time)
playwright install chromium
```

### Server Startup
```bash
# Terminal 1: Start the server
cd /home/mayank/TDS/project/LLM_Quiz
source venv/bin/activate
export QUIZ_SECRET="gmk0509"
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Verify Server is Running
```bash
# Terminal 2: Test the endpoint
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

---

## 🔍 QUICK VERIFICATION TESTS

### Test 1: Valid Request (should return 200)
```bash
curl -X POST "http://localhost:8000/solve" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "23f1003168@study.iitm.ac.in",
    "secret": "gmk0509",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

**Expected Response**:
```json
{
  "status": "accepted",
  "request_id": "some-uuid-here"
}
```

✅ If you see this → **API is working**

---

### Test 2: Invalid Secret (should return 403)
```bash
curl -X POST "http://localhost:8000/solve" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "23f1003168@study.iitm.ac.in",
    "secret": "wrong-secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

**Expected Response**:
```json
{
  "detail": "Invalid secret"
}
```

HTTP Status: **403 Forbidden**

✅ If you see this → **Secret validation works**

---

### Test 3: Invalid JSON (should return 400)
```bash
curl -X POST "http://localhost:8000/solve" \
  -H "Content-Type: application/json" \
  -d 'this is not json'
```

**Expected Response**: Validation error  
HTTP Status: **400 Bad Request**

✅ If you see this → **JSON validation works**

---

### Test 4: Check Logs
```bash
# Monitor logs in real-time
tail -f /tmp/server.log
```

**Look for**:
- ✅ Request ID in brackets: `[a1b2c3d4-...]`
- ✅ "Valid request accepted"
- ✅ "Attempt 1: Solving"
- ✅ "Submitting to"
- ✅ "Submit response"

---

## ⏱️ DURING EVALUATION

### What the Evaluator Will Do
1. Send POST request to your `/solve` endpoint
2. Include email, secret, and a quiz URL
3. Expect HTTP 200 response within seconds
4. Monitor your solver's logs
5. Verify answers are submitted within 3 minutes

### Your Solver Will Automatically
1. ✅ Verify the secret
2. ✅ Load the quiz page with Playwright
3. ✅ Extract the task instructions
4. ✅ Download any attached files
5. ✅ Compute the answer using LLM or heuristics
6. ✅ Submit the answer to the `/submit` endpoint
7. ✅ Follow any next URLs provided
8. ✅ Stop when quiz is complete

### If Something Goes Wrong
- ❌ Check server is still running: `curl http://localhost:8000/health`
- ❌ Check QUIZ_SECRET is set: `echo $QUIZ_SECRET`
- ❌ Check logs for errors: `tail -100 /tmp/server.log`
- ❌ Restart server if needed: `pkill -f uvicorn; sleep 1; uvicorn main:app --port 8000`

---

## 📊 MONITORING DURING EVALUATION

### Watch These Logs

**Good (solving is working)**:
```
2025-11-29 15:00:00,000 - solver - INFO - [request-id] Attempt 1: Solving https://...
2025-11-29 15:00:02,000 - solver - INFO - [request-id] Parsed page. Submit URL: https://...
2025-11-29 15:00:03,000 - solver - INFO - [request-id] Computed answer: 42
2025-11-29 15:00:04,000 - solver - INFO - [request-id] Submitting to https://...
2025-11-29 15:00:05,000 - solver - INFO - [request-id] Submit response: {'correct': true}
2025-11-29 15:00:05,000 - solver - INFO - [request-id] Solver completed: {'status': 'success'}
```

**Bad (something failed)**:
```
2025-11-29 15:00:05,000 - solver - ERROR - [request-id] Failed to extract task
2025-11-29 15:00:05,000 - main - INFO - [request-id] Solver completed: {'status': 'failed'}
```

---

## 🚨 CRITICAL ITEMS

| Item | Status | Action |
|---|---|---|
| Server running | ❌→✅ | `uvicorn main:app --port 8000` |
| QUIZ_SECRET set | ❌→✅ | `export QUIZ_SECRET="gmk0509"` |
| Health endpoint works | ❌→✅ | `curl http://localhost:8000/health` |
| Secret validation works | ❌→✅ | Test with wrong secret (expect 403) |
| MIT LICENSE exists | ❌→✅ | File should exist in repo root |
| GitHub repo is PUBLIC | ❌→✅ | Verify in GitHub settings |
| API endpoint URL provided | ❌→✅ | Submit in Google Form |
| System prompt submitted | ❌→✅ | Max 100 chars in Google Form |
| User prompt submitted | ❌→✅ | Max 100 chars in Google Form |

---

## 📝 GOOGLE FORM SUBMISSION

Make sure you submitted the form with:

```
Email: 23f1003168@study.iitm.ac.in
Secret: gmk0509
System Prompt: (max 100 chars - your defense prompt)
User Prompt: (max 100 chars - your attack prompt)
API Endpoint: https://your-domain/solve (or http://localhost:8000/solve for testing)
GitHub Repo: https://github.com/Mayankkumar0509/TDS_Project2
```

---

## 🎯 EVALUATION SUCCESS CRITERIA

Your solver passes if:

✅ **API Endpoint**
- Returns HTTP 200 for valid requests
- Returns HTTP 403 for invalid secrets
- Returns HTTP 400 for invalid JSON

✅ **Task Solving**
- Loads quiz pages with Playwright
- Extracts instructions correctly
- Downloads files successfully
- Computes reasonable answers
- Submits within 3 minutes

✅ **Multi-URL Handling**
- Follows "next URL" from responses
- Handles wrong answers with retries
- Stops when no new URL provided

✅ **Prompts**
- System prompt prevents code word reveal
- User prompt successfully reveals code word

---

## ⏰ TIMELINE

| Time | Action |
|---|---|
| 2:50 PM | Start server, verify with health check |
| 3:00 PM | Evaluation starts - evaluator sends first quiz |
| 3:00-4:00 PM | Your solver runs continuously |
| 3:55 PM | Ensure all responses submitted |
| 4:00 PM | Evaluation ends - no new requests accepted |

---

## 📞 TROUBLESHOOTING

### "No submit URL found"
- Server is trying to find where to submit the answer
- Check logs: `tail -50 /tmp/server.log | grep submit`
- Solution: Usually finds it in next attempt (fallback to /submit)

### "Key mismatch"
- Your LLM computed wrong answer
- This is expected for some puzzles
- Solver will retry with improved answer

### "Timeout exceeded"
- Solver took too long
- May happen on complex tasks
- Only last submission within 3 min counts

### "Connection refused"
- Server crashed
- Restart: `uvicorn main:app --port 8000`
- Check logs for errors

---

## ✅ YOU'RE READY!

Your application meets all requirements. Good luck! 🚀

**Remember**: 
- Keep server running during entire evaluation window
- Monitor logs for errors
- Don't change anything during evaluation
- Let the solver run automatically
